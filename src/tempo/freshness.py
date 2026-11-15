"""V1.12.0 observation freshness: a reliable reading in a world that may change while it is being delivered.

Question: can an operational projection keep what a reliable reading established at its measurement time,
propagate only the publicly allowed changes to the time action begins, and choose a plan that is valid in every
state still possible then? The simulator supplies the change rules (public transition declarations); nothing here
infers dynamics from prose.

Unchanged from 1.11.0 (imported, not copied): the shared predicate table and invariants (agentstate), the
engine and historical reconstruction (assertions v0.3 + AgentStateEngine), P2's evidence-status request rule
(recovery.needs_verification), the cheapest-guaranteed-candidate planner (recovery.choose / guaranteed), the
candidate menus (goals.candidate_plans), sensor reliability, cost (1 per fact), budget (2), utility.

CLOCK (published before any scored trace; every trace stores absolute times, elapsed times and the offset)
  requested_at  the batch is requested: absolute DECIDE = 12, elapsed 0 (offset 12).
  measured_at   all fields of the batch are sampled from the environment at the request instant (= requested_at).
  received_at   measured_at + delay (delay 0 or 2 in the main panel; 1.11.0 used 1).
  decision_at   = received_at (the controller decides as soon as the receipt is available).
  execute_at    the scheduled first-action boundary = received_at + gap (gap 0 in the main panel; a fixture uses
                gap 1). It exists even if the controller declines: support and missed opportunities are evaluated
                at that same time.
  ORDERING: observations, receptions, decisions and actions occur at integer instants; at one instant the order
  is measure < receive < decide < first action. External changes occur only at non-integer (half-tick) times,
  strictly inside their window (requested_at, execute_at) -- an open interval, so a change can never be ordered
  at or after an action, and with delay 0 and gap 0 the window is empty. External changes are disabled from
  execute_at on (during the plan, only your own actions change the world).

PUBLIC TRANSITION DECLARATION (environment variant "changing"; "stable" declares none)
  {"id", "text", "guard": {field: value}, "effect": {field: value}, "window": {"from": "requested_at",
   "to": "execute_at"} (or numeric "lo"/"hi" in fixtures), "max_occurrences": 1}
  Each declared change may happen at most once, at any (unannounced) time inside its window, if its guard holds
  at that moment; it may also not happen at all (the no-change branch always exists). Correlated effects are one
  transition. Effects preserve the declared invariants and never write agent state. The realized tape, its seed,
  case labels and the eventual true state are hidden (environment side only). The absence of a new report is not
  evidence that nothing changed.

PROJECTIONS (same log, same P2 request, same receipts, same ledger)
  carry_forward  ABLATION THAT OMITS TEMPORAL PROPAGATION: the 1.11.0 scoped rule (recovery.project,
                 SCOPED-CURRENT-OBSERVATION-v1, unchanged) at decision_at, its states carried to execute_at as if
                 nothing could change. In the stable variant this is exactly 1.11.0's contract; in the changing
                 variant it deliberately extrapolates beyond 1.11.0's stable-world guarantee.
  temporal       TEMPORAL-OBSERVATION-v1 (temporal_project, below).

TEMPORAL-OBSERVATION-v1
  target state time  execute_at.   evidence-availability cutoff  decision_at.   base time  requested_at.
  1 Base support: the historical operational view at the base time from the non-sensor evidence received by
    the cutoff (a shadow AgentStateEngine over the shared log minus the sensor's own log reports, so a later
    reading is never back-propagated into an earlier time by persistence). Reports describing a time after the
    base time are outside this version's scope (none exist in the panel): the projection then returns no
    support ("out_of_scope_later_report"), never a guess.
  2 Receipts are screened exactly as in 1.11.0 (registered current-state sensor, context, requested field,
    received by the cutoff, no action of yours yet, admissible value) plus: measured at or after its request
    and the base time, and not after execute_at. Equal-time contradictory receipts are an authority conflict
    (no recency rule). A reading is a point-time value: it is certain about its measured time only.
  3 Readings at the base time anchor their fields there (the 1.11.0 scoped authority: they replace the
    historical support of that field, conflicted or not, in this projection only). Readings at later times
    constrain the propagated set at their own times (states inconsistent with them are dropped).
  4 Propagation: between consecutive observation instants, every declared transition whose window overlaps the
    segment and that has not yet occurred may occur, in any order, when its guard holds (finite closure;
    occurrence flags are tracked so a change happens at most once). Unqueried verified facts are propagated too.
    A guard that reads a field the state lacks may or may not hold: the effect's fields become absent (unknown).
  5 possible_at_execution = the reachable set at execute_at. The planner is unchanged: the cheapest candidate
    that succeeds in every state of that set; an empty set is a conflict (no plan), never universal permission.
  It never edits the log, the historical reconstruction, source statuses, conflicts or earlier-information
  views; never invents an event; never uses the hidden tape, a time-to-live, recency, or a probability.
  Limits (frozen): at most MAX_STATES states per frontier and CPU_LIMIT_S seconds per projection; exceeding
  either raises LimitExceeded (reported, never a silently truncated set).
"""
import copy
import hashlib
import itertools
import json
import time

