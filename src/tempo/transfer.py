"""V1.10.0 deferred-goal transfer: one stored history, two eligible public goals.

World: worlds.make_world, unchanged (so the extraction prompt is built exactly as in 1.8.2/1.9.1: the printed
fixed facts, rules and domain statements; no goal line). Six public reports received by DECIDE=12.

Two eligible goals per world, fixed before any extraction (by the episode specification, never by outputs):
  A, the familiar role: the 1.9.x episode-type histories (false_block, false_permission, provisional_correct,
     verified_settled, unresolved, no_plan, corrected) on the 1.9.x goal family.
       delivery: crate EA rests at G (EA is crate X or crate Y, counterbalanced 6/6 per domain);
       assembly: slot T holds a part rated >= the printed minimum (candidate part G, orderable).
  B, the alternate goal: an independent target whose stored facts are kept like the 1.9.x padding (an observation
     of the entity followed by events by other workers / teams / technicians), with declared B types:
       b_changed (4), b_delayed (2: a verified report about an earlier time arrives after a later change),
       b_prov_false (2) and b_prov_true (1) (the target's only report is a provisional observation; the frozen
       renderers have no provisional-event wording, so a provisional event is not used), b_unresolved (2: the last
       event's result was not recorded), b_corrected (1: a provisional observation withdrawn by a verified
       correction).
       delivery: crate EB (the other of X/Y) rests at G;
       assembly: slot S2 holds a part rated >= m2 (candidate part D, not orderable). m2 is drawn so that D
       qualifies and exactly one of S2's other two parts (E, E2) does; the world is redrawn otherwise.
  Every B target is fully specified by the public domain: crates are listed and portable, places and roads are
  listed; slot S2's connector and parts D/E/E2's connectors and ratings are printed fixed facts.
The A base reports name only A's facts (and, in delivery, crate Z); B's facts never appear in A's reports.
Padding (new entities, unchanged generator) fills the remaining reports.

Hidden truth: every verified report is true; uncorrected provisional reports are true or false as the type says;
an unrecorded result takes a seeded value. The world is stable after DECIDE.
"""
import copy
import hashlib
import random

from . import assertions as A, engine_fixtures as EF, generate as G, goals as GL, history as Hm, policy as P, worlds
from .worlds import EMPTY, NO, YES

DECIDE, N_REPORTS = P.DECIDE, P.N_REPORTS
A_ALLOC = dict(P.ALLOC)
B_TYPES = ["b_changed", "b_delayed", "b_prov_false", "b_prov_true", "b_unresolved", "b_corrected"]
B_ALLOC = {"b_changed": 4, "b_delayed": 2, "b_prov_false": 2, "b_prov_true": 1, "b_unresolved": 2, "b_corrected": 1}
CONS = {"goaltr": "bdgkmtz", "goaltrsmoke": "fhlnprs", "deprec": "dgknstv", "deprecsmoke": "bfhlprz"}  # 1.11.0 adds deprec*
R = G.R


class Names4(P.Names4):
    def __init__(self, pool, rng):
        self.rng, self.cons, self.used = rng, CONS[pool], set()


# ------------------------------------------------------------------ A base (1.9.x types; only A's facts + crate Z)

def base_a(w, etype, rng, item):
    """(records, accepted relevant values, true relevant values) -- policy._base with A's own init only."""
    if w.domain == "delivery":
        F, you, b, c = f"{item}.location", w.you, w.b, w.c
        others = {f"{w.z}.location": rng.choice(w.places)}
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
        raise ValueError(etype)
    T, S_ = w.slot_f, w.stock_f
    init = lambda t, s, status: R("initial", 0, 0, {"assign": {T: t, S_: s}}, status=status, key="init")
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


# ------------------------------------------------------------------ B histories

def _times(rng, n, lo=1, hi=10, gap=(1, 3)):
    while True:
        t = [rng.randint(lo, lo + 2)]
        for _ in range(n - 1):
            t.append(t[-1] + rng.randint(*gap))
        if t[-1] <= hi:
            return t


