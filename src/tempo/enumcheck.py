"""Resolver 2: consistency filtering over every trajectory the records allow. Shares no code with resolve.py.

Instead of picking "the latest assertion", this builds each field's possible trajectories: the initial value (after
corrections), then every recorded change applied at its time (an unrecorded-result change branches over its options).
Observations are not setters here; they are constraints the trajectory must satisfy at their time, and every change's
'from' must match. A field's supported value at time t is the set of values over all consistent trajectories; a
singleton is a value, otherwise 'unknown'. A record set with no consistent trajectory is a defective item.

Same-time convention: an event at time t takes effect at t; an observation about time t sees the state after it.
"""
import itertools


class Inconsistent(Exception):
    pass


def _by_field(records):
    corrections = {}
    for r in records:
        if r["kind"] == "correction":
            p = r["payload"]
            corrections[(p["target"], p["field"])] = p
    starts, events, checks = {}, {}, {}
    for r in records:
        p, k = r["payload"], r["kind"]
        if k == "initial":
            for f, v in p["assign"].items():
                c = corrections.get((r["rid"], f))
                if c is not None:
                    if c["valid_from"] != r["event_at"]:
                        raise Inconsistent("correction interval does not start at the corrected report's time")
                    v = c["value"]
                starts[f] = (r["event_at"], v)
        elif k == "observation":
            c = corrections.get((r["rid"], p["field"]))
            value, at = (c["value"], c["valid_from"]) if c is not None else (p["value"], r["event_at"])
            checks.setdefault(p["field"], []).append((at, value))
        elif k in ("change", "uncertain_change"):
            opts = [p["to"]] if k == "change" else list(p["options"])
            events.setdefault(p["field"], []).append((r["event_at"], p["from"], opts))
    for (target, f), c in corrections.items():
        if not any(r["rid"] == target for r in records):
            raise Inconsistent(f"correction targets missing report {target}")
    return starts, events, checks


def _trajectories(start, evs, checks):
    """Yield consistent trajectories as sorted lists of (time, value)."""
    evs = sorted(evs, key=lambda e: e[0])
    for choice in itertools.product(*[e[2] for e in evs]):
        traj, cur, ok = [start], start[1], True
        for (t, frm, _), to in zip(evs, choice):
            if t < start[0] or frm != cur:
                ok = False; break
            cur = to
            traj.append((t, cur))
        if not ok:
            continue
        if all(_val(traj, t) == v for t, v in checks):
            yield traj


def _val(traj, t):
    v = None
    for when, value in traj:
        if when <= t:
            v = value
    return v


def supported(records, field, t):
    starts, events, checks = _by_field(records)
    if field not in starts:
        # a field first described by an observation (padding entities): that observation is its start
        obs = sorted(checks.get(field, []))
        if not obs:
            raise KeyError(field)
        start, rest = obs[0], obs[1:]
    else:
        start, rest = starts[field], checks.get(field, [])
    if t < start[0]:
        raise KeyError(f"{field} undefined before {start[0]}")
    trajs = list(_trajectories(start, events.get(field, []), rest))
    if not trajs:
        raise Inconsistent(f"no trajectory of {field} satisfies the records")
    values = sorted({_val(tr, t) for tr in trajs})
    return ("value", values[0]) if len(values) == 1 else ("unknown", values)


def supported_set(records, fields, t):
    """All joint assignments consistent with the records at time t (fields are independent in this pilot)."""
    per = {f: supported(records, f, t) for f in fields}
    choices = [[v[1]] if v[0] == "value" else v[1] for v in per.values()]
    return per, [dict(zip(per, combo)) for combo in itertools.product(*choices)]
