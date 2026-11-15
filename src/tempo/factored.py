"""V1.18.0 factored assertion extraction (FACT-v1): representation, prompt and deterministic compiler. No model.

Interfaces (one call each, FULL raw history, same header / prior reports / new report / registry / model / 256 cap):
  EXCLUSIVE  the 1.16-1.17 FULL prompt with the NULL_PRIOR schema (ctxablate.full_prompt), adapter-v1 unchanged.
  FACTORED   the same prompt with exactly two blocks replaced (asserted): the instruction+kinds lines of
             history.EXTRACT_QUERY and the reply-schema block (EXTRACT_REPLY with the null-prior payload line and its
             clarification). The replacement asks for independent lists of events / states / revisions; generic
             field/value schema; no worked examples.

Compiler (structural only: JSON parse, public registry, the frozen 1.8.2 value/integer normalisation N1/N2; never
gold, actual states, generator classes, or phrase lists). Steps:
  C1 parse one JSON object (score.parse_object); top-level rid / received_at / status; lists events, states,
     revisions (a missing list = empty; a non-list = rejection "bad_list").
  C2 per assertion: required keys present, field in the registry, values allowed (after N1), integer times (after
     N2); else rejection "invalid_assertion" (named, raw kept).
  C3 predeclared redundancy removal only: R1 identical duplicates; R2 a state at exactly an event's time with the
     same field and the event's result (one recorded result) -> keep the event; R3 a state at exactly a revision's
     valid_from with the same field and value -> keep the revision.
  C4 a single reporting act -> the existing v0.2 record -> assertions.from_v02 (canonical v1 report, original rid):
       exactly one event                       -> change (or uncertain_change when "options")
       only states, all at one time            -> observation (one field) / initial (several fields)
       exactly one revision                    -> correction (event_at null)
     anything else -> pending: "empty", "mixed_acts", "multiple_events", "multiple_revisions", "states_mixed_times".
The compiled report then enters the unchanged engine contract; pending/rejected outputs are incorrect outcomes.
"""
import copy
import hashlib
import json
import random

from . import assertions as A, ctxablate as CA, freshgen as FG, generate as G, history as Hm, nullprior as NP, \
    score as S, worlds
from .repair import _int_string
from .worlds import EMPTY, NO, YES

INTERFACES = ("EXCLUSIVE", "FACTORED")
POOLS = {"fac": "cdgjlrt", "facsmoke": "bkmnpsz", "facctl": "dghlprv", "facctlsmoke": "bcfjkmt"}
FG.CONS.update(POOLS)

EXCL_QUERY_BODY = "\n".join(Hm.EXTRACT_QUERY[1:])
EXCL_REPLY_BODY = "\n".join([Hm.EXTRACT_REPLY[0], Hm.EXTRACT_REPLY[1], NP.NULL_PAYLOAD_LINE, NP.CLARIFICATION])
FACT_QUERY = [
    "Convert the new record into typed assertions. Report only what the new record itself states: whether it is "
    "verified or provisional, the time it was received, and its content. Do not decide what is true now, do not apply "
    "the record rules, and do not add claims the new record does not make. Earlier records may be used only to "
    "identify which entity or record the new record refers to.",
    "List the assertions by category, each in its own list (use an empty list when the new record makes none of that "
    "category): \"events\" (physical changes the record says happened), \"states\" (values the record states a field "
    "had at a time), \"revisions\" (statements that an earlier report was wrong about a fact).",
]
FACT_REPLY = [
    "Reply with only a JSON object:",
    '{"rid": "<record ID>", "status": "verified" or "provisional", "received_at": <integer>, "events": [...], '
    '"states": [...], "revisions": [...], "evidence": "<exact words from the new record>"}',
    'Items: event {"field": "<field>", "at": <integer>, "from": "<value>" or null, "to": "<value>"}, or, when the '
    'result was not recorded, {"field": "<field>", "at": <integer>, "from": "<value>" or null, "options": ["<value>", '
    '...]}; state {"field": "<field>", "at": <integer>, "value": "<value>"}; revision {"target": "<record ID>", '
    '"field": "<field>", "value": "<value>", "valid_from": <integer>, "valid_to": <integer> or null}.',
    "Use null for an event's \"from\" if the new record does not explicitly state the prior value; otherwise "
    "transcribe the stated prior value.",
]


def factored_prompt(exclusive):
    if exclusive.count(EXCL_QUERY_BODY) != 1 or exclusive.count(EXCL_REPLY_BODY) != 1:
        raise AssertionError("exclusive prompt blocks not found exactly once")
    return exclusive.replace(EXCL_QUERY_BODY, "\n".join(FACT_QUERY)).replace(EXCL_REPLY_BODY, "\n".join(FACT_REPLY))


# ---------------------------------------------------------------------------------------------- corpus
STRATA = [(t, L, o) for t in ("G", "D") for L in (3, 4) for o in ("P_first", "Q_first")]


