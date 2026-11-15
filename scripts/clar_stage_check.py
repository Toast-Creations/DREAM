"""CLAR-v1 stage integrity check. Semantics never select whether collection continues."""
import json
import sys
from pathlib import Path

from _bootstrap import ROOT  # noqa: F401
from tempo import kidconfdone as KD
import kconf_analyze as KA


def check(hub):
    hub = Path(hub)
    freeze = json.loads((hub / "config/FROZEN-PROTOCOL.json").read_text())
    info = KD.completion(hub, freeze["source_sha256"])
    problems = list(info["problems"])
    for stage in ("smoke", "main"):
        calls = {r["call_id"]: r for r in KA.load(hub / f"data/{stage}-calls.jsonl")}
        recs, dup = KA.records(hub, stage)
        if dup:
            problems.append(f"{stage}: duplicate records")
        for cid, r in recs.items():
            c = calls.get(cid)
            if c is None or r.get("user_sha256") != c["user_sha256"] or not KA.recipe_ok(r):
                problems.append(f"{stage}: prompt/recipe mismatch {cid}")
            if not r.get("complete"):
                problems.append(f"{stage}: incomplete record {cid}")
    return {**info, "complete": not problems, "problems": problems}


if __name__ == "__main__":
    result = check(sys.argv[1])
    print(json.dumps(result))
    sys.exit(0 if result["complete"] else 1)
