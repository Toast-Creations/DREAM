"""V1.9.0 closed-loop observation-policy test on structured public reports (no language model).

Episode: one world (delivery or assembly), six public contract-v1 reports received by the decision time DECIDE=12,
a hidden true state (environment only), the world's three candidate plans and its goal. Exactly one decision per
episode: execute one plan or decline. The world is stable after DECIDE (no exogenous events): declared, not assumed
away silently. Policies differ only in observation.

  P0 accepted evidence : plan from the current accepted (supported) state.
  P1 always verify     : query every relevant field, then plan.
  P2 selective verify  : query exactly the relevant fields whose supported value is unknown, depends on provisional
                         evidence (assertions.resolve_field "provisional_support"), is incomplete, or is in
                         conflict; otherwise plan directly. The test is on the evidence, not on whether the plan
                         would be authorised, so blocked opportunities are reconsidered as well as permissions.
Relevant fields (fixed): delivery = the goal crate's location; assembly = the goal slot's content and the goal part's
stock. (Hands, roads, connectors and prices are verified fixed facts.)

Observation service: a reliable current-state sensor. A query batch at time t returns, for each requested field,
its true value at t as one verified state report (rid qN, about time t, received at t + QUERY_DELAY). It reveals
nothing else (no other field, no history). Cost QUERY_COST per field; at most QUERY_BUDGET fields per episode.

Planner (common to all policies): the cheapest candidate plan that is allowed at every step and reaches the goal in
every compatible state of the belief (engine v0.3 check/predict on branches); none -> decline.
Execution (environment): steps run on the hidden state with the same action rules; the first step whose
prerequisite fails is an invalid attempt and ends the episode with no effect from that step; each executed step
takes one time unit.

Utility (fixed before any episode): U = SUCCESS_REWARD * success - executed action cost - INVALID_PENALTY *
invalid_attempts - QUERY_COST * fields queried.
"""
import copy
import hashlib
import random

from . import assertions as A, engine as E, engine_fixtures as EF, generate as G, worlds
from .worlds import EMPTY, NO, YES

DECIDE = 12
QUERY_COST = 1
QUERY_DELAY = 1
QUERY_BUDGET = 2
SUCCESS_REWARD = 10
INVALID_PENALTY = 3
N_REPORTS = 6
TYPES = ["false_block", "false_permission", "provisional_correct", "verified_settled", "unresolved", "no_plan",
         "corrected"]
ALLOC = {"false_block": 2, "false_permission": 2, "provisional_correct": 2, "verified_settled": 2, "unresolved": 2,
         "no_plan": 1, "corrected": 1}
POLICIES = ("P0_accepted", "P1_always", "P2_selective")
CONS = {"policy": "cjvwy", "policydev": "fhlnprs", "textpol": "bdgkmtz", "textpolsmoke": "fhlnprs"}


class Names4:
    def __init__(self, pool, rng):
        self.rng, self.cons, self.used = rng, CONS[pool], set()

    def word(self):
        while True:
            w = "".join(self.rng.choice(self.cons) + self.rng.choice(worlds.VOWELS) for _ in range(4)).capitalize()
            if w not in self.used:
                self.used.add(w)
                return w


def relevant(w):
    return [w.focal] if w.domain == "delivery" else [w.slot_f, w.stock_f]


R = G.R


