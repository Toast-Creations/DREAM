"""V1.11.0 explicit agent state, declared physical invariants and one shared predicate table.

Why (found in V1.10.0, del-corrected-0 under goal A): engine v0.2/v0.3 derived "your hands are empty" from every
crate's location, while the declared relevance rule treated hands as a fixed agent-owned fact and the validation
sampler left out "carried by you". The three components therefore disagreed about the state space the executor can
receive from extraction. This module replaces the implicit derivation with explicit agent state and declared
invariants, and every component (action applicability and successors, the engine's compatible states and widening,
plan relevance, validation sampling, the executor) reads the same definitions from here.

Agent state (delivery only; assembly has none):
  agent.at     your position. Declared by the fixed facts ("You are at P ... You do not move unless you act").
  agent.hands  "empty" or the name of the one crate you hold. Declared by the fixed facts ("with empty hands").
  Both are facts of the declared pre-action history, not permanent constants: "take X" sets agent.hands = X, "put
  down X" restores "empty", "go" changes agent.at. Before your first action (the whole pre-decision phase, which
  contains no action of yours) they equal their declared values. AgentStateEngine refuses to build a view after
  an executed action is in its log, so that restriction cannot be applied outside its phase.

Declared physical invariants (from the printed rules; each constrains one entity field plus agent fields):
  carry_link      for every crate X: X.location == "carried by you"  <=>  agent.hands == X.
                  ("You can carry only one item at a time"; an item is at a place only while it rests there.)
                  With agent.hands declared "empty", no crate can be carried before your first action. An
                  assertion that one is carried is then a *diagnosable inconsistency* with the declared fact: the
                  assertion and its provenance are kept, the field is an "invariant_conflict", and the declared
                  agent state is not changed to fit it.
  slot_connector  a slot holds nothing or a part whose connector equals the slot's (no adapters exist in these
                  episodes; "Installation uses the printed native connector types").
Admissible state = satisfies every invariant. Because each invariant's scope is one entity field plus agent fields,
joint admissibility given the agent state equals per-field admissibility (checked in validation).

Predicate table: every action prerequisite is (name, test(state, *args), reads(*args)); every action has an effect
and a definite write set. Relevance (plan_reads) walks the same table. Validation checks empirically that each
prerequisite's value never changes when a field outside its declared reads changes (on admissible states).
"""
import itertools

from . import assertions as A, engine as E
from .engine import CARRIED, EMPTY, NO, YES

AT, HANDS, FREE = "agent.at", "agent.hands", "empty"
INVARIANT_VERSION = "agent-invariants-v1"


# ---------------------------------------------------------------------------------------------- agent state

def agent_fields(spec):
    spec = _spec(spec)
    return [AT, HANDS] if spec.domain == "delivery" else []


def declared_agent_state(spec):
    """The agent state the fixed facts declare for the pre-action phase."""
    spec = _spec(spec)
    return {AT: spec.agent_at, HANDS: FREE} if spec.domain == "delivery" else {}


def agent_domain(spec, f):
    spec = _spec(spec)
    if f == AT:
        return list(spec.places)
    if f == HANDS:
        return [FREE] + sorted(c for c, t in spec.registry.items() if t == "crate")
    raise KeyError(f)


def _spec(spec):
    return spec if isinstance(spec, E.WorldSpec) else E.WorldSpec(spec)


def entity_fields(spec):
    spec = _spec(spec)
    return [f"{e}.{spec.ATTR[t]}" for e, t in spec.registry.items()]


def domain(spec, f):
    """The full value domain the engine accepts for a field (all phases)."""
    spec = _spec(spec)
    return agent_domain(spec, f) if f in (AT, HANDS) else spec.domain_values(f)


# ---------------------------------------------------------------------------------------------- invariants

def _accepts(spec, slot):
    a = spec.fitted.get(slot)
    return spec.adapters[a]["from"] if a else spec.slots[slot]


def violations(spec, s):
    """Invariant violations of a (possibly partial) state: list of (rule, field). Fields absent from s are not
    checked (nothing is assumed about them)."""
    spec = _spec(spec)
    out = []
    if spec.domain == "delivery":
        hands = s.get(HANDS)
        for c, t in spec.registry.items():
            if t != "crate":
                continue
            f = f"{c}.location"
            if f in s and hands is not None and (s[f] == CARRIED) != (hands == c):
                out.append(("carry_link", f))
    else:
        for sl in spec.slots:
            f = f"{sl}.part"
            v = s.get(f)
            if v is not None and v != EMPTY and (v not in spec.parts or spec.parts[v]["type"] != _accepts(spec, sl)):
                out.append(("slot_connector", f))
    return out


