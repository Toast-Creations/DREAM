"""V1.13.0 query timing and the cost of waiting (TIMING-v1). Structured input, temporal projection only, zero model calls.

What changed from 1.12.0 (assumptions recorded; 1.12.0 modules are byte-unchanged and imported):
  - The environment no longer follows the controller's clock. One fixed episode origin (absolute DECIDE = 12,
    elapsed 0) and one public activity window 0 < t < 2 (absolute 12 < t < 14) for every schedule; the world is
    declared stable after t = 2 (and at all times in the stable variant). Declarations carry the numeric window
    {"lo": 12, "hi": 14}; the hidden tape fixes events at elapsed 0.5 or 1.5, independent of requests, receipts,
    waiting, actions or declines. Every schedule acts at t >= 2, so no external change happens during a plan.
  - Three fixed schedules share the sensor (reliable, 1 per fact, delivery 2, budget 2), the P2 field list (computed
    once at t = 0 from the initial structured operational view and cloned) and the event tape:
        EARLY       request/measure t=0, receive t=2, decide/first action t=2, pre-action wait 2
        EARLY_WAIT  request/measure t=0, receive t=2, decide/first action t=4, pre-action wait 4
        DEFER       request/measure t=2, receive t=4, decide/first action t=4, pre-action wait 4
    One batch, no retry, no early exit; fees and waiting are paid on declines too.
  - Belief base time is the fixed episode origin for every schedule (never the late request time): the projection
    is freshness.temporal_project (TEMPORAL-OBSERVATION-v1, unchanged) called with base = origin, evidence cutoff =
    the schedule's decision time and target = its action boundary. Readings at the origin anchor (EARLY,
    EARLY_WAIT); DEFER's reading at t = 2 filters the propagated set at its own time (joint states, one-shot
    counts and invariants preserved; a reading of an absent field empties the support, as in 1.12.0).
  - Outcomes distinguish execute (non-empty plan), complete (the empty "already" plan: success iff the actual goal
    holds at the boundary; otherwise a false completion, not an invalid attempt) and decline (no candidate; the
    actual goal truth is reported separately). Selection is tested with `plan is not None`, never truthiness.
  - Utility U_lambda = 10*success - action_cost - 3*invalid - queried_facts - lambda*pre_action_wait;
    primary lambda = 1; sensitivity lambda in LAMBDAS evaluated analytically on the same trajectories.
"""
import copy
import hashlib
import json
import time

from . import agentstate as AS, engine as E, freshness as F, goals as GL, recovery as R

ORIGIN = R.DECIDE  # absolute 12 = elapsed 0
WINDOW = (ORIGIN, ORIGIN + 2)  # public activity window, open
SENSOR_DELAY = 2
SCHEDULES = {"EARLY": {"request": 0, "decide": 2}, "EARLY_WAIT": {"request": 0, "decide": 4},
             "DEFER": {"request": 2, "decide": 4}}
ORDER = ("EARLY", "EARLY_WAIT", "DEFER")
ENVS = ("stable", "changing")
LAMBDAS = (0, 0.25, 0.5, 1, 2)
PRIMARY_LAMBDA = 1
RULE = "TIMING-v1 over TEMPORAL-OBSERVATION-v1 (base = episode origin)"


def _sha(o):
    return hashlib.sha256(json.dumps(o, sort_keys=True, default=str).encode()).hexdigest()


def schedule_clock(name):
    s = SCHEDULES[name]
    q = ORIGIN + s["request"]
    r = q + SENSOR_DELAY
    d = ORIGIN + s["decide"]
    if d < r:
        raise ValueError("decision before receipt")
    return {"schedule": name, "episode_origin": ORIGIN, "offset": ORIGIN, "activity_window": list(WINDOW),
            "requested_at": q, "measured_at": q, "received_at": r, "decision_at": d, "execute_at": d,
            "pre_action_wait": d - ORIGIN,
            "elapsed": {"requested_at": q - ORIGIN, "measured_at": q - ORIGIN, "received_at": r - ORIGIN,
                        "decision_at": d - ORIGIN, "execute_at": d - ORIGIN},
            "ordering": "integer instants: measure < receive < decide < first action; external changes only at "
                        "half-ticks inside the fixed window (12, 14); none after 14"}


def projection_clock(sc):
    """The clock handed to the unchanged 1.12.0 projection, sensor screening, environment and reference: its
    'requested_at' slot is the projection BASE time, here always the episode origin."""
    return {"requested_at": sc["episode_origin"], "measured_at": sc["measured_at"], "received_at": sc["received_at"],
            "decision_at": sc["decision_at"], "execute_at": sc["execute_at"], "offset": sc["offset"],
            "delay": SENSOR_DELAY, "receipt_to_execution_gap": sc["execute_at"] - sc["received_at"]}


