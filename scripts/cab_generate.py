"""Commit the V1.17.0 record-context ablation corpus (no model).
Usage: cab_generate.py --hub HUB --set cab|cabsmoke [--base-seed N]
Main: 120 groups x 4 variants x FULL/LOCAL = 960 calls + 12 control groups x (FULL_A, FULL_B, LOCAL) = 36 calls.
Smoke: 4 groups (32) + 2 controls (6) = 38 calls. Strata: group g -> STRATA[g // 15] (smoke: g); arrival template
g % 12. Redraw (logged) only if a build/equivalence/tie assertion fails. Writes:
  HUB/data/<set>-calls.jsonl            calls in the precommitted balanced schedule (run with order=as_committed)
  HUB/data/public/<set>-targets.jsonl   per scored cell: call id(s), condition, registry, reception time, text
  HUB/data/hidden/<set>-gold.jsonl      per scored cell: canonical target record, canonical prefix, labels
  HUB/data/hidden/<set>-groups.jsonl    world seeds, renderer seeds, strata, template ids
  HUB/data/COMMITMENT-<set>.json"""
import argparse
import collections
import hashlib
import json
import random
from pathlib import Path

from _bootstrap import ROOT
from dream_core.ledger import release_source_hash
from tempo import ctxablate as CA, prose, prose_study as PS, render

