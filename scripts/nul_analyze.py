"""V1.16.0 analysis: software gates first, then the paired extraction-interface outcomes (descriptive). No model.
Usage: nul_analyze.py --hub HUB --set SET --stage STAGE [--boot 10000] [--seed 20261105]
Primary: NULL_PRIOR minus ORIGINAL in source-aware exact meaning (contract_validate.score_record denotation_equal,
unchanged) over all stock-arrival records (ratio of correct to all, per interface, same records). Interval: resample
worlds within each of the 24 fixed families (family size preserved; all of a world's records, goals, interfaces and
conditions move together), 10,000 resamples, seed 20261105. Downstream utility: DEPENDENCY, goals averaged within
world first, same resampling. Conditional on the 24-family construction."""
import argparse
import collections
import json
import random
import statistics
from pathlib import Path

from _bootstrap import ROOT  # noqa: F401
from tempo import agentstate as AS, depquery as DQ, nullprior as NP, timing as TM

ROLES = ("A", "B")
IF = NP.INTERFACES
CH = ("structured",) + IF


def load(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]


def skey(states):
    return sorted(json.dumps(sorted(s.items())) for s in states)


def fam_boot(worlds, fam, stat, B, seed):
    """stat(list of world ids, possibly repeated) -> value or None. Resample within family."""
    by = collections.defaultdict(list)
    for w in worlds:
        by[fam[w]].append(w)
    rng = random.Random(seed)
    est = []
    for _ in range(B):
        samp = [rng.choice(ws) for ws in by.values() for _ in ws]
        v = stat(samp)
        if v is not None:
            est.append(v)
    if not est:
        return None
    est.sort()
    n = len(est)
    return [round(est[int(0.025 * n)], 4), round(est[min(n - 1, int(0.975 * n))], 4)]


