"""V1.22.0 completion check. Usage: kconf_stage_check.py HUB. Pass iff smoke and main END.json say finished and the
main records equal the main schedule exactly (one ok record per call, no extras, no duplicates). Exit 0/1."""
import json
import sys
from pathlib import Path

from _bootstrap import ROOT  # noqa: F401
from tempo import kidconf as KC
import kconf_analyze as KA

hub = Path(sys.argv[1])
pubs = KA.load(hub / "data" / "public" / "main-targets.jsonl")
calls = {c["call_id"] for c in KA.load(hub / "data" / "main-calls.jsonl")}
recs, dup = KA.records(hub, "main")
ends = {st: (hub / "stages" / st / "END.json").exists() and json.loads((hub / "stages" / st / "END.json").read_text()).get("finished")
        for st in ("smoke", "main")}
try:
    if dup:
        raise KC.Incomplete(f"duplicates {dup[:3]}")
    KC.check_complete({(p["group"], p["act"]): p["stratum"] for p in pubs}, calls, recs)
    problem = None
except KC.Incomplete as e:
    problem = str(e)
print(json.dumps({"end_finished": ends, "scheduled": len(calls), "records": len(recs), "problem": problem}))
sys.exit(0 if all(ends.values()) and problem is None else 1)
