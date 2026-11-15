"""Seeded generation of temporal groups: base pattern histories, nested irrelevant padding, matched variants,
queries and gold. Every gold value is computed by resolver 1 and must equal resolver 2 (enumcheck); every plan
status comes from two solvers; the A0 successor comes from two implementations; the pattern's declared intended
focal answers are a third check. Any disagreement raises and the group is rejected.

Group = one independently generated world + history pattern. Variants inside a group (pair sides a/b, the irrelevant
variant i, lengths short/medium/long) are correlated observations of that group, never independent samples.
"""
import copy
import hashlib
import json
import random

from . import enumcheck, resolve, worlds
from .worlds import UNKNOWN

NOW = 12
LENGTHS = {"short": 6, "medium": 14, "long": 30}
PATTERNS = {1: "change", 2: "delayed", 3: "correction", 4: "return", 5: "scoped_correction", 6: "uncertain"}
# (P0 target time, K0 cutoff) per pattern
TIMES = {1: (3, 4), 2: (6, 7), 3: (3, 4), 4: (4, 5), 5: (3, 4), 6: (4, 5)}
OPTION_IDS = ["A", "B", "C", "D"]


def R(kind, event_at, received_at, payload, status="verified", key=None, src="base"):
    return {"key": key, "kind": kind, "status": status, "event_at": event_at, "received_at": received_at,
            "payload": payload, "_src": src}


def base_records(p, side, F, u, v, Y, y1, y2, assign, c0, opts, res):
    """Return (records, intended focal value now, lure focal value or None, truth overrides)."""
    prov = "provisional" if p in (3, 5) else "verified"
    a = dict(assign)
    if p == 6:
        a[F] = c0
    init = R("initial", 0, 0, {"assign": a}, status=prov, key="init")
    if p == 1:
        if side == "a":
            return [init, R("change", 5, 5, {"field": F, "from": u, "to": v})], v, u, {}
        return [init, R("observation", 5, 5, {"field": F, "value": u})], u, None, {}
    if p == 2:
        mv = R("change", 5, 5, {"field": F, "from": u, "to": v})
        if side == "a":
            return [init, mv, R("observation", 2, 9, {"field": F, "value": u})], v, u, {}
        return [init, mv, R("change", 8, 9, {"field": F, "from": v, "to": u})], u, v, {}
    if p == 3:
        if side == "a":
            return [init, R("correction", None, 6, {"target": "init", "field": F, "value": v, "valid_from": 0,
                                                     "valid_to": None})], v, u, {F: [(0, v)]}
        return [init, R("observation", 6, 6, {"field": F, "value": u})], u, None, {}
    if p == 4:
        m1 = R("change", 3, 3, {"field": F, "from": u, "to": v})
        if side == "a":
            return [init, m1, R("change", 6, 6, {"field": F, "from": v, "to": u})], u, v, {}
        return [init, m1, R("observation", 6, 6, {"field": F, "value": v})], v, None, {}
    if p == 5:
        if side == "a":
            return [init, R("correction", None, 6, {"target": "init", "field": F, "value": v, "valid_from": 0,
                                                     "valid_to": None})], v, u, {F: [(0, v)]}
        return [init, R("correction", None, 6, {"target": "init", "field": Y, "value": y2, "valid_from": 0,
                                                 "valid_to": None})], u, None, {Y: [(0, y2)]}
    if p == 6:
        unc = R("uncertain_change", 3, 3, {"field": F, "from": c0, "options": list(opts)})
        if side == "a":
            return [init, unc, R("observation", 6, 6, {"field": Y, "value": y1})], UNKNOWN, None, {"_hidden": res}
        return [init, unc, R("observation", 6, 6, {"field": F, "value": res})], res, None, {}
    raise ValueError(p)


