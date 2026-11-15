"""V1.11.0 dependency-parity repair and the scoped current-observation authority rule (matched comparison).

Part 1: shared definitions (tempo.agentstate) in every component.
  relevance      agentstate.plan_reads over the goal's candidate plans (goals.candidate_plans, unchanged menu);
                 entity fields in registry order; agent reads are listed separately and must be declared facts of
                 the pre-action phase.
  belief states  AgentStateEngine.view: the historical per-field reconstruction (engine v0.3, unchanged) plus the
                 declared agent state, filtered by the declared invariants, with excluded values kept as
                 diagnostics.
  planner        the cheapest candidate plan guaranteed in every compatible state (rule unchanged), checked with
                 the shared predicate table; a prerequisite that reads a field the state lacks is unknown.
  executor       the same predicate table on the hidden true state (which must be admissible and complete for
                 every field a candidate reads).

Part 2: contracts (both use part 1, the same engine log, the same queries and the same sensor receipts).
  strict  (control)    the operational view of the log: a verified-verified conflict stays a conflict after a
                       sensor reading (contract v1, unchanged).
  scoped  (treatment)  rule SCOPED-CURRENT-OBSERVATION-v1, below.

Sensor (unchanged reliability, cost 1 per field, delay 1, budget 2): a query request at t names fields; the sensor
service returns one receipt per field {receipt_id, sensor_id, context, request_id, field, measured_at=t,
received_at=t+1, value=true value at t}. Receipts go to a separate sensor ledger written only by the sensor
service. As in 1.9.x/1.10.0 the same measurement is also ingested into the log as one verified state report (rid
q1, source "sensor"), identically in both contracts.

SCOPED-CURRENT-OBSERVATION-v1 (named authority rule; not "newest verified wins"):
  A receipt anchors field f for the current pre-action decision at time t iff
    - its sensor_id is registered as a current-state authority for this context in the ledger's sensor registry
      (only the sensor service registers; an extracted report, or text calling itself a sensor, never qualifies);
    - its context equals the decision context, its request_id is a request in the ledger, and f is one of that
      request's fields;
    - measured_at >= STABLE_FROM (the declared stable interval: from the decision time, nothing changes except
      through your own actions) and received_at <= t;
    - no evidence about f is later than the measurement: no report assertion or event about f at a time after
      measured_at, and no unprocessed report naming f received after measured_at; and no action of yours has been
      executed (pre-action phase);
    - every qualifying receipt for f agrees (equal-time contradictory readings from authorities stay conflicted;
      under the stable-world declaration, any disagreement is a contradiction, never resolved by recency);
    - the value is admissible under the declared invariants and agent state.
  An anchored field takes the measured value in the operational projection only: it is no longer conflicted,
  incomplete or widened for this decision. Everything else is the strict operational view, unchanged.
  It never: edits the log, the historical per-field reconstruction or its conflict/culprit records; certifies or
  suspends any extracted report; creates an event or reconstructs any earlier interval; changes any
  earlier-information view or old decision record; touches an unqueried field, another context, or any state
  after an action (later states come from the plan's own action effects in planning and execution).
  The projection is versioned and records, per anchored field, the receipt IDs, measurement time, validity scope
  and the field's historical status; refused receipts are listed with a reason.
"""
import copy
import hashlib
import json

from . import agentstate as AS, assertions as A, engine as E, goals as GL, policy as P

DECIDE, QUERY_COST, QUERY_DELAY, QUERY_BUDGET = P.DECIDE, P.QUERY_COST, P.QUERY_DELAY, P.QUERY_BUDGET
SUCCESS_REWARD, INVALID_PENALTY, POLICIES = P.SUCCESS_REWARD, P.INVALID_PENALTY, P.POLICIES
STABLE_FROM = DECIDE
SENSOR_ID = "sensor:reliable-current-v1"
RULE = "SCOPED-CURRENT-OBSERVATION-v1"
CONTRACTS = ("strict", "scoped")


def _sha(o):
    return hashlib.sha256(json.dumps(o, sort_keys=True, default=str).encode()).hexdigest()


# ---------------------------------------------------------------------------------------------- goal contexts

def relevant_fields(spec, plans, goal, allowed):
    rel, agent = set(), set()
    for p in plans.values():
        r, a = AS.plan_reads(spec, p, GL.goal_field(goal))
        rel |= set(r); agent |= set(a)
    order = list(allowed)
    missing = rel - set(order)
    if missing:
        raise AssertionError(f"relevant fields outside the public registry: {sorted(missing)}")
    undeclared = agent - set(AS.declared_agent_state(spec))
    if undeclared:
        raise AssertionError(f"agent reads with no declared pre-action value: {sorted(undeclared)}")
    return [f for f in order if f in rel], sorted(agent)


