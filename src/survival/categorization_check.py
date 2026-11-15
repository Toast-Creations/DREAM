"""V1.5.5 Stage A v2: does targeted steer-then-release steering change categorization, and does it survive release?

Criteria: Runs/idea-survival-20261031/output/continuity/CATEGORIZATION-CHECK-CRITERIA-v2.md (fixed before running).
Inference only; raw records are scored host-side (analysis/categorization_check_report_v2.py).

Measures per object:
* M1 membership DURING the intervention: one forward on "Object: ... <formulation>", steered (target, R0-R8) or
  prefixed (P2). Score = log-odds of Yes-variants vs No-variants at the first answer token, temperature fixed at 1.
* M3 associations: "List ten single words you associate with this object." generated under the intervention
  (target/R0-R8: release schedule; temp: annealed temperature; P2: prefix; baseline: greedy).
* M2 membership AFTER release: the arm's own association turn stays in context, the hook is removed, and the whole
  context is re-read unsteered; the membership question is asked as a second user turn. The only carry-over is the
  text the arm wrote (and, for P2, its prefix).

Two phases: ``calibration`` (already-seen set A: associations for baseline, target and the temperature grid) and
``test`` (sets C and D with the temperature frozen from calibration).
"""
import json
from pathlib import Path
import time

from survival.categorization_items import FORMULATIONS, SETS, TEMPERATURE_GRID, TEMPERATURE_SEEDS, categories
from survival.direction_screen import PREAMBLES, SCREEN_OBJECTS, object_line, random_vectors

TARGET = ("D1", -12, 0.2)
RELEASE = {"shape": "release", "glide_tokens": 64, "end_fraction": 0.0}
ASSOC_TOKENS = 48
TEMP_END = 0.001
YES = ("Yes", "yes", " Yes", " yes", "YES")
NO = ("No", "no", " No", " no", "NO")
ASSOC_ASK = "List ten single words you associate with this object. Reply with one comma-separated line and nothing else."


def assoc_user(name, desc, preamble=None):
    head = f"{preamble}\n\n" if preamble else ""
    return f"{head}Object: {object_line(name, desc)}\n\n{ASSOC_ASK}"


def membership_user(name, desc, category, form, preamble=None):
    head = f"{preamble}\n\n" if preamble else ""
    return f"{head}Object: {object_line(name, desc)}\n\n{FORMULATIONS[form].format(c=category)}"


def label_ids(tokenizer):
    def first(words):
        ids = []
        for w in words:
            enc = tokenizer(w, add_special_tokens=False)["input_ids"]
            if enc and enc[0] not in ids:
                ids.append(enc[0])
        return ids
    yes, no = first(YES), first(NO)
    shared = set(yes) & set(no)
    # A first token shared by a Yes and a No variant (e.g. a bare space) carries no label information; drop it.
    yes, no = [i for i in yes if i not in shared], [i for i in no if i not in shared]
    if not yes or not no:
        raise ValueError("No usable Yes/No label tokens")
    return yes, no


def render(tokenizer, messages):
    if not getattr(tokenizer, "chat_template", None):
        raise ValueError("Use an instruction model with a documented chat template")
    kwargs = dict(getattr(tokenizer, "dream_chat_kwargs", {}))
    return tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, **kwargs)


def steerer(model, vector, layer, strength):
    from dream_core.steering import MaskedSteerer
    return MaskedSteerer(model, layer, vector, strength, generation=True, max_new_tokens=ASSOC_TOKENS,
                         schedule_spec=RELEASE)


def log_odds(model, tokenizer, messages, steer=None):
    """Yes-vs-No log-odds and label mass at the first answer token, temperature 1."""
    import torch
    from contextlib import nullcontext
    ids = tokenizer(render(tokenizer, messages), return_tensors="pt", add_special_tokens=False)["input_ids"]
    ids = ids.to(model.get_input_embeddings().weight.device)
    ctx = steerer(model, *steer) if steer else nullcontext()
    with ctx as s, torch.no_grad():
        logits = model(input_ids=ids, use_cache=False).logits[0, -1].float()
    if steer and (not s.trace or s.trace[0] != float(steer[2])):
        raise RuntimeError("The during-intervention readout must be fully steered")
    logp = torch.log_softmax(logits, -1)
    yes, no = label_ids(tokenizer)
    ly, ln = torch.logsumexp(logp[yes], 0), torch.logsumexp(logp[no], 0)
    return {"log_odds": float(ly - ln), "mass": float(ly.exp() + ln.exp())}


def associations(model, tokenizer, user, steer=None, temperature=None, seed=0):
    from contextlib import nullcontext
    from dream_core import modeling
    ctx = steerer(model, *steer) if steer else nullcontext()
    sched = {"start": temperature, "end": TEMP_END, "anneal_tokens": RELEASE["glide_tokens"]} if temperature else None
    with ctx as s:
        out = modeling.generate(model, tokenizer, user, max_input_tokens=512, max_new_tokens=ASSOC_TOKENS,
                                temperature=0.0, seed=seed, temperature_schedule=sched)
    rec = {"text": out["text"], "finish": out["finish_reason"], "output_tokens": out["output_tokens"]}
    if steer:
        if not s.trace or s.trace[0] != float(steer[2]):
            raise RuntimeError("Release schedule must start at full dose")
        rec["dose_trace"] = [round(x, 5) for x in s.trace]
    return rec