from . import agentstate as AS, assertions as A, engine as E, goals as GL, policy as P, recovery as R

REQUEST_AT = R.DECIDE
DELAYS = (0, 2)
ENVS = ("stable", "changing")
PROJECTIONS = ("carry_forward", "temporal")
RULE = "TEMPORAL-OBSERVATION-v1"
ABLATION = "CARRY-FORWARD (recovery.project, SCOPED-CURRENT-OBSERVATION-v1, no propagation)"
MAX_STATES = 4096
CPU_LIMIT_S = 5.0
SENSOR_ID = R.SENSOR_ID
QUERY_COST, QUERY_BUDGET = R.QUERY_COST, R.QUERY_BUDGET
SUCCESS_REWARD, INVALID_PENALTY = R.SUCCESS_REWARD, R.INVALID_PENALTY
ORDERING = ("integer instants: measure < receive < decide < first action; external changes only at half-ticks "
            "strictly inside (requested_at, execute_at); none from execute_at on")


class LimitExceeded(Exception):
    pass


class DeclarationError(Exception):
    pass


def _sha(o):
    return hashlib.sha256(json.dumps(o, sort_keys=True, default=str).encode()).hexdigest()


# ---------------------------------------------------------------------------------------------- clock

def make_clock(delay, gap=0, requested_at=REQUEST_AT):
    m = requested_at
    r = m + delay
    x = r + gap
    return {"requested_at": requested_at, "measured_at": m, "received_at": r, "decision_at": r, "execute_at": x,
            "offset": requested_at, "delay": delay, "receipt_to_execution_gap": gap,
            "elapsed": {"requested_at": 0, "measured_at": m - requested_at, "received_at": r - requested_at,
                        "decision_at": r - requested_at, "execute_at": x - requested_at},
            "ordering": ORDERING}


def window(tr, clock):
    w = tr["window"]
    lo = w["lo"] if "lo" in w else clock[w["from"]]
    hi = w["hi"] if "hi" in w else clock[w["to"]]
    return lo, min(hi, clock["execute_at"])  # external changes are disabled from the first action on


# ---------------------------------------------------------------------------------------------- declarations

def check_declaration(spec, tr, allowed=None):
    """Raise DeclarationError unless the transition is well formed and preserves the invariants on every
    admissible state (over the involved fields' engine domains, with the declared agent state)."""
    spec_ = AS._spec(spec)
    for k in ("id", "guard", "effect", "window"):
        if k not in tr:
            raise DeclarationError(f"{tr.get('id')}: missing {k}")
    if tr.get("max_occurrences", 1) != 1:
        raise DeclarationError(f"{tr['id']}: only one-shot transitions are supported")
    ag = set(AS.agent_fields(spec_))
    fs = list(dict.fromkeys(list(tr["guard"]) + list(tr["effect"])))
    for f in fs:
        if f in ag:
            raise DeclarationError(f"{tr['id']}: external changes never read or write agent state ({f})")
        if not spec_.field_ok(f):
            raise DeclarationError(f"{tr['id']}: field {f} not registered")
    for f, v in list(tr["guard"].items()) + list(tr["effect"].items()):
        if not spec_.value_ok(f, v):
            raise DeclarationError(f"{tr['id']}: value {v} outside the domain of {f}")
    for f, v in tr["effect"].items():
        if allowed is not None and f in allowed and v not in allowed[f]:
            raise DeclarationError(f"{tr['id']}: effect value {v} not publicly allowed for {f}")
    agent = AS.declared_agent_state(spec_)
    n = 0
    for combo in itertools.product(*[AS.domain(spec_, f) for f in fs]):
        s = dict(agent, **dict(zip(fs, combo)))
        if not AS.admissible(spec_, s) or any(s[f] != v for f, v in tr["guard"].items()):
            continue
        n += 1
        t = dict(s, **tr["effect"])
        if AS.violations(spec_, t):
            raise DeclarationError(f"{tr['id']}: effect violates {AS.violations(spec_, t)} from {s}")
    if n == 0:
        raise DeclarationError(f"{tr['id']}: guard never holds in an admissible state")
    return True