def context(ep, goal):
    plans = GL.candidate_plans(ep["world"], ep["domain"], goal)
    rel, agent = relevant_fields(ep["spec"], plans, goal, ep["registry_allowed"])
    return {"goal": goal, "plans": plans, "relevant": rel, "agent_reads": agent}


def truth_state(ep):
    """The hidden true pre-action state with the declared agent state (must be admissible)."""
    s = dict(ep["truth"])
    for f, v in AS.declared_agent_state(ep["spec"]).items():
        if f in s and s[f] != v:
            raise AssertionError(f"truth {f}={s[f]} contradicts the declared agent state {v}")
        s[f] = v
    bad = AS.violations(ep["spec"], s)
    if bad:
        raise AssertionError(f"true state violates invariants: {bad}")
    return s


# ---------------------------------------------------------------------------------------------- planner / executor

def guaranteed(spec, states, world, goal, plan, table):
    if not states:
        return False
    gf = GL.goal_field(goal)
    for s in states:
        cur = dict(s)
        for step in plan:
            if AS.missing_reads(spec, cur, list(step), table):
                return False
            _, ok, nxt = AS.evaluate(spec, cur, list(step), table)
            if not ok:
                return False
            cur = nxt
            if AS.violations(spec, cur):
                raise AssertionError(f"successor violates invariants: {step} {AS.violations(spec, cur)}")
        if gf not in cur or not GL.goal_ok(world, goal, cur):
            return False
    return True


def choose(ep, gc, states):
    table = AS.actions(ep["spec"])
    good = [(P.plan_cost(ep["spec"], p), k) for k, p in gc["plans"].items()
            if guaranteed(ep["spec"], states, ep["world"], gc["goal"], p, table)]
    return min(good)[1] if good else None


def _simulate(ep, gc, plan):
    spec, table = ep["spec"], AS.actions(ep["spec"])
    s = truth_state(ep)
    for i, step in enumerate(plan):
        miss = AS.missing_reads(spec, s, list(step), table)
        if miss:
            raise AssertionError(f"true state lacks {miss} read by {step}")
        _, ok, nxt = AS.evaluate(spec, s, list(step), table)
        if not ok:
            return False, i, s
        s = nxt
        if AS.violations(spec, s):
            raise AssertionError(f"executor successor violates invariants after {step}")
    return True, len(plan), s


def true_valid_plans(ep, gc):
    out = []
    for k, p in gc["plans"].items():
        ok, _, s = _simulate(ep, gc, p)
        if ok and GL.goal_ok(ep["world"], gc["goal"], s):
            out.append(k)
    return out


def execute(ep, gc, plan_key, t):
    plan = gc["plans"][plan_key]
    ok, n, s = _simulate(ep, gc, plan)
    if not ok:
        return {"success": False, "invalid_attempt": True, "failed_step": list(plan[n]),
                "action_cost": P.plan_cost(ep["spec"], plan[:n]), "steps": n + 1, "end_time": t + n + 1}
    return {"success": GL.goal_ok(ep["world"], gc["goal"], s), "invalid_attempt": False, "failed_step": None,
            "action_cost": P.plan_cost(ep["spec"], plan), "steps": n, "end_time": t + n}


# ---------------------------------------------------------------------------------------------- engine and P2 rule

def engine_from(ep, channel=None, context="ctx"):
    eng = AS.AgentStateEngine(ep["spec"], context)
    if channel is None:
        for r in ep["reports"]:
            eng.ingest(r)
        return eng
    for item in channel["sequence"]:
        if item["kind"] == "report":
            eng.ingest(item["report"])
        else:
            p = item["pending"]
            eng.record_unprocessed(p["rid"], p["received_at"], p["raw"], p["candidate"], p["code"], p["message"])
    return eng


def needs_verification(view, fields):
    """policy.needs_verification on the operational view: a relevant field is queried if it is not described,
    unknown or conflicted (historically, or with the declared invariants), depends on provisional evidence, or is
    incomplete."""
    out = []
    for f in fields:
        d = view["detail"].get(f, {"status": "not_yet_described"})
        st = view["op_per_field"].get(f)
        if st is None or st in (E.UNKNOWN, "conflict") or d.get("provisional_support") or \
                f in view["incomplete_fields"] or view["context_incomplete"]:
            out.append(f)
    return out


# ---------------------------------------------------------------------------------------------- sensor ledger

def new_ledger(context):
    return {"sensor_registry": {SENSOR_ID: {"kind": "current_state", "reliable": True, "cost": QUERY_COST,
                                             "delay": QUERY_DELAY, "contexts": [context]}},
            "requests": [], "receipts": []}


