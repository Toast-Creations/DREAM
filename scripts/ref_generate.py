"""Commit the V1.20.0 REFRES inputs and the stage-A call schedule (no model).
Usage: ref_generate.py --hub HUB --set ref|refsmoke [--base-seed N]
Per target (public, data/public/<set>-targets.jsonl): prefix envelopes, original target, registry, the BASE FACT-v1
prompt, the public detection result, the RES-DET resolution and its rewritten prompt (if any), the resolver prompt
(if the route is "resolve"). Hidden (data/hidden/<set>-cases.jsonl): canonical case, gold field, control labels.
Stage A calls (data/<set>A-calls.jsonl, one Qwen3-32B NF4 configuration): per target unit BASE extraction (256),
RESOLVER (128) if the route is "resolve", DET extraction (256) if RES-DET resolved; units in a seeded order, the
call order inside a unit rotated by unit index. Stage B (RES-MODEL extraction) is built after stage A by
ref_stageb.py with frozen rules. Bypass targets: all arms use BASE (no further calls)."""
import argparse
import hashlib
import json
import random
from pathlib import Path

from _bootstrap import ROOT
from dream_core.ledger import release_source_hash
from tempo import holdout as HO, refgen as RG, refres as RR, render

DEFAULT_SEED = {"ref": 20261701, "refsmoke": 20261702}
SCHED_SEED = 20261706


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def call(cid, kind, u, cap):
    return {"call_id": cid, "group_id": cid.split("|")[0], "domain": "assembly", "surface": "prose", "k": 0,
            "length": "short", "arm": kind, "pattern": kind, "qtype": "X", "variant": cid, "n_records": 0,
            "evidence_cutoff": 0, "max_new_tokens": cap, "system": render.SYSTEM, "user": u,
            "user_sha256": hashlib.sha256(u.encode()).hexdigest()}


