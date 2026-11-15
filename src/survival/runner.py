"""Idea-survival runner (V1.4.0). Inference only: no optimizer, adapter or weight update exists here.

Chain (mode "chains", tests 4-5):
  1. ideation   - the ONLY call an arm can change: strong prompt (ordinary sampling),
                  higher temperature, temporary targeted steering, or a norm-matched
                  random direction on the same token-clock curve;
  2. development - unsteered; reads the verbatim ideation answer (the I1-I5 ledger);
  3. finalization - unsteered; reads the ledger again plus the development text.
Development and finalization prompts, sampling and seeds are identical across arms.

devqual (test 3): fork a supplied starting ledger through two budget-matched branches
("develop" or "review" first pass, then the same finalizer).

continuity (V1.5.0): ONE continuous generation per chain (IDEAS, THINKING, DEVELOPMENT, FINAL), so
processing happens in the same context while the dose returns to baseline. perceive_* arms steer the
task text's prompt positions while it is read (prefill) and then glide the decode dose to zero;
generate_* arms read at baseline and write the ideas under a rise/hold/return curve. The raw answer is
kept whole; per-section "views" are verbatim slices so the 1.4.2 extractor and gate apply unchanged.

Records: one JSON file per unit under <output_dir>/units/. A restart skips finished
units only when config, source and input hashes are unchanged (manifest.json).
Loops, length stops, empty answers and format failures are OUTCOMES, never resampled.
Only an infrastructure exception (RuntimeError/OSError, e.g. CUDA OOM) gets one
identical retry; a second failure is recorded as an external failure (missing).
"""
from contextlib import nullcontext
import json
from pathlib import Path
import random
import time

import re

from .config import ARMS, CONT_ARMS
from .extract import extract
from .prompts import SECTIONS, render, render_continuity

ROOT = Path(__file__).resolve().parents[2]
SEED_OFFSETS = {"ideation": 0, "first_pass": 100000, "final": 200000}
BUDGET_REFUSALS = ("Prompt exceeds token budget", "Generation would exceed the model context window")


def load_rows(path, phase):
    rows = [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]
    if not rows or len({r["id"] for r in rows}) != len(rows):
        raise ValueError("Rows need unique IDs")
    rows = [r for r in rows if r.get("split", phase) == phase]
    if not rows:
        raise ValueError("No rows for declared phase")
    return rows


def plan_units(cfg, rows):
    """Deterministic unit list. Arm (or branch) order is shuffled within each block with order_seed."""
    s = cfg["survival"]
    rng = random.Random(s["order_seed"])
    units = []
    if s["mode"] in ("chains", "continuity"):
        for ti, row in enumerate(rows):
            for si, seed in enumerate(cfg["seeds"]):
                arms = list(s["arms"])
                rng.shuffle(arms)
                for position, arm in enumerate(arms):
                    unit = {"unit_id": f"{row['id']}__s{seed}__{arm}", "task_id": row["id"], "task_index": ti,
                            "seed": seed, "seed_index": si, "arm": arm, "block_position": position}
                    if arm.endswith("random"):
                        # Protocol: (3 * task_index + seed_index) mod 9, both zero-based.
                        unit["random_vector_index"] = (3 * ti + si) % cfg["steering"]["random_count"]
                    units.append(unit)
    else:
        seed = cfg["seeds"][0]
        for row in rows:
            branches = list(s["branches"])
            rng.shuffle(branches)
            for position, branch in enumerate(branches):
                units.append({"unit_id": f"{row['id']}__{branch}", "task_id": row["id"], "seed": seed,
                              "branch": branch, "block_position": position})
    return units


def unit_count(cfg, rows):
    return len(plan_units(cfg, rows))


def _random_paths(cfg):
    folder = Path(cfg["steering"]["random_set_dir"])
    return [folder / f"random-direction-{i:02d}.json" for i in range(cfg["steering"]["random_count"])]


