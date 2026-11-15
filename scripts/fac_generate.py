"""Commit the V1.18.0 factored-assertion corpus (no model).
Usage: fac_generate.py --hub HUB --set fac|facsmoke [--base-seed N]
Main: 120 groups x 4 variants x {EXCLUSIVE, FACTORED} = 960 calls + 12 control groups x 2 histories x 2 interfaces =
48 calls (all distinct; FULL history in both). Smoke: 4 groups + 2 controls = 40 calls. Strata: group g ->
factored.STRATA[g // 15] (target part G/D x prefix length 3/4 x mention order); lure alternates within stratum
(lure_G for even, lure_W for odd position); arrival template g % 12. Redraw only if a build / equivalence / tie
assertion fails (logged). Calls are written in a precommitted balanced schedule (seeded unit order, interface order
alternating by unit); run with order=as_committed."""
import argparse
import collections
import hashlib
import json
import random
from pathlib import Path

from _bootstrap import ROOT
from dream_core.ledger import release_source_hash
from tempo import ctxablate as CA, factored as FA, prose, prose_study as PS, render

DEFAULT_SEED = {"fac": 20261501, "facsmoke": 20261502}
SIZES = {"fac": (120, 12), "facsmoke": (4, 2)}
SCHEDULE_SEED = 20261106


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def call(cid, gid, kind, iface, u, k, t):
    return {"call_id": cid, "group_id": gid, "domain": "assembly", "surface": "prose", "k": k, "length": "short",
            "arm": iface, "pattern": kind, "qtype": "X", "variant": kind, "n_records": k, "evidence_cutoff": t,
            "max_new_tokens": 256, "system": render.SYSTEM, "user": u, "user_sha256": hashlib.sha256(u.encode()).hexdigest()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", required=True)
    ap.add_argument("--set", choices=["fac", "facsmoke"], required=True)
    ap.add_argument("--base-seed", type=int)
    a = ap.parse_args()
    seed = a.base_seed or DEFAULT_SEED[a.set]
    smoke = a.set.endswith("smoke")
    pool, cpool = ("facsmoke", "facctlsmoke") if smoke else ("fac", "facctl")
    n_g, n_c = SIZES[a.set]
    data = Path(a.hub) / "data"
    (data / "public").mkdir(parents=True, exist_ok=True)
    (data / "hidden").mkdir(parents=True, exist_ok=True)
    commit = data / f"COMMITMENT-{a.set}.json"
    if commit.exists():
        raise SystemExit(f"{commit} exists")
    units, targets, golds, groups, rejected = [], [], [], [], []
    for g in range(n_g):
        gid = f"g{g + 1:03d}"
        si = g * 2 if smoke else g // 15
        stratum = FA.STRATA[si % len(FA.STRATA)]
        lure = "lure_G" if (g if smoke else g % 15) % 2 == 0 else "lure_W"
        tmpl = g % 12
        for att in range(80):
            s = int(hashlib.sha256(f"{seed}|{pool}|{gid}|{att}".encode()).hexdigest()[:12], 16)
            try:
                w, out, rs, meta = FA.build_group(gid, s, stratum, lure, pool, tmpl)
                built = {}
                for v, recs in out.items():
                    for r in recs:
                        PS.check_equivalent(r, prose.prose_line(w, r, rs))
                    ex = CA.full_prompt(w, recs, rs)
                    built[v] = (recs, prose.prose_line(w, recs[-1], rs), ex, FA.factored_prompt(ex))
                break
            except AssertionError as e:
                rejected.append({"group": gid, "attempt": att, "reason": str(e)[:200]})
        else:
            raise SystemExit(f"cannot build {gid}")
        groups.append({"group": gid, "world_seed": s, "render_seed": rs, "stratum": list(stratum), "lure": lure,
                       "arrival_template": tmpl, "pool": pool, **meta})
        for v, (recs, text, ex, fa) in built.items():
            reg = CA.registry(w, recs)
            u = []
            for iface, prompt in (("EXCLUSIVE", ex), ("FACTORED", fa)):
                cid = f"{gid}|{v}|{iface}"
                u.append(call(cid, gid, v, iface, prompt, len(recs), recs[-1]["received_at"]))
                targets.append({"cell": cid, "call_id": cid, "group": gid, "variant": v, "interface": iface, "registry": reg,
                                "received_at": recs[-1]["received_at"], "text": text, "control": False})
                golds.append({"cell": cid, "group": gid, "variant": v, "interface": iface, "gold": CA.public(recs)[-1],
                              "prefix": CA.public(recs)[:-1], "text": text, "stratum": list(stratum), "lure": lure,
                              "anchor": meta["anchor"], "P": meta["P"], "control": False})
            units.append(u)
    for c in range(n_c):
        cg = f"c{c + 1:02d}"
        for att in range(80):
            s = int(hashlib.sha256(f"{seed}|{cpool}|{cg}|{att}".encode()).hexdigest()[:12], 16)
            try:
                w, hist, rs, text = CA.build_control(cg, s, cpool)
                ps = {}
                for alt in "AB":
                    ex = CA.full_prompt(w, hist[alt], rs, text)
                    ps[alt] = (ex, FA.factored_prompt(ex))
                    for r in hist[alt][:-1]:
                        PS.check_equivalent(r, prose.prose_line(w, r, rs))
                if ps["A"][0] == ps["B"][0] or CA.registry(w, hist["A"]) != CA.registry(w, hist["B"]):
                    raise AssertionError("control histories not distinct / registry differs")
                break
            except AssertionError as e:
                rejected.append({"group": cg, "attempt": att, "reason": str(e)[:200]})
        else:
            raise SystemExit(f"cannot build {cg}")
        groups.append({"group": cg, "world_seed": s, "render_seed": rs, "control": True, "pool": cpool})
        reg = CA.registry(w, hist["A"])
        for alt in "AB":
            u = []
            for iface, prompt in zip(FA.INTERFACES, ps[alt]):
                cid = f"{cg}|ctl|{alt}|{iface}"
                u.append(call(cid, cg, "control", iface, prompt, 4, hist[alt][-1]["received_at"]))
                targets.append({"cell": cid, "call_id": cid, "group": cg, "variant": "control", "alternative": alt,
                                "interface": iface, "registry": reg, "received_at": hist[alt][-1]["received_at"],
                                "text": text, "control": True})
                golds.append({"cell": cid, "group": cg, "variant": "control", "alternative": alt, "interface": iface,
                              "gold": CA.public(hist[alt])[-1], "prefix": CA.public(hist[alt])[:-1], "text": text,
                              "control": True})
            units.append(u)
    random.Random(SCHEDULE_SEED).shuffle(units)
    calls = []
    for j, u in enumerate(units):
        calls.extend(u if j % 2 == 0 else list(reversed(u)))
    paths = {"calls": data / f"{a.set}-calls.jsonl", "targets": data / f"public/{a.set}-targets.jsonl",
             "gold": data / f"hidden/{a.set}-gold.jsonl", "groups": data / f"hidden/{a.set}-groups.jsonl"}
    for k, rows in (("calls", calls), ("targets", targets), ("gold", golds), ("groups", groups)):
        with open(paths[k], "w") as fh:
            for r in rows:
                fh.write(json.dumps(r, sort_keys=True) + "\n")
    rec = {"set": a.set, "base_seed": seed, "source_sha256": release_source_hash(ROOT), "groups": n_g, "control_groups": n_c,
           "calls": len(calls), "variant_counts": dict(collections.Counter(t["variant"] for t in targets if t["interface"] == "FACTORED")),
           "rejected_attempts": rejected, "strata": [list(s) for s in FA.STRATA],
           "schedule": f"seeded unit order (seed {SCHEDULE_SEED}), interface order alternating by unit; order=as_committed",
           **{f"{k}_sha256": sha(p) for k, p in paths.items()}}
    commit.write_text(json.dumps(rec, indent=2) + "\n")
    print(json.dumps({k: rec[k] for k in ("set", "groups", "control_groups", "calls")}), "rejected:", len(rejected))


if __name__ == "__main__":
    main()
