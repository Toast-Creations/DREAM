"""V1.22.0 KEEP+ID confirmation harness core (KIDCONF-v1). No model.

Fresh SUB vs unchanged KEEPID-v1 on fresh F1-F3 groups. This module holds the parts that must be exact and testable:

  allocation   whole groups in blocks of 8 (F1 imm, F1 del, F2 imm, F2 del, F3 imm x2, F3 del x2), so the sampling
               allocation is proportional to the frozen estimand weights F1:F2:F3 = 1:1:2 with balanced reception.
               Correction targets come from every main group; arrival targets come from a predeclared nested subset
               (the first n_arrival/8 blocks in generation order; chosen before generation, outcome-free).
  schedule     one unit per (group, act): SUB and KEEP x histories A and B (4 calls); units in seeded order; the arm
               order inside a unit is seeded per unit. Smoke groups are disjoint (own pool and id prefix), unscored.
  completeness the analyzer refuses to aggregate unless every declared (group, act) has both histories for both arms
               with exactly one ok record each, and no record is outside the schedule (no all(empty) = success).
  statistic    per group-act: D_g = sum over histories of (KEEP exact - SUB exact) in {-2..2} (integer = 2 x group
               difference). Stratified estimate m = sum_s w_s * mean_s(D_g)/2 with w_s = k_s/8, computed EXACTLY as a
               Fraction. Group bootstrap within strata (Python random; draw order = 1.21 kid_analyze.boot).
  rules        "P95" percentile int(.025B) (1.21 rule); "P99" percentile int(.01B); "BT" studentized bootstrap-t with
               normal-quantile floor. All with the SE floor of the planning model. The method, B, seed and margin are
               parameters until the design is approved and frozen.
  gates        decided on unrounded values. Percentile and point comparisons are exact (Fractions). BT lower bounds
               are real: pass iff LB > threshold + EPS (conservative; an exact tie never passes).
"""
import collections
import hashlib
import math
import random
from fractions import Fraction

FAMILIES = ("F1_two_hop", "F2_slot_join", "F3_historical_occupant")
FAMILY_SHORT = {"F1_two_hop": "F1", "F2_slot_join": "F2", "F3_historical_occupant": "F3"}
RECEPTION = ("immediate", "delayed")
BLOCK = (("F1_two_hop", "immediate"), ("F1_two_hop", "delayed"), ("F2_slot_join", "immediate"),
         ("F2_slot_join", "delayed"), ("F3_historical_occupant", "immediate"), ("F3_historical_occupant", "immediate"),
         ("F3_historical_occupant", "delayed"), ("F3_historical_occupant", "delayed"))
WEIGHT = {"F1|immediate": Fraction(1, 8), "F1|delayed": Fraction(1, 8), "F2|immediate": Fraction(1, 8),
          "F2|delayed": Fraction(1, 8), "F3|immediate": Fraction(2, 8), "F3|delayed": Fraction(2, 8)}
ACTS = ("arrival", "correction")
HISTORIES = ("A", "B")
ARMS = ("SUB", "KEEP")
MARGIN = Fraction(3, 64)
EPS = 1e-9
Z975, Z99 = 1.959963984540054, 2.3263478740408408


def stratum(family, reception):
    return f"{FAMILY_SHORT.get(family, family[:2])}|{reception}"