def fixed_windows(transitions):
    out = []
    for tr in transitions:
        t = copy.deepcopy(tr)
        t["window"] = {"lo": WINDOW[0], "hi": WINDOW[1]}
        out.append(t)
    return out


def environment(env_ep, env_kind, transitions, tape, sc):
    """The hidden environment (fixed window, fixed tape). Independent of the schedule except for the time at
    which it is queried."""
    trs = transitions if env_kind == "changing" else []
    return F.Environment(env_ep, trs, tape if env_kind == "changing" else [], projection_clock(sc))


def utility(t, lam):
    return t["utility_base"] - lam * t["pre_action_wait"]


def run(pub, gc, request, env_kind, transitions, env_ep, tape, schedule, tag=""):
    """One goal copy, one environment variant, one schedule. pub: public inputs; env_ep / tape: hidden (sensor
    service, executor and scorer only)."""
    sc = schedule_clock(schedule)
    pc = projection_clock(sc)
    declared = transitions if env_kind == "changing" else []
    env = environment(env_ep, env_kind, transitions, tape, sc)
    ctx = f"{pub['episode_id']}|P2_selective|{env_kind}|{schedule}{tag}"
    eng = R.engine_from(pub, None, ctx)
    origin_view = eng.view("current", ORIGIN)
    known_at_measure_before = eng.view("earlier", sc["measured_at"], cutoff=sc["measured_at"])
    n0, head0 = len(eng.log.entries), eng.log.head()
    queried = list(request["fields"])
    ledger = F.new_ledger(ctx)
    req, receipts = None, []
    if queried:
        req, receipts = F.sensor_query(env, ledger, ctx, queried, sc["requested_at"], SENSOR_DELAY)
        F.ingest_receipts(eng, ledger, receipts, "q1")
    head1 = eng.log.head()
    views_before = (eng.view("earlier", ORIGIN, cutoff=sc["decision_at"]), eng.view("current", sc["decision_at"]))
    # a receipt received after the measurement instant must not appear in "what was known at measurement"
    known_at_measure_after = eng.view("earlier", sc["measured_at"], cutoff=sc["received_at"] - 1)
    t0 = time.process_time()
    pr = F.temporal_project(eng, ledger, ctx, declared, pc)
    cpu = time.process_time() - t0
    states = pr["states"]
    plan = R.choose(pub, gc, states)
    cls = F.classify(pub, gc, states)
    actual_x, applied = env.state_at(sc["execute_at"])
    actual_0, _ = env.state_at(ORIGIN)
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
        "rule": RULE, "clock": sc, "projection_clock": pc, "declared_transitions": [x["id"] for x in declared],
        "queried": queried, "request": req, "receipts": receipts, "receipts_sha256": _sha(receipts),
        "ledger_sha256": _sha(ledger), "readings": pr["readings"], "anchors": pr.get("anchors", {}),
        "refused": pr["refused"], "authority_conflicts": pr["authority_conflicts"], "status": pr["status"],
        "frontier_sizes": pr["frontier_sizes"], "max_set": pr["max_set"], "cpu_s": cpu,
        "states": states, "states_sha256": _sha(sorted(F._key(s) for s in states)), "n_states": len(states),
        "relevant_support": dec, "uncertain_relevant": [f for f in rel if dec[f] == E.UNKNOWN],
        "uncertain_queried": [f for f in rel if dec[f] == E.UNKNOWN and f in queried],
        "uncertain_unqueried": [f for f in rel if dec[f] == E.UNKNOWN and f not in queried],
        "candidates": cls, "plan": plan, "selected": selected, "outcome_kind": kind, "empty_plan": empty,
        **res, "goal_true_at_boundary": goal_true,
        "false_completion": kind == "complete" and not res["success"],
        "decline_goal_already_true": kind == "decline" and goal_true,
        "queried_facts": len(queried), "pre_action_wait": sc["pre_action_wait"], "utility_base": u0,
        "utility": {str(l): u0 - l * sc["pre_action_wait"] for l in LAMBDAS},
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
        F._prefix(eng, n0).view("earlier", ORIGIN, cutoff=ORIGIN) == eng.view("earlier", ORIGIN, cutoff=ORIGIN) and
        (eng.view("earlier", ORIGIN, cutoff=sc["decision_at"]), eng.view("current", sc["decision_at"])) == views_before,
        "receipt_absent_before_reception": known_at_measure_after == known_at_measure_before,
        "historical_detail_sha256": _sha(eng.view("current", sc["decision_at"])["detail"]),
        "origin_view_sha256": _sha(origin_view["detail"]),
    }
    return t
