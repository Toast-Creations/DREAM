"""V1.23 development panel: one revision.value clarification x SUB/KEEP.

No model or evaluator is called here. Each independent stem supplies both histories and both correction
directions. Arrival is sampled once per selected stem/history, not duplicated across correction directions.
Only the added sentence differs between ORIG and CLAR. FACT-v1 and its compiler remain imported unchanged.
"""
import copy
import hashlib
import random

from . import factored as FA, holdout as HO, kidconf as KC, kidconfgen as KG
from .worlds import YES, NO

RULE = "CLAR-VALUE-v1-development"
CLARIFICATION = ("For a revision, value is the corrected value asserted by the new record, not the value in the "
                 "earlier report being corrected.")
ARMS = ("SUB_ORIG", "KEEP_ORIG", "SUB_CLAR", "KEEP_CLAR")
DIRECTIONS = ("yes_to_no", "no_to_yes")
DEFAULT_CONFIG = {"base_seed": 2026111101, "smoke_base_seed": 2026111102, "schedule_seed": 2026111103,
                  "pool": "clar23", "smoke_pool": "clar23s", "consonants": KG.DEFAULT_CONSONANTS,
                  "id_prefix": "c23-g", "smoke_prefix": "c23-s", "max_attempts": 300}


def clarify_prompt(original):
    """Append exactly one sentence after the unchanged FACT-v1 item schema."""
    anchor = FA.FACT_REPLY[2]
    if original.count(anchor) != 1 or CLARIFICATION in original:
        raise AssertionError("FACT-v1 schema anchor missing, duplicated, or already clarified")
    return original.replace(anchor, anchor + "\n" + CLARIFICATION)


def prompts_from_public(pub):
    """No construction labels, canonical records, or hidden values are consulted."""
    sub, keep, ledger = KG.arms_from_public(pub)
    return {"SUB_ORIG": sub, "KEEP_ORIG": keep, "SUB_CLAR": clarify_prompt(sub),
            "KEEP_CLAR": clarify_prompt(keep)}, ledger


def plan(smoke=False, config=None):
    """F2 focus with F1/F3 sentinels. The arrival subset is fixed before world generation.

    Main F2: 12 stems per reception, each of the four b0/b1 cells three times. Its 12 arrival stems have
    six per reception: indices 0..5 immediate, 6..11 delayed, balancing all four cells across reception.
    Each sentinel family has two stems/reception and one arrival stem/reception. Their four cells occur once
    globally; arrivals use immediate index zero and delayed index one. All intervals are open (b2=0).
    """
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    if smoke:
        return [{"stem": cfg["smoke_prefix"] + "0001", "family": "F2_slot_join", "reception": "immediate",
                 "bits": [0, 0, 0], "arrival_selected": True},
                {"stem": cfg["smoke_prefix"] + "0002", "family": "F3_historical_occupant", "reception": "delayed",
                 "bits": [1, 1, 0], "arrival_selected": True}]
    out = []
    for family, n in (("F2_slot_join", 12), ("F1_two_hop", 2), ("F3_historical_occupant", 2)):
        for ri, reception in enumerate(HO.RECEPTION):
            for i in range(n):
                k = i if family == "F2_slot_join" else i + 2 * ri
                arrival = (i < 6 if ri == 0 else i >= 6) if family == "F2_slot_join" else i == ri
                out.append({"stem": f"{cfg['id_prefix']}{len(out) + 1:04d}", "family": family,
                            "reception": reception, "bits": [k & 1, (k >> 1) & 1, 0],
                            "arrival_selected": arrival})
    return out


def correction_case(original, direction):
    """Reverse the selected field's stock history and replacement assertion together.

    F1 has a custom rendered xrec line, so its suffix is reversed as well. Other selected-field prefix
    observations are rendered from the changed canonical records by HO.prompt/RG.envelopes. No competitor
    values, identity descriptions, names, times, IDs, or ordering are changed.
    """
    if direction not in DIRECTIONS:
        raise ValueError(direction)
    case = copy.deepcopy(original)
    if direction == "yes_to_no":
        return case
    target = case["records"][-1]
    if target["kind"] != "correction" or target["payload"]["value"] != NO:
        raise AssertionError("expected original yes-to-no correction")
    selected_field = case["field"]
    for rec in case["records"][:-1]:
        p = rec["payload"]
        if rec["kind"] == "observation" and p.get("field") == selected_field:
            if p.get("value") not in (YES, NO):
                raise AssertionError("nonbinary stock observation")
            p["value"] = NO if p["value"] == YES else YES
            if rec["rid"] in case["custom"]:
                old = case["custom"][rec["rid"]]
                if old.endswith(" is on hand."):
                    new = old[:-len(" is on hand.")] + " is not on hand."
                elif old.endswith(" is not on hand."):
                    new = old[:-len(" is not on hand.")] + " is on hand."
                else:
                    raise AssertionError("unknown selected-field custom stock suffix")
                case["custom"][rec["rid"]] = new
    target["payload"]["value"] = YES
    marker = "it was not on hand."
    if case["text"].count(marker) != 1:
        raise AssertionError("correction wording missing or repeated")
    case["text"] = case["text"].replace(marker, "it was on hand.")
    case["custom"][target["rid"]] = case["text"]
    return case


