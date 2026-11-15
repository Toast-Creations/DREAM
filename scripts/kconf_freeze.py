"""V1.22.0 freeze (no model). Usage: kconf_freeze.py --hub HUB [--model-manifest PATH]
Writes HUB/config/FROZEN-PROTOCOL.json binding: release source hash, canonical analysis-plan hash, every file in
HUB/design, HUB/config (except DEADLINE.json and FROZEN-PROTOCOL.json), HUB/data (recursive) and HUB/phase0, the driver
script and the model manifest. Refuses if the validation did not pass, if any stage output exists, or if a freeze exists."""
import argparse
import hashlib
import json
import time
from pathlib import Path

from _bootstrap import ROOT
from dream_core import localpaths as LP  # public release: local paths from environment
from dream_core.ledger import release_source_hash
from tempo import kidconfdone as KD


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", required=True)
    ap.add_argument("--model-manifest", default=f"{LP.MODELS}/Qwen3-32B/model-manifest.json")
    a = ap.parse_args()
    hub = Path(a.hub)
    out = hub / "config" / "FROZEN-PROTOCOL.json"
    if out.exists():
        raise SystemExit("freeze exists")
    if (hub / "stages").exists() or (hub / "config" / "DEADLINE.json").exists():
        raise SystemExit("stage output or deadline exists: too late to freeze")
    v = json.loads((hub / "phase0" / "VALIDATION.json").read_text())
    if not v["all_pass"]:
        raise SystemExit("validation did not pass")
    plan = json.loads((hub / "config" / "ANALYSIS-PLAN.json").read_text())
    KD.validate_plan(plan)
    sec = {}
    for name in ("design", "config", "data", "phase0"):
        d = hub / name
        sec[name] = {str(p.relative_to(d)): sha(p) for p in sorted(d.rglob("*")) if p.is_file()
                     and p.name not in ("DEADLINE.json", "FROZEN-PROTOCOL.json")}
    rec = {"status": "FROZEN before any model output; collection not started",
           "frozen_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "source_sha256": release_source_hash(ROOT),
           "source_dir": str(ROOT), "analysis_plan_sha256": KD.plan_sha256(plan), "analysis_plan": plan,
           "driver_sha256": sha(hub / "run_kconf.sh"), "model_manifest_sha256": sha(a.model_manifest),
           "validation_sha256": sha(hub / "phase0" / "VALIDATION.json"), **sec}
    out.write_text(json.dumps(rec, indent=1) + "\n")
    print(json.dumps({k: rec[k] for k in ("source_sha256", "analysis_plan_sha256", "driver_sha256")}), sha(out))


if __name__ == "__main__":
    main()
