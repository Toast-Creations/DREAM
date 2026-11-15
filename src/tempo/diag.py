"""V1.7.2 temporal diagnostic (development only): explicit domain defaults, decision-policy wording, a state-first
two-call workflow, and balanced prerequisite pairs. Built from the 1.7.1 pilot's committed main groups (short length).

Nothing here changes the 1.7.1 prompt path: render.py is untouched, and tests check that it still reproduces the
committed pilot prompts byte for byte. The new text lives only in this module.

Blocks (see the run hub's design/DIAGNOSTIC-PLAN.md):
  A  completed domain facts, original decision wording, four options            (C0, C1; D0/D1)
  B  completed domain facts, policy wording POLICY_B, same four options         (C0, C1; D0/D1)
  C  state-first: C1 readout (call 1), then B's decision with the verbatim model-written record added (call 2)
  D  A0 on one applicable and one inapplicable variant per group, plus the 4 original uncertain A0 controls
  E  B's packets with the observation option removed, determined rows only (pre-declared optional block)
"""
import copy

from . import generate as G, render, resolve, worlds
from .worlds import UNKNOWN

# Model-facing statements of defaults the solvers already assume (amendment D1). They change no gold value.
DOMAIN_FACTS = {
    "delivery": [
        "All listed roads are open. Road availability does not change in this episode. Only the listed roads exist.",
        "Only the listed places exist.",
        "While you carry out a plan, nothing changes except through your own actions.",
    ],
    "assembly": [
        "There are no adapters in this episode, and no adapter is fitted to any slot. Installation uses the printed "
        "native connector types.",
        "Only the listed slots exist.",
        "While you carry out a plan, nothing changes except through your own actions.",
    ],
}

# The 1.7.1 decision wording (block A); a test checks it is exactly what render.decision_query prints.
POLICY_ORIGINAL = ("Choose the cheapest option whose plan is sure to be allowed at every step and to reach the goal, "
                   "given what the records establish about now. If the records leave a needed fact unknown, so that "
                   "no plan is sure to work, choose the option that asks for an observation first.")

POLICY_B = ("Apply the printed action rules to the current state supported by the records. Provisional reports count "
            "as accepted information until corrected. Select the lowest-cost listed plan that is valid at every step "
            "and reaches the goal in every state consistent with that information. Select the observation option only "
            "if unresolved information prevents any listed plan from meeting that rule. A report's age or provisional "
            "label alone does not require a new observation.")

# Block E: B without the sentence about the (removed) observation option.
POLICY_E = ("Apply the printed action rules to the current state supported by the records. Provisional reports count "
            "as accepted information until corrected. Select the lowest-cost listed plan that is valid at every step "
            "and reaches the goal in every state consistent with that information. A report's age or provisional "
            "label alone does not require a new observation.")

STATE_RECORD_INTRO = ("Current-state record written by you in an earlier step from the records above. It was not "
                      "checked and may contain mistakes; the records above remain the evidence:")

POLICIES = {"A": POLICY_ORIGINAL, "B": POLICY_B, "E": POLICY_E}


def header_complete(w):
    lines = [f"WORLD ({w.domain})", "", "Action rules:"] + ["- " + r for r in w.rules()]
    lines += ["", "Fixed facts (these never change):"] + ["- " + x for x in w.fixed_lines() + DOMAIN_FACTS[w.domain]]
    return lines


def decision_query(w, option_map, policy, drop_obs=False):
    lines = ["", "QUERY (decision)", w.goal_line(), policy, "Options:"]
    for oid, key in option_map.items():
        if drop_obs and key == "OBS":
            continue
        lines.append(f"[{oid}] " + (worlds.OBS_OPTION_TEXT if key == "OBS" else w.plan_text(key)))
    lines += ["", 'Reply with only a JSON object: {"choice": "<option ID>"}']
    return lines


def head_text(w, arm, records, state, now):
    return "\n".join(header_complete(w) + render.evidence_block(w, arm, records, state, now))