def input_hashes(cfg):
    from dream_core.ledger import file_hash
    hashes = {"data": file_hash(cfg["data_path"]), "model_manifest": file_hash(cfg["model"]["manifest"])}
    if cfg["survival"]["mode"] in ("chains", "continuity"):
        if any(a.endswith("targeted") for a in cfg["survival"]["arms"]):
            hashes["targeted_vector"] = file_hash(cfg["steering"]["vector_path"])
        if any(a.endswith("random") for a in cfg["survival"]["arms"]):
            hashes["random_set"] = [file_hash(p) for p in _random_paths(cfg)]
    return hashes


def _call(model, tokenizer, cfg, stage, system, user, seed, temperature, cap_key, steer=None):
    """One generation with the frozen retry rule. Returns a call record (never raises for model outcomes)."""
    from dream_core import modeling
    from dream_core.steering import MaskedSteerer, assert_no_dream_hooks
    lim, gen = cfg["limits"], cfg["generation"]
    record = {"stage": stage, "system": system, "user": user, "seed": seed, "temperature": temperature,
              "top_p": gen["top_p"], "top_k": gen["top_k"], "max_new_tokens": lim["max_new_tokens"],
              "max_input_tokens": lim["stage_input_tokens"][cap_key], "steering": None, "attempts": []}
    if steer is not None:
        record["steering"] = {k: v for k, v in steer.items() if k != "vector"}
    for attempt in range(1 + lim.get("external_retries", 1)):
        assert_no_dream_hooks(model)
        started = time.monotonic()
        ctx = (MaskedSteerer(model, cfg["steering"]["layer_index"], steer["vector"], steer["peak_strength"],
                             generation=True, schedule_spec=steer["schedule"], record_norms=True,
                             max_new_tokens=lim["max_new_tokens"],
                             prefill_positions=steer.get("prefill_positions"),
                             prefill_strength=steer.get("prefill_strength"),
                             prompt_tokens=steer.get("prompt_tokens")) if steer is not None else nullcontext())
        try:
            with ctx as steerer:
                # Resolved through the module at call time so the controller's observer wrapper applies.
                out = modeling.generate(model, tokenizer, user, system=system, seed=seed, temperature=temperature,
                                        top_p=gen["top_p"], top_k=gen["top_k"],
                                        max_input_tokens=lim["stage_input_tokens"][cap_key],
                                        max_new_tokens=lim["max_new_tokens"], loop_guard=lim.get("loop_guard"))
        except ValueError as exc:
            # V1.4.1: only the two budget refusals are outcomes (the ledger is never truncated).
            # Any other ValueError is a code or configuration fault and stops the run loudly.
            if not any(m in str(exc) for m in BUDGET_REFUSALS):
                raise
            record["attempts"].append({"error": str(exc), "kind": "input_budget_exceeded",
                                       "seconds": time.monotonic() - started})
            record.update(status="input_budget_exceeded", output=None)
            return record
        except (RuntimeError, OSError) as exc:
            record["attempts"].append({"error": repr(exc), "kind": "external", "seconds": time.monotonic() - started})
            try:
                import torch
                torch.cuda.empty_cache()
            except Exception:
                pass
            continue
        finally:
            assert_no_dream_hooks(model)
        record["attempts"].append({"kind": "ok", "seconds": time.monotonic() - started})
        record.update(status="completed", output=out, runtime_seconds=time.monotonic() - started)
        if steerer is not None:
            record["steering_trace"] = steerer.trace
            record["norm_trace"] = steerer.norm_trace
            record["comedown_complete"] = steerer.comedown_complete
            if steerer.prefill_positions is not None:
                if steerer.prefill_trace is None:
                    raise RuntimeError("Prefill steering was requested but never applied")
                record["prefill_trace"] = steerer.prefill_trace
        return record
    record.update(status="external_failure", output=None)
    return record


def _text(call):
    return call["output"]["text"] if call and call.get("status") == "completed" else None


