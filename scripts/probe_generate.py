"""Build the V1.7.3 precondition probe's committed inputs (no model).

Usage: probe_generate.py --hub HUB --set probe|probesmoke [--base-seed 20261108]
Fresh worlds (new seeds, new name pool disjoint from the pilot's). Writes HUB/data/<set>-{worlds,calls,gold}.jsonl
and COMMITMENT-<set>.json; refuses to overwrite.
"""
import argparse
import collections
import hashlib
import json
from pathlib import Path

from _bootstrap import ROOT
from dream_core.ledger import release_source_hash
from tempo import probe as P, render

CAP = 512
CONDITIONS = [("direct", "C0"), ("direct", "C1"), ("checklist", "C0"), ("checklist", "C1"), ("supplied", "C0")]
# smoke: world index -> [(condition, arm, row)]
SMOKE_PLAN = {
    0: [("direct", "C1", "valid"), ("direct", "C1", "invalid"), ("checklist", "C1", "valid"),
        ("checklist", "C1", "invalid"), ("supplied", "C0", "valid"), ("supplied", "C0", "invalid")],
    1: [("checklist", "C0", "valid"), ("checklist", "C0", "invalid"), ("checklist", "C1", "false_unknown"),
        ("direct", "C0", "false_unknown"), ("supplied", "C0", "false_unknown")],
    2: [("direct", "C0", "valid"), ("direct", "C0", "invalid"), ("checklist", "C1", "valid"),
        ("checklist", "C1", "invalid"), ("checklist", "C0", "unknown_only"), ("supplied", "C0", "unknown_only")],
    3: [("checklist", "C0", "valid"), ("checklist", "C0", "invalid"), ("direct", "C1", "valid"),
        ("direct", "C1", "invalid"), ("supplied", "C0", "valid"), ("supplied", "C0", "invalid")],
}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def build(pool, base_seed, smoke):
    built, rejected = [], []
    for wid, dom, fk, pat, ctl, seed in P.world_specs(pool, base_seed, smoke):
        for attempt in range(60):
            try:
                w, meta, rows = P.build_world(wid, dom, fk, pat, ctl, seed + attempt, pool)
                break
            except AssertionError as e:
                rejected.append({"world_id": wid, "seed": seed + attempt, "reason": str(e)})
        else:
            raise SystemExit(f"could not build {wid}")
        built.append((w, meta, rows))
    return built, rejected


def call_and_gold(w, meta, rows, cond, arm, rk):
    row = rows[rk]
    u = P.user(w, cond, arm, row)
    cid = f"{meta['world_id']}|{cond}|{arm}|{rk}"
    c = {"call_id": cid, "group_id": meta["world_id"], "domain": meta["domain"], "pattern": meta["pair_pattern"],
         "family": meta["family"], "length": "short", "condition": cond, "arm": arm, "qtype": "A0", "row": rk,
         "variant": rk, "n_records": len(row["records"]) if arm == "C1" else 0, "evidence_cutoff": 12,
         "max_new_tokens": CAP, "system": render.SYSTEM, "user": u,
         "user_sha256": hashlib.sha256(u.encode()).hexdigest()}
    g = {"call_id": cid, "type": "action", **row["a0"], "allowed": {f: w.allowed(f) for f in w.asked},
         "predicates": {k: row["predicates"][k] for k, _ in P.predicate_spec(w)}, "condition": cond, "row": rk}
    return c, g


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", required=True)
    ap.add_argument("--set", choices=["probe", "probesmoke"], required=True)
    ap.add_argument("--base-seed", type=int, default=20261108)
    a = ap.parse_args()
    data = Path(a.hub) / "data"
    data.mkdir(parents=True, exist_ok=True)
    commit = data / f"COMMITMENT-{a.set}.json"
    if commit.exists():
        raise SystemExit(f"{commit} exists; inputs are committed")
    smoke = a.set == "probesmoke"
    built, rejected = build(a.set, a.base_seed, smoke)
    calls, golds, wrows = [], [], []
    for i, (w, meta, rows) in enumerate(built):
        plan = SMOKE_PLAN.get(i, []) if smoke else [(c, arm, rk) for rk in rows for c, arm in CONDITIONS]
        for cond, arm, rk in plan:
            c, g = call_and_gold(w, meta, rows, cond, arm, rk)
            calls.append(c); golds.append(g)
        wrows.append({**meta, "world": {k: v for k, v in vars(w).items() if k != "pad_names"},
                      "rows": rows})
    for name, rs in (("worlds", wrows), ("calls", calls), ("gold", golds)):
        with open(data / f"{a.set}-{name}.jsonl", "w") as fh:
            for r in rs:
                fh.write(json.dumps(r, sort_keys=True) + "\n")
    rec = {"set": a.set, "base_seed": a.base_seed, "source_sha256": release_source_hash(ROOT),
           "worlds": len(built), "calls": len(calls), "rejected_attempts": rejected,
           "by_condition": dict(collections.Counter(f"{c['condition']}:{c['arm']}" for c in calls)),
           "by_row": dict(collections.Counter(c["row"] for c in calls)),
           **{f"{p}_sha256": sha(data / f"{a.set}-{p}.jsonl") for p in ("worlds", "calls", "gold")}}
    commit.write_text(json.dumps(rec, indent=2) + "\n")
    print(json.dumps({k: rec[k] for k in ("set", "worlds", "calls", "by_condition", "by_row", "calls_sha256")}),
          "rejected:", len(rejected))


if __name__ == "__main__":
    main()