def step2_user(head, raw, tail):
    """C step 2: original history + the verbatim, uncorrected model-written record + B's decision query."""
    return head + "\n\n" + STATE_RECORD_INTRO + "\n" + raw + "\n" + tail


def user(w, arm, records, state, now, query_lines):
    return head_text(w, arm, records, state, now) + "\n" + "\n".join(query_lines)


# ------------------------------------------------------------------ gold

def supported_states(w, records):
    from . import enumcheck
    return enumcheck.supported_set(records, w.asked, G.NOW)[1]


def decision_gold(w, group, var, side, drop_obs=False):
    om = group["option_map"]
    letter = {k: L for L, k in om.items()}
    other = {"a": "b", "b": "a"}[side]
    states = supported_states(w, var[side]["records"])
    plan_valid = {L: all(worlds.plan_status(w, s, k)[0] for s in states) for L, k in om.items() if k != "OBS"}
    lure = var[side].get("lure_key")
    return {"type": "decision", "acceptable": [letter[var[side]["key"]]], "key_plan": var[side]["key"],
            "pair_other_option": letter[var[other]["key"]], "obs_option": None if drop_obs else letter["OBS"],
            "lure_option": letter[lure] if lure else None, "plan_valid": plan_valid,
            "determined": var[side]["key"] != "OBS"}


# ------------------------------------------------------------------ D: prerequisite pairs

def _resolved(w, records):
    G.check_no_ties(records)
    now_state = G.agree_state(records, resolve.fields_of(records), G.NOW)
    return {"records": records, "now_state": now_state, "a0": G.a0_gold(w, records)}


def d_variants(w, group, length="short"):
    """{'valid': {...}, 'invalid': {...}} for one group, each with records, now_state and A0 gold.

    Patterns 1-5: the existing fully determined pair sides a/b (their supported states differ in the focal field;
    pattern 5's sides also differ in the side field, which the action does not read). Pattern 6: side b's records
    with its settling observation set once to each stated possibility (all other records identical)."""
    var = group["variants"][length]
    F = group["focal_field"]
    if group["pattern"] != 6:
        raw = {"a": copy.deepcopy(var["a"]["records"]), "b": copy.deepcopy(var["b"]["records"])}
        origin = {"a": "side a", "b": "side b"}
    else:
        base = var["b"]["records"]
        unc = [r for r in base if r["kind"] == "uncertain_change"]
        obs = [i for i, r in enumerate(base) if r["kind"] == "observation" and r["_src"] == "base"
               and r["payload"]["field"] == F]
        if len(unc) != 1 or len(obs) != 1:
            raise AssertionError("pattern 6 side b shape")
        raw, origin = {}, {}
        for n, o in enumerate(unc[0]["payload"]["options"]):
            rr = copy.deepcopy(base)
            rr[obs[0]]["payload"]["value"] = o
            raw[f"x{n}"] = rr
            origin[f"x{n}"] = f"side b, settling observation = {o}" + (" (original)" if
                                                                       o == base[obs[0]]["payload"]["value"] else "")
    out = {}
    for k, recs in raw.items():
        r = _resolved(w, recs)
        r["origin"] = origin[k]
        app = r["a0"]["applicable"]
        if app is UNKNOWN or app == UNKNOWN:
            raise AssertionError("D variant applicability not determined")
        label = "valid" if app else "invalid"
        if label in out:
            raise AssertionError("D pair not balanced")
        out[label] = r
    if set(out) != {"valid", "invalid"}:
        raise AssertionError("D pair not balanced")
    # one prerequisite differs: the focal field must differ; any other differing asked field must not matter
    fv, fi = (G.flat({f: out[x]["now_state"][f] for f in w.asked}) for x in ("valid", "invalid"))
    diff = [f for f in w.asked if fv[f] != fi[f]]
    if F not in diff:
        raise AssertionError("D pair does not differ in the focal prerequisite")
    for f in diff:
        if f == F:
            continue
        swapped = dict(fi, **{f: fv[f]})
        if w.apply_own(swapped)[0] != w.apply_own(fi)[0]:
            raise AssertionError(f"D pair differs in a second prerequisite {f}")
    return out