def schedule(units, seed):
    """Shuffle stem-act-direction units, then arm order; histories A then B remain paired inside each arm.

    A correction unit contains eight calls (one direction, both histories x four arms). An arrival unit has
    eight calls with direction=na. This prevents any performance-based scheduling or duplicated arrivals.
    """
    rng = random.Random(seed)
    units = list(units)
    rng.shuffle(units)
    calls = []
    for unit in units:
        arms = list(ARMS)
        rng.shuffle(arms)
        rank = {a: i for i, a in enumerate(arms)}
        calls.extend(sorted(unit, key=lambda c: (rank[c["arm"]], c["history"])))
    return calls


def build_part(spec, base_seed, pool, config):
    KG.register_pool(pool, config["consonants"])
    publics, hidden, units, rejected = [], [], [], []
    for meta in spec:
        stem = meta["stem"]
        for attempt in range(config["max_attempts"]):
            seed = KC.seed_for(base_seed, pool, stem, attempt)
            try:
                group = HO.build_group(stem, seed, meta["family"], meta["reception"], meta["bits"], pool)
                built = []
                acts = [("correction", d) for d in DIRECTIONS]
                if meta["arrival_selected"]:
                    acts.append(("arrival", "na"))
                for act, direction in acts:
                    for history in HO.HISTORIES:
                        case = group["cases"][(act, history)]
                        case = correction_case(case, direction) if act == "correction" else copy.deepcopy(case)
                        tid = f"{stem}|{act}|{direction}|{history}"
                        rowmeta = {**meta, "group": stem, "act": act, "direction": direction,
                                   "history": history, "component": "development",
                                   "stratum": KC.stratum(meta["family"], meta["reception"])}
                        pub = KG.public_row(tid, group["world"], case, group["render_seed"], rowmeta)
                        prompts, ledger = prompts_from_public(pub)
                        if ledger["field"] != case["field"]:
                            raise AssertionError("public identity differs from construction label")
                        pub["identity"] = ledger
                        hid = {"target": tid, **rowmeta, "world_seed": seed, "pool": pool,
                               "render_seed": group["render_seed"], "gold_field": case["field"], "case": case}
                        built.append((pub, hid, prompts))
                break
            except AssertionError as e:
                rejected.append({"stem": stem, "attempt": attempt, "seed": seed, "reason": str(e)[:240]})
        else:
            raise AssertionError(f"unable to construct {stem}")
        byunit = {}
        for pub, hid, prompts in built:
            publics.append(pub)
            hidden.append(hid)
            for arm in ARMS:
                call = KG.call(pub["target"] + "|" + arm, arm, pub["history"], prompts[arm])
                call.update({k: pub[k] for k in ("target", "stem", "family", "reception", "act", "direction")})
                byunit.setdefault((pub["act"], pub["direction"]), []).append(call)
        units.extend(byunit.values())
    return {"plan": spec, "public": publics, "hidden": hidden, "units": units, "rejected": rejected}


def generate(config=None, historical_prompts=(), historical_seeds=()):
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    if cfg["pool"] == cfg["smoke_pool"] or cfg["id_prefix"] == cfg["smoke_prefix"] or \
            cfg["base_seed"] == cfg["smoke_base_seed"]:
        raise AssertionError("main and smoke identifiers must be disjoint")
    out = {}
    for smoke in (False, True):
        part = "smoke" if smoke else "main"
        result = build_part(plan(smoke, cfg), cfg["smoke_base_seed" if smoke else "base_seed"],
                            cfg["smoke_pool" if smoke else "pool"], cfg)
        result["calls"] = schedule(result.pop("units"), cfg["schedule_seed"] + int(smoke))
        out[part] = result
    prompts = [p["base_prompt"] for result in out.values() for p in result["public"]]
    seeds = {h["world_seed"] for result in out.values() for h in result["hidden"]}
    ids = [c["call_id"] for result in out.values() for c in result["calls"]]
    if len(set(prompts)) != len(prompts) or set(prompts) & set(historical_prompts):
        raise AssertionError("repeated BASE prompt in new or historical panel")
    if seeds & set(historical_seeds):
        raise AssertionError("historical world seed repeated")
    if len(set(ids)) != len(ids):
        raise AssertionError("duplicate call id")
    return out
