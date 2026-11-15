"""Resolver 1: rule-based evidence timeline (implements the printed record rules directly).

Records (see records schema in SCHEMAS.md) are dicts with rid, kind, status, event_at, received_at, ordinal and a
payload. A query sees only records with received_at <= cutoff (the caller filters, see `prefix`).

Rules implemented here (identical to the system prompt):
 1 persistence: a fact keeps its value until a recorded event changes it;
 3 latest event time wins (ties: the later-received record, i.e. higher ordinal);
 4 a verified correction withdraws the named report's statement about the named field and asserts its replacement
   from valid_from; it is not an event;
 5 uncorrected provisional statements are accepted;
 6 an unrecorded-result change makes the field unknown among its options; the next later assertion of that field,
   if it is an observation (or a change whose 'from' is given), settles the value back to that change.
"""
UNKNOWN = "unknown"


def prefix(records, cutoff):
    return [r for r in records if r["received_at"] <= cutoff]


def _assertions(records):
    withdrawn = {(r["payload"]["target"], r["payload"]["field"]) for r in records if r["kind"] == "correction"}
    out = []
    for r in records:
        p, k = r["payload"], r["kind"]
        if k == "initial":
            for f, v in p["assign"].items():
                if (r["rid"], f) not in withdrawn:
                    out.append((f, r["event_at"], r["ordinal"], "obs", v))
        elif k == "observation":
            if (r["rid"], p["field"]) not in withdrawn:
                out.append((p["field"], r["event_at"], r["ordinal"], "obs", p["value"]))
        elif k == "change":
            out.append((p["field"], r["event_at"], r["ordinal"], "change", (p["from"], p["to"])))
        elif k == "uncertain_change":
            out.append((p["field"], r["event_at"], r["ordinal"], "maybe", (p["from"], tuple(p["options"]))))
        elif k == "correction":
            out.append((p["field"], p["valid_from"], r["ordinal"], "obs", p["value"]))
        else:
            raise ValueError(k)
    return out


def value_at(records, field, t):
    """('value', v) or ('unknown', sorted options). Raises if the field has no assertion at or before t."""
    rows = sorted((a for a in _assertions(records) if a[0] == field), key=lambda a: (a[1], a[2]))
    upto = [a for a in rows if a[1] <= t]
    if not upto:
        raise KeyError(f"no record about {field} at or before {t}")
    last = upto[-1]
    if last[3] == "obs":
        return ("value", last[4])
    if last[3] == "change":
        return ("value", last[4][1])
    options = last[4][1]
    later = rows[rows.index(last) + 1:]
    if later:
        nxt = later[0]
        if nxt[3] == "obs" and nxt[4] in options:
            return ("value", nxt[4])
        if nxt[3] == "change" and nxt[4][0] in options:
            return ("value", nxt[4][0])
    return ("unknown", sorted(options))


def fields_of(records):
    out = []
    for f, *_ in _assertions(records):
        if f not in out:
            out.append(f)
    return out


def state_at(records, t, fields=None):
    return {f: value_at(records, f, t) for f in (fields or fields_of(records))}