# ------------------------------------------------------------------------------------------------ allocation
def plan(n_groups, id_prefix):
    """Whole groups in generation order: [(gid, family, reception, bits, block_index)]. bits cycle over the four
    (record order, stated prior) settings within each stratum, b2 = 0 (open intervals)."""
    if n_groups <= 0 or n_groups % 8:
        raise ValueError("n_groups must be a positive multiple of 8")
    seen = collections.Counter()
    out = []
    for b in range(n_groups // 8):
        for fam, rec in BLOCK:
            k = seen[(fam, rec)]
            seen[(fam, rec)] += 1
            out.append((f"{id_prefix}{len(out) + 1:04d}", fam, rec, (k & 1, (k >> 1) & 1, 0), b))
    return out


def acts_for(block_index, n_arrival_groups):
    """Correction for every main group; arrival only inside the predeclared nested subset."""
    if n_arrival_groups % 8:
        raise ValueError("n_arrival_groups must be a multiple of 8")
    return ("arrival", "correction") if block_index < n_arrival_groups // 8 else ("correction",)


def allocation_table(groups, n_arrival_groups):
    t = collections.Counter()
    for gid, fam, rec, bits, b in groups:
        for act in acts_for(b, n_arrival_groups):
            t[(act, stratum(fam, rec))] += 1
    return {f"{a}|{s}": n for (a, s), n in sorted(t.items())}


# ------------------------------------------------------------------------------------------------ schedule
def unit_order(units, seed):
    """units: list of lists of calls (one per group-act). Seeded unit shuffle, then a seeded arm order per unit
    (SUB first or KEEP first), histories A then B within an arm."""
    rng = random.Random(seed)
    units = list(units)
    rng.shuffle(units)
    out = []
    for u in units:
        first = rng.choice(ARMS)
        order = sorted(u, key=lambda c: (c["arm"] != first, c["history"]))
        out.extend(order)
    return out


def seed_for(base_seed, pool, gid, attempt):
    return int(hashlib.sha256(f"{base_seed}|{pool}|{gid}|{attempt}".encode()).hexdigest()[:12], 16)


# ------------------------------------------------------------------------------------------------ completeness
class Incomplete(Exception):
    pass


def check_complete(declared, scheduled_ids, records):
    """declared: {(group, act): stratum}; scheduled_ids: set of call ids "<group>|<act>|<hist>|<arm>";
    records: {call_id: record}. Raises Incomplete with the reasons; returns None when complete."""
    want = {f"{g}|{a}|{h}|{arm}" for (g, a) in declared for h in HISTORIES for arm in ARMS}
    problems = []
    if want != set(scheduled_ids):
        problems.append(f"schedule != declared membership ({len(set(scheduled_ids) ^ want)} differ)")
    extra = set(records) - set(scheduled_ids)
    if extra:
        problems.append(f"{len(extra)} records outside the schedule")
    missing = [c for c in sorted(want) if c not in records]
    if missing:
        problems.append(f"{len(missing)} scheduled calls without a record")
    notok = [c for c in sorted(want) if c in records and records[c].get("status") != "ok"]
    if notok:
        problems.append(f"{len(notok)} records not ok")
    if problems:
        raise Incomplete("; ".join(problems))


def pair_table(declared, exact, acts, arms=("KEEP", "SUB")):
    """Per group: D_g = sum over the given acts and both histories of (arm0 exact - arm1 exact); integer.
    declared: {(group, act): stratum}; exact: {(group, act, hist, arm): bool}. A group enters only if EVERY act in
    `acts` is declared for it, and then all its cells must exist (asserted; never an empty-set success).
    Returns ({group: (stratum, D_g)}, k) with k = targets per group per arm (= 2 * len(acts))."""
    acts = tuple(acts)
    groups = sorted({g for (g, a) in declared if all((g, x) in declared for x in acts)})
    out = {}
    for g in groups:
        sts = {declared[(g, a)] for a in acts}
        if len(sts) != 1:
            raise Incomplete(f"{g}: inconsistent stratum {sts}")
        cells = [(g, a, h, arm) for a in acts for h in HISTORIES for arm in arms]
        miss = [c for c in cells if c not in exact]
        if miss:
            raise Incomplete(f"{g}: missing {miss[:4]}")
        d = sum(int(bool(exact[(g, a, h, arms[0])])) - int(bool(exact[(g, a, h, arms[1])])) for a in acts for h in HISTORIES)
        out[g] = (sts.pop(), d)
    if not out:
        raise Incomplete(f"no declared groups for {acts}")
    return out, 2 * len(acts)


def paired_counts(declared, exact, acts, arms=("KEEP", "SUB")):
    """Target-level (both / one only / neither) and history-unit (all histories exact per group-act) counts."""
    A, Bm = arms
    pc, ph = collections.Counter(), collections.Counter()
    tab, _ = pair_table(declared, exact, acts, arms)        # asserts completeness
    for g in tab:
        for a in acts:
            for h in HISTORIES:
                k, s = bool(exact[(g, a, h, A)]), bool(exact[(g, a, h, Bm)])
                pc["both" if k and s else f"{A} only" if k else f"{Bm} only" if s else "neither"] += 1
            k2 = all(bool(exact[(g, a, h, A)]) for h in HISTORIES)
            s2 = all(bool(exact[(g, a, h, Bm)]) for h in HISTORIES)
            ph["both" if k2 and s2 else f"{A} only" if k2 else f"{Bm} only" if s2 else "neither"] += 1
    return dict(pc), dict(ph)


# ------------------------------------------------------------------------------------------------ statistic
class Strata:
    """Sufficient statistics: per stratum the list of integer D_g (insertion order = sorted group id)."""

    def __init__(self, table, weights=WEIGHT, k=2):
        self.k = k
        self.by = collections.OrderedDict()
        for g, (st, d) in table.items():
            if st not in weights:
                raise ValueError(f"unknown stratum {st}")
            self.by.setdefault(st, []).append(int(d))
        self.weights = weights
        if set(self.by) != set(weights):
            raise Incomplete(f"strata present {sorted(self.by)} != weighted strata {sorted(weights)}")
        self.n = {s: len(v) for s, v in self.by.items()}
        # SE if one group per stratum had difference 1/k and the rest 0 (k = 2: d = +-0.5)
        self.floor = math.sqrt(sum(float(weights[s]) ** 2 * (1 / k) ** 2 / self.n[s] ** 2 for s in self.by))

    def mean_exact(self, sums=None):
        sums = sums or {s: sum(v) for s, v in self.by.items()}
        return sum(self.weights[s] * Fraction(sums[s], self.k * self.n[s]) for s in self.by)

    def se(self, vals):
        tot = 0.0
        for s, v in vals.items():
            n = len(v)
            mu = sum(v) / (self.k * n)
            var = sum((x / self.k - mu) ** 2 for x in v) / (n - 1) if n > 1 else 0.0
            tot += float(self.weights[s]) ** 2 * var / n
        return math.sqrt(tot)

    def boot(self, B, seed):
        """Resampled (exact mean, se) pairs. Draw order = 1.21 kid_analyze.boot (strata in insertion order, each
        stratum resampled to its size with rng.choice)."""
        rng = random.Random(seed)
        out = []
        for _ in range(B):
            draw = {s: [rng.choice(v) for _ in v] for s, v in self.by.items()}
            out.append((self.mean_exact({s: sum(x) for s, x in draw.items()}), self.se(draw)))
        return out


def zq(alpha):
    """Upper normal quantile z_(1-alpha) (bisection; stdlib only)."""
    lo, hi = 0.0, 10.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if 0.5 * math.erfc(mid / math.sqrt(2)) > alpha:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


LEGACY = {"P95": ("P", 0.025), "P99": ("P", 0.01), "BT": ("BT", 0.025)}


def decide(table, threshold, rule, B, seed, weights=WEIGHT, k=2):
    """Gate decision with unrounded values. rule: ("P" | "BT", one-sided alpha) or a legacy name (P95, P99, BT).
    threshold is a Fraction (0 for arrival, -3/64 for correction).
      P   percentile lower bound = sorted bootstrap means[round(alpha B)] (exact Fraction), floored at
          m - z_(1-alpha) * se_floor; pass iff exact bound > threshold (floor: float bound > threshold + EPS).
      BT  m - max(t*_[round((1-alpha) B) - 1], z_(1-alpha)) * max(se, se_floor); pass iff > threshold + EPS."""
    fam, alpha = LEGACY.get(rule, rule) if isinstance(rule, str) else rule
    if fam not in ("P", "BT") or not 0 < alpha < 0.5:
        raise ValueError(rule)
    S = Strata(table, weights, k)
    m = S.mean_exact()
    se = max(S.se(S.by), S.floor)
    bs = S.boot(B, seed)
    means = sorted(x for x, _ in bs)
    z = zq(alpha)
    if fam == "P":
        q = means[round(alpha * B)]
        floor_lb = float(m) - z * S.floor
        if float(q) <= floor_lb:
            lb, lb_exact = float(q), q
            passed = q > threshold
        else:
            lb, lb_exact = floor_lb, None
            passed = lb > float(threshold) + EPS
    else:
        t = sorted(float(x - m) / max(s, S.floor) for x, s in bs)
        tq = max(t[round((1 - alpha) * B) - 1], z)
        lb, lb_exact = float(m) - tq * se, None
        passed = math.isfinite(lb) and lb > float(threshold) + EPS
    return {"rule": [fam, alpha], "B": B, "seed": seed, "threshold": str(threshold), "estimate_exact": str(m),
            "estimate": float(m), "lower": lb, "lower_exact": None if lb_exact is None else str(lb_exact),
            "percentile95": [float(means[round(0.025 * B)]), float(means[round(0.975 * B) - 1])], "se": se,
            "se_floor": S.floor, "n_groups": sum(S.n.values()), "n_by_stratum": S.n, "pass": bool(passed)}


def qualification(arrival, correction):
    """Both components must pass for the combined upgrade claim."""
    a, c = arrival["pass"], correction["pass"]
    if a and c:
        verdict = "qualifies conditional on the declared tolerance 3/64"
    elif a:
        verdict = "arrival superiority shown; correction non-inferiority not shown (trade-off or inconclusive)"
    elif c:
        verdict = "arrival superiority not shown; does not qualify"
    else:
        verdict = "neither component shown; does not qualify"
    return {"arrival_pass": a, "correction_pass": c, "qualifies": a and c, "verdict": verdict}
