"""V1.8.2 paired prose-robustness study: surfaces, prompts and the prose equivalence check (no model)."""
import json
import re

from . import diag, history as Hm, render
from .prose import prose_line
from .worlds import CARRIED, EMPTY, YES

SURFACES = ("lines", "prose")


def line_fn(w, h, surface):
    if surface == "lines":
        return lambda r: render.record_line(w, r)
    return lambda r: prose_line(w, r, h["seed"])


def extraction_prompt(w, h, surface, k):
    """Same fixed instruction for both surfaces; only the record text differs."""
    recs, line = h["records"], line_fn(w, h, surface)
    prior, new = recs[:k - 1], recs[k - 1]
    lines = diag.header_complete(w)
    lines += ["", "Records received before this one (context only):"]
    lines += [line(r) for r in prior] if prior else ["(none)"]
    lines += ["", "New record to convert:", line(new), ""] + Hm.EXTRACT_QUERY
    lines += ["Fields and allowed values:"]
    lines += [f"- {json.dumps(f)}: one of " + ", ".join(json.dumps(x) for x in Hm.allowed_values(w, f))
              for f in Hm.registry_fields(w, recs[:k])]
    lines += Hm.EXTRACT_REPLY
    return "\n".join(lines)


def _vals_text(f, v):
    if f.endswith(".location"):
        return ["carr"] if v == CARRIED else [v]
    if f.endswith(".on_hand"):
        return ["not on hand", "do not have", "no longer on hand"] if v != YES else ["on hand"]
    return ["empty", "nothing is installed"] if v == EMPTY else [v]


def check_equivalent(r, text):
    """Raise unless the prose names everything the typed record asserts (necessary conditions, checked for every
    rendering; full equivalence was also reviewed by reading every template)."""
    def need(cond, what):
        if not cond:
            raise AssertionError(f"{r['rid']}: prose lacks {what}: {text}")
    need(re.search(rf"\b{r['rid']}\b", text), "record ID")
    need(re.search(rf"time {r['received_at']}\b", text), "reception time")
    p, k = r["payload"], r["kind"]
    if k == "correction":
        need(text.count(p["target"]) >= 2, "target")
        need(re.search(rf"time {p['valid_from']}\b", text), "validity start")
        need("verified correction" in text.lower(), "correction status")
    else:
        need(re.search(rf"time {r['event_at']}\b", text), "event time")
    if r["status"] == "provisional":
        need("provisional" in text and "verified" not in text.replace("not yet verified", "").replace(
            "not been verified", ""), "provisional status only")
    else:
        need("verified" in text.lower() or "confirmed" in text.lower(), "verified status")
        need("provisional" not in text.lower() and "unconfirmed" not in text.lower(), "no provisional wording")
    pairs = list(p["assign"].items()) if k == "initial" else [(p["field"], p.get("value"))]
    for f, v in pairs:
        need(f.split(".")[0] in text, f"entity of {f}")
        if v is not None:
            need(any(x in text for x in _vals_text(f, v)), f"value {v} of {f}")
    if k in ("change", "uncertain_change"):
        need(p["from"] in text or not p["field"].endswith(".location"), "from value")
    if k == "change":
        need(any(x in text for x in _vals_text(p["field"], p["to"])), "to value")
    if k == "uncertain_change":
        need("either" in text and "not" in text, "unrecorded result wording")
        for o in p["options"]:
            need(any(x in text for x in _vals_text(p["field"], o)), f"option {o}")
