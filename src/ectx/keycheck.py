"""Solver 2: an independent re-implementation of the three families' rules.

Deliberately shares no code with world.py: it simulates each family directly on plain
dictionaries (following the rule text in render.py), enumerates every reachable state,
and computes optimal costs by Bellman-Ford relaxation instead of Dijkstra. Any
disagreement with solver 1 on any key rejects the item set.
"""
import collections
import copy
import json


def _corrected(static, correction):
    s = json.loads(json.dumps(static))
    if correction:
        node = s
        for key in correction["path"][:-1]:
            node = node[key]
        node[correction["path"][-1]] = correction["value"]
    return s


# ---------- per-family transition functions: (static, state, step) -> (new_state, cost) or None

def _delivery_step(st, s, step):
    kind = step[0]
    if kind == "go":
        _, a, b = step
        if s["agent"] != a:
            return None
        for x, y, cost in st["roads"]:
            if {x, y} == {a, b} and a != b:
                if any({p, q} == {a, b} for p, q in s["closed"]):
                    return None
                n = copy.deepcopy(s); n["agent"] = b
                return n, cost
        return None
    if kind == "take":
        item = step[1]
        if item not in st["items"] or not st["items"][item]["portable"]:
            return None
        if "held" in s["item_at"].values() or s["item_at"][item] != s["agent"]:
            return None
        n = copy.deepcopy(s); n["item_at"][item] = "held"
        return n, 1
    if kind == "put":
        item = step[1]
        if s["item_at"].get(item) != "held":
            return None
        n = copy.deepcopy(s); n["item_at"][item] = s["agent"]
        return n, 1
    return None


def _assembly_step(st, s, step):
    kind = step[0]
    if kind == "order":
        part = step[1]
        if part not in st["prices"] or part in s["on_hand"] or part in s["slot_part"].values():
            return None
        n = copy.deepcopy(s); n["on_hand"] = sorted(n["on_hand"] + [part])
        return n, st["prices"][part]
    if kind == "fit":
        _, adapter, slot = step
        if adapter not in s["on_hand"] or adapter not in st["adapters"]:
            return None
        if s["slot_part"].get(slot) or s["slot_adapter"].get(slot):
            return None
        if st["adapters"][adapter]["to"] != st["slots"][slot]:
            return None
        n = copy.deepcopy(s); n["on_hand"].remove(adapter); n["slot_adapter"][slot] = adapter
        return n, 1
    if kind == "install":
        _, part, slot = step
        if part not in s["on_hand"] or part not in st["parts"] or s["slot_part"].get(slot):
            return None
        adapter = s["slot_adapter"].get(slot)
        accepts = st["adapters"][adapter]["from"] if adapter else st["slots"][slot]
        if st["parts"][part]["type"] != accepts:
            return None
        n = copy.deepcopy(s); n["on_hand"].remove(part); n["slot_part"][slot] = part
        return n, 2
    if kind == "remove":
        slot = step[1]
        part = s["slot_part"].get(slot)
        if not part:
            return None
        n = copy.deepcopy(s); n["slot_part"][slot] = None; n["on_hand"] = sorted(n["on_hand"] + [part])
        return n, 1
    return None


def _workshop_step(st, s, step):
    kind = step[0]
    if kind == "get":
        _, resource, source = step
        spec = st["sources"].get(source)
        if not spec or spec["resource"] != resource or source in s["out_of_stock"]:
            return None
        if spec["permit"] and spec["permit"] not in s["permits"]:
            return None
        n = copy.deepcopy(s); n["have"] = sorted(set(n["have"]) | {resource})
        return n, spec["cost"]
    if kind == "obtain":
        permit = step[1]
        if permit not in st["permits"]:
            return None
        n = copy.deepcopy(s); n["permits"] = sorted(set(n["permits"]) | {permit})
        return n, st["permits"][permit]
    if kind == "make":
        item = step[1]
        spec = st["recipes"].get(item)
        if not spec or not set(spec["inputs"]) <= set(s["have"]):
            return None
        if spec["permit"] and spec["permit"] not in s["permits"]:
            return None
        n = copy.deepcopy(s); n["have"] = sorted((set(n["have"]) - set(spec["inputs"])) | {item})
        return n, 1
    return None


