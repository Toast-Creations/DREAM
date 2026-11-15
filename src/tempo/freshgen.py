"""V1.12.0 generated panel: 24 fresh base worlds (12 per domain), two goals each, a public transition declaration
and a hidden event tape per world. Structured, meaning-correct evidence only (every report is true; provisional
and unresolved reports carry the true value, so the initial support contains the actual initial state).

The case allocation below is fixed before any trace exists (it is part of the frozen plan). Per world it gives
each goal's evidence status for its relevant facts (which decides P2's request under the frozen rule:
"prov" = a correct provisional observation, "unres:X" = a verified observation followed by an event whose result
was not recorded, options {true value, X}; "ver" = a verified observation), the declared transitions, and the
realized tape [(transition index, elapsed time)]. Labels are the intended goal dependence (hidden; scoring only).

Value tokens. delivery: YOU, B, C, G (places), crates EA (goal A's crate), EB (goal B's), Z (a third crate).
assembly: T (goal A's slot), G (A's part, orderable), W (low-rated part fitting T), S2 (B's slot), D (B's part),
HI / LO (the S2-compatible part that does / does not qualify for B).
"""
import copy
import hashlib
import random

from . import assertions as A, engine_fixtures as EF, generate as G, goals as GL, history as Hm, recovery as R, \
    transfer as T, worlds
from .worlds import EMPTY, NO, YES

N_MIN_REPORTS = 6
CONS = {"fresh": "cdjlmrv", "freshsmoke": "bgknptz"}

DELIVERY = [
    # id, A crate (truth, status), B crate (truth, status), transitions [(crate, from, to)], realized, labels
    ("d01", ("B", "prov"), ("YOU", "prov"), [("EA", "B", "C")], [(0, 0.5)], ("loss_realized", "irrelevant")),
    ("d02", ("B", "prov"), ("G", "unres:C"), [("EA", "B", "C")], [], ("loss_possible_no_change", "irrelevant")),
    ("d03", ("YOU", "unres:B"), ("B", "prov"), [("EA", "YOU", "G")], [(0, 1.5)], ("loss_realized", "irrelevant")),
    ("d04", ("YOU", "prov"), ("B", "prov"), [("EB", "B", "YOU")], [], ("irrelevant", "loss_possible_no_change")),
    ("d05", ("C", "prov"), ("YOU", "prov"), [("EA", "C", "YOU")], [(0, 0.5)], ("gain_realized", "irrelevant")),
    ("d06", ("C", "prov"), ("B", "unres:YOU"), [("EA", "C", "G")], [], ("gain_possible_no_change", "irrelevant")),
    ("d07", ("G", "prov"), ("C", "prov"), [("EB", "C", "B")], [(0, 1.5)], ("irrelevant", "gain_realized")),
    ("d08", ("YOU", "prov"), ("YOU", "prov"), [("EA", "B", "C"), ("EB", "YOU", "C")], [(1, 0.5)],
     ("preserved_guard_false", "loss_realized")),
    ("d09", ("B", "unres:C"), ("G", "prov"), [("Z", "ZV", "ZO")], [(0, 0.5)], ("irrelevant", "irrelevant")),
    ("d10", ("YOU", "prov"), ("B", "prov"), [("EA", "YOU", "B"), ("EB", "B", "YOU")], [(0, 0.5), (1, 1.5)],
     ("loss_realized", "loss_realized")),
    ("d11", ("G", "unres:C"), ("YOU", "prov"), [("EA", "G", "C")], [], ("loss_possible_no_change", "irrelevant")),
    ("d12", ("B", "prov"), ("C", "unres:G"), [("EB", "C", "G")], [(0, 1.5)], ("irrelevant", "gain_realized")),
]

