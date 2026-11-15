"""Temporarily perturb one transformer's hidden activations, without editing weights.

The intervention at a selected position is ``h' = h + lambda * ||h||_2 * v``:
``v`` is a fixed unit direction, and lambda is a dimensionless fraction of the
current hidden-state norm. It is not a learning rate or a wall-clock duration.
The norm is detached from autograd; the hidden state being modified is not.

Two execution paths deliberately use different position and timing policies:

* DREAM 1 generation: steer the final position in each forward call. The legacy
  ramp/hold/taper uses the planned generated-token budget as its time axis; a
  V1.2.0 ``schedule_spec`` (see schedules.py) uses absolute generated tokens.
* DREAM 2 training: steer the explicit causal-predictor mask supplied by the
  training code. The caller uses a constant lambda, without the generation ramp.

V1.2.0 adds signed generation strength (a negative lambda pushes against the
direction) and configurable trip schedules. Training remains constant and
nonnegative; a training-step schedule is not implemented.
"""
import json
import math
from pathlib import Path
import weakref
import torch
from .contracts import finite_number
from .ledger import file_hash
from .schedules import dose, end_token, legacy_linear, validate_spec

# Track only steering hooks owned by this module, keyed by model identity.
# Weak keys avoid keeping a discarded model alive solely through the registry.
# This is a guard against accidental nesting, not an inventory of third-party
# hooks or an isolation boundary for code that can modify the Python process.
_ACTIVE = weakref.WeakKeyDictionary()


def assert_no_dream_hooks(model):
    """Reject a model with an experiment-owned steering context still active."""
    if _ACTIVE.get(model, 0):
        raise RuntimeError("An experiment-owned steering hook is still active")


def blocks(model):
    """Find an explicitly supported decoder block list, including PEFT wrappers.

    Architecture paths are allowlisted rather than guessed by walking arbitrary
    modules. A returned list establishes where to attach the hook; integration
    tests must still verify semantics on the exact model architecture in use.
    """
    roots = [model]
    if hasattr(model, "get_base_model"):
        roots.append(model.get_base_model())
    for root in roots:
        for path in (("model", "layers"), ("transformer", "h"), ("model", "decoder", "layers")):
            obj = root
            try:
                for name in path:
                    obj = getattr(obj, name)
                if len(obj):
                    return list(obj)
            except (AttributeError, TypeError):
                pass
    raise ValueError("Unsupported transformer architecture; add and test an explicit block path")


def resolve_layer(model, layer):
    """Convert a Python-style layer index into an absolute decoder block index.

    For example, -1 selects the last block and -8 the eighth from the end. The
    resolved index is also used to bind a saved direction to its extraction site.
    """
    count = len(blocks(model))
    resolved = layer if layer >= 0 else count + layer
    if not 0 <= resolved < count:
        raise ValueError("Steering layer is outside the model")
    return resolved


def hidden_tensor(output):
    """Extract a block's [batch, sequence, hidden] tensor or reject its layout.

    Supported blocks return either a tensor directly or a tuple whose first
    member is that tensor. Steering preserves any remaining tuple members.
    """
    hidden = output if torch.is_tensor(output) else output[0] if isinstance(output, tuple) and output else None
    if not torch.is_tensor(hidden) or hidden.ndim != 3:
        raise TypeError("Expected [batch, sequence, hidden] block output")
    return hidden


def validate_vector(vector, hidden_size):
    """Validate an already normalized, finite direction and detach its gradients.

    Refusing to silently normalize an input keeps accidental scale changes from
    being hidden. The direction is fixed research input, not an optimized tensor.
    FP32 validation precedes conversion to the activation's device and dtype.
    """
    vector = torch.as_tensor(vector, dtype=torch.float32).detach()
    if vector.ndim != 1 or vector.numel() != hidden_size or not torch.isfinite(vector).all():
        raise ValueError("Steering vector has incompatible dimensions or non-finite entries")
    if not math.isclose(float(vector.norm()), 1.0, rel_tol=1e-4, abs_tol=1e-4):
        raise ValueError("Steering vector must already be unit normalized")
    return vector


