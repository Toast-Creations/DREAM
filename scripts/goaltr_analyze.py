"""Deferred-goal transfer analysis (development; descriptive). No model calls.

Usage: goaltr_analyze.py --hub HUB --set SET --stage STAGE [--boot 10000] [--seed 20261105]
Per world: one text channel built from the six committed extraction replies (adapter v1, no goal), shared by every
goal/policy clone; the structured channel is the public contract-v1 reports. Each goal (A, B) is revealed only to its
own isolated copy (transfer.goal_episode). Policies P0/P1/P2 unchanged; the sensor stays structured.
Independent units: the 24 worlds (domain-stratified cluster bootstrap over worlds).
Writes HUB/analysis-<set>/{trajectories.jsonl, extraction.jsonl, ANALYSIS.json, TABLES.md}.
"""
import argparse
import collections
import json
from pathlib import Path

from _bootstrap import ROOT  # noqa: F401
from tempo import goals as GL, policy as P, text_channel as TC, transfer as T
from tempo_analyze import bootstrap, domain_weighted, load, mean
from contract_validate import score_record

ROLES = ("A", "B")
CHANNELS = ("structured", "text")


def fields_of_v02(r):
    if not isinstance(r, dict) or not isinstance(r.get("payload"), dict):
        return set()
    p = r["payload"]
    if r.get("kind") == "initial" and isinstance(p.get("assign"), dict):
        return set(p["assign"])
    return {p["field"]} if isinstance(p.get("field"), str) else set()


