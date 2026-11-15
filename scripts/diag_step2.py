"""Build block C's step-2 calls from the completed step-1 records (no model).

Usage: diag_step2.py --hub HUB --set diag|diagsmoke --stage STAGE1
Each step-2 prompt = the frozen template head + the step-1 raw reply, verbatim and uncorrected + the frozen tail.
The template file must match its commitment; every step-1 call must have a complete record. A step-1 call that
ended infra_failed (no reply) yields no step-2 call and is reported as an upstream failure (scored incorrect).
Writes HUB/data/<set>c2-{calls,gold}.jsonl and COMMITMENT-<set>c2.json (refuses to overwrite).
"""
import argparse
import hashlib
import json
from pathlib import Path

from _bootstrap import ROOT
from dream_core.ledger import release_source_hash
from tempo import diag as D


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def safe(cid):
    return cid.replace("|", "__")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", required=True)
    ap.add_argument("--set", required=True)
    ap.add_argument("--stage", required=True)
    a = ap.parse_args()
    hub, data = Path(a.hub), Path(a.hub) / "data"
    commit = json.loads((data / f"COMMITMENT-{a.set}.json").read_text())
    tpath = data / f"{a.set}-step2-templates.jsonl"
    if sha(tpath) != commit["step2_templates_sha256"]:
        raise SystemExit("step-2 templates do not match their commitment")
    out_commit = data / f"COMMITMENT-{a.set}c2.json"
    if out_commit.exists():
        raise SystemExit(f"{out_commit} exists")
    stage = hub / "stages" / a.stage
    if not (stage / "END.json").exists():
        raise SystemExit("step-1 stage has not finished (no END.json)")
    tmpls = [json.loads(l) for l in tpath.read_text().splitlines() if l.strip()]
    step1 = {json.loads(l)["call_id"]: json.loads(l) for l in (data / f"{a.set}-calls.jsonl").read_text().splitlines()}
    calls, golds, upstream, rec_shas = [], [], [], {}
    for t in tmpls:
        rp = stage / "calls" / f"{safe(t['step1_call_id'])}.json"
        rec = json.loads(rp.read_text())
        if not rec.get("complete") or rec["user_sha256"] != step1[t["step1_call_id"]]["user_sha256"]:
            raise SystemExit(f"step-1 record {rp} incomplete or mismatched")
        rec_shas[t["step1_call_id"]] = sha(rp)
        if rec["status"] != "ok" or rec["raw"] is None:
            upstream.append({"call_id": t["call_id"], "step1_status": rec["status"]})
            continue
        u = D.step2_user(t["head"], rec["raw"], t["tail"])
        row = {k: t[k] for k in ("call_id", "group_id", "domain", "pattern", "pattern_name", "length", "block",
                                 "arm", "qtype", "variant", "n_records", "evidence_cutoff", "option_ids",
                                 "max_new_tokens", "system", "step", "step1_call_id")}
        row.update(user=u, user_sha256=hashlib.sha256(u.encode()).hexdigest(),
                   step1_raw_sha256=hashlib.sha256(rec["raw"].encode()).hexdigest())
        calls.append(row)
        golds.append(t["gold"])
    for name, rows in (("calls", calls), ("gold", golds)):
        with open(data / f"{a.set}c2-{name}.jsonl", "w") as fh:
            for r in rows:
                fh.write(json.dumps(r, sort_keys=True) + "\n")
    rec = {"set": f"{a.set}c2", "source_sha256": release_source_hash(ROOT), "from_stage": a.stage,
           "templates_sha256": commit["step2_templates_sha256"], "calls": len(calls), "upstream_failures": upstream,
           "step1_record_sha256": rec_shas,
           "calls_sha256": sha(data / f"{a.set}c2-calls.jsonl"), "gold_sha256": sha(data / f"{a.set}c2-gold.jsonl")}
    out_commit.write_text(json.dumps(rec, indent=2) + "\n")
    print(json.dumps({k: rec[k] for k in ("set", "calls", "upstream_failures", "calls_sha256")}))


if __name__ == "__main__":
    main()
