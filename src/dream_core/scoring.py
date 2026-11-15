"""Strict typed scoring, deliberately independent of ML frameworks."""
import json
import re


def parse_answer(text, answer_type):
    if not isinstance(text, str) or len(text) > 4096:
        return None, False
    value = text.strip()
    if value.startswith("{"):
        try:
            obj = json.loads(value, object_pairs_hook=_unique_object)
        except (ValueError, TypeError):
            return None, False
        if not isinstance(obj, dict) or set(obj) != {"answer"}:
            return None, False
        value = obj["answer"]
    if answer_type == "integer":
        if type(value) is int:
            return value, True
        if isinstance(value, str) and re.fullmatch(r"[+-]?\d{1,12}", value):
            return int(value), True
    elif answer_type == "boolean":
        if type(value) is bool:
            return value, True
        if isinstance(value, str) and value.lower() in {"yes", "no", "true", "false"}:
            return value.lower() in {"yes", "true"}, True
    elif answer_type == "string":
        if isinstance(value, str) and value and "\n" not in value:
            return value, True
    else:
        raise ValueError(f"Unsupported answer type: {answer_type}")
    return None, False


def _unique_object(pairs):
    result = {}
    for k, v in pairs:
        if k in result:
            raise ValueError("Duplicate JSON key")
        result[k] = v
    return result


def score(prediction, reference, answer_type):
    expected = {"integer": int, "boolean": bool, "string": str}.get(answer_type)
    if expected is None or type(reference) is not expected:
        raise ValueError("Reference does not match its declared type")
    parsed, valid = parse_answer(prediction, answer_type)
    return {"parsed": parsed, "valid": valid, "correct": bool(valid and parsed == reference)}


def accuracy(rows, category):
    group = [r for r in rows if r["category"] == category]
    if not group:
        return None
    return sum(bool(r["correct"]) for r in group) / len(group)
