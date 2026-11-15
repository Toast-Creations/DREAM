"""Solver 1: ground each family's structured facts into STRIPS actions; simulate and search.

Plans are lists of steps (JSON lists). A step names a lifted action; it may match several
ground variants (e.g. "take pod" at different places). Exactly one variant must be applicable,
otherwise the step is invalid. All queries ask for the lowest-total-cost plan that achieves
the goal, so a candidate is acceptable iff it is valid and its cost equals the global optimum.
"""
import heapq
import itertools


class Ground:
    def __init__(self, init, actions, goal):
        self.init = frozenset(init)
        self.actions = actions  # list of (step_tuple, pre, neg, add, delete, cost)
        self.goal = [frozenset(g) for g in goal]  # DNF

    def satisfied(self, state):
        return any(g <= state for g in self.goal)

    def applicable(self, state):
        for step, pre, neg, add, delete, cost in self.actions:
            if pre <= state and not (neg & state):
                yield step, (state - delete) | add, cost

    def simulate(self, plan):
        """Return (valid, cost)."""
        state, total = self.init, 0
        for raw in plan:
            step = tuple(raw)
            options = [(s, c) for st, s, c in self.applicable(state) if st == step]
            if len(options) != 1:
                return False, None
            state, cost = options[0]
            total += cost
        return self.satisfied(state), total

    def optimum(self):
        """Dijkstra; returns (cost, plan) or (None, None) if unreachable."""
        counter = itertools.count()
        frontier = [(0, next(counter), self.init, ())]
        best = {self.init: 0}
        while frontier:
            cost, _, state, plan = heapq.heappop(frontier)
            if cost > best.get(state, float("inf")):
                continue
            if self.satisfied(state):
                return cost, [list(s) for s in plan]
            for step, nxt, c in self.applicable(state):
                if cost + c < best.get(nxt, float("inf")):
                    best[nxt] = cost + c
                    heapq.heappush(frontier, (cost + c, next(counter), nxt, plan + (step,)))
        return None, None


def apply_correction(static, correction):
    """Return a copy of the static facts with one explicitly labeled override."""
    import copy
    out = copy.deepcopy(static)
    if correction:
        target = out
        path = correction["path"]
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = correction["value"]
    return out


def _road_key(a, b):
    return tuple(sorted((a, b)))


def ground_delivery(static, state, goal):
    closed = {_road_key(a, b) for a, b in state["closed"]}
    init = {("agent", state["agent"])}
    held = [i for i, where in state["item_at"].items() if where == "held"]
    for item, where in state["item_at"].items():
        init.add(("held", item) if where == "held" else ("at", item, where))
    if not held:
        init.add(("handfree",))
    actions = []
    for a, b, cost in static["roads"]:
        if _road_key(a, b) in closed:
            continue
        for x, y in ((a, b), (b, a)):
            actions.append((("go", x, y), frozenset({("agent", x)}), frozenset(),
                            frozenset({("agent", y)}), frozenset({("agent", x)}), cost))
    for item, props in static["items"].items():
        for place in static["places"]:
            if props["portable"]:
                actions.append((("take", item), frozenset({("agent", place), ("at", item, place), ("handfree",)}),
                                frozenset(), frozenset({("held", item)}),
                                frozenset({("at", item, place), ("handfree",)}), 1))
            actions.append((("put", item), frozenset({("agent", place), ("held", item)}), frozenset(),
                            frozenset({("at", item, place), ("handfree",)}), frozenset({("held", item)}), 1))
    return Ground(init, actions, [{("at", goal["item"], goal["place"])}])


def ground_assembly(static, state, goal):
    init = {("onhand", x) for x in state["on_hand"]}
    for slot in static["slots"]:
        part = state["slot_part"].get(slot)
        adapter = state["slot_adapter"].get(slot)
        init.add(("part_in", slot, part) if part else ("empty", slot))
        init.add(("adapter_on", slot, adapter) if adapter else ("noadapter", slot))
    actions = []
    for part, price in static["prices"].items():
        neg = {("onhand", part)} | {("part_in", s, part) for s in static["slots"]}
        actions.append((("order", part), frozenset(), frozenset(neg),
                        frozenset({("onhand", part)}), frozenset(), price))
    for slot, connector in static["slots"].items():
        for adapter, spec in static["adapters"].items():
            if spec["to"] == connector:
                actions.append((("fit", adapter, slot),
                                frozenset({("onhand", adapter), ("empty", slot), ("noadapter", slot)}), frozenset(),
                                frozenset({("adapter_on", slot, adapter)}),
                                frozenset({("onhand", adapter), ("noadapter", slot)}), 1))
        for part, spec in static["parts"].items():
            if spec["type"] == connector:
                actions.append((("install", part, slot),
                                frozenset({("onhand", part), ("empty", slot), ("noadapter", slot)}), frozenset(),
                                frozenset({("part_in", slot, part)}),
                                frozenset({("onhand", part), ("empty", slot)}), 2))
            for adapter, aspec in static["adapters"].items():
                if aspec["to"] == connector and aspec["from"] == spec["type"]:
                    actions.append((("install", part, slot),
                                    frozenset({("onhand", part), ("empty", slot), ("adapter_on", slot, adapter)}),
                                    frozenset(), frozenset({("part_in", slot, part)}),
                                    frozenset({("onhand", part), ("empty", slot)}), 2))
            actions.append((("remove", slot), frozenset({("part_in", slot, part)}), frozenset(),
                            frozenset({("onhand", part), ("empty", slot)}), frozenset({("part_in", slot, part)}), 1))
    good = [{("part_in", goal["slot"], p)} for p, spec in static["parts"].items()
            if spec["rating"] >= goal["min_rating"]]
    return Ground(init, actions, good)


def ground_workshop(static, state, goal):
    init = {("have", x) for x in state["have"]} | {("permit", k) for k in state["permits"]}
    out = set(state["out_of_stock"])
    actions = []
    for source, spec in static["sources"].items():
        if source in out:
            continue
        pre = {("permit", spec["permit"])} if spec["permit"] else set()
        actions.append((("get", spec["resource"], source), frozenset(pre), frozenset(),
                        frozenset({("have", spec["resource"])}), frozenset(), spec["cost"]))
    for permit, cost in static["permits"].items():
        actions.append((("obtain", permit), frozenset(), frozenset(),
                        frozenset({("permit", permit)}), frozenset(), cost))
    for item, spec in static["recipes"].items():
        pre = {("have", r) for r in spec["inputs"]}
        if spec["permit"]:
            pre.add(("permit", spec["permit"]))
        actions.append((("make", item), frozenset(pre), frozenset(),
                        frozenset({("have", item)}), frozenset({("have", r) for r in spec["inputs"]}), 1))
    return Ground(init, actions, [{("have", goal["item"])}])


GROUNDERS = {"delivery": ground_delivery, "assembly": ground_assembly, "workshop": ground_workshop}


def ground(family, static, query):
    return GROUNDERS[family](apply_correction(static, query.get("correction")), query["state"], query["goal"])


def judge(family, static, query):
    """Return (optimal_cost, acceptable_ids, per-candidate (valid, cost))."""
    g = ground(family, static, query)
    best, _ = g.optimum()
    detail = {c["id"]: g.simulate(c["plan"]) for c in query["candidates"]}
    ok = sorted(cid for cid, (valid, cost) in detail.items() if valid and cost == best)
    return best, ok, detail