def _base(w, etype, rng):
    """(v0.2-style base records, accepted relevant values, true relevant values)."""
    if w.domain == "delivery":
        F, you, b, c = w.focal, w.you, w.b, w.c
        others = {w.side: rng.choice(w.places), f"{w.z}.location": rng.choice(w.places)}
        init = lambda val, status: R("initial", 0, 0, {"assign": {F: val, **others}}, status=status, key="init")
        if etype == "false_block":
            truth = rng.choice([you, b]); return [init(c, "provisional")], {F: c}, {F: truth}
        if etype == "false_permission":
            acc = rng.choice([you, b]); return [init(acc, "provisional")], {F: acc}, {F: b if acc == you else you}
        if etype == "provisional_correct":
            v = rng.choice([you, b]); return [init(v, "provisional")], {F: v}, {F: v}
        if etype == "verified_settled":
            v = rng.choice([you, b])
            return [init(c, "verified"), R("change", 5, 5, {"field": F, "from": c, "to": v})], {F: v}, {F: v}
        if etype == "unresolved":
            v = rng.choice([you, b])
            return [init(c, "verified"), R("uncertain_change", 3, 3, {"field": F, "from": c, "options": [you, b]})], \
                {F: "unknown"}, {F: v}
        if etype == "no_plan":
            return [init(c, "verified")], {F: c}, {F: c}
        if etype == "corrected":
            u = rng.choice([you, b]); v = b if u == you else you
            return [init(u, "provisional"), R("correction", None, 6, {"target": "init", "field": F, "value": v,
                                                                       "valid_from": 0, "valid_to": None})], {F: v}, {F: v}
    T, S_ = w.slot_f, w.stock_f
    others = {w.side: rng.choice([EMPTY, w.e, w.e2]), f"{w.d}.on_hand": rng.choice([YES, NO])}
    init = lambda t, s, status: R("initial", 0, 0, {"assign": {T: t, S_: s, **others}}, status=status, key="init")
    if etype == "false_block":
        if rng.random() < 0.5:
            return [init(w.w, NO, "provisional")], {T: w.w, S_: NO}, {T: w.w, S_: YES}
        return [init(w.w, NO, "provisional")], {T: w.w, S_: NO}, {T: EMPTY, S_: NO}
    if etype == "false_permission":
        if rng.random() < 0.5:
            return [init(EMPTY, YES, "provisional")], {T: EMPTY, S_: YES}, {T: w.w, S_: YES}
        return [init(EMPTY, NO, "provisional")], {T: EMPTY, S_: NO}, {T: EMPTY, S_: YES}
    if etype == "provisional_correct":
        t, s = rng.choice([(EMPTY, YES), (w.w, YES), (EMPTY, NO)])
        return [init(t, s, "provisional")], {T: t, S_: s}, {T: t, S_: s}
    if etype == "verified_settled":
        return [init(w.w, NO, "verified"), R("change", 5, 5, {"field": S_, "from": NO, "to": YES})], \
            {T: w.w, S_: YES}, {T: w.w, S_: YES}
    if etype == "unresolved":
        v = rng.choice([EMPTY, w.w])
        return [init(EMPTY, YES, "verified"), R("uncertain_change", 3, 3, {"field": T, "from": EMPTY,
                                                                           "options": [EMPTY, w.w]})], \
            {T: "unknown", S_: YES}, {T: v, S_: YES}
    if etype == "no_plan":
        return [init(w.w, NO, "verified")], {T: w.w, S_: NO}, {T: w.w, S_: NO}
    if etype == "corrected":
        return [init(EMPTY, YES, "provisional"), R("correction", None, 6, {"target": "init", "field": T, "value": w.w,
                                                                            "valid_from": 0, "valid_to": None})], \
            {T: w.w, S_: YES}, {T: w.w, S_: YES}
    raise ValueError(etype)


def build_episode(eid, domain, etype, seed, pool):
    return build_episode_world(eid, domain, etype, seed, pool)[1]


def build_episode_world(eid, domain, etype, seed, pool):
    """(world object, episode dict); the episode dict is exactly build_episode's."""
    rng = random.Random(seed)
    names = Names4(pool, rng)
    w = worlds.make_world(domain, rng, names, "slot" if domain == "assembly" else None)
    base, accepted, truth_rel = _base(w, etype, rng)
    chains = G.padding_chains(w, rng, N_REPORTS)
    recs = G.finalize(base + copy.deepcopy(G.take_padding(chains, N_REPORTS - len(base))))
    G.check_no_ties(recs)
    if any(r["received_at"] > DECIDE for r in recs):
        raise AssertionError("report after the decision time")
    reports = [A.from_v02(EF.public_record(r)) for r in recs]
    spec = EF.spec_from_world(vars(w), domain, recs)
    eng = A.AssertionEngine(spec, eid)
    for r in reports:
        eng.ingest(r)
    view = eng.view("current", DECIDE)
    for f, v in accepted.items():
        if view["per_field"][f] != v:
            raise AssertionError(f"accepted {f} = {view['per_field'][f]}, intended {v}")
    truth = {f: v for f, v in view["per_field"].items() if v not in ("unknown", "conflict")}
    truth.update(truth_rel)
    if domain == "delivery":
        truth["agent.at"] = w.you
    world = {k: v for k, v in vars(w).items() if k != "pad_names"}
    return w, {"episode_id": eid, "domain": domain, "type": etype, "seed": seed, "pool": pool, "world": world,
               "spec": spec, "reports": reports, "records_v02": recs, "relevant": relevant(w), "truth": truth,
               "accepted_relevant": accepted}


def episode_specs(pool, base_seed):
    out = []
    for domain in ("delivery", "assembly"):
        n = 0
        for etype in TYPES:
            for j in range(ALLOC[etype]):
                eid = f"{pool}-{domain[:3]}-{etype}-{j}"
                out.append((eid, domain, etype, int(hashlib.sha256(f"{base_seed}|{eid}".encode()).hexdigest()[:12], 16)))
                n += 1
        assert n == 12
    return out


# ------------------------------------------------------------------ planner and environment

def step_cost(spec, step):
    if step[0] == "go":
        return next(c for a, b, c in spec["roads"] if {a, b} == {step[1], step[2]})
    return {"take": 1, "put": 1, "install": 2, "remove": 1, "order": spec.get("prices", {}).get(step[1], 0)}[step[0]]


def plan_cost(spec, plan):
    return sum(step_cost(spec, s) for s in plan)


