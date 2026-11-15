"""V1.19.0 evaluation wrapper (HOLD-EVAL-v1). The historical scorer (scripts/contract_validate.py) and fac_analyze stay
unchanged; this wrapper adds what they omit: the correction's valid_to, explicitly stated event priors, case-specific
replay times and an independently written temporal reference.

Exact source meaning of a FACT-v1 reply (all must hold; anything pending, rejected, malformed or truncated is wrong):
  - the reply compiles to one reporting act (factored.compile_reply, frozen) and the compiled report is accepted by
    the unchanged contract over the canonical public prefix (evaluator only; never a model input);
  - meta: rid, received_at and status equal the target's;
  - the reduced claims (after the frozen R1-R3 only) equal the canonical meaning:
      event      field, at, to; prior: if the source states it, from must equal it; if unstated, null or the correct value
      state      field, at, value (one state)
      revision   target, field, value, valid_from and valid_to (None for an open interval)
Quotation validity is scored separately (evidence is a substring of the target text) and never certifies meaning.
Reported separately (brief addendum, Nov 6):
  exact_extraction   the reduced claims carry the full source meaning (the definition above, incl. valid_to)
  compilation_loss   a source constraint present in the reduced claims is absent from the compiled contract-v1
                     report (contract v1 has no valid_to); assigned identically to perfect canonical extractions
  exact_end_to_end   exact_extraction and not compilation_loss (source meaning preserved into the engine)
  replay_ok          restricted replay (see below); not evidence of end-to-end preservation for finite intervals

Temporal reference (independent of tempo.assertions; written from the contract-v1 meaning rules): per field, values
change only at events; state assertions and corrections constrain the value at their time; a correction withdraws its
target's assertion; provisional constraints inconsistent with verified evidence are suspended; verified inconsistency
= conflict. Supported value = the set over consistent trajectories (domain yes/no).
Replay queries on the selected field X (and, for finite corrections, the unaffected later field):
  events/observation: Q_hist (anchor, all evidence), Q_now (12, all evidence), Q_before (event time, cutoff before
  reception); open correction: Q_hist (valid_from), Q_now, Q_before (valid_from, cutoff before reception); finite
  correction: Q_hist, Q_before and Q_unaffected (the later unaffected field at its time). Contract v1 has no
  valid_to, so no query is placed after a finite interval's end (declared limitation).
"""
import itertools

from . import assertions as A, engine_fixtures as EF, factored as FA, worlds
from .worlds import NO, YES

NOW = 12


# ---------------------------------------------------------------------------------------------- independent reference

def _items(records, f, cutoff):
    rs = [r for r in records if r["received_at"] <= cutoff]
    withdrawn = {(r["payload"]["target"], r["payload"]["field"]) for r in rs if r["kind"] == "correction"}
    cons, evs = [], []
    for n, r in enumerate(rs):
        p = r["payload"]
        if r["kind"] in ("observation", "initial"):
            pairs = p["assign"].items() if r["kind"] == "initial" else [(p["field"], p["value"])]
            for ff, v in pairs:
                if ff == f and (r["rid"], f) not in withdrawn:
                    cons.append((r["event_at"], {v}, r["status"]))
        elif r["kind"] == "change" and p["field"] == f:
            evs.append((r["event_at"], n, p.get("from"), [p["to"]]))
        elif r["kind"] == "uncertain_change" and p["field"] == f:
            evs.append((r["event_at"], n, p.get("from"), list(p["options"])))
        elif r["kind"] == "correction" and p["field"] == f:
            cons.append((p["valid_from"], {p["value"]}, "verified"))
    return cons, sorted(evs)


def _consistent_values(domain, cons, evs, t):
    vals = set()
    for v0 in domain:
        for choice in itertools.product(*[e[3] for e in evs]):
            traj, cur, ok = [(None, v0)], v0, True
            for e, to in zip(evs, choice):
                if e[2] is not None and e[2] != cur:
                    ok = False
                    break
                cur = to
                traj.append((e[0], cur))
            if not ok:
                continue
            at = lambda x: [v for w, v in traj if w is None or w <= x][-1]
            if all(at(c[0]) in c[1] for c in cons):
                vals.add(at(t))
    return vals


