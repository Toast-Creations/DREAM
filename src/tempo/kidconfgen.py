"""V1.22.0 KIDCONF-v1 panel construction (no model).

Fresh instances of the 1.20 families F1-F3 (tempo.holdout.build_group, unchanged; open intervals, b2 = 0). Each
planned group is built whole (all acts x both histories); only the acts the allocation declares are kept, always with
both histories. Per kept target the public row carries: prefix envelopes, original target, registry order, the BASE
FACT-v1 prompt, the public detection, the RES-DET resolution, the SUB prompt (1.20 rewrite, refres.rewrite_prompt)
and the KEEP prompt (KEEPID-v1, keepid.keep_prompt). Identity comes only from public input.

Construction validity (model-independent; failures are logged and the group redrawn with the next attempt seed):
holdout.build_group checks, every kept target detected with route "resolve", RES-DET resolves a field, and that field
equals the construction label. The last check reads the hidden label AFTER both prompts are built from public input;
it only decides whether the group is a valid instance (same rule as the 1.20 R2 gate, applied at construction).
"""
import hashlib

from . import freshgen as FG, holdout as HO, keepid as KI, kidconf as KC, refgen as RG, refres as RR, render

DEFAULT_CONSONANTS = "bcdfhjk"   # the 1.20 main pool's consonants; new pool names and seeds give fresh worlds


def register_pool(pool, consonants=DEFAULT_CONSONANTS):
    if pool in FG.CONS and FG.CONS[pool] != consonants:
        raise AssertionError(f"pool {pool} already registered with other consonants")
    FG.CONS[pool] = consonants


def call(cid, arm, hist, user, cap=256):
    return {"call_id": cid, "group_id": cid.split("|")[0], "domain": "assembly", "surface": "prose", "k": 0,
            "length": "short", "arm": arm, "pattern": arm, "qtype": "X", "variant": cid, "n_records": 0,
            "evidence_cutoff": 0, "max_new_tokens": cap, "system": render.SYSTEM, "user": user, "history": hist,
            "user_sha256": hashlib.sha256(user.encode()).hexdigest()}


def public_row(tid, w, case, rseed, meta):
    """Public-only construction of BASE, SUB and KEEP prompts for one target."""
    base = HO.prompt(w, case, rseed)
    env = RG.envelopes(w, case, rseed)
    for e in env:
        if base.count(e["raw_text"]) != 1:
            raise AssertionError(f"{tid}: envelope text not found exactly once in the prompt")
    reg = HO.registry(w, case)
    pub = {"target": tid, **meta, "prefix": env, "target_text": case["text"], "registry": reg,
           "registry_order": list(reg), "base_prompt": base}
    return pub


def arms_from_public(pub):
    """(SUB prompt, KEEP prompt, ledger) from the public row only. Raises AssertionError if no public identity."""
    pi = RR.PublicInput.make(pub["prefix"], pub["target_text"], pub["registry_order"])
    det = RR.detect(pub["target_text"])
    if det["route"] != "resolve":
        raise AssertionError(f"{pub['target']}: detector route {det['route']}")
    res = RR.resolve_det(pi, det)
    if not res["field"]:
        raise AssertionError(f"{pub['target']}: RES-DET unresolved ({res.get('reason')})")
    new_t, sub_led = RR.rewrite(pub["target_text"], det, res["field"])
    sub = RR.rewrite_prompt(pub["base_prompt"], pub["target_text"], new_t)
    keep, keep_led = KI.keep_prompt(pub["base_prompt"], pub["target_text"], det["text"], res["field"])
    return sub, keep, {"detection": det, "resolution": res, "sub_ledger": sub_led, "keep_ledger": keep_led,
                       "field": res["field"]}


def build_panel(groups, n_arrival_groups, base_seed, pool, max_attempts=300):
    """groups from kidconf.plan. Returns (public rows, hidden rows, calls by unit, rejected attempts log)."""
    pubs, hid, units, rejected = [], [], [], []
    for gid, fam, rec, bits, block in groups:
        acts = KC.acts_for(block, n_arrival_groups)
        for att in range(max_attempts):
            s = KC.seed_for(base_seed, pool, gid, att)
            try:
                g = HO.build_group(gid, s, fam, rec, bits, pool)
                built = []
                for act in acts:
                    for hist in KC.HISTORIES:
                        case = g["cases"][(act, hist)]
                        tid = f"{gid}|{act}|{hist}"
                        meta = {"component": "primary", "group": gid, "family": fam, "reception": rec, "act": act,
                                "history": hist, "stratum": KC.stratum(fam, rec), "bits": list(bits), "block": block}
                        pub = public_row(tid, g["world"], case, g["render_seed"], meta)
                        sub, keep, led = arms_from_public(pub)
                        if led["field"] != case["field"]:          # construction validity (after public build)
                            raise AssertionError(f"{tid}: public identity differs from construction label")
                        built.append((pub, case, sub, keep, led))
                break
            except AssertionError as e:
                rejected.append({"group": gid, "attempt": att, "reason": str(e)[:200]})
        else:
            raise AssertionError(f"cannot build {gid}")
        by_act = {}
        for pub, case, sub, keep, led in built:
            pubs.append(dict(pub, identity=led))
            hid.append({"target": pub["target"], "group": gid, "family": fam, "reception": rec, "act": pub["act"],
                        "history": pub["history"], "world_seed": s, "pool": pool, "render_seed": g["render_seed"],
                        "gold_field": case["field"], "case": case})
            by_act.setdefault(pub["act"], []).extend(
                [call(f"{pub['target']}|SUB", "SUB", pub["history"], sub),
                 call(f"{pub['target']}|KEEP", "KEEP", pub["history"], keep)])
        units.extend(by_act[a] for a in acts)
    return pubs, hid, units, rejected