def padding_chains(w, rng, need):
    chains, total = [], 0
    while total < need:
        field, cur = w.new_pad_entity(rng)
        t = rng.randint(1, 6)
        recs = [R("observation", t, t, {"field": field, "value": cur}, src="pad")]
        traj = [(t, cur)]
        for _ in range(rng.randint(1, 3)):
            t += rng.randint(1, 3)
            if t > 11:
                break
            nv = w.pad_next(field, cur, rng)
            recs.append(R("change", t, t, {"field": field, "from": cur, "to": nv}, src="pad"))
            traj.append((t, nv)); cur = nv
        change_times = {tt for tt, _ in traj}
        if rng.random() < 0.5 and len(traj) > 1:
            cands = [x for x in range(traj[0][0] + 1, traj[-1][0] + 2) if x not in change_times and x <= 10]
            if cands:
                te = rng.choice(cands)
                val = [vv for tt, vv in traj if tt <= te][-1]
                tr = min(NOW, te + rng.randint(2, 5))
                pos = max(i for i, (tt, _) in enumerate(traj) if tt <= te) + 1
                recs.insert(pos, R("observation", te, tr, {"field": field, "value": val}, src="pad"))
        chains.append(recs)
        total += len(recs)
    return chains


def take_padding(chains, n):
    out = []
    for ch in chains:
        if len(out) >= n:
            break
        out += ch[: n - len(out)]
    if len(out) != n:
        raise ValueError("not enough padding")
    return out


def finalize(records):
    """Sort by reception (base before padding before irrelevant at equal times), assign ordinals and rids, resolve
    correction targets. Returns new list; the internal key/_src fields stay for scoring only."""
    rank = {"base": 0, "pad": 1, "irrelevant": 2}
    recs = [copy.deepcopy(r) for r in records]
    order = sorted(range(len(recs)), key=lambda i: (recs[i]["received_at"], rank[recs[i]["_src"]], i))
    out = []
    for n, i in enumerate(order, 1):
        r = recs[i]
        r["ordinal"], r["rid"] = n, f"r{n:02d}"
        out.append(r)
    by_key = {r["key"]: r["rid"] for r in out if r["key"]}
    for r in out:
        if r["kind"] == "correction":
            r["payload"]["target"] = by_key[r["payload"]["target"]]
    return out


def check_no_ties(records):
    seen = set()
    for f, t, *_ in resolve._assertions(records):
        if (f, t) in seen:
            raise AssertionError(f"two assertions of {f} at time {t}")
        seen.add((f, t))


def agree_state(records, fields, t):
    """Resolver 1 and resolver 2 must agree on every field."""
    r1 = {f: resolve.value_at(records, f, t) for f in fields}
    r2 = {f: enumcheck.supported(records, f, t) for f in fields}
    for f in fields:
        a, b = r1[f], r2[f]
        if a[0] != b[0] or (a[0] == "value" and a[1] != b[1]) or (a[0] == "unknown" and sorted(a[1]) != sorted(b[1])):
            raise AssertionError(f"resolver disagreement on {f} at {t}: {a} vs {b}")
    return r1


def flat(state):
    return {f: (v[1] if v[0] == "value" else UNKNOWN) for f, v in state.items()}


def decide(w, records):
    """Key option under the printed policy over the supported state set at NOW."""
    _, states = enumcheck.supported_set(records, w.asked, NOW)
    status = {}
    for key in w.plans:
        res = [worlds.plan_status(w, s, key) for s in states]
        status[key] = {"guaranteed": all(ok for ok, _ in res),
                       "cost": max(c for _, c in res) if all(ok for ok, _ in res) else None,
                       "valid_in": sum(ok for ok, _ in res), "n_states": len(states)}
    good = {k: s["cost"] for k, s in status.items() if s["guaranteed"]}
    if not good:
        return "OBS", status
    best = min(good.values())
    winners = [k for k, c in good.items() if c == best]
    if len(winners) != 1:
        raise AssertionError(f"tied optimal plans {winners}")
    return winners[0], status


