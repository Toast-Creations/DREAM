"""Seeded episode generator. Items are constructed with solver 1 and must later pass solver 2.

Split boundaries (proposal draft 1.1, "separate concrete episodes and answer-generation templates"):
- Names: development and sealed sets draw nonce words from disjoint consonant pools, so no label recurs.
- Flip constructions: each family has four fact-flip templates; two belong to development, two to the
  sealed evaluation. The sealed set therefore tests new query forms, never seen while tuning.
"""
import copy
import hashlib
import json
import random

from . import world

FLIPS = {
    "delivery": {"dev": ["closed", "goalplace"], "sealed": ["already", "elsewhere"]},
    "assembly": {"dev": ["rating", "occupied"], "sealed": ["already", "onhand"]},
    "workshop": {"dev": ["stock", "goalitem"], "sealed": ["owned", "permit"]},
}
CONSONANTS = {"dev": "bdgklm", "sealed": "nprstv"}
VOWELS = "aeiou"
SUFFIX = {
    "delivery_place": ["Yard", "Gate", "Mill", "Hall", "Dock", "Post", "Barn", "Quay"],
    "delivery_item": ["pod", "crate", "drum", "kit", "notice", "case"],
    "assembly_part": ["unit", "module", "cell", "core"],
    "workshop_res": ["resin", "fibre", "wire", "salt", "glass", "clay", "ink"],
    "workshop_src": ["Store", "Depot", "Stall", "Works"],
    "workshop_item": ["lamp", "frame", "token", "bell", "vane"],
}
PAIRS_PER_FLIP = 2
N_OPTIONS = 4
SUPPORT_N = 6


class Names:
    def __init__(self, split, rng):
        self.rng, self.cons, self.used = rng, CONSONANTS[split], set()

    def word(self):
        while True:
            w = "".join(self.rng.choice(self.cons) + self.rng.choice(VOWELS) for _ in range(2)).capitalize()
            if w not in self.used:
                self.used.add(w)
                return w

    def name(self, kind):
        return f"{self.word()} {self.rng.choice(SUFFIX[kind])}"


# ---------------------------------------------------------------- static worlds

def static_delivery(rng, names):
    places = [names.name("delivery_place") for _ in range(5)]
    order = places[:]
    rng.shuffle(order)
    edges = {tuple(sorted((order[i], rng.choice(order[:i])))) for i in range(1, 5)}
    while len(edges) < 6:
        a, b = rng.sample(places, 2)
        edges.add(tuple(sorted((a, b))))
    roads = [[a, b, rng.randint(1, 4)] for a, b in sorted(edges)]
    items = {names.name("delivery_item"): {"portable": True} for _ in range(2)}
    items[names.name("delivery_item")] = {"portable": False}
    return {"places": places, "roads": roads, "items": items}


def static_assembly(rng, names):
    conns = [names.word() + " jack" for _ in range(3)]
    slots = {names.word(): rng.choice(conns) for _ in range(3)}
    parts = {names.name("assembly_part"): {"type": rng.choice(conns), "rating": rng.randint(1, 5)} for _ in range(5)}
    adapters = {}
    for _ in range(2):
        a, b = rng.sample(conns, 2)
        adapters[names.word() + " adapter"] = {"from": a, "to": b}
    prices = {p: rng.randint(2, 6) for p in rng.sample(sorted(parts), 3)}
    return {"slots": slots, "parts": parts, "adapters": adapters, "prices": prices}


def static_workshop(rng, names):
    res = [names.name("workshop_res") for _ in range(5)]
    permits = {names.word(): rng.randint(2, 4) for _ in range(2)}
    pnames = sorted(permits)
    sources = {}
    for r in res:
        sources[names.name("workshop_src")] = {"resource": r, "cost": rng.randint(1, 5), "permit": None}
    for r in rng.sample(res, 2):
        sources[names.name("workshop_src")] = {"resource": r, "cost": rng.randint(1, 5),
                                               "permit": rng.choice([None, pnames[0]])}
    items = [names.name("workshop_item") for _ in range(3)]
    a, b, c, d, e = rng.sample(res, 5)
    recipes = {items[0]: {"inputs": [a, b], "permit": rng.choice([None, pnames[1]])},
               items[1]: {"inputs": [items[0], c], "permit": None},
               items[2]: {"inputs": [d, e], "permit": rng.choice([None, pnames[1]])}}
    return {"sources": sources, "permits": permits, "recipes": recipes}


