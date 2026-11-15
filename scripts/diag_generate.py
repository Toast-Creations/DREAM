"""Build the V1.7.2 diagnostic's committed inputs (no model) from the 1.7.1 pilot's committed groups.

Usage: diag_generate.py --pilot-hub PILOT --hub HUB --set diag|diagsmoke
Reads PILOT/data (read-only; hashes checked against its commitments). Each group is rebuilt from its committed seed
with the same generator and must equal the stored group exactly, so no group is re-sampled or replaced.
Writes HUB/data/<set>-calls.jsonl, <set>-gold.jsonl, <set>-step2-templates.jsonl and COMMITMENT-<set>.json.
Refuses to overwrite an existing commitment.
"""
import argparse
import hashlib
import json
from pathlib import Path

from _bootstrap import ROOT
from dream_core.ledger import release_source_hash
from tempo import diag as D, generate as G, render

CAPS = {"D": 64, "S": 384, "A0": 512}
L = "short"
# smoke: (pool group index, list of (block, arm, item)) — item: D0/D1 (decision side), C:a|b, D:valid|invalid|unc
SMOKE_PLAN = [
    (0, [("B", "C1", "D0"), ("C", "C1", "a"), ("D", "C1", "valid"), ("D", "C1", "invalid"),
         ("E", "C0", "D1")]),                                      # delivery p3 (correction)
    (1, [("A", "C1", "D0"), ("B", "C0", "D0"), ("D", "C0", "valid"), ("D", "C0", "invalid"),
         ("D", "C1", "unc")]),                                     # delivery p6 (uncertain)
    (2, [("A", "C0", "D1"), ("C", "C1", "b"), ("D", "C0", "valid"), ("D", "C0", "invalid")]),  # assembly p2 stock
    (3, [("B", "C1", "D1"), ("D", "C1", "valid"), ("D", "C1", "invalid"), ("E", "C1", "D0")]),  # assembly p5 slot
]
SMOKE_REPEATS = ["main-del-p1-0|short|C0|D0", "main-del-p1-0|short|C1|D0",
                 "main-ass-p3-0|short|C0|D1", "main-ass-p3-0|short|C1|D1"]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]


def rebuild(pilot_data, pool):
    commit = json.loads((pilot_data / f"COMMITMENT-{pool}.json").read_text())
    for part in ("groups", "calls", "gold"):
        if sha(pilot_data / f"{pool}-{part}.jsonl") != commit[f"{part}_sha256"]:
            raise SystemExit(f"pilot {pool}-{part} does not match its commitment")
    stored = load(pilot_data / f"{pool}-groups.jsonl")
    out = []
    for sg in stored:
        w, g = G.build_group(sg["group_id"], sg["domain"], sg["pattern"], sg["seed"], sg["pool"], sg["focal_kind"])
        a = json.dumps(json.loads(json.dumps(g)), sort_keys=True)
        b = json.dumps({k: v for k, v in sg.items() if k != "world"}, sort_keys=True)
        if a != b:
            raise SystemExit(f"rebuilt group {sg['group_id']} differs from the committed group")
        out.append((w, g))
    return commit, out


def base_row(g, block, arm, qtype, variant, records, now, cap, user_text, option_ids=None, extra=None):
    cid = f"{g['group_id']}|{L}|{block}|{arm}|{qtype}|{variant}"
    row = {"call_id": cid, "group_id": g["group_id"], "domain": g["domain"], "pattern": g["pattern"],
           "pattern_name": g["pattern_name"], "length": L, "block": block, "arm": arm, "qtype": qtype,
           "variant": variant, "n_records": len(records) if arm == "C1" else 0, "evidence_cutoff": now,
           "option_ids": option_ids, "max_new_tokens": cap, "system": render.SYSTEM, "user": user_text,
           "user_sha256": hashlib.sha256(user_text.encode()).hexdigest()}
    row.update(extra or {})
    return row


def decision_call(w, g, block, arm, side, drop_obs=False):
    var = g["variants"][L]
    recs, now = var[side]["records"], g["now"]
    state = var[side]["now_state"] if arm == "C0" else None
    q = D.decision_query(w, g["option_map"], D.POLICIES["A" if block == "A" else ("E" if block == "E" else "B")],
                         drop_obs=drop_obs)
    ids = sorted(L_ for L_, k in g["option_map"].items() if not (drop_obs and k == "OBS"))
    qtype = {"a": "D0", "b": "D1"}[side]
    row = base_row(g, block, arm, qtype, side, recs, now, CAPS["D"], D.user(w, arm, recs, state, now, q), ids)
    gold = {"call_id": row["call_id"], **D.decision_gold(w, g, var, side, drop_obs=drop_obs)}
    return row, gold


def c_calls(w, g, side):
    """Step-1 call (C1 current-state readout under B's packet) and the frozen step-2 template."""
    var = g["variants"][L]
    recs, now = var[side]["records"], g["now"]
    head = D.head_text(w, "C1", recs, None, now)
    u1 = head + "\n" + "\n".join(render.facts_query(w, "S0", None))
    qtype = {"a": "D0", "b": "D1"}[side]
    r1 = base_row(g, "C", "C1", "S0", side, recs, now, CAPS["S"], u1, extra={"step": 1})
    gold_state = G.flat({f: var[side]["now_state"][f] for f in w.asked})
    g1 = {"call_id": r1["call_id"], "type": "facts", "gold": gold_state, "allowed": {f: w.allowed(f) for f in w.asked},
          "focal_field": g["focal_field"], "side_field": g["side_field"]}
    tail = "\n".join(D.decision_query(w, g["option_map"], D.POLICY_B))
    ids = sorted(g["option_map"])
    meta = {k: r1[k] for k in ("group_id", "domain", "pattern", "pattern_name", "length", "arm", "n_records",
                                "evidence_cutoff")}
    tmpl = {"step1_call_id": r1["call_id"], "call_id": f"{g['group_id']}|{L}|C|C1|{qtype}|{side}",
            "block": "C", "qtype": qtype, "variant": side, "step": 2, "option_ids": ids, "max_new_tokens": CAPS["D"],
            "system": render.SYSTEM, "head": head, "tail": tail, **meta,
            "gold": {"call_id": f"{g['group_id']}|{L}|C|C1|{qtype}|{side}", **D.decision_gold(w, g, var, side)}}
    return r1, g1, tmpl