class MaskedSteerer:
    """Own one temporary forward hook and remove it when its context exits.

    Args:
        model: Supported causal language model, possibly wrapped with LoRA.
        layer: Decoder block index; negative indices count from the end.
        vector: Finite unit vector with one entry per hidden dimension.
        strength: Lambda, in [0, 1] for training and [-1, 1] for generation.
            Experiment configs impose tighter bounds. With a unit vector, its
            perturbation norm is lambda times the hidden norm, before rounding.
        mask: [batch, sequence] predictor-position mask for teacher-forced input.
        generation: Select the final-position generation policy instead of mask.
        max_new_tokens: Planned generation budget used to normalize schedule time.
        schedule: Enable the legacy V1.1 generation curve; unused in training mode.
        schedule_spec: V1.2.0 absolute-token trip spec; exclusive with schedule.
        prefill_positions: V1.5.0, generation only. Prompt token indices to steer at the
            prefill forward (the "introduced idea" is read under the intervention). None
            (the default) keeps the final-position policy bit-for-bit.
        prefill_strength: lambda for those positions at prefill; required with positions.
        prompt_tokens: expected prompt length; the prefill forward must match it exactly.

    ``step`` counts hooked generation forwards, starting with prompt prefill.
    ``trace`` records the applied scalar lambda per such call, including zeros.
    It does not record activation norms, physical time, or a training-dose trace.
    ``comedown_complete`` reports whether a trip spec reached its zero tail.
    Callers must use the context manager; construction alone installs no hook.
    """
    def __init__(self, model, layer, vector, strength, *, mask=None, generation=False,
                 max_new_tokens=1, schedule=False, schedule_spec=None, record_norms=False,
                 prefill_positions=None, prefill_strength=None, prompt_tokens=None):
        self.model = model
        self.layer = resolve_layer(model, layer)
        self.vector = validate_vector(vector, model.config.hidden_size)
        # Signed strength is a generation-only research dial; DREAM 2 training
        # keeps its reviewed nonnegative contract.
        self.strength = finite_number(strength, "steering strength", -1 if generation else 0, 1)
        if schedule and schedule_spec is not None:
            raise ValueError("Choose the legacy schedule or a trip spec, not both")
        self.schedule_spec = validate_spec(schedule_spec) if schedule_spec is not None else None
        self.mask = mask
        self.generation = generation
        self.max_new_tokens = max_new_tokens
        self.schedule = schedule
        self.step = 0
        self.trace = []
        # V1.4.0 (DREAM3 logging): optional unperturbed final-position ||h||_2 per
        # generation forward, aligned with trace. Off by default, so earlier paths are unchanged.
        self.record_norms = record_norms
        self.norm_trace = []
        self.handle = None
        if not generation and mask is None:
            raise ValueError("Training steering requires an explicit predictor mask")
        # V1.5.0 continuity: steer the introduced text while it is read. Its perturbed keys and
        # values stay in the KV cache, so later tokens attend to a steered encoding even after
        # the decode dose has returned to zero.
        self.prefill_positions = None
        if prefill_positions is not None:
            if not generation:
                raise ValueError("Prefill positions are a generation-only policy")
            if type(prompt_tokens) is not int or prompt_tokens < 1:
                raise ValueError("Prefill steering needs the exact prompt length")
            positions = sorted(set(int(i) for i in prefill_positions))
            if not positions or positions[0] < 0 or positions[-1] >= prompt_tokens:
                raise ValueError("Prefill positions must be nonempty and inside the prompt")
            self.prefill_positions = positions
            self.prefill_strength = finite_number(prefill_strength, "prefill strength", -1, 1)
            self.prompt_tokens = prompt_tokens
        self.prefill_trace = None

    def _hook(self, module, inputs, output):
        """Return perturbed activations while preserving the block output shape."""
        hidden = hidden_tensor(output)
        if not torch.isfinite(hidden).all():
            raise FloatingPointError("Non-finite activation")
        strength = self.strength
        if self.generation:
            # Prefill produces the first next-token distribution; count it explicitly.
            if self.schedule_spec is not None:
                # Absolute generated-token time: the curve does not stretch with
                # the answer cap. The trace shows where an early EOS cut it off.
                strength *= dose(self.step, self.schedule_spec)
            elif self.schedule:
                # Time here means position within the PLANNED token budget, not
                # elapsed seconds or progress toward an observed answer length.
                # Hardcoded normalized breakpoints:
                #   [0, .15): linear rise from zero toward peak strength;
                #   [.15, .60): hold at peak strength;
                #   [.60, .90): linear taper to zero; [.90, ...): zero.
                # Discrete calls need not land exactly on any breakpoint. In
                # particular, a scheduled one-token run only sees progress=0
                # and therefore receives zero steering. Early EOS can truncate
                # the curve before its peak or taper; the trace makes this visible.
                strength *= legacy_linear(self.step, self.max_new_tokens)
            self.step += 1
            # During prefill, previous prompt positions are left alone. During
            # ordinary cached decoding there is typically one new position.
            # This counts forward calls, not beams or individual batch examples;
            # callers use the simple generation policy in modeling.generate.
            mask = torch.zeros(hidden.shape[:2], dtype=torch.bool, device=hidden.device)
            if self.prefill_positions is not None and self.step == 1:
                # Prefill forward (step was just incremented from 0): steer the introduced span,
                # and not the final position unless it lies inside the span.
                if hidden.shape[1] != self.prompt_tokens:
                    raise RuntimeError("Prefill arrived in a different shape than the tokenized prompt")
                strength = self.prefill_strength
                mask[:, self.prefill_positions] = True
                self.prefill_trace = {"positions": list(self.prefill_positions), "strength": float(strength)}
            else:
                mask[:, -1] = True
            self.trace.append(float(strength))
            if self.record_norms:
                self.norm_trace.append(float(torch.linalg.vector_norm(hidden[0, -1].detach().float())))
        else:
            # All teacher-forced positions arrive together. The training caller
            # supplies h[t] positions whose next-token labels are supervised;
            # selecting target-token positions directly would be off by one.
            mask = torch.as_tensor(self.mask, dtype=torch.bool, device=hidden.device)
            if mask.shape != hidden.shape[:2]:
                raise ValueError("Predictor mask shape differs from activation positions")
        if strength == 0:
            # Keep the identical hook path for zero-dose controls, but return
            # the original output without floating-point perturbation arithmetic.
            return output
        # Use the unperturbed activation norm as a fixed scale for this forward.
        # Detaching ONLY this scale prevents gradients through ||h||. The sum
        # below keeps hidden attached: downstream loss still backpropagates
        # through the perturbed forward to eligible upstream adapter parameters.
        norms = torch.linalg.vector_norm(hidden.detach().float(), dim=-1, keepdim=True)
        delta = strength * norms.to(hidden.dtype) * self.vector.to(hidden.device, hidden.dtype)
        # Broadcasting: delta is [batch, sequence, hidden]; the mask expands from
        # [batch, sequence] to [batch, sequence, 1]. Avoid an in-place activation
        # edit so autograd can retain tensors needed for the backward pass.
        modified = hidden + delta * mask.unsqueeze(-1).to(hidden.dtype)
        if not torch.isfinite(modified).all():
            raise FloatingPointError("Steering produced non-finite activations")
        return modified if torch.is_tensor(output) else (modified,) + output[1:]

    @property
    def comedown_complete(self):
        """True once a trip spec's dose has returned to zero (a release rung: reached
        its end level); None if not a trip."""
        if self.schedule_spec is None or end_token(self.schedule_spec) is None:
            return None
        return self.step > end_token(self.schedule_spec)

    def __enter__(self):
        """Install one hook after checking that a prior context has been removed."""
        assert_no_dream_hooks(self.model)
        self.handle = blocks(self.model)[self.layer].register_forward_hook(self._hook)
        _ACTIVE[self.model] = 1
        return self

    def __exit__(self, kind, value, tb):
        """Remove the hook on normal exit or Python exception; propagate errors.

        Removing a hook does not undo weight updates or reset a generation's KV
        cache. Trial rollback is owned by plasticity.reversible_trial; clean
        evaluation/integration starts another generation call without past state.
        A killed process does not get to execute Python context-manager cleanup.
        """
        if self.handle is not None:
            self.handle.remove()
            self.handle = None
        _ACTIVE.pop(self.model, None)
        return False