ASSEMBLY = [
    # id, A {T, G}, B {S2, D}, transitions, realized, labels
    ("a01", {"T": ("empty", "ver"), "G": ("yes", "prov")}, {"S2": ("empty", "prov"), "D": ("yes", "prov")},
     [("on_hand", "G", "yes", "no")], [(0, 0.5)], ("loss_realized", "irrelevant")),
    ("a02", {"T": ("empty", "unres:W"), "G": ("yes", "ver")}, {"S2": ("LO", "ver"), "D": ("yes", "prov")},
     [("install", "T", "W")], [], ("loss_possible_no_change", "irrelevant")),
    ("a03", {"T": ("empty", "ver"), "G": ("yes", "prov")}, {"S2": ("empty", "ver"), "D": ("no", "prov")},
     [("install", "T", "W")], [(0, 1.5)], ("unqueried_loss_realized", "irrelevant")),
    ("a04", {"T": ("W", "ver"), "G": ("yes", "prov")}, {"S2": ("HI", "prov"), "D": ("yes", "ver")},
     [("remove", "T", "W")], [], ("unqueried_loss_possible_no_change", "irrelevant")),
    ("a05", {"T": ("empty", "prov"), "G": ("no", "prov")}, {"S2": ("empty", "ver"), "D": ("yes", "prov")},
     [("on_hand", "G", "no", "yes")], [(0, 0.5)], ("loss_realized_opens_other", "irrelevant")),
    ("a06", {"T": ("G", "prov"), "G": ("no", "ver")}, {"S2": ("empty", "prov"), "D": ("no", "ver")},
     [("on_hand", "G", "no", "yes"), ("on_hand", "D", "no", "yes")], [(0, 0.5), (1, 1.5)],
     ("preserved_effect_irrelevant", "gain_realized")),
    ("a07", {"T": ("empty", "ver"), "G": ("yes", "prov")}, {"S2": ("empty", "prov"), "D": ("yes", "ver")},
     [("install", "S2", "LO")], [], ("irrelevant", "loss_possible_no_change")),
    ("a08", {"T": ("W", "prov"), "G": ("yes", "ver")}, {"S2": ("empty", "prov"), "D": ("yes", "ver")},
     [("install", "S2", "HI")], [(0, 0.5)], ("irrelevant", "loss_realized_opens_other")),
    ("a09", {"T": ("W", "prov"), "G": ("yes", "ver")}, {"S2": ("LO", "unres:HI"), "D": ("yes", "prov")},
     [("remove", "T", "W"), ("on_hand", "D", "yes", "no")], [(0, 1.5)], ("loss_realized", "loss_possible_no_change")),
    ("a10", {"T": ("G", "ver"), "G": ("no", "prov")}, {"S2": ("HI", "prov"), "D": ("no", "ver")},
     [("return", "T", "G")], [(0, 0.5)], ("unqueried_correlated_loss_realized", "irrelevant")),
    ("a11", {"T": ("empty", "prov"), "G": ("yes", "prov")}, {"S2": ("HI", "prov"), "D": ("no", "ver")},
     [("remove", "S2", "HI")], [], ("irrelevant", "loss_possible_no_change")),
    ("a12", {"T": ("empty", "ver"), "G": ("no", "prov")}, {"S2": ("empty", "ver"), "D": ("yes", "prov")},
     [("install", "T", "W")], [(0, 0.5)], ("unqueried_loss_realized", "irrelevant")),
]

SMOKE_D = [("s-d1", ("B", "prov"), ("YOU", "unres:B"), [("EA", "B", "G")], [(0, 1.5)], ("smoke", "smoke")),
           ("s-d2", ("YOU", "prov"), ("C", "prov"), [("EB", "C", "YOU")], [], ("smoke", "smoke"))]
SMOKE_A = [("s-a1", {"T": ("empty", "prov"), "G": ("yes", "ver")}, {"S2": ("empty", "ver"), "D": ("yes", "prov")},
            [("on_hand", "D", "yes", "no")], [(0, 0.5)], ("smoke", "smoke")),
           ("s-a2", {"T": ("W", "ver"), "G": ("yes", "prov")}, {"S2": ("HI", "prov"), "D": ("no", "ver")},
            [("return", "T", "G")], [], ("smoke", "smoke"))]


class Names(T.Names4):
    def __init__(self, pool, rng):
        self.rng, self.cons, self.used = rng, CONS[pool], set()