# ---------------------------------------------------------------------------------------------- environment (hidden)

class Environment:
    """Environment side only: the hidden initial truth, the public declarations and the hidden event tape
    [{"transition": id, "elapsed": u}] (absolute time = offset + u). An event occurs iff its time is strictly inside
    its window and strictly before the queried time, and its guard holds in the actual state at that moment."""

    def __init__(self, ep, transitions, tape, clock):
        self.spec, self.clock = ep["spec"], clock
        self.s0 = R.truth_state(ep)
        self.trs = {t["id"]: t for t in transitions}
        self.tape = sorted(tape, key=lambda e: e["elapsed"])
        self.log = []

    def state_at(self, t):
        s, applied = dict(self.s0), []
        for e in self.tape:
            at = self.clock["offset"] + e["elapsed"]
            tr = self.trs.get(e["transition"])
            if tr is None or at >= t:
                continue
            lo, hi = window(tr, self.clock)
            if not (lo < at < hi) or float(at).is_integer():
                continue
            if all(s.get(f) == v for f, v in tr["guard"].items()):
                s = dict(s, **tr["effect"])
                applied.append({"transition": tr["id"], "at": at})
                if AS.violations(self.spec, s):
                    raise AssertionError(f"environment state violates invariants after {tr['id']}")
        return s, applied


# ---------------------------------------------------------------------------------------------- sensor

def new_ledger(context):
    led = R.new_ledger(context)
    led["log_rids"] = []
    return led


def sensor_query(env, ledger, context, fields, requested_at, delay, measured_at=None):
    """The sensor service: measures the actual environment state at measured_at (default: the request instant)
    and delivers at measured_at + delay."""
    m = requested_at if measured_at is None else measured_at
    req = {"request_id": f"{context}|req{len(ledger['requests']) + 1}", "context": context, "sensor_id": SENSOR_ID,
           "fields": list(fields), "requested_at": requested_at}
    s, _ = env.state_at(m)
    recs = [{"receipt_id": f"{req['request_id']}|{f}", "sensor_id": SENSOR_ID, "context": context,
             "request_id": req["request_id"], "field": f, "measured_at": m, "received_at": m + delay,
             "value": s[f]} for f in fields]
    ledger["requests"].append(req)
    ledger["receipts"].extend(recs)
    return req, recs


def ingest_receipts(eng, ledger, receipts, rid):
    """The same verified state report 1.9.x-1.11.0 ingested for a query batch (one per batch)."""
    eng.ingest(R.log_report(receipts, rid))
    ledger["log_rids"].append(rid)


# ---------------------------------------------------------------------------------------------- temporal projection

def _shadow(eng, exclude_rids):
    sh = AS.AgentStateEngine(eng.spec, eng.log.context)
    for e in eng.log.entries:
        if e["type"] == "report" and e["body"]["rid"] in exclude_rids:
            continue
        sh.log.append(e["type"], e["body"])
    return sh


def _prefix(eng, n):
    sh = AS.AgentStateEngine(eng.spec, eng.log.context)
    for e in eng.log.entries[:n]:
        sh.log.append(e["type"], e["body"])
    return sh


def _key(s):
    return tuple(sorted(s.items()))


def _succ(spec, s, tr):
    """Successor of state s under transition tr, or None if its guard is false in s."""
    g = tr["guard"]
    if any(f in s and s[f] != v for f, v in g.items()):
        return None
    if all(f in s for f in g):
        n = dict(s, **tr["effect"])
        if AS.violations(spec, n):
            raise DeclarationError(f"{tr['id']} produced an inadmissible state")
        return n
    return {f: v for f, v in s.items() if f not in tr["effect"]}  # guard unknown: effect fields become unknown


def reach(spec, items, transitions, a, b, deadline=None):
    """Closure over the open segment (a, b): items is {(state_key, fired frozenset)}."""
    elig = [(tr, lo, hi) for tr, (lo, hi) in transitions if a < b and lo < b and hi > a]
    seen, frontier = set(items), list(items)
    while frontier:
        k, fired = frontier.pop()
        s = dict(k)
        for tr, _, _ in elig:
            if tr["id"] in fired:
                continue
            n = _succ(spec, s, tr)
            if n is None:
                continue
            it = (_key(n), fired | {tr["id"]})
            if it not in seen:
                seen.add(it)
                frontier.append(it)
                if len(seen) > MAX_STATES:
                    raise LimitExceeded(f"more than {MAX_STATES} states")
        if deadline and time.process_time() > deadline:
            raise LimitExceeded(f"more than {CPU_LIMIT_S} s CPU")
    return seen