def goal_ok(world, domain, s):
    if domain == "delivery":
        return s.get(f"{world['goal']['item']}.location") == world["goal"]["place"]
    p = s.get(f"{world['goal']['slot']}.part")
    return p not in (None, EMPTY) and world["parts"].get(p, {}).get("rating", -1) >= world["goal"]["min_rating"]


def guaranteed(eng, branch, world, domain, plan):
    head = eng.log.head()
    for s in branch.states:
        cur = E.Branch([s], branch.base_version)
        for step in plan:
            if eng.check_action(cur, list(step))["verdict"] != "allowed":
                return False
            cur = eng.predict_action(cur, list(step))
        if not goal_ok(world, domain, cur.states[0]):
            return False
    assert eng.log.head() == head, "planning changed the log"
    return True


def choose(eng, t, ep):
    b = eng.branch(t)
    b.conflicts = eng.view("current", t)["conflict_fields"]
    good = [(plan_cost(ep["spec"], p), k) for k, p in ep["world"]["plans"].items()
            if guaranteed(eng, b, ep["world"], ep["domain"], p)]
    return min(good)[1] if good else None


def true_valid_plans(ep):
    out = []
    env = E.Engine(ep["spec"])
    for k, p in ep["world"]["plans"].items():
        s, ok = dict(ep["truth"]), True
        for step in p:
            _, allowed, eff = env._eval(s, list(step))
            if not allowed:
                ok = False
                break
            s = eff(s, *step[1:])
        if ok and goal_ok(ep["world"], ep["domain"], s):
            out.append(k)
    return out


def execute(ep, plan_key, t):
    env = E.Engine(ep["spec"])
    s = dict(ep["truth"])
    cost, steps = 0, 0
    for step in ep["world"]["plans"][plan_key]:
        _, allowed, eff = env._eval(s, list(step))
        steps += 1
        if not allowed:
            return {"success": False, "invalid_attempt": True, "failed_step": list(step), "action_cost": cost,
                    "steps": steps, "end_time": t + steps}
        s = eff(s, *step[1:])
        cost += step_cost(ep["spec"], step)
    return {"success": goal_ok(ep["world"], ep["domain"], s), "invalid_attempt": False, "failed_step": None,
            "action_cost": cost, "steps": steps, "end_time": t + steps}


def needs_verification(eng, t, fields):
    v = eng.view("current", t)
    out = []
    for f in fields:
        d = v["detail"].get(f, {"status": "not_yet_described"})
        if d["status"] in ("unknown", "conflict", "not_yet_described") or d.get("provisional_support") or \
                f in v["incomplete_fields"] or v["context_incomplete"]:
            out.append(f)
    return out


def engine_from(ep, channel=None, context="ctx"):
    """channel None: the structured public reports. Otherwise {"reports": [...], "pending": [...]} produced by an
    input channel (e.g. text extraction); pending entries are registered as unprocessed evidence."""
    eng = A.AssertionEngine(ep["spec"], context)
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


def run_policy(ep, policy, channel=None):
    eng = engine_from(ep, channel, f"{ep['episode_id']}|{policy}")
    t = DECIDE
    before = eng.view("current", t)
    earlier_before = eng.view("earlier", t, cutoff=DECIDE)
    pre_plan = choose(eng, t, ep)
    queried = []
    if policy == "P1_always":
        queried = list(ep["relevant"])
    elif policy == "P2_selective":
        queried = needs_verification(eng, t, ep["relevant"])
    budget_exhausted = len(queried) > QUERY_BUDGET
    queried = queried[:QUERY_BUDGET]
    if queried:
        eng.ingest({"rid": "q1", "received_at": t + QUERY_DELAY, "status": "verified", "type": "state",
                    "source": "sensor", "assertions": [{"field": f, "at": t, "value": ep["truth"][f]} for f in queried]})
        t += QUERY_DELAY
    after = eng.view("current", t)
    plan = choose(eng, t, ep)
    valid = true_valid_plans(ep)
    res = execute(ep, plan, t) if plan else {"success": False, "invalid_attempt": False, "failed_step": None,
                                               "action_cost": 0, "steps": 0, "end_time": t}
    rel = ep["relevant"]
    belief_ok = lambda v: all(v["per_field"].get(f) == ep["truth"][f] for f in rel)
    utility = SUCCESS_REWARD * res["success"] - res["action_cost"] - INVALID_PENALTY * res["invalid_attempt"] - \
        QUERY_COST * len(queried)
    return {"episode_id": ep["episode_id"], "domain": ep["domain"], "type": ep["type"], "policy": policy,
            "queried": queried, "pre_query_plan": pre_plan, "plan": plan, **res, "utility": utility,
            "opportunity": bool(valid), "true_valid_plans": valid,
            "declined": plan is None, "false_block": plan is None and bool(valid),
            "missed_opportunity": bool(valid) and not res["success"],
            "unresolved_decline": plan is None and any(before["detail"][f]["status"] == "unknown" for f in rel)
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
            "incomplete_at_decision": [f for f in rel if f in after["incomplete_fields"]]}
