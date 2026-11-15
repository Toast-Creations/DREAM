"""Score and analyse a temporal-pilot stage (development observations; descriptive only).

Usage: tempo_analyze.py --hub HUB --stage NAME --set main|smoke [--boot 10000] [--seed 20261105]
Writes HUB/stages/NAME/analysis/{scores.jsonl, ANALYSIS.json, TABLES.md}.

Units: the independently generated group. Lengths and variants are averaged within group before any mean; domains
get equal weight. Uncertainty: domain-stratified cluster bootstrap over groups (all nested variants and the C0/C1
pairing retained). Missing (never-run) calls are reported separately; invalid or infra-failed calls count as
incorrect for model outcomes, and infra failures are also listed separately.
"""
import argparse
import collections
import json
import random
import statistics
from pathlib import Path

from _bootstrap import ROOT  # noqa: F401
from tempo import score as S
from tempo.worlds import UNKNOWN


def load(path):
    return [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]


def mean(xs):
    xs = [x for x in xs if x is not None]
    return statistics.mean(xs) if xs else None


def score_call(call, gold, rec):
    base = {k: call[k] for k in ("call_id", "group_id", "domain", "pattern", "length", "arm", "qtype")}
    if rec is None:
        return dict(base, status="missing")
    base.update(status=rec["status"], input_tokens=rec["input_tokens"], output_tokens=rec["output_tokens"],
                stop=rec["stop"], seconds=rec["seconds"])
    text = rec["raw"] if rec["status"] == "ok" else ""
    if gold["type"] == "decision":
        base.update(S.score_decision(text, call["option_ids"], gold), key_plan=gold["key_plan"])
    elif gold["type"] == "facts":
        r = S.score_facts(text, gold["allowed"], gold["gold"])
        f = r["fields"] or {}
        base.update(valid=r["valid"], error=r["error"], exact=r["exact"], extra_fields=r["extra_fields"],
                    field_acc=mean([v["correct"] for v in f.values()]) if f else 0.0,
                    focal_correct=bool(f) and f[gold["focal_field"]]["correct"],
                    side_correct=bool(f) and f[gold["side_field"]]["correct"],
                    focal_gold=gold["gold"][gold["focal_field"]],
                    focal_got=f[gold["focal_field"]]["got"] if f else None,
                    unknown_gold_fields=[k for k, v in gold["gold"].items() if v == UNKNOWN],
                    false_unknown=sum(1 for v in f.values() if v["got"] == UNKNOWN and v["gold"] != UNKNOWN),
                    missed_unknown=sum(1 for v in f.values() if v["gold"] == UNKNOWN and v["got"] != UNKNOWN))
    else:
        r = S.score_action(text, gold["allowed"], gold)
        pred, obs = r["predicted"] or {}, r["observed"] or {}
        changed = [f for f in gold["predicted"] if gold["predicted"][f] not in (UNKNOWN,)
                   and gold["observed"][f] != UNKNOWN and gold["predicted"][f] != gold["observed"][f]]
        ok = lambda d, fs: [bool(d) and d[f]["correct"] for f in fs]
        base.update(valid=r["valid"], error=r["error"], applicable_gold=str(gold["applicable"]),
                    applicable_correct=r["applicable_correct"],
                    predicted_exact=bool(pred) and all(v["correct"] for v in pred.values()),
                    effect_acc=mean(ok(pred, gold["effect_fields"])),
                    preserve_acc=mean(ok(pred, gold["preserve_fields"])),
                    changed_acc=mean(ok(pred, changed)) if changed else None, n_changed=len(changed),
                    observed_exact=bool(obs) and all(v["correct"] for v in obs.values()),
                    a0_all=r["applicable_correct"] and bool(pred) and all(v["correct"] for v in pred.values())
                    and bool(obs) and all(v["correct"] for v in obs.values()))
    return base


def group_means(rows, fn):
    """fn(rows of one group) -> value or None; returns {group: value}."""
    by = collections.defaultdict(list)
    for r in rows:
        by[r["group_id"]].append(r)
    return {g: fn(rs) for g, rs in by.items()}


