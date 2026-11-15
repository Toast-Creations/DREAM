"""V1.7.3 fresh-world precondition probe (development; static inference only).

24 new worlds (12 delivery, 6 assembly-slot, 6 assembly-stock), each with one applicable / inapplicable state pair for
the same single action (delivery `take X`, assembly `install G in T`), short history (6 records). 8 control rows
inside declared worlds: 4 "unknown only" (one required condition unresolved, none known false) and 4 "false +
unknown" (one requirement false, another unresolved).

Conditions: direct (the existing A0 query), checklist-first (a fixed `preconditions` object before the A0 fields),
correct-checklist (C0 state plus the evidence-supported predicate values, then the direct A0 query).

Every gold value is computed twice: applicability and successor by two action implementations (worlds.apply_own and
keycheck), and the predicate vector both from the per-field supported values (three-valued conjunction) and by
enumerating every compatible joint state. They must agree or generation fails.
"""
import copy
import hashlib
import itertools
import json
import random

from . import diag, enumcheck, generate as G, render, resolve, worlds
from .worlds import CARRIED, EMPTY, NO, UNKNOWN, YES

N_RECORDS = 6
FAMILIES = ([("delivery", None)] * 12) + ([("assembly", "slot")] * 6) + ([("assembly", "stock")] * 6)
# pair pattern per world (cycled within family so each family covers patterns 1-5)
PAIR_PATTERNS = [1, 2, 3, 4, 5, 1, 2, 3, 4, 5, 1, 2] + [1, 2, 3, 4, 5, 3] + [1, 2, 3, 4, 5, 4]
# control allocation: world index -> control kind. Delivery: worlds 0,1 unknown-only; 2,3 false+unknown (hands
# occupied: the courier carries the side crate). Assembly slot worlds 12,13 / stock worlds 18,19: one of each; the
# false requirement is part not on hand (slot kind) or slot occupied by W (stock kind).
CONTROLS = {0: "unknown_only", 1: "unknown_only", 2: "false_unknown", 3: "false_unknown",
            12: "unknown_only", 13: "false_unknown", 18: "unknown_only", 19: "false_unknown"}
SMOKE_FAMILIES = [("delivery", None), ("delivery", None), ("assembly", "slot"), ("assembly", "stock")]
SMOKE_PATTERNS = [3, 2, 5, 1]
SMOKE_CONTROLS = {1: "false_unknown", 2: "unknown_only"}

TV = (True, False, UNKNOWN)


# ------------------------------------------------------------------ predicates

def predicate_spec(w):
    """[(key, text)] — every prerequisite of the probe action, in fixed order, with concrete names."""
    if w.domain == "delivery":
        return [("crate_at_your_place", f"crate {w.x} rests at {w.you}, the place where you are"),
                ("hands_empty", "your hands are empty (you are not carrying any crate)"),
                ("crate_portable", f"crate {w.x} is portable")]
    return [("part_on_hand", f"part {w.g} is on hand"),
            ("slot_empty", f"slot {w.t} is empty"),
            ("connector_matches", f"part {w.g}'s connector equals the connector that slot {w.t} accepts now "
                                  f"(no adapter is fitted)")]


def predicates_of_state(w, s):
    """Exact predicate values in one fully specified joint state (asked fields)."""
    if w.domain == "delivery":
        return {"crate_at_your_place": s[w.focal] == w.you,
                "hands_empty": not any(v == CARRIED for f, v in s.items() if f.endswith(".location")),
                "crate_portable": True}
    return {"part_on_hand": s[w.stock_f] == YES, "slot_empty": s[w.slot_f] == EMPTY,
            "connector_matches": w.parts[w.g]["type"] == w.k}


def _tv(field_state, test):
    kind, val = field_state
    vals = [val] if kind == "value" else list(val)
    outs = {test(v) for v in vals}
    return outs.pop() if len(outs) == 1 else UNKNOWN


def predicates_from_fields(w, per):
    """Three-valued predicates from per-field supported values (implementation 1)."""
    if w.domain == "delivery":
        loc = [f for f in per if f.endswith(".location")]
        hands = [_tv(per[f], lambda v: v != CARRIED) for f in loc]
        he = False if False in hands else (UNKNOWN if UNKNOWN in hands else True)
        return {"crate_at_your_place": _tv(per[w.focal], lambda v: v == w.you), "hands_empty": he,
                "crate_portable": True}
    return {"part_on_hand": _tv(per[w.stock_f], lambda v: v == YES),
            "slot_empty": _tv(per[w.slot_f], lambda v: v == EMPTY),
            "connector_matches": w.parts[w.g]["type"] == w.k}


def conj3(vals):
    vals = list(vals)
    if False in vals:
        return False
    if UNKNOWN in vals:
        return UNKNOWN
    return True


