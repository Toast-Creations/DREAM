"""Adapters from saved DREAM temporal artifacts to the engine's public inputs (fixtures only; not used by the engine).

public_record strips scorer/generator fields (key, _src, ordinal) so only the public schema reaches the engine.
spec_from_world builds the episode's fixed facts from the same values the prompts printed (worlds.py fixed_lines,
plus the 1.7.2 domain statements: all roads open, no adapters). The entity registry lists every entity the episode's
public text names (fixed facts and records).
"""
from .engine import CARRIED

PUBLIC = ("rid", "kind", "status", "event_at", "received_at", "payload")


def public_record(r, source="env"):
    out = {k: r[k] for k in PUBLIC}
    out["source"] = source
    return out


def _ents(records, attr):
    out = []
    for r in records:
        p = r["payload"]
        fs = list(p["assign"]) if r["kind"] == "initial" else [p["field"]]
        for f in fs:
            e, a = f.split(".")
            if a == attr and e not in out:
                out.append(e)
    return out


def spec_from_world(world, domain, records, carried=None):
    if domain == "delivery":
        crates = [world["x"], world["y"], world["z"]] + [e for e in _ents(records, "location")
                                                          if e not in (world["x"], world["y"], world["z"])]
        return {"domain": "delivery", "places": world["places"], "roads": world["roads"], "closed": [],
                "agent_at": world["you"], "crates": crates, "non_portable": []}
    parts = {p: v for p, v in world["parts"].items()}
    return {"domain": "assembly", "slots": {world["t"]: world["k"], world["s2"]: world["k2"]}, "parts": parts,
            "prices": {world["g"]: world["price"]}, "adapters": {}, "fitted": {},
            "extra_parts": [e for e in _ents(records, "on_hand") if e not in parts]}


def engine_for(world, domain, records, context="ctx"):
    from .engine import Engine
    eng = Engine(spec_from_world(world, domain, records), context)
    for r in records:
        eng.ingest_report(public_record(r))
    return eng


def flat_now_state(now_state):
    return {f: (v[1] if v[0] == "value" else "unknown") for f, v in now_state.items()}
