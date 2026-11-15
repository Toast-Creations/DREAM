"""Fixed-final-sample bounded-mean mixture rule (CCONF-v1).

Inputs are already averaged *independent stem* differences in [-1,1]. This
module does not check allocation, construct cases, read files, score replies or
authorize interim stopping. The analyzer owns those contracts. Under the null
average E[d_g] <= tau, independence and AM-GM give E[T(tau)] <= 1.
Qualification uses an exact strict comparison with 40, never a displayed bound.
"""
from collections import Counter
from dataclasses import dataclass
from fractions import Fraction
import math
from types import MappingProxyType


def _fraction(value):
    if isinstance(value, bool) or not isinstance(value, (int, str, Fraction)):
        raise TypeError("use integers, rational strings or Fraction; binary floats are not accepted")
    try:
        return Fraction(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError("invalid rational value") from exc


def _sequence(values, name):
    if isinstance(values, (str, bytes)):
        raise TypeError(f"{name} must be a sequence of rational values")
    try:
        return tuple(_fraction(x) for x in values)
    except TypeError as exc:
        raise TypeError(f"{name}: {exc}") from exc


@dataclass(frozen=True)
class Rule:
    c: tuple
    weights: tuple
    threshold: Fraction
    evidence_threshold: Fraction = Fraction(40)

    def __post_init__(self):
        cs, weights = _sequence(self.c, "c"), _sequence(self.weights, "weights")
        threshold, cutoff = _fraction(self.threshold), _fraction(self.evidence_threshold)
        if not cs or len(cs) != len(weights):
            raise ValueError("c and weights must be nonempty and have the same length")
        if any(not 0 <= c < 1 for c in cs):
            raise ValueError("each c must satisfy 0 <= c < 1")
        if any(w < 0 for w in weights) or sum(weights) != 1:
            raise ValueError("weights must be nonnegative and sum exactly to one")
        if not any(c > 0 and w > 0 for c, w in zip(cs, weights)):
            raise ValueError("at least one positive c must have positive weight")
        if not -1 < threshold <= 1 or cutoff <= 1:
            raise ValueError("threshold must be in (-1,1] and evidence threshold must exceed one")
        for name, value in (("c", cs), ("weights", weights), ("threshold", threshold),
                            ("evidence_threshold", cutoff)):
            object.__setattr__(self, name, value)

    def as_dict(self):
        return {"threshold": str(self.threshold), "c": [str(x) for x in self.c],
                "weights": [str(x) for x in self.weights]}


ARRIVAL_RULE = Rule(("1/10", "1/4", "1/2", "3/4"), ("1/4",) * 4, "0")
CORRECTION_RULE = Rule(("1/4", "1/2", "3/4", "9/10"), ("1/10", "1/10", "3/10", "1/2"), "-3/64")
RULES = MappingProxyType({"arrival": ARRIVAL_RULE, "correction": CORRECTION_RULE})


def rule_config():
    """Canonical JSON-ready rule identity; every call returns fresh containers."""
    return {"method": "fixed_time_bounded_mean_mixture_v1", "alpha": "1/40",
            "evidence_threshold": "40", "strict": True,
            **{name: rule.as_dict() for name, rule in RULES.items()}}


def validate_rule_config(config):
    """Only the committed rule is allowed in production; no silent alternatives."""
    expected = rule_config()
    if not isinstance(config, dict) or set(config) != set(expected) or config.get("strict") is not True:
        raise ValueError("rule config differs from the canonical CCONF-v1 rule")
    for name in ("method", "alpha", "evidence_threshold"):
        if type(config[name]) is not str or config[name] != expected[name]:
            raise ValueError(f"noncanonical rule field: {name}")
    for name in RULES:
        value = config[name]
        if not isinstance(value, dict) or set(value) != {"threshold", "c", "weights"}:
            raise ValueError(f"noncanonical component rule: {name}")
        if type(value["threshold"]) is not str or type(value["c"]) is not list or type(value["weights"]) is not list \
                or any(type(x) is not str for x in value["c"] + value["weights"]) or value != expected[name]:
            raise ValueError(f"noncanonical component constants: {name}")
    return dict(RULES)


def _data(differences):
    values = _sequence(differences, "differences")
    if not values:
        raise ValueError("no independent stem data; suppress inference")
    if any(not -1 <= d <= 1 for d in values):
        raise ValueError("each independent stem difference must be in [-1,1]")
    return values, Counter(values)


def _evidence_counts(counts, threshold, rule):
    # Sufficient counts preserve the exact product while avoiding repeated work.
    total = Fraction(0)
    for c, weight in zip(rule.c, rule.weights):
        if not weight:
            continue
        product = Fraction(1)
        for d, n in counts.items():
            factor = 1 - c + c * (1 + d) / (1 + threshold)
            product *= factor ** n
        total += weight * product
    return total


def evidence(differences, threshold, c, weights):
    """Exact mixture evidence at one threshold; floating inputs are rejected."""
    rule = Rule(c, weights, threshold)
    _, counts = _data(differences)
    return _evidence_counts(counts, rule.threshold, rule)


def passes_evidence(value, cutoff=Fraction(40)):
    """Strict rational comparison. Exact equality fails."""
    value, cutoff = _fraction(value), _fraction(cutoff)
    if value < 0 or cutoff <= 1:
        raise ValueError("evidence must be nonnegative and cutoff must exceed one")
    return value > cutoff


def _outward_float(value, lower):
    shown = float(value)
    represented = Fraction.from_float(shown)
    if lower and represented > value:
        shown = math.nextafter(shown, -math.inf)
    elif not lower and represented < value:
        shown = math.nextafter(shown, math.inf)
    return shown


def _lower_bound_counts(values, counts, rule, bits):
    if type(bits) is not int or not 1 <= bits <= 512:
        raise ValueError("bisection precision must be an integer in [1,512]")
    empty = all(d == -1 for d in values)
    lo, hi = Fraction(-1), Fraction(-1 if empty else 1)
    if not empty:
        # -1 is a limiting endpoint, never a threshold at which we divide.
        # At any other sample the evidence tends to infinity as tau -> -1.
        for _ in range(bits):
            mid = (lo + hi) / 2
            if _evidence_counts(counts, mid, rule) > rule.evidence_threshold:
                lo = mid
            else:
                hi = mid
        if lo > -1:
            assert _evidence_counts(counts, lo, rule) > rule.evidence_threshold
        assert _evidence_counts(counts, hi, rule) <= rule.evidence_threshold
    return {"kind": "numerical enclosure of the one-sided lower confidence endpoint",
            "alpha_exact": str(1 / rule.evidence_threshold), "lower_exact": str(lo), "upper_exact": str(hi),
            "lower": _outward_float(lo, True), "upper": _outward_float(hi, False),
            "width_exact": str(hi - lo), "empty_pass_set": empty,
            "censored": not empty and lo == -1, "iterations": 0 if empty else bits,
            "endpoint_certification": "exact rational; -1 uses the analytic boundary limit"}


def lower_bound(differences, rule, bits=64):
    """Certified rational bracket, not a two-sided population confidence interval.

    Censored means a nonempty passing set lies closer to -1 than this bracket
    resolves. The returned -1 lower endpoint is conservative. Display floats
    are rounded outward; gates always use exact threshold arithmetic.
    """
    if not isinstance(rule, Rule):
        raise TypeError("rule must be a validated Rule")
    values, counts = _data(differences)
    return _lower_bound_counts(values, counts, rule, bits)


def evaluate(differences, component, bracket_bits=64):
    """JSON-ready exact primary gate plus a separately labelled bound bracket."""
    if component not in RULES:
        raise ValueError("component must be arrival or correction")
    values, counts = _data(differences)
    rule = RULES[component]
    statistic = _evidence_counts(counts, rule.threshold, rule)
    estimate = sum(values) / len(values)
    return {"n": len(values), "estimate_exact": str(estimate), "estimate": float(estimate),
            "threshold_exact": str(rule.threshold), "evidence_exact": str(statistic),
            "log_evidence": math.log(statistic.numerator) - math.log(statistic.denominator),
            "cutoff_exact": str(rule.evidence_threshold), "pass": passes_evidence(statistic, rule.evidence_threshold),
            "rule": rule.as_dict(), "fixed_final_sample_only": True,
            "lower_bound": _lower_bound_counts(values, counts, rule, bracket_bits)}