def build_group(gid, seed, stratum, lure, pool, want_template):
    """ctxablate.build_group generalised: the target part P is the world's G or D (counterbalanced); the lure is an
    installation into slot T of part G or of the low-rated part W (for P = D, G is the competitor)."""
    tp, length, order = stratum
    rng = random.Random(seed)
    w = worlds.make_world("assembly", rng, FG.Names(pool, rng), "stock")
    P = f"{w.g}.on_hand" if tp == "G" else f"{w.d}.on_hand"
    Q = f"{w.d}.on_hand" if tp == "G" else f"{w.g}.on_hand"
    times = sorted(rng.sample(range(1, 10), length))
    t_target = rng.randint(times[-1] + 1, 11)
    qval = rng.choice([YES, NO])
    sval = rng.choice([EMPTY, w.e, w.e2])
    out = {}
    for v in CA.VARIANTS:
        p_rec = G.R("observation", None, None, {"field": P, "value": NO if v == "arrival" else YES},
                    status="provisional" if v == "correction" else "verified", key="prec")
        q_rec = G.R("observation", None, None, {"field": Q, "value": qval})
        t_rec = G.R("change", None, None, {"field": w.slot_f, "from": EMPTY, "to": w.g if lure == "lure_G" else w.w})
        recs = ([p_rec, q_rec] if order == "P_first" else [q_rec, p_rec]) + [t_rec]
        if length == 4:
            recs.append(G.R("observation", None, None, {"field": w.side, "value": sval}))
        for r, t in zip(recs, times):
            r["event_at"] = r["received_at"] = t
        p_t = p_rec["event_at"]
        tgt = {"arrival": G.R("change", t_target, t_target, {"field": P, "from": NO, "to": YES}),
               "observation": G.R("observation", t_target, t_target, {"field": P, "value": YES}),
               "removal": G.R("change", t_target, t_target, {"field": P, "from": YES, "to": NO}),
               "correction": G.R("correction", None, t_target, {"target": "prec", "field": P, "value": NO,
                                                                 "valid_from": p_t, "valid_to": None})}[v]
        recs = G.finalize(recs + [tgt])
        G.check_no_ties(recs)
        out[v] = recs
    from . import prose
    for rs in CA.seed_iter(seed):
        if CA.template_id(prose.prose_line(w, out["arrival"][-1], rs)) == want_template:
            return w, out, rs, {"P": P, "Q": Q, "anchor": p_t, "target_time": t_target}
    raise AssertionError("no renderer seed for the template")


# ---------------------------------------------------------------------------------------------- compiler
LISTS = ("events", "states", "revisions")


def _nv(f, v, registry, log, where):
    if not isinstance(v, str):
        return v
    m = S.match_value(v, registry[f])
    if m is not None and m != v:
        log.append({"rule": "N1", "key": where, "original": v, "normalised": m})
        return m
    return v


def _int(x, log, where):
    n = _int_string(x)
    if n != x:
        log.append({"rule": "N2", "key": where, "original": x})
    return n


def _isint(x):
    return isinstance(x, int) and not isinstance(x, bool)


def normalise_claims(obj, registry):
    """C1-C2. Returns (claims dict or None, log, error code or None)."""
    log = []
    if not isinstance(obj, dict):
        return None, log, "not_an_object"
    out = {"rid": obj.get("rid"), "status": obj.get("status"), "received_at": _int(obj.get("received_at"), log, "received_at")}
    for k in LISTS:
        x = obj.get(k, [])
        if x is None:
            x = []
        if not isinstance(x, list):
            return None, log, "bad_list"
        out[k] = []
        for i, a in enumerate(x):
            if not isinstance(a, dict) or not isinstance(a.get("field"), str) or a["field"] not in registry:
                return None, log, "invalid_assertion"
            a = copy.deepcopy(a)
            f = a["field"]
            if k == "events":
                a["at"] = _int(a.get("at"), log, f"events[{i}].at")
                if "from" not in a:
                    return None, log, "invalid_assertion"
                a["from"] = _nv(f, a["from"], registry, log, f"events[{i}].from")
                if "options" in a:
                    if not isinstance(a["options"], list) or not a["options"]:
                        return None, log, "invalid_assertion"
                    a["options"] = [_nv(f, o, registry, log, f"events[{i}].options") for o in a["options"]]
                    vals = a["options"]
                elif "to" in a:
                    a["to"] = _nv(f, a["to"], registry, log, f"events[{i}].to")
                    vals = [a["to"]]
                else:
                    return None, log, "invalid_assertion"
                if not _isint(a["at"]) or any(v not in registry[f] for v in vals) or \
                        (a["from"] is not None and a["from"] not in registry[f]):
                    return None, log, "invalid_assertion"
                a = {kk: a[kk] for kk in ("field", "at", "from", "to", "options") if kk in a}
            elif k == "states":
                a["at"] = _int(a.get("at"), log, f"states[{i}].at")
                a["value"] = _nv(f, a.get("value"), registry, log, f"states[{i}].value")
                if not _isint(a["at"]) or a["value"] not in registry[f]:
                    return None, log, "invalid_assertion"
                a = {kk: a[kk] for kk in ("field", "at", "value")}
            else:
                a["valid_from"] = _int(a.get("valid_from"), log, f"revisions[{i}].valid_from")
                a["value"] = _nv(f, a.get("value"), registry, log, f"revisions[{i}].value")
                vt = a.get("valid_to")
                if not isinstance(a.get("target"), str) or not _isint(a["valid_from"]) or a["value"] not in registry[f] \
                        or not (vt is None or _isint(vt)):
                    return None, log, "invalid_assertion"
                a = {"target": a["target"], "field": f, "value": a["value"], "valid_from": a["valid_from"], "valid_to": vt}
            out[k].append(a)
    return out, log, None


