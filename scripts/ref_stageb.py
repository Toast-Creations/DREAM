"""Build the V1.20.0 stage-B (RES-MODEL extraction) calls from stage-A resolver replies with frozen rules (no model).
Usage: ref_stageb.py --hub HUB --set SET --stage-a STAGE
For each target whose public route is "resolve": parse the RESOLVER reply (refres.parse_resolver). Resolved ->
rewrite the detected span with the model's field and build the RES-MODEL extraction prompt; if it is byte-identical
to the DET extraction prompt (same checkpoint and configuration) the DET reply is reused (cache, no call); otherwise
a stage-B call "<target>|MODEL" (256 tokens) is scheduled. Unresolved / invalid reply -> pending, no call, no fallback
to BASE. A missing, infra_failed or input_too_long resolver record -> "incomplete" (infrastructure, not refusal). Bypass targets -> RES-MODEL = BASE (no call). Writes data/<set>B-calls.jsonl (seeded order),
COMMITMENT-<set>B.json and data/<set>-stageB-ledger.jsonl (route, resolver parse, rewrite ledger, cache source)."""
import argparse
import hashlib
import json
import random
from pathlib import Path

from _bootstrap import ROOT  # noqa: F401
from tempo import refres as RR, render

SCHED_SEED = 20261707


def load(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", required=True)
    ap.add_argument("--set", required=True)
    ap.add_argument("--stage-a", required=True)
    a = ap.parse_args()
    hub = Path(a.hub)
    data = hub / "data"
    if (data / f"COMMITMENT-{a.set}B.json").exists():
        raise SystemExit("stage B already committed")
    targets = load(data / "public" / f"{a.set}-targets.jsonl")
    recs = {}
    for p in (hub / "stages" / a.stage_a / "calls").glob("*.json"):
        r = json.loads(p.read_text())
        recs[r["call_id"]] = r
    ledger, calls = [], []
    for t in targets:
        tid, route = t["target"], t["detection"]["route"]
        row = {"target": tid, "route": route}
        if route == "bypass":
            row.update(model="use_BASE")
        elif route != "resolve":
            row.update(model="pending", reason=t["detection"]["reason"])
        else:
            pi = RR.PublicInput.make(t["prefix"], t["target_text"], t["registry_order"])
            rc = recs.get(f"{tid}|RESOLVER")
            if rc is None or rc.get("status") != "ok":
                # infrastructure completion failure (missing / infra_failed / input_too_long): incomplete, not refusal
                row.update(model="incomplete", reason=f"resolver_infra:{None if rc is None else rc.get('status')}")
                ledger.append(row)
                continue
            raw = rc["raw"]
            pr = RR.parse_resolver(raw, pi)
            if rc and rc.get("stop") == "length" and pr["status"] == "resolved":
                pr = {"field": None, "status": "invalid", "reason": "truncated"}
            row["resolver"] = dict(pr, raw=raw, call_status=None if rc is None else rc.get("status"))
            if pr["status"] != "resolved":
                row.update(model="pending", reason=f"resolver_{pr['status']}:{pr['reason']}")
            else:
                nt, lg = RR.rewrite(t["target_text"], t["detection"], pr["field"])
                prompt = RR.rewrite_prompt(t["base_prompt"], t["target_text"], nt)
                row["ledger"] = lg
                row["prompt_sha256"] = hashlib.sha256(prompt.encode()).hexdigest()
                if t.get("det_prompt") == prompt:
                    row.update(model="use_DET_cache")
                else:
                    row.update(model="call")
                    calls.append({"call_id": f"{tid}|MODEL", "group_id": tid.split("|")[0], "domain": "assembly",
                                  "surface": "prose", "k": 0, "length": "short", "arm": "MODEL", "pattern": "MODEL",
                                  "qtype": "X", "variant": tid, "n_records": 0, "evidence_cutoff": 0, "max_new_tokens": 256,
                                  "system": render.SYSTEM, "user": prompt,
                                  "user_sha256": hashlib.sha256(prompt.encode()).hexdigest()})
        ledger.append(row)
    random.Random(SCHED_SEED).shuffle(calls)
    pc, pl = data / f"{a.set}B-calls.jsonl", data / f"{a.set}-stageB-ledger.jsonl"
    with open(pc, "w") as fh:
        for c in calls:
            fh.write(json.dumps(c, sort_keys=True) + "\n")
    with open(pl, "w") as fh:
        for r in ledger:
            fh.write(json.dumps(r, sort_keys=True, default=str) + "\n")
    (data / f"COMMITMENT-{a.set}B.json").write_text(json.dumps({"set": f"{a.set}B", "calls": len(calls),
                                                                  "calls_sha256": sha(pc), "ledger_sha256": sha(pl),
                                                                  "routes": {k: sum(r["model"] == k for r in ledger) for k in
                                                                             ("call", "use_DET_cache", "use_BASE", "pending", "incomplete")}},
                                                                 indent=1) + "\n")
    print(json.dumps({k: sum(r["model"] == k for r in ledger) for k in ("call", "use_DET_cache", "use_BASE", "pending", "incomplete")}))


if __name__ == "__main__":
    main()
