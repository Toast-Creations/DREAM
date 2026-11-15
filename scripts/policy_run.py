"""Observation-policy study on structured public reports (no model calls).

Usage: policy_run.py --hub HUB --set policy|policydev [--base-seed 20261111] [--boot 10000] [--seed 20261105]
Generates (or, if committed, verifies) HUB/data/<set>-episodes.jsonl + COMMITMENT-<set>.json, runs the three fixed
policies on matched clones of every episode, and writes HUB/analysis-<set>/{trajectories.jsonl, ANALYSIS.json,
TABLES.md}. Unit: the episode (24, 12 per domain); policy trajectories are matched, not independent.
"""
import argparse
import collections
import hashlib
import json
from pathlib import Path

from _bootstrap import ROOT
from dream_core.ledger import release_source_hash
from tempo import policy as P
from tempo_analyze import bootstrap, domain_weighted, mean

REWEIGHT_PROV_WRONG = 0.25  # pre-declared sensitivity: share of uncorrected provisional reports that are wrong


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", required=True)
    ap.add_argument("--set", choices=["policy", "policydev"], required=True)
    ap.add_argument("--base-seed", type=int, default=20261111)
    ap.add_argument("--boot", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=20261105)
    a = ap.parse_args()
    hub = Path(a.hub)
    data = hub / "data"
    data.mkdir(parents=True, exist_ok=True)
    ep_path, commit = data / f"{a.set}-episodes.jsonl", data / f"COMMITMENT-{a.set}.json"
    if commit.exists():
        c = json.loads(commit.read_text())
        if sha(ep_path) != c["episodes_sha256"]:
            raise SystemExit("episodes do not match their commitment")
        eps = [json.loads(l) for l in ep_path.read_text().splitlines()]
    else:
        eps, rejected = [], []
        for eid, dom, et, seed in P.episode_specs(a.set, a.base_seed):
            for att in range(60):
                try:
                    eps.append(P.build_episode(eid, dom, et, seed + att, a.set))
                    break
                except AssertionError as e:
                    rejected.append({"episode_id": eid, "seed": seed + att, "reason": str(e)})
            else:
                raise SystemExit(f"cannot build {eid}")
        with open(ep_path, "w") as fh:
            for e in eps:
                fh.write(json.dumps(e, sort_keys=True) + "\n")
        commit.write_text(json.dumps({"set": a.set, "base_seed": a.base_seed, "episodes": len(eps),
                                      "source_sha256": release_source_hash(ROOT), "rejected_attempts": rejected,
                                      "episodes_sha256": sha(ep_path),
                                      "constants": {k: getattr(P, k) for k in ("DECIDE", "QUERY_COST", "QUERY_DELAY",
                                                                               "QUERY_BUDGET", "SUCCESS_REWARD",
                                                                               "INVALID_PENALTY")},
                                      "allocation": P.ALLOC}, indent=2) + "\n")
        eps = [json.loads(l) for l in ep_path.read_text().splitlines()]
    rows = [P.run_policy(ep, pol) for ep in eps for pol in P.POLICIES]
    out = hub / f"analysis-{a.set}"
    out.mkdir(exist_ok=True)
    with open(out / "trajectories.jsonl", "w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    gdom = {e["episode_id"]: e["domain"] for e in eps}
    B, sd = a.boot, a.seed

    def est(gv):
        m = domain_weighted(gv, gdom)
        return {"mean": None if m is None else round(m, 4), "ci95": bootstrap(gv, gdom, B, sd)}
    res = {"set": a.set, "episodes": len(eps), "trajectories": len(rows), "constants": {
        k: getattr(P, k) for k in ("DECIDE", "QUERY_COST", "QUERY_DELAY", "QUERY_BUDGET", "SUCCESS_REWARD",
                                   "INVALID_PENALTY")}, "policies": {}, "by_type": {}, "contrasts": {}}
    per = {}
    for pol in P.POLICIES:
        r = [x for x in rows if x["policy"] == pol]
        per[pol] = {x["episode_id"]: x for x in r}
        res["policies"][pol] = {
            "PRIMARY_utility": est({x["episode_id"]: float(x["utility"]) for x in r}),
            "utility_total": sum(x["utility"] for x in r),
            "success": f"{sum(x['success'] for x in r)}/{len(r)}",
            "success_rate": est({x["episode_id"]: float(x["success"]) for x in r}),
            "opportunities": sum(x["opportunity"] for x in r),
            "invalid_attempts": sum(x["invalid_attempt"] for x in r),
            "missed_opportunities": sum(x["missed_opportunity"] for x in r),
            "false_blocks": sum(x["false_block"] for x in r),
            "unresolved_declines": sum(x["unresolved_decline"] for x in r),
            "declines": sum(x["declined"] for x in r),
            "fields_queried": sum(len(x["queried"]) for x in r),
            "episodes_with_query": sum(bool(x["queried"]) for x in r),
            "wasted_queries": sum(len(x["queried"]) for x in r if not x["belief_changed_by_query"]
                                  and x["pre_query_plan"] == x["plan"]),
            "budget_exhausted": sum(x["budget_exhausted"] for x in r),
            "delay_total": sum(x["delay"] for x in r), "delay_mean": round(mean([x["delay"] for x in r]), 3),
            "action_cost_total": sum(x["action_cost"] for x in r),
            "belief_correct_before": sum(x["belief_correct_before"] for x in r),
            "belief_correct_at_decision": sum(x["belief_correct_at_decision"] for x in r),
            "correction_uptake": f"{sum(x['plan_changed_by_query'] for x in r)} plan changes / "
                                 f"{sum(x['belief_changed_by_query'] for x in r)} belief changes",
            "earlier_view_preserved": f"{sum(x['earlier_view_preserved'] for x in r)}/{len(r)}"}
        for t in P.TYPES:
            rt = [x for x in r if x["type"] == t]
            res["by_type"].setdefault(t, {})[pol] = {
                "n": len(rt), "success": sum(x["success"] for x in rt), "invalid": sum(x["invalid_attempt"] for x in rt),
                "false_blocks": sum(x["false_block"] for x in rt), "queries": sum(len(x["queried"]) for x in rt),
                "utility_mean": round(mean([x["utility"] for x in rt]), 3)}
    for x, y in (("P1_always", "P0_accepted"), ("P2_selective", "P0_accepted"), ("P2_selective", "P1_always")):
        c = {}
        for key in ("utility", "success", "fields_queried", "invalid_attempt"):
            val = (lambda z: float(len(z["queried"]))) if key == "fields_queried" else (lambda z, k=key: float(z[k]))
            d = {e: val(per[x][e]) - val(per[y][e]) for e in per[x]}
            ee = est(d)
            ee.update(better=sum(v > 0 for v in d.values()), equal=sum(v == 0 for v in d.values()),
                      worse=sum(v < 0 for v in d.values()))
            c[key] = ee
        res["contrasts"][f"{x} - {y}"] = c
    # pre-declared sensitivity: reweight types so that REWEIGHT_PROV_WRONG of uncorrected provisional reports are wrong
    wrong_types, right_types = ("false_block", "false_permission"), ("provisional_correct",)
    n_wrong = sum(P.ALLOC[t] for t in wrong_types); n_right = sum(P.ALLOC[t] for t in right_types)
    n_prov = n_wrong + n_right
    w = {t: 1.0 for t in P.TYPES}
    for t in wrong_types:
        w[t] = REWEIGHT_PROV_WRONG * n_prov / n_wrong
    for t in right_types:
        w[t] = (1 - REWEIGHT_PROV_WRONG) * n_prov / n_right
    res["sensitivity_reweighted"] = {"provisional_wrong_share": REWEIGHT_PROV_WRONG,
                                     "design_share": round(n_wrong / n_prov, 3), "type_weights": w,
                                     "weighted_mean_utility": {pol: round(sum(w[x["type"]] * x["utility"] for x in rows if x["policy"] == pol) /
                                                                          sum(w[x["type"]] for x in rows if x["policy"] == pol), 3)
                                                               for pol in P.POLICIES}}
    (out / "ANALYSIS.json").write_text(json.dumps(res, indent=1) + "\n")
    L = ["# Observation-policy study (generated)", "", f"Episodes {len(eps)} (matched across {len(P.POLICIES)} policies); "
         f"constants {res['constants']}.", "", "| Policy | utility mean [95% CI] (total) | success | invalid attempts | missed opportunities | false blocks | declines | fields queried (episodes) | wasted queries | delay total | belief correct before → at decision | correction uptake | earlier view preserved |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for pol, d in res["policies"].items():
        u = d["PRIMARY_utility"]
        L.append(f"| {pol} | {u['mean']:.3f} [{u['ci95'][0]:.2f}, {u['ci95'][1]:.2f}] ({d['utility_total']}) | {d['success']} | "
                 f"{d['invalid_attempts']} | {d['missed_opportunities']} | {d['false_blocks']} | {d['declines']} | "
                 f"{d['fields_queried']} ({d['episodes_with_query']}) | {d['wasted_queries']} | {d['delay_total']} | "
                 f"{d['belief_correct_before']} → {d['belief_correct_at_decision']} | {d['correction_uptake']} | {d['earlier_view_preserved']} |")
    L += ["", "## Paired contrasts (per episode; better / equal / worse)", "", "| Contrast | utility | success | fields queried | invalid attempts |", "|---|---|---|---|---|"]
    for k, c in res["contrasts"].items():
        L.append(f"| {k} | " + " | ".join(f"{c[m]['mean']:+.3f} [{c[m]['ci95'][0]:.2f}, {c[m]['ci95'][1]:.2f}] ({c[m]['better']}/{c[m]['equal']}/{c[m]['worse']})"
                                         for m in ("utility", "success", "fields_queried", "invalid_attempt")) + " |")
    L += ["", "## By episode type (success / invalid / false blocks / queries / mean utility)", "", "| Type | n | " + " | ".join(P.POLICIES) + " |", "|---|---|" + "---|" * len(P.POLICIES)]
    for t, d in res["by_type"].items():
        L.append(f"| {t} | {d[P.POLICIES[0]]['n']} | " + " | ".join(f"{d[p]['success']} / {d[p]['invalid']} / {d[p]['false_blocks']} / {d[p]['queries']} / {d[p]['utility_mean']}" for p in P.POLICIES) + " |")
    s = res["sensitivity_reweighted"]
    L += ["", f"Pre-declared sensitivity: provisional-error share reweighted from {s['design_share']} (design) to "
          f"{s['provisional_wrong_share']}: weighted mean utility {s['weighted_mean_utility']}."]
    (out / "TABLES.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