def reduce_claims(c):
    """C3 redundancy rules R1-R3 (logged)."""
    log = []
    c = copy.deepcopy(c)
    for k in LISTS:
        seen, keep = set(), []
        for a in c[k]:
            key = json.dumps(a, sort_keys=True)
            if key in seen:
                log.append({"rule": "R1", "list": k, "item": a})
                continue
            seen.add(key)
            keep.append(a)
        c[k] = keep
    keep = []
    for s in c["states"]:
        if any(e["field"] == s["field"] and e["at"] == s["at"] and "to" in e and e["to"] == s["value"] for e in c["events"]):
            log.append({"rule": "R2", "item": s})
        elif any(r["field"] == s["field"] and r["valid_from"] == s["at"] and r["value"] == s["value"] for r in c["revisions"]):
            log.append({"rule": "R3", "item": s})
        else:
            keep.append(s)
    c["states"] = keep
    return c, log


def compile_claims(c):
    """C4 -> (v0.2 record or None, pending code or None)."""
    ev, st, rv = c["events"], c["states"], c["revisions"]
    n_cat = sum(bool(x) for x in (ev, st, rv))
    if n_cat == 0:
        return None, "empty"
    if n_cat > 1:
        return None, "mixed_acts"
    base = {"rid": c["rid"], "status": c["status"], "received_at": c["received_at"]}
    if ev:
        if len(ev) > 1:
            return None, "multiple_events"
        e = ev[0]
        if "options" in e:
            return dict(base, kind="uncertain_change", event_at=e["at"],
                        payload={"field": e["field"], "from": e["from"], "options": e["options"]}), None
        return dict(base, kind="change", event_at=e["at"], payload={"field": e["field"], "from": e["from"], "to": e["to"]}), None
    if rv:
        if len(rv) > 1:
            return None, "multiple_revisions"
        r = rv[0]
        return dict(base, kind="correction", event_at=None, payload=dict(r)), None
    if len({s["at"] for s in st}) != 1 or len({s["field"] for s in st}) != len(st):
        return None, "states_mixed_times"
    if len(st) == 1:
        return dict(base, kind="observation", event_at=st[0]["at"], payload={"field": st[0]["field"], "value": st[0]["value"]}), None
    return dict(base, kind="initial", event_at=st[0]["at"], payload={"assign": {s["field"]: s["value"] for s in st}}), None


def compile_reply(raw, registry):
    """raw factored reply -> (v1 report or None, trace dict)."""
    tr = {"parse_error": None, "norm": [], "reduce": [], "claims": None, "reduced": None, "code": None, "v02": None}
    if raw is None:
        tr.update(parse_error="no reply", code="parse")
        return None, tr
    obj, err = S.parse_object(raw)
    if err is not None:
        tr.update(parse_error=err, code="parse")
        return None, tr
    claims, nlog, code = normalise_claims(obj, registry)
    tr.update(norm=nlog, claims=claims)
    if code:
        tr["code"] = code
        return None, tr
    red, rlog = reduce_claims(claims)
    tr.update(reduce=rlog, reduced=red)
    rec, pend = compile_claims(red)
    if pend:
        tr["code"] = pend
        return None, tr
    tr["v02"] = rec
    try:
        rep = A.from_v02(rec)
    except (KeyError, TypeError, AttributeError) as e:
        tr["code"] = f"unmappable: {e!r}"[:120]
        return None, tr
    rep["source"] = "extractor:qwen3-8b:factored"
    if isinstance(obj.get("evidence"), str):
        rep["evidence"] = obj["evidence"]
    return rep, tr


def canonical_factored(gold):
    """The canonical FACTORED reply for a public record (token-budget check and perfect fixture)."""
    k, p = gold["kind"], gold["payload"]
    out = {"rid": gold["rid"], "status": gold["status"], "received_at": gold["received_at"], "events": [], "states": [],
           "revisions": []}
    if k in ("change", "uncertain_change"):
        e = {"field": p["field"], "at": gold["event_at"], "from": p.get("from")}
        e.update({"to": p["to"]} if k == "change" else {"options": p["options"]})
        out["events"].append(e)
        if k == "change":
            out["states"].append({"field": p["field"], "at": gold["event_at"], "value": p["to"]})
    elif k == "observation":
        out["states"].append({"field": p["field"], "at": gold["event_at"], "value": p["value"]})
    elif k == "initial":
        out["states"] += [{"field": f, "at": gold["event_at"], "value": v} for f, v in p["assign"].items()]
    else:
        out["revisions"].append(dict(p))
    out["evidence"] = "..."
    return out
