"""Strict parsing and deterministic scoring. No retries for model content; no judge.

Accepted reply: optional surrounding whitespace and at most one surrounding markdown code fence (``` or ```json),
around exactly one JSON object. Anything else (extra prose, two objects, duplicate keys, truncation) is invalid,
and an invalid reply scores 0 on every outcome of that call.

Value matching for facts: case-insensitive, surrounding whitespace and a trailing full stop ignored, and an optional
leading entity word ("place ", "crate ", "part ", "slot ") ignored. On-hand fields also accept JSON booleans.
"applicable" accepts JSON true/false or the string "unknown" (any case), and "true"/"false" strings.
A missing field scores wrong; an extra field is recorded and ignored; a value outside the allowed list scores wrong.
"""
import json
import re

FENCE = re.compile(r"^```(?:json)?\s*\n?(.*?)\n?```$", re.S)
UNKNOWN = "unknown"


class _Dup(Exception):
    pass


def _no_dups(pairs):
    keys = [k for k, _ in pairs]
    if len(keys) != len(set(keys)):
        raise _Dup()
    return dict(pairs)


def parse_object(text):
    """(obj, error). error is None on success."""
    s = text.strip()
    m = FENCE.match(s)
    if m:
        s = m.group(1).strip()
    if not s.startswith("{"):
        return None, "no_json_object"
    try:
        obj = json.loads(s, object_pairs_hook=_no_dups)
    except _Dup:
        return None, "duplicate_key"
    except ValueError:
        return None, "malformed_or_extra_text"
    if not isinstance(obj, dict):
        return None, "not_object"
    return obj, None


def norm(v):
    if isinstance(v, bool):
        return "yes" if v else "no"
    if not isinstance(v, str):
        return None
    s = v.strip().rstrip(".").strip().lower()
    for pre in ("place ", "crate ", "part ", "slot "):
        if s.startswith(pre):
            s = s[len(pre):]
    return s


def match_value(raw, allowed):
    n = norm(raw)
    for a in allowed:
        if n is not None and n == a.lower():
            return a
    return None


def score_decision(text, option_ids, gold):
    obj, err = parse_object(text)
    choice = None
    if err is None:
        c = obj.get("choice")
        if set(obj) != {"choice"} or not isinstance(c, str) or c.strip().upper() not in option_ids:
            err = "bad_choice"
        else:
            choice = c.strip().upper()
    return {"valid": err is None, "error": err, "choice": choice,
            "correct": choice is not None and choice in gold["acceptable"],
            "lure": choice is not None and choice == gold.get("lure_option"),
            "other_side": choice is not None and choice == gold.get("pair_other_option"),
            "obs_chosen": choice is not None and choice == gold.get("obs_option")}


def _fields(obj, allowed_map, gold_map):
    out, extra = {}, []
    if not isinstance(obj, dict):
        return None, None
    for f in obj:
        if f not in allowed_map:
            extra.append(f)
    for f, allowed in allowed_map.items():
        got = match_value(obj[f], allowed) if f in obj else None
        out[f] = {"got": got, "raw": obj.get(f), "gold": gold_map[f], "correct": got is not None and got == gold_map[f]}
    return out, extra


def score_facts(text, allowed_map, gold_map):
    obj, err = parse_object(text)
    fields, extra = (None, None)
    if err is None:
        if set(obj) != {"facts"}:
            err = "bad_top_level_keys"
        else:
            fields, extra = _fields(obj["facts"], allowed_map, gold_map)
            if fields is None:
                err = "facts_not_object"
    valid = err is None and bool(fields) and all(v["got"] is not None for v in fields.values())
    return {"valid": valid, "error": err if err else (None if valid else "missing_or_disallowed_value"),
            "fields": fields, "extra_fields": extra,
            "exact": bool(fields) and err is None and all(v["correct"] for v in fields.values())}


def _applicable(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        s = v.strip().lower()
        return {"true": True, "false": False, "unknown": UNKNOWN}.get(s)
    return None


def score_action(text, allowed_map, gold):
    obj, err = parse_object(text)
    res = {"valid": False, "error": err, "applicable": None, "applicable_correct": False,
           "predicted": None, "observed": None, "extra_fields": None}
    if err is not None:
        return res
    if set(obj) != {"applicable", "predicted_next_facts", "observed_world_facts"}:
        res["error"] = "bad_top_level_keys"
        return res
    app = _applicable(obj["applicable"])
    pred, ex1 = _fields(obj["predicted_next_facts"], allowed_map, gold["predicted"])
    obs, ex2 = _fields(obj["observed_world_facts"], allowed_map, gold["observed"])
    if pred is None or obs is None:
        res["error"] = "facts_not_object"
        return res
    ok = app is not None and all(v["got"] is not None for v in list(pred.values()) + list(obs.values()))
    res.update(valid=ok, error=None if ok else "missing_or_disallowed_value", applicable=app,
               applicable_correct=app is not None and app == gold["applicable"], predicted=pred, observed=obs,
               extra_fields=(ex1 or []) + (ex2 or []))
    return res