def sensor_query(ep, ledger, context, fields, t):
    """The sensor service (environment side): records the request and returns its receipts."""
    req = {"request_id": f"{context}|req{len(ledger['requests']) + 1}", "context": context, "sensor_id": SENSOR_ID,
           "fields": list(fields), "requested_at": t}
    truth = truth_state(ep)
    recs = [{"receipt_id": f"{req['request_id']}|{f}", "sensor_id": SENSOR_ID, "context": context,
             "request_id": req["request_id"], "field": f, "measured_at": t, "received_at": t + QUERY_DELAY,
             "value": truth[f]} for f in fields]
    ledger["requests"].append(req)
    ledger["receipts"].extend(recs)
    return req, recs


def log_report(receipts, rid="q1"):
    """The same verified state report 1.9.x/1.10.0 ingested for a query batch."""
    return {"rid": rid, "received_at": receipts[0]["received_at"], "status": "verified", "type": "state",
            "source": "sensor", "assertions": [{"field": r["field"], "at": r["measured_at"], "value": r["value"]}
                                               for r in receipts]}


# ---------------------------------------------------------------------------------------------- scoped projection

def _later_evidence(eng, f, m):
    for r in eng.reports():
        for a in r["assertions"]:
            if a["field"] != f:
                continue
            at = a["valid_from"] if r["type"] == "correction" else a["at"]
            if at > m:
                return f"report {r['rid']} about time {at}"
    for p in eng.pending():
        if (f in p["affected_fields"] or p["context_wide"]) and p["received_at"] > m:
            return f"unprocessed {p['rid']} received at {p['received_at']}"
    return None


def project(eng, view, ledger, t, context):
    """SCOPED-CURRENT-OBSERVATION-v1. Returns the projection record; never changes eng or view."""
    head, spec = eng.log.head(), eng.spec
    agent = AS.declared_agent_state(spec)
    reqs = {r["request_id"]: r for r in ledger["requests"]}
    reg = ledger["sensor_registry"]
    cand, refused = {}, []
    for r in ledger["receipts"]:
        why = None
        if r["sensor_id"] not in reg or reg[r["sensor_id"]].get("kind") != "current_state":
            why = "unregistered_sensor"
        elif context not in reg[r["sensor_id"]]["contexts"] or r["context"] != context:
            why = "other_context"
        elif r["request_id"] not in reqs or r["field"] not in reqs[r["request_id"]]["fields"] or \
                reqs[r["request_id"]]["context"] != context:
            why = "unrequested_field"
        elif r["received_at"] > t:
            why = "not_yet_received"
        elif r["measured_at"] < STABLE_FROM or r["measured_at"] > t:
            why = "outside_stable_interval"
        elif eng.log.executions():
            why = "after_an_action"
        else:
            later = _later_evidence(eng, r["field"], r["measured_at"])
            if later:
                why = f"stale: {later}"
            elif not AS.admissible(spec, dict(agent, **{r["field"]: r["value"]})):
                why = "inadmissible_value"
        if why:
            refused.append({"receipt_id": r["receipt_id"], "field": r["field"], "reason": why})
        else:
            cand.setdefault(r["field"], []).append(r)
    anchors, authority_conflicts = {}, []
    for f, rs in cand.items():
        vals = sorted({r["value"] for r in rs})
        if len(vals) > 1:
            authority_conflicts.append({"field": f, "values": vals, "receipt_ids": [r["receipt_id"] for r in rs]})
            continue
        d = view["detail"].get(f, {"status": "not_yet_described"})
        anchors[f] = {"value": vals[0], "receipt_ids": [r["receipt_id"] for r in rs],
                      "measured_at": max(r["measured_at"] for r in rs),
                      "valid_for": f"pre-action state of {f} from time {max(r['measured_at'] for r in rs)} under the "
                                   f"declared stable interval; later states only through your own actions",
                      "historical_status": d["status"], "historical_culprits": list(d.get("culprits", [])),
                      "operational_status_without_rule": view["op_per_field"].get(f, "not_yet_described"),
                      "incomplete_without_rule": f in view["incomplete_fields"]}
    fixed = {f: a["value"] for f, a in anchors.items()}
    states = []
    for s in view["states"]:
        n = dict(s, **fixed)
        if n not in states:
            states.append(n)
    if not view["states"]:
        states = []
    assert eng.log.head() == head, "the projection changed the log"
    return {"rule": RULE, "version": 1, "anchors": anchors, "refused": refused,
            "authority_conflicts": authority_conflicts, "states": states,
            "conflict_fields": [f for f in view["op_conflict_fields"] if f not in anchors],
            "incomplete_fields": [f for f in view["incomplete_fields"] if f not in anchors],
            "historical_conflict_fields": list(view["conflict_fields"]), "log_head": head}