def predicate_gold(w, records):
    """(predicates, applicability) — checked against enumeration of compatible joint states (implementation 2)."""
    per, states = enumcheck.supported_set(records, w.asked, G.NOW)
    p1 = predicates_from_fields(w, per)
    by_state = [predicates_of_state(w, s) for s in states]
    p2 = {k: (by_state[0][k] if len({d[k] for d in by_state}) == 1 else UNKNOWN) for k in p1}
    if p1 != p2:
        raise AssertionError(f"predicate implementations disagree: {p1} vs {p2}")
    app_enum = {all(d.values()) for d in by_state}
    app2 = app_enum.pop() if len(app_enum) == 1 else UNKNOWN
    if conj3(p1.values()) != app2:
        raise AssertionError("three-valued conjunction disagrees with enumeration")
    return p1, app2


# ------------------------------------------------------------------ world construction

def fixed_lines(w, carried=None):
    lines = list(w.fixed_lines())
    if w.domain == "delivery" and carried:
        old = f"You are at {w.you}, with empty hands. You do not move unless you act."
        if old not in lines:
            raise AssertionError("hands line not found")
        lines[lines.index(old)] = (f"You are at {w.you}, carrying crate {carried}. You do not move unless you act.")
    return lines + diag.DOMAIN_FACTS[w.domain]


def header(w, carried=None):
    return [f"WORLD ({w.domain})", "", "Action rules:"] + ["- " + r for r in w.rules()] + \
           ["", "Fixed facts (these never change):"] + ["- " + x for x in fixed_lines(w, carried)]


def _records(w, rng, pattern, side, assign, u, v, y1, y2, c0, opts, res, chains):
    recs, intended, _, truth = G.base_records(pattern, side, w.focal, u, v, w.side, y1, y2, assign, c0, opts, res)
    pad = G.take_padding(chains, N_RECORDS - len(recs))
    out = G.finalize(recs + copy.deepcopy(pad))
    G.check_no_ties(out)
    if pattern != 6:
        G.truth_check(out, truth, pattern, side)
    return out, intended


def _row(w, records, kind, origin, carried=None):
    now_state = G.agree_state(records, resolve.fields_of(records), G.NOW)
    a0 = G.a0_gold(w, records)
    preds, app = predicate_gold(w, records)
    if app != a0["applicable"]:
        raise AssertionError(f"predicate conjunction {app} != action implementations {a0['applicable']}")
    hands_carrying = [f for f, s in now_state.items() if f.endswith(".location") and s[0] == "value"
                      and s[1] == CARRIED]
    if w.domain == "delivery" and [w.ent(f) for f in hands_carrying] != ([carried] if carried else []):
        raise AssertionError("hands line disagrees with the records")
    return {"kind": kind, "origin": origin, "records": records, "now_state": now_state, "a0": a0,
            "predicates": preds, "carried": carried}


def build_world(world_id, domain, focal_kind, pair_pattern, control, seed, pool):
    rng = random.Random(seed)
    names = worlds.Names(pool, rng)
    w = worlds.make_world(domain, rng, names, focal_kind)
    u, v = rng.sample(w.focal_values, 2)
    y1, y2 = w.side_values(rng)
    base_assign = {w.focal: u, w.side: y1}
    base_assign.update(w.other_init(rng))
    base_assign = {f: base_assign[f] for f in w.asked}
    c0 = w.focal_start_uncertain if domain == "delivery" else u
    opts = rng.sample([u, v], 2)
    res = rng.choice(opts)
    chains = G.padding_chains(w, rng, N_RECORDS * 2)
    rows = {}
    for side in ("a", "b"):
        recs, _ = _records(w, rng, pair_pattern, side, base_assign, u, v, y1, y2, c0, opts, res, chains)
        r = _row(w, recs, "pair", f"pattern {pair_pattern} side {side}")
        rows[side] = r
    labels = {}
    for side, r in rows.items():
        app = r["a0"]["applicable"]
        if app == UNKNOWN or app is UNKNOWN:
            raise AssertionError("pair applicability undetermined")
        labels["valid" if app else "invalid"] = r
    if set(labels) != {"valid", "invalid"}:
        raise AssertionError("pair not balanced")
    fv, fi = (G.flat({f: labels[x]["now_state"][f] for f in w.asked}) for x in ("valid", "invalid"))
    for f in [f for f in w.asked if fv[f] != fi[f] and f != w.focal]:
        if w.apply_own(dict(fi, **{f: fv[f]}))[0] != w.apply_own(fi)[0]:
            raise AssertionError("pair differs in a second prerequisite")
    if fv[w.focal] == fi[w.focal]:
        raise AssertionError("pair does not differ in the focal prerequisite")
    out = {"valid": labels["valid"], "invalid": labels["invalid"]}
    if control:
        a = dict(base_assign)
        carried = None
        if control == "false_unknown":
            if domain == "delivery":
                a[w.side] = CARRIED
                carried = w.ent(w.side)
            elif focal_kind == "slot":
                a[w.stock_f] = NO
            else:
                a[w.slot_f] = w.w
        y_obs = a[w.side]
        recs, _ = _records(w, rng, 6, "a", a, u, v, y_obs, y2, c0, opts, res, chains)
        r = _row(w, recs, control, f"pattern 6 side a ({control})", carried=carried)
        want = UNKNOWN if control == "unknown_only" else False
        if r["a0"]["applicable"] != want:
            raise AssertionError(f"control {control} applicability {r['a0']['applicable']}")
        vals = list(r["predicates"].values())
        if control == "unknown_only" and (False in vals or vals.count(UNKNOWN) != 1):
            raise AssertionError("unknown-only control shape")
        if control == "false_unknown" and (vals.count(False) != 1 or vals.count(UNKNOWN) != 1):
            raise AssertionError("false+unknown control shape")
        out[control] = r
    meta = {"world_id": world_id, "domain": domain, "focal_kind": focal_kind, "pair_pattern": pair_pattern,
            "control": control, "seed": seed, "pool": pool, "focal_field": w.focal, "asked": w.asked,
            "family": "location" if domain == "delivery" else ("slot occupancy" if focal_kind == "slot"
                                                                 else "stock availability")}
    return w, meta, out