def a0_gold(w, records):
    per, states = enumcheck.supported_set(records, w.asked, NOW)
    outs = []
    for s in states:
        own, kc = w.apply_own(s), w.apply_keycheck(s)
        if own != kc:
            raise AssertionError(f"A0 implementations disagree: {own} vs {kc}")
        outs.append(own)
    apps = {ok for ok, _ in outs}
    applicable = apps.pop() if len(apps) == 1 else UNKNOWN
    pred = {}
    for f in w.asked:
        vals = {o[1][f] for o in outs}
        pred[f] = vals.pop() if len(vals) == 1 else UNKNOWN
    observed = flat(per)
    changed = [f for f in w.asked if pred[f] != observed[f]]
    effect = [w.focal] if w.domain == "delivery" else [w.slot_f, w.stock_f]
    return {"applicable": applicable, "predicted": pred, "observed": observed, "changed_fields": changed,
            "effect_fields": effect, "preserve_fields": [f for f in w.asked if f not in effect]}


def truth_check(records, truth_over, p, side):
    """Verified records must be true of the hidden physical trajectory; a corrected provisional statement must be
    false and its correction true. The trajectory is the records' own except for declared overrides."""
    withdrawn = {(r["payload"]["target"], r["payload"]["field"]) for r in records if r["kind"] == "correction"}
    for r in records:
        if r["kind"] == "initial" and r["status"] == "provisional":
            for f, v in r["payload"]["assign"].items():
                true_v = truth_over[f][0][1] if f in truth_over else v
                if ((r["rid"], f) in withdrawn) == (v == true_v):
                    raise AssertionError(f"provisional statement truth mismatch on {f}")
        if r["kind"] == "correction":
            f = r["payload"]["field"]
            if f not in truth_over or truth_over[f][0][1] != r["payload"]["value"]:
                raise AssertionError("correction not true of hidden trajectory")
    if p == 6 and side == "a" and truth_over.get("_hidden") is None:
        raise AssertionError("uncertain pattern needs a hidden actual value")