# ---------------------------------------------------------------------------------------------- the matched loop

def _summary(states, fields):
    out = {}
    for f in fields:
        vals = {s.get(f, "<absent>") for s in states}
        out[f] = "conflict_or_absent" if "<absent>" in vals else (vals.pop() if len(vals) == 1 else E.UNKNOWN)
    return out


def run(ep, gc, policy="P2_selective", channel=None, tag=""):
    """One goal clone, one channel: shared extraction, view, query request and receipts; then the decision under
    each contract. Returns {"strict": trajectory, "scoped": trajectory}."""
    ctx = f"{ep['episode_id']}|{policy}{tag}"
    eng = engine_from(ep, channel, ctx)
    t = DECIDE
    before = eng.view("current", t)
    earlier_before = eng.view("earlier", t, cutoff=DECIDE)
    rel = gc["relevant"]
    pre_plan = choose(ep, gc, before["states"])
    queried = [] if policy == "P0_accepted" else list(rel) if policy == "P1_always" else needs_verification(before, rel)
    budget_exhausted = len(queried) > QUERY_BUDGET
    queried = queried[:QUERY_BUDGET]
    ledger = new_ledger(ctx)
    req, receipts = None, []
    if queried:
        req, receipts = sensor_query(ep, ledger, ctx, queried, t)
        eng.ingest(log_report(receipts))
        t += QUERY_DELAY
    after = eng.view("current", t)
    valid = true_valid_plans(ep, gc)
    truth = truth_state(ep)
    all_fields = sorted({f for s in after["states"] for f in s} | set(after["detail"]))
    strict_summary = _summary(after["states"], all_fields)
    out = {}
    for contract in CONTRACTS:
        proj = None
        if contract == "strict":
            states, conf, inc = after["states"], after["op_conflict_fields"], after["incomplete_fields"]
        else:
            proj = project(eng, after, ledger, t, ctx)
            states, conf, inc = proj["states"], proj["conflict_fields"], proj["incomplete_fields"]
        plan = choose(ep, gc, states)
        res = execute(ep, gc, plan, t) if plan else {"success": False, "invalid_attempt": False, "failed_step": None,
                                                       "action_cost": 0, "steps": 0, "end_time": t}
        dec = _summary(states, rel)
        anchored = set(proj["anchors"]) if proj else set()
        summ = _summary(states, all_fields)
        reasons = sorted({("conflict" if f in conf else "incomplete" if f in inc else
                           "unresolved" if dec[f] == E.UNKNOWN else "absent" if dec[f] == "conflict_or_absent" else "")
                          for f in rel} - {""}) if plan is None else []
        utility = SUCCESS_REWARD * res["success"] - res["action_cost"] - INVALID_PENALTY * res["invalid_attempt"] - \
            QUERY_COST * len(queried)
        out[contract] = {
            "episode_id": ep["episode_id"], "domain": ep["domain"], "type": ep.get("type"), "policy": policy,
            "contract": contract, "queried": list(queried), "request": req, "receipts": receipts,
            "receipts_sha256": _sha(receipts), "pre_query_plan": pre_plan, "plan": plan, **res, "utility": utility,
            "opportunity": bool(valid), "true_valid_plans": valid, "declined": plan is None,
            "false_block": plan is None and bool(valid), "false_permission": res["invalid_attempt"],
            "missed_opportunity": bool(valid) and not res["success"], "decline_reasons": reasons,
            "budget_exhausted": budget_exhausted,
            "op_state_correct_at_decision": all(dec[f] == truth.get(f) for f in rel),
            "op_state_correct_before": all(_summary(before["states"], rel)[f] == truth.get(f) for f in rel),
            "relevant_at_decision": dec,
            "conflict_at_decision": [f for f in rel if f in conf], "incomplete_at_decision": [f for f in rel if f in inc],
            "historical_conflicts_at_decision": list(after["conflict_fields"]),
            "invariant_before": before["invariant"], "invariant_at_decision": after["invariant"],
            "anchors": proj["anchors"] if proj else {}, "refused_receipts": proj["refused"] if proj else [],
            "authority_conflicts": proj["authority_conflicts"] if proj else [],
            "unanchored_fields_unchanged": all(summ[f] == strict_summary[f] for f in all_fields if f not in anchored),
            "earlier_view_preserved": eng.view("earlier", DECIDE, cutoff=DECIDE) == earlier_before,
            "historical_detail_sha256": _sha(after["detail"]), "log_head": eng.log.head(),
            "log_reports": len(eng.reports()), "delay": res["end_time"] - DECIDE,
            "state_before": dict(before["op_per_field"]), "historical_before": dict(before["per_field"]),
        }
    return out