def check_random(vectors, hidden):
    import torch
    expected = {n: v for n, _, v in random_vectors(hidden)}
    for (c, _), v in vectors.items():
        if c.startswith("R") and not torch.allclose(v.float(), expected[c]):
            raise ValueError("Saved random directions differ from the frozen seeds")


def run(model, tokenizer, out_dir, vectors_path, phase, temperature=None, max_seconds=21600):
    import torch
    from dream_core.ledger import atomic_json
    from dream_core.steering import assert_no_dream_hooks
    if phase not in ("calibration", "test"):
        raise ValueError("phase must be calibration or test")
    if phase == "test" and temperature not in TEMPERATURE_GRID:
        raise ValueError("The test phase needs the temperature frozen from calibration (a grid value)")
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    vectors = torch.load(vectors_path, weights_only=False)
    check_random(vectors, model.config.hidden_size)
    code, layer, strength = TARGET
    target = (vectors[(code, layer)], layer, strength)
    path = out / "records.jsonl"
    done, texts = set(), {}
    if path.exists():
        for x in path.read_text().splitlines():
            if x.strip():
                r = json.loads(x); done.add(r["key"])
                if "text" in r:
                    texts[r["key"]] = r["text"]

    def emit(key, rec):
        if time.monotonic() - started > max_seconds:
            raise TimeoutError("Wall-time budget reached; finished records preserved, resume to continue")
        with open(path, "a") as f:
            f.write(json.dumps({"key": key, **rec}) + "\n")
        done.add(key)
        if "text" in rec:
            texts[key] = rec["text"]

    if phase == "calibration":
        for name, desc in SCREEN_OBJECTS:
            user = assoc_user(name, desc)
            for arm, steer in (("baseline", None), ("target", target)):
                key = f"cal|{arm}|0|{name}"
                if key not in done:
                    emit(key, {"phase": "calibration", "arm": arm, "seed": 0, "object": name,
                               "description": desc, **associations(model, tokenizer, user, steer)})
            for t in TEMPERATURE_GRID:
                for seed in TEMPERATURE_SEEDS:
                    key = f"cal|T{t}|{seed}|{name}"
                    if key not in done:
                        emit(key, {"phase": "calibration", "arm": f"T{t}", "seed": seed, "object": name,
                                   "description": desc,
                                   **associations(model, tokenizer, user, temperature=t, seed=seed)})
        assert_no_dream_hooks(model)
        atomic_json(out / "COMPLETE.json", {"phase": phase, "records": len(done)})
        return out

    arms = [("baseline", None, None), ("target", target, None)]
    arms += [(n, (vectors[(n, layer)], layer, strength), None) for n, _, _ in random_vectors(model.config.hidden_size)]
    arms += [("P2", None, PREAMBLES["P2"])]
    for set_name in ("C", "D"):
        for entry in SETS[set_name]:
            name, desc = entry[0], entry[1]
            cats = list(categories(entry))
            runs = [(arm, steer, pre, None, 0) for arm, steer, pre in arms]
            runs += [("temp", None, None, temperature, seed) for seed in TEMPERATURE_SEEDS]
            for arm, steer, pre, temp, seed in runs:
                base = {"phase": set_name, "arm": arm, "seed": seed, "object": name, "description": desc}
                if temp is not None:
                    base["temperature"] = temp
                user = assoc_user(name, desc, pre)
                akey = f"{set_name}|assoc|{arm}|{seed}|{name}"
                if akey not in done:
                    emit(akey, {**base, "probe": "associations",
                                **associations(model, tokenizer, user, steer, temp, seed)})
                assoc_text = texts[akey]
                for level, cat in cats:
                    for form in FORMULATIONS:
                        if temp is None:
                            k1 = f"{set_name}|during|{arm}|{seed}|{name}|{cat}|{form}"
                            if k1 not in done:
                                msgs = [{"role": "user", "content": membership_user(name, desc, cat, form, pre)}]
                                emit(k1, {**base, "probe": "during", "category": cat, "level": level, "form": form,
                                          **log_odds(model, tokenizer, msgs, steer)})
                        k2 = f"{set_name}|after|{arm}|{seed}|{name}|{cat}|{form}"
                        if k2 not in done:
                            msgs = [{"role": "user", "content": user}, {"role": "assistant", "content": assoc_text},
                                    {"role": "user", "content": FORMULATIONS[form].format(c=cat)}]
                            assert_no_dream_hooks(model)
                            emit(k2, {**base, "probe": "after", "category": cat, "level": level, "form": form,
                                      **log_odds(model, tokenizer, msgs)})
    assert_no_dream_hooks(model)
    atomic_json(out / "COMPLETE.json", {"phase": phase, "records": len(done), "temperature": temperature})
    return out
