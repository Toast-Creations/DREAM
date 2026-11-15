"""V1.15.0 frozen-text integration: the 1.14.0 BASE / DEPENDENCY selectors with the past-report channel threaded
through every stage (FTX-v1). Only the past-report channel changes; goals, action rules, sensor registry, public
transition declarations, fixed activity window, sensor receipts and executor stay structured and unchanged.

Channel (None = structured public reports; otherwise {"sequence": [...]} from build_channel) is used for:
  1 Q0 at the episode origin      freshness.p2_request(pub, gc, channel)            (unchanged; already channel-aware)
  2 S2 and field selection        s2_support / selection_for below = depquery's versions with the channel passed to
                                  recovery.engine_from (depquery.select, sensor_registry, s2_clock unchanged)
  3 post-query support / planning run below = timing.run line for line, with the channel passed to engine_from
The reference uses the same channel: freshref.reference_for(..., channel) (unchanged) and selection_reference below
(depref's method, channel-aware). Text clones receive a public copy WITHOUT the structured "reports" list, so a gold
fallback cannot happen silently (engine_from never reads it when a channel is given; tests poison it as well).

build_channel = text_channel.build_channel (adapter-v1 unchanged: text_channel.adapt) with two plumbing changes, no
semantic change: (a) the four input lists must have equal length (zip silently dropped reports); (b) the reception
time of an unprocessed report comes from the public call metadata (the time printed in the prose and in the call
record), not from the generator's gold record.

Pre-declared resource rule: if a projection exceeds freshness.MAX_STATES / CPU_LIMIT_S (LimitExceeded) on a text
channel, the trajectory has no support (status "limit_exceeded"), so it declines; this is logged and counted, never
a silently truncated set. On the structured channel it is a software failure.
"""
import hashlib
import json
import time

from . import agentstate as AS, assertions as A, depquery as DQ, engine as E, freshness as F, freshref as FREF, \
    goals as GL, recovery as R, text_channel as TC, timing as TM

RULE = "FTX-v1: DEPQUERY-v1 / TIMING-v1 DEFER with a channel-aware past-report stream"
CHANNELS = ("structured", "text")
SELECTORS = ("BASE", "DEPENDENCY")


def _sha(o):
    return hashlib.sha256(json.dumps(o, sort_keys=True, default=str).encode()).hexdigest()


def text_copy(pub):
    """The public copy handed to every text clone: no structured past reports."""
    out = {k: v for k, v in pub.items() if k != "reports"}
    out["reports"] = None
    return out


# ---------------------------------------------------------------------------------------------- channel

def build_channel(context, spec, raws, registries, texts, received):
    n = len(texts)
    if not (len(raws) == len(registries) == len(received) == n):
        raise AssertionError(f"channel lists differ in length: raws {len(raws)}, registries {len(registries)}, "
                             f"texts {n}, received {len(received)}")
    eng = A.AssertionEngine(spec, f"{context}|text")
    seq, rows = [], []
    for k in range(1, n + 1):
        raw, reg, text, recv = raws[k - 1], registries[k - 1], texts[k - 1], received[k - 1]
        rep, log = TC.adapt(raw, reg)
        accepted, code = False, None
        if rep is not None:
            try:
                eng.ingest(rep)
                accepted = True
                seq.append({"kind": "report", "report": rep})
            except A.ContractRejected as e:
                code = e.code
        else:
            code = "parse" if log["parse_error"] else "unmapped"
        if not accepted:
            pend = {"rid": f"r{k:02d}", "received_at": recv, "raw": text, "candidate": rep, "code": code,
                    "message": log["parse_error"] or log["unmapped"]}
            eng.record_unprocessed(pend["rid"], recv, text, rep, code, pend["message"])
            seq.append({"kind": "pending", "pending": pend})
        rows.append({"k": k, "raw": raw, "report": rep, "adapter_log": log, "accepted": accepted, "code": code})
    return {"sequence": seq, "rows": rows, "n": n}


def perfect_raws(public_records):
    """Canonical public records serialised as ideal extractor replies (no-model protection)."""
    return [json.dumps(r) for r in public_records]


# ---------------------------------------------------------------------------------------------- selection

def s2_support(pub, env_kind, channel, context="select"):
    declared = pub["transitions"] if env_kind == "changing" else []
    ctx = f"{context}|S2|{env_kind}"
    eng = R.engine_from(pub, channel, ctx)
    ledger = F.new_ledger(ctx)
    try:
        return F.temporal_project(eng, ledger, ctx, declared, DQ.s2_clock())
    except F.LimitExceeded as e:
        if channel is None:
            raise
        return {"states": [], "status": "limit_exceeded", "max_set": F.MAX_STATES, "limit": str(e)}