def _delivery_goal(st, s, g):
    return s["item_at"].get(g["item"]) == g["place"]


def _assembly_goal(st, s, g):
    part = s["slot_part"].get(g["slot"])
    return bool(part) and st["parts"][part]["rating"] >= g["min_rating"]


def _workshop_goal(st, s, g):
    return g["item"] in s["have"]


def _delivery_moves(st, s):
    places = st["places"]
    for a in places:
        for b in places:
            yield ["go", a, b]
    for item in st["items"]:
        yield ["take", item]
        yield ["put", item]


def _assembly_moves(st, s):
    for p in st["prices"]:
        yield ["order", p]
    for slot in st["slots"]:
        yield ["remove", slot]
        for a in st["adapters"]:
            yield ["fit", a, slot]
        for p in st["parts"]:
            yield ["install", p, slot]


def _workshop_moves(st, s):
    for source, spec in st["sources"].items():
        yield ["get", spec["resource"], source]
    for permit in st["permits"]:
        yield ["obtain", permit]
    for item in st["recipes"]:
        yield ["make", item]


FAMILIES = {
    "delivery": (_delivery_step, _delivery_goal, _delivery_moves),
    "assembly": (_assembly_step, _assembly_goal, _assembly_moves),
    "workshop": (_workshop_step, _workshop_goal, _workshop_moves),
}


def _normalize(state):
    s = json.loads(json.dumps(state))
    for key in ("on_hand", "have", "permits"):
        if key in s:
            s[key] = sorted(s[key])
    return s


def _key(state):
    return json.dumps(state, sort_keys=True)


def run_plan(family, static, query, plan):
    step_fn, goal_fn, _ = FAMILIES[family]
    st = _corrected(static, query.get("correction"))
    s, total = _normalize(query["state"]), 0
    for step in plan:
        result = step_fn(st, s, list(step))
        if result is None:
            return False, None
        s, cost = result
        total += cost
    return goal_fn(st, s, query["goal"]), total


def optimum(family, static, query):
    step_fn, goal_fn, moves = FAMILIES[family]
    st = _corrected(static, query.get("correction"))
    start = _normalize(query["state"])
    states, edges, queue = {_key(start): start}, [], [start]
    while queue:
        s = queue.pop()
        for step in moves(st, s):
            r = step_fn(st, s, step)
            if r is None:
                continue
            n, cost = _normalize(r[0]), r[1]
            k = _key(n)
            edges.append((_key(s), k, cost))
            if k not in states:
                states[k] = n
                queue.append(n)
    dist = {k: float("inf") for k in states}
    dist[_key(start)] = 0
    for _ in range(len(states)):
        changed = False
        for a, b, c in edges:
            if dist[a] + c < dist[b]:
                dist[b] = dist[a] + c
                changed = True
        if not changed:
            break
    goals = [dist[k] for k, s in states.items() if goal_fn(st, s, query["goal"])]
    best = min(goals) if goals else float("inf")
    return None if best == float("inf") else best


def judge(family, static, query):
    best = optimum(family, static, query)
    detail = {c["id"]: run_plan(family, static, query, c["plan"]) for c in query["candidates"]}
    ok = sorted(cid for cid, (valid, cost) in detail.items() if valid and cost == best)
    return best, ok, detail


