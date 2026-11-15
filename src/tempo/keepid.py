"""V1.21.0 KEEP+ID representation (KEEPID-v1). Development screen on the 1.20 panel. Public text only.

KEEP+ID keeps the BASE FACT-v1 prompt byte-for-byte (original target sentence, original prefix, rules, query) and
inserts exactly one separate metadata line immediately before the line "New record to convert:":

    Resolved reference: "<original referring phrase>" = part <X> (field <X>.on_hand).

<original referring phrase> is the span found by the frozen 1.20 detector (refres.detect) in the original target;
<X> comes ONLY from the frozen 1.20 public-input deterministic resolver (refres.resolve_det over PublicInput:
prefix envelopes, original target, public registry order). No hidden label, canonical record, gold field or model
output is read here. No reasoning scaffold, act hint or instruction text is added.

SUB (the 1.20 RES-DET rewrite) and KEEP+ID receive the same verified identity in different representations; BASE
receives none. FACT-v1, its compiler, the engine and HOLD-EVAL-v1 are unchanged (imported, not copied).
"""
import hashlib

from . import refres as RR

RULE = "KEEPID-v1"
ANCHOR = "New record to convert:"


def annotation(phrase, field):
    if not field.endswith(".on_hand"):
        raise AssertionError("identity must be a registered stock field")
    if '"' in phrase or "\n" in phrase:
        raise AssertionError("phrase must be a single line without double quotes")
    name = field[: -len(".on_hand")]
    return f'Resolved reference: "{phrase}" = part {name} (field {name}.on_hand).'


def identity(pi):
    """Public-only identity: (detection, det_resolution). pi is a refres.PublicInput."""
    det = RR.detect(pi.target)
    if det["route"] != "resolve":
        return det, None
    return det, RR.resolve_det(pi, det)


def keep_prompt(base_prompt, target_text, phrase, field):
    """Insert the annotation as its own line immediately before ANCHOR. Everything else is byte-identical."""
    line = annotation(phrase, field)
    key = "\n" + ANCHOR + "\n" + target_text + "\n"
    if base_prompt.count(key) != 1 or base_prompt.count(ANCHOR) != 1:
        raise AssertionError("anchor + target line not unique in the BASE prompt")
    if target_text.count(phrase) != 1:
        raise AssertionError("referring phrase not unique in the original target")
    new = base_prompt.replace(key, "\n" + line + key)
    return new, {"rule": RULE, "annotation": line, "phrase": phrase, "field": field,
                 "base_sha256": hashlib.sha256(base_prompt.encode()).hexdigest(),
                 "keep_sha256": hashlib.sha256(new.encode()).hexdigest()}


def strip_annotation(keep_prompt_text, line):
    """Inverse used by validation: removing exactly the annotation line must give back the BASE prompt."""
    key = "\n" + line + "\n" + ANCHOR + "\n"
    if keep_prompt_text.count(key) != 1:
        raise AssertionError("annotation not found exactly once before the anchor")
    return keep_prompt_text.replace(key, "\n" + ANCHOR + "\n")


def build(pub):
    """From one public 1.20 target row: the KEEP+ID prompt and ledger, or None if RES-DET has no identity."""
    pi = RR.PublicInput.make(pub["prefix"], pub["target_text"], pub["registry_order"])
    det, res = identity(pi)
    if res is None or res["field"] is None:
        return None
    prompt, led = keep_prompt(pub["base_prompt"], pub["target_text"], det["text"], res["field"])
    led["detection"] = det
    led["resolution"] = res
    return prompt, led
