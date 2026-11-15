"""IGUARD-v0.1 identity-consistency decision. Public inputs only; rejection-only.

decide(prefix, target_text, registry, registry_order, raw) -> decision dict

Inputs (the complete decision interface; nothing else is accepted):
  prefix          original public prefix envelopes [{"record_id", "raw_text"}, ...]
  target_text     original public target text (never a rewritten SUB target)
  registry        public registry {field: [values]} used by the unchanged FACT-v1 compiler
  registry_order  public registry order (the resolver's registry tuple)
  raw             the saved raw model reply (str or None)

Rule, fixed before implementation (NEXT-STEP-PLAN.md, "Identity check"):
  1. Unchanged refres.detect + refres.resolve_det on the original description. Exactly one supported description and a
     unique registered stock field are required. Unresolved / ambiguous / unsupported / literal-only / no-entity /
     multiple descriptions -> ABSTAIN (never a silent pass).
  2. Unchanged factored.compile_reply with the public registry. A parse/structural rejection stays rejected and its
     original code is recorded. Nothing is repaired.
  3. For a compiled reply, the set of fields in its compiled assertions must be nonempty and equal {resolved field}.
     A different field or an extra field -> IDENTITY_MISMATCH. Raw-claim fields are logged as diagnostics only.
  4. guard_pass is True only for (resolved, compiled, field set == {resolved}). The evaluator composes
     final_accepted = original_accepted AND guard_pass, so the guard can never expand acceptance.
The raw reply and the compiled report are never modified; the decision only adds a disposition.
"""
import hashlib
import json

from tempo import factored as FA
from tempo import refres as RR

RULE = "IGUARD-v0.1"
SUPPORTED_KINDS = ("one_hop", "two_hop", "slot_join", "historical", "measure")


def _h(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def input_hashes(prefix, target_text, registry, registry_order, raw):
    return {"prefix": _h([[p["record_id"], p["raw_text"]] for p in prefix]), "target_text": _h(target_text),
            "registry": _h(registry), "registry_order": _h(list(registry_order)), "raw": _h(raw)}


def resolve(prefix, target_text, registry_order):
    """Public subject: {"status": resolved|unresolved|unsupported, "field", "reason", "detection", "trace"}."""
    det = RR.detect(target_text)
    if det["route"] != "resolve":
        # bypass (literal-only) and pending (multiple descriptions / no entity) are outside this narrow policy
        reason = det.get("reason") or det["route"]
        return {"status": "unsupported", "field": None, "reason": f"{det['route']}:{reason}", "detection": det,
                "trace": None}
    if det["kind"] not in SUPPORTED_KINDS:
        return {"status": "unsupported", "field": None, "reason": f"unsupported_kind:{det['kind']}", "detection": det,
                "trace": None}
    pi = RR.PublicInput.make(prefix, target_text, registry_order)
    res = RR.resolve_det(pi, det)
    field = res["field"]
    if field is None:
        return {"status": "unresolved", "field": None, "reason": res["reason"], "detection": det, "trace": res["trace"]}
    if not field.endswith(".on_hand") or field not in pi.registry:   # defensive; resolve_det already enforces both
        return {"status": "unresolved", "field": None, "reason": "not_registered_stock_field", "detection": det,
                "trace": res["trace"]}
    return {"status": "resolved", "field": field, "reason": None, "detection": det, "trace": res["trace"]}


def decide(prefix, target_text, registry, registry_order, raw):
    prefix = [{"record_id": p["record_id"], "raw_text": p["raw_text"]} for p in prefix]
    res = resolve(prefix, target_text, list(registry_order))
    rep, tr = FA.compile_reply(raw, registry)
    claims = tr.get("claims") or {}
    raw_fields = sorted({a.get("field") for k in FA.LISTS for a in (claims.get(k) or []) if isinstance(a, dict)},
                        key=str)
    compiled = rep is not None
    fields = sorted({a["field"] for a in rep["assertions"]}) if compiled else None

    if res["status"] != "resolved":
        disposition, mismatch = "abstain", None
    elif not compiled:
        disposition, mismatch = "compile_rejected", None
    elif not fields:
        disposition, mismatch = "no_compiled_fields", None
    elif fields == [res["field"]]:
        disposition, mismatch = "pass", None
    else:
        disposition = "identity_mismatch"
        mismatch = "extra_field" if res["field"] in fields else "different_field"

    return {
        "rule": RULE,
        "input_sha256": input_hashes(prefix, target_text, registry, registry_order, raw),
        "resolver": {"status": res["status"], "field": res["field"], "reason": res["reason"],
                     "detection": res["detection"], "trace": res["trace"]},
        "compile": {"compiled": compiled, "code": tr.get("code"), "parse_error": tr.get("parse_error"),
                    "type": rep["type"] if compiled else None},
        "compiled_fields": fields,
        "raw_fields": raw_fields,
        "raw_fields_differ_from_resolved": (res["field"] is not None and bool(raw_fields)
                                            and raw_fields != [res["field"]]),
        "disposition": disposition,
        "mismatch_kind": mismatch,
        "guard_pass": disposition == "pass",
    }