def world_specs(pool, base_seed, smoke=False):
    fams = SMOKE_FAMILIES if smoke else FAMILIES
    pats = SMOKE_PATTERNS if smoke else PAIR_PATTERNS
    ctl = SMOKE_CONTROLS if smoke else CONTROLS
    specs = []
    for i, ((dom, fk), p) in enumerate(zip(fams, pats)):
        wid = f"{pool}-{dom[:3]}-{fk or 'loc'}-{i:02d}"
        seed = int(hashlib.sha256(f"{base_seed}|{wid}".encode()).hexdigest()[:12], 16)
        specs.append((wid, dom, fk, p, ctl.get(i), seed))
    return specs


# ------------------------------------------------------------------ prompts

def checklist_lines(w):
    out = ["Requirements of this action (for \"preconditions\"):"]
    out += [f"- {json.dumps(k)}: {t}" for k, t in predicate_spec(w)]
    return out


def checklist_query(w):
    """The existing A0 query with one fixed `preconditions` field first."""
    fields_ex = ", ".join(f"{json.dumps(f)}: \"...\"" for f in w.asked)
    pre_ex = ", ".join(f"{json.dumps(k)}: ..." for k, _ in predicate_spec(w))
    return ["", "QUERY (action consequence)", f"Suppose you were to do this one action now: {w.action_text()}. "
            "It has not been done; you are only considering it.",
            "If the action is not allowed right now it fails and changes nothing.",
            "Answer four things, in this order:",
            "0. \"preconditions\": for each requirement listed below, true if it holds right now, false if it does "
            "not, or \"unknown\" if the records do not settle it."] + checklist_lines(w) + \
           ["1. \"applicable\": true if the action would be allowed right now, false if not, or \"unknown\" if the "
            "records do not settle it.",
            "2. \"predicted_next_facts\": the value of each fact below right after the action, if you did it.",
            "3. \"observed_world_facts\": the value of each fact below in the actual world now, given that you have "
            "only considered the action.", "Facts:"] + render.fields_block(w) + \
           ["", 'Reply with only a JSON object: {"preconditions": {' + pre_ex + '}, "applicable": ..., '
            '"predicted_next_facts": {' + fields_ex + '}, "observed_world_facts": {' + fields_ex + "}}"]


def tv_text(v):
    return "unknown" if v == UNKNOWN else ("true" if v else "false")


def supplied_checklist(w, preds):
    return ["", "Requirement check for the action below, computed from all records received so far (verified):"] + \
           [f"- {t}: {tv_text(preds[k])}" for k, t in predicate_spec(w)]


def user(w, condition, arm, row, now=G.NOW):
    lines = header(w, row["carried"])
    if condition == "supplied":
        lines += render.evidence_block(w, "C0", row["records"], row["now_state"], now)
        lines += supplied_checklist(w, row["predicates"])
        lines += render.action_query(w)
    else:
        state = row["now_state"] if arm == "C0" else None
        lines += render.evidence_block(w, arm, row["records"], state, now)
        lines += render.action_query(w) if condition == "direct" else checklist_query(w)
    return "\n".join(lines)
