"""V1.21.0 resource guard (no model). Usage: kid_guard.py HUB CALLS_TO_RUN DEADLINE_EPOCH
Policy (frozen in HUB/config/RESOURCE-GUARD.json before any generation):
  attempts  at most 192 generation attempts in total, smoke included, counting every final call record and every
            logged failed attempt (attempts.jsonl) in every HUB stage directory; retry_limit 0, no auto-resume.
  deadline  absolute: smoke driver start + 7,200 s (earlier than the first generation attempt, so stricter); each
            model stage runs under an in-container `timeout` of the remaining seconds minus 60.
Prints the guard JSON, then the remaining seconds on the last line. Exit 0 iff the stage may start."""
import json
import sys
import time

from _bootstrap import ROOT  # noqa: F401
from tempo import refguard as RG

TOTAL_ATTEMPTS = 192
hub, n_run, deadline = sys.argv[1], int(sys.argv[2]), float(sys.argv[3])
used = RG.used_attempts(hub)
rem_s = int(deadline - time.time())
ok = n_run <= TOTAL_ATTEMPTS - used and rem_s > 120
print(json.dumps({"ok": ok, "to_run": n_run, "used_attempts": used, "remaining_attempts": TOTAL_ATTEMPTS - used,
                  "remaining_seconds": rem_s}))
print(rem_s)
sys.exit(0 if ok else 1)
