"""Run paired DREAM 2 conditions with clean evaluation and reversible adapters.

For each seed: load the frozen base, initialize one adapter, and save its state.
For each world: measure a clean baseline, reset, then run every declared cell
from that same initial adapter. Within each cell perform no-update exposure,
learning, and evaluation with steering removed; finally restore and verify.

Seeds reuse a world's tasks; they are not additional independent worlds. This
runner records the factorial but does not select a winning dose or perform a
confirmatory statistical analysis. Primary contrasts must be fixed separately.
"""
import gc
from pathlib import Path
import torch
from dream_core.contracts import consolidation_decision
from dream_core.ledger import RunLedger, atomic_json, file_hash, json_hash
from dream_core.steering import assert_no_dream_hooks, load_vector
from .worlds import load_worlds
from .concept_worlds import load_concept_worlds
from .concept_evaluation import concept_metrics, evaluate_concepts
from .plasticity import adapter_hash, attach_adapter, base_hash, displacement, reversible_trial, snapshot
from .training import learn
from .evaluation import evaluate_world, gate_metrics


def conditions(cfg):
    """Enumerate the full lambda-by-eta grid and declared comparison controls.

    lambda=0 removes activation perturbation; eta=0 removes parameter updates.
    With eta=0, the 'exploration_only' label describes a temporary exposure state,
    not a learned adapter: evaluation is clean after that state is removed.
    load_config requires both zero levels so these controls cannot be omitted.
    """
    rows = []
    for lam in cfg["steering"]["lambda_values"]:
        for eta in cfg["plasticity"]["eta_values"]:
            label = "frozen" if lam == eta == 0 else "exploration_only" if eta == 0 else "plasticity_only" if lam == 0 else "coupled"
            rows.append({"condition": label, "lambda": lam, "eta": eta, "preexposure_lambda": 0.0})
    if cfg["plasticity"].get("preexposure_control", True):
        # Only the first, no-update phase is steered for this control. The later
        # learning phase uses lambda=0. With no updates or carried inference cache
        # during exposure, this checks a redundant state; it is not evidence of
        # delayed biological-style plasticity or a persistent exploration memory.
        rows += [{"condition": "preexposure_control", "lambda": 0.0, "eta": eta, "preexposure_lambda": lam}
                 for lam in cfg["steering"]["lambda_values"] if lam > 0
                 for eta in cfg["plasticity"]["eta_values"] if eta > 0]
    high = cfg["plasticity"].get("high_eta")
    if high is not None:
        if not 0 < high <= 10:
            raise ValueError("Invalid high-plasticity multiplier")
        # One higher-LR unsteered comparator probes a magnitude/LR explanation.
        # It cannot rule out every effective-LR or update-magnitude mechanism.
        rows.append({"condition": "high_plasticity", "lambda": 0.0, "eta": high, "preexposure_lambda": 0.0})
    # V1.3.3: an extra arm (e.g. decategorization) couples its own vector with learning.
    for arm in cfg["steering"].get("extra_arms", []):
        rows += [{"condition": f"coupled_{arm['name']}", "lambda": float(arm["lambda"]), "eta": eta,
                  "preexposure_lambda": 0.0, "vector": arm["name"]}
                 for eta in cfg["plasticity"]["eta_values"] if eta > 0]
    return rows