def domain_weighted(gvals, gdom):
    per = collections.defaultdict(list)
    for g, v in gvals.items():
        if v is not None:
            per[gdom[g]].append(v)
    ds = [statistics.mean(v) for v in per.values() if v]
    return statistics.mean(ds) if ds else None


def bootstrap(gvals, gdom, n, seed):
    rng = random.Random(seed)
    doms = collections.defaultdict(list)
    for g, v in gvals.items():
        if v is not None:
            doms[gdom[g]].append(v)
    if not doms:
        return None
    est = []
    for _ in range(n):
        ms = [statistics.mean(rng.choice(vs) for _ in vs) for vs in doms.values()]
        est.append(statistics.mean(ms))
    est.sort()
    return [round(est[int(0.025 * n)], 4), round(est[int(0.975 * n) - 1], 4)]


def pair_rows(scored):
    """Complete-pair per (group, length, arm)."""
    idx = {(r["group_id"], r["length"], r["arm"], r["qtype"]): r for r in scored}
    out = []
    for (g, L, arm, q), r in idx.items():
        if q != "D0":
            continue
        d1 = idx.get((g, L, arm, "D1"))
        i1 = idx.get((g, L, arm, "I1"))
        miss = r["status"] == "missing" or d1 is None or d1["status"] == "missing"
        out.append({"group_id": g, "domain": r["domain"], "pattern": r["pattern"], "length": L, "arm": arm,
                    "missing": miss,
                    "pair": None if miss else bool(r.get("correct")) and bool(d1.get("correct")),
                    "same_choice_pair": None if miss else (r.get("choice") is not None and r.get("choice") == d1.get("choice")),
                    "i1_same": None if (i1 is None or i1["status"] == "missing" or r["status"] == "missing")
                    else (r.get("choice") is not None and r.get("choice") == i1.get("choice")),
                    "i1_both_correct": None if (i1 is None or i1["status"] == "missing" or r["status"] == "missing")
                    else bool(r.get("correct")) and bool(i1.get("correct"))})
    return out


def summarize(rows, key, gdom, n, seed, filt=lambda r: True):
    rs = [r for r in rows if filt(r) and r.get(key) is not None and r.get("status", "ok") != "missing"
          and not r.get("missing")]
    gv = group_means(rs, lambda x: mean([float(r[key]) for r in x]))
    return {"mean": domain_weighted(gv, gdom), "ci95": bootstrap(gv, gdom, n, seed), "groups": len(gv),
            "rows": len(rs)}