def base_b_delivery(w, btype, j, rng, item):
    F, you, b, c, g = f"{item}.location", w.you, w.b, w.c, w.g
    obs = lambda t, v, status="verified", key=None, recv=None: R("observation", t, t if recv is None else recv,
                                                                  {"field": F, "value": v}, status=status, key=key)
    mv = lambda t, frm, to, status="verified": R("change", t, t, {"field": F, "from": frm, "to": to}, status=status)
    if btype == "b_changed":
        final = [you, b, g, c][j]
        if rng.random() < 0.5:
            t0, t1 = _times(rng, 2)
            v0 = rng.choice([p for p in w.places if p != final])
            return [obs(t0, v0), mv(t1, v0, final)], {F: final}, {F: final}
        t0, t1, t2 = _times(rng, 3)
        v1 = rng.choice([p for p in w.places if p != final])
        v0 = rng.choice([p for p in w.places if p != v1])
        return [obs(t0, v0), mv(t1, v0, v1), mv(t2, v1, final)], {F: final}, {F: final}
    if btype == "b_delayed":
        final = [you, b][j]
        t0, t1 = _times(rng, 2, gap=(2, 4))
        v0 = rng.choice([p for p in w.places if p != final])
        te = rng.randint(t0 + 1, t1 - 1)
        return [obs(t0, v0), mv(t1, v0, final), obs(te, v0, recv=min(DECIDE - 1, t1 + rng.randint(1, 3)))], \
            {F: final}, {F: final}
    if btype == "b_prov_true":
        return [obs(rng.randint(1, 6), b, "provisional")], {F: b}, {F: b}
    if btype == "b_prov_false":
        said, true = [(you, b), (c, you)][j]
        return [obs(rng.randint(1, 6), said, "provisional")], {F: said}, {F: true}
    if btype == "b_unresolved":
        t0, t1 = _times(rng, 2)
        opts = rng.sample([you, b], 2)
        return [obs(t0, c), R("uncertain_change", t1, t1, {"field": F, "from": c, "options": opts})], \
            {F: "unknown"}, {F: rng.choice(opts)}
    if btype == "b_corrected":
        t0, t1 = _times(rng, 2, gap=(2, 4))
        u = rng.choice([c, you]); v = b
        return [obs(t0, u, "provisional", key="bobs"),
                R("correction", None, t1, {"target": "bobs", "field": F, "value": v, "valid_from": t0,
                                           "valid_to": None})], {F: v}, {F: v}
    raise ValueError(btype)