STATIC = {"delivery": static_delivery, "assembly": static_assembly, "workshop": static_workshop}


# ---------------------------------------------------------------- random queries

def random_query(fam, st, rng):
    if fam == "delivery":
        portable = [i for i, p in st["items"].items() if p["portable"]]
        state = {"agent": rng.choice(st["places"]),
                 "item_at": {i: rng.choice(st["places"]) for i in st["items"]}, "closed": []}
        other = [i for i in portable]
        if rng.random() < 0.25:
            state["item_at"][rng.choice(other)] = "held"
        if rng.random() < 0.4:
            a, b, _ = rng.choice(st["roads"])
            state["closed"] = [[a, b]]
        item = rng.choice(portable)
        if state["item_at"][item] == "held":
            state["item_at"][item] = rng.choice(st["places"])
        goal = {"item": item, "place": rng.choice([p for p in st["places"] if p != state["item_at"][item]])}
        return {"state": state, "goal": goal}
    if fam == "assembly":
        parts = sorted(st["parts"]); rng.shuffle(parts)
        slot_part = {s: None for s in st["slots"]}
        for s in st["slots"]:
            if rng.random() < 0.4:
                compatible = [p for p in parts if st["parts"][p]["type"] == st["slots"][s]]
                if compatible:
                    slot_part[s] = compatible[0]; parts.remove(compatible[0])
        on_hand = [p for p in parts if rng.random() < 0.5]
        on_hand += [a for a in st["adapters"] if rng.random() < 0.6]
        slot = rng.choice(sorted(st["slots"]))
        state = {"slot_part": slot_part, "slot_adapter": {s: None for s in st["slots"]}, "on_hand": sorted(on_hand)}
        cur = slot_part[slot]
        cur_r = st["parts"][cur]["rating"] if cur else 0
        if cur_r >= 5:
            return None
        goal = {"slot": slot, "min_rating": rng.randint(cur_r + 1, 5)}
        return {"state": state, "goal": goal}
    items = sorted(st["recipes"])
    resources = sorted({v["resource"] for v in st["sources"].values()})
    state = {"have": sorted(rng.sample(resources, rng.randint(0, 2))),
             "permits": sorted(rng.sample(sorted(st["permits"]), rng.randint(0, 1))),
             "out_of_stock": sorted(rng.sample(sorted(st["sources"]), rng.randint(0, 1)))}
    return {"state": state, "goal": {"item": rng.choice(items)}}


# ---------------------------------------------------------------- flips, irrelevant changes, corrections

def _plan_steps(plan, kind):
    return [s for s in plan if s[0] == kind]


