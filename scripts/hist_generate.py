"""Build milestone 2's committed inputs (no model). Usage: hist_generate.py --hub HUB --set hist|histsmoke
Writes HUB/data/<set>-{histories,calls,gold}.jsonl and COMMITMENT-<set>.json (refuses to overwrite).
Every call depends only on prose records, so all calls (X per record, R per checkpoint) are committed up front."""
import argparse
import collections
import hashlib
import json
from pathlib import Path

from _bootstrap import ROOT
from dream_core.ledger import release_source_hash
from tempo import history as Hm, render

CAP = {"X": 256, "R": 384}
SMOKE_X = (0, 1)  # smoke: all extractions for histories 0,1; readouts for all 4


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def build(pool, base_seed, smoke):
    out, rejected = [], []
    for hid, dom, fk, p, seed in Hm.specs(pool, base_seed, smoke):
        for att in range(60):
            try:
                w, h = Hm.build_history(hid, dom, fk, p, seed + att, pool)
                break
            except AssertionError as e:
                rejected.append({"history_id": hid, "seed": seed + att, "reason": str(e)})
        else:
            raise SystemExit(f"cannot build {hid}")
        out.append((w, h))
    return out, rejected


def calls_for(w, h, do_x=True):
    calls, golds = [], []
    recs = h["records"]
    meta = {k: h[k] for k in ("domain", "pattern", "pattern_name")}
    if do_x:
        for k in range(1, Hm.N_RECORDS + 1):
            u = Hm.extraction_prompt(w, recs, k)
            cid = f"{h['history_id']}|X|r{k}"
            calls.append({"call_id": cid, "group_id": h["history_id"], **meta, "system_name": "X", "k": k,
                          "length": "short", "arm": "X", "qtype": "X", "variant": f"r{k}", "n_records": k,
                          "evidence_cutoff": recs[k - 1]["received_at"], "max_new_tokens": CAP["X"],
                          "system": render.SYSTEM, "user": u, "user_sha256": hashlib.sha256(u.encode()).hexdigest()})
            golds.append({"call_id": cid, "type": "record", "gold": Hm.public(recs[k - 1]),
                          "registry": {f: Hm.allowed_values(w, f) for f in Hm.registry_fields(w, recs[:k])},
                          "text": render.record_line(w, recs[k - 1])})
    for cp in h["checkpoints"]:
        k = cp["k"]
        u = Hm.readout_prompt(w, recs, k)
        cid = f"{h['history_id']}|R|cp{k}"
        calls.append({"call_id": cid, "group_id": h["history_id"], **meta, "system_name": "R", "k": k,
                      "length": "short", "arm": "R", "qtype": "R", "variant": f"cp{k}", "n_records": k,
                      "evidence_cutoff": cp["now"], "max_new_tokens": CAP["R"], "system": render.SYSTEM,
                      "user": u, "user_sha256": hashlib.sha256(u.encode()).hexdigest()})
        golds.append({"call_id": cid, "type": "facts", "gold": {f: cp["gold_state"][f] for f in w.asked},
                      "allowed": {f: w.allowed(f) for f in w.asked}, "focal_field": h["focal_field"],
                      "side_field": w.side})
    return calls, golds


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", required=True)
    ap.add_argument("--set", choices=["hist", "histsmoke"], required=True)
    ap.add_argument("--base-seed", type=int, default=20261109)
    a = ap.parse_args()
    data = Path(a.hub) / "data"
    data.mkdir(parents=True, exist_ok=True)
    commit = data / f"COMMITMENT-{a.set}.json"
    if commit.exists():
        raise SystemExit(f"{commit} exists")
    smoke = a.set == "histsmoke"
    built, rejected = build(a.set, a.base_seed, smoke)
    calls, golds, hs = [], [], []
    for i, (w, h) in enumerate(built):
        c, g = calls_for(w, h, do_x=(not smoke) or i in SMOKE_X)
        calls += c; golds += g; hs.append(h)
    for name, rows in (("histories", hs), ("calls", calls), ("gold", golds)):
        with open(data / f"{a.set}-{name}.jsonl", "w") as fh:
            for r in rows:
                fh.write(json.dumps(r, sort_keys=True) + "\n")
    rec = {"set": a.set, "base_seed": a.base_seed, "source_sha256": release_source_hash(ROOT),
           "histories": len(hs), "calls": len(calls), "rejected_attempts": rejected,
           "by_system": dict(collections.Counter(c["system_name"] for c in calls)),
           **{f"{p}_sha256": sha(data / f"{a.set}-{p}.jsonl") for p in ("histories", "calls", "gold")}}
    commit.write_text(json.dumps(rec, indent=2) + "\n")
    print(json.dumps({k: rec[k] for k in ("set", "histories", "calls", "by_system", "calls_sha256")}),
          "rejected:", len(rejected))


if __name__ == "__main__":
    main()