def by(rows, key, field, gdom, filt=lambda r: True):
    out = {}
    for val in sorted({r.get(field) for r in rows if filt(r) and field in r}, key=str):
        rs = [r for r in rows if filt(r) and r.get(field) == val and r.get(key) is not None and not r.get("missing")
              and r.get("status", "ok") != "missing"]
        gv = group_means(rs, lambda x: mean([float(r[key]) for r in x]))
        out[str(val)] = {"mean": domain_weighted(gv, gdom) if field != "domain" else mean(list(gv.values())),
                         "groups": len(gv), "rows": len(rs)}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", required=True)
    ap.add_argument("--stage", required=True)
    ap.add_argument("--set", required=True)
    ap.add_argument("--boot", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=20261105)
    a = ap.parse_args()
    hub = Path(a.hub)
    stage = hub / "stages" / a.stage
    calls = load(hub / "data" / f"{a.set}-calls.jsonl")
    gold = {g["call_id"]: g for g in load(hub / "data" / f"{a.set}-gold.jsonl")}
    recs = {}
    for p in (stage / "calls").glob("*.json"):
        r = json.loads(p.read_text())
        recs[r["call_id"]] = r
    cfg = json.loads((stage / "config.json").read_text())
    planned = calls if cfg["select"] == "all" else [c for c in calls if c["call_id"] in set(cfg["select"])]
    scored = [score_call(c, gold[c["call_id"]], recs.get(c["call_id"])) for c in planned]
    gdom = {r["group_id"]: r["domain"] for r in scored}
    an = stage / "analysis"
    an.mkdir(exist_ok=True)
    with open(an / "scores.jsonl", "w") as fh:
        for r in scored:
            fh.write(json.dumps(r) + "\n")
    pairs = pair_rows(scored)
    B, sd = a.boot, a.seed
    res = {"stage": a.stage, "set": a.set, "planned_calls": len(planned),
           "status_counts": dict(collections.Counter(r["status"] for r in scored)),
           "invalid_by_error": dict(collections.Counter(r.get("error") for r in scored
                                                        if r["status"] == "ok" and not r.get("valid"))),
           "truncated": sum(1 for r in scored if r.get("stop") == "length"),
           "tokens": {"input_max": max((r.get("input_tokens") or 0) for r in scored),
                      "input_mean": mean([r.get("input_tokens") for r in scored]),
                      "output_total": sum((r.get("output_tokens") or 0) for r in scored),
                      "seconds_total": round(sum((r.get("seconds") or 0) for r in scored), 1)}}
    for arm in ("C0", "C1"):
        A = lambda r, arm=arm: r["arm"] == arm
        res[arm] = {
            "complete_pair": summarize(pairs, "pair", gdom, B, sd, A),
            "complete_pair_by_length": by(pairs, "pair", "length", gdom, A),
            "complete_pair_by_pattern": by(pairs, "pair", "pattern", gdom, A),
            "complete_pair_by_domain": by(pairs, "pair", "domain", gdom, A),
            "same_choice_both_sides": summarize(pairs, "same_choice_pair", gdom, B, sd, A),
            "i1_same_as_d0": summarize(pairs, "i1_same", gdom, B, sd, A),
            "i1_and_d0_both_correct": summarize(pairs, "i1_both_correct", gdom, B, sd, A),
        }
        for q in ("D0", "D1", "I1"):
            F = lambda r, q=q, arm=arm: r["arm"] == arm and r["qtype"] == q
            res[arm][f"{q}_correct"] = summarize(scored, "correct", gdom, B, sd, F)
            res[arm][f"{q}_correct_by_pattern"] = by(scored, "correct", "pattern", gdom, F)
            res[arm][f"{q}_lure_rate"] = summarize(scored, "lure", gdom, B, sd,
                                                   lambda r, F=F: F(r) and r["pattern"] != 6 and r.get("lure") is not None)
            res[arm][f"{q}_other_side_rate"] = summarize(scored, "other_side", gdom, B, sd, F)
        res[arm]["unc_D0_obs_correct"] = summarize(scored, "correct", gdom, B, sd,
                                                   lambda r: r["arm"] == arm and r["qtype"] == "D0" and r["pattern"] == 6)
        res[arm]["unc_D1_resolved_correct"] = summarize(scored, "correct", gdom, B, sd,
                                                        lambda r: r["arm"] == arm and r["qtype"] == "D1" and r["pattern"] == 6)
        res[arm]["needless_obs_rate"] = summarize(scored, "obs_chosen", gdom, B, sd,
                                                  lambda r: r["arm"] == arm and r["qtype"] in ("D0", "D1", "I1")
                                                  and r.get("key_plan") != "OBS")
        FA = lambda r, arm=arm: r["arm"] == arm and r["qtype"] == "A0"
        for k in ("applicable_correct", "predicted_exact", "effect_acc", "preserve_acc", "changed_acc",
                  "observed_exact", "a0_all"):
            res[arm][f"A0_{k}"] = summarize(scored, k, gdom, B, sd, FA)
        res[arm]["A0_applicable_by_class"] = by(scored, "applicable_correct", "applicable_gold", gdom, FA)
        res[arm]["A0_by_pattern"] = by(scored, "a0_all", "pattern", gdom, FA)
    for q in ("S0", "P0", "K0"):
        F = lambda r, q=q: r["qtype"] == q
        res["C1"][q] = {k: summarize(scored, k, gdom, B, sd, F) for k in ("exact", "field_acc", "focal_correct",
                                                                         "side_correct")}
        res["C1"][q]["focal_by_pattern"] = by(scored, "focal_correct", "pattern", gdom, F)
        res["C1"][q]["exact_by_length"] = by(scored, "exact", "length", gdom, F)
        res["C1"][q]["false_unknown_fields"] = sum(r.get("false_unknown") or 0 for r in scored if F(r))
        res["C1"][q]["missed_unknown_fields"] = sum(r.get("missed_unknown") or 0 for r in scored if F(r))
    # paired primary contrast C1 - C0 per group (lengths averaged within group)
    def gpair(arm):
        rs = [p for p in pairs if p["arm"] == arm and not p["missing"]]
        return group_means(rs, lambda x: mean([float(p["pair"]) for p in x]))
    g0, g1 = gpair("C0"), gpair("C1")
    common = sorted(set(g0) & set(g1))
    diff = {g: g1[g] - g0[g] for g in common}
    res["primary"] = {"C1_complete_pair": res["C1"]["complete_pair"], "C0_complete_pair": res["C0"]["complete_pair"],
                      "C1_minus_C0": {"mean": domain_weighted(diff, gdom), "ci95": bootstrap(diff, gdom, B, sd),
                                      "groups_better": sum(1 for v in diff.values() if v > 0),
                                      "groups_worse": sum(1 for v in diff.values() if v < 0),
                                      "groups_equal": sum(1 for v in diff.values() if v == 0), "groups": len(diff)},
                      "bootstrap": {"resamples": B, "seed": sd, "method": "domain-stratified cluster bootstrap"}}
    # group-level table
    table = []
    for g in sorted(gdom):
        row = {"group": g, "domain": gdom[g], "pattern": next(r["pattern"] for r in scored if r["group_id"] == g)}
        for arm in ("C0", "C1"):
            ps = [p["pair"] for p in pairs if p["group_id"] == g and p["arm"] == arm and not p["missing"]]
            row[f"{arm}_pairs"] = f"{sum(ps)}/{len(ps)}"
        for q in ("S0", "P0", "K0"):
            xs = [r.get("exact") for r in scored if r["group_id"] == g and r["qtype"] == q and r["status"] != "missing"]
            row[q] = f"{sum(bool(x) for x in xs)}/{len(xs)}"
        for arm in ("C0", "C1"):
            xs = [r.get("a0_all") for r in scored if r["group_id"] == g and r["qtype"] == "A0" and r["arm"] == arm
                  and r["status"] != "missing"]
            row[f"A0_{arm}"] = f"{sum(bool(x) for x in xs)}/{len(xs)}"
        table.append(row)
    res["group_table"] = table
    (an / "ANALYSIS.json").write_text(json.dumps(res, indent=2) + "\n")
    lines = ["# Temporal pilot tables (development observations)", "", f"Stage {a.stage}; set {a.set}; "
             f"planned calls {len(planned)}; status {res['status_counts']}", "",
             "| group | domain | pattern | C0 pairs | C1 pairs | S0 | P0 | K0 | A0 C0 | A0 C1 |", "|---|---|---|---|---|---|---|---|---|---|"]
    for r in table:
        lines.append(f"| {r['group']} | {r['domain']} | {r['pattern']} | {r['C0_pairs']} | {r['C1_pairs']} | {r['S0']} | "
                     f"{r['P0']} | {r['K0']} | {r['A0_C0']} | {r['A0_C1']} |")
    (an / "TABLES.md").write_text("\n".join(lines) + "\n")
    p = res["primary"]
    print(json.dumps({"status": res["status_counts"], "C0_pair": p["C0_complete_pair"]["mean"],
                      "C1_pair": p["C1_complete_pair"]["mean"], "C1-C0": p["C1_minus_C0"]}, indent=1))


if __name__ == "__main__":
    main()