def _chain(rng, f, truth, status, others, t_lo=1):
    """Records for one fact; all true. others: values the field may take besides the truth (for histories)."""
    obs = lambda t, v, st="verified": G.R("observation", t, t, {"field": f, "value": v}, status=st)
    t0 = rng.randint(t_lo, 5)
    if status == "prov":
        return [obs(rng.randint(t_lo, 9), truth, "provisional")]
    if status == "ver":
        if rng.random() < 0.5:
            return [obs(t0, truth)]
        v0 = rng.choice([o for o in others if o != truth])
        return [obs(t0, v0), G.R("change", t0 + rng.randint(1, 4), None, {"field": f, "from": v0, "to": truth})]
    if status.startswith("unres:"):
        alt = status.split(":")[1]
        v0 = rng.choice([o for o in others if o not in (truth, alt)])
        t1 = t0 + rng.randint(1, 4)
        return [obs(t0, v0), G.R("uncertain_change", t1, t1, {"field": f, "from": v0, "options": rng.sample([truth, alt], 2)})]
    raise ValueError(status)


def _fix_recv(recs):
    for r in recs:
        if r["received_at"] is None:
            r["received_at"] = r["event_at"]
    return recs


def build(spec_row, domain, seed, pool):
    rng = random.Random(seed)
    names = Names(pool, rng)
    w = worlds.make_world(domain, rng, names, "slot" if domain == "assembly" else None)
    wid, sa, sb, trs, tape, labels = spec_row
    if domain == "delivery":
        ia, ib = (w.x, w.y) if rng.random() < 0.5 else (w.y, w.x)
        tok = {"YOU": w.you, "B": w.b, "C": w.c, "G": w.g}
        crate = {"EA": ia, "EB": ib, "Z": w.z}
        zv = rng.choice(w.places)
        tok.update(ZV=zv, ZO=rng.choice([p for p in w.places if p != zv]))
        truth_vals = {f"{ia}.location": tok[sa[0]], f"{ib}.location": tok[sb[0]], f"{w.z}.location": zv}
        status = {f"{ia}.location": sa[1], f"{ib}.location": sb[1], f"{w.z}.location": "ver"}
        alt = lambda st: st if ":" not in st else "unres:" + tok[st.split(":")[1]]
        recs = []
        for f in truth_vals:
            recs += _chain(rng, f, truth_vals[f], alt(status[f]), list(w.places))
        goals = {"A": {"kind": "deliver", "item": ia, "place": w.g}, "B": {"kind": "deliver", "item": ib, "place": w.g}}
        decl = []
        for n, (c, frm, to) in enumerate(trs, 1):
            f = f"{crate[c]}.location"
            decl.append({"id": f"x{n}", "text": f"another worker may move crate {crate[c]} from {tok[frm]} to {tok[to]}",
                         "guard": {f: tok[frm]}, "effect": {f: tok[to]},
                         "window": {"from": "requested_at", "to": "execute_at"}, "max_occurrences": 1})
    else:
        g = T._assembly_b_goal(w, rng)
        if g is None:
            raise AssertionError("no admissible m2 for goal B")
        m2, hi, lo = g
        tok = {"empty": EMPTY, "yes": YES, "no": NO, "W": w.w, "G": w.g, "HI": hi, "LO": lo, "D": w.d}
        fT, fG, fS, fD = f"{w.t}.part", f"{w.g}.on_hand", f"{w.s2}.part", f"{w.d}.on_hand"
        fmap = {"T": fT, "G": fG, "S2": fS, "D": fD}
        others = {fT: [EMPTY, w.w, w.g], fG: [YES, NO], fS: [EMPTY, w.e, w.e2], fD: [YES, NO]}
        truth_vals, status = {}, {}
        for side in (sa, sb):
            for k, (v, st) in side.items():
                truth_vals[fmap[k]] = tok[v]
                status[fmap[k]] = st if ":" not in st else "unres:" + tok[st.split(":")[1]]
        recs = []
        for f in truth_vals:
            st = status[f]
            if st == "ver" and f.endswith(".on_hand"):
                recs += _chain(rng, f, truth_vals[f], st, others[f])
            elif st.startswith("unres:") and f.endswith(".on_hand"):
                raise ValueError("no unresolved on_hand in this allocation")
            else:
                recs += _chain(rng, f, truth_vals[f], st, others[f] if len(others[f]) > 2 else others[f])
        goals = {"A": {"kind": "fill", "slot": w.t, "min_rating": w.min_rating, "part": w.g},
                 "B": {"kind": "fill", "slot": w.s2, "min_rating": m2, "part": w.d}}
        decl = []
        for n, tr in enumerate(trs, 1):
            kind = tr[0]
            if kind == "on_hand":
                f = f"{tok[tr[1]]}.on_hand"
                txt = (f"part {tok[tr[1]]} may be delivered to you (then it is on hand)" if tr[3] == "yes" else
                       f"another team may take part {tok[tr[1]]} away (then it is no longer on hand)")
                d = {"guard": {f: tok[tr[2]]}, "effect": {f: tok[tr[3]]}}
            elif kind == "install":
                f = fmap[tr[1]]
                txt = f"another technician may install part {tok[tr[2]]} in slot {f.split('.')[0]} (from their own stock)"
                d = {"guard": {f: EMPTY}, "effect": {f: tok[tr[2]]}}
            elif kind == "remove":
                f = fmap[tr[1]]
                txt = f"another technician may remove part {tok[tr[2]]} from slot {f.split('.')[0]} and take it away"
                d = {"guard": {f: tok[tr[2]]}, "effect": {f: EMPTY}}
            elif kind == "return":
                f, p = fmap[tr[1]], tok[tr[2]]
                txt = (f"another technician may take part {p} out of slot {f.split('.')[0]} and return it to your "
                       f"stock (then the slot is empty and {p} is on hand)")
                d = {"guard": {f: p, f"{p}.on_hand": NO}, "effect": {f: EMPTY, f"{p}.on_hand": YES}}
            else:
                raise ValueError(kind)
            decl.append(dict({"id": f"x{n}", "text": txt, "window": {"from": "requested_at", "to": "execute_at"},
                              "max_occurrences": 1}, **d))
    recs = _fix_recv(recs)
    n_pad = max(0, N_MIN_REPORTS - len(recs))
    if n_pad:
        recs += copy.deepcopy(G.take_padding(G.padding_chains(w, rng, n_pad), n_pad))
    recs = G.finalize(recs)
    G.check_no_ties(recs)
    if any(r["received_at"] > R.DECIDE for r in recs):
        raise AssertionError("report after the request time")
    reports = [A.from_v02(EF.public_record(r)) for r in recs]
    spec = EF.spec_from_world(vars(w), domain, recs)
    allowed = {f: Hm.allowed_values(w, f) for f in Hm.registry_fields(w, recs)}
    world = {k: v for k, v in vars(w).items() if k != "pad_names"}
    pub = {"world_id": wid, "domain": domain, "spec": spec, "world": world, "reports": reports,
           "registry_allowed": allowed, "goals": goals, "transitions": decl}
    eng = A.AssertionEngine(spec, wid)
    for r in reports:
        eng.ingest(r)
    view = eng.view("current", R.DECIDE)
    if view["conflict_fields"] or view["incomplete_fields"]:
        raise AssertionError("structured history has a conflict or incomplete field")
    truth = {f: v for f, v in view["per_field"].items() if v not in ("unknown", "conflict")}
    for f, v in truth_vals.items():
        if f in truth and truth[f] != v:
            raise AssertionError(f"verified history says {f}={truth[f]}, intended {v}")
        truth[f] = v
    if domain == "delivery":
        truth["agent.at"] = w.you
    hidden = {"world_id": wid, "seed": seed, "truth": truth, "labels": {"A": labels[0], "B": labels[1]},
              "tape": [{"transition": f"x{i + 1}", "elapsed": u} for i, u in tape],
              "intended_status": status, "records_v02": recs}
    return w, pub, hidden


def goal_copy(pub, hidden, role):
    """The isolated per-goal public copy (controller input) and the matching hidden episode (environment)."""
    ep = copy.deepcopy({k: v for k, v in pub.items() if k not in ("goals",)})
    ep.update(episode_id=f"{pub['world_id']}|{role}", group_id=pub["world_id"], goal_role=role)
    gc = R.context(ep, pub["goals"][role])
    env_ep = dict(copy.deepcopy(ep), truth=dict(hidden["truth"]))
    return ep, gc, env_ep


def specs(pool, base_seed, smoke=False):
    rows = [("delivery", r) for r in (SMOKE_D if smoke else DELIVERY)] + \
        [("assembly", r) for r in (SMOKE_A if smoke else ASSEMBLY)]
    out = []
    for domain, r in rows:
        seed = int(hashlib.sha256(f"{base_seed}|{pool}|{r[0]}".encode()).hexdigest()[:12], 16)
        out.append((domain, r, seed))
    return out
