"""Model runtime: per-episode LoRA training, W / W+A / W+X evaluation, reset checks.

Conditions see byte-identical prompts (render.user_prompt + one common system instruction).
Only the active parameters differ: W = adapter disabled, W+A = this episode's adapter,
W+X = the adapter trained for a different episode of the same family (derangement).
"""
import hashlib
import json
import random
import re
import time

from . import render

SYSTEM_PROMPTS = {
    # Candidate common instructions, selected on development cases using condition W only.
    "S0": None,
    "S1": ("You choose plans in a rule-based world. Read the goal and the current state first. "
           "Check each option step by step against the rules: a step is allowed only if all of its requirements hold "
           "at that moment. A correction in the query replaces the packet's fact it names. "
           "Reject options that break a rule or do not reach the goal; the goal may already hold. "
           "Among the remaining options choose the one with the lowest total cost."),
    "S2": ("Decide from the stated facts only. Goal, current state and any correction in the query take precedence over "
           "habits from the solved examples. An option is correct only if every step is allowed when taken, the goal holds "
           "at the end, and no other valid option costs less."),
}

UNRELATED = [
    ("Which of these animals is a mammal?", ["trout", "dolphin", "sparrow", "frog"], 1),
    ("Which number is prime?", ["21", "27", "29", "33"], 2),
    ("Which planet is closest to the Sun?", ["Venus", "Mars", "Earth", "Mercury"], 3),
    ("Water freezes at what temperature in degrees Celsius at sea level?", ["0", "10", "-10", "100"], 0),
    ("Which word is a synonym of 'rapid'?", ["slow", "quick", "heavy", "quiet"], 1),
    ("How many sides does a hexagon have?", ["5", "7", "6", "8"], 2),
    ("Which of these is a primary colour of light in the RGB model?", ["green", "purple", "orange", "brown"], 0),
    ("What is 12 multiplied by 3?", ["36", "34", "38", "32"], 0),
    ("Which instrument has keys, hammers and strings?", ["flute", "drum", "trumpet", "piano"], 3),
    ("Which gas do plants take in for photosynthesis?", ["oxygen", "nitrogen", "carbon dioxide", "helium"], 2),
    ("Which month comes directly after April?", ["March", "May", "June", "July"], 1),
    ("Which of these is the largest ocean?", ["Atlantic", "Indian", "Arctic", "Pacific"], 3),
]
UNRELATED_IDS = ["A", "B", "C", "D"]


def unrelated_prompt(i):
    q, opts, _ = UNRELATED[i]
    lines = [q] + [f"[{k}] {o}" for k, o in zip(UNRELATED_IDS, opts)] + ["", render.ANSWER_LINE]
    return "\n".join(lines)


def parse_choice(text, valid_ids):
    """Strict: the reply must contain one JSON object whose 'choice' is a listed option ID."""
    found = re.findall(r"\{[^{}]*\}", text)
    if len(found) != 1:
        return None
    try:
        obj = json.loads(found[0])
    except ValueError:
        return None
    choice = obj.get("choice") if isinstance(obj, dict) else None
    return choice if isinstance(choice, str) and choice in valid_ids else None


def augment(q, rng):
    """Relabel and reorder a support example's options; the answer follows its plan."""
    import copy
    from .generate import ids
    q = copy.deepcopy(q)
    answer_plan = next(c["plan"] for c in q["candidates"] if c["id"] == q["answer"])
    plans = [c["plan"] for c in q["candidates"]]
    rng.shuffle(plans)
    q["candidates"] = [{"id": i, "plan": p} for i, p in zip(ids(rng, len(plans)), plans)]
    q["answer"] = next(c["id"] for c in q["candidates"] if c["plan"] == answer_plan)
    return q


TRAIN_CONTEXTS = ("loo", "rules_only")


def support_prompt(ep, s, context):
    """'loo': packet with the other solved examples (V1.6.0 method). 'rules_only' (V1.6.1 diagnostic):
    rules and fixed facts only, no solved examples. Evaluation always uses the full packet."""
    if context == "loo":
        return render.user_prompt(ep, s, exclude_support=s["qid"])
    if context == "rules_only":
        return render.user_prompt(ep, s, include_support=False)
    raise ValueError(context)