def admissible(spec, s):
    return not violations(spec, s)


def admissible_values(spec, f, agent=None):
    """Values of entity field f that are admissible given the agent state (None: any agent state, i.e. the
    phase-independent domain)."""
    spec = _spec(spec)
    vals = spec.domain_values(f)
    if agent is None:
        return [v for v in vals if any(admissible(spec, dict(a, **{f: v})) for a in _agent_states(spec))]
    return [v for v in vals if admissible(spec, dict(agent, **{f: v}))]


def _agent_states(spec):
    fs = agent_fields(spec)
    if not fs:
        return [{}]
    return [dict(zip(fs, c)) for c in itertools.product(*[agent_domain(spec, f) for f in fs])]


# ---------------------------------------------------------------------------------------------- predicate table

def actions(spec):
    """name -> (prerequisites [(name, test(state, *args), reads(*args))], effect(state, *args), writes(*args)).
    Same printed rules as engine._actions; the only change is that "hands empty" reads agent.hands (explicit
    state) instead of being derived from every crate's location, and take/put update agent.hands."""
    spec = _spec(spec)
    if spec.domain == "delivery":
        def road(a, b):
            return any({x, y} == {a, b} and a != b for x, y, _ in spec.roads)

        def take_eff(s, x):
            n = dict(s); n[f"{x}.location"] = CARRIED; n[HANDS] = x; return n

        def go_eff(s, a, b):
            n = dict(s); n[AT] = b; return n

        def put_eff(s, x):
            n = dict(s); n[f"{x}.location"] = s[AT]; n[HANDS] = FREE; return n
        return {
            "take": ([("crate_at_your_place", lambda s, x: s.get(f"{x}.location") == s[AT],
                       lambda x: [f"{x}.location", AT]),
                      ("hands_empty", lambda s, x: s.get(HANDS) == FREE, lambda x: [HANDS]),
                      ("crate_portable", lambda s, x: x not in spec.non_portable, lambda x: [])],
                     take_eff, lambda x: [f"{x}.location", HANDS]),
            "go": ([("agent_at_start", lambda s, a, b: s[AT] == a, lambda a, b: [AT]),
                    ("road_exists", lambda s, a, b: road(a, b), lambda a, b: []),
                    ("road_open", lambda s, a, b: tuple(sorted((a, b))) not in spec.closed, lambda a, b: [])],
                   go_eff, lambda a, b: [AT]),
            "put": ([("carrying_crate", lambda s, x: s.get(f"{x}.location") == CARRIED,
                      lambda x: [f"{x}.location"])],
                    put_eff, lambda x: [f"{x}.location", HANDS]),
        }

    def holders(p):
        """Slot fields that can hold p under the invariants (the ancestors of the derived "installed")."""
        return [f"{sl}.part" for sl in spec.slots if p in admissible_values(spec, f"{sl}.part")]

    def installed(s, p):
        return any(s.get(f) == p for f in holders(p))

    def inst_eff(s, p, sl):
        n = dict(s); n[f"{sl}.part"] = p; n[f"{p}.on_hand"] = NO; return n

    def rem_eff(s, sl):
        n = dict(s); n[f"{s[f'{sl}.part']}.on_hand"] = YES; n[f"{sl}.part"] = EMPTY; return n

    def ord_eff(s, p):
        n = dict(s); n[f"{p}.on_hand"] = YES; return n
    return {
        "install": ([("part_on_hand", lambda s, p, sl: s.get(f"{p}.on_hand") == YES, lambda p, sl: [f"{p}.on_hand"]),
                     ("slot_empty", lambda s, p, sl: s.get(f"{sl}.part") == EMPTY, lambda p, sl: [f"{sl}.part"]),
                     ("connector_matches", lambda s, p, sl: spec.parts[p]["type"] == _accepts(spec, sl),
                      lambda p, sl: [])],
                    inst_eff, lambda p, sl: [f"{p}.on_hand", f"{sl}.part"]),
        # remove: the returned part's on_hand is written only conditionally (which part depends on the state)
        "remove": ([("slot_holds_part", lambda s, sl: s.get(f"{sl}.part", EMPTY) != EMPTY, lambda sl: [f"{sl}.part"])],
                   rem_eff, lambda sl: [f"{sl}.part"]),
        "order": ([("part_has_price", lambda s, p: p in spec.prices, lambda p: []),
                   ("part_not_on_hand", lambda s, p: s.get(f"{p}.on_hand", NO) != YES, lambda p: [f"{p}.on_hand"]),
                   ("part_not_installed", lambda s, p: not installed(s, p), lambda p: holders(p))],
                  ord_eff, lambda p: [f"{p}.on_hand"]),
        "fit": ([("adapter_exists", lambda s, a, sl: a in spec.adapters, lambda a, sl: [])], None, lambda a, sl: []),
    }