def package(tid, w, case, rseed, meta):
    prompt = HO.prompt(w, case, rseed)
    env = RG.envelopes(w, case, rseed)
    for e in env:
        if prompt.count(e["raw_text"]) != 1:
            raise AssertionError(f"{tid}: envelope text not found exactly once in the prompt")
    reg = HO.registry(w, case)
    pi = RR.PublicInput.make(env, case["text"], list(reg))
    det = RR.detect(case["text"])
    pub = {"target": tid, **{k: v for k, v in meta.items() if k in ("component", "group", "family", "reception", "act",
                                                                      "history", "stratum", "bits")},
           "prefix": env, "target_text": case["text"], "registry": reg, "registry_order": list(reg),
           "base_prompt": prompt, "detection": det}
    if det["route"] == "resolve":
        dres = RR.resolve_det(pi, det)
        pub["det"] = dres
        pub["resolver_prompt"] = RR.resolver_prompt(pi, det)
        if dres["field"]:
            nt, ledger = RR.rewrite(case["text"], det, dres["field"])
            pub["det_prompt"], pub["det_ledger"] = RR.rewrite_prompt(prompt, case["text"], nt), ledger
    return pub


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", required=True)
    ap.add_argument("--set", choices=["ref", "refsmoke"], required=True)
    ap.add_argument("--base-seed", type=int)
    a = ap.parse_args()
    seed = a.base_seed or DEFAULT_SEED[a.set]
    smoke = a.set == "refsmoke"
    pool, cpool = ("refsmoke", "refsmokectl") if smoke else ("ref", "refctl")
    data = Path(a.hub) / "data"
    (data / "public").mkdir(parents=True, exist_ok=True)
    (data / "hidden").mkdir(parents=True, exist_ok=True)
    if (data / f"COMMITMENT-{a.set}.json").exists():
        raise SystemExit("commitment exists")
    pubs, hid, rejected = [], [], []
    for gi, (fam, rec, bits) in enumerate(RG.main_plan(smoke)):
        gid = f"g{gi + 1:03d}"
        for att in range(300):
            s = int(hashlib.sha256(f"{seed}|{pool}|{gid}|{att}".encode()).hexdigest()[:12], 16)
            try:
                g = HO.build_group(gid, s, fam, rec, bits, pool)
                built = [(k, c, package(f"{gid}|{k[0]}|{k[1]}", g["world"], c, g["render_seed"],
                                        {"component": "primary", "group": gid, "family": fam, "reception": rec,
                                         "act": k[0], "history": k[1], "stratum": f"{fam}|{rec}", "bits": list(bits)}))
                         for k, c in g["cases"].items()]
                break
            except AssertionError as e:
                rejected.append({"group": gid, "attempt": att, "reason": str(e)[:160]})
        else:
            raise SystemExit(f"cannot build {gid}")
        for (act, hist), c, p in built:
            pubs.append(p)
            hid.append({"target": p["target"], "component": "primary", "group": gid, "family": fam, "reception": rec,
                        "act": act, "history": hist, "world_seed": s, "pool": pool, "render_seed": g["render_seed"],
                        "gold_field": c["field"], "case": c})
    # controls
    ctl = []
    kinds = RG.REFUSAL_TYPES if not smoke else ("measure_tie", "measure_missing", "hist_missing_support", "hist_nonunique_occupant")
    reps = 1 if smoke else 2
    n = 0
    for kind in kinds:
        for r in range(reps):
            n += 1
            cid = f"c{n:02d}"
            for att in range(100):
                s = int(hashlib.sha256(f"{seed}|{cpool}|{cid}|{att}".encode()).hexdigest()[:12], 16)
                try:
                    w, c, rs = RG.refusal_control(kind, s, cpool)
                    p = package(f"{cid}|arrival|-", w, c, rs, {"component": "control_refusal", "group": cid, "family": kind,
                                                              "reception": "immediate", "act": "arrival", "history": "-",
                                                              "stratum": "control", "bits": []})
                    break
                except AssertionError as e:
                    rejected.append({"group": cid, "attempt": att, "reason": str(e)[:160]})
            else:
                raise SystemExit(f"cannot build {cid}")
            pubs.append(p)
            hid.append({"target": p["target"], "component": "control_refusal", "group": cid, "family": kind,
                        "act": "arrival", "history": "-", "world_seed": s, "pool": cpool, "render_seed": rs,
                        "gold_field": None, "expected_refusal": c["expected"], "case": c})
    # bypass controls: explicit-name targets from fresh CN groups (bare corrections + explicit names, 2 per act)
    want = [("correction",)] * (2 if smoke else 8) + [(x,) for x in HO.ACTS for _ in range(0 if smoke else 2)]
    if smoke:
        want = [("correction",), ("correction",), ("arrival",), ("removal",)]
    for i, (act,) in enumerate(want):
        n += 1
        cid = f"c{n:02d}"
        for att in range(100):
            s = int(hashlib.sha256(f"{seed}|{cpool}|{cid}|{att}".encode()).hexdigest()[:12], 16)
            try:
                g = HO.build_group(cid, s, "CN_explicit_name", HO.RECEPTION[i % 2], (i & 1, (i >> 1) & 1, 0), cpool)
                c = g["cases"][(act, "A")]
                comp = "control_bare_correction" if act == "correction" and i < (2 if smoke else 8) else "control_explicit"
                p = package(f"{cid}|{act}|A", g["world"], c, g["render_seed"], {"component": comp, "group": cid,
                                                                                 "family": "CN_explicit_name", "reception": HO.RECEPTION[i % 2],
                                                                                 "act": act, "history": "A", "stratum": "control", "bits": []})
                if p["detection"]["route"] != "bypass":
                    raise AssertionError("explicit control not bypassed")
                break
            except AssertionError as e:
                rejected.append({"group": cid, "attempt": att, "reason": str(e)[:160]})
        else:
            raise SystemExit(f"cannot build {cid}")
        pubs.append(p)
        hid.append({"target": p["target"], "component": comp, "group": cid, "family": "CN_explicit_name", "act": act,
                    "history": "A", "world_seed": s, "pool": cpool, "render_seed": g["render_seed"],
                    "gold_field": c["field"], "case": c})
    base = [p["base_prompt"] for p in pubs if p["component"] == "primary"]
    if len(set(base)) != len(base):
        raise SystemExit("duplicate original prompts")
    units = []
    for p in pubs:
        u = [call(f"{p['target']}|BASE", "BASE", p["base_prompt"], 256)]
        if p["detection"]["route"] == "resolve":
            u.append(call(f"{p['target']}|RESOLVER", "RESOLVER", p["resolver_prompt"], 128))
            if p.get("det_prompt"):
                u.append(call(f"{p['target']}|DET", "DET", p["det_prompt"], 256))
        units.append(u)
    random.Random(SCHED_SEED).shuffle(units)
    calls = []
    for j, u in enumerate(units):
        r = j % len(u)
        calls.extend(u[r:] + u[:r])
    files = {"targets": data / f"public/{a.set}-targets.jsonl", "cases": data / f"hidden/{a.set}-cases.jsonl",
             "callsA": data / f"{a.set}A-calls.jsonl"}
    for k, rows in (("targets", pubs), ("cases", hid), ("callsA", calls)):
        with open(files[k], "w") as fh:
            for r in rows:
                fh.write(json.dumps(r, sort_keys=True, default=str) + "\n")
    (data / f"COMMITMENT-{a.set}A.json").write_text(json.dumps({"set": f"{a.set}A", "calls": len(calls),
                                                                  "calls_sha256": sha(files["callsA"])}, indent=1) + "\n")
    rec = {"set": a.set, "base_seed": seed, "source_sha256": release_source_hash(ROOT), "targets": len(pubs),
           "primary_targets": sum(p["component"] == "primary" for p in pubs),
           "controls": {c: sum(p["component"] == c for p in pubs) for c in ("control_refusal", "control_bare_correction", "control_explicit")},
           "stageA_calls": len(calls), "stageA_by_kind": {k: sum(c["arm"] == k for c in calls) for k in ("BASE", "RESOLVER", "DET")},
           "rejected_attempts": rejected, "schedule_seed": SCHED_SEED, **{f"{k}_sha256": sha(p) for k, p in files.items()}}
    (data / f"COMMITMENT-{a.set}.json").write_text(json.dumps(rec, indent=1) + "\n")
    print(json.dumps({k: rec[k] for k in ("set", "targets", "primary_targets", "controls", "stageA_calls", "stageA_by_kind")}),
          "rejected:", len(rejected))


if __name__ == "__main__":
    main()
