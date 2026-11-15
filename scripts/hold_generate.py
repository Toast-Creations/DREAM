"""Commit the V1.19.0 structural-holdout inputs (no model).
Usage: hold_generate.py --hub HUB --set hold|holdsmoke [--base-seed N]
hold:      64 primary groups (4 held-out families x 2 receptions x 8 factor settings) + 16 calibration groups
           (CN explicit name, C1 one-hop: 8 each); each group 4 acts x 2 histories = 8 targets -> 640 targets.
holdsmoke: 4 familiar groups (CN, C1 x immediate/delayed) -> 32 targets.
For each model (SMALL, LARGE) a calls file <set>SMALL / <set>LARGE with the same prompts in a frozen within-model
permutation (seed per model), run with order=as_committed; block order SMALL then LARGE. Redraws only under
model-independent construction checks (logged). Writes data/<set>{SMALL,LARGE}-calls.jsonl, COMMITMENT-<set>{SMALL,
LARGE}.json (calls_sha256 for the runner), data/public/<set>-targets.jsonl, data/hidden/<set>-cases.jsonl and
data/COMMITMENT-<set>.json."""
import argparse
import hashlib
import json
import random
from pathlib import Path

from _bootstrap import ROOT
from dream_core.ledger import release_source_hash
from tempo import holdout as HO, render

DEFAULT_SEED = {"hold": 20261601, "holdsmoke": 20261602}
MODELS = ("SMALL", "LARGE")
PERM_SEED = {"SMALL": 20261611, "LARGE": 20261612}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def plan(set_name):
    out = []
    if set_name == "hold":
        for fam in HO.FAMILIES:
            for rec in HO.RECEPTION:
                for b in range(8):
                    out.append(("primary", fam, rec, (b & 1, (b >> 1) & 1, (b >> 2) & 1), "hold"))
        for fam in HO.CAL_FAMILIES:
            for i in range(8):
                out.append(("calibration", fam, HO.RECEPTION[i % 2], ((i >> 1) & 1, (i >> 2) & 1, i & 1), "holdcal"))
    else:
        for fam, rec, bits in (("CN_explicit_name", "immediate", (0, 1, 0)), ("CN_explicit_name", "delayed", (1, 0, 1)),
                               ("C1_one_hop", "immediate", (1, 1, 1)), ("C1_one_hop", "delayed", (0, 0, 0))):
            out.append(("smoke", fam, rec, bits, "holdsmoke"))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", required=True)
    ap.add_argument("--set", choices=["hold", "holdsmoke"], required=True)
    ap.add_argument("--base-seed", type=int)
    a = ap.parse_args()
    seed = a.base_seed or DEFAULT_SEED[a.set]
    data = Path(a.hub) / "data"
    (data / "public").mkdir(parents=True, exist_ok=True)
    (data / "hidden").mkdir(parents=True, exist_ok=True)
    if (data / f"COMMITMENT-{a.set}.json").exists():
        raise SystemExit("commitment exists")
    targets, cases, prompts, rejected = [], [], [], []
    for gi, (comp, fam, rec, bits, pool) in enumerate(plan(a.set)):
        gid = f"{comp[0]}{gi + 1:03d}"
        for att in range(200):
            s = int(hashlib.sha256(f"{seed}|{pool}|{gid}|{att}".encode()).hexdigest()[:12], 16)
            try:
                g = HO.build_group(gid, s, fam, rec, bits, pool)
                built = {k: HO.prompt(g["world"], c, g["render_seed"]) for k, c in g["cases"].items()}
                break
            except AssertionError as e:
                rejected.append({"group": gid, "attempt": att, "reason": str(e)[:160]})
        else:
            raise SystemExit(f"cannot build {gid}")
        stratum = f"{fam}|{rec}"
        for (act, hist), c in g["cases"].items():
            tid = f"{gid}|{act}|{hist}"
            u = built[(act, hist)]
            prompts.append((tid, u))
            targets.append({"target": tid, "group": gid, "component": comp, "family": fam, "reception": rec, "bits": list(bits),
                            "stratum": stratum, "act": act, "history": hist, "registry": HO.registry(g["world"], c),
                            "text": c["text"]})
            cases.append({"target": tid, "group": gid, "component": comp, "family": fam, "reception": rec, "bits": list(bits),
                          "stratum": stratum, "act": act, "history": hist, "world_seed": s, "pool": pool,
                          "render_seed": g["render_seed"], "case": {k: v for k, v in c.items()}})
    if len({u for _, u in prompts}) != len(prompts):
        raise SystemExit("duplicate prompts")
    files = {"targets": data / f"public/{a.set}-targets.jsonl", "cases": data / f"hidden/{a.set}-cases.jsonl"}
    for k, rows in (("targets", targets), ("cases", cases)):
        with open(files[k], "w") as fh:
            for r in rows:
                fh.write(json.dumps(r, sort_keys=True, default=str) + "\n")
    rec = {"set": a.set, "base_seed": seed, "source_sha256": release_source_hash(ROOT), "groups": len(plan(a.set)),
           "targets": len(targets), "calls_per_model": len(prompts), "rejected_attempts": rejected,
           "block_order": list(MODELS), "within_model_permutation_seeds": PERM_SEED,
           **{f"{k}_sha256": sha(p) for k, p in files.items()}}
    for m in MODELS:
        order = list(prompts)
        random.Random(PERM_SEED[m]).shuffle(order)
        p = data / f"{a.set}{m}-calls.jsonl"
        with open(p, "w") as fh:
            for tid, u in order:
                fh.write(json.dumps({"call_id": f"{tid}|{m}", "group_id": tid.split("|")[0], "domain": "assembly",
                                     "surface": "prose", "k": 0, "length": "short", "arm": m, "pattern": tid.split("|")[1],
                                     "qtype": "X", "variant": tid, "n_records": 0, "evidence_cutoff": 0,
                                     "max_new_tokens": 256, "system": render.SYSTEM, "user": u,
                                     "user_sha256": hashlib.sha256(u.encode()).hexdigest()}, sort_keys=True) + "\n")
        (data / f"COMMITMENT-{a.set}{m}.json").write_text(json.dumps({"set": f"{a.set}{m}", "calls": len(order),
                                                                        "calls_sha256": sha(p)}, indent=1) + "\n")
        rec[f"calls_{m}_sha256"] = sha(p)
    (data / f"COMMITMENT-{a.set}.json").write_text(json.dumps(rec, indent=1) + "\n")
    print(json.dumps({k: rec[k] for k in ("set", "groups", "targets", "calls_per_model")}), "rejected:", len(rejected))


if __name__ == "__main__":
    main()
