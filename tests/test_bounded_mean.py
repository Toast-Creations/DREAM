"""Exact bounded-mean fixtures. No model, cases, filesystem fixtures or RNG required."""
import copy
from dataclasses import FrozenInstanceError
from fractions import Fraction as F
import itertools
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from tempo import bounded_mean as BM  # noqa: E402


def independent_evidence(values, tau, rule):
    """Direct raw-data product, separate from the implementation's count powers."""
    answer = F(0)
    for c, weight in zip(rule.c, rule.weights):
        factor = F(1)
        for value in values:
            factor *= 1 + c * (value - tau) / (1 + tau)
        answer += weight * factor
    return answer


def enumerate_laws(laws, rule):
    expected, rejected = F(0), F(0)
    for selections in itertools.product(*[tuple(law.items()) for law in laws]):
        values, probabilities = zip(*selections)
        probability = math.prod(probabilities)
        value = BM.evidence(values, rule.threshold, rule.c, rule.weights)
        expected += probability * value
        if BM.passes_evidence(value, rule.evidence_threshold):
            rejected += probability
    return expected, rejected


class RuleContract(unittest.TestCase):
    def test_canonical_rule_identity_and_defensive_containers(self):
        config = BM.rule_config()
        self.assertEqual(config["alpha"], "1/40")
        self.assertEqual(config["correction"]["threshold"], "-3/64")
        self.assertEqual(BM.validate_rule_config(config)["arrival"], BM.ARRIVAL_RULE)
        config["arrival"]["c"][0] = "1/2"
        self.assertEqual(BM.rule_config()["arrival"]["c"][0], "1/10")
        with self.assertRaises(TypeError):
            BM.RULES["arrival"] = BM.CORRECTION_RULE
        with self.assertRaises(FrozenInstanceError):
            BM.ARRIVAL_RULE.threshold = F(1, 2)

    def test_noncanonical_config_fails_closed(self):
        mutations = []
        for key, value in (("strict", 1), ("alpha", .025), ("method", "alternate"),
                           ("evidence_threshold", "39")):
            changed = BM.rule_config(); changed[key] = value; mutations.append(changed)
        changed = BM.rule_config(); changed["extra"] = True; mutations.append(changed)
        changed = BM.rule_config(); del changed["correction"]; mutations.append(changed)
        changed = BM.rule_config(); changed["arrival"]["c"][0] = .1; mutations.append(changed)
        changed = BM.rule_config(); changed["arrival"]["weights"] = ["1/2"] * 4; mutations.append(changed)
        changed = BM.rule_config(); changed["arrival"]["threshold"] = 0; mutations.append(changed)
        for changed in mutations:
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                BM.validate_rule_config(changed)

    def test_invalid_rules(self):
        cases = [((), (), "0", "40"), (("1/2",), (), "0", "40"),
                 (("-1/2",), ("1",), "0", "40"), (("1",), ("1",), "0", "40"),
                 (("0",), ("1",), "0", "40"), (("1/2",), ("-1",), "0", "40"),
                 (("1/2",), ("1/2",), "0", "40"), (("1/2",), ("1",), "-1", "40"),
                 (("1/2",), ("1",), "2", "40"), (("1/2",), ("1",), "0", "1")]
        for case in cases:
            with self.subTest(case=case), self.assertRaises(ValueError):
                BM.Rule(*case)
        for value in (.5, True, float("nan"), None):
            with self.subTest(value=value), self.assertRaises(TypeError):
                BM.Rule((value,), ("1",), "0")
        with self.assertRaises(ValueError):
            BM.Rule(("1/0",), ("1",), "0")

    def test_input_and_precision_validation(self):
        for values in ([], (), ["2"], ["-5/4"]):
            with self.subTest(values=values), self.assertRaises(ValueError):
                BM.evaluate(values, "arrival")
        for values in ([0.5], [True]):
            with self.subTest(values=values), self.assertRaises(TypeError):
                BM.evaluate(values, "arrival")
        for bits in (0, 513, True, 1.5):
            with self.subTest(bits=bits), self.assertRaises(ValueError):
                BM.lower_bound([0], BM.ARRIVAL_RULE, bits)
        with self.assertRaises(ValueError):
            BM.evaluate([0], "reference")
        with self.assertRaises(TypeError):
            BM.lower_bound([0], {})


