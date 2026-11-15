"""V1.10.0 goal-parameterised candidate plans, goal dependency and the observation-policy loop (deferred goals).

policy.py (V1.9.0/1.9.1) is frozen and unchanged. This module generalises exactly three things it hard-coded:
the goal, the candidate plans, and the relevant-field lookup. Everything else (engine v0.3, the three policies'
rules, the sensor, costs, delay, budget, planner rule, execution and utility) is imported from policy.py or copied
from it line for line, and tests check that goal A on the 1.9.0 and 1.9.1 episodes reproduces policy.run_policy
exactly, field for field.

Goals (public):
  deliver  {"kind": "deliver", "item": E, "place": P}           goal holds iff E.location == P
  fill     {"kind": "fill", "slot": S, "min_rating": m, "part": p}
                                                                 goal holds iff S holds a listed part rated >= m;
                                                                 "part" names the part the candidate plans use.
Candidate plans (the 1.9.x families, parameterised; action definitions unchanged):
  deliver: here (take E at your place), b_cheap / b_dear (fetch E from place B by the direct or the C route),
           each followed by the shortest route to P and "put down E"; plus "already" = [] (the goal holds now).
           E at C has no candidate (the family's declared coverage gap, kept visible as no-plan).
  fill:    install p in S; remove S then install p; order p then install p (only if p has a price);
           plus "already" = [].
  For goal A these are exactly the world's three 1.9.x plans plus "already".

Goal dependency (replaces policy.relevant's literal favoured-field lookup). A field is relevant iff some
candidate plan's step prerequisite, or the goal test after the plan, reads it before the plan itself has
definitely written it. Declared read/write tables (from the printed action rules):
  take E       reads E.location (must be at your place); writes E.location.
               "hands empty" and "your position" are agent-owned: the fixed facts state that you start at a
               listed place with empty hands and do not move unless you act, so they are not stored dynamic facts.
  go A B       reads only your position (agent-owned) and roads (fixed).
  put down E   reads E.location (must be carried); writes E.location.
  install p S  reads p.on_hand and S.part; writes both.
  remove S     reads S.part; writes S.part (the returned part's on_hand is written only conditionally, so a later
               read of it still depends on its prior value).
  order p      reads p.on_hand and every slot field whose publicly allowed values include p ("not installed");
               price is fixed; writes p.on_hand.
  goal         reads the goal field (E.location / S.part) unless the plan definitely wrote it.
Allowed values are those of the public extraction registry. Relevant fields are listed in registry order.
Nothing here reads gold, hidden truth, extraction output or the generator's role labels.
"""
from . import assertions as A, engine as E, policy as P, worlds

DECIDE, QUERY_COST, QUERY_DELAY, QUERY_BUDGET = P.DECIDE, P.QUERY_COST, P.QUERY_DELAY, P.QUERY_BUDGET
SUCCESS_REWARD, INVALID_PENALTY, POLICIES = P.SUCCESS_REWARD, P.INVALID_PENALTY, P.POLICIES


def _steps(path):
    return [["go", path[i], path[i + 1]] for i in range(len(path) - 1)]


def candidate_plans(world, domain, goal):
    if goal["kind"] == "deliver":
        if domain != "delivery":
            raise ValueError("deliver goal outside delivery")
        e, dest = goal["item"], goal["place"]
        you, b, c, roads = world["you"], world["b"], world["c"], world["roads"]
        if dest not in world["places"]:
            raise ValueError("destination not a listed place")
        take, put = [["take", e]], [["put", e]]
        to_dest_from_you = worlds._dijkstra(roads, you, dest)[1]
        to_dest_from_b = worlds._dijkstra(roads, b, dest)[1]
        return {"here": take + _steps(to_dest_from_you) + put,
                "b_cheap": _steps([you, b]) + take + _steps(to_dest_from_b) + put,
                "b_dear": _steps([you, c, b]) + take + _steps(to_dest_from_b) + put,
                "already": []}
    if goal["kind"] == "fill":
        if domain != "assembly":
            raise ValueError("fill goal outside assembly")
        p, s = goal["part"], goal["slot"]
        out = {"install": [["install", p, s]], "remove_install": [["remove", s], ["install", p, s]]}
        if p in world.get("prices", {}) or (p == world.get("g") and "price" in world):
            out["order_install"] = [["order", p], ["install", p, s]]
        out["already"] = []
        return out
    raise ValueError(goal)