def base_b_assembly(w, btype, j, rng, hi, lo):
    S2, D = w.side, f"{w.d}.on_hand"
    obs = lambda f, t, v, status="verified", key=None, recv=None: R("observation", t, t if recv is None else recv,
                                                                     {"field": f, "value": v}, status=status, key=key)
    mv = lambda f, t, frm, to, status="verified": R("change", t, t, {"field": f, "from": frm, "to": to}, status=status)
    ts = rng.randint(1, 4)  # slot observation time
    if btype == "b_changed":
        if j == 0:   # install
            t0, t1 = _times(rng, 2)
            return [obs(S2, ts, EMPTY), obs(D, t0, NO), mv(D, t1, NO, YES)], {S2: EMPTY, D: YES}, {S2: EMPTY, D: YES}
        if j == 1:   # remove_install
            t1 = ts + rng.randint(1, 4)
            return [obs(S2, ts, EMPTY), mv(S2, t1, EMPTY, lo), obs(D, rng.randint(1, 6), YES)], \
                {S2: lo, D: YES}, {S2: lo, D: YES}
        if j == 2:   # already holds
            t1 = ts + rng.randint(1, 4)
            dv = rng.choice([YES, NO])
            return [obs(S2, ts, EMPTY), mv(S2, t1, EMPTY, hi), obs(D, rng.randint(1, 6), dv)], \
                {S2: hi, D: dv}, {S2: hi, D: dv}
        t0, t1 = _times(rng, 2)  # no plan: D taken away
        return [obs(S2, ts, EMPTY), obs(D, t0, YES), mv(D, t1, YES, NO)], {S2: EMPTY, D: NO}, {S2: EMPTY, D: NO}
    if btype == "b_delayed":
        sv = [EMPTY, lo][j]
        t0, t1 = _times(rng, 2, gap=(2, 4))
        te = rng.randint(t0 + 1, t1 - 1)
        return [obs(S2, ts, sv), obs(D, t0, NO), mv(D, t1, NO, YES),
                obs(D, te, NO, recv=min(DECIDE - 1, t1 + rng.randint(1, 3)))], {S2: sv, D: YES}, {S2: sv, D: YES}
    if btype == "b_prov_true":
        return [obs(S2, ts, EMPTY), obs(D, rng.randint(1, 6), YES, "provisional")], \
            {S2: EMPTY, D: YES}, {S2: EMPTY, D: YES}
    if btype == "b_prov_false":
        said, true = [(YES, NO), (NO, YES)][j]
        return [obs(S2, ts, EMPTY), obs(D, rng.randint(1, 6), said, "provisional")], \
            {S2: EMPTY, D: said}, {S2: EMPTY, D: true}
    if btype == "b_unresolved":
        t0, t1 = _times(rng, 2)
        frm = rng.choice([YES, NO])
        return [obs(S2, ts, EMPTY), obs(D, t0, frm),
                R("uncertain_change", t1, t1, {"field": D, "from": frm, "options": rng.sample([YES, NO], 2)})], \
            {S2: EMPTY, D: "unknown"}, {S2: EMPTY, D: rng.choice([YES, NO])}
    if btype == "b_corrected":
        t0, t1 = _times(rng, 2, gap=(2, 4))
        return [obs(S2, ts, EMPTY), obs(D, t0, NO, "provisional", key="bobs"),
                R("correction", None, t1, {"target": "bobs", "field": D, "value": YES, "valid_from": t0,
                                           "valid_to": None})], {S2: EMPTY, D: YES}, {S2: EMPTY, D: YES}
    raise ValueError(btype)


# ------------------------------------------------------------------ episode

def _assembly_b_goal(w, rng):
    """m2 such that D qualifies and exactly one of E, E2 does; None if impossible (the world is redrawn)."""
    rd = w.parts[w.d]["rating"]
    re_, re2 = w.parts[w.e]["rating"], w.parts[w.e2]["rating"]
    lo_r, hi_r = min(re_, re2), max(re_, re2)
    cands = [m for m in range(lo_r + 1, min(hi_r, rd) + 1)]
    if not cands or re_ == re2:
        return None
    m2 = rng.choice(cands)
    hi, lo = (w.e, w.e2) if re_ > re2 else (w.e2, w.e)
    return m2, hi, lo


