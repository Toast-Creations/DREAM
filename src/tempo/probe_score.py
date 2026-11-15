"""Deterministic scoring for the precondition probe (no judge, no retries for content).

Direct and supplied conditions use the existing A0 scorer unchanged. Checklist-first replies must have exactly the
top-level keys preconditions, applicable, predicted_next_facts, observed_world_facts (any order; the actual order is
recorded) and a preconditions object with exactly the listed requirement keys, each true, false or "unknown"
(JSON booleans or the strings "true"/"false"/"unknown", any case; V1.7.4 amendment P1: also "yes"/"no", any
case, for requirement values only — found in smoke, where assembly replies used the on-hand vocabulary). The remaining three fields are then scored by the
existing A0 scorer. Any parse failure makes the whole reply invalid (scored wrong on every outcome).
"""
import json

from . import score as S
from .probe import conj3
from .worlds import UNKNOWN


def _derived(r, gold):
    pred, obs = r["predicted"] or {}, r["observed"] or {}
    changed = [f for f in gold["predicted"] if gold["predicted"][f] != UNKNOWN and gold["observed"][f] != UNKNOWN
               and gold["predicted"][f] != gold["observed"][f]]
    ok = lambda d, fs: [bool(d) and d[f]["correct"] for f in fs]
    pe = bool(pred) and all(v["correct"] for v in pred.values())
    oe = bool(obs) and all(v["correct"] for v in obs.values())
    model_app = r["applicable"]
    model_noeffect = bool(pred) and bool(obs) and all(pred[f]["got"] == obs[f]["got"] for f in pred)
    return {"predicted_exact": pe, "observed_exact": oe,
            "changed_correct": all(ok(pred, changed)) if changed else None, "n_changed": len(changed),
            "preserve_acc": (sum(ok(pred, gold["preserve_fields"])) / len(gold["preserve_fields"]))
            if gold["preserve_fields"] else None,
            "a0_all": r["applicable_correct"] and pe and oe,
            "model_applicable": "unknown" if model_app == UNKNOWN else model_app,
            # transition gating as answered: rejected (false) yet predicted a change
            "gating_inconsistent": r["valid"] and model_app is False and not model_noeffect,
            "blocked_and_no_effect": r["applicable_correct"] and gold["applicable"] is False and pe}


def score_probe(text, gold, condition, pred_keys):
    if condition != "checklist":
        r = S.score_action(text, gold["allowed"], gold)
        r.update(_derived(r, gold), preconditions_valid=None, order=None)
        return r
    obj, err = S.parse_object(text)
    base = {"valid": False, "error": err, "applicable": None, "applicable_correct": False, "predicted": None,
            "observed": None, "extra_fields": None, "preconditions_valid": False, "order": None}
    if err is not None:
        base.update(_derived(base, gold))
        return base
    base["order"] = list(obj)
    if set(obj) != {"preconditions", "applicable", "predicted_next_facts", "observed_world_facts"}:
        base["error"] = "bad_top_level_keys"
        base.update(_derived(base, gold))
        return base
    pre = obj["preconditions"]
    preds = None
    if isinstance(pre, dict) and set(pre) == set(pred_keys):
        preds = {k: _pred_value(pre[k]) for k in pred_keys}
        if any(v is None for v in preds.values()):
            preds = None
    rest = {k: obj[k] for k in ("applicable", "predicted_next_facts", "observed_world_facts")}
    r = S.score_action(json.dumps(rest), gold["allowed"], gold)
    if preds is None:
        r.update(valid=False, error=r["error"] or "bad_preconditions", applicable_correct=False)
        r["preconditions_valid"] = False
    else:
        r["preconditions_valid"] = True
        gp = gold["predicates"]
        r["model_predicates"] = {k: tv(v) for k, v in preds.items()}
        r["pred_correct"] = {k: preds[k] == gp[k] for k in pred_keys}
        r["pred_vector_exact"] = all(r["pred_correct"].values())
        r["false_certainty"] = sum(1 for k in pred_keys if gp[k] == UNKNOWN and preds[k] != UNKNOWN)
        r["unneeded_unknown"] = sum(1 for k in pred_keys if gp[k] != UNKNOWN and preds[k] == UNKNOWN)
        r["wrong_definite"] = sum(1 for k in pred_keys if gp[k] != UNKNOWN and preds[k] not in (UNKNOWN, gp[k]))
        if r["applicable"] is not None:
            r["consistent_with_own_predicates"] = conj3(preds.values()) == r["applicable"]
    r["order"] = base["order"]
    if not r["valid"]:
        r["applicable_correct"] = False
    r.update(_derived(r, gold))
    return r


def _pred_value(v):
    if isinstance(v, str) and v.strip().lower() in ("yes", "no"):
        return v.strip().lower() == "yes"
    return S._applicable(v)


def tv(v):
    return "unknown" if v == UNKNOWN else v
