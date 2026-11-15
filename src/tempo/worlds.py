"""Two domains for the temporal pilot: delivery and assembly.

A world's temporal facts are named fields ("Gemi.location", "Lamo.part", "Kide.on_hand") with string
values. This module turns a full field assignment into the planner formats of the two existing,
independently written solvers (ectx.world = solver 1, ectx.keycheck = solver 2), and applies the single
A0 action with its own field-level code (a third implementation, compared against keycheck's).
"""
import heapq
import random

from ectx import keycheck, render as ectx_render, world as ectx_world

CARRIED = "carried by you"
EMPTY = "empty"
YES, NO = "yes", "no"
UNKNOWN = "unknown"

OBS_OPTION_TEXT = ("Do not act yet: first ask for a fresh verified observation of the facts the goal depends on, "
                   "then decide.")

CONSONANTS = {"main": "bdgkmtz", "smoke": "fhlnprs", "probe": "cjvwy", "probesmoke": "fhlnprs"}
VOWELS = "aeiou"


class Names:
    def __init__(self, pool, rng):
        self.rng, self.cons, self.used = rng, CONSONANTS[pool], set()

    def word(self):
        while True:
            w = "".join(self.rng.choice(self.cons) + self.rng.choice(VOWELS) for _ in range(2)).capitalize()
            if w not in self.used:
                self.used.add(w)
                return w


def _dijkstra(roads, a, b):
    adj = {}
    for x, y, c in roads:
        adj.setdefault(x, []).append((y, c)); adj.setdefault(y, []).append((x, c))
    best, frontier = {a: (0, [a])}, [(0, [a])]
    while frontier:
        cost, path = heapq.heappop(frontier)
        node = path[-1]
        if node == b:
            return cost, path
        for nxt, c in adj.get(node, []):
            if nxt not in best or cost + c < best[nxt][0]:
                best[nxt] = (cost + c, path + [nxt])
                heapq.heappush(frontier, (cost + c, path + [nxt]))
    return None, None


def _route_steps(path):
    return [["go", path[i], path[i + 1]] for i in range(len(path) - 1)]


def _path_cost(roads, path):
    total = 0
    for x, y in zip(path, path[1:]):
        total += next(c for a, b, c in roads if {a, b} == {x, y})
    return total


# ============================================================== delivery

class Delivery:
    domain = "delivery"
    entity_word = "crate"

    def __init__(self, rng, names):
        self.you, self.b, self.c, self.g = (names.word() for _ in range(4))
        self.places = [self.you, self.b, self.c, self.g]
        while True:
            cost = {k: rng.randint(1, 5) for k in ("yb", "yc", "cb", "bg", "yg", "cg")}
            roads = [[self.you, self.b, cost["yb"]], [self.you, self.c, cost["yc"]], [self.c, self.b, cost["cb"]],
                     [self.b, self.g, cost["bg"]], [self.you, self.g, cost["yg"]], [self.c, self.g, cost["cg"]]]
            c_yb, p_yb = _dijkstra(roads, self.you, self.b)
            dear = [self.you, self.c, self.b]
            if p_yb == [self.you, self.b] and _path_cost(roads, dear) > c_yb \
                    and _dijkstra(roads, self.you, self.b)[0] < _dijkstra(roads, self.you, self.g)[0] + cost["bg"]:
                break
        self.roads = roads
        self.x, self.y, self.z = (names.word() for _ in range(3))
        # focal: X's location, two candidate values (the place you stand at, and B); P6 starts at C
        self.focal = f"{self.x}.location"
        self.focal_values = [self.you, self.b]
        self.focal_start_uncertain = self.c
        self.side = f"{self.y}.location"
        self.other = [f"{self.z}.location"]
        self.asked = [self.focal, self.side, f"{self.z}.location"]
        self.goal = {"item": self.x, "place": self.g}
        _, to_g_from_you = _dijkstra(roads, self.you, self.g)
        _, to_g_from_b = _dijkstra(roads, self.b, self.g)
        self.plans = {
            "here": [["take", self.x]] + _route_steps(to_g_from_you) + [["put", self.x]],
            "b_cheap": _route_steps([self.you, self.b]) + [["take", self.x]] + _route_steps(to_g_from_b) + [["put", self.x]],
            "b_dear": _route_steps(dear) + [["take", self.x]] + _route_steps(to_g_from_b) + [["put", self.x]],
        }
        self.action = ["take", self.x]
        self.pad_names = names

    # ---- values
    def side_values(self, rng):
        return rng.sample(self.places, 2)

    def other_init(self, rng):
        return {f"{self.z}.location": rng.choice(self.places)}

    def allowed(self, field):
        return self.places + [CARRIED, UNKNOWN]

    def new_pad_entity(self, rng):
        return f"{self.pad_names.word()}.location", rng.choice(self.places)

    def pad_next(self, field, cur, rng):
        return rng.choice([p for p in self.places if p != cur])

    def side_next(self, cur, rng):
        return rng.choice([p for p in self.places if p != cur])

    # ---- text
    def ent(self, field):
        return field.split(".")[0]

    def fact(self, field, value):
        e = self.ent(field)
        return f"crate {e} is being carried by you" if value == CARRIED else f"crate {e} rests at {value}"

    def unknown(self, field, options):
        return f"crate {self.ent(field)}: not known — it rests at either {options[0]} or {options[1]}"

    def change(self, field, frm, to):
        return f"another worker moved crate {self.ent(field)} from {frm} to {to}"

    def uncertain(self, field, frm, options):
        return (f"another worker moved crate {self.ent(field)} away from {frm}; where it went was not recorded. "
                f"Afterwards it rests at either {options[0]} or {options[1]}")

    def rules(self):
        return ectx_render.RULES["delivery"]

    def fixed_lines(self):
        out = ["Places: " + ", ".join(self.places) + "."]
        out += [f"Road between {a} and {b}: cost {c}." for a, b, c in self.roads]
        out += ["All crates are portable.", f"You are at {self.you}, with empty hands. You do not move unless you act."]
        return out

    def goal_line(self):
        return f"Goal: crate {self.x} rests at {self.g}."

    def plan_text(self, key):
        return ectx_render.plan_text("delivery", self.plans[key])

    def action_text(self):
        return f"take {self.x}"

    # ---- planner bridges
    def to_planner(self, fields):
        static = {"places": self.places, "roads": self.roads,
                  "items": {e: {"portable": True} for e in (self.x, self.y, self.z)}}
        state = {"agent": self.you, "closed": [],
                 "item_at": {e: ("held" if fields[f"{e}.location"] == CARRIED else fields[f"{e}.location"])
                             for e in (self.x, self.y, self.z)}}
        return static, state, self.goal

    def from_planner(self, state, fields):
        out = dict(fields)
        for e, w in state["item_at"].items():
            out[f"{e}.location"] = CARRIED if w == "held" else w
        return out

    def apply_own(self, fields):
        """Third implementation of 'take X' at the field level: (applicable, successor fields)."""
        carrying = any(v == CARRIED for k, v in fields.items() if k.endswith(".location"))
        if fields[self.focal] == self.you and not carrying:
            out = dict(fields); out[self.focal] = CARRIED
            return True, out
        return False, dict(fields)

    def apply_keycheck(self, fields):
        static, state, _ = self.to_planner(fields)
        res = keycheck._delivery_step(static, keycheck._normalize(state), list(self.action))
        if res is None:
            return False, dict(fields)
        return True, self.from_planner(res[0], fields)