class ExactEvidence(unittest.TestCase):
    def test_handworked_products(self):
        self.assertEqual(BM.evidence([1, -1], 0, ("1/2",), ("1",)), F(3, 4))
        self.assertEqual(BM.evidence([1, -1, 0], "-3/64", ("1/2",), ("1",)), F(23625, 29768))
        self.assertEqual(BM.evidence(["1/2", 0, "-1/2"], 0,
                                     ("1/4", "3/4"), ("1/3", "2/3")), F(173, 192))

    def test_direct_count_order_and_replication_parity(self):
        values = [F(-1), F(-3, 4), F(-1, 2), F(-1, 4), F(0), F(1, 4), F(1, 2), F(3, 4), F(1)] * 3
        for rule in BM.RULES.values():
            expected = independent_evidence(values, rule.threshold, rule)
            observed = BM.evidence(values, rule.threshold, rule.c, rule.weights)
            self.assertEqual(observed, expected)
            self.assertEqual(BM.evidence(reversed(values), rule.threshold, rule.c, rule.weights), expected)

    def test_strict_ties_and_arbitrarily_close_neighbors(self):
        epsilon = F(1, 10**100)
        self.assertFalse(BM.passes_evidence(F(40)))
        self.assertFalse(BM.passes_evidence(F(40) - epsilon))
        self.assertTrue(BM.passes_evidence(F(40) + epsilon))
        self.assertEqual(float(F(40) + epsilon), float(F(40) - epsilon))
        with self.assertRaises(TypeError):
            BM.passes_evidence(40.0)
        with self.assertRaises(ValueError):
            BM.passes_evidence(-1)

    def test_extreme_products_remain_exact(self):
        small = BM.evidence([-1] * 1000, 0, ("99/100",), ("1",))
        large = BM.evidence([1] * 2000, 0, ("99/100",), ("1",))
        self.assertEqual(small, F(1, 100)**1000)
        self.assertEqual(large, F(199, 100)**2000)
        self.assertLess(small, F(1, 10**1000))
        self.assertGreater(large, 10**500)

    def test_primary_gate_zero_samples_have_nonzero_uncertainty(self):
        correction = BM.evaluate([0] * 160, "correction")
        arrival = BM.evaluate([0] * 224, "arrival")
        self.assertTrue(correction["pass"])
        self.assertFalse(arrival["pass"])
        self.assertEqual(correction["n"], 160)
        self.assertEqual(correction["estimate_exact"], "0")
        self.assertAlmostEqual(correction["lower_bound"]["lower"], -.027911716182357604, places=13)
        self.assertLess(correction["lower_bound"]["upper"], 0)
        self.assertEqual(arrival["evidence_exact"], "1")

    def test_reference_numerics_checked_against_independent_formula(self):
        for n, approximate in ((94, 39.64278776542294), (95, 41.30145240365064), (96, 43.030477002157994)):
            rule = BM.CORRECTION_RULE
            exact = sum(w * (1 + c * F(3, 61))**n for c, w in zip(rule.c, rule.weights))
            observed = BM.evidence([0] * n, rule.threshold, rule.c, rule.weights)
            self.assertEqual(observed, exact)
            self.assertAlmostEqual(float(exact), approximate, places=10)
            self.assertEqual(BM.passes_evidence(exact), n >= 95)