def selection_for(pub, gc, q0, env_kind, channel):
    pr = s2_support(pub, env_kind, channel, pub["episode_id"])
    reg = DQ.sensor_registry(pub)
    sel = DQ.select(q0, pr["states"], reg, gc["relevant"], pr["status"])
    S = pr["states"]
    sel.update(s2_states=S, s2_projection_status=pr["status"],
               s2_uncertain={f: sorted({s.get(f, "<absent>") for s in S}) for f in sel["R"] + list(q0) if f in reg},
               s2_max_set=pr["max_set"], registry=list(reg),
               s2_relevant_coverage={f: (sum(f in s for s in S), len(S)) for f in gc["relevant"]})
    return sel


def selection_reference(pub, gc, q0, env_kind, channel):
    """depref.selection_reference with the channel (exhaustive freshref.reachable; no production propagation)."""
    import itertools
    from fractions import Fraction
    eng = R.engine_from(pub, channel, "ftxref")
    v = eng.view("earlier", TM.ORIGIN, cutoff=DQ.SELECT_AT)
    options = {f: list(o) for f, o in v["op_options"].items()}
    trs = [(tr, tr["window"]["lo"], min(tr["window"]["hi"], DQ.SELECT_AT))
           for tr in (pub["transitions"] if env_kind == "changing" else [])]
    S = FREF.reachable(pub["spec"], options, dict(v["agent_state"]), [], trs, TM.ORIGIN, DQ.SELECT_AT)
    ag = set(AS.agent_fields(pub["spec"]))
    reg = [f for f in pub["registry_allowed"] if f not in ag]
    rr = []
    for f in reg:
        if f in q0:
            continue
        vals = {s.get(f, "<absent>") for s in S}
        if vals == {"<absent>"}:
            continue
        if len(vals) > 1:
            rr.append(f)
    dd = [f for f in rr if f in gc["relevant"]]
    add = dd[:max(0, DQ.CAP - len(q0))]
    subs = list(itertools.combinations(rr, len(add)))
    return {"s2_states": S, "R": rr, "D": dd, "DEPENDENCY": list(q0) + add, "e": len(add),
            "random_weight": str(Fraction(1, len(subs)))}


# ---------------------------------------------------------------------------------------------- trajectory