def goal_field(goal):
    return f"{goal['item']}.location" if goal["kind"] == "deliver" else f"{goal['slot']}.part"


def goal_ok(world, goal, s):
    if goal["kind"] == "deliver":
        return s.get(f"{goal['item']}.location") == goal["place"]
    p = s.get(f"{goal['slot']}.part")
    return p not in (None, worlds.EMPTY) and world["parts"].get(p, {}).get("rating", -1) >= goal["min_rating"]


def plan_reads(plan, goal, allowed):
    written, reads = set(), []

    def read(f):
        if f not in written and f not in reads:
            reads.append(f)
    for name, *args in plan:
        if name in ("take", "put"):
            f = f"{args[0]}.location"
            read(f); written.add(f)
        elif name == "go":
            pass
        elif name == "install":
            p, s = args
            read(f"{p}.on_hand"); read(f"{s}.part"); written |= {f"{p}.on_hand", f"{s}.part"}
        elif name == "remove":
            read(f"{args[0]}.part"); written.add(f"{args[0]}.part")
        elif name == "order":
            p = args[0]
            read(f"{p}.on_hand")
            for f, vals in allowed.items():
                if f.endswith(".part") and p in vals:
                    read(f)
            written.add(f"{p}.on_hand")
        else:
            raise ValueError(f"no read table for {name}")
    read(goal_field(goal))
    return reads


def relevant_fields(plans, goal, allowed):
    """allowed: the public registry {field: allowed values} (its key order is the registry order)."""
    rel = set()
    for p in plans.values():
        rel |= set(plan_reads(p, goal, allowed))
    order = list(allowed)
    missing = rel - set(order)
    if missing:
        raise AssertionError(f"relevant fields outside the public registry: {sorted(missing)}")
    return [f for f in order if f in rel]


def context(world, domain, goal, allowed):
    plans = candidate_plans(world, domain, goal)
    return {"goal": goal, "plans": plans, "relevant": relevant_fields(plans, goal, allowed)}


def goal_a_of(ep):
    """The 1.9.x episode's own goal (for parity tests)."""
    w = ep["world"]
    if ep["domain"] == "delivery":
        return {"kind": "deliver", "item": w["goal"]["item"], "place": w["goal"]["place"]}
    return {"kind": "fill", "slot": w["goal"]["slot"], "min_rating": w["goal"]["min_rating"], "part": w["g"]}


# ------------------------------------------------------------------ planner and environment (policy.py, goal-generic)

def guaranteed(eng, branch, world, goal, plan):
    head = eng.log.head()
    for s in branch.states:
        cur = E.Branch([s], branch.base_version)
        for step in plan:
            if eng.check_action(cur, list(step))["verdict"] != "allowed":
                return False
            cur = eng.predict_action(cur, list(step))
        if not goal_ok(world, goal, cur.states[0]):
            return False
    assert eng.log.head() == head, "planning changed the log"
    return True


def choose(eng, t, ep, gc):
    b = eng.branch(t)
    b.conflicts = eng.view("current", t)["conflict_fields"]
    good = [(P.plan_cost(ep["spec"], p), k) for k, p in gc["plans"].items()
            if guaranteed(eng, b, ep["world"], gc["goal"], p)]
    return min(good)[1] if good else None


def true_valid_plans(ep, gc):
    out = []
    env = E.Engine(ep["spec"])
    for k, p in gc["plans"].items():
        s, ok = dict(ep["truth"]), True
        for step in p:
            _, allowed, eff = env._eval(s, list(step))
            if not allowed:
                ok = False
                break
            s = eff(s, *step[1:])
        if ok and goal_ok(ep["world"], gc["goal"], s):
            out.append(k)
    return out


def execute(ep, gc, plan_key, t):
    env = E.Engine(ep["spec"])
    s = dict(ep["truth"])
    cost, steps = 0, 0
    for step in gc["plans"][plan_key]:
        _, allowed, eff = env._eval(s, list(step))
        steps += 1
        if not allowed:
            return {"success": False, "invalid_attempt": True, "failed_step": list(step), "action_cost": cost,
                    "steps": steps, "end_time": t + steps}
        s = eff(s, *step[1:])
        cost += P.step_cost(ep["spec"], step)
    return {"success": goal_ok(ep["world"], gc["goal"], s), "invalid_attempt": False, "failed_step": None,
            "action_cost": cost, "steps": steps, "end_time": t + steps}