class BoundInversion(unittest.TestCase):
    def assert_certified(self, values, rule, bits=64):
        bound = BM.lower_bound(values, rule, bits)
        lo, hi = F(bound["lower_exact"]), F(bound["upper_exact"])
        self.assertLessEqual(F.from_float(bound["lower"]), lo)
        self.assertGreaterEqual(F.from_float(bound["upper"]), hi)
        self.assertLessEqual(hi - lo, F(2, 2**bits))
        if lo > -1:
            self.assertTrue(BM.passes_evidence(BM.evidence(values, lo, rule.c, rule.weights)))
        if hi > -1:
            self.assertFalse(BM.passes_evidence(BM.evidence(values, hi, rule.c, rule.weights)))
        return bound

    def test_all_negative_boundary_is_empty_not_zero_precision_mean(self):
        for rule in BM.RULES.values():
            bound = self.assert_certified([-1] * 12, rule)
            self.assertTrue(bound["empty_pass_set"])
            self.assertFalse(bound["censored"])
            self.assertEqual(bound["lower_exact"], "-1")
            self.assertEqual(bound["upper_exact"], "-1")
            self.assertIn("lower confidence endpoint", bound["kind"])

    def test_all_positive_and_half_quarter_data(self):
        for values, rule in (([1] * 224, BM.ARRIVAL_RULE),
                             ([F(1, 2)] * 40 + [F(-1, 2)] * 10, BM.ARRIVAL_RULE),
                             ([F(1, 4)] * 80 + [F(-1, 4)] * 10, BM.CORRECTION_RULE)):
            bound = self.assert_certified(values, rule)
            self.assertFalse(bound["empty_pass_set"])
            self.assertLess(bound["upper"], 1)

    def test_almost_negative_boundary_is_not_falsely_empty(self):
        values = [-1] * 159 + [F(-3, 4)]
        coarse = self.assert_certified(values, BM.CORRECTION_RULE, 16)
        self.assertFalse(coarse["empty_pass_set"])
        self.assertTrue(coarse["censored"])
        self.assertEqual(coarse["lower_exact"], "-1")
        fine = self.assert_certified(values, BM.CORRECTION_RULE, 128)
        self.assertFalse(fine["empty_pass_set"])
        self.assertFalse(fine["censored"])
        self.assertGreater(F(fine["lower_exact"]), -1)

    def test_monotonicity_and_refining_brackets(self):
        values = [F(1, 4)] * 30 + [0] * 40 + [F(-1, 2)] * 2
        rule = BM.CORRECTION_RULE
        thresholds = [F(-3, 4), F(-1, 2), F(-3, 64), F(0), F(1, 2), F(1)]
        evidences = [BM.evidence(values, t, rule.c, rule.weights) for t in thresholds]
        self.assertTrue(all(a > b for a, b in zip(evidences, evidences[1:])))
        rough, fine = self.assert_certified(values, rule, 12), self.assert_certified(values, rule, 64)
        self.assertLessEqual(F(rough["lower_exact"]), F(fine["lower_exact"]))
        self.assertGreaterEqual(F(rough["upper_exact"]), F(fine["upper_exact"]))


class FixedTimeNullFixtures(unittest.TestCase):
    def test_heterogeneous_handworked_expectation(self):
        laws = [{F(1): F(9, 10), F(-1): F(1, 10)}, {F(1): F(1, 10), F(-1): F(9, 10)}]
        rule = BM.Rule(("1/2", "3/4"), ("1/2", "1/2"), "0")
        expectation, rejected = enumerate_laws(laws, rule)
        self.assertEqual(expectation, F(37, 50))
        self.assertEqual(rejected, 0)

    def test_homogeneous_and_heterogeneous_small_law_null_control(self):
        for rule in BM.RULES.values():
            mean_plus = (1 + rule.threshold) / 2
            for heterogeneous in (False, True):
                plus = [mean_plus + (F(1, 5) if i % 2 else F(-1, 5)) if heterogeneous else mean_plus
                        for i in range(10)]
                laws = [{F(1): p, F(-1): 1-p} for p in plus]
                expectation, rejected = enumerate_laws(laws, rule)
                self.assertLessEqual(expectation, 1)
                self.assertLessEqual(rejected, F(1, 40))

    def test_positive_prefix_does_not_authorize_interim_qualification(self):
        prefix = [1] * 10
        self.assertTrue(BM.evaluate(prefix, "arrival", bracket_bits=8)["pass"])
        final = BM.evaluate(prefix + [-1] * 10, "arrival", bracket_bits=8)
        self.assertFalse(final["pass"])
        self.assertLess(F(final["evidence_exact"]), 1)
        self.assertTrue(final["fixed_final_sample_only"])


if __name__ == "__main__":
    unittest.main()
