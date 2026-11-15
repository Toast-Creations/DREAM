"""Validate a fixed research plan, then gate any real local model execution.

--plan-only checks configuration/data/counts and returns before model loading.
A real run additionally requires a verified local model manifest, discoverable
ML packages, and matching-source evidence from a no-skip ML-inclusive test run.
These checks prevent accidental unqualified runs; they do not authenticate an
attacker-writable report or provide the future tool-worker's OS containment.
"""
import argparse
from _bootstrap import ROOT
from dream_core.config import load_config
from dream_core.modeling import load_local_model


def main():
    """Choose DREAM/DREAM 2 and enforce readiness before admitting model work."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--plan-only", action="store_true", help="Validate data and limits without loading a model")
    args = parser.parse_args()
    cfg = load_config(args.config)
    if cfg["experiment"] == "survival":
        # V1.4.0 idea survival: one unit per chain (or devqual branch).
        from survival.runner import load_rows, unit_count
        items = load_rows(cfg["data_path"], cfg["phase"])
        count = unit_count(cfg, items)
        selected_count = len(items)
    elif cfg["experiment"] == "decategorization":
        from dream.decategorization import load_objects
        from dream_core.planning import trial_count
        items = load_objects(cfg["data_path"], cfg["phase"])
        count = trial_count(cfg, len(items))
        selected_count = len(items)
    elif cfg["experiment"] == "concept_association":
        from dream.concepts import load_concepts
        from dream_core.planning import trial_count
        items = load_concepts(cfg["data_path"], cfg["phase"])
        count = trial_count(cfg, len(items))
        selected_count = len(items)
    elif cfg["experiment"] in ("dream2", "dream2_concepts"):
        from dream2.worlds import load_worlds
        from dream2.concept_worlds import load_concept_worlds
        worlds = (load_concept_worlds if cfg["experiment"] == "dream2_concepts" else load_worlds)(cfg["data_path"], cfg["phase"])
        # Pure plan formula, available without PyTorch.
        from dream_core.planning import trial_count
        count = trial_count(cfg, len(worlds))
        selected_count = len(worlds)
    else:
        import json
        tasks = [json.loads(line) for line in open(cfg["data_path"], encoding="utf-8") if line.strip()]
        from dream_core.planning import trial_count
        count = trial_count(cfg, sum(t["split"] == cfg["phase"] for t in tasks))
        selected_count = sum(t["split"] == cfg["phase"] for t in tasks)
    if selected_count > cfg["limits"]["max_worlds"]:
        raise ValueError("Selected world/task budget exceeded")
    if count > cfg["limits"]["max_trials"]:
        raise ValueError("Planned cells exceed configured trial budget")
    print(f"Validated plan: {count} trial cells, phase={cfg['phase']}; no model downloaded")
    if args.plan_only:
        # A successful plan is a wiring check, not evidence of GPU compatibility,
        # gradient influence, rollback behavior, model safety, or effectiveness.
        return
    from dream_core.modeling import verify_local_manifest
    verify_local_manifest(cfg["model"])
    # Discovery establishes only that importable modules are advertised. The
    # integration-test gate below is also required; package presence alone says
    # nothing about compatible versions or a functioning CUDA/PEFT combination.
    import importlib.util
    missing = [name for name in ("torch", "transformers", "safetensors")
               if importlib.util.find_spec(name) is None]
    if cfg["experiment"] in ("dream2", "dream2_concepts") and importlib.util.find_spec("peft") is None:
        missing.append("peft")
    if missing:
        raise RuntimeError("Install the optional ML environment and pass --require-ml tests first. Missing: " + ", ".join(missing))
    import json
    from dream_core.ledger import release_source_hash
    report_path=ROOT/"test-results/latest.json"
    report=json.loads(report_path.read_text(encoding="utf-8")) if report_path.is_file() else {}
    # Require all four conditions, not merely success=True: optional integration
    # tests may have been skipped in an otherwise successful logic-only report.
    # V1.1.4 binds evidence to source, tests, scripts and dependency declarations.
    if (not report.get("success") or not report.get("ml_dependencies_available") or report.get("skipped") != 0
            or report.get("source_sha256") != release_source_hash(ROOT)):
        raise RuntimeError("Pass python scripts/run_tests.py --require-ml on the current source before running a model")
    if cfg["experiment"] in ("dream2", "dream2_concepts"):
        # DREAM 2 receives a factory so each seed gets a freshly loaded base and
        # independently initialized adapter. DREAM 1 never creates an optimizer.
        from dream2.experiment import run
        path = run(cfg, lambda: load_local_model(cfg["model"]))
    elif cfg["experiment"] == "survival":
        from survival.runner import run as survival_run
        model, tokenizer, identity = load_local_model(cfg["model"])
        path = survival_run(model, tokenizer, cfg)
    elif cfg["experiment"] in ("concept_association", "decategorization"):
        from dream.concepts import run as concepts_run
        from dream.decategorization import run as decategorization_run
        run = decategorization_run if cfg["experiment"] == "decategorization" else concepts_run
        model, tokenizer, identity = load_local_model(cfg["model"])
        path = run(model, tokenizer, cfg)
    else:
        from dream.experiment import run
        model, tokenizer, identity = load_local_model(cfg["model"])
        path = run(model, tokenizer, cfg)
    print(f"Completed run: {path}")


if __name__ == "__main__":
    main()
