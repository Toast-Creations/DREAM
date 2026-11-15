"""Commit the prose-robustness study's initial extraction calls (no model).
Usage: prose_generate.py --hub HUB --set prose|prosesmoke [--base-seed 20261110]
Writes HUB/data/<set>-{histories,calls,gold}.jsonl and COMMITMENT-<set>.json; refuses to overwrite."""
import argparse
import collections
import hashlib
import json
from pathlib import Path

from _bootstrap import ROOT
from dream_core.ledger import release_source_hash
from tempo import history as Hm, prose_study as P, render
import hist_generate as HG

CAP = 256


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", required=True)
    ap.add_argument("--set", choices=["prose", "prosesmoke"], required=True)
    ap.add_argument("--base-seed", type=int, default=20261110)
    a = ap.parse_args()
    data = Path(a.hub) / "data"
    data.mkdir(parents=True, exist_ok=True)
    commit = data / f"COMMITMENT-{a.set}.json"
    if commit.exists():
        raise SystemExit(f"{commit} exists")
    smoke = a.set == "prosesmoke"
    built, rejected = HG.build(a.set, a.base_seed, smoke)
    if smoke:
        built = built[:2]
    calls, golds, hs = [], [], []
    for i, (w, h) in enumerate(built):
        surfaces = P.SURFACES if (not smoke or i == 0) else ("prose",)
        h["texts"] = {s: [P.line_fn(w, h, s)(r) for r in h["records"]] for s in P.SURFACES}
        for r, t in zip(h["records"], h["texts"]["prose"]):
            P.check_equivalent(r, t)
        for s in surfaces:
            for k in range(1, Hm.N_RECORDS + 1):
                u = P.extraction_prompt(w, h, s, k)
                cid = f"{h['history_id']}|{s}|r{k}"
                calls.append({"call_id": cid, "group_id": h["history_id"], "domain": h["domain"],
                              "pattern": h["pattern"], "pattern_name": h["pattern_name"], "surface": s, "k": k,
                              "length": "short", "arm": s, "qtype": "X", "variant": f"r{k}", "n_records": k,
                              "evidence_cutoff": h["records"][k - 1]["received_at"], "max_new_tokens": CAP,
                              "system": render.SYSTEM, "user": u, "user_sha256": hashlib.sha256(u.encode()).hexdigest()})
                golds.append({"call_id": cid, "type": "record", "gold": Hm.public(h["records"][k - 1]),
                              "registry": {f: Hm.allowed_values(w, f) for f in Hm.registry_fields(w, h["records"][:k])},
                              "text": h["texts"][s][k - 1]})
        hs.append(h)
    for name, rows in (("histories", hs), ("calls", calls), ("gold", golds)):
        with open(data / f"{a.set}-{name}.jsonl", "w") as fh:
            for r in rows:
                fh.write(json.dumps(r, sort_keys=True) + "\n")
    rec = {"set": a.set, "base_seed": a.base_seed, "source_sha256": release_source_hash(ROOT), "histories": len(hs),
           "calls": len(calls), "rejected_attempts": rejected,
           "by_surface": dict(collections.Counter(c["surface"] for c in calls)),
           **{f"{p}_sha256": sha(data / f"{a.set}-{p}.jsonl") for p in ("histories", "calls", "gold")}}
    commit.write_text(json.dumps(rec, indent=2) + "\n")
    print(json.dumps({k: rec[k] for k in ("set", "histories", "calls", "by_surface", "calls_sha256")}),
          "rejected:", len(rejected))


if __name__ == "__main__":
    main()