def run(cfg, model_factory):
    """Execute the bounded plan and return its uniquely named record directory.

    model_factory loads verified local files; it creates a fresh model per seed.
    World and trial caps are checked before the queue starts. Ledger deadlines
    are cooperative checks, not an independent process-killing supervisor.
    """
    concepts = cfg["experiment"] == "dream2_concepts"
    worlds = (load_concept_worlds if concepts else load_worlds)(cfg["data_path"], cfg["phase"])
    if len(worlds) > cfg["limits"]["max_worlds"]:
        raise ValueError("World budget exceeded")
    plan = conditions(cfg)
    if len(plan) * len(worlds) * len(cfg["seeds"]) > cfg["limits"]["max_trials"]:
        raise ValueError("Planned trials exceed configured limit; narrow the grid explicitly")
    with RunLedger(cfg["output_dir"], cfg, cfg["limits"]["max_seconds"], cfg["limits"]["max_trials"]) as ledger:
        atomic_json(ledger.path / "data_provenance.json", {"data_sha256": file_hash(cfg["data_path"]),
                    "vector_sha256": file_hash(cfg["steering"]["vector_path"]), "worlds": [w["id"] for w in worlds],
                    **{f"vector_{a['name']}_sha256": file_hash(a["vector_path"]) for a in cfg["steering"].get("extra_arms", [])}})
        for seed in cfg["seeds"]:
            # One initialization per seed, paired across ALL cells/worlds below.
            # Restore this snapshot instead of letting a preceding world teach
            # the next. The base loader may also consume RNG during construction.
            torch.manual_seed(seed)
            if torch.cuda.is_available():
                torch.cuda.manual_seed_all(seed)
            base, tokenizer, identity = model_factory()
            model = attach_adapter(base, cfg["adapter"])
            initial = snapshot(model)
            original_base_hash = base_hash(model)
            vectors = {None: load_vector(cfg["steering"]["vector_path"], model,
                                         file_hash(cfg["model"]["manifest"]), cfg["steering"]["layer_index"])}
            for arm in cfg["steering"].get("extra_arms", []):
                vectors[arm["name"]] = load_vector(arm["vector_path"], model, file_hash(cfg["model"]["manifest"]),
                                                   cfg["steering"]["layer_index"], kind=arm["kind"])
            if concepts:
                evaluate = lambda w: evaluate_concepts(model, tokenizer, w, cfg, seed, ledger.check)
                summarize = concept_metrics
            else:
                evaluate = lambda w: evaluate_world(model, tokenizer, w, cfg, ledger.check)
                summarize = gate_metrics
            atomic_json(ledger.path / f"model-seed-{seed}.json", {"identity": identity,
                "base_parameter_sha256": original_base_hash, "initial_adapter_sha256": adapter_hash(model)})
            try:
                for world in worlds:
                    # This clean pre-learning baseline is shared by that world's
                    # paired conditions, rather than regenerated after learning.
                    with reversible_trial(model, initial):
                        before_eval = evaluate(world)
                    for cell in plan:
                        ledger.check()
                        trial = {"seed": seed, "world_id": world["id"], "phase": cfg["phase"], **cell}
                        try:
                            with reversible_trial(model, initial):
                                before_hash = adapter_hash(model)
                                # Every condition receives two forward-exposure phases.
                                # The first is no-update; only the control's first-phase state differs.
                                # Pre-exposure always uses the main (divergent) direction.
                                first = learn(model, tokenizer, world, cfg, vectors[None], cell["preexposure_lambda"], 0.0, ledger.check)
                                if adapter_hash(model) != before_hash:
                                    raise RuntimeError("No-update exposure changed adapter values")
                                second = learn(model, tokenizer, world, cfg, vectors[cell.get("vector")], cell["lambda"], cell["eta"], ledger.check)
                                # learn() has exited its context: evaluate retention
                                # in adapter weights WITHOUT steering or examples
                                # carried as a generation cache from the training.
                                after_eval = evaluate(world)
                                metrics = summarize(before_eval, after_eval)
                                decision = consolidation_decision(metrics, cfg["gate"], cfg["phase"])
                                trial.update(status="completed", before_adapter_sha256=before_hash,
                                    after_adapter_sha256=adapter_hash(model), adapter_displacement=displacement(model, initial),
                                    exposure_diagnostics=first, training_diagnostics=second,
                                    before_eval=before_eval, after_eval=after_eval, metrics=metrics, gate=decision)
                                if decision["decision"] == "KEEP_CANDIDATE":
                                    # Even an enabled validation gate only permits
                                    # a quarantined research artifact. It is not a
                                    # base-weight merge, clean reload verification,
                                    # deployment permission, or an independent test.
                                    candidate = ledger.path / "quarantine" / f"trial-{ledger.count:06d}"
                                    candidate.mkdir(parents=True, exist_ok=False)
                                    model.save_pretrained(candidate, safe_serialization=True)
                                    atomic_json(candidate / "candidate.json", {"research_only": True,
                                        "fresh_process_reload_verified": False, "world_id": world["id"],
                                        "phase": cfg["phase"], "model_manifest_sha256": file_hash(cfg["model"]["manifest"]),
                                        "data_sha256": file_hash(cfg["data_path"]), "gate": decision,
                                        "adapter_files": {p.name:file_hash(p) for p in candidate.iterdir() if p.is_file()}})
                                    trial["candidate_directory"] = str(candidate.relative_to(ledger.path))
                            if adapter_hash(model) != before_hash:
                                raise RuntimeError("Restored adapter hash differs")
                            if cfg.get("verify_base_each_trial", True) and base_hash(model) != original_base_hash:
                                raise RuntimeError("Base parameter integrity failed")
                            # Admit a completed record only after reset checks.
                            # Unverifiable state aborts; it is not an ordinary
                            # negative accuracy result to pool into the analysis.
                            trial["rollback_verified"] = True
                            ledger.record(trial)
                        except BaseException as exc:
                            # Include KeyboardInterrupt/SystemExit as interrupted
                            # invalid trials and re-raise, preserving prior records.
                            # This minimal record stores the type, not a complete
                            # traceback, partial outputs, or a recovery checkpoint.
                            atomic_json(ledger.path / f"failed-trial-{ledger.count:06d}.json",
                                {"status": "invalid", "seed": seed, "world_id": world["id"],
                                 **cell, "error_type": type(exc).__name__})
                            raise
            finally:
                # A second boundary at seed teardown restores/checks before model
                # disposal. It runs on Python exceptions, not forced termination;
                # an external worker controller needs its own interruption record.
                assert_no_dream_hooks(model)
                model.zero_grad(set_to_none=True)
                from .plasticity import restore
                restore(model, initial)
                if base_hash(model) != original_base_hash:
                    raise RuntimeError("Base integrity failed at seed teardown")
                del model, base
                gc.collect()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
        return ledger.path
