"""Pure dose curves for time-varying steering. No PyTorch import.

A schedule maps a hooked generation forward index (0 = prompt prefill) to a
multiplier in [0, 1] applied to the configured peak lambda. A negative peak
lambda therefore produces a negative curve of the same shape.

Two time axes exist deliberately:

* ``legacy_linear``: the V1.1 curve, normalized by the PLANNED token budget.
  Retained bit-for-bit so earlier DREAM pipeline results remain reproducible.
* ``trip`` specs (V1.2.0): measured in ABSOLUTE generated tokens. The curve
  shape no longer stretches with the answer cap, and ``comedown_complete``
  reports whether the model kept generating until the dose returned to zero.
* ``release`` specs (V1.3.0): one rung of the release ladder. The dose starts
  at the configured lambda and glides (raised cosine) down to ``end_fraction``
  of it over ``glide_tokens``, then holds there. Chained rungs whose start
  equals the previous end give a continuous, gradual step-down across passes.

The psychedelic come-up/plateau/come-down language is an analogy for this
curve shape only; it makes no claim about model experience or neural entropy.
"""
import math

SHAPES = ("smooth", "linear", "constant", "release")


def legacy_linear(step, max_new_tokens):
    """V1.1 hardcoded curve: rise [0,.15), hold [.15,.60), taper [.60,.90), zero."""
    progress = step / max(1, max_new_tokens - 1)
    return progress / .15 if progress < .15 else 1 if progress < .6 else max(0, (.9-progress)/.3)


def validate_spec(spec):
    """Reject malformed trip specs before any model work; return a clean copy."""
    if not isinstance(spec, dict) or spec.get("shape") not in SHAPES:
        raise ValueError("Schedule shape must be one of " + ", ".join(SHAPES))
    clean = {"shape": spec["shape"]}
    if clean["shape"] == "release":
        glide, end = spec.get("glide_tokens"), spec.get("end_fraction")
        if type(glide) is not int or not 1 <= glide <= 8192:
            raise ValueError("glide_tokens must be an integer in [1, 8192]")
        if type(end) not in (int, float) or not math.isfinite(end) or not 0 <= end <= 1:
            raise ValueError("end_fraction must be in [0, 1]")
        return {"shape": "release", "glide_tokens": glide, "end_fraction": float(end)}
    for key in ("onset_tokens", "plateau_tokens", "comedown_tokens"):
        value = spec.get(key, 0)
        if type(value) is not int or not 0 <= value <= 8192:
            raise ValueError(f"{key} must be an integer token count in [0, 8192]")
        clean[key] = value
    if clean["shape"] != "constant" and clean["onset_tokens"] + clean["plateau_tokens"] + clean["comedown_tokens"] == 0:
        raise ValueError("A non-constant schedule needs a nonzero duration")
    return clean


def end_token(spec):
    """First forward index at which a non-constant curve is back to zero."""
    if spec["shape"] == "constant":
        return None
    if spec["shape"] == "release":
        return spec["glide_tokens"]
    return spec["onset_tokens"] + spec["plateau_tokens"] + spec["comedown_tokens"]


def dose(step, spec):
    """Multiplier for forward index ``step`` under a validated trip spec.

    ``smooth`` uses raised-cosine ramps (zero slope at both ends of each ramp),
    so the dose changes gently at onset, peak entry, peak exit and return.
    ``linear`` uses straight ramps. Both reach exactly 0 at ``end_token``.
    """
    if step < 0:
        raise ValueError("Schedule step must be nonnegative")
    if spec["shape"] == "constant":
        return 1.0
    if spec["shape"] == "release":
        if step >= spec["glide_tokens"]:
            return spec["end_fraction"]
        fraction = 0.5 - 0.5 * math.cos(math.pi * step / spec["glide_tokens"])
        return 1 - (1 - spec["end_fraction"]) * fraction
    up, hold, down = spec["onset_tokens"], spec["plateau_tokens"], spec["comedown_tokens"]
    if step < up:
        fraction = step / up
    elif step < up + hold:
        return 1.0
    elif step < up + hold + down:
        fraction = 1 - (step - up - hold) / down
    else:
        return 0.0
    if spec["shape"] == "linear":
        return fraction
    return 0.5 - 0.5 * math.cos(math.pi * fraction)


def validate_temperature_schedule(spec):
    """Check a hot-to-cold sampling schedule (the decoding-only control arm)."""
    if not isinstance(spec, dict):
        raise ValueError("Temperature schedule must be an object")
    for key in ("start", "end"):
        value = spec.get(key)
        if type(value) not in (int, float) or not math.isfinite(value) or not 1e-3 <= value <= 3:
            raise ValueError(f"Temperature schedule {key} must be in [0.001, 3]")
    tokens = spec.get("anneal_tokens")
    if type(tokens) is not int or not 1 <= tokens <= 8192:
        raise ValueError("anneal_tokens must be an integer in [1, 8192]")
    return {"start": float(spec["start"]), "end": float(spec["end"]), "anneal_tokens": tokens}


def annealed_temperature(step, spec):
    """Raised-cosine glide from start to end over anneal_tokens, then hold end.

    Exploratory annealed decoding (arXiv 2510.05251) motivates this control: it
    tests whether early randomness alone reproduces any trip-arm effect.
    """
    if step >= spec["anneal_tokens"]:
        return spec["end"]
    fraction = 0.5 - 0.5 * math.cos(math.pi * step / spec["anneal_tokens"])
    return spec["start"] + (spec["end"] - spec["start"]) * fraction
