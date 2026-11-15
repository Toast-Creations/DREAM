"""V1.14.0 dependency-aware query selection at a fixed deferred clock (DEPQUERY-v1). Structured input, temporal
projection only, zero model calls.

Unchanged and imported (byte-identical to 1.13.0): the TIMING-v1 DEFER clock and trajectory runner (timing.run with
schedule "DEFER": select just before a batch measured at t = 2, delivery and decision/action at t = 4, pre-action
wait 4 for every arm, including zero-query arms and declines), TEMPORAL-OBSERVATION-v1 (freshness.temporal_project,
base = episode origin), the reliable sensor (cost 1 per fact), P2's frozen field rule (freshness.p2_request at t = 0,
cap 2), the shared dependency table (recovery.context -> agentstate.plan_reads over the unchanged candidate menus),
the cheapest-guaranteed-candidate planner, the executor and the utility
    U = 10*success - action_cost - 3*invalid - queried_facts - 1*pre_action_wait.

New here: which fields are measured in the single t = 2 batch.

PUBLIC INPUTS TO THE SELECTOR (never the hidden truth, tape, case labels or generator records)
  S2   the pre-query supported-state set at elapsed t = 2: TEMPORAL-OBSERVATION-v1 over the public reports and the
       declared transitions with base = origin, evidence cutoff = origin + 2, target = origin + 2, and an empty
       sensor ledger (no receipts exist before the batch).
  Q0   P2's original list (t = 0, initial operational view, frozen order, cap 2). May be empty.
  REG  the public sensor registry: the entity fields of the public extraction registry (registry_allowed), in its
       key order, each with a finite declared value list. Agent state (agent.at / agent.hands) is declared, not
       sensed, and is not queryable.
  R    fields of REG outside Q0 whose represented values vary across S2 (a field absent from some but not all
       S2 states counts as varying and is flagged "partially_represented"; a field absent from every S2 state is
       flagged "unrepresented" and is not in R). Computed over the whole context, including other-goal facts.
  G    the current goal's dependency set (recovery.context(...)["relevant"]; the planner's own read table).
  D    R intersected with G, in registry order.
An empty S2 is reported (status "empty_support"); the selector then keeps Q0 and appends nothing.

SELECTORS (one batch at t = 2, cap 2 facts in total)
  BASE          exactly Q0 (no request if Q0 is empty).
  DEPENDENCY    Q0 followed by the first fields of D until D is exhausted or the cap is reached; e = number
                appended. Q0 is never replaced; no condition on expected answers, cost or redundancy.
  RANDOM_EXTRA  Q0 plus exactly e fields drawn uniformly without replacement from R: every e-subset of R
                (itertools.combinations in registry order) is executed and weighted 1 / C(|R|, e). e = 0 -> the
                BASE outcome (weight 1). One eligible subset -> identical to DEPENDENCY (reported as a tie).
"""
import itertools
import math

from . import freshness as F, recovery as R, timing as TM

RULE = "DEPQUERY-v1 over TIMING-v1 DEFER (TEMPORAL-OBSERVATION-v1, base = episode origin)"
SELECT_AT = TM.ORIGIN + TM.SCHEDULES["DEFER"]["request"]  # absolute 14 = elapsed 2
CAP = F.QUERY_BUDGET
ARMS = ("BASE", "DEPENDENCY", "RANDOM_EXTRA")
SCHEDULE = "DEFER"


def s2_clock():
    """Clock for the pre-query projection: base origin, cutoff and target = the selection time (t = 2)."""
    return {"requested_at": TM.ORIGIN, "measured_at": TM.ORIGIN, "received_at": TM.ORIGIN, "decision_at": SELECT_AT,
            "execute_at": SELECT_AT, "offset": TM.ORIGIN, "delay": 0, "receipt_to_execution_gap": 0}


def sensor_registry(pub):
    """The public queryable fields: registry entity fields in registry order with their finite value lists."""
    from . import agentstate as AS
    ag = set(AS.agent_fields(pub["spec"]))
    out = {}
    for f, vals in pub["registry_allowed"].items():
        if f in ag:
            continue
        out[f] = list(vals)
    return out


def s2_support(pub, env_kind, context="select"):
    """S2 from public inputs only (no receipts). Returns the projection record."""
    declared = pub["transitions"] if env_kind == "changing" else []
    eng = R.engine_from(pub, None, f"{context}|S2|{env_kind}")
    ledger = F.new_ledger(f"{context}|S2|{env_kind}")
    return F.temporal_project(eng, ledger, f"{context}|S2|{env_kind}", declared, s2_clock())


def varying(states, reg):
    """(R-candidates in registry order, partially_represented, unrepresented) over a state set."""
    vary, partial, unrep = [], [], []
    for f in reg:
        present = [s for s in states if f in s]
        if not present:
            unrep.append(f)
            continue
        if len(present) < len(states):
            partial.append(f)
            vary.append(f)
            continue
        if len({s[f] for s in present}) > 1:
            vary.append(f)
    return vary, partial, unrep


def select(q0, states, reg, dep_fields, status="ok", cap=CAP):
    """The frozen rule on public inputs. Returns the selection record (no answers, no truth)."""
    q0 = list(q0)
    if status != "ok" or not states:
        vary, partial, unrep = [], [], list(reg)
        rr, dd = [], []
    else:
        vary, partial, unrep = varying(states, reg)
        rr = [f for f in vary if f not in q0]
        dd = [f for f in rr if f in dep_fields]
    room = max(0, cap - len(q0))
    add = dd[:room]
    e = len(add)
    subs = [list(c) for c in itertools.combinations(rr, e)] if e else [[]]
    if e and len(subs) != math.comb(len(rr), e):
        raise AssertionError("subset enumeration")
    return {"rule": RULE, "Q0": q0, "R": rr, "G": list(dep_fields), "D": dd, "spare_capacity": room, "e": e,
            "added": add, "fields": {"BASE": q0, "DEPENDENCY": q0 + add},
            "random_subsets": [q0 + s for s in subs], "random_added": subs,
            "random_weight": 1 / len(subs), "random_pool_size": len(rr), "n_random_subsets": len(subs),
            "random_tie_with_dependency": len(subs) == 1, "partially_represented": partial, "unrepresented": unrep,
            "s2_status": status if states else "empty_support", "s2_size": len(states)}


def selection_for(pub, gc, q0, env_kind):
    pr = s2_support(pub, env_kind, pub["episode_id"])
    reg = sensor_registry(pub)
    sel = select(q0, pr["states"], reg, gc["relevant"], pr["status"])
    S = pr["states"]
    sel.update(s2_states=S, s2_uncertain={f: sorted({s.get(f, "<absent>") for s in S}) for f in sel["R"] + list(q0)
                                          if f in reg},
               s2_max_set=pr["max_set"], registry=list(reg))
    return sel


def run_arm(pub, gc, fields, env_kind, env_ep, tape, tag):
    """One trajectory at the fixed DEFER clock with the given field list (timing.run, unchanged)."""
    return TM.run(pub, gc, {"fields": list(fields)}, env_kind, pub["transitions"], env_ep, tape, SCHEDULE, tag=tag)


def u1(t):
    return t["utility"][str(TM.PRIMARY_LAMBDA)]