def screen_receipts(eng, ledger, context, clock):
    reqs = {r["request_id"]: r for r in ledger["requests"]}
    reg = ledger["sensor_registry"]
    agent = AS.declared_agent_state(eng.spec)
    ok, refused = [], []
    for r in ledger["receipts"]:
        why = None
        req = reqs.get(r["request_id"])
        if r["sensor_id"] not in reg or reg[r["sensor_id"]].get("kind") != "current_state":
            why = "unregistered_sensor"
        elif context not in reg[r["sensor_id"]]["contexts"] or r["context"] != context:
            why = "other_context"
        elif req is None or r["field"] not in req["fields"] or req["context"] != context:
            why = "unrequested_field"
        elif r["received_at"] > clock["decision_at"]:
            why = "not_yet_received"
        elif r["measured_at"] < req["requested_at"] or r["measured_at"] < clock["requested_at"]:
            why = "measured_before_request"
        elif r["measured_at"] > clock["execute_at"]:
            why = "measured_after_target_time"
        elif eng.log.executions():
            why = "after_an_action"
        elif not AS.admissible(eng.spec, dict(agent, **{r["field"]: r["value"]})):
            why = "inadmissible_value"
        if why:
            refused.append({"receipt_id": r["receipt_id"], "field": r["field"], "reason": why})
        else:
            ok.append(r)
    by, conflicts, readings = {}, [], []
    for r in ok:
        by.setdefault((r["measured_at"], r["field"]), []).append(r)
    for (m, f), rs in sorted(by.items()):
        vals = sorted({r["value"] for r in rs})
        if len(vals) > 1:
            conflicts.append({"field": f, "measured_at": m, "values": vals, "receipt_ids": [r["receipt_id"] for r in rs]})
            continue
        readings.append({"field": f, "measured_at": m, "value": vals[0], "receipt_ids": [r["receipt_id"] for r in rs]})
    return readings, refused, conflicts


def _resolved(transitions, clock):
    return [(tr, window(tr, clock)) for tr in transitions]


def temporal_project(eng, ledger, context, transitions, clock):
    """TEMPORAL-OBSERVATION-v1. Returns the projection record; never changes eng."""
    t0 = time.process_time()
    deadline = t0 + CPU_LIMIT_S
    head, spec = eng.log.head(), eng.spec
    if eng.log.executions():
        raise AS.InvariantViolationInPhase("the temporal projection is a pre-action projection")
    base, cutoff, target = clock["requested_at"], clock["decision_at"], clock["execute_at"]
    hist = _shadow(eng, set(ledger.get("log_rids", [])))
    later = sorted({r["rid"] for r in hist.reports(cutoff) for a in r["assertions"]
                    if (a["valid_from"] if r["type"] == "correction" else a["at"]) > base})
    view = hist.view("earlier", base, cutoff=cutoff)
    readings, refused, conflicts = screen_receipts(eng, ledger, context, clock)
    rec = {"rule": RULE, "version": 1, "base_time": base, "evidence_cutoff": cutoff, "target_time": target,
           "readings": readings, "refused": refused, "authority_conflicts": conflicts,
           "historical_conflict_fields": list(view["conflict_fields"]), "op_conflict_fields_at_base":
           list(view["op_conflict_fields"]), "incomplete_fields": list(view["incomplete_fields"]),
           "invariant_at_base": view["invariant"], "transitions": [tr["id"] for tr in transitions]}
    if later:
        assert eng.log.head() == head
        return dict(rec, status="out_of_scope_later_report", later_reports=later, states=[], states_at_base=[],
                    frontier_sizes=[], max_set=0, cpu_s=time.process_time() - t0, log_head=head)
    anchors = {x["field"]: x for x in readings if x["measured_at"] == base}
    states = []
    for s in view["states"]:
        n = dict(s, **{f: x["value"] for f, x in anchors.items()})
        if n not in states:
            states.append(n)
    at_base = [dict(s) for s in states]
    trs = _resolved(transitions, clock)
    items = {(_key(s), frozenset()) for s in states}
    sizes, prev = [len(items)], base
    for m in sorted({x["measured_at"] for x in readings if x["measured_at"] > base}):
        items = reach(spec, items, trs, prev, m, deadline)
        sizes.append(len(items))
        here = [x for x in readings if x["measured_at"] == m]
        items = {it for it in items if all(dict(it[0]).get(x["field"]) == x["value"] for x in here)}
        sizes.append(len(items))
        prev = m
    items = reach(spec, items, trs, prev, target, deadline)
    sizes.append(len(items))
    final, seen = [], set()
    for k, _ in sorted(items, key=lambda it: (it[0], sorted(it[1]))):
        if k not in seen:
            seen.add(k)
            final.append(dict(k))
    assert eng.log.head() == head, "the projection changed the log"
    return dict(rec, status="ok" if final else "empty_support", anchors={f: {"value": x["value"], "measured_at": base,
                "receipt_ids": x["receipt_ids"], "valid_for": f"value of {f} at its measurement time {base}; later "
                "values only through the public transition relation or your own actions"} for f, x in anchors.items()},
                states=final, states_at_base=at_base, frontier_sizes=sizes, max_set=max(sizes),
                cpu_s=time.process_time() - t0, log_head=head)


