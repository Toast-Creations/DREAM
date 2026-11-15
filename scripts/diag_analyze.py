"""Score and analyse the V1.7.2 diagnostic (development observations; descriptive only).

Usage: diag_analyze.py --hub HUB --set diag|diagsmoke --stage1 S1 --stage2 S2 --pilot-hub PILOT [--boot 10000]
Writes HUB/analysis-<set>/{scores.jsonl, ANALYSIS.json, TABLES.md}.

Unit: the original independently generated group (24). Every side, variant, block and arm of a group is a
correlated observation of it. Group values are means within group; domains get equal weight; intervals are a
domain-stratified cluster bootstrap over groups (seed 20261105). Pooled counts are reported as counts.
Invalid replies, infra failures, upstream (step-1) failures and missing calls all count as incorrect and are also
listed. No primary outcome is conditioned on commitment or on a correct intermediate readout.
"""
import argparse
import collections
import json
from pathlib import Path

from _bootstrap import ROOT  # noqa: F401
from tempo_analyze import bootstrap, domain_weighted, load, mean, score_call
from tempo.worlds import UNKNOWN


def safe(cid):
    return cid.replace("|", "__")


def records(stage_dir):
    out = {}
    if stage_dir.exists():
        for p in (stage_dir / "calls").glob("*.json"):
            r = json.loads(p.read_text())
            out[r["call_id"]] = r
    return out


def scored_rows(calls, gold, recs):
    rows = []
    for c in calls:
        g = gold[c["call_id"]]
        r = score_call(c, g, recs.get(c["call_id"]))
        r.update(block=c.get("block"), variant=c.get("variant"), step=c.get("step"))
        if g["type"] == "decision":
            r["determined"] = g["determined"]
            ch = r.get("choice")
            r["chose_invalid_plan"] = bool(ch) and ch in g["plan_valid"] and not g["plan_valid"][ch]
            r["unneeded_obs"] = g["determined"] and bool(r.get("obs_chosen"))
        rows.append(r)
    return rows


def ok(r, k):
    return r.get("status") == "ok" and bool(r.get(k))


def est(gvals, gdom, B, seed):
    gv = {g: v for g, v in gvals.items() if v is not None}
    m = domain_weighted(gv, gdom)
    return {"mean": None if m is None else round(m, 4), "ci95": bootstrap(gv, gdom, B, seed), "groups": len(gv)}


def contrast(x, y, gdom, B, seed):
    """Paired group-level difference x - y over groups present in both."""
    gs = [g for g in x if g in y and x[g] is not None and y[g] is not None]
    d = {g: x[g] - y[g] for g in gs}
    e = est(d, gdom, B, seed)
    e.update(better=sum(v > 0 for v in d.values()), equal=sum(v == 0 for v in d.values()),
             worse=sum(v < 0 for v in d.values()))
    return e


def group_vals(rows, fn):
    by = collections.defaultdict(list)
    for r in rows:
        by[r["group_id"]].append(r)
    return {g: fn(rs) for g, rs in by.items()}


def decisions(rows, block, arm):
    return [r for r in rows if r.get("block") == block and r["arm"] == arm and r["qtype"] in ("D0", "D1")]


def pair_val(rs):
    d = {r["qtype"]: r for r in rs}
    if "D0" not in d or "D1" not in d:
        return None
    return float(ok(d["D0"], "correct") and ok(d["D1"], "correct"))


def det_acc(rs):
    xs = [float(ok(r, "correct")) for r in rs if r.get("determined")]
    return mean(xs) if xs else None