def span_positions(tokenizer, system, user, char_span, max_input_tokens):
    """Token indices of the rendered prompt that overlap ``user[char_span]``; also the prompt length.

    Uses the same render and tokenization as modeling.generate (add_special_tokens=False), so the
    indices address exactly the positions the prefill forward will see.
    """
    from dream_core.modeling import render_chat
    rendered = render_chat(tokenizer, user, system)
    offset = rendered.find(user)
    if offset < 0 or rendered.find(user, offset + 1) >= 0:
        raise ValueError("User text must appear exactly once in the rendered prompt")
    lo, hi = offset + char_span[0], offset + char_span[1]
    enc = tokenizer(rendered, return_offsets_mapping=True, add_special_tokens=False)
    ids, offsets = enc["input_ids"], enc["offset_mapping"]
    if hasattr(ids, "tolist"):
        ids, offsets = ids.tolist(), offsets.tolist()
    if ids and isinstance(ids[0], list):
        ids, offsets = ids[0], offsets[0]
    if len(ids) > max_input_tokens:
        raise ValueError("Prompt exceeds token budget; silent truncation is disabled")
    positions = [i for i, (a, b) in enumerate(offsets) if b > lo and a < hi]
    if not positions:
        raise ValueError("Introduced span maps to no prompt tokens")
    return positions, len(ids), rendered[lo:hi]


def section_views(text, finish_reason):
    """Verbatim slices of one continuous answer at its first IDEAS/THINKING/DEVELOPMENT/FINAL headers (in order)."""
    found, pos = {}, 0
    for name in SECTIONS:
        m = re.compile(r"^[ \t#*]*" + name + r"[ \t*:]*$", re.M).search(text, pos)
        if m:
            found[name] = (m.start(), m.end()); pos = m.end()
    views, names = {}, [n for n in SECTIONS if n in found]
    for i, name in enumerate(names):
        start = found[name][1]
        end = found[names[i + 1]][0] if i + 1 < len(names) else len(text)
        last = i + 1 == len(names)
        views[name] = {"char_span": [start, end], "text": text[start:end].strip("\n"),
                       "finish_reason": finish_reason if last else "eos"}
    return views


def _view_call(stage, view, source_status):
    if view is None:
        return {"stage": stage, "view_of": "continuous", "status": "missing_section", "output": None}
    return {"stage": stage, "view_of": "continuous", "status": source_status, "char_span": view["char_span"],
            "output": {"text": view["text"], "finish_reason": view["finish_reason"]}}


def _steer_for(cfg, unit, vectors, arm):
    st = cfg["steering"]
    key = "targeted" if arm.endswith("targeted") else unit["random_vector_index"]
    vector, sha = vectors[key]
    base = {"vector": vector, "vector_sha256": sha, "vector_role": arm.split("_", 1)[1],
            "random_vector_index": unit.get("random_vector_index"), "layer_index": st["layer_index"]}
    if arm.startswith("perceive"):
        return {**base, "mode": "perceive", "peak_strength": st["perceive"]["prefill_strength"],
                "prefill_strength": st["perceive"]["prefill_strength"], "schedule": st["perceive"]["schedule"]}
    return {**base, "mode": "generate", "peak_strength": st["generate"]["peak_strength"],
            "schedule": st["generate"]["schedule"]}


def run_continuity(model, tokenizer, cfg, row, unit, vectors):
    gen, lim = cfg["generation"], cfg["limits"]
    record = {**unit, "task": row, "calls": []}
    arm = unit["arm"]
    system, user, span = render_continuity(row["prompt"])
    steer = None if arm == "baseline" else _steer_for(cfg, unit, vectors, arm)
    if steer is not None and steer["mode"] == "perceive":
        positions, n, covered = span_positions(tokenizer, system, user, span, lim["stage_input_tokens"]["continuous"])
        steer.update(prefill_positions=positions, prompt_tokens=n, prefill_covered_text=covered)
    call = _call(model, tokenizer, cfg, "continuous", system, user, unit["seed"], gen["temperature"],
                 "continuous", steer)
    if call.get("steering") and "prefill_positions" in call["steering"]:
        call["steering"]["prefill_positions"] = steer["prefill_positions"]
    record["continuous_call"] = call
    text = _text(call)
    views = section_views(text, call["output"]["finish_reason"]) if text is not None else {}
    record["sections_found"] = [n for n in SECTIONS if n in views]
    record["calls"] = [_view_call(stage, views.get(name), call["status"])
                       for stage, name in (("ideation", "IDEAS"), ("thinking", "THINKING"),
                                           ("development", "DEVELOPMENT"), ("final", "FINAL"))]
    record["original_ledger"] = views["IDEAS"]["text"] if "IDEAS" in views else None
    record["status"] = ("completed" if call["status"] == "completed" and len(views) == len(SECTIONS)
                        else "missing_sections" if call["status"] == "completed" else call["status"])
    if cfg["survival"].get("category_probe") and arm in ("baseline", "perceive_targeted", "perceive_random"):
        record["category_probe"] = category_probe(model, tokenizer, cfg, row, unit, vectors, arm)
    return record


