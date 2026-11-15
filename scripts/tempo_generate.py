"""Build the temporal pilot's committed inputs (no model). Writes into HUB/data:
  <set>-groups.jsonl  full groups: worlds, records per variant, gold, hidden truth   (scorer only)
  <set>-calls.jsonl   one row per model call: identifiers + exact system/user text + output cap (model-visible only)
  <set>-gold.jsonl    one row per call: gold answer (scorer only; the runner never opens it)
  COMMITMENT-<set>.json  sha256 of the three files, seeds, source hash
Usage: tempo_generate.py --hub HUB --set main|smoke [--base-seed N]
Refuses to overwrite an existing commitment.
"""
import argparse
import hashlib
import json
from pathlib import Path

from _bootstrap import ROOT
from dream_core.ledger import release_source_hash
from tempo import generate as G, render, worlds

CAPS = {"D0": 64, "D1": 64, "I1": 64, "S0": 384, "P0": 256, "K0": 256, "A0": 512}
C0_QUERIES = ("D0", "D1", "I1", "A0")
C1_QUERIES = ("D0", "D1", "I1", "S0", "P0", "K0", "A0")
VARIANT = {"D0": "a", "D1": "b", "I1": "i", "S0": "a", "P0": "a", "K0": "a", "A0": "a"}
SMOKE_SPECS = [("delivery", 3, None), ("delivery", 6, None), ("assembly", 2, "stock"), ("assembly", 5, "slot")]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def calls_for(w, group, lengths_queries):
    calls, golds = [], []
    om = group["option_map"]
    letter = {k: L for L, k in om.items()}
    for length, arm, q in lengths_queries:
        var = group["variants"][length]
        vk = VARIANT[q]
        now = group["now"]
        if q == "K0":
            records, now = var["k0_records"], group["k0_cutoff"]
        else:
            records = var[vk]["records"]
        state = var[vk]["now_state"] if arm == "C0" else None
        t = group["p0_time"] if q in ("P0", "K0") else None
        user = render.user_prompt(w, arm, q, records, state, now, option_map=om, t=t)
        cid = f"{group['group_id']}|{length}|{arm}|{q}"
        calls.append({"call_id": cid, "group_id": group["group_id"], "domain": group["domain"],
                      "pattern": group["pattern"], "pattern_name": group["pattern_name"], "length": length, "arm": arm,
                      "qtype": q, "variant": vk, "n_records": len(records) if arm == "C1" else 0,
                      "evidence_cutoff": now, "option_ids": sorted(om) if q in ("D0", "D1", "I1") else None,
                      "max_new_tokens": CAPS[q], "system": render.SYSTEM, "user": user,
                      "user_sha256": hashlib.sha256(user.encode()).hexdigest()})
        if q in ("D0", "D1", "I1"):
            other = {"D0": "b", "D1": "a", "I1": "b"}[q]
            lure = var[vk if vk != "i" else "a"].get("lure_key")
            g = {"type": "decision", "acceptable": [letter[var[vk]["key"]]], "key_plan": var[vk]["key"],
                 "pair_other_option": letter[var[other]["key"]], "obs_option": letter["OBS"],
                 "lure_option": letter[lure] if lure else None}
        elif q in ("S0", "P0", "K0"):
            g = {"type": "facts", "gold": var[q], "allowed": {f: w.allowed(f) for f in w.asked},
                 "focal_field": group["focal_field"], "side_field": group["side_field"]}
        else:
            g = {"type": "action", **var["A0"], "allowed": {f: w.allowed(f) for f in w.asked}}
        golds.append({"call_id": cid, **g})
    return calls, golds


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", required=True)
    ap.add_argument("--set", choices=["main", "smoke"], required=True)
    ap.add_argument("--base-seed", type=int, default=20261105)
    a = ap.parse_args()
    data = Path(a.hub) / "data"
    data.mkdir(parents=True, exist_ok=True)
    commit = data / f"COMMITMENT-{a.set}.json"
    if commit.exists():
        raise SystemExit(f"{commit} exists; inputs are committed")
    if a.set == "main":
        specs = G.group_specs("main", a.base_seed)
    else:
        specs = []
        for i, (dom, p, fk) in enumerate(SMOKE_SPECS):
            gid = f"smoke-{dom[:3]}-p{p}-{i}"
            specs.append((gid, dom, p, int(hashlib.sha256(f"{a.base_seed}|{gid}".encode()).hexdigest()[:12], 16), fk))
    groups, calls, golds, rejected = [], [], [], []
    for gid, dom, p, seed, fk in specs:
        attempt = 0
        while True:
            s = seed + attempt
            try:
                w, g = G.build_group(gid, dom, p, s, a.set, fk)
                break
            except AssertionError as e:
                rejected.append({"group_id": gid, "seed": s, "reason": str(e)})
                attempt += 1
                if attempt > 50:
                    raise
        if a.set == "main":
            lq = [(L, arm, q) for L in G.LENGTHS for arm, qs in (("C0", C0_QUERIES), ("C1", C1_QUERIES)) for q in qs]
        else:
            lq = [("short", arm, q) for arm, qs in (("C0", C0_QUERIES), ("C1", C1_QUERIES)) for q in qs]
            if len(groups) < 2:
                lq += [("long", arm, q) for arm in ("C0", "C1") for q in ("D0", "A0")]
        c, gd = calls_for(w, g, lq)
        g["world"] = {k: v for k, v in vars(w).items() if k != "pad_names"}
        groups.append(g); calls += c; golds += gd
    for path, rows in (("groups", groups), ("calls", calls), ("gold", golds)):
        with open(data / f"{a.set}-{path}.jsonl", "w") as fh:
            for r in rows:
                fh.write(json.dumps(r, sort_keys=True) + "\n")
    names = {}
    for g in groups:
        names[g["group_id"]] = sorted({x for k, x in g["world"].items() if isinstance(x, str) and x[:1].isupper()})
    rec = {"set": a.set, "base_seed": a.base_seed, "source_sha256": release_source_hash(ROOT),
           "groups": len(groups), "calls": len(calls), "rejected_attempts": rejected,
           **{f"{p}_sha256": sha(data / f"{a.set}-{p}.jsonl") for p in ("groups", "calls", "gold")},
           "group_seeds": {gid: g["seed"] for gid, g in zip([s[0] for s in specs], groups)}}
    commit.write_text(json.dumps(rec, indent=2) + "\n")
    print(json.dumps({k: rec[k] for k in ("set", "groups", "calls", "calls_sha256")}, indent=1),
          "rejected attempts:", len(rejected))


if __name__ == "__main__":
    main()