# ---------------------------------------------------------------------------------------------- planner / executor

def classify(pub, gc, states):
    """Per candidate: guaranteed (every state) / possible (some state) / impossible (none), production planner."""
    spec, table = pub["spec"], AS.actions(pub["spec"])
    out = {}
    for k, p in gc["plans"].items():
        per = [R.guaranteed(spec, [s], pub["world"], gc["goal"], p, table) for s in states]
        out[k] = "guaranteed" if per and all(per) else "possible" if any(per) else "impossible"
    return out


def simulate_from(pub, gc, plan, s):
    spec, table = pub["spec"], AS.actions(pub["spec"])
    s = dict(s)
    for i, step in enumerate(plan):
        miss = AS.missing_reads(spec, s, list(step), table)
        if miss:
            raise AssertionError(f"actual state lacks {miss} read by {step}")
        _, ok, nxt = AS.evaluate(spec, s, list(step), table)
        if not ok:
            return False, i, s
        s = nxt
    return True, len(plan), s


def valid_plans_at(pub, gc, s):
    return sorted(k for k, p in gc["plans"].items()
                  if (lambda r: r[0] and GL.goal_ok(pub["world"], gc["goal"], r[2]))(simulate_from(pub, gc, p, s)))


def execute_from(pub, gc, plan_key, s, t):
    plan = gc["plans"][plan_key]
    ok, n, end = simulate_from(pub, gc, plan, s)
    if not ok:
        return {"success": False, "invalid_attempt": True, "failed_step": list(plan[n]),
                "action_cost": P.plan_cost(pub["spec"], plan[:n]), "steps": n + 1, "end_time": t + n + 1}
    return {"success": GL.goal_ok(pub["world"], gc["goal"], end), "invalid_attempt": False, "failed_step": None,
            "action_cost": P.plan_cost(pub["spec"], plan), "steps": n, "end_time": t + n}


# ---------------------------------------------------------------------------------------------- request (P2, frozen)

def p2_request(pub, gc, channel=None):
    """P2's request, computed once per base world and goal from the initial operational view at the request time,
    before any delay condition and before any receipt (recovery.needs_verification, budget 2, unchanged)."""
    eng = R.engine_from(pub, channel, "request")
    v = eng.view("current", REQUEST_AT)
    q = R.needs_verification(v, gc["relevant"])
    return {"fields": q[:QUERY_BUDGET], "budget_exhausted": len(q) > QUERY_BUDGET}


# ---------------------------------------------------------------------------------------------- matched loop

def _summary(states, fields):
    return R._summary(states, fields)