def flip(fam, kind, st, q, plan, rng):
    b = copy.deepcopy(q)
    s, g = b["state"], b["goal"]
    if fam == "delivery":
        if kind == "already":
            if s["item_at"][g["item"]] == "held":
                return None
            s["item_at"][g["item"]] = g["place"]
        elif kind == "closed":
            gos = _plan_steps(plan, "go")
            if not gos:
                return None
            _, x, y = rng.choice(gos)
            s["closed"] = s["closed"] + [[x, y]]
        elif kind == "elsewhere":
            opts = [p for p in st["places"] if p not in (g["place"], s["item_at"][g["item"]])]
            s["item_at"][g["item"]] = rng.choice(opts)
        elif kind == "goalplace":
            opts = [p for p in st["places"] if p not in (g["place"], s["item_at"][g["item"]])]
            g["place"] = rng.choice(opts)
    elif fam == "assembly":
        slot = g["slot"]
        if kind == "already":
            good = [p for p, v in st["parts"].items() if v["rating"] >= g["min_rating"]
                    and v["type"] == st["slots"][slot] and p not in s["slot_part"].values()]
            if not good or s["slot_adapter"][slot]:
                return None
            p = rng.choice(sorted(good))
            if s["slot_part"][slot]:
                s["on_hand"] = sorted(s["on_hand"] + [s["slot_part"][slot]])
            s["slot_part"][slot] = p
            s["on_hand"] = sorted(x for x in s["on_hand"] if x != p)
        elif kind == "rating":
            cur = s["slot_part"][slot]
            lo = (st["parts"][cur]["rating"] + 1) if cur else 1
            opts = [r for r in range(lo, 6) if r != g["min_rating"]]
            if not opts:
                return None
            g["min_rating"] = rng.choice(opts)
        elif kind == "onhand":
            pool = [x for x in list(st["parts"]) + list(st["adapters"]) if x not in s["slot_part"].values()]
            x = rng.choice(sorted(pool))
            s["on_hand"] = sorted(set(s["on_hand"]) ^ {x})
        elif kind == "occupied":
            if s["slot_part"][slot]:
                s["on_hand"] = sorted(s["on_hand"] + [s["slot_part"][slot]])
                s["slot_part"][slot] = None
            else:
                weak = [p for p, v in st["parts"].items() if v["rating"] < g["min_rating"]
                        and v["type"] == st["slots"][slot] and p not in s["slot_part"].values()]
                if not weak:
                    return None
                p = rng.choice(sorted(weak))
                s["slot_part"][slot] = p
                s["on_hand"] = sorted(x for x in s["on_hand"] if x != p)
    else:
        if kind == "owned":
            gets = _plan_steps(plan, "get")
            if not gets:
                return None
            s["have"] = sorted(set(s["have"]) | {rng.choice(gets)[1]})
        elif kind == "stock":
            gets = _plan_steps(plan, "get")
            if not gets:
                return None
            s["out_of_stock"] = sorted(set(s["out_of_stock"]) | {rng.choice(gets)[2]})
        elif kind == "permit":
            obtains = _plan_steps(plan, "obtain")
            if obtains:
                s["permits"] = sorted(set(s["permits"]) | {obtains[0][1]})
            elif s["permits"]:
                s["permits"] = sorted(set(s["permits"]) - {rng.choice(s["permits"])})
            else:
                return None
        elif kind == "goalitem":
            opts = [i for i in st["recipes"] if i != g["item"]]
            g["item"] = rng.choice(sorted(opts))
    return b


def irrelevant(fam, st, q, rng):
    b = copy.deepcopy(q)
    s, g = b["state"], b["goal"]
    if fam == "delivery":
        others = [i for i in st["items"] if i != g["item"] and s["item_at"][i] != "held"]
        if not others:
            return None
        i = rng.choice(others)
        s["item_at"][i] = rng.choice([p for p in st["places"] if p != s["item_at"][i]])
    elif fam == "assembly":
        pool = [x for x in st["parts"] if x not in s["slot_part"].values()]
        x = rng.choice(sorted(pool))
        s["on_hand"] = sorted(set(s["on_hand"]) ^ {x})
    else:
        resources = sorted({v["resource"] for v in st["sources"].values()})
        x = rng.choice(resources)
        s["have"] = sorted(set(s["have"]) ^ {x})
    return b


def correction(fam, st, q, plan, rng, names_used):
    if fam == "delivery":
        idx = rng.randrange(len(st["roads"]))
        a, b, c = st["roads"][idx]
        new = rng.choice([v for v in range(1, 9) if v != c])
        return {"path": ["roads", idx, 2], "value": new,
                "text": f"the road between {a} and {b} now costs {new}, not {c}."}
    if fam == "assembly":
        p = rng.choice(sorted(st["parts"]))
        if rng.random() < 0.5:
            old = st["parts"][p]["rating"]
            new = rng.choice([v for v in range(1, 6) if v != old])
            return {"path": ["parts", p, "rating"], "value": new,
                    "text": f"part {p} has rating {new}, not {old}."}
        old = st["parts"][p]["type"]
        conns = sorted(set(st["slots"].values()) | {v["type"] for v in st["parts"].values()})
        opts = [c for c in conns if c != old]
        if not opts:
            return None
        new = rng.choice(opts)
        return {"path": ["parts", p, "type"], "value": new,
                "text": f"part {p} has connector {new}, not {old}."}
    src = rng.choice(sorted(st["sources"]))
    old = st["sources"][src]["cost"]
    new = rng.choice([v for v in range(1, 9) if v != old])
    return {"path": ["sources", src, "cost"], "value": new,
            "text": f"source {src} now costs {new}, not {old}."}