def decision_block(rows, block, arm, gdom, B, seed):
    rs = decisions(rows, block, arm)
    det = [r for r in rs if r.get("determined")]
    unc = [r for r in rs if not r.get("determined")]
    out = {"rows": len(rs), "status": dict(collections.Counter(r["status"] for r in rs)),
           "invalid": sum(1 for r in rs if r["status"] == "ok" and not r.get("valid")),
           "correct": sum(ok(r, "correct") for r in rs),
           "determined_rows": len(det), "determined_correct": sum(ok(r, "correct") for r in det),
           "unneeded_obs": sum(ok(r, "unneeded_obs") for r in det),
           "chose_invalid_plan": sum(ok(r, "chose_invalid_plan") for r in det),
           "chose_plan_on_determined": sum(1 for r in det if r.get("choice") and not r.get("obs_chosen")),
           "uncertain_rows": len(unc), "uncertain_obs_correct": sum(ok(r, "correct") for r in unc),
           "D0_correct": sum(ok(r, "correct") for r in rs if r["qtype"] == "D0"),
           "D1_correct": sum(ok(r, "correct") for r in rs if r["qtype"] == "D1"),
           "same_choice_both_sides": None}
    pv = group_vals(rs, pair_val)
    out["complete_pair"] = est(pv, gdom, B, seed)
    out["complete_pair_count"] = f"{int(sum(v for v in pv.values() if v is not None))}/{sum(v is not None for v in pv.values())}"
    out["determined_accuracy"] = est(group_vals(rs, det_acc), gdom, B, seed)
    out["unneeded_obs_rate"] = est(group_vals(det, lambda x: mean([float(ok(r, "unneeded_obs")) for r in x])),
                                   gdom, B, seed)
    ch = collections.defaultdict(dict)
    for r in rs:
        ch[r["group_id"]][r["qtype"]] = r.get("choice")
    out["same_choice_both_sides"] = sum(1 for v in ch.values() if v.get("D0") and v.get("D0") == v.get("D1"))
    return out, pv, group_vals(rs, det_acc)


