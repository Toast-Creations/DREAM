"""V1.11.0 analysis: strict vs scoped current-observation authority under P2 (development; descriptive). No model.

Usage: deprec_analyze.py --hub HUB --set SET --stage STAGE [--boot 10000] [--seed 20261105]
Per world: one text channel from the six committed extraction replies (adapter v1, no goal), shared by both goal
clones and both contracts; the structured channel is the public contract-v1 reports. For every (goal, channel) the
engine log, the P2 query request and the sensor receipts are built once (recovery.run) and the two contracts decide
from them. Independent units: the 24 worlds (domain-stratified cluster bootstrap over worlds).
PRIMARY: text channel, per world mean over the two goal clones of U_scoped - U_strict.
Writes HUB/analysis-<set>/{trajectories.jsonl, extraction.jsonl, ANALYSIS.json, TABLES.md}.
"""
import argparse
import collections
import json
from pathlib import Path

from _bootstrap import ROOT  # noqa: F401
from tempo import recovery as R, text_channel as TC, transfer as T
from tempo_analyze import bootstrap, domain_weighted, load
from contract_validate import score_record

ROLES, CHANNELS, CONTRACTS = ("A", "B"), ("structured", "text"), R.CONTRACTS
CMP = ("queried", "plan", "success", "invalid_attempt", "utility")


def fields_of_v02(r):
    if not isinstance(r, dict) or not isinstance(r.get("payload"), dict):
        return set()
    p = r["payload"]
    if r.get("kind") == "initial" and isinstance(p.get("assign"), dict):
        return set(p["assign"])
    return {p["field"]} if isinstance(p.get("field"), str) else set()


def fields_of_v1(rep):
    return {x.get("field") for x in (rep or {}).get("assertions", []) if isinstance(x, dict)} - {None}


def contexts(ep):
    out = {}
    for role in ROLES:
        ge, gc = T.goal_episode(ep, role)
        out[role] = (ge, R.context(ge, gc["goal"]))
    return out