def reference_value(records, f, t, cutoff, domain=(YES, NO)):
    cons, evs = _items(records, f, cutoff)
    if not cons and not evs or min([c[0] for c in cons] + [e[0] for e in evs]) > t:
        return "not_yet_described"
    vals = _consistent_values(domain, cons, evs, t)
    if not vals:
        ver = [c for c in cons if c[2] == "verified"]
        if _consistent_values(domain, ver, evs, t):
            vals = _consistent_values(domain, ver, evs, t)
        else:
            return "conflict"
    return next(iter(vals)) if len(vals) == 1 else "unknown"


def queries(case):
    a, recv = case["anchor"], case["recv"]
    q = {"Q_hist": (case["field"], a, NOW)}
    if case["finite"]:
        u = case["unaffected"]
        q["Q_unaffected"] = (u["payload"]["field"], u["event_at"], NOW)
        q["Q_before"] = (case["field"], a, recv - 1)
    else:
        q["Q_now"] = (case["field"], NOW, NOW)
        q["Q_before"] = (case["field"], case["t_event"] if case["t_event"] is not None else a, recv - 1)
    return q


def reference_answers(case):
    domain_of = lambda f: (YES, NO) if f.endswith(".on_hand") else None
    out = {}
    for k, (f, t, c) in queries(case).items():
        if f.endswith(".on_hand"):
            out[k] = reference_value(case["records"], f, t, c)
        else:  # slot field (unaffected evidence): domain from the canonical records themselves
            vals = sorted({r["payload"].get("value") for r in case["records"] if r["payload"].get("field") == f} - {None})
            out[k] = reference_value(case["records"], f, t, c, tuple(vals) + ("__other__",))
    return out


# ---------------------------------------------------------------------------------------------- engine replay

def engine_for(w, prefix, target_rep, gold, ctx):
    eng = A.AssertionEngine(EF.spec_from_world(vars(w), "assembly", prefix + [gold]), ctx)
    for r in prefix:
        eng.ingest(A.from_v02(EF.public_record(r)))
    accepted, code = False, None
    if target_rep is not None:
        try:
            eng.ingest(target_rep)
            accepted = True
        except A.ContractRejected as e:
            code = e.code
    if not accepted:
        eng.record_unprocessed(gold["rid"], gold["received_at"], "", target_rep, code or "unprocessed", None)
    return eng, accepted, code


def engine_answers(eng, case):
    out = {}
    for k, (f, t, c) in queries(case).items():
        v = eng.view("earlier", t, cutoff=c)
        out[k] = v["per_field"].get(f, "not_yet_described")
    return out


# ---------------------------------------------------------------------------------------------- meaning score

def _claims_match(red, gold, prior_stated):
    k, p = gold["kind"], gold["payload"]
    ev, st, rv = red["events"], red["states"], red["revisions"]
    if k == "change":
        if len(ev) != 1 or st or rv:
            return False
        e = ev[0]
        if e.get("field") != p["field"] or e.get("at") != gold["event_at"] or e.get("to") != p["to"] or "options" in e:
            return False
        return e.get("from") == p["from"] if prior_stated else e.get("from") in (None, p["from"])
    if k == "observation":
        return (not ev and not rv and len(st) == 1 and st[0]["field"] == p["field"] and st[0]["at"] == gold["event_at"]
                and st[0]["value"] == p["value"])
    if k == "correction":
        if ev or st or len(rv) != 1:
            return False
        r = rv[0]
        return (r["target"], r["field"], r["value"], r["valid_from"], r["valid_to"]) == \
            (p["target"], p["field"], p["value"], p["valid_from"], p.get("valid_to"))
    raise ValueError(k)


