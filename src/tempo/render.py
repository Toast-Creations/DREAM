"""Exact model-visible text. Only rid, kind, status, event_at, received_at and payload of a record are rendered;
the scorer-only fields (key, _src, ordinal) and every gold value are never read here.

Arms: C0 (exact supported state at the query time, no records) and C1 (all records received by the cutoff).
Both use the same system instruction, domain rules, fixed facts, query wording and option mapping.
"""
import json

from .worlds import UNKNOWN, OBS_OPTION_TEXT

SYSTEM = (
    "You answer questions about a small world using a written log of records. How records work:\n"
    "1. A fact keeps its value until a recorded event changes it. Nothing changes without a recorded event.\n"
    "2. Records are listed in the order they were received. Each record also says what time the fact or event it "
    "reports belongs to. A record can arrive late: that time can be earlier than when it was received.\n"
    "3. The value of a fact at a given time comes from the record about the latest time that is not after it. "
    "A late-arriving record about an earlier time does not override a record about a later time. If two records "
    "are about the same time, the one received later counts.\n"
    "4. A verified correction names an earlier report that was wrong. That report's statement about the named fact "
    "is withdrawn and replaced by the correction's statement. A correction is not an event: nothing moved or "
    "changed when it arrived.\n"
    "5. A provisional report is accepted until a verified correction withdraws it. Verified records are never wrong.\n"
    "6. If the result of an event was not recorded, the fact is unknown among the stated possibilities until a "
    "later record settles it. A later observation, with no recorded event in between, also tells you what the value "
    "has been since that event.\n"
    "7. Answer only from the rules and records given. Use \"unknown\" when they do not determine a value.\n"
    "Reply with only the requested JSON object."
)


def _stmt(w, field, value):
    return w.fact(field, value)


def record_line(w, r):
    p, k = r["payload"], r["kind"]
    head = f"{r['rid']} | received at time {r['received_at']} | "
    if k == "initial":
        label = "provisional report (not yet verified)" if r["status"] == "provisional" else "verified observation"
        facts = "; ".join(_stmt(w, f, v) for f, v in p["assign"].items())
        return head + f"{label} | about time {r['event_at']}: {facts}."
    if k == "observation":
        label = "provisional report (not yet verified)" if r["status"] == "provisional" else "verified observation"
        return head + f"{label} | about time {r['event_at']}: {_stmt(w, p['field'], p['value'])}."
    if k == "change":
        return head + f"verified event | at time {r['event_at']}: {w.change(p['field'], p['from'], p['to'])}."
    if k == "uncertain_change":
        return head + f"verified event | at time {r['event_at']}: {w.uncertain(p['field'], p['from'], p['options'])}."
    if k == "correction":
        f = p["field"]
        return head + (f"verified correction of {p['target']} | {p['target']} was wrong about "
                       f"{_subject(w, f)}. In fact, from time {p['valid_from']}, {_stmt(w, f, p['value'])} "
                       f"(until a recorded event changes it).")
    raise ValueError(k)


def _subject(w, field):
    e = field.split(".")[0]
    if w.domain == "delivery":
        return f"where crate {e} rests"
    return f"whether part {e} is on hand" if field.endswith(".on_hand") else f"what slot {e} holds"


def state_lines(w, state):
    """V1.7.1: asked fields first, in the query's field order, then other entities in first-record order, so the
    listing order is the same on both sides of a pair (1.7.0 used first-assertion order, which moved a corrected
    field to the end on the correction side only)."""
    out = []
    order = [f for f in w.asked if f in state] + [f for f in state if f not in w.asked]
    for f in order:
        kind, val = state[f]
        out.append(_stmt(w, f, val) + "." if kind == "value" else w.unknown(f, list(val)) + ".")
    return [s[0].upper() + s[1:] for s in out]


def header(w):
    lines = [f"WORLD ({w.domain})", "", "Action rules:"] + ["- " + r for r in w.rules()]
    lines += ["", "Fixed facts (these never change):"] + ["- " + x for x in w.fixed_lines()]
    return lines


def evidence_block(w, arm, records, state, now):
    if arm == "C1":
        return ["", "Records received so far:"] + [record_line(w, r) for r in records] + ["", f"It is now time {now}."]
    if arm == "C0":
        return ["", f"It is now time {now}. Current state, worked out from all records received so far:"] + \
               ["- " + s for s in state_lines(w, state)]
    raise ValueError(arm)


def allowed_text(w, field):
    vals = w.allowed(field)
    return ", ".join(json.dumps(v) for v in vals)


def fields_block(w):
    return [f"- {json.dumps(f)}: one of {allowed_text(w, f)}" for f in w.asked]


def decision_query(w, option_map):
    lines = ["", "QUERY (decision)", w.goal_line(),
             "Choose the cheapest option whose plan is sure to be allowed at every step and to reach the goal, given "
             "what the records establish about now. If the records leave a needed fact unknown, so that no plan is "
             "sure to work, choose the option that asks for an observation first.", "Options:"]
    for oid, key in option_map.items():
        lines.append(f"[{oid}] " + (OBS_OPTION_TEXT if key == "OBS" else w.plan_text(key)))
    lines += ["", 'Reply with only a JSON object: {"choice": "<option ID>"}']
    return lines


def facts_query(w, qtype, t):
    if qtype == "S0":
        ask = "QUERY (current state): What is the value of each fact below now?"
    else:
        ask = (f"QUERY (state at an earlier time): What was the value of each fact below at time {t}? "
               "Use every record received so far.")
    example = ", ".join(f"{json.dumps(f)}: \"...\"" for f in w.asked)
    return ["", ask, "Facts:"] + fields_block(w) + \
           ["", 'Reply with only a JSON object: {"facts": {' + example + "}}"]


def action_query(w):
    example = ", ".join(f"{json.dumps(f)}: \"...\"" for f in w.asked)
    return ["", "QUERY (action consequence)", f"Suppose you were to do this one action now: {w.action_text()}. "
            "It has not been done; you are only considering it.",
            "If the action is not allowed right now it fails and changes nothing.",
            "Answer three things:",
            "1. \"applicable\": true if the action would be allowed right now, false if not, or \"unknown\" if the "
            "records do not settle it.",
            "2. \"predicted_next_facts\": the value of each fact below right after the action, if you did it.",
            "3. \"observed_world_facts\": the value of each fact below in the actual world now, given that you have "
            "only considered the action.", "Facts:"] + fields_block(w) + \
           ["", 'Reply with only a JSON object: {"applicable": ..., "predicted_next_facts": {' + example +
            '}, "observed_world_facts": {' + example + "}}"]


def user_prompt(w, arm, qtype, records, state, now, option_map=None, t=None):
    lines = header(w) + evidence_block(w, arm, records, state, now)
    if qtype in ("D0", "D1", "I1"):
        lines += decision_query(w, option_map)
    elif qtype in ("S0", "P0", "K0"):
        if arm != "C1":
            raise ValueError("state readouts run in C1 only")
        lines += facts_query(w, qtype, t)
    elif qtype == "A0":
        lines += action_query(w)
    else:
        raise ValueError(qtype)
    return "\n".join(lines)
