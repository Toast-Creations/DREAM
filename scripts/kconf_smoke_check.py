"""V1.22.0 smoke check (structural only; no exactness is computed or printed). Usage: kconf_smoke_check.py HUB
Pass iff the smoke stage has exactly one record per scheduled smoke call, each status ok, stop eos, prompt hash equal
to the schedule, model recipe pinned, input <= 2048 tokens, and the reply parses and normalises under FACT-v1."""
import json
import sys
from pathlib import Path

from _bootstrap import ROOT  # noqa: F401
from tempo import factored as FA
import kconf_analyze as KA

hub = Path(sys.argv[1])
calls = {c["call_id"]: c for c in KA.load(hub / "data" / "smoke-calls.jsonl")}
T = {t["target"]: t for t in KA.load(hub / "data" / "public" / "smoke-targets.jsonl")}
recs, dup = KA.records(hub, "smoke")
bad = list(dup) + [c for c in calls if c not in recs] + [c for c in recs if c not in calls]
for cid, r in recs.items():
    if cid not in calls:
        continue
    ok = (r["status"] == "ok" and r["stop"] == "eos" and r["input_tokens"] <= 2048 and KA.recipe_ok(r)
          and r["user_sha256"] == calls[cid]["user_sha256"])
    claims = FA.compile_reply(r["raw"], T[cid.rsplit("|", 1)[0]]["registry"])[1]["claims"] if r["status"] == "ok" else None
    if not ok or claims is None:
        bad.append(cid)
print(json.dumps({"scheduled": len(calls), "records": len(recs), "structural_failures": bad}))
sys.exit(0 if calls and not bad else 1)
