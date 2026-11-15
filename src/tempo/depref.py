"""V1.14.0 independent selector check (separate from tempo.depquery).

It recomputes S2 with the exhaustive trajectory reference (tempo.freshref.reachable, never freshness.reach or
temporal_project) from the historical support at the origin, no readings, the declared transitions with their
numeric windows and target = selection time; then recomputes R, D, the DEPENDENCY list and the exact RANDOM_EXTRA
subsets and weights from first principles, using only public inputs: the registry, Q0 and the goal's dependency
set. Reference utility never enters a query choice."""
import itertools
from fractions import Fraction

from . import freshref as FREF, recovery as R

ABSENT = "<absent>"


def s2_reference(pub, env_kind, origin, select_at):
    eng = R.engine_from(pub, None, "depref")
    v = eng.view("earlier", origin, cutoff=select_at)
    options = {f: list(o) for f, o in v["op_options"].items()}
    agent = dict(v["agent_state"])
    trs = []
    for tr in (pub["transitions"] if env_kind == "changing" else []):
        w = tr["window"]
        trs.append((tr, w["lo"], min(w["hi"], select_at)))
    return FREF.reachable(pub["spec"], options, agent, [], trs, origin, select_at)


def selection_reference(pub, dep_fields, q0, env_kind, origin, select_at, cap, agent_fields):
    S = s2_reference(pub, env_kind, origin, select_at)
    reg = [f for f in pub["registry_allowed"] if f not in agent_fields]
    rr = []
    for f in reg:
        if f in q0:
            continue
        vals = {s.get(f, ABSENT) for s in S}
        if vals == {ABSENT}:
            continue
        if len(vals) > 1:
            rr.append(f)
    dd = [f for f in reg if f in rr and f in dep_fields]
    add = dd[:max(0, cap - len(q0))]
    subs = list(itertools.combinations(rr, len(add)))
    return {"s2_states": S, "R": rr, "D": dd, "DEPENDENCY": list(q0) + add, "e": len(add),
            "random_subsets": [list(q0) + list(c) for c in subs],
            "random_weight": str(Fraction(1, len(subs)))}
