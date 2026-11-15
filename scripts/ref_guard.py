"""Usage: ref_guard.py HUB CALLS_FILE DEADLINE_EPOCH  -> prints the guard JSON; exit 0 if the stage may start.
The remaining seconds (for the watchdog timeout) are the last line of stdout."""
import json
import sys

from _bootstrap import ROOT  # noqa: F401
from tempo import refguard as RG

r = RG.check(sys.argv[1], sys.argv[2], float(sys.argv[3]))
print(json.dumps(r))
print(r["remaining_seconds"])
sys.exit(0 if r["ok"] else 1)