def build_group(group_id, domain, pattern, seed, pool, focal_kind=None):
    rng = random.Random(seed)
    names = worlds.Names(pool, rng)
    w = worlds.make_world(domain, rng, names, focal_kind)
    F, Y = w.focal, w.side
    u, v = rng.sample(w.focal_values, 2)
    y1, y2 = w.side_values(rng)
    assign = {F: u, Y: y1}
    assign.update(w.other_init(rng))
    assign = {f: assign[f] for f in w.asked}
    if domain == "delivery":
        c0, opts = w.focal_start_uncertain, rng.sample([u, v], 2)
    else:
        c0, opts = u, rng.sample([u, v], 2)
    res = rng.choice(opts)
    sides = {}
    for side in ("a", "b"):
        recs, intended, lure, truth = base_records(pattern, side, F, u, v, Y, y1, y2, assign, c0, opts, res)
        sides[side] = {"base": recs, "intended": intended, "lure": lure, "truth": truth}
    n_base = len(sides["a"]["base"])
    if len(sides["b"]["base"]) != n_base:
        raise AssertionError("pair sides differ in record count")
    chains = padding_chains(w, rng, LENGTHS["long"] - n_base)
    letters = OPTION_IDS[:]
    keys = list(w.plans) + ["OBS"]
    rng.shuffle(keys)
    option_map = dict(zip(letters, keys))
    t_p, cutoff = TIMES[pattern]
    group = {"group_id": group_id, "domain": domain, "pattern": pattern, "pattern_name": PATTERNS[pattern],
             "focal_kind": focal_kind, "seed": seed, "pool": pool, "focal_field": F, "side_field": Y,
             "asked": w.asked, "option_map": option_map, "p0_time": t_p, "k0_cutoff": cutoff, "now": NOW,
             "u": u, "v": v, "variants": {}}
    for length, target in LENGTHS.items():
        pad = take_padding(chains, target - n_base)
        var = {}
        for side in ("a", "b"):
            var[side] = finalize(sides[side]["base"] + copy.deepcopy(pad))
        # irrelevant variant: D0 (side a) plus one change of the side field, at time 7
        ycur = resolve.value_at(var["a"], Y, 7)[1]
        irr = R("change", 7, 7, {"field": Y, "from": ycur, "to": w.side_next(ycur, random.Random(seed * 7 + 1))},
                src="irrelevant")
        var["i"] = finalize(sides["a"]["base"] + copy.deepcopy(pad) + [irr])
        out = {}
        for vk, recs in var.items():
            check_no_ties(recs)
            all_fields = resolve.fields_of(recs)
            now_state = agree_state(recs, all_fields, NOW)
            key, status = decide(w, recs)
            out[vk] = {"records": recs, "now_state": now_state, "key": key, "plan_status": status}
            side = "a" if vk in ("a", "i") else "b"
            if vk in ("a", "b"):
                truth_check(recs, sides[side]["truth"], pattern, side)
                got = flat({F: now_state[F]})[F]
                if got != sides[vk]["intended"]:
                    raise AssertionError(f"pattern intent {sides[vk]['intended']} != resolved {got}")
        if out["a"]["key"] == out["b"]["key"]:
            raise AssertionError("relevant pair keys not disjoint")
        if out["i"]["key"] != out["a"]["key"]:
            raise AssertionError("irrelevant variant changed the key")
        a = out["a"]["records"]
        out["S0"] = flat(agree_state(a, w.asked, NOW))
        out["P0"] = flat(agree_state(a, w.asked, t_p))
        k_prefix = resolve.prefix(a, cutoff)
        out["K0"] = flat(agree_state(k_prefix, w.asked, t_p))
        out["k0_records"] = k_prefix
        out["A0"] = a0_gold(w, a)
        for vk in ("a", "b"):
            lure = sides[vk]["lure"]
            if lure is not None:
                recs = copy.deepcopy(out[vk]["records"])
                lure_states = [dict(s, **{F: lure}) for s in enumcheck.supported_set(recs, w.asked, NOW)[1]]
                out[vk]["lure_key"] = _decide_states(w, lure_states)
            else:
                out[vk]["lure_key"] = None
        group["variants"][length] = out
    # keys must be identical across lengths
    for vk in ("a", "b", "i"):
        if len({group["variants"][L][vk]["key"] for L in LENGTHS}) != 1:
            raise AssertionError("key changed across lengths")
    for q in ("S0", "P0", "K0"):
        if len({json.dumps(group["variants"][L][q], sort_keys=True) for L in LENGTHS}) != 1:
            raise AssertionError(f"{q} gold changed across lengths")
    group["hidden_truth"] = {s: sides[s]["truth"] for s in sides}
    return w, group


def _decide_states(w, states):
    good = {}
    for key in w.plans:
        res = [worlds.plan_status(w, s, key) for s in states]
        if all(ok for ok, _ in res):
            good[key] = max(c for _, c in res)
    if not good:
        return "OBS"
    best = min(good.values())
    return [k for k, c in good.items() if c == best][0]


def group_specs(pool, base_seed, per_domain_pattern=2):
    """24 main groups: per domain, 6 patterns x 2. Assembly's two groups per pattern differ in focal kind."""
    specs, n = [], 0
    for domain in ("delivery", "assembly"):
        for p in PATTERNS:
            for j in range(per_domain_pattern):
                fk = None if domain == "delivery" else ("slot", "stock")[j % 2]
                gid = f"{pool}-{domain[:3]}-p{p}-{j}"
                seed = int(hashlib.sha256(f"{base_seed}|{gid}".encode()).hexdigest()[:12], 16)
                specs.append((gid, domain, p, seed, fk))
                n += 1
    return specs