def run_policy(ep, gc, policy, channel=None, tag=""):
    """policy.run_policy with the goal context gc = {"goal", "plans", "relevant"} in place of the episode's fixed
    goal, plans and relevant fields. Same keys and the same values for goal A.
    Amendment S1 (after smoke, before main): "unresolved_decline" reads a relevant field's status with .get, so a
    relevant field the text channel never described (absent from the view) counts as not unknown instead of
    raising KeyError (policy.run_policy has the same lookup; 1.9.x never reached it). No value changes otherwise."""
    eng = P.engine_from(ep, channel, f"{ep['episode_id']}|{policy}{tag}")
    t = DECIDE
    before = eng.view("current", t)
    earlier_before = eng.view("earlier", t, cutoff=DECIDE)
    pre_plan = choose(eng, t, ep, gc)
    rel = gc["relevant"]
    queried = []
    if policy == "P1_always":
        queried = list(rel)
    elif policy == "P2_selective":
        queried = P.needs_verification(eng, t, rel)
    budget_exhausted = len(queried) > QUERY_BUDGET
    queried = queried[:QUERY_BUDGET]
    if queried:
        eng.ingest({"rid": "q1", "received_at": t + QUERY_DELAY, "status": "verified", "type": "state",
                    "source": "sensor", "assertions": [{"field": f, "at": t, "value": ep["truth"][f]} for f in queried]})
        t += QUERY_DELAY
    after = eng.view("current", t)
    plan = choose(eng, t, ep, gc)
    valid = true_valid_plans(ep, gc)
    res = execute(ep, gc, plan, t) if plan else {"success": False, "invalid_attempt": False, "failed_step": None,
                                                   "action_cost": 0, "steps": 0, "end_time": t}
    belief_ok = lambda v: all(v["per_field"].get(f) == ep["truth"][f] for f in rel)
    utility = SUCCESS_REWARD * res["success"] - res["action_cost"] - INVALID_PENALTY * res["invalid_attempt"] - \
        QUERY_COST * len(queried)
    return {"episode_id": ep["episode_id"], "domain": ep["domain"], "type": ep["type"], "policy": policy,
            "queried": queried, "pre_query_plan": pre_plan, "plan": plan, **res, "utility": utility,
            "opportunity": bool(valid), "true_valid_plans": valid,
            "declined": plan is None, "false_block": plan is None and bool(valid),
            "missed_opportunity": bool(valid) and not res["success"],
            "unresolved_decline": plan is None and any(before["detail"].get(f, {}).get("status") == "unknown" for f in rel)
            and not queried,
            "belief_correct_before": belief_ok(before), "belief_correct_at_decision": belief_ok(after),
            "belief_changed_by_query": bool(queried) and any(before["per_field"].get(f) != after["per_field"].get(f)
                                                              for f in rel),
            "plan_changed_by_query": bool(queried) and pre_plan != plan,
            "suspended": sorted({s for d in after["detail"].values() for s in d["suspended"]}),
            "earlier_view_preserved": eng.view("earlier", DECIDE, cutoff=DECIDE) == earlier_before,
            "delay": res["end_time"] - DECIDE, "log_reports": len(eng.reports()), "budget_exhausted": budget_exhausted,
            "relevant_status_before": {f: (before["detail"].get(f, {}).get("status"), f in before["incomplete_fields"],
                                           bool(before["detail"].get(f, {}).get("provisional_support")))
                                       for f in rel},
            "relevant_status_at_decision": {f: after["per_field"].get(f, "missing") for f in rel},
            "conflict_at_decision": [f for f in rel if f in after["conflict_fields"]],
            "incomplete_at_decision": [f for f in rel if f in after["incomplete_fields"]],
            # added in 1.10.0 (not in policy.run_policy): whole declared-state view before any query
            "state_before": dict(before["per_field"]), "conflict_before": list(before["conflict_fields"]),
            "incomplete_before": list(before["incomplete_fields"])}


PARITY_EXTRA = ("state_before", "conflict_before", "incomplete_before")
