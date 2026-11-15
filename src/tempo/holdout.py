"""V1.19.0 structural-holdout corpus for the larger-extractor comparison (HOLD-v1). No model.

Interface: FACT-v1 (tempo.factored) is frozen. Prompts = factored.factored_prompt(nullprior.null_prompt(
prose_study.extraction_prompt(...))) with the standard rendered line of each record that carries a referring
description replaced by its declared HOLD-v1 text (asserted unique). FULL raw prefix, the target report last.

Domain: assembly worlds (worlds.make_world, unchanged). Parts G and W fit slot T; D, E, E2 fit slot S2. Stock
fields G.on_hand and D.on_hand are fixed registry fields; W.on_hand enters the registry through its stock record,
which sits at the same prefix position in both alternative histories, so the registry is identical across them.

Every group has four compatible acts (arrival, observation, removal, genuine correction) x two alternative histories
(A, B) that require different target bindings (selected part X) while the target wording is byte-identical. The
histories differ only by which part fills each fixed record position. The correction revises the selected part's
own stock claim (a provisional record at a fixed position), so its target record concerns the selected field in both
alternatives.

Held-out dependency families (primary):
  F1 two-hop       r_link: "the part whose stock was checked in r_ref ..." ; target: "the part described in r_link"
  F2 slot join     r_slot: slot T observed holding X ; target: "the part that r_slot found installed in slot T"
  F3 historical    slot T fitted with X at t1, swapped for the other part at t2 ; target: "the part that slot T held
                   at time th" (t1 <= th < t2), never the latest occupant
  F4 measure order two stock checks whose measurement order is opposite to their reception order ; target: "the part
                   whose stock check, of rI and rJ, was measured earlier|later"
Calibration (familiar, secondary): CN explicit name ("part X"), C1 one-hop ("the part whose stock was checked in rK").
Strata (primary): family x target reception (immediate: received = event time; delayed: received = event time + 2).
Secondary factors, balanced by group index within stratum (bits): b0 X's records before/after the competitor's;
b1 event prior stated/unstated; b2 correction interval finite/open (finite: "from a until b"; plus one later record
about an unaffected field). Competitor mention: an extra competitor stock record when b0 xor b1.
"""
import hashlib
import random

from . import factored as FA, freshgen as FG, generate as G, history as Hm, nullprior as NP, prose, prose_study as PS, \
    worlds
from .worlds import EMPTY, NO, YES

POOLS = {"hold": "bdfghjk", "holdcal": "lmnprst", "holdsmoke": "cgkpvwz"}
FG.CONS.update(POOLS)
ACTS = ("arrival", "observation", "removal", "correction")
HISTORIES = ("A", "B")
FAMILIES = ("F1_two_hop", "F2_slot_join", "F3_historical_occupant", "F4_measurement_order")
CAL_FAMILIES = ("CN_explicit_name", "C1_one_hop")
RECEPTION = ("immediate", "delayed")


def head(rid, recv, rng):
    return rng.choice([f"Message {rid}, received at time {recv}: ", f"{rid} (came in at time {recv}): "])


def target_text(act, desc, rid, t, recv, prior_stated, interval, rng, corr_target=None):
    h = head(rid, recv, rng)
    if act == "arrival":
        body = (f"it is verified that at time {t} {desc} went from not on hand to on hand: it was delivered to you."
                if prior_stated else f"it is verified that at time {t} {desc} was delivered to you, so it is now on hand.")
    elif act == "removal":
        body = (f"it is verified that at time {t} {desc} went from on hand to not on hand: another team took it away."
                if prior_stated else f"it is verified that at time {t} another team took {desc} away, so it is no "
                                     f"longer on hand.")
    elif act == "observation":
        body = f"a confirmed check shows that at time {t} {desc} is on hand."
    else:
        a, b = interval
        span = f"from time {a} until time {b}" if b is not None else f"from time {a} on"
        body = (f"this is a verified correction of {corr_target}. {corr_target} got whether {desc} was on hand wrong: "
                f"actually, {span}, it was not on hand. Nothing physically changed when this correction arrived.")
    return h + body


