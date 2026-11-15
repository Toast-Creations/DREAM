"""Run DREAM 1's clean anchor, steered exploration, and clean integration stages.

Only the exploration forward calls receive the intervention. Integration gets
the candidate as text in a fresh generation call with no steering hook or KV
cache carried over. Because the model is the same, its errors can be correlated
across stages; independent correctness/novelty judgments remain external.

Zero-dose and temperature controls use the same pipeline. Assignment to a dose
and schedule defines the comparison; realized traces and length are diagnostics,
not reasons to retrospectively regroup or discard treatment-affected outputs.
"""
import json
from pathlib import Path
from dream_core.ledger import RunLedger, atomic_json, file_hash
from dream_core.modeling import generate
from dream_core.steering import MaskedSteerer, assert_no_dream_hooks, load_vector
from .protocol import ANCHOR_SYSTEM, EXPLORE_SYSTEM, INTEGRATE_SYSTEM, exploration_prompt, integration_prompt, plan, step_sampling


def run(model, tokenizer, cfg):
    """Write one record per task/seed/condition and return the run directory.

    Configuration and data define the plan before any generation. The time cap
    is checked between model calls, so a blocked call needs external supervision.
    This function generates research text; it does not run model-suggested code.
    """
    tasks = [json.loads(line) for line in Path(cfg["data_path"]).read_text(encoding="utf-8").splitlines() if line.strip()]
    tasks = [t for t in tasks if t["split"] == cfg["phase"]]
    if not tasks or len(tasks) > cfg["limits"]["max_worlds"] or len({t["id"] for t in tasks}) != len(tasks):
        raise ValueError("Invalid, missing, or excessive task set")
    cells = plan(cfg)
    if len(tasks)*len(cells)*len(cfg["seeds"]) > cfg["limits"]["max_trials"]:
        raise ValueError("Planned trial budget exceeded")
    vectors = {None: load_vector(cfg["steering"]["vector_path"], model,
                                 file_hash(cfg["model"]["manifest"]), cfg["steering"]["layer_index"])}
    for arm in cfg["steering"].get("extra_arms", []):
        vectors[arm["name"]] = load_vector(arm["vector_path"], model, file_hash(cfg["model"]["manifest"]),
                                           cfg["steering"]["layer_index"], kind=arm["kind"])
    limits = {k:cfg["limits"][k] for k in ("max_input_tokens", "max_new_tokens")}
    if cfg["limits"].get("loop_guard") is not None:
        limits["loop_guard"] = cfg["limits"]["loop_guard"]
    with RunLedger(cfg["output_dir"], cfg, cfg["limits"]["max_seconds"], cfg["limits"]["max_trials"]) as ledger:
        atomic_json(ledger.path / "input_hashes.json", {"tasks":file_hash(cfg["data_path"]),
                    "steering":file_hash(cfg["steering"]["vector_path"]), "model":file_hash(cfg["model"]["manifest"]),
                    **{f"steering_{a['name']}":file_hash(a["vector_path"]) for a in cfg["steering"].get("extra_arms", [])}})
        for task in tasks:
            for seed in cfg["seeds"]:
                ledger.check()
                assert_no_dream_hooks(model)
                # Hold this deterministic, unsteered anchor fixed across every
                # condition for a task/seed. No parameter optimizer exists here.
                anchor = generate(model, tokenizer, task["prompt"], system=ANCHOR_SYSTEM,
                                  seed=seed, **step_sampling(cfg, "anchor"), **limits)
                if anchor.get("finish_reason") == "loop":
                    # V1.3.3 option A: a looped step is a recorded outcome, not a halt.
                    # The shared anchor serves every cell, so this task/seed is skipped.
                    ledger.record({"status":"looped", "stage":"anchor", "task_id":task["id"], "category":task["category"],
                        "seed":seed, "skipped_conditions":[c["condition"] + f"@{c['lambda']}" for c in cells],
                        "anchor":anchor, "input_tokens":anchor["input_tokens"], "output_tokens":anchor["output_tokens"]})
                    continue
                if not anchor["text"].strip() or anchor.get("finish_reason") == "length":
                    atomic_json(ledger.path / "incomplete-anchor.json", {"task_id": task["id"], "seed": seed, **anchor})
                    raise RuntimeError("Incomplete anchor preserved; downstream generation stopped")
                for cell in cells:
                    ledger.check()
                    # A NEW context resets the scheduled forward-call index to
                    # zero for each condition. Peak lambda is chosen by the cell;
                    # the optional ramp breakpoints live in steering._hook and
                    # currently scale with max_new_tokens, not wall-clock time.
                    with MaskedSteerer(model, cfg["steering"]["layer_index"], vectors[cell.get("vector")], cell["lambda"],
                            generation=True, max_new_tokens=limits["max_new_tokens"],
                            schedule=cfg["steering"].get("schedule", True)) as steerer:
                        exploratory = generate(model, tokenizer, exploration_prompt(task, anchor["text"]),
                            system=EXPLORE_SYSTEM, seed=seed, temperature=cell["temperature"], top_p=cell["top_p"], **limits)
                    assert_no_dream_hooks(model)
                    if exploratory.get("finish_reason") == "loop":
                        ledger.record({"status":"looped", "stage":"exploration", "task_id":task["id"], "category":task["category"],
                            "seed":seed, **cell, "anchor":anchor, "exploratory":exploratory, "steering_trace":steerer.trace,
                            "input_tokens":anchor["input_tokens"] + exploratory["input_tokens"],
                            "output_tokens":anchor["output_tokens"] + exploratory["output_tokens"]})
                        continue
                    if not exploratory["text"].strip() or exploratory.get("finish_reason") == "length":
                        atomic_json(ledger.path / "incomplete-exploration.json", {"task_id": task["id"], "seed": seed, **cell, **exploratory})
                        raise RuntimeError("Incomplete exploration preserved; integration stopped")
                    ledger.check()
                    # Removing the hook happens BEFORE integration. A new
                    # generate() call supplies a fresh prompt/cache, though the
                    # steered candidate text deliberately influences integration.
                    # JSON wrapping that text is not a prompt-injection boundary.
                    integrated = generate(model, tokenizer, integration_prompt(task, anchor["text"], exploratory["text"]),
                        system=INTEGRATE_SYSTEM, seed=seed+100000, **step_sampling(cfg, "integration"), **limits)
                    # Preserve condition assignment and actual scalar trace.
                    # Early EOS may shorten delivery. Treat length as a possible
                    # outcome; do not silently condition the primary comparison
                    # on realized exposure or on the length of a generated answer.
                    # Pending external ratings are not successful verification.
                    ledger.record({"status":"looped" if integrated.get("finish_reason") == "loop" else "completed",
                        **({"stage":"integration"} if integrated.get("finish_reason") == "loop" else {}), "task_id":task["id"], "category":task["category"],
                        "seed":seed, **cell, "anchor":anchor, "exploratory":exploratory, "integrated":integrated,
                        "steering_trace":steerer.trace,
                        "input_tokens":sum(x["input_tokens"] for x in (anchor,exploratory,integrated)),
                        "output_tokens":sum(x["output_tokens"] for x in (anchor,exploratory,integrated)),
                        "external_verification":"pending", "human_ratings":None})
        assert_no_dream_hooks(model)
        return ledger.path
