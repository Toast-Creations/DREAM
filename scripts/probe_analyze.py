"""Score and analyse the precondition probe (development; descriptive only).

Usage: probe_analyze.py --hub HUB --set probe|probesmoke --stage STAGE [--boot 10000] [--seed 20261105]
Writes HUB/analysis-<set>/{scores.jsonl, ANALYSIS.json, TABLES.md}.

Unit: the fresh world (24; 12 per domain). Rows, controls, conditions and arms are nested in worlds. Group value =
mean within world; domains equally weighted; domain-stratified cluster bootstrap over worlds. Invalid replies,
infra failures and missing calls are wrong on every outcome and also counted. No primary outcome is conditioned on
a correct intermediate answer.
"""
import argparse
import collections
import json
from pathlib import Path

from _bootstrap import ROOT  # noqa: F401
from tempo_analyze import bootstrap, domain_weighted, load, mean
from tempo import probe_score as PS
from tempo.worlds import UNKNOWN

CELLS = [("direct", "C0"), ("direct", "C1"), ("checklist", "C0"), ("checklist", "C1"), ("supplied", "C0")]


def records(stage):
    out = {}
    for p in (stage / "calls").glob("*.json"):
        r = json.loads(p.read_text())
        out[r["call_id"]] = r
    return out


def ok(r, k):
    return r.get("status") == "ok" and bool(r.get("valid")) and bool(r.get(k))


def est(gv, gdom, B, seed):
    gv = {g: v for g, v in gv.items() if v is not None}
    m = domain_weighted(gv, gdom)
    return {"mean": None if m is None else round(m, 4), "ci95": bootstrap(gv, gdom, B, seed), "worlds": len(gv)}


def contrast(x, y, gdom, B, seed):
    d = {g: x[g] - y[g] for g in x if g in y and x[g] is not None and y[g] is not None}
    e = est(d, gdom, B, seed)
    e.update(better=sum(v > 0 for v in d.values()), equal=sum(v == 0 for v in d.values()),
             worse=sum(v < 0 for v in d.values()))
    return e


def by_world(rows, fn):
    b = collections.defaultdict(list)
    for r in rows:
        b[r["group_id"]].append(r)
    return {g: fn(rs) for g, rs in b.items()}


def pair_app(rs):
    d = {r["row"]: r for r in rs}
    if "valid" not in d or "invalid" not in d:
        return None
    return float(ok(d["valid"], "applicable_correct") and ok(d["invalid"], "applicable_correct"))


def inv_blocked(rs):
    x = [r for r in rs if r["row"] == "invalid"]
    return float(ok(x[0], "blocked_and_no_effect")) if x else None


def balanced(rs):
    d = {r["row"]: r for r in rs}
    if "valid" not in d or "invalid" not in d:
        return None
    return (float(ok(d["valid"], "applicable_correct")) + float(ok(d["invalid"], "applicable_correct"))) / 2