def analyse(hub, set_name, stage, B=10000, sd=20261105):
    eps = load(hub / "data" / f"{set_name}-episodes.jsonl")
    calls = {c["call_id"]: c for c in load(hub / "data" / f"{set_name}-calls.jsonl")}
    gold = {g["call_id"]: g for g in load(hub / "data" / f"{set_name}-gold.jsonl")}
    recs = {}
    for p in (hub / "stages" / stage / "calls").glob("*.json"):
        r = json.loads(p.read_text()); recs[r["call_id"]] = r
    traj, ext = [], []
    for ep in eps:
        cids = [f"{ep['episode_id']}|prose|r{k}" for k in range(1, len(ep["records_v02"]) + 1)]
        raws = [recs[c]["raw"] if c in recs and recs[c]["status"] == "ok" else None for c in cids]
        ch = TC.build_channel(ep, raws, [gold[c]["registry"] for c in cids], ep["prose_texts"])
        ctx = contexts(ep)
        for c, row in zip(cids, ch["rows"]):
            sc = score_record(row["report"], gold[c]["gold"], gold[c]["text"])
            named = fields_of_v02(gold[c]["gold"]) | fields_of_v1(row["report"])
            ext.append({"call_id": c, "episode_id": ep["episode_id"], "domain": ep["domain"], "a_type": ep["a_type"],
                        "b_type": ep["b_type"], "k": row["k"], "gold_kind": gold[c]["gold"]["kind"],
                        "gold_status": gold[c]["gold"]["status"], "accepted": row["accepted"], "code": row["code"],
                        "adapter_log": row["adapter_log"], "raw": row["raw"], "report": row["report"], **sc,
                        "text": gold[c]["text"],
                        "touches_A": sorted(named & set(ctx["A"][1]["relevant"])),
                        "touches_B": sorted(named & set(ctx["B"][1]["relevant"])),
                        "status_wrong": bool(row["report"]) and row["report"]["status"] != gold[c]["gold"]["status"],
                        "output_tokens": (recs.get(c) or {}).get("output_tokens"),
                        "seconds": (recs.get(c) or {}).get("seconds"), "stop": (recs.get(c) or {}).get("stop")})
        for role in ROLES:
            ge, gc = ctx[role]
            for chn in CHANNELS:
                x = R.run(ge, gc, "P2_selective", channel=None if chn == "structured" else ch, tag=f"|{chn}")
                for con in CONTRACTS:
                    traj.append(dict(x[con], channel=chn, role=role, world=ep["episode_id"], a_type=ep["a_type"],
                                     b_type=ep["b_type"], relevant=gc["relevant"],
                                     matched_receipts=x["strict"]["receipts_sha256"] == x["scoped"]["receipts_sha256"]
                                     and x["strict"]["queried"] == x["scoped"]["queried"],
                                     matched_log=x["strict"]["log_head"] == x["scoped"]["log_head"] and
                                     x["strict"]["historical_detail_sha256"] == x["scoped"]["historical_detail_sha256"]))
    out = hub / f"analysis-{set_name}"
    out.mkdir(exist_ok=True)
    for name, rows in (("trajectories", traj), ("extraction", ext)):
        with open(out / f"{name}.jsonl", "w") as fh:
            for r in rows:
                fh.write(json.dumps(r, default=str) + "\n")
    gdom = {e["episode_id"]: e["domain"] for e in eps}
    worlds_ = [e["episode_id"] for e in eps]
    idx = {(r["role"], r["channel"], r["contract"], r["world"]): r for r in traj}

    def est(gv):
        m = domain_weighted(gv, gdom)
        return {"mean": None if m is None else round(m, 4), "ci95": bootstrap(gv, gdom, B, sd)}

    def contrast(fn):
        d = {w: fn(w) for w in worlds_}
        x = est(d)
        x.update(better=sum(v > 0 for v in d.values()), equal=sum(v == 0 for v in d.values()),
                 worse=sum(v < 0 for v in d.values()))
        return x
    U = lambda role, chn, con: (lambda w: float(idx[(role, chn, con, w)]["utility"]))
    avgU = lambda chn, con: (lambda w: (U("A", chn, con)(w) + U("B", chn, con)(w)) / 2)
    res = {"set": set_name, "worlds": len(eps), "trajectories": len(traj), "calls": len(calls),
           "call_status": dict(collections.Counter((recs.get(c) or {}).get("status", "missing") for c in calls)),
           "truncated": sum(1 for r in recs.values() if r.get("stop") == "length"),
           "output_tokens": sum(r.get("output_tokens") or 0 for r in recs.values()),
           "generation_seconds": round(sum(r.get("seconds") or 0 for r in recs.values()), 1), "cells": {},
           "contrasts": {}}
    for role in ROLES:
        for chn in CHANNELS:
            for con in CONTRACTS:
                r = [x for x in traj if (x["role"], x["channel"], x["contract"]) == (role, chn, con)]
                res["cells"][f"{role}:{chn}:{con}"] = {
                    "utility": est({x["world"]: float(x["utility"]) for x in r}),
                    "utility_total": sum(x["utility"] for x in r),
                    "success": sum(x["success"] for x in r), "menu_feasible": sum(x["opportunity"] for x in r),
                    "false_permissions": sum(x["false_permission"] for x in r),
                    "false_blocks": sum(x["false_block"] for x in r),
                    "missed_opportunities": sum(x["missed_opportunity"] for x in r),
                    "declines": sum(x["declined"] for x in r),
                    "decline_reasons": dict(collections.Counter(z for x in r for z in x["decline_reasons"])),
                    "fields_queried": sum(len(x["queried"]) for x in r),
                    "budget_exhausted": sum(x["budget_exhausted"] for x in r),
                    "decisions_with_conflict": sum(bool(x["conflict_at_decision"]) for x in r),
                    "decisions_with_incomplete": sum(bool(x["incomplete_at_decision"]) for x in r),
                    "historical_relevant_conflict_at_decision": sum(
                        bool(set(x["historical_conflicts_at_decision"]) & set(x["relevant"])) for x in r),
                    "op_state_correct_before": sum(x["op_state_correct_before"] for x in r),
                    "op_state_correct_at_decision": sum(x["op_state_correct_at_decision"] for x in r),
                    "anchored_fields": sum(len(x["anchors"]) for x in r),
                    "refused_receipts": sum(len(x["refused_receipts"]) for x in r),
                    "authority_conflicts": sum(len(x["authority_conflicts"]) for x in r),
                    "invariant_diagnostics_before": sum(bool(x["invariant_before"]) for x in r),
                    "action_cost": sum(x["action_cost"] for x in r),
                    "earlier_view_preserved": f"{sum(x['earlier_view_preserved'] for x in r)}/{len(r)}",
                    "unanchored_fields_unchanged": f"{sum(x['unanchored_fields_unchanged'] for x in r)}/{len(r)}"}
    C = res["contrasts"]
    C["PRIMARY text scoped-strict (mean over goals)"] = contrast(lambda w: avgU("text", "scoped")(w) -
                                                                avgU("text", "strict")(w))
    for role in ROLES:
        for chn in CHANNELS:
            C[f"{role} {chn} scoped-strict"] = contrast(lambda w, role=role, chn=chn: U(role, chn, "scoped")(w) -
                                                         U(role, chn, "strict")(w))
    C["NEGATIVE CONTROL structured scoped-strict (mean over goals)"] = contrast(
        lambda w: avgU("structured", "scoped")(w) - avgU("structured", "strict")(w))
    for con in CONTRACTS:
        C[f"text loss under {con} (text-structured, mean over goals)"] = contrast(
            lambda w, con=con: avgU("text", con)(w) - avgU("structured", con)(w))
        for role in ROLES:
            C[f"{role} text loss under {con}"] = contrast(lambda w, role=role, con=con: U(role, "text", con)(w) -
                                                         U(role, "structured", con)(w))
    res["primary"] = C["PRIMARY text scoped-strict (mean over goals)"]
    res["primary_components"] = {f"{role}:text:{con}": round(sum(U(role, "text", con)(w) for w in worlds_) / len(worlds_), 4)
                                 for role in ROLES for con in CONTRACTS}
    pairs = [(idx[(role, chn, "strict", w)], idx[(role, chn, "scoped", w)]) for role in ROLES for chn in CHANNELS
             for w in worlds_]
    res["matching"] = {"pairs": len(pairs), "identical_queries_and_receipts": sum(a["matched_receipts"] for a, _ in pairs),
                       "identical_log_and_historical_reconstruction": sum(a["matched_log"] for a, _ in pairs)}
    diffs = []
    for a, b in pairs:
        if any(a[k] != b[k] for k in CMP):
            diffs.append({"world": a["world"], "role": a["role"], "channel": a["channel"],
                          "strict": {k: a[k] for k in CMP + ("decline_reasons",)},
                          "scoped": {k: b[k] for k in CMP},
                          "anchored": {f: {k: v[k] for k in ("value", "historical_status", "historical_culprits",
                                                                "operational_status_without_rule",
                                                                "incomplete_without_rule")}
                                       for f, v in b["anchors"].items()},
                          "historical_conflicts_kept": b["historical_conflicts_at_decision"],
                          "restored_opportunity": a["missed_opportunity"] and b["success"],
                          "new_false_permission": b["false_permission"] and not a["false_permission"]})
    res["scoped_vs_strict_differences"] = diffs
    res["summary"] = {
        "restored_opportunities": {chn: sum(d["restored_opportunity"] for d in diffs if d["channel"] == chn)
                                   for chn in CHANNELS},
        "new_false_permissions": sum(d["new_false_permission"] for d in diffs),
        "remaining_text_missed_under_scoped": [
            {"world": b["world"], "role": b["role"], "queried": b["queried"], "decline_reasons": b["decline_reasons"],
             "plan": b["plan"], "op_state_correct_at_decision": b["op_state_correct_at_decision"]}
            for a, b in pairs if b["channel"] == "text" and b["missed_opportunity"]],
        "text_differs_from_structured": {con: sorted({f"{x['world']}|{x['role']}" for x in traj
                                                      if x["channel"] == "text" and x["contract"] == con and
                                                      any(x[k] != idx[(x['role'], 'structured', con, x['world'])][k]
                                                          for k in CMP)}) for con in CONTRACTS},
        "invariant_diagnostics_text": [{"world": x["world"], "role": x["role"], "invariant": x["invariant_before"]}
                                       for x in traj if x["channel"] == "text" and x["contract"] == "strict"
                                       and x["invariant_before"]]}
    acc = [e for e in ext]
    res["extraction"] = {"records": len(acc), "accepted": sum(e["accepted"] for e in acc),
                         "denotation_equal": sum(bool(e.get("denotation_equal")) for e in acc),
                         "status_wrong": sum(e["status_wrong"] for e in acc),
                         "codes": dict(collections.Counter(e["code"] for e in acc if e["code"])),
                         "errors_touching": dict(collections.Counter(
                             ("A" if e["touches_A"] else "") + ("B" if e["touches_B"] else "") or "neither"
                             for e in acc if not e.get("denotation_equal"))),
                         "by_gold_kind": {k: f"{sum(not e.get('denotation_equal') for e in acc if e['gold_kind'] == k)}"
                                             f"/{sum(e['gold_kind'] == k for e in acc)} errors"
                                          for k in sorted({e['gold_kind'] for e in acc})}}
    (out / "ANALYSIS.json").write_text(json.dumps(res, indent=1, default=str) + "\n")
    L = [f"# {set_name} / {stage}: strict vs scoped current-observation authority (P2)", "",
         f"Calls {res['call_status']}, truncated {res['truncated']}, output tokens {res['output_tokens']}, "
         f"generation {res['generation_seconds']} s.", "",
         "| Cell | U mean [95%] | total | success | menu-feasible | false perm. | false blocks | queried | "
         "conflict at decision | op state correct at decision | anchored |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for k, c in res["cells"].items():
        L.append(f"| {k} | {c['utility']['mean']} {c['utility']['ci95']} | {c['utility_total']} | {c['success']} | "
                 f"{c['menu_feasible']} | {c['false_permissions']} | {c['false_blocks']} | {c['fields_queried']} | "
                 f"{c['decisions_with_conflict']} | {c['op_state_correct_at_decision']} | {c['anchored_fields']} |")
    L += ["", "| Contrast | mean [95%] | better / equal / worse |", "|---|---|---|"]
    for k, c in C.items():
        L.append(f"| {k} | {c['mean']} {c['ci95']} | {c['better']} / {c['equal']} / {c['worse']} |")
    L += ["", f"Matching: {res['matching']}", "", "Scoped vs strict differences:"]
    L += [f"- {d['world']} {d['role']} {d['channel']}: strict {d['strict']} -> scoped {d['scoped']}; anchored "
          f"{d['anchored']}; historical conflicts kept {d['historical_conflicts_kept']}" for d in diffs]
    L += ["", f"Summary: {json.dumps(res['summary'], default=str)}", "", f"Extraction: {json.dumps(res['extraction'])}"]
    (out / "TABLES.md").write_text("\n".join(L) + "\n")
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", required=True)
    ap.add_argument("--set", required=True)
    ap.add_argument("--stage", required=True)
    ap.add_argument("--boot", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=20261105)
    a = ap.parse_args()
    res = analyse(Path(a.hub), a.set, a.stage, a.boot, a.seed)
    print(json.dumps({k: res[k] for k in ("trajectories", "primary", "matching")}, default=str))


if __name__ == "__main__":
    main()
