"""Fresh-process reload check for a quarantined adapter. Never merges or deploys."""
import argparse
import json
from pathlib import Path
from _bootstrap import ROOT
from dream_core.config import load_config
from dream_core.ledger import atomic_json, file_hash
from dream_core.modeling import load_local_model


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--candidate", required=True)
    args = parser.parse_args()
    cfg = load_config(args.config)
    path = Path(args.candidate).resolve()
    metadata = json.loads((path / "candidate.json").read_text(encoding="utf-8"))
    if file_hash(cfg["model"]["manifest"]) != metadata["model_manifest_sha256"] or file_hash(cfg["data_path"]) != metadata["data_sha256"]:
        raise ValueError("Candidate model or evaluation-data identity differs")
    if metadata["gate"]["decision"] != "KEEP_CANDIDATE" or cfg["phase"] != "validation":
        raise ValueError("Only validation-selected research candidates can use this check")
    for name, expected in metadata["adapter_files"].items():
        target = (path / name).resolve()
        if not target.is_relative_to(path) or file_hash(target) != expected:
            raise ValueError("Candidate adapter content changed")
    from peft import PeftModel
    from dream2.evaluation import evaluate_world, gate_metrics
    from dream2.worlds import load_worlds
    from dream_core.contracts import consolidation_decision
    base, tokenizer, identity = load_local_model(cfg["model"])
    world = next(w for w in load_worlds(cfg["data_path"], "validation") if w["id"] == metadata["world_id"])
    before = evaluate_world(base, tokenizer, world, cfg)
    model = PeftModel.from_pretrained(base, str(path), is_trainable=False, local_files_only=True)
    after = evaluate_world(model, tokenizer, world, cfg)
    gate = consolidation_decision(gate_metrics(before, after), cfg["gate"], "validation")
    output = path / "reload-verification.json"
    if output.exists():
        raise FileExistsError("A reload report already exists; preserve it")
    atomic_json(output, {"fresh_process_reload_verified":gate["decision"] == "KEEP_CANDIDATE",
                "deployment_authorized":False, "gate":gate, "before_eval":before, "after_eval":after})
    print("Saved a research-only reload check. No deployment or model merge occurred.")


if __name__ == "__main__":
    main()