def run(pub, gc, request, env_kind, transitions, env, clock, channel=None, tag=""):
    """One goal copy, one environment variant, one clock: one shared engine log, P2 request, receipts and ledger;
    then both projections. pub is public; env is the hidden environment (used only by the sensor service, the
    executor and the scorer)."""
    ctx = f"{pub['episode_id']}|P2_selective|{env_kind}|d{clock['delay']}g{clock['receipt_to_execution_gap']}{tag}"
    declared = transitions if env_kind == "changing" else []
    eng = R.engine_from(pub, channel, ctx)
    base = clock["requested_at"]
    before = eng.view("current", base)
    earlier_before = eng.view("earlier", base, cutoff=base)
    n0, head0 = len(eng.log.entries), eng.log.head()
    queried = list(request["fields"])
    ledger = new_ledger(ctx)
    req, receipts = None, []
    if queried:
        req, receipts = sensor_query(env, ledger, ctx, queried, base, clock["delay"])
        ingest_receipts(eng, ledger, receipts, "q1")
    head_after_receipts = eng.log.head()
    views_before = (eng.view("earlier", base, cutoff=clock["decision_at"]), eng.view("current", clock["decision_at"]))
    actual_m, _ = env.state_at(clock["measured_at"])
    actual_x, applied = env.state_at(clock["execute_at"])
    rel = gc["relevant"]
    valid_x = valid_plans_at(pub, gc, actual_x)
    valid_m = valid_plans_at(pub, gc, actual_m)
    out = {}
    for proj in PROJECTIONS:
        t0 = time.process_time()
        if proj == "carry_forward":
            after = eng.view("current", clock["decision_at"])
            pr = R.project(eng, after, ledger, clock["decision_at"], ctx)
            states, status, max_set = pr["states"], "ok" if pr["states"] else "empty_support", len(pr["states"])
            meta = {"anchors": pr["anchors"], "refused": pr["refused"], "authority_conflicts": pr["authority_conflicts"]}
        else:
            pr = temporal_project(eng, ledger, ctx, declared, clock)
            states, status, max_set = pr["states"], pr["status"], pr["max_set"]
            meta = {"anchors": pr.get("anchors", {}), "refused": pr["refused"],
                    "authority_conflicts": pr["authority_conflicts"], "frontier_sizes": pr["frontier_sizes"],
                    "states_at_base": pr["states_at_base"], "readings": pr["readings"]}
        cpu = time.process_time() - t0
        plan = R.choose(pub, gc, states)
        cls = classify(pub, gc, states)
        res = execute_from(pub, gc, plan, actual_x, clock["execute_at"]) if plan else \
            {"success": False, "invalid_attempt": False, "failed_step": None, "action_cost": 0, "steps": 0,
             "end_time": clock["execute_at"]}
        utility = SUCCESS_REWARD * res["success"] - res["action_cost"] - INVALID_PENALTY * res["invalid_attempt"] - \
            QUERY_COST * len(queried)
        dec = _summary(states, rel)
        in_support = any(all(actual_x.get(f) == v for f, v in s.items()) for s in states)
        out[proj] = {
            "episode_id": pub["episode_id"], "domain": pub["domain"], "env": env_kind, "delay": clock["delay"],
            "gap": clock["receipt_to_execution_gap"], "projection": proj,
            "rule": RULE if proj == "temporal" else ABLATION, "clock": clock,
            "declared_transitions": [t["id"] for t in declared], "queried": queried, "request": req,
            "receipts": receipts, "receipts_sha256": _sha(receipts), "ledger_sha256": _sha(ledger),
            "status": status, "n_states": len(states), "max_set": max_set, "cpu_s": cpu,
            "states": states, "states_sha256": _sha(sorted(_key(s) for s in states)),
            "relevant_support": dec, "uncertain_relevant": [f for f in rel if dec[f] == E.UNKNOWN],
            "candidates": cls, "plan": plan, **res, "utility": utility, "declined": plan is None,
            # hidden-side scoring (never an input to the projection)
            "actual_relevant_at_execute": {f: actual_x.get(f) for f in rel},
            "actual_relevant_at_measure": {f: actual_m.get(f) for f in rel},
            "applied_events": applied, "actual_in_support": in_support,
            "valid_at_execute": valid_x, "valid_at_measure": valid_m, "opportunity": bool(valid_x),
            "missed_opportunity": bool(valid_x) and not res["success"],
            "false_permission": res["invalid_attempt"],
            "log_head": eng.log.head(), "log_unchanged_by_projection": eng.log.head() == head_after_receipts,
            # the pre-request record: the log prefix is untouched and still yields the earlier answer recorded
            # before the request; and neither projection changes any view of the shared log
            "earlier_view_preserved": (eng.log.entries[n0 - 1]["sha"] if n0 else head0) == head0 and
            _prefix(eng, n0).view("earlier", base, cutoff=base) == earlier_before and
            (eng.view("earlier", base, cutoff=clock["decision_at"]), eng.view("current", clock["decision_at"])) == views_before,
            "historical_detail_sha256": _sha(eng.view("current", clock["decision_at"])["detail"]),
            "state_before": dict(before["op_per_field"]), **meta,
        }
    return out