def score(raw, case, w, reg, stop=None):
    recs = [dict(r) for r in case["records"]]
    gold, prefix = recs[-1], recs[:-1]
    pub = lambda r: {k: r[k] for k in ("rid", "kind", "status", "event_at", "received_at", "payload")}
    gold, prefix = pub(gold), [pub(r) for r in prefix]
    rep, tr = FA.compile_reply(raw, reg)
    eng, accepted, ccode = engine_for(w, prefix, rep, gold, "score")
    red = tr.get("reduced")
    claims = tr.get("claims")
    meta_ok = bool(claims) and claims.get("rid") == gold["rid"] and claims.get("received_at") == gold["received_at"] \
        and claims.get("status") == gold["status"]
    exact = rep is not None and accepted and meta_ok and stop != "length" and _claims_match(red, gold, case["prior_stated"])
    loss = compilation_loss(red, rep)
    f = case["field"]
    out = {"exact": exact, "exact_extraction": exact, "compilation_loss": loss, "exact_end_to_end": exact and not loss, "compiled": rep is not None, "accepted": accepted, "pending_code": tr["code"],
           "contract_code": ccode, "meta_ok": meta_ok, "category": None if rep is None else rep["type"],
           "truncated": stop == "length"}
    if claims:
        allf = [a["field"] for k in FA.LISTS for a in claims[k]]
        out.update(raw_events=len(claims["events"]), raw_states=len(claims["states"]), raw_revisions=len(claims["revisions"]),
                   bound_ok_raw=bool(allf) and set(allf) == {f}, other_field_raw=any(x != f for x in allf),
                   slot_field_claimed=any(x.endswith(".part") for x in allf),
                   event_on_X=any(e["field"] == f for e in claims["events"]),
                   state_on_X=any(s["field"] == f for s in claims["states"]),
                   quote_valid=isinstance((raw_obj := _evidence(raw)), str) and len(raw_obj) > 0 and raw_obj in case["text"])
        if gold["kind"] == "correction" and red and len(red["revisions"]) == 1:
            r = red["revisions"][0]
            p = gold["payload"]
            out.update(rev_target_ok=r["target"] == p["target"], rev_from_ok=r["valid_from"] == p["valid_from"],
                       rev_to_ok=r["valid_to"] == p.get("valid_to"))
        if gold["kind"] == "change" and red and len(red["events"]) == 1:
            e = red["events"][0]
            out.update(event_time_ok=e.get("at") == gold["event_at"],
                       prior_ok=(e.get("from") == gold["payload"]["from"]) if case["prior_stated"] else
                       e.get("from") in (None, gold["payload"]["from"]))
    out["bound_ok_accepted"] = accepted and rep is not None and {a["field"] for a in rep["assertions"]} == {f}
    out["reception_ok"] = bool(claims) and claims.get("received_at") == gold["received_at"]
    out["false_revision_raw"] = gold["kind"] != "correction" and bool(claims) and bool(claims["revisions"])
    out["false_revision_compiled"] = gold["kind"] != "correction" and rep is not None and rep["type"] == "correction"
    out["false_revision_accepted"] = out["false_revision_compiled"] and accepted
    out["state_only_event_accepted"] = gold["kind"] == "change" and accepted and rep is not None and rep["type"] == "state"
    out["endpoint_ok"] = rep is not None and any(a.get("field") == f and a.get("value", a.get("to")) ==
                                                 (gold["payload"].get("to") or gold["payload"].get("value"))
                                                 for a in rep["assertions"])
    out["replay"] = engine_answers(eng, case)
    out["replay_ref"] = reference_answers(case)
    out["replay_ok"] = out["replay"] == out["replay_ref"]
    return out, rep, tr


def compilation_loss(red, rep):
    """True if a constraint in the reduced claims is not carried by the compiled contract-v1 report."""
    if not red or rep is None:
        return False
    if rep["type"] == "correction" and red.get("revisions"):
        return any(r.get("valid_to") is not None for r in red["revisions"]) and \
            not any("valid_to" in a for a in rep["assertions"])
    return False


def _evidence(raw):
    from . import score as S
    if raw is None:
        return None
    obj, err = S.parse_object(raw)
    return obj.get("evidence") if err is None and isinstance(obj, dict) else None