def analyse(hub, set_name, stage, B, sd):
    ev = hub / "stages" / stage / "eval"
    L = lambda n: load(ev / f"{n}.jsonl")
    traj, refs, selc, sels = L("trajectories"), L("reference"), L("selcheck"), L("selections")
    par, poi, leak, ext, chans, feas = L("parity"), L("poison"), L("leakage"), L("extraction"), L("channels"), L("feasibility")
    meta = json.loads((ev / "EVAL-META.json").read_text())
    commit = json.loads((hub / "data" / f"COMMITMENT-{set_name}.json").read_text())
    pubs = {p["world_id"]: p for p in load(hub / "data" / "public" / f"{set_name}-worlds.jsonl")}
    W = sorted(pubs)
    fam = {w: NP.family(w) for w in W}
    dom = {w: pubs[w]["domain"] for w in W}
    k = lambda r: (r["world"], r["role"], r["env"], r["channel"])
    T, RF, S_ = {k(t): t for t in traj}, {k(r): r for r in refs}, {k(s): s for s in sels}
    FE = {(f["world"], f["role"], f["env"]): f for f in feas}
    gates, fails = {}, []

    def gate(name, bad, total):
        gates[name] = {"pass": not bad, "failures": len(bad), "checked": total, "examples": [str(b) for b in bad[:10]]}
        if bad:
            fails.append(name)
    gate("S1 support, classes and choice equal the independent reference given each channel's own evidence",
         [x for x in T if skey(T[x]["states"]) != skey(RF[x]["states"]) or T[x]["candidates"] != RF[x]["classes"]
          or T[x]["plan"] != RF[x]["choice"]], len(T))
    gate("S2 structured: actual in support; no unsupported choice, invalid attempt, false completion or limit",
         [x for x in T if x[3] == "structured" and (not T[x]["actual_in_support"] or T[x]["invalid_attempt"] or
                                                     T[x]["false_completion"] or T[x]["status"] == "limit_exceeded")],
         sum(x[3] == "structured" for x in T))
    bad = [("selector_reference",) + k(c) for c in selc if not c["all_ok"]]
    for x, s in S_.items():
        q0, dep = s["Q0"], s["fields"]["DEPENDENCY"]
        if dep[:len(q0)] != q0 or len(dep) > DQ.CAP or dep[len(q0):] != s["D"][:max(0, DQ.CAP - len(q0))]:
            bad.append(("rule", x))
    gate("S3 frozen selector rule on each channel's evidence; independent selector check", bad, len(S_))
    bad = [("perfect_parity", p["world"], p["role"], p["env"]) for p in par if not (p["q0"] and p["fields"] and p["s2"] and p["trajectory"])]
    bad += [("gold_poison", p["world"], p["role"], p["env"], p["interface"]) for p in poi if not p["ok"]]
    gate("S4 perfect extraction reproduces structured; poisoning gold reports changes no text result (both interfaces)",
         bad, len(par) + len(poi))
    bad = []
    exp = TM.schedule_clock(DQ.SCHEDULE)
    for x, t in T.items():
        if t["clock"] != exp or t["pre_action_wait"] != 4 or t["queried"] != t["fields"]:
            bad.append(("clock_or_fields", x))
        if any(r["measured_at"] != 14 or r["received_at"] != 16 or not r["context"].startswith(f"{x[0]}|{x[1]}|") or
               (x[3] != "structured" and not r["context"].endswith(f"|{x[3]}|DEPENDENCY")) for r in t["receipts"]):
            bad.append(("receipt_time_or_context", x))
        if not (t["history_preserved"] and t["log_unchanged_by_projection"] and t["receipt_absent_before_reception"]):
            bad.append(("history", x))
        if any(AS.violations(pubs[x[0]]["spec"], s) for s in t["states"]):
            bad.append(("inadmissible", x))
        if t["utility_base"] != 10 * t["success"] - t["action_cost"] - 3 * t["invalid_attempt"] - t["queried_facts"]:
            bad.append(("cost_identity", x))
    grp = collections.defaultdict(list)
    for x, t in T.items():
        grp[(x[0], x[2])].append(t)
    for g, ts in grp.items():
        if len({t["actual_preaction_state_sha256"] for t in ts}) != 1:
            bad.append(("preaction_state_differs", g))
        vals = collections.defaultdict(set)
        for t in ts:
            for r in t["receipts"]:
                vals[r["field"]].add(json.dumps(r["value"]))
        if any(len(v) != 1 for v in vals.values()):
            bad.append(("common_field_readings_differ", g))
    for row in leak:
        g2 = collections.defaultdict(set)
        alts = row["by_list"]["DEPENDENCY"]
        for b in alts.values():
            g2[json.dumps(b["readings"])].add((b["states_sha256"], b["plan"]))
        if any(len(v) != 1 for v in g2.values()) or len({json.dumps(b["queried"]) for b in alts.values()}) != 1:
            bad.append(("hidden_tape_leak", row["world"], row["role"], row["channel"]))
    for c in chans:
        if len(c["rows"]) != c["n_reports"]:
            bad.append(("channel_length", c["world"], c["interface"]))
    gate("S5 clock, fees, receipt timing and per-interface context isolation, history, invariants, cost identity, shared "
         "actual state and readings, tape independence, channel lengths", bad, len(T))
    ok_calls = sum(e["call_status"] == "ok" for e in ext)
    res = {"set": set_name, "stage": stage, "worlds": len(W), "eval_meta": meta, "gates": gates,
           "software_gates_pass": not fails, "failed_gates": fails,
           "calls": {"committed": commit["calls"], "records": len(ext), "ok": ok_calls,
                     "complete": ok_calls == commit["calls"] == len(ext)},
           "source_kind_counts": commit["source_kind_counts"]}

    # ------------------------------------------------------------------ extraction (paired by record)
    E = {(e["base_id"], e["interface"]): e for e in ext}
    base = sorted({e["base_id"] for e in ext})
    bw = {b: E[(b, IF[0])]["world"] for b in base}
    kc = {b: E[(b, IF[0])]["kind_class"] for b in base}
    by_world_class = collections.defaultdict(list)
    for b in base:
        by_world_class[(bw[b], kc[b])].append(b)

    def acc(ws, cls, iface, key="denotation_equal"):
        rs = [b for w in ws for b in by_world_class.get((w, cls), [])]
        return (sum(bool(E[(b, iface)][key]) for b in rs), len(rs))

    def ratio_diff(ws, cls="stock_arrival", key="denotation_equal"):
        a, n = acc(ws, cls, IF[0], key)
        c, m = acc(ws, cls, IF[1], key)
        return None if n == 0 else c / m - a / n
    arr = [b for b in base if kc[b] == "stock_arrival"]
    pair = collections.Counter()
    for b in arr:
        o, nn = E[(b, "ORIGINAL")]["denotation_equal"], E[(b, "NULL_PRIOR")]["denotation_equal"]
        pair["both correct" if o and nn else "ORIGINAL only" if o else "NULL_PRIOR only" if nn else "neither"] += 1
    a0, n0 = acc(W, "stock_arrival", "ORIGINAL")
    a1, n1 = acc(W, "stock_arrival", "NULL_PRIOR")
    res["primary"] = {"metric": "stock-arrival exact meaning (denotation_equal), NULL_PRIOR - ORIGINAL",
                      "n_arrival_records": len(arr), "ORIGINAL": [a0, n0], "NULL_PRIOR": [a1, n1],
                      "difference": None if not n0 else round(a1 / n1 - a0 / n0, 4),
                      "ci95": fam_boot(W, fam, lambda ws: ratio_diff(ws), B, sd), "paired": dict(pair),
                      "kind_accuracy": {i: acc(W, "stock_arrival", i, "kind_correct") for i in IF},
                      "kind_accuracy_difference_ci95": fam_boot(W, fam, lambda ws: ratio_diff(ws, key="kind_correct"), B, sd),
                      "per_family_arrivals": {f: {i: acc([w for w in W if fam[w] == f], "stock_arrival", i) for i in IF}
                                              for f in sorted(set(fam.values()))}}
    classes = sorted(set(kc.values()))
    comp = {}
    for cls in classes:
        rs = [b for b in base if kc[b] == cls]
        row = {"n": len(rs)}
        for i in IF:
            es = [E[(b, i)] for b in rs]
            row[i] = {x: sum(bool(e[x]) for e in es) for x in ("denotation_equal", "kind_correct", "field_attribution_ok",
                                                               "result_ok", "meta_ok", "accepted", "mapped")}
            row[i]["prior"] = dict(collections.Counter(e["prior"] for e in es if e.get("prior")))
            row[i]["codes"] = dict(collections.Counter(str(e["code"]) for e in es))
        comp[cls] = row
    res["by_class"] = comp
    res["removal_difference"] = {"value": ratio_diff(W, "stock_removal"), "ci95": fam_boot(W, fam, lambda ws: ratio_diff(ws, "stock_removal"), B, sd)}
    res["wrong_field_records"] = {i: [{"call": e["call_id"], "kind_class": e["kind_class"], "gold": e["fields_gold"],
                                       "got": e["fields_extracted"], "type": e["extracted_type"]}
                                      for e in ext if e["interface"] == i and e["mapped"] and not e["field_attribution_ok"]] for i in IF}
    toks = collections.defaultdict(lambda: [0, 0.0])
    for e in ext:
        toks[e["interface"]][0] += e["output_tokens"] or 0
        toks[e["interface"]][1] += e["seconds"] or 0
    res["runtime"] = {i: {"output_tokens": v[0], "generation_s": round(v[1], 1)} for i, v in toks.items()}
    res["truncated"] = {i: sum(e["stop"] == "length" for e in ext if e["interface"] == i) for i in IF}

    # ------------------------------------------------------------------ downstream (DEPENDENCY)
    U = lambda w, env, ch: sum(T[(w, r, env, ch)]["utility"]["1"] for r in ROLES) / 2

    def contrast(fn, ws=None):
        ws = ws or W
        v = {w: fn(w) for w in ws}
        return {"mean": round(statistics.mean(v.values()), 4),
                "ci95": fam_boot(ws, fam, lambda s: statistics.mean(v[w] for w in s), B, sd),
                "better": sum(x > 0 for x in v.values()), "equal": sum(x == 0 for x in v.values()),
                "worse": sum(x < 0 for x in v.values()), "n_worlds": len(v)}
    con = {}
    for env in ("changing", "stable"):
        con[f"{env}: DEPENDENCY utility NULL_PRIOR - ORIGINAL"] = contrast(lambda w, e=env: U(w, e, "NULL_PRIOR") - U(w, e, "ORIGINAL"))
        for i in IF:
            con[f"{env}: interface loss {i} - structured"] = contrast(lambda w, e=env, i=i: U(w, e, i) - U(w, e, "structured"))
    for d in ("delivery", "assembly"):
        ws = [w for w in W if dom[w] == d]
        con[f"changing: NULL_PRIOR - ORIGINAL, {d}"] = contrast(lambda w: U(w, "changing", "NULL_PRIOR") - U(w, "changing", "ORIGINAL"), ws)
    res["downstream_contrasts"] = con
    cells = {}
    for env in TM.ENVS:
        for ch in CH:
            ts = [(T[(w, r, env, ch)], FE[(w, r, env)]) for w in W for r in ROLES]
            cells[f"{env}|{ch}"] = {"n": len(ts), "U": sum(t["utility"]["1"] for t, _ in ts), "success": sum(t["success"] for t, _ in ts),
                                    "invalid_attempts": sum(t["invalid_attempt"] for t, _ in ts),
                                    "false_completions": sum(t["false_completion"] for t, _ in ts),
                                    "declines": sum(t["outcome_kind"] == "decline" for t, _ in ts),
                                    "fees": sum(t["queried_facts"] for t, _ in ts), "action_cost": sum(t["action_cost"] for t, _ in ts),
                                    "actual_in_support": sum(t["actual_in_support"] for t, _ in ts),
                                    "fully_represented": sum(t["fully_represented"] for t, _ in ts),
                                    "empty_support": sum(t["n_states"] == 0 for t, _ in ts),
                                    "with_pending": sum(bool(t["pending"]) for t, _ in ts),
                                    "with_historical_conflict": sum(bool(t["historical_conflict_fields"]) for t, _ in ts),
                                    "truthful_reading_incompatible": sum(t["n_states"] == 0 and bool(t["receipts"]) for t, _ in ts),
                                    "missed_menu_feasible": sum(t["missed_opportunity"] for t, _ in ts),
                                    "full_domain_feasible": sum(fe["optimum_at_action"] is not None for _, fe in ts)}
    res["cells"] = cells
    res["unsafe_copies"] = {ch: sorted({f"{x[0]}/{x[1]}" for x, t in T.items() if x[3] == ch and (t["invalid_attempt"] or t["false_completion"])})
                            for ch in CH}
    return res


