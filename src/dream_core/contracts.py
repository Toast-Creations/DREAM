"""Pure control logic used by training, configuration and validation."""
import math


def predictor_mask(labels, attention_mask=None):
    """Select h[t] exactly when the shifted label[t+1] contributes to loss.

    Causal language-model training predicts the NEXT token. Prompt labels use
    -100 to exclude their targets; selecting labels[t] instead of labels[t+1]
    would miss the last prompt position that predicts the first answer token.
    Both predictor and target must be attended, excluding padded transitions.
    The final activation has no next-token target in this sequence and is False.

    Example: [-100, -100, A, B] -> [False, True, True, False]. This pure Python
    contract is shared with training; it is not itself an autograd integration
    test. Actual gradient influence must be checked with the transformer stack.
    """
    if len(labels) < 2:
        raise ValueError("A causal sequence needs at least two tokens")
    attention = attention_mask if attention_mask is not None else [1] * len(labels)
    if len(attention) != len(labels) or any(x not in (0, 1) for x in attention):
        raise ValueError("Invalid attention mask")
    mask = [bool(attention[i] and attention[i+1] and labels[i+1] != -100)
            for i in range(len(labels)-1)] + [False]
    if not any(mask):
        raise ValueError("No supervised next-token predictions")
    return mask


def finite_number(value, name, minimum=None, maximum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    if minimum is not None and value < minimum or maximum is not None and value > maximum:
        raise ValueError(f"{name} outside permitted range")
    return value


def integer(value, name, minimum=1, maximum=1000000):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be an integer in [{minimum}, {maximum}]")
    return value


REQUIRED_CATEGORIES = ("direct", "paraphrase", "composition", "contradiction", "scope", "anchor", "lookup")


def consolidation_decision(metrics, policy, phase):
    """Apply declared validation thresholds; never authorize deployment or merge.

    Disabled promotion returns QUARANTINE regardless of apparent improvement.
    Enabled selection requires validation worlds, finite predeclared thresholds,
    sufficient category probes, and zero invalid formats. Missing evidence is
    INVALID; measured failures are ROLLBACK; a pass is only KEEP_CANDIDATE for
    quarantined saving and later fresh-process QA. Final-test data cannot select
    a candidate, even if every numeric threshold would otherwise pass.
    """
    if not policy.get("enabled", False):
        return {"decision": "QUARANTINE", "reasons": ["Promotion disabled for this pilot"]}
    reasons = []
    if phase != "validation":
        reasons.append("Gate selection requires validation worlds, never final test worlds")
    required = ("min_composition_gain", "max_anchor_regression", "max_error_rate", "min_items_per_category")
    if any(policy.get(k) is None for k in required):
        return {"decision": "INVALID", "reasons": ["All thresholds must be specified in advance"]}
    try:
        for k in required[:3]:
            finite_number(policy[k], k, 0, 1)
        integer(policy["min_items_per_category"], "min_items_per_category")
        for category in REQUIRED_CATEGORIES:
            count = metrics["counts"][category]
            integer(count, category + " count")
            if count < policy["min_items_per_category"]:
                reasons.append("Insufficient " + category + " probes")
        for k in ("composition_gain", "anchor_regression", "error_rate"):
            finite_number(metrics[k], k, -1, 1)
        finite_number(metrics["invalid_format_rate"], "invalid_format_rate", 0, 1)
    except (KeyError, ValueError, TypeError):
        return {"decision": "INVALID", "reasons": ["Missing or non-finite gate evidence"]}
    if metrics["composition_gain"] < policy["min_composition_gain"]:
        reasons.append("Composition gain below threshold")
    if metrics["anchor_regression"] > policy["max_anchor_regression"]:
        reasons.append("Anchor regression exceeds threshold")
    if metrics["error_rate"] > policy["max_error_rate"]:
        reasons.append("Error rate exceeds threshold")
    if metrics["invalid_format_rate"] > 0:
        reasons.append("Invalid answer formats prevent candidate promotion")
    return {"decision": "ROLLBACK" if reasons else "KEEP_CANDIDATE", "reasons": reasons}