def _world(seed, pool):
    rng = random.Random(seed)
    return worlds.make_world("assembly", rng, FG.Names(pool, rng), "stock"), rng


def _obs(f, v, status="verified", key=None):
    return G.R("observation", None, None, {"field": f, "value": v}, status=status, key=key)


def build_group(gid, seed, family, reception, bits, pool):
    """Returns {"world", "render_seed", "cases": {(act, hist): case}, ...}. A case has the finalized canonical records,
    the declared HOLD-v1 texts by rid, the target text, the selected field and the replay/score metadata. Raises
    AssertionError for a construction that fails a model-independent check (the caller redraws and logs it)."""
    w, rng = _world(seed, pool)
    b0, b1, b2 = bits
    prior_stated, finite = bool(b1), bool(b2)
    parts = (w.g, w.w) if family in ("F2_slot_join", "F3_historical_occupant") else (w.g, w.d)
    stock = {p: f"{p}.on_hand" for p in parts}
    competitor_extra = bool(b0 ^ b1)
    n_struct = {"CN_explicit_name": 2, "C1_one_hop": 2, "F1_two_hop": 3, "F2_slot_join": 3,
                "F3_historical_occupant": 4, "F4_measurement_order": 2}[family] + int(competitor_extra)
    times = sorted(rng.sample(range(2, 9), n_struct + 1))
    t_target = rng.randint(times[-1] + 1, 10)
    recv = t_target + (2 if reception == "delayed" else 0)
    other_val = rng.choice([YES, NO])
    side_val = rng.choice([EMPTY, w.e, w.e2])
    render_seed = int(hashlib.sha256(f"render|{seed}".encode()).hexdigest()[:12], 16)
    cases = {}
    for hist in HISTORIES:
        X, Y = parts if hist == "A" else parts[::-1]
        fX, fY = stock[X], stock[Y]
        for act in ACTS:
            xval = NO if act == "arrival" else YES
            xrec = _obs(fX, xval, "provisional" if act == "correction" else "verified", key="xrec")
            yrec = _obs(fY, other_val, key="yrec")
            if family in ("CN_explicit_name", "C1_one_hop", "F4_measurement_order"):
                recs = [xrec, yrec] if b0 == 0 else [yrec, xrec]
            elif family == "F1_two_hop":
                ref = _obs(fX, NO if act in ("arrival", "correction") else YES, key="ref")
                recs = ([ref, yrec] if b0 == 0 else [yrec, ref]) + [xrec]
            elif family == "F2_slot_join":
                recs = [_obs(w.slot_f, X, key="slot")] + ([xrec, yrec] if b0 == 0 else [yrec, xrec])
            else:
                fit = G.R("change", None, None, {"field": w.slot_f, "from": EMPTY, "to": X}, key="fit")
                swap = G.R("change", None, None, {"field": w.slot_f, "from": X, "to": Y}, key="swap")
                recs = [fit] + ([xrec, swap, yrec] if b0 == 0 else [yrec, swap, xrec])
            if competitor_extra:
                recs.append(_obs(fY, other_val, key="yextra"))
            for r, t in zip(recs, times):
                r["event_at"] = r["received_at"] = t
            if family == "F4_measurement_order":
                first, second = recs[0], recs[1]
                second["event_at"] = first["event_at"] - 1   # measured before the earlier-received check
            if finite and act == "correction":
                u = _obs(w.side, side_val, key="unaffected")
                u["event_at"] = u["received_at"] = times[-1]
                recs.append(u)
            anchor = xrec["event_at"]
            if act == "arrival":
                tgt = G.R("change", t_target, recv, {"field": fX, "from": NO, "to": YES})
            elif act == "removal":
                tgt = G.R("change", t_target, recv, {"field": fX, "from": YES, "to": NO})
            elif act == "observation":
                tgt = G.R("observation", t_target, recv, {"field": fX, "value": YES})
            else:
                vt = None
                if finite:
                    vt = times[-1] - 1
                    if vt <= anchor:
                        raise AssertionError("finite interval too short")
                tgt = G.R("correction", None, recv, {"target": "xrec", "field": fX, "value": NO, "valid_from": anchor,
                                                      "valid_to": vt})
            recs = G.finalize(recs + [tgt])
            G.check_no_ties(recs)
            byk = {r["key"]: r for r in recs if r.get("key")}
            trid = recs[-1]["rid"]
            custom = {}
            if family == "CN_explicit_name":
                desc = f"part {X}"
            elif family == "C1_one_hop":
                desc = f"the part whose stock was checked in {byk['xrec']['rid']}"
            elif family == "F1_two_hop":
                link = byk["xrec"]
                desc = f"the part described in {link['rid']}"
                lrng = random.Random(f"{render_seed}|{link['rid']}")
                lv = "on hand" if link["payload"]["value"] == YES else "not on hand"
                lst = ("a provisional report, not yet verified, states that" if link["status"] == "provisional"
                       else "it is verified that")
                custom[link["rid"]] = head(link["rid"], link["received_at"], lrng) + \
                    f"{lst} at time {link['event_at']} the part whose stock was checked in {byk['ref']['rid']} is {lv}."
            elif family == "F2_slot_join":
                desc = f"the part that {byk['slot']['rid']} found installed in slot {w.t}"
            elif family == "F3_historical_occupant":
                if not byk["fit"]["event_at"] < byk["swap"]["event_at"]:
                    raise AssertionError("occupancy order")
                desc = f"the part that slot {w.t} held at time {byk['fit']['event_at']}"
            else:
                r1, r2 = sorted([byk["xrec"], byk["yrec"]], key=lambda r: r["rid"])
                if (r1["event_at"] < r2["event_at"]) == (r1["received_at"] < r2["received_at"]):
                    raise AssertionError("measurement and reception order coincide")
                word = "earlier" if byk["xrec"]["event_at"] < byk["yrec"]["event_at"] else "later"
                desc = f"the part whose stock check, of {r1['rid']} and {r2['rid']}, was measured {word}"
            trng = random.Random(f"{render_seed}|{trid}|{act}")
            interval = (anchor, tgt["payload"].get("valid_to")) if act == "correction" else None
            text = target_text(act, desc, trid, t_target, recv, prior_stated, interval, trng,
                               byk["xrec"]["rid"] if act == "correction" else None)
            custom[trid] = text
            cases[(act, hist)] = {"records": recs, "custom": custom, "text": text, "field": fX, "selected": X,
                                  "other": Y, "prior_stated": prior_stated and act in ("arrival", "removal"),
                                  "anchor": anchor, "t_event": None if act == "correction" else t_target, "recv": recv,
                                  "finite": finite and act == "correction", "desc": desc,
                                  "unaffected": byk.get("unaffected"), "target_rid": trid}
    for act in ACTS:
        a, b = cases[(act, "A")], cases[(act, "B")]
        if family != "CN_explicit_name" and a["text"] != b["text"]:
            raise AssertionError(f"{gid} {act}: target wording differs across histories")
        if a["field"] == b["field"]:
            raise AssertionError(f"{gid} {act}: histories do not require different bindings")
        if registry(w, a) != registry(w, b):
            raise AssertionError(f"{gid} {act}: registry differs across histories")
    return {"world": w, "render_seed": render_seed, "cases": cases, "family": family, "reception": reception,
            "bits": list(bits)}


def prompt(w, case, rseed):
    recs = case["records"]
    h = {"records": [Hm.public(r) for r in recs], "seed": rseed}
    u = PS.extraction_prompt(w, h, "prose", len(recs))
    line = PS.line_fn(w, h, "prose")
    for r in h["records"]:
        if r["rid"] in case["custom"]:
            old = line(r)
            if u.count(old) != 1:
                raise AssertionError("rendered line not unique")
            u = u.replace(old, case["custom"][r["rid"]])
    return FA.factored_prompt(NP.null_prompt(u))


def registry(w, case):
    return {f: Hm.allowed_values(w, f) for f in Hm.registry_fields(w, [Hm.public(r) for r in case["records"]])}


def public(case):
    return [Hm.public(r) for r in case["records"]]