def build(eid, domain, a_type, b_type, b_j, a_item_is_x, seed, pool):
    """(world object, episode dict). Raises AssertionError for a rejected draw (the caller redraws)."""
    rng = random.Random(seed)
    names = Names4(pool, rng)
    w = worlds.make_world(domain, rng, names, "slot" if domain == "assembly" else None)
    if domain == "delivery":
        ia, ib = (w.x, w.y) if a_item_is_x else (w.y, w.x)
        goal_a = {"kind": "deliver", "item": ia, "place": w.g}
        goal_b = {"kind": "deliver", "item": ib, "place": w.g}
        base, acc_a, tr_a = base_a(w, a_type, rng, ia)
        bb, acc_b, tr_b = base_b_delivery(w, b_type, b_j, rng, ib)
    else:
        g = _assembly_b_goal(w, rng)
        if g is None:
            raise AssertionError("no admissible m2 for goal B")
        m2, hi, lo = g
        goal_a = {"kind": "fill", "slot": w.t, "min_rating": w.min_rating, "part": w.g}
        goal_b = {"kind": "fill", "slot": w.s2, "min_rating": m2, "part": w.d}
        base, acc_a, tr_a = base_a(w, a_type, rng, None)
        bb, acc_b, tr_b = base_b_assembly(w, b_type, b_j, rng, hi, lo)
    n_pad = N_REPORTS - len(base) - len(bb)
    if n_pad < 0:
        raise AssertionError("too many base reports")
    chains = G.padding_chains(w, rng, max(n_pad, 1))
    recs = G.finalize(base + bb + copy.deepcopy(G.take_padding(chains, n_pad)))
    G.check_no_ties(recs)
    if any(r["received_at"] > DECIDE for r in recs):
        raise AssertionError("report after the decision time")
    reports = [A.from_v02(EF.public_record(r)) for r in recs]
    spec = EF.spec_from_world(vars(w), domain, recs)
    eng = A.AssertionEngine(spec, eid)
    for r in reports:
        eng.ingest(r)
    view = eng.view("current", DECIDE)
    if view["conflict_fields"] or view["incomplete_fields"]:
        raise AssertionError("structured history has a conflict or incomplete field")
    for f, v in {**acc_a, **acc_b}.items():
        if view["per_field"][f] != v:
            raise AssertionError(f"accepted {f} = {view['per_field'][f]}, intended {v}")
    truth = {f: v for f, v in view["per_field"].items() if v not in ("unknown", "conflict")}
    truth.update(tr_a); truth.update(tr_b)
    if domain == "delivery":
        truth["agent.at"] = w.you
    allowed = {f: Hm.allowed_values(w, f) for f in Hm.registry_fields(w, recs)}
    world = {k: v for k, v in vars(w).items() if k != "pad_names"}
    gcs = {"A": GL.context(world, domain, goal_a, allowed), "B": GL.context(world, domain, goal_b, allowed)}
    if set(gcs["A"]["relevant"]) & set(gcs["B"]["relevant"]):
        raise AssertionError("goals share a relevant field")
    for k in ("A", "B"):
        for f in gcs[k]["relevant"]:
            if f not in truth:
                raise AssertionError(f"no truth for relevant {f}")
    ep = {"episode_id": eid, "domain": domain, "type": a_type, "a_type": a_type, "b_type": b_type, "b_j": b_j,
          "a_item_is_x": a_item_is_x, "seed": seed, "pool": pool, "world": world, "spec": spec, "reports": reports,
          "records_v02": recs, "truth": truth, "registry_allowed": allowed,
          "goals": {k: gcs[k]["goal"] for k in gcs}, "accepted_relevant": {"A": acc_a, "B": acc_b}}
    return w, ep


def goal_context(ep, role):
    return GL.context(ep["world"], ep["domain"], ep["goals"][role], ep["registry_allowed"])


def goal_episode(ep, role):
    """The isolated per-goal copy of the episode handed to the controller (policy.run_policy-compatible keys)."""
    out = copy.deepcopy({k: v for k, v in ep.items() if k not in ("goals", "accepted_relevant")})
    gc = goal_context(ep, role)
    out.update(episode_id=f"{ep['episode_id']}|{role}", group_id=ep["episode_id"], goal_role=role,
               type=ep["a_type"] if role == "A" else ep["b_type"], relevant=gc["relevant"])
    return out, gc


def episode_specs(pool, base_seed):
    """24 worlds: 12 per domain; A types by policy.ALLOC, B types by B_ALLOC, paired by a seeded permutation;
    delivery A item X/Y alternating within the pairing (6/6 per domain)."""
    out = []
    for domain in ("delivery", "assembly"):
        a_list = [(t, j) for t in P.TYPES for j in range(A_ALLOC[t])]
        b_list = [(t, j) for t in B_TYPES for j in range(B_ALLOC[t])]
        prng = random.Random(int(hashlib.sha256(f"{base_seed}|{pool}|{domain}|pairing".encode()).hexdigest()[:12], 16))
        prng.shuffle(b_list)
        xs = [True] * 6 + [False] * 6
        prng.shuffle(xs)
        for n, ((at, aj), (bt, bj)) in enumerate(zip(a_list, b_list)):
            eid = f"{pool}-{domain[:3]}-{at}-{aj}"
            seed = int(hashlib.sha256(f"{base_seed}|{eid}".encode()).hexdigest()[:12], 16)
            out.append({"episode_id": eid, "domain": domain, "a_type": at, "b_type": bt, "b_j": bj,
                        "a_item_is_x": xs[n] if domain == "delivery" else True, "seed": seed})
    return out