def run(pub, gc, fields, env_kind, env_ep, tape, channel=None, tag=""):
    """timing.run(schedule DEFER) with the channel passed to engine_from; otherwise identical."""
    schedule = DQ.SCHEDULE
    sc = TM.schedule_clock(schedule)
    pc = TM.projection_clock(sc)
    transitions = pub["transitions"]
    declared = transitions if env_kind == "changing" else []
    env = TM.environment(env_ep, env_kind, transitions, tape, sc)
    ctx = f"{pub['episode_id']}|P2_selective|{env_kind}|{schedule}{tag}"
    eng = R.engine_from(pub, channel, ctx)
    origin_view = eng.view("current", TM.ORIGIN)
    known_at_measure_before = eng.view("earlier", sc["measured_at"], cutoff=sc["measured_at"])
    n0, head0 = len(eng.log.entries), eng.log.head()
    queried = list(fields)
    ledger = F.new_ledger(ctx)
    req, receipts = None, []
    if queried:
        req, receipts = F.sensor_query(env, ledger, ctx, queried, sc["requested_at"], TM.SENSOR_DELAY)
        F.ingest_receipts(eng, ledger, receipts, "q1")
    head1 = eng.log.head()
    views_before = (eng.view("earlier", TM.ORIGIN, cutoff=sc["decision_at"]), eng.view("current", sc["decision_at"]))
    known_at_measure_after = eng.view("earlier", sc["measured_at"], cutoff=sc["received_at"] - 1)
    t0 = time.process_time()
    try:
        pr = F.temporal_project(eng, ledger, ctx, declared, pc)
    except F.LimitExceeded as e:
        if channel is None:
            raise
        pr = {"states": [], "status": "limit_exceeded", "readings": [], "anchors": {}, "refused": [],
              "authority_conflicts": [], "frontier_sizes": [], "max_set": F.MAX_STATES, "limit": str(e)}
    cpu = time.process_time() - t0
    states = pr["states"]
    plan = R.choose(pub, gc, states)
    cls = F.classify(pub, gc, states)
    actual_x, applied = env.state_at(sc["execute_at"])
    actual_0, _ = env.state_at(TM.ORIGIN)
    actual_m, _ = env.state_at(sc["measured_at"])
    rel = gc["relevant"]
    selected = plan is not None
    empty = selected and len(gc["plans"][plan]) == 0
    goal_true = GL.goal_ok(pub["world"], gc["goal"], actual_x)
    if selected:
        res = F.execute_from(pub, gc, plan, actual_x, sc["execute_at"])
    else:
        res = {"success": False, "invalid_attempt": False, "failed_step": None, "action_cost": 0, "steps": 0,
               "end_time": sc["execute_at"]}
    kind = "decline" if not selected else "complete" if empty else "execute"
    u0 = F.SUCCESS_REWARD * res["success"] - res["action_cost"] - F.INVALID_PENALTY * res["invalid_attempt"] - \
        F.QUERY_COST * len(queried)
    dec = F._summary(states, rel)
    valid_x = F.valid_plans_at(pub, gc, actual_x)
    valid_0 = F.valid_plans_at(pub, gc, actual_0)
    t = {
        "episode_id": pub["episode_id"], "domain": pub["domain"], "env": env_kind, "schedule": schedule,
        "rule": TM.RULE, "ftx_rule": RULE, "clock": sc, "projection_clock": pc,
        "declared_transitions": [x["id"] for x in declared],
        "queried": queried, "request": req, "receipts": receipts, "receipts_sha256": _sha(receipts),
        "ledger_sha256": _sha(ledger), "readings": pr["readings"], "anchors": pr.get("anchors", {}),
        "refused": pr["refused"], "authority_conflicts": pr["authority_conflicts"], "status": pr["status"],
        "frontier_sizes": pr["frontier_sizes"], "max_set": pr["max_set"], "cpu_s": cpu,
        "states": states, "states_sha256": _sha(sorted(F._key(s) for s in states)), "n_states": len(states),
        "relevant_support": dec, "uncertain_relevant": [f for f in rel if dec[f] == E.UNKNOWN],
        "uncertain_queried": [f for f in rel if dec[f] == E.UNKNOWN and f in queried],
        "uncertain_unqueried": [f for f in rel if dec[f] == E.UNKNOWN and f not in queried],
        "relevant_coverage": {f: sum(f in s for s in states) for f in rel},
        "fully_represented": bool(states) and all(f in s for s in states for f in rel),
        "candidates": cls, "plan": plan, "selected": selected, "outcome_kind": kind, "empty_plan": empty,
        **res, "goal_true_at_boundary": goal_true,
        "false_completion": kind == "complete" and not res["success"],
        "decline_goal_already_true": kind == "decline" and goal_true,
        "queried_facts": len(queried), "pre_action_wait": sc["pre_action_wait"], "utility_base": u0,
        "utility": {str(l): u0 - l * sc["pre_action_wait"] for l in TM.LAMBDAS},
        "pending": [e["body"]["rid"] for e in eng.log.entries if e["type"] == "pending"],
        "historical_conflict_fields": pr.get("historical_conflict_fields", []),
        "op_conflict_fields_at_base": pr.get("op_conflict_fields_at_base", []),
        "incomplete_fields": pr.get("incomplete_fields", []),
        # hidden-side scoring only
        "actual_relevant_at_execute": {f: actual_x.get(f) for f in rel},
        "actual_relevant_at_measure": {f: actual_m.get(f) for f in rel},
        "actual_preaction_state_sha256": _sha(sorted(actual_x.items())), "applied_events": applied,
        "actual_in_support": any(all(actual_x.get(f) == v for f, v in s.items()) for s in states),
        "valid_at_execute": valid_x, "valid_at_origin": valid_0, "menu_feasible": bool(valid_x),
        "menu_feasible_at_origin": bool(valid_0),
        "candidate_gain": sorted(set(valid_x) - set(valid_0)), "candidate_loss": sorted(set(valid_0) - set(valid_x)),
        "missed_opportunity": bool(valid_x) and not res["success"],
        "log_head": eng.log.head(), "log_unchanged_by_projection": eng.log.head() == head1,
        "history_preserved": (eng.log.entries[n0 - 1]["sha"] if n0 else head0) == head0 and
        F._prefix(eng, n0).view("earlier", TM.ORIGIN, cutoff=TM.ORIGIN) == eng.view("earlier", TM.ORIGIN, cutoff=TM.ORIGIN) and
        (eng.view("earlier", TM.ORIGIN, cutoff=sc["decision_at"]), eng.view("current", sc["decision_at"])) == views_before,
        "receipt_absent_before_reception": known_at_measure_after == known_at_measure_before,
        "historical_detail_sha256": _sha(eng.view("current", sc["decision_at"])["detail"]),
        "origin_view_sha256": _sha(origin_view["detail"]),
    }
    return t


def reference(pub, gc, t, env_kind, channel):
    return FREF.reference_for(pub, gc, t["receipts"], pub["transitions"] if env_kind == "changing" else [],
                              t["projection_clock"], channel)