def category_probe(model, tokenizer, cfg, row, unit, vectors, arm):
    """Manipulation check: greedy, fresh context, task read under the arm's prefill steering, decode unsteered."""
    lim = cfg["limits"]
    system, user, span = render_continuity(row["prompt"], probe=True)
    steer = None
    if arm != "baseline":
        steer = _steer_for(cfg, unit, vectors, arm)
        positions, n, _ = span_positions(tokenizer, system, user, span, lim["stage_input_tokens"]["continuous"])
        steer.update(prefill_positions=positions, prompt_tokens=n, peak_strength=0.0, schedule=None)
    probe_cfg = {**cfg, "limits": {**lim, "max_new_tokens": 64, "loop_guard": None}}
    call = _call(model, tokenizer, probe_cfg, "category_probe", system, user, 0, 0.0, "continuous", steer)
    return {"status": call["status"], "text": _text(call), "steering": call.get("steering"),
            "prefill_trace": call.get("prefill_trace")}


def run_chain(model, tokenizer, cfg, row, unit, vectors):
    gen = cfg["generation"]
    s = cfg["survival"]
    if s["mode"] == "continuity":
        return run_continuity(model, tokenizer, cfg, row, unit, vectors)
    record = {**unit, "task": row, "calls": []}
    task_prompt = row["prompt"]
    if s["mode"] == "chains":
        arm = unit["arm"]
        steer = None
        temperature = gen["high_temperature"] if arm == "high_temperature" else gen["temperature"]
        if arm in ("targeted", "random"):
            key = "targeted" if arm == "targeted" else unit["random_vector_index"]
            vector, sha = vectors[key]
            steer = {"vector": vector, "vector_sha256": sha, "vector_role": arm,
                     "random_vector_index": unit.get("random_vector_index"),
                     "peak_strength": cfg["steering"]["peak_strength"], "schedule": cfg["steering"]["schedule"],
                     "layer_index": cfg["steering"]["layer_index"]}
        system, user = render("ideation", task_prompt=task_prompt)
        ideation = _call(model, tokenizer, cfg, "ideation", system, user, unit["seed"] + SEED_OFFSETS["ideation"],
                         temperature, "ideation", steer)
        record["calls"].append(ideation)
        ledger = _text(ideation)
        first_stage = "development" if s["workflow"] == "develop" else "review"
    else:
        ledger = row["original_ledger"]
        first_stage = "development" if unit["branch"] == "develop" else "review"
    record["original_ledger"] = ledger
    if ledger is None:
        record["status"] = "stopped_before_development"
        return record
    system, user = render(first_stage, task_prompt=task_prompt, original_ledger=ledger)
    first = _call(model, tokenizer, cfg, first_stage, system, user, unit["seed"] + SEED_OFFSETS["first_pass"],
                  gen["temperature"], "development")
    record["calls"].append(first)
    if _text(first) is None:
        record["status"] = "stopped_before_final"
        return record
    system, user = render("final", task_prompt=task_prompt, original_ledger=ledger, development_text=_text(first))
    final = _call(model, tokenizer, cfg, "final", system, user, unit["seed"] + SEED_OFFSETS["final"],
                  gen["temperature"], "final")
    record["calls"].append(final)
    record["status"] = "completed" if final["status"] == "completed" else "final_" + final["status"]
    return record