def action_block(rows, arm, gdom, B, seed):
    rs = [r for r in rows if r.get("block") == "D" and r["arm"] == arm]
    cls = {"valid": "True", "invalid": "False", "uncertain": UNKNOWN}
    out = {"rows": len(rs), "invalid_replies": sum(1 for r in rs if r["status"] == "ok" and not r.get("valid")),
           "status": dict(collections.Counter(r["status"] for r in rs))}
    for v in ("valid", "invalid", "uncertain"):
        x = [r for r in rs if r["variant"] == v]
        assert all(r.get("applicable_gold") == cls[v] for r in x if r["status"] != "missing"), v
        out[v] = {"rows": len(x), "applicable_correct": sum(ok(r, "applicable_correct") for r in x),
                  "successor_exact": sum(ok(r, "predicted_exact") for r in x),
                  "observed_exact": sum(ok(r, "observed_exact") for r in x),
                  "all_three": sum(ok(r, "a0_all") for r in x),
                  "applicable_answers": dict(collections.Counter(str(r.get("applicable_raw")) for r in x))}
        if v == "valid":
            out[v]["changed_fields_correct"] = f"{sum(1 for r in x if r.get('changed_acc') == 1.0)}/{len(x)}"
        out[v]["unaffected_fields_mean"] = mean([r.get("preserve_acc") for r in x if r["status"] == "ok"])
    vi = [r for r in rs if r["variant"] in ("valid", "invalid")]

    def bal(x):
        d = {r["variant"]: r for r in x}
        if set(d) != {"valid", "invalid"}:
            return None
        return (float(ok(d["valid"], "applicable_correct")) + float(ok(d["invalid"], "applicable_correct"))) / 2

    def pair(key):
        def f(x):
            d = {r["variant"]: r for r in x}
            return None if set(d) != {"valid", "invalid"} else float(ok(d["valid"], key) and ok(d["invalid"], key))
        return f
    out["balanced_applicability"] = est(group_vals(vi, bal), gdom, B, seed)
    out["pair_applicability_correct"] = est(group_vals(vi, pair("applicable_correct")), gdom, B, seed)
    out["pair_all_three_correct"] = est(group_vals(vi, pair("a0_all")), gdom, B, seed)
    out["successor_exact_mean"] = est(group_vals(vi, lambda x: mean([float(ok(r, "predicted_exact")) for r in x])),
                                      gdom, B, seed)
    out["observed_exact_mean"] = est(group_vals(vi, lambda x: mean([float(ok(r, "observed_exact")) for r in x])),
                                     gdom, B, seed)
    out["all_three_mean"] = est(group_vals(vi, lambda x: mean([float(ok(r, "a0_all")) for r in x])), gdom, B, seed)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", required=True)
    ap.add_argument("--set", required=True)
    ap.add_argument("--stage1", required=True)
    ap.add_argument("--stage2", required=True)
    ap.add_argument("--pilot-hub", required=True)
    ap.add_argument("--boot", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=20261105)
    a = ap.parse_args()
    hub, pilot = Path(a.hub), Path(a.pilot_hub)
    B, sd = a.boot, a.seed
    c1 = load(hub / "data" / f"{a.set}-calls.jsonl")
    g1 = {g["call_id"]: g for g in load(hub / "data" / f"{a.set}-gold.jsonl")}
    tm = load(hub / "data" / f"{a.set}-step2-templates.jsonl")
    c2p = hub / "data" / f"{a.set}c2-calls.jsonl"
    c2 = load(c2p) if c2p.exists() else []
    c2_ids = {c["call_id"] for c in c2}
    g2 = {t["call_id"]: t["gold"] for t in tm}
    rec1, rec2 = records(hub / "stages" / a.stage1), records(hub / "stages" / a.stage2)
    # step-2 calls never built (upstream failure or step 2 not yet built) are scored as missing/upstream
    for t in tm:
        if t["call_id"] not in c2_ids:
            c2.append({k: t[k] for k in ("call_id", "group_id", "domain", "pattern", "length", "arm", "qtype",
                                         "block", "variant", "step", "option_ids")})
    rows = scored_rows([c for c in c1 if c.get("block") != "R"], g1, rec1) + scored_rows(c2, g2, rec2)
    for r in rows:
        if r["block"] == "C" and r.get("step") == 2 and r["status"] == "missing":
            s1 = rec1.get(next(t["step1_call_id"] for t in tm if t["call_id"] == r["call_id"]))
            r["upstream"] = None if s1 is None else s1["status"]
    # raw applicability answer for per-class reporting
    for r in rows:
        if r["qtype"] == "A0" and r["status"] == "ok":
            from tempo import score as S
            obj, err = S.parse_object(rec1[r["call_id"]]["raw"])
            r["applicable_raw"] = S._applicable(obj.get("applicable")) if err is None else "invalid"
    # old pilot short D0/D1 (block "old"): same groups, arms and option mappings as A
    old = []
    if a.set == "diag":
        pc = {c["call_id"]: c for c in load(pilot / "data" / "main-calls.jsonl")}
        pg = {g["call_id"]: g for g in load(pilot / "data" / "main-gold.jsonl")}
        prec = records(pilot / "stages" / "main")
        for r in [r for r in rows if r["block"] == "A"]:
            ocid = f"{r['group_id']}|short|{r['arm']}|{r['qtype']}"
            ag = g1[r["call_id"]]
            og = dict(pg[ocid], plan_valid=ag["plan_valid"], determined=ag["determined"])
            assert og["acceptable"] == ag["acceptable"] and og["obs_option"] == ag["obs_option"]
            c = dict(pc[ocid], block="old", variant={"D0": "a", "D1": "b"}[r["qtype"]])
            old += scored_rows([c], {ocid: og}, prec)
    allrows = rows + old
    gdom = {r["group_id"]: r["domain"] for r in allrows}
    out = Path(a.hub) / f"analysis-{a.set}"
    out.mkdir(exist_ok=True)
    with open(out / "scores.jsonl", "w") as fh:
        for r in allrows:
            fh.write(json.dumps(r) + "\n")
    res = {"set": a.set, "stages": [a.stage1, a.stage2], "boot": B, "seed": sd,
           "planned_calls": {"stage1": len([c for c in c1]), "stage2_templates": len(tm), "stage2_built": len(c2_ids)},
           "status_counts": dict(collections.Counter((r["block"], r["status"]) for r in rows).most_common()),
           "invalid_by_error": dict(collections.Counter(r.get("error") for r in rows
                                                        if r["status"] == "ok" and not r.get("valid"))),
           "truncated": sum(1 for r in rows if r.get("stop") == "length"),
           "input_tokens_max": max((r.get("input_tokens") or 0) for r in rows),
           "seconds_total": round(sum((r.get("seconds") or 0) for r in rows), 1)}
    res["status_counts"] = {f"{k[0]}:{k[1]}": v for k, v in res["status_counts"].items()}
    dec, pv, dv = {}, {}, {}
    blocks = (["old"] if old else []) + ["A", "B", "C", "E"]
    for b in blocks:
        for arm in ("C0", "C1"):
            if not decisions(allrows, b, arm):
                continue
            dec[f"{b}:{arm}"], pv[(b, arm)], dv[(b, arm)] = decision_block(allrows, b, arm, gdom, B, sd)
    res["decisions"] = dec
    con = {}
    for arm in ("C0", "C1"):
        if ("old", arm) in pv and ("A", arm) in pv:
            con[f"A-old:{arm}:complete_pair"] = contrast(pv[("A", arm)], pv[("old", arm)], gdom, B, sd)
            con[f"A-old:{arm}:determined_accuracy"] = contrast(dv[("A", arm)], dv[("old", arm)], gdom, B, sd)
        if ("A", arm) in pv and ("B", arm) in pv:
            con[f"B-A:{arm}:complete_pair"] = contrast(pv[("B", arm)], pv[("A", arm)], gdom, B, sd)
            con[f"B-A:{arm}:determined_accuracy"] = contrast(dv[("B", arm)], dv[("A", arm)], gdom, B, sd)
        if ("E", arm) in dv and ("B", arm) in dv:
            con[f"E-B:{arm}:determined_accuracy"] = contrast(dv[("E", arm)], dv[("B", arm)], gdom, B, sd)
    if ("C", "C1") in pv and ("B", "C1") in pv:
        con["C-B:C1:complete_pair"] = contrast(pv[("C", "C1")], pv[("B", "C1")], gdom, B, sd)
        con["C-B:C1:determined_accuracy"] = contrast(dv[("C", "C1")], dv[("B", "C1")], gdom, B, sd)
    res["contrasts"] = con
    # C: readouts and joint readout/decision
    s1 = {r["call_id"]: r for r in rows if r["block"] == "C" and r["qtype"] == "S0"}
    s2 = {r["call_id"]: r for r in rows if r["block"] == "C" and r.get("step") == 2}
    joint = collections.Counter()
    for t in tm:
        a1, a2 = s1.get(t["step1_call_id"]), s2.get(t["call_id"])
        rd = "readout_invalid" if not a1 or a1["status"] != "ok" or not a1.get("valid") else (
            "readout_exact" if a1.get("exact") else "readout_inexact")
        dc = "decision_correct" if a2 and ok(a2, "correct") else "decision_wrong"
        joint[f"{rd}|{dc}"] += 1
    res["C_workflow"] = {"sides": len(tm), "readout_valid": sum(1 for r in s1.values() if ok(r, "valid")),
                         "readout_exact": sum(1 for r in s1.values() if ok(r, "exact")),
                         "readout_focal_correct": sum(1 for r in s1.values() if ok(r, "focal_correct")),
                         "readout_false_unknown_fields": sum(r.get("false_unknown") or 0 for r in s1.values()),
                         "decision_correct": sum(1 for r in s2.values() if ok(r, "correct")),
                         "upstream_failures": sum(1 for r in s2.values() if r.get("upstream")),
                         "joint": dict(joint)}
    res["actions"] = {arm: action_block(rows, arm, gdom, B, sd) for arm in ("C0", "C1")
                      if any(r.get("block") == "D" and r["arm"] == arm for r in rows)}
    # smoke: exact-prompt repeats against the saved pilot outputs
    rep = [c for c in c1 if c.get("block") == "R"]
    if rep:
        prec = records(pilot / "stages" / "main")
        res["repeats"] = [{"call_id": c["call_id"], "identical_raw": (rec1.get(c["call_id"]) or {}).get("raw")
                           == prec[c["repeat_of"]]["raw"]} for c in rep]
    (out / "ANALYSIS.json").write_text(json.dumps(res, indent=1) + "\n")
    (out / "TABLES.md").write_text(tables(res))
    print(json.dumps({"decisions": {k: (v["complete_pair_count"], v["determined_correct"], v["unneeded_obs"])
                                    for k, v in dec.items()}, "invalid": res["invalid_by_error"],
                      "truncated": res["truncated"]}, indent=1))