DEFAULT_SEED = {"cab": 20261401, "cabsmoke": 20261402}
SIZES = {"cab": (120, 12), "cabsmoke": (4, 2)}
SCHEDULE_SEED = 20261106


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def call(cid, gid, kind, cond, u, k, t):
    return {"call_id": cid, "group_id": gid, "domain": "assembly", "surface": "prose", "k": k, "length": "short",
            "arm": cond, "pattern": kind, "qtype": "X", "variant": kind, "n_records": k, "evidence_cutoff": t,
            "max_new_tokens": 256,
            "system": render.SYSTEM, "user": u, "user_sha256": hashlib.sha256(u.encode()).hexdigest()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", required=True)
    ap.add_argument("--set", choices=["cab", "cabsmoke"], required=True)
    ap.add_argument("--base-seed", type=int)
    a = ap.parse_args()
    seed = a.base_seed or DEFAULT_SEED[a.set]
    smoke = a.set.endswith("smoke")
    pool, cpool = ("cabsmoke", "cabctlsmoke") if smoke else ("cab", "cabctl")
    n_g, n_c = SIZES[a.set]
    data = Path(a.hub) / "data"
    (data / "public").mkdir(parents=True, exist_ok=True)
    (data / "hidden").mkdir(parents=True, exist_ok=True)
    commit = data / f"COMMITMENT-{a.set}.json"
    if commit.exists():
        raise SystemExit(f"{commit} exists")
    units, targets, golds, groups, rejected = [], [], [], [], []
    kinds = collections.Counter()
    for g in range(n_g):
        gid = f"g{g + 1:03d}"
        stratum = CA.STRATA[g if smoke else g // 15]
        tmpl = g % 12
        for att in range(80):
            s = int(hashlib.sha256(f"{seed}|{pool}|{gid}|{att}".encode()).hexdigest()[:12], 16)
            try:
                w, out, rs = CA.build_group(gid, s, stratum, pool, tmpl)
                built = {}
                for v, recs in out.items():
                    text = prose.prose_line(w, recs[-1], rs)
                    for r in recs:
                        PS.check_equivalent(r, prose.prose_line(w, r, rs))
                    full = CA.full_prompt(w, recs, rs)
                    local = CA.local_prompt(full)
                    CA.check_diff(full, local)
                    built[v] = (recs, text, full, local)
                break
            except AssertionError as e:
                rejected.append({"group": gid, "attempt": att, "reason": str(e)[:200]})
        else:
            raise SystemExit(f"cannot build {gid}")
        groups.append({"group": gid, "world_seed": s, "render_seed": rs, "stratum": list(stratum), "arrival_template": tmpl,
                       "pool": pool})
        for v, (recs, text, full, local) in built.items():
            kinds[v] += 1
            reg = CA.registry(w, recs)
            pairs = []
            for cond, u in (("FULL", full), ("LOCAL", local)):
                cid = f"{gid}|{v}|{cond}"
                pairs.append(call(cid, gid, v, cond, u, len(recs), recs[-1]["received_at"]))
                targets.append({"cell": cid, "call_id": cid, "group": gid, "variant": v, "condition": cond,
                                "registry": reg, "received_at": recs[-1]["received_at"], "text": text, "control": False})
                golds.append({"cell": cid, "group": gid, "variant": v, "condition": cond, "gold": CA.public(recs)[-1],
                              "prefix": CA.public(recs)[:-1], "text": text, "stratum": list(stratum), "control": False})
            units.append(pairs)
    for c in range(n_c):
        cg = f"c{c + 1:02d}"
        for att in range(80):
            s = int(hashlib.sha256(f"{seed}|{cpool}|{cg}|{att}".encode()).hexdigest()[:12], 16)
            try:
                w, hist, rs, text = CA.build_control(cg, s, cpool)
                fa, fb = CA.full_prompt(w, hist["A"], rs, text), CA.full_prompt(w, hist["B"], rs, text)
                la, lb = CA.local_prompt(fa), CA.local_prompt(fb)
                if la != lb or fa == fb or CA.registry(w, hist["A"]) != CA.registry(w, hist["B"]):
                    raise AssertionError("control pair not identical in LOCAL / distinct in FULL")
                for h in hist.values():
                    for r in h[:-1]:
                        PS.check_equivalent(r, prose.prose_line(w, r, rs))
                break
            except AssertionError as e:
                rejected.append({"group": cg, "attempt": att, "reason": str(e)[:200]})
        else:
            raise SystemExit(f"cannot build {cg}")
        groups.append({"group": cg, "world_seed": s, "render_seed": rs, "control": True, "pool": cpool})
        reg = CA.registry(w, hist["A"])
        tr = hist["A"][-1]["received_at"]
        trip = [call(f"{cg}|ctl|FULL_A", cg, "control", "FULL", fa, 4, tr), call(f"{cg}|ctl|FULL_B", cg, "control", "FULL", fb, 4, tr),
                call(f"{cg}|ctl|LOCAL", cg, "control", "LOCAL", la, 4, tr)]
        units.append(trip)
        for alt in ("A", "B"):
            for cond, cid in (("FULL", f"{cg}|ctl|FULL_{alt}"), ("LOCAL", f"{cg}|ctl|LOCAL")):
                cell = f"{cg}|ctl|{cond}|{alt}"
                targets.append({"cell": cell, "call_id": cid, "group": cg, "variant": "control", "alternative": alt,
                                "condition": cond, "registry": reg, "received_at": hist[alt][-1]["received_at"],
                                "text": text, "control": True})
                golds.append({"cell": cell, "group": cg, "variant": "control", "alternative": alt, "condition": cond,
                              "gold": CA.public(hist[alt])[-1], "prefix": CA.public(hist[alt])[:-1], "text": text,
                              "control": True})
    rng = random.Random(SCHEDULE_SEED)
    rng.shuffle(units)
    calls = []
    for j, u in enumerate(units):
        order = u if j % 2 == 0 else list(reversed(u))
        calls.extend(order)
    paths = {"calls": data / f"{a.set}-calls.jsonl", "targets": data / f"public/{a.set}-targets.jsonl",
             "gold": data / f"hidden/{a.set}-gold.jsonl", "groups": data / f"hidden/{a.set}-groups.jsonl"}
    for k, rows in (("calls", calls), ("targets", targets), ("gold", golds), ("groups", groups)):
        with open(paths[k], "w") as fh:
            for r in rows:
                fh.write(json.dumps(r, sort_keys=True) + "\n")
    rec = {"set": a.set, "base_seed": seed, "source_sha256": release_source_hash(ROOT), "groups": n_g, "control_groups": n_c,
           "calls": len(calls), "scored_cells": len(targets), "cached_local_controls": n_c,
           "variant_counts": dict(kinds), "rejected_attempts": rejected, "schedule": f"seeded unit order (seed {SCHEDULE_SEED}), order alternating by unit; run with order=as_committed",
           "strata": [list(s) for s in CA.STRATA], "templates": 12,
           **{f"{k}_sha256": sha(p) for k, p in paths.items()}}
    commit.write_text(json.dumps(rec, indent=2) + "\n")
    print(json.dumps({k: rec[k] for k in ("set", "groups", "control_groups", "calls", "scored_cells")}), "rejected:", len(rejected))


if __name__ == "__main__":
    main()
