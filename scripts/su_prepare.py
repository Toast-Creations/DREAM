"""EVT-suite stage configuration, direct launcher and pre-output freeze. No model calls. Adapted from ev_prepare.py.

The study is named by the hub's closed config/PANEL.json (key A, B, C or, from V1.29.0, D).
"""
import argparse
import hashlib
import json
import shlex
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from _bootstrap import ROOT
from dream_core.ledger import release_source_hash
from tempo import evsuite as S
from tempo.kidconfdone import plan_sha256
from ev_prepare import MODEL

CEILING_S = 28800
# V1.20-V1.25 historical rows checked by EVT-v1 (3,772) plus EVT-v1's own 492 targets.
MIN_HISTORICAL_PROMPTS = 4264
EVT_V1_PUBLIC = "temporal-event-report-dev-20261112-070245/data/public/main-targets.jsonl"
# Every earlier hub whose panels EVT-v1 checked, plus EVT-v1 itself; the phase0 scan must inventory all of them.
REQUIRED_HISTORICAL_HUBS = {"temporal-keepid-confirm-20261110-150658", "temporal-keepid-dev-20261110-104944",
                            "temporal-reference-resolution-20261106-171704",
                            "temporal-revision-value-clarification-20261111-015000",
                            "temporal-clarified-keep-confirm-20261111-063336",
                            "temporal-explicit-subject-dev-20261111-210104",
                            "temporal-event-report-dev-20261112-070245"}
# V1.29.0, study D: the EVT suite's three hubs are nested one level down, so they are named with their parent.
SUITE_HUBS = tuple(f"temporal-event-suite-20261112-195430/{n}" for n in ("A-confirm", "B-narrowed", "C-wrongbind"))
REQUIRED_HISTORICAL_HUBS_BY_KEY = {"A": REQUIRED_HISTORICAL_HUBS, "B": REQUIRED_HISTORICAL_HUBS,
                                   "C": REQUIRED_HISTORICAL_HUBS, "D": REQUIRED_HISTORICAL_HUBS | set(SUITE_HUBS)}
REQUIRED_HISTORICAL_FILES_BY_KEY = {"A": (EVT_V1_PUBLIC,), "B": (EVT_V1_PUBLIC,), "C": (EVT_V1_PUBLIC,),
                                    "D": (EVT_V1_PUBLIC,) + tuple(f"{h}/data/public/main-targets.jsonl"
                                                                  for h in SUITE_HUBS)}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def panel(hub):
    return S.validate_config(json.loads((Path(hub) / "config/PANEL.json").read_text()))


def stages(hub):
    cfg = panel(hub)
    return (("smoke", cfg["smoke_calls"]), ("main", cfg["main_calls"]))


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
    for stage, expected in stages(hub):
        cfg = _want(hub, stage, expected, model)
        if len(cfg["select"]) != expected or len(set(cfg["select"])) != expected:
            raise ValueError(f"wrong {stage} schedule")
        with (hub / f"config/stage-{stage}.json").open("x") as out:
            out.write(json.dumps(cfg, indent=2) + "\n")


def validate_stage_configs(hub):
    hub = Path(hub)
    for stage, expected in stages(hub):
        cfg = json.loads((hub / f"config/stage-{stage}.json").read_text())
        want = _want(hub, stage, expected, MODEL)
        if len(want["select"]) != expected or json.dumps(cfg, sort_keys=True) != json.dumps(want, sort_keys=True):
            raise ValueError(f"unsupported {stage} config/model recipe")


def launcher(hub):
    return ("#!/bin/bash\n# EVT suite: the supervisor owns all stages and terminal status.\n"
            "export TZ=America/New_York\nexec /usr/bin/python3 -B " + shlex.quote(str(ROOT / "scripts/su_run.py"))
            + " --hub " + shlex.quote(str(Path(hub).resolve())) + "\n")


def freeze(hub, manifest):
    from su_analyze import validate_plan
    from su_guard import policy
    hub = Path(hub)
    if any((hub / "stages").glob("*")) or (hub / "config/DEADLINE.json").exists():
        raise ValueError("stage output/deadline exists")
    cfg = panel(hub)
    validate_stage_configs(hub)
    if json.loads((hub / "config/RESOURCE-GUARD.json").read_text()) != policy(cfg["key"]):
        raise ValueError("resource policy differs from the declared policy")
    if Path(manifest).resolve() != Path(MODEL["manifest"]).resolve():
        raise ValueError("manifest must be the declared model manifest")
    plan = json.loads((hub / "config/ANALYSIS-PLAN.json").read_text())
    validate_plan(plan, cfg["key"])
    commit = json.loads((hub / "data/COMMITMENT.json").read_text())["historical_checked"]
    if commit["prompts"] < MIN_HISTORICAL_PROMPTS or commit["world_seeds"] < MIN_HISTORICAL_PROMPTS or \
            not all(any(req in f for f in commit["files"]) for req in REQUIRED_HISTORICAL_FILES_BY_KEY[cfg["key"]]):
        raise ValueError("historical coverage below the declared inventory (Codex F12)")
    hist = json.loads((hub / "phase0/HISTORICAL.json").read_text())
    if hist.get("all_zero_overlap") is not True or \
            not REQUIRED_HISTORICAL_HUBS_BY_KEY[cfg["key"]] <= set(hist.get("by_hub", {})):
        raise ValueError("phase0 historical-coverage evidence missing a required hub or shows overlap (Codex F12)")
    validation = json.loads((hub / "phase0/VALIDATION.json").read_text())
    source = release_source_hash(ROOT)
    if validation.get("all_pass") is not True or validation.get("source_sha256") != source:
        raise ValueError("validation must pass on final source")
    from su_phase0 import validate as validate_phase0   # V1.29.0, Codex pre-freeze F1/F2 (study D only)
    phase0_problems = validate_phase0(hub, cfg, source)
    if phase0_problems:
        raise ValueError("phase0 evidence invalid: " + "; ".join(phase0_problems)[:1500])
    sections = {}
    for name in ("design", "config", "data", "phase0"):
        directory = hub / name
        sections[name] = {str(p.relative_to(directory)): sha(p) for p in sorted(directory.rglob("*"))
                          if p.is_file() and p.name not in ("DEADLINE.json", "FROZEN-PROTOCOL.json")}
    record = {"study": cfg["study"], "suite": S.SUITE, "key": cfg["key"], "status": "FROZEN before any model output",
              "frozen_at": datetime.now(ZoneInfo("America/New_York")).isoformat(),
              "source_dir": str(ROOT), "source_sha256": source,
              "analysis_plan_sha256": plan_sha256(plan), "analysis_plan": plan,
              "driver_sha256": sha(hub / "run_su.sh"),
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
        path = hub / "run_su.sh"
        with path.open("x") as out:
            out.write(launcher(hub))
        path.chmod(0o755)
    else:
        rec = freeze(hub, a.model_manifest)
        print(json.dumps({k: rec[k] for k in ("study", "source_sha256", "analysis_plan_sha256", "driver_sha256")}))


if __name__ == "__main__":
    main()