def check_episode(ep):
    """Recompute every key with solver 2 and check the design properties. Returns a list of problems."""
    from . import world  # only for the agreement comparison, after solver 2 has run
    problems, fam, st = [], ep["family"], ep["static"]
    by_id = {q["qid"]: q for q in ep["queries"]}
    for q in ep["support"] + ep["queries"]:
        best, ok, _ = judge(fam, st, q)
        best1, ok1, _ = world.judge(fam, st, q)
        if (best, ok) != (best1, ok1):
            problems.append(f"{q['qid']}: solvers disagree {best, ok} vs {best1, ok1}")
        if best is None or not ok:
            problems.append(f"{q['qid']}: no acceptable candidate")
        if len(ok) == len(q["candidates"]):
            problems.append(f"{q['qid']}: every candidate acceptable")
        if sorted(q["acceptable"]) != ok or q["optimal_cost"] != best:
            problems.append(f"{q['qid']}: stored key differs from solver 2")
        if q in ep["support"] and q["answer"] not in ok:
            problems.append(f"{q['qid']}: support answer not acceptable")
        if len({c["id"] for c in q["candidates"]}) != len(q["candidates"]):
            problems.append(f"{q['qid']}: duplicate candidate IDs")
        if len({json.dumps(c["plan"]) for c in q["candidates"]}) != len(q["candidates"]):
            problems.append(f"{q['qid']}: duplicate candidate plans")
    pairs = {}
    for q in ep["queries"]:
        if q["kind"] == "pair":
            pairs.setdefault(q["pair_id"], {})[q["side"]] = q
    for pid, sides in pairs.items():
        if set(sides) != {"A", "B"}:
            problems.append(f"{pid}: incomplete pair")
            continue
        a, b = sides["A"], sides["B"]
        if [c["id"] for c in a["candidates"]] != [c["id"] for c in b["candidates"]] or a["candidates"] != b["candidates"]:
            problems.append(f"{pid}: pair sides do not share candidates")
        if set(a["acceptable"]) & set(b["acceptable"]):
            problems.append(f"{pid}: acceptable sets overlap")
        if a["goal"] == b["goal"] and a["state"] == b["state"]:
            problems.append(f"{pid}: sides identical")
    for q in ep["queries"]:
        if q["kind"] == "irrelevant":
            base = by_id[q["base_qid"]]
            if q["candidates"] != base["candidates"] or q["acceptable"] != base["acceptable"]:
                problems.append(f"{q['qid']}: irrelevant change altered candidates or key")
            if q["state"] == base["state"]:
                problems.append(f"{q['qid']}: irrelevant variant identical to base")
        if q["kind"] == "correction":
            stale = dict(q); stale["correction"] = None
            _, stale_ok, _ = judge(fam, st, stale)
            if sorted(q["stale_acceptable"]) != stale_ok or not stale_ok:
                problems.append(f"{q['qid']}: stale key wrong")
            if set(stale_ok) & set(q["acceptable"]):
                problems.append(f"{q['qid']}: correction does not change the answer")
    # A situation = state + goal, canonicalized (order-free lists), ignoring option labels/order and any
    # correction. Support examples must not repeat a scored situation or each other (V1.6.2: stricter).
    support_sigs = collections.Counter(situation(s) for s in ep["support"])
    for sig, n in support_sigs.items():
        if n > 1:
            problems.append(f"support examples repeat a situation ({n}x)")
    for q in ep["queries"]:
        if situation(q) in support_sigs:
            problems.append(f"{q['qid']}: evaluation state/goal duplicates a support example")
    for s in ep["support"]:
        if s.get("correction") and s["correction"].get("scope") != "example":
            problems.append(f"{s['qid']}: support correction not scoped to its example")
    return problems


def situation(q):
    """Canonical state+goal signature: equal for situations that differ only in list order or option labels."""
    s = json.loads(json.dumps(q["state"]))
    if "closed" in s:
        s["closed"] = sorted(sorted(x) for x in s["closed"])
    for key in ("on_hand", "have", "permits", "out_of_stock"):
        if key in s:
            s[key] = sorted(s[key])
    return json.dumps([s, q["goal"]], sort_keys=True)
