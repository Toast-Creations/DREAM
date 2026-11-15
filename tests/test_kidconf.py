"""No-model fixtures for V1.22.0 KIDCONF-v1: allocation, schedule, completeness, exact statistic, gates, and parity
with all 18 stored 1.21 development contrasts (differences, intervals, paired counts)."""
import collections
import json
import random
import statistics
import sys
import unittest
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tempo import kidconf as KC  # noqa: E402

FIX = ROOT / "tests" / "fixtures"


def legacy_boot(diffs, strat, B, seed):
    """Verbatim logic of 1.21 kid_analyze.boot on precomputed group statistics."""
    by = collections.defaultdict(list)
    for g in diffs:
        by[strat[g]].append(g)
    rng = random.Random(seed)
    est = sorted(statistics.mean(diffs[rng.choice(v)] for v in by.values() for _ in v) for _ in range(B))
    return [round(est[int(0.025 * B)], 4), round(est[int(0.975 * B) - 1], 4)]


class Allocation(unittest.TestCase):
    def test_blocks_proportional_and_nested(self):
        g = KC.plan(392, "c22-g")
        self.assertEqual(len(g), 392)
        self.assertEqual(len({x[0] for x in g}), 392)
        t = KC.allocation_table(g, 168)
        self.assertEqual(t["correction|F1|immediate"], 49)
        self.assertEqual(t["correction|F3|delayed"], 98)
        self.assertEqual(t["arrival|F2|delayed"], 21)
        self.assertEqual(t["arrival|F3|immediate"], 42)
        self.assertEqual(sum(v for k, v in t.items() if k.startswith("arrival")), 168)
        # nested: every arrival group is also a correction group
        arr = {x[0] for x in g if "arrival" in KC.acts_for(x[4], 168)}
        cor = {x[0] for x in g if "correction" in KC.acts_for(x[4], 168)}
        self.assertTrue(arr <= cor and len(cor) == 392)
        # bits cycle within stratum
        f1i = [x[3] for x in g if x[1] == "F1_two_hop" and x[2] == "immediate"][:4]
        self.assertEqual(f1i, [(0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 0)])

    def test_rejects_non_multiple_of_8(self):
        with self.assertRaises(ValueError):
            KC.plan(390, "x")
        with self.assertRaises(ValueError):
            KC.acts_for(0, 12)

    def test_ids_cannot_collide_with_historical_probes(self):
        g = KC.plan(16, "c22-g")
        self.assertFalse(any(x[0].startswith("g0") for x in g))


class Schedule(unittest.TestCase):
    def test_units_kept_together_and_seeded(self):
        units = [[{"call_id": f"u{i}|{h}|{a}", "arm": a, "history": h} for a in KC.ARMS for h in KC.HISTORIES]
                 for i in range(10)]
        o1, o2 = KC.unit_order(units, 5), KC.unit_order(units, 5)
        self.assertEqual(o1, o2)
        for j in range(0, 40, 4):
            self.assertEqual(len({c["call_id"].split("|")[0] for c in o1[j:j + 4]}), 1)
            self.assertEqual([c["history"] for c in o1[j:j + 2]], ["A", "B"])
        firsts = {o1[j]["arm"] for j in range(0, 40, 4)}
        self.assertEqual(firsts, {"SUB", "KEEP"})


class Completeness(unittest.TestCase):
    def setUp(self):
        self.decl = {("c1", "correction"): "F1|immediate", ("c1", "arrival"): "F1|immediate",
                     ("c2", "correction"): "F1|immediate"}
        self.ids = {f"{g}|{a}|{h}|{arm}" for (g, a) in self.decl for h in "AB" for arm in KC.ARMS}

    def test_complete_ok(self):
        KC.check_complete(self.decl, self.ids, {c: {"status": "ok"} for c in self.ids})

    def test_missing_extra_notok(self):
        recs = {c: {"status": "ok"} for c in self.ids}
        recs.pop(sorted(self.ids)[0])
        with self.assertRaises(KC.Incomplete):
            KC.check_complete(self.decl, self.ids, recs)
        recs = {c: {"status": "ok"} for c in self.ids} | {"zz|arrival|A|SUB": {"status": "ok"}}
        with self.assertRaises(KC.Incomplete):
            KC.check_complete(self.decl, self.ids, recs)
        recs = {c: {"status": "ok"} for c in self.ids}
        recs[sorted(self.ids)[1]] = {"status": "error"}
        with self.assertRaises(KC.Incomplete):
            KC.check_complete(self.decl, self.ids, recs)
        with self.assertRaises(KC.Incomplete):
            KC.check_complete(self.decl, self.ids - {sorted(self.ids)[2]}, {c: {"status": "ok"} for c in self.ids})

    def test_no_empty_set_success(self):
        ex = {(g, a, h, arm): True for (g, a) in self.decl for h in "AB" for arm in KC.ARMS}
        # c2 has no arrival: it must not enter the arrival table (and is not counted as a success there)
        tab, k = KC.pair_table(self.decl, ex, ("arrival",))
        self.assertEqual(set(tab), {"c1"})
        self.assertEqual(k, 2)
        tab, k = KC.pair_table(self.decl, ex, ("arrival", "correction"))
        self.assertEqual(set(tab), {"c1"})
        self.assertEqual(k, 4)
        del ex[("c1", "arrival", "B", "KEEP")]
        with self.assertRaises(KC.Incomplete):
            KC.pair_table(self.decl, ex, ("arrival",))
        with self.assertRaises(KC.Incomplete):
            KC.pair_table({("c2", "correction"): "F1|immediate"}, ex, ("arrival",))


