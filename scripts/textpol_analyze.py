"""Text-interface policy study analysis (development; descriptive). No model calls.

Usage: textpol_analyze.py --hub HUB --set SET --stage STAGE [--boot 10000] [--seed 20261105]
Channels per episode: structured (the public contract-v1 reports) and text (the six committed extraction replies,
shared by all three text-policy clones, through text_channel adapter v1). Policies P0/P1/P2 unchanged; the sensor stays
structured. Writes HUB/analysis-<set>/{trajectories.jsonl, extraction.jsonl, ANALYSIS.json, TABLES.md}.
"""
import argparse
import collections
import json
from pathlib import Path

from _bootstrap import ROOT  # noqa: F401
from tempo import policy as P, text_channel as TC
from tempo_analyze import bootstrap, domain_weighted, load, mean
from contract_validate import score_record


def safe(cid):
    return cid.replace("|", "__")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", required=True)
    ap.add_argument("--set", required=True)
    ap.add_argument("--stage", required=True)
    ap.add_argument("--boot", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=20261105)
    a = ap.parse_args()
    hub = Path(a.hub)
    eps = load(hub / "data" / f"{a.set}-episodes.jsonl")
    calls = {c["call_id"]: c for c in load(hub / "data" / f"{a.set}-calls.jsonl")}
    gold = {g["call_id"]: g for g in load(hub / "data" / f"{a.set}-gold.jsonl")}
    recs = {}
    for p in (hub / "stages" / a.stage / "calls").glob("*.json"):
        r = json.loads(p.read_text()); recs[r["call_id"]] = r
    traj, ext = [], []
    for ep in eps:
        cids = [f"{ep['episode_id']}|prose|r{k}" for k in range(1, len(ep["records_v02"]) + 1)]
        raws = [recs[c]["raw"] if c in recs and recs[c]["status"] == "ok" else None for c in cids]
        ch = TC.build_channel(ep, raws, [gold[c]["registry"] for c in cids], ep["prose_texts"])
        for c, row in zip(cids, ch["rows"]):
            sc = score_record(row["report"], gold[c]["gold"], gold[c]["text"])
            ext.append({"call_id": c, "episode_id": ep["episode_id"], "domain": ep["domain"], "type": ep["type"],
                        "k": row["k"], "gold_kind": gold[c]["gold"]["kind"], "gold_status": gold[c]["gold"]["status"],
                        "accepted": row["accepted"], "code": row["code"], "adapter_log": row["adapter_log"],
                        "raw": row["raw"], "report": row["report"], **sc,
                        "output_tokens": (recs.get(c) or {}).get("output_tokens"), "seconds": (recs.get(c) or {}).get("seconds"),
                        "stop": (recs.get(c) or {}).get("stop")})
        for pol in P.POLICIES:
            s = P.run_policy(ep, pol)
            t = P.run_policy(ep, pol, channel=ch)
            traj.append(dict(s, channel="structured"))
            traj.append(dict(t, channel="text"))
    out = hub / f"analysis-{a.set}"
    out.mkdir(exist_ok=True)
    for name, rows in (("trajectories", traj), ("extraction", ext)):
        with open(out / f"{name}.jsonl", "w") as fh:
            for r in rows:
                fh.write(json.dumps(r, default=str) + "\n")
    gdom = {e["episode_id"]: e["domain"] for e in eps}
    B, sd = a.boot, a.seed

    def est(gv):
        m = domain_weighted(gv, gdom)
        return {"mean": None if m is None else round(m, 4), "ci95": bootstrap(gv, gdom, B, sd)}
    idx = {(r["channel"], r["policy"], r["episode_id"]): r for r in traj}
    res = {"set": a.set, "episodes": len(eps), "calls": len(calls),
           "call_status": dict(collections.Counter((recs.get(c) or {}).get("status", "missing") for c in calls)),
           "truncated": sum(1 for r in recs.values() if r.get("stop") == "length"),
           "output_tokens": sum(r.get("output_tokens") or 0 for r in recs.values()),
           "generation_seconds": round(sum(r.get("seconds") or 0 for r in recs.values()), 1), "cells": {}, "contrasts": {}}
    for chn in ("structured", "text"):
        for pol in P.POLICIES:
            r = [x for x in traj if x["channel"] == chn and x["policy"] == pol]
            res["cells"][f"{chn}:{pol}"] = {
                "utility": est({x["episode_id"]: float(x["utility"]) for x in r}), "utility_total": sum(x["utility"] for x in r),
                "success": f"{sum(x['success'] for x in r)}/{len(r)}", "feasible": sum(x["opportunity"] for x in r),
                "invalid_attempts": sum(x["invalid_attempt"] for x in r), "false_blocks": sum(x["false_block"] for x in r),
                "missed_opportunities": sum(x["missed_opportunity"] for x in r), "declines": sum(x["declined"] for x in r),
                "fields_queried": sum(len(x["queried"]) for x in r),
                "decisions_with_conflict": sum(bool(x["conflict_at_decision"]) for x in r),
                "decisions_with_incomplete": sum(bool(x["incomplete_at_decision"]) for x in r),
                "belief_correct_before": sum(x["belief_correct_before"] for x in r),
                "belief_correct_at_decision": sum(x["belief_correct_at_decision"] for x in r),
                "action_cost": sum(x["action_cost"] for x in r), "delay_total": sum(x["delay"] for x in r),
                "earlier_view_preserved": f"{sum(x['earlier_view_preserved'] for x in r)}/{len(r)}"}

    def diff(f1, f2):
        d = {e["episode_id"]: f1(e["episode_id"]) - f2(e["episode_id"]) for e in eps}
        x = est(d)
        x.update(better=sum(v > 0 for v in d.values()), equal=sum(v == 0 for v in d.values()), worse=sum(v < 0 for v in d.values()))
        return x
    U = lambda chn, pol: (lambda e: float(idx[(chn, pol, e)]["utility"]))
    for chn in ("text", "structured"):
        res["contrasts"][f"{chn}: P2 - P0"] = diff(U(chn, "P2_selective"), U(chn, "P0_accepted"))
        res["contrasts"][f"{chn}: P2 - P1"] = diff(U(chn, "P2_selective"), U(chn, "P1_always"))
        res["contrasts"][f"{chn}: P1 - P0"] = diff(U(chn, "P1_always"), U(chn, "P0_accepted"))
    for pol in P.POLICIES:
        res["contrasts"][f"{pol}: text - structured"] = diff(U("text", pol), U("structured", pol))
    for a_, b_ in (("P2_selective", "P0_accepted"), ("P2_selective", "P1_always")):
        res["contrasts"][f"({a_} - {b_}): text - structured"] = diff(
            lambda e: U("text", a_)(e) - U("text", b_)(e), lambda e: U("structured", a_)(e) - U("structured", b_)(e))
    # where text trajectories differ from their structured clone
    why = collections.Counter()
    diffs = []
    for e in eps:
        for pol in P.POLICIES:
            s, t = idx[("structured", pol, e["episode_id"])], idx[("text", pol, e["episode_id"])]
            if (s["plan"], s["success"], s["invalid_attempt"], s["queried"]) == (t["plan"], t["success"], t["invalid_attempt"], t["queried"]):
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
            for tag in tags or ["other"]:
                why[tag] += 1
            diffs.append({"episode_id": e["episode_id"], "type": e["type"], "policy": pol, "tags": tags,
                          "structured": {k: s[k] for k in ("plan", "success", "invalid_attempt", "queried", "utility")},
                          "text": {k: t[k] for k in ("plan", "success", "invalid_attempt", "queried", "utility")}})
    res["text_vs_structured_differences"] = {"trajectories_differing": len(diffs), "tags": dict(why), "list": diffs}
    res["extraction"] = {"records": len(ext), "accepted": sum(x["accepted"] for x in ext),
                         "denotation_equal": sum(x["denotation_equal"] for x in ext),
                         "full_coverage": sum(x["coverage"] == 1.0 for x in ext),
                         "mean_coverage": round(mean([x["coverage"] for x in ext]), 4),
                         "type_class_equal": sum(x["type_class_equal"] for x in ext),
                         "status_wrong": sum(1 for x in ext if x["report"] and x["report"]["status"] != x["gold_status"]),
                         "unprocessed_codes": dict(collections.Counter(x["code"] for x in ext if not x["accepted"])),
                         "not_equal_by_gold_kind": dict(collections.Counter(x["gold_kind"] for x in ext if not x["denotation_equal"])),
                         "normalisation_rules": dict(collections.Counter(n["rule"] for x in ext for n in x["adapter_log"]["norm"]))}
    (out / "ANALYSIS.json").write_text(json.dumps(res, indent=1, default=str) + "\n")
    L = ["# Text-interface policy study (generated)", "", f"Calls {res['calls']} {res['call_status']}; truncated {res['truncated']}; "
         f"output tokens {res['output_tokens']}; generation {res['generation_seconds']} s.", "", f"Extraction: {res['extraction']}", "",
         "| Channel:policy | utility mean [95% CI] (total) | success | invalid | false blocks | missed | declines | fields queried | decisions with conflict / incomplete | belief correct before → at decision |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for k, d in res["cells"].items():
        u = d["utility"]
        L.append(f"| {k} | {u['mean']:.3f} [{u['ci95'][0]:.2f}, {u['ci95'][1]:.2f}] ({d['utility_total']}) | {d['success']} | {d['invalid_attempts']} | "
                 f"{d['false_blocks']} | {d['missed_opportunities']} | {d['declines']} | {d['fields_queried']} | "
                 f"{d['decisions_with_conflict']} / {d['decisions_with_incomplete']} | {d['belief_correct_before']} → {d['belief_correct_at_decision']} |")
    L += ["", "## Paired contrasts (per episode; better / equal / worse)", "", "| Contrast | utility |", "|---|---|"]
    for k, c in res["contrasts"].items():
        L.append(f"| {k} | {c['mean']:+.3f} [{c['ci95'][0]:.2f}, {c['ci95'][1]:.2f}] ({c['better']}/{c['equal']}/{c['worse']}) |")
    dd = res["text_vs_structured_differences"]
    L += ["", f"Text trajectories differing from their structured clone: {dd['trajectories_differing']}; tags {dd['tags']}."]
    (out / "TABLES.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
