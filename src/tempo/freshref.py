"""V1.12.0 independent temporal reference (exhaustive; separate from the production projection).

It shares only declarative inputs with the treatment: the domain's predicate table and invariants
(agentstate.actions / violations), goal tests (goals.goal_ok), plan costs (policy.plan_cost) and the public
transition declarations. It never calls freshness.reach, freshness.temporal_project, recovery.guaranteed or
recovery.choose.

Input (all public): the initial support at the base time as per-field option lists plus the declared agent state;
the accepted readings [(field, measured_at, value)]; the transitions with resolved open windows; the base and
target times. Method, different from production's segment closure: enumerate whole trajectories. Every
transition either does not occur or occurs in one elementary gap between consecutive breakpoints (base, reading
times, target) that lies inside its window; within a gap every order of the transitions placed there is tried.
A trajectory is kept only if each placed transition's guard holds at its turn and every reading agrees at its
time (readings at the base time are anchors: they replace that field's initial options). Guards on an absent
field: the effect's fields become absent. The reachable set is the set of end states.
Plan classification: a plan is guaranteed iff it succeeds (every prerequisite's declared reads present and
true, goal holds) in every reachable state, which must be non-empty. Choice: the minimum (cost, key).
"""
import itertools

from . import agentstate as AS, goals as GL, policy as P

ABSENT = None


def _ok_guard(s, g):
    vals = [s.get(f, ABSENT) for f in g]
    if any(v is not ABSENT and v != g[f] for f, v in zip(g, vals)):
        return "false"
    return "true" if all(v is not ABSENT for v in vals) else "unknown"


def reachable(spec, options, agent, readings, transitions, base, target):
    """transitions: [(decl, lo, hi)] with open windows. Returns a sorted list of end states (dicts)."""
    eq = {}
    for r in readings:
        eq.setdefault((r["measured_at"], r["field"]), set()).add(r["value"])
    usable = [(m, f, next(iter(v))) for (m, f), v in eq.items() if len(v) == 1]
    anchor = {f: v for m, f, v in usable if m == base}
    later = sorted({m for m, _, _ in usable if m > base})
    pts = [base] + later + ([target] if target not in later else [])
    pts = sorted(set(pts))
    gaps = list(zip(pts, pts[1:]))
    fields = list(options)
    out = set()
    for combo in itertools.product(*[options[f] for f in fields]):
        s0 = dict(agent, **dict(zip(fields, combo)))
        s0.update(anchor)
        places = []
        for tr, lo, hi in transitions:
            places.append([None] + [i for i, (a, b) in enumerate(gaps) if lo < b and hi > a])
        for assign in itertools.product(*places):
            per_gap = [[transitions[j][0] for j, g in enumerate(assign) if g == i] for i in range(len(gaps))]
            for orders in itertools.product(*[list(itertools.permutations(x)) for x in per_gap]):
                s, ok = dict(s0), True
                for i, (a, b) in enumerate(gaps):
                    for tr in orders[i]:
                        st = _ok_guard(s, tr["guard"])
                        if st == "false":
                            ok = False
                            break
                        if st == "true":
                            s.update(tr["effect"])
                        else:
                            for f in tr["effect"]:
                                s.pop(f, None)
                    if not ok:
                        break
                    for m, f, v in usable:
                        if m == b and m != base and s.get(f, ABSENT) != v:
                            ok = False
                            break
                    if not ok:
                        break
                if ok:
                    if AS.violations(spec, s):
                        raise AssertionError("reference reached an inadmissible state")
                    out.add(tuple(sorted(s.items())))
    return [dict(k) for k in sorted(out)]


def plan_ok(spec, world, goal, plan, s):
    table = AS.actions(spec)
    cur = dict(s)
    for name, *args in plan:
        pre, eff, _ = table[name]
        for _, fn, rd in pre:
            if any(f not in cur for f in rd(*args)) or not fn(cur, *args):
                return False
        if eff:
            cur = eff(cur, *args)
    return GL.goal_field(goal) in cur and GL.goal_ok(world, goal, cur)


def classify(spec, world, goal, plans, states):
    out = {}
    for k, p in plans.items():
        per = [plan_ok(spec, world, goal, p, s) for s in states]
        out[k] = "guaranteed" if per and all(per) else "possible" if any(per) else "impossible"
    return out


def choice(spec, plans, cls):
    good = sorted((P.plan_cost(spec, plans[k]), k) for k, c in cls.items() if c == "guaranteed")
    return good[0][1] if good else None


def reference_for(pub, gc, receipts, transitions, clock, channel=None):
    """The reference answer for one trajectory from public inputs only: the historical support at the base time
    (engine reconstruction from the public reports received by the cutoff; the sensor's log copy is not used),
    the receipts received by the cutoff and measured inside [requested_at, execute_at], and the declared
    transitions with windows (requested_at, execute_at) unless numeric. Returns states, classes and choice."""
    from . import recovery as R  # the historical engine only (not the planner)
    base, cutoff, target = clock["requested_at"], clock["decision_at"], clock["execute_at"]
    eng = R.engine_from(pub, channel, "reference")
    v = eng.view("earlier", base, cutoff=cutoff)
    options = {f: list(o) for f, o in v["op_options"].items()}
    agent = dict(v["agent_state"])
    rd = [r for r in receipts if r["received_at"] <= cutoff and base <= r["measured_at"] <= target]
    trs = []
    for tr in transitions:
        w = tr["window"]
        lo = w["lo"] if "lo" in w else clock[w["from"]]
        hi = min(w["hi"] if "hi" in w else clock[w["to"]], target)
        trs.append((tr, lo, hi))
    states = reachable(pub["spec"], options, agent, rd, trs, base, target)
    cls = classify(pub["spec"], pub["world"], gc["goal"], gc["plans"], states)
    return {"states": states, "classes": cls, "choice": choice(pub["spec"], gc["plans"], cls)}
