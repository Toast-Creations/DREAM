"""ESUB-v1 stage configuration, direct launcher and pre-output freeze. No model calls. Adapted from cc_prepare.py."""
import argparse
import hashlib
import json
import shlex
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from _bootstrap import ROOT
from dream_core import localpaths as LP  # public release: local paths from environment
from dream_core.ledger import release_source_hash
from tempo.kidconfdone import plan_sha256

MODEL = {"path": f"{LP.MODELS}/Qwen3-32B/9216db5781bf21249d130ec9da846c4624c16137",
         "manifest": f"{LP.MODELS}/Qwen3-32B/model-manifest.json", "dtype": "bfloat16",
         "device": "cuda", "enable_thinking": False, "quantization": "nf4"}
STAGES = (("smoke", 36), ("main", 1440))
CEILING_S = 28800


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _calls(hub, stage):
    return [json.loads(line)["call_id"] for line in (Path(hub) / f"data/{stage}-calls.jsonl").read_text().splitlines()
            if line.strip()]


def _want(hub, stage, expected, model):
    return {"set": stage, "order_seed": 0, "order": "as_committed", "max_input_tokens": 2048,
            "retry_limit": 0, "model": model, "select": _calls(hub, stage), "max_calls": expected,
            "max_seconds": CEILING_S}


def configs(hub, model_from):
    hub = Path(hub)
    model = json.loads(Path(model_from).read_text())["model"]
    if json.dumps(model, sort_keys=True) != json.dumps(MODEL, sort_keys=True):
        raise ValueError("model recipe differs from the declared V1.24 recipe")
    for stage, expected in STAGES:
        cfg = _want(hub, stage, expected, model)
        if len(cfg["select"]) != expected or len(set(cfg["select"])) != expected:
            raise ValueError(f"wrong {stage} schedule")
        with (hub / f"config/stage-{stage}.json").open("x") as out:
            out.write(json.dumps(cfg, indent=2) + "\n")


def validate_stage_configs(hub):
    hub = Path(hub)
    for stage, expected in STAGES:
        cfg = json.loads((hub / f"config/stage-{stage}.json").read_text())
        want = _want(hub, stage, expected, MODEL)
        if len(want["select"]) != expected or json.dumps(cfg, sort_keys=True) != json.dumps(want, sort_keys=True):
            raise ValueError(f"unsupported {stage} config/model recipe")


def launcher(hub):
    return ("#!/bin/bash\n# ESUB-v1: the reviewed supervisor owns all stages and terminal status.\n"
            "export TZ=America/New_York\nexec /usr/bin/python3 -B " + shlex.quote(str(ROOT / "scripts/es_run.py"))
            + " --hub " + shlex.quote(str(Path(hub).resolve())) + "\n")


def freeze(hub, manifest):
    from tempo import esubject as ES
    from es_analyze import validate_plan
    hub = Path(hub)
    if any((hub / "stages").glob("*")) or (hub / "config/DEADLINE.json").exists():
        raise ValueError("stage output/deadline exists")
    ES.validate_config(json.loads((hub / "config/PANEL.json").read_text()))
    validate_stage_configs(hub)
    if Path(manifest).resolve() != Path(MODEL["manifest"]).resolve():
        raise ValueError("manifest must be the declared model manifest")
    plan = json.loads((hub / "config/ANALYSIS-PLAN.json").read_text())
    validate_plan(plan)
    validation = json.loads((hub / "phase0/VALIDATION.json").read_text())
    source = release_source_hash(ROOT)
    if validation.get("all_pass") is not True or validation.get("source_sha256") != source:
        raise ValueError("validation must pass on final source")
    sections = {}
    for name in ("design", "config", "data", "phase0"):
        directory = hub / name
        sections[name] = {str(p.relative_to(directory)): sha(p) for p in sorted(directory.rglob("*"))
                          if p.is_file() and p.name not in ("DEADLINE.json", "FROZEN-PROTOCOL.json")}
    record = {"study": "ESUB-v1", "status": "FROZEN before any model output",
              "frozen_at": datetime.now(ZoneInfo("America/New_York")).isoformat(),
              "source_dir": str(ROOT), "source_sha256": source,
              "analysis_plan_sha256": plan_sha256(plan), "analysis_plan": plan,
              "driver_sha256": sha(hub / "run_es.sh"),
              "model_manifest_path": str(Path(manifest).resolve()), "model_manifest_sha256": sha(manifest),
              **sections}
    with (hub / "config/FROZEN-PROTOCOL.json").open("x") as out:
        out.write(json.dumps(record, indent=2) + "\n")
    return record


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=("configs", "driver", "freeze"))
    ap.add_argument("--hub", required=True)
    ap.add_argument("--model-from")
    ap.add_argument("--model-manifest", default=MODEL["manifest"])
    a = ap.parse_args()
    hub = Path(a.hub)
    if a.step == "configs":
        configs(hub, a.model_from)
    elif a.step == "driver":
        path = hub / "run_es.sh"
        with path.open("x") as out:
            out.write(launcher(hub))
        path.chmod(0o755)
    else:
        rec = freeze(hub, a.model_manifest)
        print(json.dumps({k: rec[k] for k in ("study", "source_sha256", "analysis_plan_sha256", "driver_sha256")}))


if __name__ == "__main__":
    main()