def cell_summary(rows, gdom, B, seed):
    out = {"rows": len(rows), "status": dict(collections.Counter(r["status"] for r in rows)),
           "invalid_replies": sum(1 for r in rows if r["status"] == "ok" and not r.get("valid")),
           "invalid_by_error": dict(collections.Counter(r.get("error") for r in rows
                                                        if r["status"] == "ok" and not r.get("valid"))),
           "output_tokens_mean": mean([r.get("output_tokens") for r in rows]),
           "seconds_total": round(sum(r.get("seconds") or 0 for r in rows), 1)}
    for k in ("valid", "invalid", "unknown_only", "false_unknown"):
        x = [r for r in rows if r["row"] == k]
        if not x:
            continue
        out[k] = {"rows": len(x), "applicable_correct": sum(ok(r, "applicable_correct") for r in x),
                  "answers": dict(collections.Counter(str(r.get("model_applicable")) if r.get("valid") else "invalid"
                                                      for r in x)),
                  "successor_exact": sum(ok(r, "predicted_exact") for r in x),
                  "observed_exact": sum(ok(r, "observed_exact") for r in x),
                  "all_three": sum(ok(r, "a0_all") for r in x),
                  "gating_inconsistent": sum(1 for r in x if r.get("valid") and r.get("gating_inconsistent"))}
        if k == "valid":
            out[k]["changed_correct"] = sum(ok(r, "changed_correct") for r in x)
        if k == "invalid":
            out[k]["blocked_and_no_effect"] = sum(ok(r, "blocked_and_no_effect") for r in x)
    pv = by_world(rows, pair_app)
    ib = by_world(rows, inv_blocked)
    out["PRIMARY_pair_applicability"] = est(pv, gdom, B, seed)
    out["PRIMARY_pair_applicability_count"] = f"{int(sum(v for v in pv.values() if v is not None))}/{sum(v is not None for v in pv.values())}"
    out["PRIMARY_invalid_blocked_no_effect"] = est(ib, gdom, B, seed)
    out["balanced_applicability"] = est(by_world(rows, balanced), gdom, B, seed)
    vi = [r for r in rows if r["row"] in ("valid", "invalid")]
    out["successor_exact_pairs"] = est(by_world(vi, lambda x: mean([float(ok(r, "predicted_exact")) for r in x])),
                                       gdom, B, seed)
    out["observed_exact_pairs"] = est(by_world(vi, lambda x: mean([float(ok(r, "observed_exact")) for r in x])),
                                      gdom, B, seed)
    out["preserve_mean"] = mean([r.get("preserve_acc") for r in rows if r.get("valid")])
    if rows and rows[0]["condition"] == "checklist":
        pr = [r for r in rows if r.get("valid") and r.get("preconditions_valid")]
        keys = sorted({k for r in pr for k in r["pred_correct"]})
        out["predicates"] = {
            "rows_with_valid_vector": len(pr),
            "vector_exact": sum(1 for r in pr if r["pred_vector_exact"]),
            "per_key_correct": {k: f"{sum(1 for r in pr if r['pred_correct'].get(k))}/{sum(1 for r in pr if k in r['pred_correct'])}" for k in keys},
            "false_certainty": sum(r["false_certainty"] for r in pr),
            "unneeded_unknown": sum(r["unneeded_unknown"] for r in pr),
            "wrong_definite": sum(r["wrong_definite"] for r in pr),
            "applicability_consistent_with_own_predicates": sum(1 for r in pr if r.get("consistent_with_own_predicates")),
            "vector_exact_by_row": {k: f"{sum(1 for r in pr if r['row'] == k and r['pred_vector_exact'])}/{sum(1 for r in pr if r['row'] == k)}"
                                    for k in ("valid", "invalid", "unknown_only", "false_unknown")},
            "vector_exact_mean": est(by_world(rows, lambda x: mean([float(ok(r, "pred_vector_exact")) for r in x])),
                                     gdom, B, seed)}
        j = collections.Counter()
        for r in rows:
            if not (r.get("valid") and r.get("preconditions_valid")):
                j["reply_invalid"] += 1
                continue
            a = "predicates_exact" if r["pred_vector_exact"] else "predicates_wrong"
            b = "app_correct" if r["applicable_correct"] else (
                "app_wrong_consistent" if r.get("consistent_with_own_predicates") else "app_wrong_inconsistent")
            j[f"{a}|{b}"] += 1
        out["mapping_joint"] = dict(j)
        out["output_orders"] = dict(collections.Counter(" > ".join(r["order"]) for r in rows if r.get("order")))
    return out, pv, ib


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", required=True)
    ap.add_argument("--set", required=True)
    ap.add_argument("--stage", required=True)
    ap.add_argument("--boot", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=20261105)
    a = ap.parse_args()
    hub = Path(a.hub)
    calls = load(hub / "data" / f"{a.set}-calls.jsonl")
    gold = {g["call_id"]: g for g in load(hub / "data" / f"{a.set}-gold.jsonl")}
    recs = records(hub / "stages" / a.stage)
    rows = []
    for c in calls:
        g = gold[c["call_id"]]
        base = {k: c[k] for k in ("call_id", "group_id", "domain", "family", "pattern", "condition", "arm", "row")}
        rec = recs.get(c["call_id"])
        if rec is None:
            rows.append(dict(base, status="missing", valid=False))
            continue
        base.update(status=rec["status"], input_tokens=rec["input_tokens"], output_tokens=rec["output_tokens"],
                    stop=rec["stop"], seconds=rec["seconds"])
        text = rec["raw"] if rec["status"] == "ok" else ""
        r = PS.score_probe(text, g, c["condition"], list(g["predicates"]))
        r.pop("predicted", None); r.pop("observed", None)
        rows.append({**base, **r, "applicable_gold": PS.tv(g["applicable"])})
    gdom = {r["group_id"]: r["domain"] for r in rows}
    out = hub / f"analysis-{a.set}"
    out.mkdir(exist_ok=True)
    with open(out / "scores.jsonl", "w") as fh:
        for r in rows:
            fh.write(json.dumps(r, default=str) + "\n")
    B, sd = a.boot, a.seed
    res = {"set": a.set, "stage": a.stage, "boot": B, "seed": sd, "planned": len(calls),
           "status": dict(collections.Counter(r["status"] for r in rows)),
           "truncated": sum(1 for r in rows if r.get("stop") == "length"),
           "input_tokens_max": max((r.get("input_tokens") or 0) for r in rows),
           "output_tokens_max": max((r.get("output_tokens") or 0) for r in rows),
           "seconds_total": round(sum(r.get("seconds") or 0 for r in rows), 1), "cells": {}, "contrasts": {}}
    pv, ib = {}, {}
    for cond, arm in CELLS:
        x = [r for r in rows if r["condition"] == cond and r["arm"] == arm]
        if x:
            res["cells"][f"{cond}:{arm}"], pv[(cond, arm)], ib[(cond, arm)] = cell_summary(x, gdom, B, sd)
    for (x, y) in ((("checklist", "C0"), ("direct", "C0")), (("checklist", "C1"), ("direct", "C1")),
                   (("supplied", "C0"), ("direct", "C0")), (("supplied", "C0"), ("checklist", "C0"))):
        if x in pv and y in pv:
            nm = f"{x[0]}:{x[1]} - {y[0]}:{y[1]}"
            res["contrasts"][nm] = {"pair_applicability": contrast(pv[x], pv[y], gdom, B, sd),
                                    "invalid_blocked_no_effect": contrast(ib[x], ib[y], gdom, B, sd)}
    (out / "ANALYSIS.json").write_text(json.dumps(res, indent=1, default=str) + "\n")
    (out / "TABLES.md").write_text(tables(res))
    print(json.dumps({k: (v["PRIMARY_pair_applicability_count"], v.get("invalid", {}).get("blocked_and_no_effect"))
                      for k, v in res["cells"].items()}))