def f(e):
    if not e or e.get("mean") is None:
        return "—"
    ci = e.get("ci95")
    return f"{e['mean']:.3f}" + (f" [{ci[0]:.2f}, {ci[1]:.2f}]" if ci else "")


def tables(res):
    L = ["# Diagnostic tables (generated)", "", "## Decisions", "",
         "| Block:arm | complete pair (count; weighted) | determined correct | unneeded observe | invalid-plan choices | uncertain controls: observe | invalid replies |",
         "|---|---|---|---|---|---|---|"]
    for k, v in res["decisions"].items():
        L.append(f"| {k} | {v['complete_pair_count']}; {f(v['complete_pair'])} | {v['determined_correct']}/{v['determined_rows']} "
                 f"| {v['unneeded_obs']}/{v['determined_rows']} | {v['chose_invalid_plan']} | {v['uncertain_obs_correct']}/{v['uncertain_rows']} | {v['invalid']} |")
    L += ["", "## Paired contrasts (group-level, domain-weighted; better/equal/worse groups)", "",
          "| Contrast | estimate [95% CI] | better / equal / worse |", "|---|---|---|"]
    for k, v in res["contrasts"].items():
        L.append(f"| {k} | {f(v)} | {v['better']} / {v['equal']} / {v['worse']} |")
    c = res["C_workflow"]
    L += ["", "## C state-first workflow (C1)", "", f"Sides {c['sides']}; readout valid {c['readout_valid']}, exact "
          f"{c['readout_exact']}, focal correct {c['readout_focal_correct']}, false-unknown fields "
          f"{c['readout_false_unknown_fields']}; step-2 decisions correct {c['decision_correct']}; upstream failures "
          f"{c['upstream_failures']}.", "", "| readout | decision | sides |", "|---|---|---|"]
    for k, v in sorted(c["joint"].items()):
        a, b = k.split("|")
        L.append(f"| {a} | {b} | {v} |")
    L += ["", "## D prerequisite pairs", ""]
    for arm, d in res["actions"].items():
        L += [f"### {arm}", "", "| variant | rows | applicability correct | successor exact | observed world exact | all three | applicable answers |",
              "|---|---|---|---|---|---|---|"]
        for v in ("valid", "invalid", "uncertain"):
            x = d[v]
            L.append(f"| {v} | {x['rows']} | {x['applicable_correct']} | {x['successor_exact']} | {x['observed_exact']} "
                     f"| {x['all_three']} | {x['applicable_answers']} |")
        L += ["", f"Balanced applicability {f(d['balanced_applicability'])}; pair applicability correct "
              f"{f(d['pair_applicability_correct'])}; pair all-three correct {f(d['pair_all_three_correct'])}; "
              f"changed fields on valid {d['valid']['changed_fields_correct']}; invalid replies {d['invalid_replies']}.", ""]
    if res.get("repeats"):
        L += ["## Exact-prompt repeats", ""] + [f"- {r['call_id']}: identical raw = {r['identical_raw']}" for r in res["repeats"]]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