# ============================================================== assembly

class Assembly:
    domain = "assembly"

    def __init__(self, rng, names, focal_kind):
        self.t, self.s2 = names.word(), names.word()
        self.g, self.w, self.d, self.e, self.e2 = (names.word() for _ in range(5))
        k, k2 = rng.sample(["K2", "K3", "K4", "K5", "K6"], 2)
        self.k, self.k2 = k, k2
        self.min_rating = rng.randint(4, 7)
        self.parts = {self.g: {"type": k, "rating": rng.randint(self.min_rating + 1, 9)},
                      self.w: {"type": k, "rating": rng.randint(1, self.min_rating - 1)},
                      self.d: {"type": k2, "rating": rng.randint(1, 9)},
                      self.e: {"type": k2, "rating": rng.randint(1, 9)},
                      self.e2: {"type": k2, "rating": rng.randint(1, 9)}}
        self.price = rng.randint(2, 6)
        self.focal_kind = focal_kind  # "slot" or "stock"
        self.slot_f, self.stock_f = f"{self.t}.part", f"{self.g}.on_hand"
        if focal_kind == "slot":
            self.focal, self.focal_values, self.fixed_other = self.slot_f, [EMPTY, self.w], {self.stock_f: YES}
        else:
            self.focal, self.focal_values, self.fixed_other = self.stock_f, [YES, NO], {self.slot_f: EMPTY}
        self.focal_start_uncertain = None  # assembly P6 starts from one of the focal values
        self.side = f"{self.s2}.part"
        self.asked = [self.slot_f, self.stock_f, self.side, f"{self.d}.on_hand"]
        self.goal = {"slot": self.t, "min_rating": self.min_rating}
        self.plans = {"install": [["install", self.g, self.t]],
                      "remove_install": [["remove", self.t], ["install", self.g, self.t]],
                      "order_install": [["order", self.g], ["install", self.g, self.t]]}
        self.action = ["install", self.g, self.t]
        self.pad_names = names

    def side_values(self, rng):
        return rng.sample([EMPTY, self.e, self.e2], 2)

    def other_init(self, rng):
        out = dict(self.fixed_other)
        out[f"{self.d}.on_hand"] = rng.choice([YES, NO])
        return out

    def allowed(self, field):
        if field.endswith(".on_hand"):
            return [YES, NO, UNKNOWN]
        if field == self.slot_f:
            return [EMPTY, self.w, self.g, UNKNOWN]
        return [EMPTY, self.e, self.e2, UNKNOWN]

    def new_pad_entity(self, rng):
        return f"{self.pad_names.word()}.on_hand", rng.choice([YES, NO])

    def pad_next(self, field, cur, rng):
        return NO if cur == YES else YES

    def side_next(self, cur, rng):
        return rng.choice([v for v in (EMPTY, self.e, self.e2) if v != cur])

    def ent(self, field):
        return field.split(".")[0]

    def fact(self, field, value):
        e = self.ent(field)
        if field.endswith(".on_hand"):
            return f"part {e} is on hand" if value == YES else f"part {e} is not on hand"
        return f"slot {e} is empty" if value == EMPTY else f"slot {e} holds part {value}"

    def unknown(self, field, options):
        e = self.ent(field)
        if field.endswith(".on_hand"):
            return f"part {e}: not known whether it is on hand"
        a, b = (("empty" if o == EMPTY else f"holds part {o}") for o in options)
        return f"slot {e}: not known — it is either {a} or {b}"

    def change(self, field, frm, to):
        e = self.ent(field)
        if field.endswith(".on_hand"):
            return (f"part {e} was delivered to you; it is now on hand" if to == YES
                    else f"another team took part {e}; it is no longer on hand")
        if frm == EMPTY:
            return f"another technician installed part {to} in slot {e} (from their own stock)"
        if to == EMPTY:
            return f"another technician removed part {frm} from slot {e} and took it away"
        return f"another technician replaced part {frm} in slot {e} with part {to} (taking {frm} away)"

    def uncertain(self, field, frm, options):
        e = self.ent(field)
        if field.endswith(".on_hand"):
            return (f"a stock check of part {e} was interrupted; whether part {e} was moved was not recorded. "
                    f"Afterwards part {e} is either on hand or not on hand")
        a, b = (("empty" if o == EMPTY else f"holds part {o}") for o in options)
        return (f"another technician worked on slot {e}; the result was not recorded. "
                f"Afterwards slot {e} is either {a} or {b}")

    def rules(self):
        return ectx_render.RULES["assembly"]

    def fixed_lines(self):
        out = [f"Slot {self.t}: connector {self.k}.", f"Slot {self.s2}: connector {self.k2}."]
        out += [f"Part {p}: connector {v['type']}, rating {v['rating']}." for p, v in self.parts.items()]
        out += [f"Price of {self.g}: {self.price}. No other part can be ordered.",
                "Parts other technicians install come from their own stock, not from what you have on hand."]
        return out

    def goal_line(self):
        return f"Goal: slot {self.t} holds a part rated at least {self.min_rating}."

    def plan_text(self, key):
        return ectx_render.plan_text("assembly", self.plans[key])

    def action_text(self):
        return f"install {self.g} in {self.t}"

    def to_planner(self, fields):
        static = {"slots": {self.t: self.k, self.s2: self.k2}, "parts": self.parts, "adapters": {},
                  "prices": {self.g: self.price}}
        on_hand = [p for p in (self.g, self.d) if fields[f"{p}.on_hand"] == YES]
        slot_part = {s: (None if fields[f"{s}.part"] == EMPTY else fields[f"{s}.part"]) for s in (self.t, self.s2)}
        return static, {"on_hand": sorted(on_hand), "slot_part": slot_part, "slot_adapter": {}}, self.goal

    def from_planner(self, state, fields):
        out = dict(fields)
        for p in (self.g, self.d):
            out[f"{p}.on_hand"] = YES if p in state["on_hand"] else NO
        for s in (self.t, self.s2):
            out[f"{s}.part"] = state["slot_part"][s] or EMPTY
        return out

    def apply_own(self, fields):
        """Third implementation of 'install G in T' at the field level."""
        ok = (fields[self.stock_f] == YES and fields[self.slot_f] == EMPTY and self.parts[self.g]["type"] == self.k)
        if not ok:
            return False, dict(fields)
        out = dict(fields); out[self.slot_f] = self.g; out[self.stock_f] = NO
        return True, out

    def apply_keycheck(self, fields):
        static, state, _ = self.to_planner(fields)
        res = keycheck._assembly_step(static, keycheck._normalize(state), list(self.action))
        if res is None:
            return False, dict(fields)
        return True, self.from_planner(res[0], fields)


# ============================================================== plan checking (two solvers)

def plan_status(w, fields, key):
    """(valid_and_goal, cost) from both solvers; raises on disagreement."""
    static, state, goal = w.to_planner(fields)
    plan = w.plans[key]
    if w.domain == "delivery":
        g = ectx_world.ground_delivery(static, state, goal)
    else:
        g = ectx_world.ground_assembly(static, state, goal)
    s1 = g.simulate([tuple(s) for s in plan])
    s2 = keycheck.run_plan(w.domain, static, {"state": state, "goal": goal}, plan)
    if (bool(s1[0]), s1[1] if s1[0] else None) != (bool(s2[0]), s2[1] if s2[0] else None):
        raise AssertionError(f"solver disagreement on {key}: {s1} vs {s2}")
    return bool(s1[0]), (s1[1] if s1[0] else None)


def make_world(domain, rng, names, focal_kind=None):
    return Delivery(rng, names) if domain == "delivery" else Assembly(rng, names, focal_kind)
