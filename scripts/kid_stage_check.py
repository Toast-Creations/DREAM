"""V1.21.0 completion check. Usage: kid_stage_check.py HUB. Pass iff smoke and main END.json say finished and every
one of the 192 scheduled KEEP calls has exactly one final record with status ok across the two stages. Exit 0/1."""
import json
import sys
from pathlib import Path

hub = Path(sys.argv[1])
calls = [json.loads(l)["call_id"] for l in (hub / "data" / "kid-calls.jsonl").read_text().splitlines() if l.strip()]
recs, dup = {}, []
for st in ("smoke", "main"):
    for p in (hub / "stages" / st / "calls").glob("*.json") if (hub / "stages" / st / "calls").exists() else []:
        r = json.loads(p.read_text())
        if r["call_id"] in recs:
            dup.append(r["call_id"])
        recs[r["call_id"]] = r.get("status")
ends = {st: (hub / "stages" / st / "END.json").exists() and json.loads((hub / "stages" / st / "END.json").read_text()).get("finished")
        for st in ("smoke", "main")}
bad = [c for c in calls if recs.get(c) != "ok"]
print(json.dumps({"end_finished": ends, "scheduled": len(calls), "not_ok": len(bad), "duplicates": dup, "examples": bad[:5]}))
sys.exit(0 if all(ends.values()) and not bad and not dup else 1)