@torch.no_grad()
def build_vector(model, tokenizer, pairs, layer, max_tokens, poles=("divergent", "convergent")):
    """Extract mean(toward pole) - mean(away pole) at a clean block's last position.

    ``poles`` names the (toward, away) keys in each pair. The default preserves
    the V1.1 divergent-minus-convergent contrast; V1.2.0 decategorization uses
    ("decategorized", "categorical").

    ``pairs`` supplies matched contrast prompts; these labels name prompt groups,
    not independently verified mental states. Last-position pooling occurs after
    rendering the model's chat template, rather than averaging all prompt tokens.
    The result can reflect wording, topic, or length confounds. Held-out checks
    are needed before interpreting this direction as a specific behavior signal.
    """
    from .modeling import render_chat
    assert_no_dream_hooks(model)
    model.eval()
    toward, away = poles
    if toward == away:
        raise ValueError("Contrast poles must differ")
    rows = {toward: [], away: []}
    captured = []
    def capture(module, inputs, output):
        # Extraction observes activations without perturbing them. Move detached
        # FP32 rows to CPU so the contrast computation retains no autograd graph.
        captured.append(hidden_tensor(output)[:, -1, :].detach().float().cpu())
    handle = blocks(model)[resolve_layer(model, layer)].register_forward_hook(capture)
    try:
        for pair in pairs:
            for label in rows:
                encoded = tokenizer(render_chat(tokenizer, pair[label]), return_tensors="pt", add_special_tokens=False)
                if encoded["input_ids"].shape[1] > max_tokens:
                    raise ValueError("Contrast prompt exceeds token cap")
                before = len(captured)
                device = model.get_input_embeddings().weight.device
                model(**{k:v.to(device) for k,v in encoded.items()}, use_cache=False)
                if len(captured) != before + 1:
                    # More or fewer captures would silently mix extraction sites
                    # or forwards. Reject that architecture/execution mismatch.
                    raise RuntimeError("Capture hook did not fire exactly once")
                rows[label].append(captured[-1].squeeze(0))
    finally:
        # Extraction uses its own observation hook; always remove it, including
        # on tokenizer/context errors. It is not an _ACTIVE steering context.
        handle.remove()
    if not rows[toward] or len(rows[toward]) != len(rows[away]):
        raise ValueError("Contrast pairs must be nonempty and matched")
    direction = torch.stack(rows[toward]).mean(0) - torch.stack(rows[away]).mean(0)
    if not torch.isfinite(direction).all() or direction.norm() < 1e-8:
        raise ValueError("Degenerate steering contrast")
    return validate_vector(direction / direction.norm(), model.config.hidden_size)


def load_vector(path, model, model_identity, layer, kind=None):
    """Load a direction bound to the exact model-manifest hash and resolved layer.

    This catches accidentally reusing another model or layer's artifact. Content
    identity checks do not authenticate a file's upstream creator or establish
    that its behavioral interpretation has been experimentally validated.
    """
    artifact = json.loads(Path(path).read_text(encoding="utf-8"))
    if artifact["model_manifest_sha256"] != model_identity or artifact["layer"] != resolve_layer(model, layer):
        raise ValueError("Steering vector belongs to a different model snapshot or layer")
    if kind is not None and artifact.get("kind") != kind:
        # V1.2.0 artifacts name their direction; a mislabeled file must not run
        # under another arm's condition label.
        raise ValueError(f"Steering vector kind {artifact.get('kind')!r} is not the required {kind!r}")
    return validate_vector(artifact["vector"], model.config.hidden_size)