def table(n_per_block, values):
    """values: list of D_g, cycled over a proportional allocation."""
    g = KC.plan(8 * n_per_block, "t")
    return {gid: (KC.stratum(f, r), values[i % len(values)]) for i, (gid, f, r, _, _) in enumerate(g)}


class Statistic(unittest.TestCase):
    def test_exact_estimate(self):
        t = table(7, [0, 0, 0, -1, 0, 1, 0, -2])
        S = KC.Strata(t)
        m = S.mean_exact()
        self.assertIsInstance(m, Fraction)
        self.assertEqual(m, Fraction(sum(d for _, d in t.values()), 2 * len(t)))  # proportional -> plain mean

    def test_exact_tie_at_margin_fails(self):
        # 448 groups (proportional): weighted mean = plain mean = sum(D)/896, so sum(D) = -42 gives exactly -3/64.
        g = KC.plan(448, "t")
        t = {gid: (KC.stratum(f, r), -1 if i % 10 == 0 and i < 420 else 0) for i, (gid, f, r, _, _) in enumerate(g)}
        self.assertEqual(sum(d for _, d in t.values()), -42)
        S = KC.Strata(t)
        self.assertEqual(S.mean_exact(), -KC.MARGIN)
        for rule in ("P95", "P99", "BT"):
            d = KC.decide(t, -KC.MARGIN, rule, 400, 1)
            self.assertFalse(d["pass"], rule)

    def test_zero_variance_is_floored(self):
        t = table(49, [0])
        d = KC.decide(t, Fraction(0), "BT", 200, 3)
        self.assertGreater(d["se"], 0)
        self.assertFalse(d["pass"])                      # all-zero difference does not show superiority
        d = KC.decide(t, -KC.MARGIN, "BT", 200, 3)
        self.assertTrue(d["pass"])                       # 392 groups of exact agreement exclude a 3/64 loss
        small = table(4, [0])                            # 32 groups: the conservative floor does not exclude it
        self.assertFalse(KC.decide(small, -KC.MARGIN, "BT", 200, 3)["pass"])
        for rule in ("P95", "P99"):
            self.assertFalse(KC.decide(t, Fraction(0), rule, 200, 3)["pass"])

    def test_missing_stratum_refused(self):
        t = {k: v for k, v in table(2, [0]).items() if not v[0].startswith("F1|imm")}
        with self.assertRaises(KC.Incomplete):
            KC.Strata(t)

    def test_qualification_needs_both(self):
        self.assertTrue(KC.qualification({"pass": True}, {"pass": True})["qualifies"])
        q = KC.qualification({"pass": True}, {"pass": False})
        self.assertFalse(q["qualifies"])
        self.assertIn("not shown", q["verdict"])


class Parity121(unittest.TestCase):
    """The precomputed-group analyzer reproduces every stored 1.21 contrast: difference, 95% interval (same draw
    order, B = 10000, seed 20261110) and paired counts, for MAIN and F4 x arrival/correction/both acts."""

    @classmethod
    def setUpClass(cls):
        rows = [json.loads(l) for l in (FIX / "kid121_scored_min.jsonl").read_text().splitlines() if l.strip()]
        cls.ref = json.loads((FIX / "kid121_analysis_ref.json").read_text())["ref"]
        cls.exact = {(r["group"], r["act"], r["history"], r["arm"]): bool(r["exact"]) for r in rows}
        cls.decl = {}
        for r in rows:
            cls.decl[(r["group"], r["act"])] = (r["family"], r["stratum"])
        cls.masks = {"MAIN": ("F1", "F2", "F3"), "F4": ("F4",)}

    def test_all_18(self):
        n = 0
        for m, fams in self.masks.items():
            decl = {k: v[1] for k, v in self.decl.items() if v[0] in fams}
            strata = sorted(set(decl.values()))
            groups = sorted({g for g, _ in decl})
            counts = collections.Counter(decl[(g, "arrival")] for g in groups)
            weights = {s: Fraction(counts[s], len(groups)) for s in strata}
            for key, acts in (("arrival", ("arrival",)), ("correction", ("correction",)),
                              ("both_acts", ("arrival", "correction"))):
                for A, Bm in (("KEEP", "SUB"), ("KEEP", "BASE"), ("SUB", "BASE")):
                    ref = self.ref[m][key][f"{A}-{Bm}"]
                    tab, k = KC.pair_table(decl, self.exact, acts, (A, Bm))
                    S = KC.Strata(tab, weights, k)
                    self.assertEqual(round(float(S.mean_exact()), 4), ref["difference"], (m, key, A, Bm))
                    # interval: new sufficient-statistic bootstrap == legacy draw order on group means
                    boots = sorted(float(x) for x, _ in S.boot(10000, 20261110))
                    got = [round(boots[int(0.025 * 10000)], 4), round(boots[int(0.975 * 10000) - 1], 4)]
                    self.assertEqual(got, ref["ci95"], (m, key, A, Bm))
                    diffs = {g: d / k for g, (s, d) in tab.items()}
                    self.assertEqual(legacy_boot(diffs, {g: s for g, (s, _) in tab.items()}, 10000, 20261110),
                                     ref["ci95"])
                    pc, ph = KC.paired_counts(decl, self.exact, acts, (A, Bm))
                    self.assertEqual(pc, ref["paired_targets"], (m, key, A, Bm))
                    self.assertEqual(ph, ref["paired_history_units_both_exact"], (m, key, A, Bm))
                    n += 1
        self.assertEqual(n, 18)


if __name__ == "__main__":
    unittest.main()
