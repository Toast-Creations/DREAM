"""V1.22.0 resource guard (no model). Usage: kconf_guard.py HUB STAGE DEADLINE_EPOCH
Policy from HUB/config/RESOURCE-GUARD.json (frozen before any generation):
  total_attempts   ceiling on generation attempts across all stages (every final record + every logged failed
                   attempt in attempts.jsonl); retry_limit 0; no automatic resume.
  deadline         absolute (driver start + ceiling_s); each stage runs under an in-container `timeout`.
  feasibility      (main only) measured smoke mean seconds/call x remaining main calls x slowdown + overhead_s must be
                   <= remaining seconds to the deadline, or main does not start.
Prints the guard JSON, then the remaining seconds on the last line. Exit 0 iff the stage may start."""
import json
import statistics
import sys
import time
from pathlib import Path

from _bootstrap import ROOT  # noqa: F401
from tempo import refguard as RG

hub, stage, deadline = Path(sys.argv[1]), sys.argv[2], float(sys.argv[3])
g = json.loads((hub / "config" / "RESOURCE-GUARD.json").read_text())
n_run = len(json.loads((hub / "config" / f"stage-{stage}.json").read_text())["select"])
used = RG.used_attempts(hub)
rem_s = int(deadline - time.time())
ok = n_run <= g["total_attempts"] - used and rem_s > 120
out = {"stage": stage, "ok": ok, "to_run": n_run, "used_attempts": used, "remaining_attempts": g["total_attempts"] - used,
       "remaining_seconds": rem_s}
if stage == "main":
    d = hub / "stages" / "smoke" / "calls"
    secs = [json.loads(p.read_text()).get("seconds") for p in d.glob("*.json")] if d.exists() else []
    secs = [s for s in secs if s]
    if not secs:
        ok = False
        out["feasibility"] = "no smoke timings"
    else:
        need = statistics.mean(secs) * n_run * g["feasibility_slowdown"] + g["main_overhead_s"]
        out["feasibility"] = {"smoke_mean_s": round(statistics.mean(secs), 3), "needed_s": round(need),
                              "remaining_s": rem_s, "fits": need <= rem_s}
        ok = ok and need <= rem_s
    out["ok"] = ok
print(json.dumps(out))
print(rem_s)
sys.exit(0 if ok else 1)