def engine_table(spec):
    """The same table in engine._actions' shape (name -> (prereqs [(name, fn)], effect)), for E.Engine."""
    return {k: ([(n, fn) for n, fn, _ in pre], eff) for k, (pre, eff, _) in actions(spec).items()}


def evaluate(spec, s, step, table=None):
    """(prerequisite values, allowed, successor or None)."""
    table = table or actions(spec)
    name, *args = step
    pre, eff, _ = table[name]
    vals = {n: bool(fn(s, *args)) for n, fn, _ in pre}
    ok = all(vals.values())
    return vals, ok, (eff(s, *args) if ok and eff else None)


# ---------------------------------------------------------------------------------------------- relevance

def plan_reads(spec, plan, goal_field):
    """Fields a plan's prerequisites or the goal test read before the plan has definitely written them, from the
    shared predicate table. Returns (entity_fields, agent_fields) in first-read order."""
    table = actions(spec)
    written, reads = set(), []

    def read(f):
        if f not in written and f not in reads:
            reads.append(f)
    for name, *args in plan:
        pre, _, writes = table[name]
        for _, _, rd in pre:
            for f in rd(*args):
                read(f)
        written |= set(writes(*args))
    read(goal_field)
    ag = set(agent_fields(spec))
    return [f for f in reads if f not in ag], [f for f in reads if f in ag]


def missing_reads(spec, s, step, table=None):
    """Fields a step's prerequisites read that the state does not contain (a conflicted or never-described field).
    The 1.9.x planner let such a prerequisite fall back to a default inside its test (e.g. "order": an absent stock
    field counted as "not on hand"); V1.11.0 treats it as unknown, so no plan is guaranteed through it."""
    table = table or actions(spec)
    name, *args = step
    return [f for _, _, rd in table[name][0] for f in rd(*args) if f not in s]


# ---------------------------------------------------------------------------------------------- engine view

class InvariantViolationInPhase(E.EngineError):
    pass


class AgentStateEngine(A.AssertionEngine):
    """Engine v0.3 (unchanged per-field historical reconstruction) plus an operational pre-action layer:
      - the declared agent state is part of every compatible state;
      - each described field's supported values are filtered by the declared invariants given that agent state;
        excluded values are listed with their rule and supporting reports ("narrowed"); a field none of whose
        supported values is admissible is an "invariant_conflict" (kept, with provenance; the agent state is not
        changed to fit it);
      - "detail", "per_field" and "conflict_fields" stay exactly the historical reconstruction (unchanged keys);
        the operational result is in "op_per_field", "op_options", "op_conflict_fields", "invariant" and "states".
    check_action / predict_action of the old engine (derived hands) are disabled here; plans are checked with the
    shared predicate table (recovery.guaranteed)."""

    VERSION = "assertions-0.3+agent-invariants-v1"

    def view(self, kind, t, cutoff=None):
        if self.log.executions():
            raise InvariantViolationInPhase("the declared agent state holds only before your first action")
        v = super().view(kind, t, cutoff)
        agent = declared_agent_state(self.spec)
        inv, op_opts, op_per = {}, {}, {}
        for f, d in v["detail"].items():
            if d["status"] == "not_yet_described":
                continue
            if d["status"] == "conflict":
                op_per[f] = "conflict"
                continue
            vals = [d["value"]] if d["status"] == "value" else list(d["options"])
            keep = [x for x in vals if admissible(self.spec, dict(agent, **{f: x}))]
            if len(keep) < len(vals):
                rules = sorted({r for x in vals if x not in keep
                                for r, _ in violations(self.spec, dict(agent, **{f: x}))})
                inv[f] = {"excluded": [x for x in vals if x not in keep], "rules": rules, "support": d["support"],
                          "status": "invariant_conflict" if not keep else "narrowed",
                          "agent_state": dict(agent)}
            if not keep:
                op_per[f] = "conflict"
                continue
            op_opts[f] = keep
            op_per[f] = keep[0] if len(keep) == 1 else E.UNKNOWN
        sf = list(op_opts)
        states = [dict(dict(zip(sf, c)), **agent) for c in itertools.product(*[op_opts[f] for f in sf])]
        v.update(states=states, op_per_field=op_per, op_options=op_opts,
                 op_conflict_fields=sorted(f for f, x in op_per.items() if x == "conflict"),
                 invariant=inv, agent_state=agent, engine=self.VERSION)
        return v

    def check_action(self, branch, action):
        raise NotImplementedError("V1.11.0 checks plans with the shared predicate table (recovery.guaranteed)")

    predict_action = check_action