def extraction(record):
    rows = []
    if record["calls"] and record["calls"][0]["stage"] == "ideation":
        call = record["calls"][0]
        if call["status"] == "completed":
            rows += extract(call["output"]["text"], "initial", finish_reason=call["output"]["finish_reason"])
    final = [c for c in record["calls"] if c["stage"] == "final"]
    if final and final[0]["status"] == "completed":
        rows += extract(final[0]["output"]["text"], "final", finish_reason=final[0]["output"]["finish_reason"])
    return rows


def run(model, tokenizer, cfg):
    from dream_core.ledger import atomic_json, file_hash, json_hash, release_source_hash
    from dream_core.steering import assert_no_dream_hooks, load_vector
    rows = load_rows(cfg["data_path"], cfg["phase"])
    units = plan_units(cfg, rows)
    lim = cfg["limits"]
    if len(rows) > lim["max_worlds"] or len(units) > lim["max_trials"]:
        raise ValueError("Survival plan exceeds budget")
    if any(p.requires_grad for p in model.parameters()):
        raise ValueError("Idea survival requires a frozen model")
    by_id = {r["id"]: r for r in rows}
    out = Path(cfg["output_dir"])
    (out / "units").mkdir(parents=True, exist_ok=True)
    manifest = {"config_sha256": json_hash(cfg), "source_sha256": release_source_hash(ROOT),
                "inputs": input_hashes(cfg), "units": [u["unit_id"] for u in units]}
    manifest_path = out / "manifest.json"
    if manifest_path.exists():
        previous = json.loads(manifest_path.read_text())
        if previous != manifest:
            raise RuntimeError("Resume refused: config, source, inputs or plan differ from the frozen manifest")
    else:
        atomic_json(manifest_path, manifest)
        atomic_json(out / "config.json", cfg)
    vectors = {}
    if cfg["survival"]["mode"] in ("chains", "continuity"):
        identity = file_hash(cfg["model"]["manifest"])
        layer = cfg["steering"]["layer_index"]
        arms = cfg["survival"]["arms"]
        if "targeted" in arms or any(a.endswith("_targeted") for a in arms):
            vectors["targeted"] = (load_vector(cfg["steering"]["vector_path"], model, identity, layer,
                                               kind="decategorization"), file_hash(cfg["steering"]["vector_path"]))
        if "random" in arms or any(a.endswith("_random") for a in arms):
            for i, p in enumerate(_random_paths(cfg)):
                vectors[i] = (load_vector(p, model, identity, layer, kind="random"), file_hash(p))
    previous_kwargs = getattr(tokenizer, "dream_chat_kwargs", None)
    started = time.monotonic()
    done = {p.stem for p in (out / "units").glob("*.json")}
    try:
        if previous_kwargs is not None:
            tokenizer.dream_chat_kwargs = {**previous_kwargs, "enable_thinking": False}
        for unit in units:
            if unit["unit_id"] in done:
                continue
            if time.monotonic() - started > lim["max_seconds"]:
                raise TimeoutError("Stage wall-time budget reached; finished units preserved, resume to continue")
            assert_no_dream_hooks(model)
            t0 = time.monotonic()
            record = run_chain(model, tokenizer, cfg, by_id[unit["task_id"]], unit, vectors)
            record["extraction"] = extraction(record)
            record["unit_seconds"] = time.monotonic() - t0
            atomic_json(out / "units" / f"{unit['unit_id']}.json", record)
            done.add(unit["unit_id"])
            atomic_json(out / "progress.json", {"completed_units": len(done), "planned_units": len(units),
                                                "session_elapsed_seconds": time.monotonic() - started})
    finally:
        if previous_kwargs is not None:
            tokenizer.dream_chat_kwargs = previous_kwargs
        assert_no_dream_hooks(model)
    atomic_json(out / "COMPLETE.json", {"completed_units": len(done), "planned_units": len(units)})
    return out