def f(e):
    if not e or e.get("mean") is None:
        return "—"
    ci = e.get("ci95")
    return f"{e['mean']:.3f}" + (f" [{ci[0]:.2f}, {ci[1]:.2f}]" if ci else "")


def tables(res):
    L = ["# Precondition probe tables (generated)", "",
         f"Status {res['status']}; truncated {res['truncated']}; max input {res['input_tokens_max']}; max output "
         f"{res['output_tokens_max']}; generation {res['seconds_total']} s.", "",
         "## Primary outcomes", "",
         "| Condition:arm | pair applicability (count; weighted) | invalid rejected + no effect (count; weighted) | balanced applicability | invalid replies |",
         "|---|---|---|---|---|"]
    for k, v in res["cells"].items():
        inv = v.get("invalid", {})
        L.append(f"| {k} | {v['PRIMARY_pair_applicability_count']}; {f(v['PRIMARY_pair_applicability'])} | "
                 f"{inv.get('blocked_and_no_effect')}/{inv.get('rows')}; {f(v['PRIMARY_invalid_blocked_no_effect'])} | "
                 f"{f(v['balanced_applicability'])} | {v['invalid_replies']} |")
    L += ["", "## Paired contrasts (within worlds; better / equal / worse)", "",
          "| Contrast | pair applicability | invalid rejected + no effect |", "|---|---|---|"]
    for k, v in res["contrasts"].items():
        a, b = v["pair_applicability"], v["invalid_blocked_no_effect"]
        L.append(f"| {k} | {f(a)} ({a['better']}/{a['equal']}/{a['worse']}) | {f(b)} ({b['better']}/{b['equal']}/{b['worse']}) |")
    L += ["", "## Rows by kind", "",
          "| Condition:arm | row | n | applicable correct | answers | successor exact | observed exact | all three | gating inconsistent |",
          "|---|---|---|---|---|---|---|---|---|"]
    for k, v in res["cells"].items():
        for rk in ("valid", "invalid", "unknown_only", "false_unknown"):
            if rk in v:
                x = v[rk]
                L.append(f"| {k} | {rk} | {x['rows']} | {x['applicable_correct']} | {x['answers']} | "
                         f"{x['successor_exact']} | {x['observed_exact']} | {x['all_three']} | {x['gating_inconsistent']} |")
    for k, v in res["cells"].items():
        if "predicates" in v:
            p = v["predicates"]
            L += ["", f"## Checklist predicates — {k}", "",
                  f"Valid vectors {p['rows_with_valid_vector']}; vector exact {p['vector_exact']} (by row {p['vector_exact_by_row']}); "
                  f"per key {p['per_key_correct']}; false certainty {p['false_certainty']}; unneeded unknown "
                  f"{p['unneeded_unknown']}; wrong definite {p['wrong_definite']}; applicability consistent with own "
                  f"predicates {p['applicability_consistent_with_own_predicates']}.", "",
                  f"Mapping joint: {v['mapping_joint']}", "", f"Output key orders: {v['output_orders']}"]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
