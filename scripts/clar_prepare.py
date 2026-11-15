"""CLAR-v1 configuration, guarded driver and pre-output freeze. No model calls.

Reuses the reviewed 1.22 driver, guard and structural smoke check. The stage
completion check and analyzer are specific to this four-condition development study.
"""
import argparse
import hashlib
import json
import time
from pathlib import Path

from _bootstrap import ROOT
from dream_core import localpaths as LP  # public release: local paths from environment
from dream_core.ledger import release_source_hash
from tempo.kidconfdone import plan_sha256
import kconf_prepare as KP


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def render_driver(hub, code, **over):
    text = KP.render_driver(hub, code, __ANALYZER__="scripts/clar_analyze.py", **over)
    text = text.replace("scripts/kconf_stage_check.py", "scripts/clar_stage_check.py")
    text = text.replace("analysis/confirm/ANALYSIS.json", "analysis/dev/ANALYSIS.json")
    text = text.replace("'qualification' in a", "a.get('study') == 'CLAR-v1'")
    text = text.replace("run_kconf.sh", "run_clar.sh")
    text = text.replace("V1.22.0 KEEP+ID confirmation", "V1.23.0 revision-value clarification development")
    text = text.replace("smoke (32 disjoint calls", "smoke (48 disjoint calls")
    text = text.replace("main (2240", "main (640")
    text = text.replace('H/driver.log', 'H/driver.log')
    # Bind the executable driver and model identity as well as frozen sections.
    needle = "bad=[k for sec in ('design','config','data','phase0') for k,v in f[sec].items() if hashlib.sha256((H/sec/k).read_bytes()).hexdigest()!=v]"
    replacement = needle + "\nbad += ['driver'] if hashlib.sha256((H/'run_clar.sh').read_bytes()).hexdigest()!=f['driver_sha256'] else []\nbad += ['model manifest'] if hashlib.sha256(pathlib.Path(f['model_manifest_path']).read_bytes()).hexdigest()!=f['model_manifest_sha256'] else []"
    if needle not in text:
        raise AssertionError("inherited driver freeze block changed")
    return text.replace(needle, replacement)


def configs(hub, model_from):
    hub = Path(hub)
    model = json.loads(Path(model_from).read_text())["model"]
    guard = json.loads((hub / "config/RESOURCE-GUARD.json").read_text())
    total = 0
    for stage in ("smoke", "main"):
        calls = [json.loads(l)["call_id"] for l in (hub / f"data/{stage}-calls.jsonl").read_text().splitlines() if l.strip()]
        total += len(calls)
        cfg = {"set": stage, "order_seed": 0, "order": "as_committed", "max_input_tokens": 2048,
               "retry_limit": 0, "model": model, "select": calls, "max_calls": len(calls),
               "max_seconds": guard["ceiling_s"]}
        p = hub / f"config/stage-{stage}.json"
        with p.open("x") as fh:
            fh.write(json.dumps(cfg, indent=1) + "\n")
    if total != guard["total_attempts"] or guard["retry_limit"] != 0:
        raise ValueError("schedule must equal the declared no-retry attempt ceiling")


def freeze(hub, manifest):
    hub = Path(hub)
    if any((hub / "stages").glob("*")) or (hub / "config/DEADLINE.json").exists():
        raise ValueError("stage output/deadline exists; cannot freeze")
    validation = json.loads((hub / "phase0/VALIDATION.json").read_text())
    if validation.get("all_pass") is not True:
        raise ValueError("validation did not pass")
    plan = json.loads((hub / "config/ANALYSIS-PLAN.json").read_text())
    sections = {}
    for section in ("design", "config", "data", "phase0"):
        directory = hub / section
        sections[section] = {str(p.relative_to(directory)): sha(p) for p in sorted(directory.rglob("*"))
                             if p.is_file() and p.name not in ("DEADLINE.json", "FROZEN-PROTOCOL.json")}
    record = {"status": "FROZEN before any model output", "study": "CLAR-v1",
              "frozen_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "source_dir": str(ROOT),
              "source_sha256": release_source_hash(ROOT), "analysis_plan": plan,
              "analysis_plan_sha256": plan_sha256(plan), "driver_sha256": sha(hub / "run_clar.sh"),
              "model_manifest_path": str(Path(manifest).resolve()), "model_manifest_sha256": sha(manifest),
              **sections}
    with (hub / "config/FROZEN-PROTOCOL.json").open("x") as fh:
        fh.write(json.dumps(record, indent=1) + "\n")
    return record


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=("configs", "driver", "freeze"))
    ap.add_argument("--hub", required=True)
    ap.add_argument("--model-from")
    ap.add_argument("--model-manifest", default=f"{LP.MODELS}/Qwen3-32B/model-manifest.json")
    a = ap.parse_args()
    hub = Path(a.hub)
    if a.step == "configs":
        configs(hub, a.model_from)
    elif a.step == "driver":
        p = hub / "run_clar.sh"
        with p.open("x") as fh:
            fh.write(render_driver(hub.resolve(), ROOT))
        p.chmod(0o755)
    else:
        print(json.dumps(freeze(hub, a.model_manifest), indent=1))


if __name__ == "__main__":
    main()