# ---------------------------------------------------------------- candidates

def all_steps(fam, st, q):
    g = world.ground(fam, st, q)
    seen, out = set(), []
    for step, *_ in g.actions:
        if step not in seen:
            seen.add(step); out.append(list(step))
    return out


def mutations(fam, st, q, plans, rng, n=60):
    steps = all_steps(fam, st, q)
    out = []
    for _ in range(n):
        p = copy.deepcopy(rng.choice(plans))
        r = rng.random()
        if p and r < 0.3:
            del p[rng.randrange(len(p))]
        elif p and r < 0.55:
            p[rng.randrange(len(p))] = rng.choice(steps)
        elif r < 0.8:
            p.insert(rng.randint(0, len(p)), rng.choice(steps))
        elif len(p) > 1:
            i = rng.randrange(len(p) - 1)
            p[i], p[i + 1] = p[i + 1], p[i]
        if len(p) <= 8:
            out.append(p)
    return out


def ids(rng, n):
    letters = "ACDEFHJKLMNPRTUWXY"
    pool = sorted({rng.choice(letters) + str(rng.randint(2, 9)) for _ in range(40)})
    rng.shuffle(pool)
    return pool[:n]


def build_candidates(fam, st, queries, must, rng):
    """Candidates = the required plans plus distractors (to N_OPTIONS) acceptable in none of the queries."""
    keyed = {json.dumps(p) for p in must}
    if len(keyed) != len(must):
        return None
    bests = [world.ground(fam, st, q).optimum()[0] for q in queries]
    near, far = [], []
    for p in mutations(fam, st, queries[0], must, rng):
        k = json.dumps(p)
        if k in keyed:
            continue
        results = [world.ground(fam, st, q).simulate(p) for q in queries]
        if any(v and c == b for (v, c), b in zip(results, bests)):
            continue
        keyed.add(k)
        (near if any(v for v, _ in results) else far).append(p)
    rng.shuffle(near); rng.shuffle(far)
    need = N_OPTIONS - len(must)
    take_near = min(len(near), (need + 1) // 2)
    distract = near[:take_near] + far[:need - take_near]
    if len(distract) < need:
        distract += near[take_near:take_near + need - len(distract)]
    if len(distract) < need:
        return None
    plans = must + distract
    rng.shuffle(plans)
    return [{"id": i, "plan": p} for i, p in zip(ids(rng, len(plans)), plans)]


def finish(fam, st, q, qid, kind, **extra):
    best, ok, _ = world.judge(fam, st, q)
    q.update({"qid": qid, "kind": kind, "optimal_cost": best, "acceptable": ok}, **extra)
    return q


# ---------------------------------------------------------------- episodes

def _solve(fam, st, q):
    return world.ground(fam, st, q).optimum()


def make_pair(fam, kind, st, rng):
    for _ in range(200):
        a = random_query(fam, st, rng)
        if not a:
            continue
        ca, pa = _solve(fam, st, a)
        if ca is None or ca == 0:
            continue
        b = flip(fam, kind, st, a, pa, rng)
        if not b or b == a:
            continue
        cb, pb = _solve(fam, st, b)
        if cb is None:
            continue
        cands = build_candidates(fam, st, [a, b], [pa, pb], rng)
        if not cands:
            continue
        a["candidates"], b["candidates"] = cands, copy.deepcopy(cands)
        ok_a, ok_b = world.judge(fam, st, a)[1], world.judge(fam, st, b)[1]
        if ok_a and ok_b and not set(ok_a) & set(ok_b):
            return a, b
    return None


def make_single(fam, st, rng, kinds):
    for _ in range(200):
        q = random_query(fam, st, rng)
        if not q:
            continue
        c, p = _solve(fam, st, q)
        if c is None:
            continue
        applied = None
        if kinds and rng.random() < 0.5:
            kind = rng.choice(kinds)
            q2 = flip(fam, kind, st, q, p, rng)
            if q2:
                c2, p2 = _solve(fam, st, q2)
                if c2 is not None:
                    q, p, applied = q2, p2, kind
        cands = build_candidates(fam, st, [q], [p], rng)
        if cands:
            q["candidates"] = cands
            if len(world.judge(fam, st, q)[1]) == 1:
                q["support_flip"] = applied  # recorded coverage; does not consume randomness
                return q
    return None


def make_correction(fam, st, rng):
    for _ in range(300):
        q = random_query(fam, st, rng)
        if not q:
            continue
        c0, p0 = _solve(fam, st, q)
        if c0 is None:
            continue
        corr = correction(fam, st, q, p0, rng, None)
        if not corr:
            continue
        qc = dict(q, correction=corr)
        c1, p1 = _solve(fam, st, qc)
        if c1 is None or p1 == p0:
            continue
        cands = build_candidates(fam, st, [q, qc], [p0, p1], rng)
        if not cands:
            continue
        q["candidates"] = qc["candidates"] = cands
        ok_stale, ok_new = world.judge(fam, st, q)[1], world.judge(fam, st, qc)[1]
        if ok_stale and ok_new and not set(ok_stale) & set(ok_new):
            qc["stale_acceptable"] = ok_stale
            return qc
    return None


# Development-only fixtures covering every scored flip type (David, 2026-11-04): same label pool as
# development, one pair per flip type (four pairs, as in the other splits). The committed sealed set is unchanged.
SPLITS = {"dev": ("dev", "dev"), "sealed": ("sealed", "sealed"), "dev_all": ("dev", "all")}


def flip_kinds(fam, which):
    return FLIPS[fam]["dev"] + FLIPS[fam]["sealed"] if which == "all" else FLIPS[fam][which]


def make_episode(fam, split, index, seed):
    rng = random.Random(seed)
    pool, which = SPLITS[split]
    names = Names(pool, rng)
    st = STATIC[fam](rng, names)
    eid = f"{split.replace('_', '')}-{fam}-{index:03d}"
    kinds = flip_kinds(fam, which)
    queries = []
    per_flip = (2 * PAIRS_PER_FLIP) // len(kinds)
    for k, kind in enumerate(kind for kind in kinds for _ in range(per_flip)):
        pair = make_pair(fam, kind, st, rng)
        if not pair:
            return None
        pid = f"{eid}-p{k}"
        for side, q in zip("AB", pair):
            queries.append(finish(fam, st, q, f"{pid}{side}", "pair", pair_id=pid, side=side, flip=kind))
    for k, base in enumerate([queries[0], queries[4]]):
        for _ in range(100):
            v = irrelevant(fam, st, {"state": base["state"], "goal": base["goal"]}, rng)
            if not v or v["state"] == base["state"]:
                continue
            v["candidates"] = copy.deepcopy(base["candidates"])
            best, ok, _ = world.judge(fam, st, v)
            if ok == base["acceptable"] and best == base["optimal_cost"]:
                queries.append(finish(fam, st, v, f"{eid}-i{k}", "irrelevant", base_qid=base["qid"]))
                break
        else:
            return None
    for k in range(2):
        qc = make_correction(fam, st, rng)
        if not qc:
            return None
        stale = qc.pop("stale_acceptable")
        queries.append(finish(fam, st, qc, f"{eid}-c{k}", "correction", stale_acceptable=stale))
    sigs = {json.dumps([q["state"], q["goal"]], sort_keys=True) for q in queries}
    support = []
    while len(support) < SUPPORT_N:
        q = make_single(fam, st, rng, kinds)
        if not q:
            return None
        sig = json.dumps([q["state"], q["goal"]], sort_keys=True)
        if sig in sigs:
            continue
        sigs.add(sig)
        q = finish(fam, st, q, f"{eid}-s{len(support)}", "support")
        q["answer"] = q["acceptable"][0]
        support.append(q)
    for q in queries + support:
        q.setdefault("correction", None)
    return {"episode_id": eid, "family": fam, "split": split, "seed": seed,
            "world_name": f"{names.word()} district", "static": st, "support": support, "queries": queries}


# ---------------------------------------------------------------- V1.6.2 harder support (12 examples)

def harder_support(ep, seed):
    """Replace an episode's worked examples; its scored questions are untouched.

    Composition (David, 2026-11-04): one verified fact-flip pair (both sides, shared options) for every flip
    type scored in the episode, two worked corrections scoped to their own example, two ordinary examples.
    Drawn from an independent random stream; no support situation repeats a scored one or another support one.
    Every support example has exactly one acceptable option.
    """
    from .keycheck import situation
    rng = random.Random(seed)
    fam, st, eid = ep["family"], ep["static"], ep["episode_id"]
    kinds = sorted({q["flip"] for q in ep["queries"] if q.get("flip")}, key=lambda k: flip_order(fam).index(k))
    taken = {situation(q) for q in ep["queries"]}
    support = []

    def fresh(q):
        return situation(q) not in taken

    for k, kind in enumerate(kinds):
        for _ in range(100):
            pair = make_pair(fam, kind, st, rng)
            if not pair or not all(fresh(q) for q in pair) or situation(pair[0]) == situation(pair[1]):
                continue
            done = [finish(fam, st, q, f"{eid}-sp{k}{side}", "support", support_flip=kind, support_pair=f"{eid}-sp{k}")
                    for side, q in zip("AB", pair)]
            if all(len(q["acceptable"]) == 1 for q in done):
                break
        else:
            return None
        for q in done:
            q["answer"] = q["acceptable"][0]; q.setdefault("correction", None)
            taken.add(situation(q)); support.append(q)
    for k in range(2):
        for _ in range(100):
            qc = make_correction(fam, st, rng)
            if not qc or not fresh(qc):
                continue
            qc.pop("stale_acceptable")
            qc["correction"] = dict(qc["correction"], scope="example")
            q = finish(fam, st, qc, f"{eid}-sc{k}", "support", support_flip="correction")
            if len(q["acceptable"]) == 1:
                break
        else:
            return None
        q["answer"] = q["acceptable"][0]
        taken.add(situation(q)); support.append(q)
    for k in range(2):
        for _ in range(100):
            q = make_single(fam, st, rng, [])
            if q and fresh(q):
                break
        else:
            return None
        q = finish(fam, st, q, f"{eid}-so{k}", "support")
        q["answer"] = q["acceptable"][0]; q["correction"] = None
        taken.add(situation(q)); support.append(q)
    order = list(range(len(support)))
    rng.shuffle(order)  # presentation order in the packet; pair sides need not be adjacent
    return [support[i] for i in order]


def flip_order(fam):
    return FLIPS[fam]["dev"] + FLIPS[fam]["sealed"]


def with_harder_support(ep, base_seed):
    """Return a copy of ``ep`` with the 12-example support set; retries with a new support seed if needed."""
    for attempt in range(50):
        h = hashlib.sha256(f"support-v2|{base_seed}|{ep['episode_id']}|{attempt}".encode()).hexdigest()
        new = harder_support(ep, int(h[:12], 16))
        if new:
            out = copy.deepcopy(ep)
            out["support"] = new
            out["support_design"] = {"version": "s12", "seed_base": base_seed, "attempt": attempt}
            return out
    raise RuntimeError(f"could not build harder support for {ep['episode_id']}")


def episode_seed(base, split, fam, index, attempt):
    h = hashlib.sha256(f"{base}|{split}|{fam}|{index}|{attempt}".encode()).hexdigest()
    return int(h[:12], 16)


def generate_split(split, per_family, base_seed):
    episodes = []
    for fam in ("delivery", "assembly", "workshop"):
        for i in range(per_family):
            for attempt in range(50):
                ep = make_episode(fam, split, i, episode_seed(base_seed, split, fam, i, attempt))
                if ep:
                    ep["generation_attempt"] = attempt
                    episodes.append(ep)
                    break
            else:
                raise RuntimeError(f"could not generate {split} {fam} {i}")
    return episodes
