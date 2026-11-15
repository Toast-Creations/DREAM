"""Limit learned state to LoRA A/B tensors and restore those tensors between trials.

The base model is frozen before adapter attachment. Each independent condition
starts with the same saved adapter values for its seed. Fresh optimizers are
created in training.learn(), so no optimizer moments are part of this snapshot.
Parameter rollback is a scientific-state control, not an OS sandbox, a reset of
all possible Python objects, or cleanup guaranteed after process termination.
"""
from contextlib import contextmanager
import hashlib
import torch
from dream_core.steering import assert_no_dream_hooks


def attach_adapter(base, cfg):
    """Attach zero-dropout causal-LM LoRA to a base that is already fully frozen."""
    from peft import LoraConfig, TaskType, get_peft_model
    if any(p.requires_grad for p in base.parameters()):
        raise RuntimeError("Freeze every base parameter before attaching LoRA")
    # Rank/alpha control the low-rank adapter's parameterization and scale. They
    # are separate from activation-steering lambda and learning-rate multiplier
    # eta. bias='none' excludes otherwise trainable bias parameters from the trial.
    model = get_peft_model(base, LoraConfig(r=cfg["rank"], lora_alpha=cfg["alpha"],
        target_modules=cfg["target_modules"], lora_dropout=0.0, bias="none", task_type=TaskType.CAUSAL_LM))
    adapter_parameters(model)
    return model


def adapter_parameters(model):
    """Require exactly LoRA A/B names to be trainable; return their parameters.

    This is a bidirectional check: a trainable base tensor AND an unexpectedly
    frozen LoRA tensor are rejected. It intentionally supports one declared
    adapter policy, not every PEFT adapter type or multi-adapter arrangement.
    """
    result = {}
    for name, parameter in model.named_parameters():
        allowed = ".lora_A." in name or ".lora_B." in name
        if parameter.requires_grad != allowed:
            raise RuntimeError("Trainability differs from the adapter allowlist: " + name)
        if allowed:
            result[name] = parameter
    if not result:
        raise RuntimeError("No trainable LoRA A/B parameters")
    return result


def snapshot(model):
    """Copy eligible parameter values to independent CPU tensors without a graph.

    clone() prevents the snapshot from sharing storage with live parameters;
    otherwise an optimizer could mutate the supposed initial state as well.
    """
    return {name:p.detach().cpu().clone() for name,p in adapter_parameters(model).items()}


@torch.no_grad()
def restore(model, saved):
    """Validate and copy adapter values back, then demand elementwise equality.

    no_grad() makes restoration a state reset rather than a learning operation.
    Keeping the original tensor dtype allows exact finite-value comparison,
    rather than accepting a numerical tolerance that could accumulate drift.
    """
    current = adapter_parameters(model)
    if set(current) != set(saved):
        raise RuntimeError("Adapter snapshot key set differs")
    for name, value in saved.items():
        parameter = current[name]
        if parameter.shape != value.shape or parameter.dtype != value.dtype or not torch.isfinite(value).all():
            raise RuntimeError("Invalid snapshot tensor")
        parameter.copy_(value.to(parameter.device))
    if any(not torch.equal(p.detach().cpu(), saved[name]) for name,p in current.items()):
        raise RuntimeError("Adapter rollback did not restore exact values")


def parameter_hash(named_parameters):
    """Hash sorted parameter names, shape/dtype, and raw contiguous CPU bytes.

    The byte view supports BF16 without converting its values to another dtype.
    Full base hashing can be expensive: each check reads/copies all included
    parameters. This does not hash buffers, caches, optimizer state, or origin.
    """
    digest = hashlib.sha256()
    for name, parameter in sorted(named_parameters):
        value = parameter.detach().cpu().contiguous()
        digest.update(name.encode())
        digest.update(str((tuple(value.shape), value.dtype)).encode())
        digest.update(value.view(torch.uint8).numpy().tobytes())
    return digest.hexdigest()


def adapter_hash(model):
    """Identify the current allowlisted adapter parameter values."""
    return parameter_hash(adapter_parameters(model).items())


def base_hash(model):
    """Identify named parameters outside the LoRA A/B set, not all model buffers."""
    adapter_names = set(adapter_parameters(model))
    return parameter_hash((n,p) for n,p in model.named_parameters() if n not in adapter_names)


def displacement(model, before):
    """Return the FP32 Euclidean distance from initial adapter parameters.

    This is an end-of-phase diagnostic, not a matched-norm control or a sum of
    optimizer step lengths. An equal final distance does not imply equal paths.
    """
    return sum(float((p.detach().float().cpu()-before[n].float()).square().sum())
               for n,p in adapter_parameters(model).items()) ** .5


@contextmanager
def reversible_trial(model, before):
    """Reset before admission and again after the trial, including Python errors.

    The experiment orchestrator separately compares adapter/base hashes after
    each trial. If the initial restore fails, the body is never admitted. If
    cleanup fails, let the error stop the queue rather than continue with an
    unverifiable state. A hard process kill cannot run this finally block.
    """
    restore(model, before)
    try:
        yield
    finally:
        # Clear gradient tensors as well as restoring values. Cache/context and
        # optimizer isolation come from fresh calls/objects in the other modules.
        model.zero_grad(set_to_none=True)
        restore(model, before)
        model.eval()
        assert_no_dream_hooks(model)