def action_call(w, g, arm, label, v):
    recs, now = v["records"], g["now"]
    state = v["now_state"] if arm == "C0" else None
    u = D.user(w, arm, recs, state, now, render.action_query(w))
    row = base_row(g, "D", arm, "A0", label, recs, now, CAPS["A0"], u, extra={"origin": v["origin"]})
    gold = {"call_id": row["call_id"], "type": "action", **v["a0"], "allowed": {f: w.allowed(f) for f in w.asked}}
    return row, gold


def items_for_group(w, g, plan=None):
    """All diagnostic calls for one group (plan=None: the full core + E matrix)."""
    calls, golds, tmpls = [], [], []
    var = g["variants"][L]
    dv = D.d_variants(w, g)
    unc = {"records": var["a"]["records"], "now_state": var["a"]["now_state"], "a0": var["A0"],
           "origin": "side a, original uncertain A0 control"} if g["pattern"] == 6 else None
    if plan is None:
        plan = [(b, arm, s) for b in ("A", "B") for arm in ("C0", "C1") for s in ("D0", "D1")]
        plan += [("C", "C1", s) for s in ("a", "b")]
        plan += [("D", arm, x) for arm in ("C0", "C1") for x in ("valid", "invalid")]
        if unc:
            plan += [("D", arm, "unc") for arm in ("C0", "C1")]
        plan += [("E", arm, s) for arm in ("C0", "C1") for s in ("D0", "D1")
                 if var[{"D0": "a", "D1": "b"}[s]]["key"] != "OBS"]
    for block, arm, item in plan:
        if block in ("A", "B", "E"):
            side = {"D0": "a", "D1": "b"}[item]
            if block == "E" and var[side]["key"] == "OBS":
                raise AssertionError("E is for determined rows only")
            r, gd = decision_call(w, g, block, arm, side, drop_obs=(block == "E"))
            calls.append(r); golds.append(gd)
        elif block == "C":
            r, gd, t = c_calls(w, g, item)
            calls.append(r); golds.append(gd); tmpls.append(t)
        else:
            v = unc if item == "unc" else dv[item]
            r, gd = action_call(w, g, arm, {"unc": "uncertain"}.get(item, item), v)
            calls.append(r); golds.append(gd)
    return calls, golds, tmpls


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot-hub", required=True)
    ap.add_argument("--hub", required=True)
    ap.add_argument("--set", choices=["diag", "diagsmoke"], required=True)
    a = ap.parse_args()
    pilot_data = Path(a.pilot_hub) / "data"
    data = Path(a.hub) / "data"
    data.mkdir(parents=True, exist_ok=True)
    commit_path = data / f"COMMITMENT-{a.set}.json"
    if commit_path.exists():
        raise SystemExit(f"{commit_path} exists; inputs are committed")
    calls, golds, tmpls = [], [], []
    if a.set == "diag":
        pc, built = rebuild(pilot_data, "main")
        for w, g in built:
            c, gd, t = items_for_group(w, g)
            calls += c; golds += gd; tmpls += t
    else:
        pc, built = rebuild(pilot_data, "smoke")
        for idx, plan in SMOKE_PLAN:
            w, g = built[idx]
            c, gd, t = items_for_group(w, g, plan)
            calls += c; golds += gd; tmpls += t
        main_calls = {c["call_id"]: c for c in load(pilot_data / "main-calls.jsonl")}
        main_gold = {c["call_id"]: c for c in load(pilot_data / "main-gold.jsonl")}
        for cid in SMOKE_REPEATS:
            c = dict(main_calls[cid], call_id="repeat|" + cid, block="R", repeat_of=cid)
            calls.append(c); golds.append(dict(main_gold[cid], call_id="repeat|" + cid))
    if len({c["call_id"] for c in calls}) != len(calls):
        raise SystemExit("duplicate call ids")
    for name, rows in (("calls", calls), ("gold", golds), ("step2-templates", tmpls)):
        with open(data / f"{a.set}-{name}.jsonl", "w") as fh:
            for r in rows:
                fh.write(json.dumps(r, sort_keys=True) + "\n")
    import collections
    rec = {"set": a.set, "source_sha256": release_source_hash(ROOT), "calls": len(calls),
           "step2_templates": len(tmpls), "pilot_commitment": {k: pc[k] for k in pc if k.endswith("sha256")},
           "by_block": dict(collections.Counter(c["block"] for c in calls)),
           **{f"{p.replace('-', '_')}_sha256": sha(data / f"{a.set}-{p}.jsonl")
              for p in ("calls", "gold", "step2-templates")}}
    commit_path.write_text(json.dumps(rec, indent=2) + "\n")
    print(json.dumps({k: rec[k] for k in ("set", "calls", "step2_templates", "by_block", "calls_sha256")}))


if __name__ == "__main__":
    main()