def tables(res):
    p = res["primary"]
    Lx = [f"# V1.16.0 nullable-prior extraction test: {res['set']} / {res['stage']}", "",
          f"Software gates pass: **{res['software_gates_pass']}**. Calls: {res['calls']}.", "", "## Gates", "",
          "| Gate | Pass | Failures / checked |", "|---|---|---|"]
    for kk, g in res["gates"].items():
        Lx.append(f"| {kk} | {'PASS' if g['pass'] else 'FAIL'} | {g['failures']} / {g['checked']} |")
    Lx += ["", "## Primary: stock-arrival exact meaning", "",
           f"- ORIGINAL {p['ORIGINAL'][0]}/{p['ORIGINAL'][1]}; NULL_PRIOR {p['NULL_PRIOR'][0]}/{p['NULL_PRIOR'][1]}; "
           f"difference {p['difference']} {p['ci95']} (family-stratified world bootstrap)",
           f"- paired: {p['paired']}", f"- event-kind accuracy: {p['kind_accuracy']}; difference CI {p['kind_accuracy_difference_ci95']}",
           f"- stock removal difference: {res['removal_difference']}", "", "## By source class", "", "```",
           json.dumps(res["by_class"], indent=1), "```", "", "## Wrong field attribution (mapped records)", "", "```",
           json.dumps(res["wrong_field_records"], indent=1), "```", "", "## Downstream (DEPENDENCY)", "",
           "| Contrast | Mean | 95% | + / = / − |", "|---|---|---|---|"]
    for kk, x in res["downstream_contrasts"].items():
        Lx.append(f"| {kk} | {x['mean']:+.4f} | {x['ci95']} | {x['better']} / {x['equal']} / {x['worse']} |")
    Lx += ["", "```", json.dumps(res["cells"], indent=1), "```", "", f"Unsafe copies: {res['unsafe_copies']}", "",
           f"Runtime: {res['runtime']}; truncated {res['truncated']}"]
    return "\n".join(Lx) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", required=True)
    ap.add_argument("--set", required=True)
    ap.add_argument("--stage", required=True)
    ap.add_argument("--boot", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=20261105)
    a = ap.parse_args()
    hub = Path(a.hub)
    res = analyse(hub, a.set, a.stage, a.boot, a.seed)
    out = hub / "analysis" / a.stage
    out.mkdir(parents=True, exist_ok=True)
    (out / "ANALYSIS.json").write_text(json.dumps(res, indent=1, default=str) + "\n")
    (out / "TABLES.md").write_text(tables(res))
    print(json.dumps({"software_gates_pass": res["software_gates_pass"], "failed": res["failed_gates"],
                      "calls": res["calls"], "primary": {k: res["primary"][k] for k in ("ORIGINAL", "NULL_PRIOR", "difference", "ci95")}}))


if __name__ == "__main__":
    main()