def fields_of_v1(rep):
    return {x.get("field") for x in (rep or {}).get("assertions", []) if isinstance(x, dict)} - {None}


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
        rel = {role: T.goal_context(ep, role)["relevant"] for role in ROLES}
        for c, row in zip(cids, ch["rows"]):
            sc = score_record(row["report"], gold[c]["gold"], gold[c]["text"])
            named = fields_of_v02(gold[c]["gold"]) | fields_of_v1(row["report"])
            ext.append({"call_id": c, "episode_id": ep["episode_id"], "domain": ep["domain"], "a_type": ep["a_type"],
                        "b_type": ep["b_type"], "k": row["k"], "gold_kind": gold[c]["gold"]["kind"],
                        "gold_status": gold[c]["gold"]["status"], "accepted": row["accepted"], "code": row["code"],
                        "adapter_log": row["adapter_log"], "raw": row["raw"], "report": row["report"], **sc,
                        "gold_fields": sorted(fields_of_v02(gold[c]["gold"])),
                        "touches_A": sorted(named & set(rel["A"])), "touches_B": sorted(named & set(rel["B"])),
                        "status_wrong": bool(row["report"]) and row["report"]["status"] != gold[c]["gold"]["status"],
                        "output_tokens": (recs.get(c) or {}).get("output_tokens"),
                        "seconds": (recs.get(c) or {}).get("seconds"), "stop": (recs.get(c) or {}).get("stop")})
        for role in ROLES:
            ge, gc = T.goal_episode(ep, role)
            for pol in P.POLICIES:
                for chn in CHANNELS:
                    r = GL.run_policy(ge, gc, pol, channel=None if chn == "structured" else ch, tag=f"|{chn}")
                    traj.append(dict(r, channel=chn, role=role, world=ep["episode_id"], a_type=ep["a_type"],
                                     b_type=ep["b_type"], relevant=gc["relevant"]))
    out = hub / f"analysis-{set_name}"
    out.mkdir(exist_ok=True)
    for name, rows in (("trajectories", traj), ("extraction", ext)):
        with open(out / f"{name}.jsonl", "w") as fh:
            for r in rows:
                fh.write(json.dumps(r, default=str) + "\n")
    gdom = {e["episode_id"]: e["domain"] for e in eps}
    worlds_ = [e["episode_id"] for e in eps]

    def est(gv):
        m = domain_weighted(gv, gdom)
        return {"mean": None if m is None else round(m, 4), "ci95": bootstrap(gv, gdom, B, sd)}
    idx = {(r["role"], r["channel"], r["policy"], r["world"]): r for r in traj}
    U = lambda role, chn, pol: (lambda w: float(idx[(role, chn, pol, w)]["utility"]))

    def diff(f1, f2):
        d = {w: f1(w) - f2(w) for w in worlds_}
        x = est(d)
        x.update(better=sum(v > 0 for v in d.values()), equal=sum(v == 0 for v in d.values()),
                 worse=sum(v < 0 for v in d.values()))
        return x
    res = {"set": set_name, "worlds": len(eps), "trajectories": len(traj), "calls": len(calls),
           "call_status": dict(collections.Counter((recs.get(c) or {}).get("status", "missing") for c in calls)),
           "truncated": sum(1 for r in recs.values() if r.get("stop") == "length"),
           "output_tokens": sum(r.get("output_tokens") or 0 for r in recs.values()),
           "generation_seconds": round(sum(r.get("seconds") or 0 for r in recs.values()), 1), "cells": {},
           "contrasts": {}}
    reg = {e["episode_id"]: list(e["registry_allowed"]) for e in eps}
    for role in ROLES:
        for chn in CHANNELS:
            for pol in P.POLICIES:
                r = [x for x in traj if x["role"] == role and x["channel"] == chn and x["policy"] == pol]
                res["cells"][f"{role}:{chn}:{pol}"] = {
                    "utility": est({x["world"]: float(x["utility"]) for x in r}),
                    "utility_total": sum(x["utility"] for x in r),
                    "success": f"{sum(x['success'] for x in r)}/{len(r)}", "feasible": sum(x["opportunity"] for x in r),
                    "invalid_attempts": sum(x["invalid_attempt"] for x in r),
                    "false_blocks": sum(x["false_block"] for x in r),
                    "missed_opportunities": sum(x["missed_opportunity"] for x in r),
                    "declines": sum(x["declined"] for x in r), "fields_queried": sum(len(x["queried"]) for x in r),
                    "budget_exhausted": sum(x["budget_exhausted"] for x in r),
                    "decisions_with_conflict": sum(bool(x["conflict_at_decision"]) for x in r),
                    "decisions_with_incomplete": sum(bool(x["incomplete_at_decision"]) for x in r),
                    "decisions_with_unknown": sum(any(v == "unknown" for v in x["relevant_status_at_decision"].values())
                                                  for x in r),
                    "relevant_state_correct_before": sum(x["belief_correct_before"] for x in r),
                    "relevant_state_correct_at_decision": sum(x["belief_correct_at_decision"] for x in r),
                    "relevant_state_complete_before": sum(
                        all(not inc and st not in ("conflict", "not_yet_described", None)
                            for st, inc, _ in x["relevant_status_before"].values()) for x in r),
                    "action_cost": sum(x["action_cost"] for x in r), "delay_total": sum(x["delay"] for x in r),
                    "earlier_view_preserved": f"{sum(x['earlier_view_preserved'] for x in r)}/{len(r)}"}
    # primary and supporting contrasts
    loss = lambda role, pol: (lambda w: U(role, "text", pol)(w) - U(role, "structured", pol)(w))
    for pol in P.POLICIES:
        res["contrasts"][f"{pol}: text loss B - text loss A"] = diff(loss("B", pol), loss("A", pol))
    for role in ROLES:
        for pol in P.POLICIES:
            res["contrasts"][f"{role} {pol}: text - structured"] = diff(U(role, "text", pol), U(role, "structured", pol))
        for chn in CHANNELS:
            res["contrasts"][f"{role} {chn}: P2 - P0"] = diff(U(role, chn, "P2_selective"), U(role, chn, "P0_accepted"))
            res["contrasts"][f"{role} {chn}: P2 - P1"] = diff(U(role, chn, "P2_selective"), U(role, chn, "P1_always"))
            res["contrasts"][f"{role} {chn}: P1 - P0"] = diff(U(role, chn, "P1_always"), U(role, chn, "P0_accepted"))
    for pol in P.POLICIES:
        for chn in CHANNELS:
            res["contrasts"][f"{chn} {pol}: B - A"] = diff(U("B", chn, pol), U("A", chn, pol))
    res["primary"] = dict(res["contrasts"]["P2_selective: text loss B - text loss A"],
                          components={f"{role}:{chn}": res["cells"][f"{role}:{chn}:P2_selective"]["utility"]["mean"]
                                      for role in ROLES for chn in CHANNELS})
    # whole declared-state coverage (text current state vs structured current state, before any query)
    cov = {}
    for w in worlds_:
        s, t = idx[("A", "structured", "P0_accepted", w)], idx[("A", "text", "P0_accepted", w)]
        fs = reg[w]
        cov[w] = sum(t["state_before"].get(f) == s["state_before"].get(f) for f in fs) / len(fs)
    res["declared_state_agreement_text_vs_structured"] = {"mean_share_of_registry_fields": round(mean(list(cov.values())), 4),
                                                          "worlds_fully_equal": sum(v == 1.0 for v in cov.values())}
    # where text differs from structured, per goal
    diffs, why = [], collections.Counter()
    for role in ROLES:
        for w in worlds_:
            for pol in P.POLICIES:
                s, t = idx[(role, "structured", pol, w)], idx[(role, "text", pol, w)]
                if (s["plan"], s["success"], s["invalid_attempt"], s["queried"]) == \
                        (t["plan"], t["success"], t["invalid_attempt"], t["queried"]):
                    continue
                tags = []
                if t["conflict_at_decision"]:
                    tags.append("conflict at decision")
                if t["incomplete_at_decision"]:
                    tags.append("incomplete at decision")
                sb, tb = s["relevant_status_before"], t["relevant_status_before"]
                if any(sb[f][2] != tb[f][2] for f in sb):
                    tags.append("provisional flag differs")
                if any(sb[f][0] != tb[f][0] for f in sb):
                    tags.append("status differs")
                if t["queried"] != s["queried"]:
                    tags.append("different queries")
                if not t["belief_correct_at_decision"] and s["belief_correct_at_decision"]:
                    tags.append("wrong belief at decision")
                if t["invalid_attempt"] and not s["invalid_attempt"]:
                    tags.append("invalid attempt (text only)")
                for tag in tags or ["other"]:
                    why[(role, tag)] += 1
                diffs.append({"role": role, "world": w, "type": t["type"], "policy": pol, "tags": tags,
                              "structured": {k: s[k] for k in ("plan", "success", "invalid_attempt", "queried", "utility")},
                              "text": {k: t[k] for k in ("plan", "success", "invalid_attempt", "queried", "utility",
                                                         "relevant_status_at_decision")}})
    res["text_vs_structured_differences"] = {
        "by_goal": {role: {"trajectories": sum(d["role"] == role for d in diffs),
                           "worlds": len({d["world"] for d in diffs if d["role"] == role})} for role in ROLES},
        "tags": {f"{k[0]}: {k[1]}": v for k, v in why.items()}, "list": diffs}
    bad = [x for x in ext if not x["denotation_equal"]]
    res["extraction"] = {
        "records": len(ext), "accepted": sum(x["accepted"] for x in ext),
        "denotation_equal": sum(x["denotation_equal"] for x in ext),
        "full_coverage": sum(x["coverage"] == 1.0 for x in ext), "mean_coverage": round(mean([x["coverage"] for x in ext]), 4),
        "type_class_equal": sum(x["type_class_equal"] for x in ext),
        "status_wrong": sum(x["status_wrong"] for x in ext),
        "not_equal_status_right_or_unprocessed": sum(not x["status_wrong"] for x in bad),
        "unprocessed_codes": dict(collections.Counter(x["code"] for x in ext if not x["accepted"])),
        "not_equal_by_gold_kind": dict(collections.Counter(x["gold_kind"] for x in bad)),
        "records_touching": {"A": sum(bool(x["touches_A"]) for x in ext), "B": sum(bool(x["touches_B"]) for x in ext)},
        "errors_touching": {"A only": sum(bool(x["touches_A"]) and not x["touches_B"] for x in bad),
                            "B only": sum(bool(x["touches_B"]) and not x["touches_A"] for x in bad),
                            "both": sum(bool(x["touches_A"]) and bool(x["touches_B"]) for x in bad),
                            "neither": sum(not x["touches_A"] and not x["touches_B"] for x in bad)},
        "normalisation_rules": dict(collections.Counter(n["rule"] for x in ext for n in x["adapter_log"]["norm"]))}
    (out / "ANALYSIS.json").write_text(json.dumps(res, indent=1, default=str) + "\n")
    L = ["# Deferred-goal transfer (generated)", "",
         f"Calls {res['calls']} {res['call_status']}; truncated {res['truncated']}; output tokens {res['output_tokens']}; "
         f"generation {res['generation_seconds']} s. Worlds {res['worlds']}, trajectories {res['trajectories']}.", "",
         f"Extraction: {json.dumps(res['extraction'])}", "",
         f"Declared-state agreement (text vs structured, before queries): {res['declared_state_agreement_text_vs_structured']}", "",
         "| Goal:channel:policy | utility mean [95% CI] (total) | success | feasible | invalid | false blocks | missed | "
         "queried | conflict / incomplete / unknown at decision | relevant state correct before → at decision | complete before |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for k, d in res["cells"].items():
        u = d["utility"]
        L.append(f"| {k} | {u['mean']:.3f} [{u['ci95'][0]:.2f}, {u['ci95'][1]:.2f}] ({d['utility_total']}) | {d['success']} | "
                 f"{d['feasible']} | {d['invalid_attempts']} | {d['false_blocks']} | {d['missed_opportunities']} | "
                 f"{d['fields_queried']} | {d['decisions_with_conflict']} / {d['decisions_with_incomplete']} / "
                 f"{d['decisions_with_unknown']} | {d['relevant_state_correct_before']} → "
                 f"{d['relevant_state_correct_at_decision']} | {d['relevant_state_complete_before']} |")
    L += ["", "## Paired contrasts (per world; better / equal / worse)", "", "| Contrast | utility |", "|---|---|"]
    for k, c in res["contrasts"].items():
        L.append(f"| {k} | {c['mean']:+.3f} [{c['ci95'][0]:.2f}, {c['ci95'][1]:.2f}] ({c['better']}/{c['equal']}/{c['worse']}) |")
    dd = res["text_vs_structured_differences"]
    L += ["", f"Text trajectories differing from their structured clone: {dd['by_goal']}; tags {dd['tags']}."]
    (out / "TABLES.md").write_text("\n".join(L) + "\n")
    return res, L


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", required=True)
    ap.add_argument("--set", required=True)
    ap.add_argument("--stage", required=True)
    ap.add_argument("--boot", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=20261105)
    a = ap.parse_args()
    _, L = analyse(Path(a.hub), a.set, a.stage, a.boot, a.seed)
    print("\n".join(L))


if __name__ == "__main__":
    main()