def training_examples(ep, n_aug, seed, context="loo"):
    """Each support example (plus relabeled variants) is a training query in the chosen context.

    Only support examples are used. Evaluation queries never enter training (tested)."""
    rng = random.Random(seed)
    out = []
    for s in ep["support"]:
        variants = [s] + [augment(s, rng) for _ in range(n_aug)]
        for v in variants:
            v = dict(v, qid=s["qid"])
            out.append({"source_qid": s["qid"], "prompt": support_prompt(ep, v, context),
                        "target": json.dumps({"choice": v["answer"]}), "answer": v["answer"]})
    return out


SCHEDULES = ("shuffle", "each_source_once")


def training_schedule(examples, train_cfg, rng):
    """'shuffle' (V1.6.0 default): repeated shuffled passes over all instances, truncated to ``steps``.
    'each_source_once' (V1.6.2): ``steps`` must be a multiple of the number of source examples; each epoch
    visits every source example exactly once (shuffled), using one of its variants (original or a relabeled
    copy) chosen by the seeded rng. Guarantees every source example is trained on."""
    mode = train_cfg.get("schedule", "shuffle")
    steps = train_cfg["steps"]
    if mode == "shuffle":
        order = []
        while len(order) < steps:
            batch = examples[:]
            rng.shuffle(batch)
            order += batch
        return order[:steps]
    if mode != "each_source_once":
        raise ValueError(mode)
    by_source = {}
    for e in examples:
        by_source.setdefault(e["source_qid"], []).append(e)
    sources = sorted(by_source)
    if steps % len(sources):
        raise ValueError(f"steps ({steps}) must be a multiple of the {len(sources)} source examples")
    order = []
    for _ in range(steps // len(sources)):
        epoch = sources[:]
        rng.shuffle(epoch)
        order += [rng.choice(by_source[s]) for s in epoch]
    return order


class Runtime:
    def __init__(self, model_cfg, lora_cfg, system_key, task_probe=None):
        from dream_core.modeling import load_local_model
        model, tok, manifest = load_local_model(model_cfg)
        self._setup(model, tok, manifest, lora_cfg, system_key, task_probe)

    @classmethod
    def from_model(cls, model, tok, lora_cfg, system_key, task_probe=None):
        """Test entry point: an already-loaded (e.g. tiny random) model and tokenizer."""
        rt = cls.__new__(cls)
        rt._setup(model, tok, {"revision": "test"}, lora_cfg, system_key, task_probe)
        return rt

    def _setup(self, model, tok, manifest, lora_cfg, system_key, task_probe):
        import torch
        self.torch = torch
        self.model, self.tok, self.manifest = model, tok, manifest
        self.system = SYSTEM_PROMPTS[system_key]
        self.lora_cfg = lora_cfg
        self.n_base_params = sum(p.numel() for p in self.model.parameters())
        # Probe inputs: a fixed plain prompt and (when given) a development-task prompt rendered exactly
        # as in evaluation. Reference logits come from the clean load, before any adapter injection.
        self.probes = {"reference": self.render_plain("Name one colour of the sky on a clear day.")}
        if task_probe is not None:
            self.probes["task"] = self.render(task_probe)
        self.reference_logits = {k: self.logits(self.model, t) for k, t in self.probes.items()}
        from peft import LoraConfig, get_peft_model
        self.LoraConfig = LoraConfig
        self.peft = get_peft_model(self.model, self._config(), adapter_name="null")
        self._freeze_all()
        self.base_fingerprint = self.fingerprint()

    def _config(self):
        c = self.lora_cfg
        return self.LoraConfig(r=c["rank"], lora_alpha=c["alpha"], lora_dropout=0.0, bias="none",
                               target_modules=c["targets"], task_type="CAUSAL_LM")

    def _freeze_all(self):
        for p in self.peft.parameters():
            p.requires_grad_(False)

    def base_params(self):
        return [(n, p) for n, p in self.peft.named_parameters() if "lora_" not in n]

    def fingerprint(self):
        """Fast per-tensor fingerprint of every base weight (float64 sum, abs-sum, and edge values)."""
        torch = self.torch
        h = hashlib.sha256()
        with torch.no_grad():
            for n, p in self.base_params():
                flat = p.detach().reshape(-1)
                total = torch.zeros((), dtype=torch.float64, device=flat.device)
                absolute = torch.zeros((), dtype=torch.float64, device=flat.device)
                for i in range(0, flat.numel(), 1 << 24):  # chunked: no full-size float64 copy
                    chunk = flat[i:i + (1 << 24)].double()
                    total += chunk.sum(); absolute += chunk.abs().sum()
                vals = [float(total), float(absolute)]
                edge = flat[:4].float().cpu().tolist() + flat[-4:].float().cpu().tolist()
                h.update(json.dumps([n, vals, edge]).encode())
        return h.hexdigest()

    def full_hash(self):
        """Exact sha256 over every base weight's bytes (slow; run at stage start and end)."""
        torch = self.torch
        h = hashlib.sha256()
        with torch.no_grad():
            for n, p in self.base_params():
                h.update(n.encode())
                h.update(p.detach().contiguous().view(torch.uint8).cpu().numpy().tobytes())
        return h.hexdigest()

    def render(self, user):
        from dream_core.modeling import render_chat
        return render_chat(self.tok, user, system=self.system, enable_thinking=False)

    def logits(self, model, text):
        torch = self.torch
        ids = self.tok(text, return_tensors="pt", add_special_tokens=False).input_ids.to(self.model.device)
        with torch.no_grad():
            return model(input_ids=ids, use_cache=False).logits[0, -1].float().cpu()

    def render_plain(self, user):
        from dream_core.modeling import render_chat
        return render_chat(self.tok, user, system=None, enable_thinking=False)

    def removal_detail(self):
        """Per probe: max |logit difference| between the adapter-removed model and the clean load (same input).

        Checked both with adapters disabled and with only the zero-update "null" adapter active."""
        out = {}
        with self.peft.disable_adapter():
            for k, t in self.probes.items():
                out[f"{k}/disabled"] = float((self.logits(self.peft, t) - self.reference_logits[k]).abs().max())
        if self.peft.active_adapter != "null":
            raise RuntimeError(f"unexpected active adapter {self.peft.active_adapter}")
        for k, t in self.probes.items():
            out[f"{k}/null"] = float((self.logits(self.peft, t) - self.reference_logits[k]).abs().max())
        return out

    def removal_check(self):
        return max(self.removal_detail().values())

    def adapter_probe(self, name):
        """Task-probe logits with adapter ``name`` active (used for the save/load functional check)."""
        self.peft.set_adapter(name)
        self._freeze_all()
        key = "task" if "task" in self.probes else "reference"
        return self.logits(self.peft, self.probes[key])

    # ------------------------------------------------------------ training

    def train_adapter(self, ep, name, seed, train_cfg):
        torch = self.torch
        torch.manual_seed(seed)
        self.peft.add_adapter(name, self._config())
        self.peft.set_adapter(name)
        self._freeze_all()
        params = [p for n, p in self.peft.named_parameters() if f".{name}." in n and "lora_" in n]
        for p in params:
            p.requires_grad_(True)
        assert params and all(not p.requires_grad for _, p in self.base_params())
        context = train_cfg.get("context", "loo")
        examples = training_examples(ep, train_cfg["n_aug"], seed, context)
        diag_before = {c: self.support_diagnostics(ep, c) for c in TRAIN_CONTEXTS}  # zero-delta adapter = base
        assert not ({e["source_qid"] for e in examples} & {q["qid"] for q in ep["queries"]})
        opt = torch.optim.AdamW(params, lr=train_cfg["lr"], weight_decay=train_cfg.get("weight_decay", 0.0))
        rng = random.Random(seed + 1)
        self.peft.train()
        self.model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
        start, tokens, losses, steps_log = time.time(), 0, [], []
        order = training_schedule(examples, train_cfg, rng)
        for step, ex in enumerate(order[:train_cfg["steps"]]):
            ids, n_target, choice_pos = self.encode(ex["prompt"], ex["target"], ex["answer"])
            logits = self.peft(input_ids=ids, use_cache=False, logits_to_keep=n_target + 1).logits[0, :-1].float()
            labels = ids[0, -n_target:]
            per_token = torch.nn.functional.cross_entropy(logits, labels, reduction="none")
            loss = per_token.mean()
            loss.backward()
            grad_norm = float(torch.sqrt(sum((p.grad.float() ** 2).sum() for p in params if p.grad is not None)))
            opt.step(); opt.zero_grad(set_to_none=True)
            tokens += ids.shape[1]
            losses.append(float(loss.detach()))
            steps_log.append({"loss": losses[-1], "choice_nll": float(per_token[choice_pos].sum().detach()),
                              "grad_norm": grad_norm, "source_qid": ex["source_qid"]})
        self.model.gradient_checkpointing_disable()
        train_seconds = round(time.time() - start, 2)
        self.peft.eval()
        for p in params:
            p.requires_grad_(False)
        from peft import get_peft_model_state_dict
        diag_after = {c: self.support_diagnostics(ep, c) for c in TRAIN_CONTEXTS}
        delta = self.delta_norms(name)
        trained_logits = self.adapter_probe(name)
        state = {k: v.detach().cpu().contiguous() for k, v in get_peft_model_state_dict(self.peft, adapter_name=name).items()}
        # PEFT selects keys by substring; insist the export is exactly this adapter's A/B matrices.
        if len(state) != len(params) or any(".null." in k or f".{name}." in k for k in state):
            raise RuntimeError("adapter export does not match the trained adapter's parameters")
        record = {"episode_id": ep["episode_id"], "seed": seed, "steps": train_cfg["steps"], "n_examples": len(examples),
                  "train_tokens": tokens, "seconds": train_seconds,
                  "peak_gib": round(torch.cuda.max_memory_allocated() / 2**30, 2) if torch.cuda.is_available() else None,
                  "approx_train_flops": 6 * self.n_base_params * tokens,
                  "flops_note": "approximation: 6 x base parameters x processed tokens (forward, backward, checkpoint recompute)",
                  "loss_first": losses[0], "loss_last": losses[-1], "loss_trace": losses,
                  "context": context, "schedule": train_cfg.get("schedule", "shuffle"), "steps_log": steps_log, "support_before": diag_before, "support_after": diag_after,
                  "delta_norm_total": delta["total"], "delta_norm_max": delta["max"],
                  "adapter_params": sum(p.numel() for p in params)}
        self.peft.set_adapter("null")
        self.peft.delete_adapter(name)
        self._freeze_all()
        return state, record, trained_logits

    def encode(self, user, target, answer):
        """Prompt + target ids, the number of target tokens, and positions (in the target) of the choice ID tokens."""
        torch = self.torch
        prompt_ids = self.tok(self.render(user), add_special_tokens=False).input_ids
        full = target + "<|im_end|>"
        enc = self.tok(full, add_special_tokens=False, return_offsets_mapping=True)
        s = target.rindex(answer); e = s + len(answer)
        choice_pos = [i for i, (a, b) in enumerate(enc["offset_mapping"]) if a < e and b > s]
        if not choice_pos:
            raise RuntimeError("choice ID tokens not found in target")
        ids = torch.tensor([prompt_ids + enc["input_ids"]], device=self.model.device)
        return ids, len(enc["input_ids"]), choice_pos

    def support_diagnostics(self, ep, context):
        """Greedy accuracy and teacher-forced choice-token NLL on the (unaugmented) support examples."""
        torch = self.torch
        was_training = self.peft.training
        self.peft.eval()
        rows = []
        for s in ep["support"]:
            user = support_prompt(ep, s, context)
            text, _, _ = self.generate(user)
            choice = parse_choice(text, [c["id"] for c in s["candidates"]])
            ids, n_target, pos = self.encode(user, json.dumps({"choice": s["answer"]}), s["answer"])
            with torch.no_grad():
                logits = self.peft(input_ids=ids, use_cache=False, logits_to_keep=n_target + 1).logits[0, :-1].float()
                nll = torch.nn.functional.cross_entropy(logits, ids[0, -n_target:], reduction="none")
            rows.append({"qid": s["qid"], "correct": choice == s["answer"], "choice": choice,
                         "choice_nll": float(nll[pos].sum()), "target_mean_nll": float(nll.mean())})
        if was_training:
            self.peft.train()
        n = len(rows)
        return {"accuracy": sum(r["correct"] for r in rows) / n,
                "mean_choice_nll": sum(r["choice_nll"] for r in rows) / n,
                "mean_target_nll": sum(r["target_mean_nll"] for r in rows) / n, "per_example": rows}

    def delta_norms(self, name):
        """Frobenius norm of each module's effective weight change scale*B@A, total (L2 over modules) and max."""
        torch = self.torch
        norms = []
        with torch.no_grad():
            for _, m in self.peft.named_modules():
                if hasattr(m, "lora_A") and name in getattr(m, "lora_A", {}):
                    d = (m.lora_B[name].weight.float() @ m.lora_A[name].weight.float()) * m.scaling[name]
                    norms.append(float(d.norm()))
        return {"total": float(sum(x * x for x in norms) ** 0.5), "max": max(norms), "modules": len(norms)}

    # ------------------------------------------------------------ evaluation

    def load_adapter(self, name, state):
        from peft import set_peft_model_state_dict
        self.peft.add_adapter(name, self._config())
        result = set_peft_model_state_dict(self.peft, {k: v.to(self.model.device) for k, v in state.items()}, adapter_name=name)
        unexpected = list(getattr(result, "unexpected_keys", []))
        missing = [k for k in getattr(result, "missing_keys", []) if f".{name}." in k]
        if unexpected or missing:
            raise RuntimeError(f"adapter keys not loaded cleanly: {(unexpected + missing)[:3]}")
        from peft import get_peft_model_state_dict
        back = get_peft_model_state_dict(self.peft, adapter_name=name)
        if set(back) != set(state) or any(not self.torch.equal(back[k].cpu(), state[k].cpu()) for k in state):
            raise RuntimeError("loaded adapter weights differ from the saved adapter")
        self.peft.set_adapter(name)
        self._freeze_all()

    def drop_adapter(self, name):
        self.peft.set_adapter("null")
        self.peft.delete_adapter(name)

    def generate(self, user, max_new_tokens=24):
        torch = self.torch
        ids = self.tok(self.render(user), return_tensors="pt", add_special_tokens=False).input_ids.to(self.model.device)
        with torch.no_grad():
            out = self.peft.generate(input_ids=ids, attention_mask=torch.ones_like(ids), max_new_tokens=max_new_tokens,
                                     do_sample=False, temperature=None, top_p=None, top_k=None,
                                     pad_token_id=self.tok.pad_token_id)
        new = out[0, ids.shape[1]:]
        return self.tok.decode(new, skip_special_tokens=True), int(ids.shape[1]), int(new.shape[0])

    def answer_all(self, ep, condition):
        rows = []
        for q in ep["queries"]:
            text, n_in, n_out = self.generate(render.user_prompt(ep, q))
            valid = [c["id"] for c in q["candidates"]]
            choice = parse_choice(text, valid)
            rows.append({"episode_id": ep["episode_id"], "qid": q["qid"], "condition": condition, "raw": text,
                         "choice": choice, "valid_format": choice is not None,
                         "correct": choice in q["acceptable"],
                         "stale": (choice in q.get("stale_acceptable", [])) if q["kind"] == "correction" else None,
                         "prompt_tokens": n_in, "output_tokens": n_out,
                         "prompt_sha256": hashlib.sha256(render.user_prompt(ep, q).encode()).hexdigest()})
        for i, (_, _, key) in enumerate(UNRELATED):
            text, n_in, n_out = self.generate(unrelated_prompt(i))
            choice = parse_choice(text, UNRELATED_IDS)
            rows.append({"episode_id": ep["episode_id"], "qid": f"unrelated-{i}", "condition": condition, "raw": text,
                         "choice": choice, "valid_format": choice is not None, "correct": choice == UNRELATED_IDS[key],
                         "stale": None, "prompt_tokens": n_in, "output_tokens": n_out,
                         "prompt_sha256": hashlib.sha256(unrelated_prompt(i).encode()).hexdigest()})
        return rows

    ADAPTER_SLOTS = {"W+A": "ectxown", "W+X": "ectxother", "W+Y": "ectxcross"}

    def evaluate_conditions(self, ep, conditions, adapters):
        """W = adapters disabled; W+A / W+X / W+Y = the given (state, source episode) adapter. Same prompts."""
        rows = []
        for cond in conditions:
            if cond == "W":
                with self.peft.disable_adapter():
                    rows += self.answer_all(ep, "W")
                continue
            state, source = adapters[cond]
            slot = self.ADAPTER_SLOTS[cond]
            self.load_adapter(slot, state)
            for r in self.answer_all(ep, cond):
                r["adapter_from"] = source
                if cond == "W+X":
                    r["x_adapter_from"] = source
                rows.append(r)
            self.drop_adapter(slot)
        return rows

    def evaluate_episode(self, ep, own_state, other_state, other_id):
        return self.evaluate_conditions(ep, ["W", "W+A", "W+X"],
                                        {"W+A": (own_state, ep["episode_id"]), "W+X": (other_state, other_id)})
