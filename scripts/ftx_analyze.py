"""V1.15.0 analysis: software/readiness gates first, then measured end-to-end outcomes (descriptive). No model.
Usage: ftx_analyze.py --hub HUB --set SET --stage STAGE [--boot 10000] [--seed 20261105]
Unit: the base world (n = 24); pairs within world, goals averaged within world before any interval."""
import argparse
import collections
import json
import statistics
from pathlib import Path

from _bootstrap import ROOT  # noqa: F401
from tempo import agentstate as AS, depquery as DQ, textdep as TD, timing as TM
from tempo_analyze import bootstrap, domain_weighted

ROLES = ("A", "B")
CH = TD.CHANNELS
SEL = TD.SELECTORS


def load(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]


def skey(states):
    return sorted(json.dumps(sorted(s.items())) for s in states)


def decline_reason(t, fe):
    if t["outcome_kind"] != "decline":
        return None
    if t["status"] in ("empty_support", "limit_exceeded", "out_of_scope_later_report"):
        return f"no support ({t['status']})"
    if fe["optimum_at_action"] is None:
        return "full_domain_infeasible"
    if not t["menu_feasible"]:
        return "menu_gap"
    return "information_insufficient" + (" (unqueried uncertain)" if t["uncertain_unqueried"] else
                                         " (queried still uncertain)" if t["uncertain_queried"] else
                                         " (no candidate guaranteed in parsed support)")


def analyse(hub, set_name, stage, B=10000, sd=20261105):
    ev = hub / "stages" / stage / "eval"
    L = lambda n: load(ev / f"{n}.jsonl")
    traj, refs, selc, sels = L("trajectories"), L("reference"), L("selcheck"), L("selections")
    par, poi, leak, feas, ext, chans = L("parity"), L("poison"), L("leakage"), L("feasibility"), L("extraction"), L("channels")
    meta = json.loads((ev / "EVAL-META.json").read_text())
    pubs = {p["world_id"]: p for p in load(hub / "data" / "public" / f"{set_name}-worlds.jsonl")}
    commit = json.loads((hub / "data" / f"COMMITMENT-{set_name}.json").read_text())
    W = sorted(pubs)
    gdom = {w: pubs[w]["domain"] for w in W}
    k = lambda r: (r["world"], r["role"], r["env"], r["channel"], r["selector"])
    T = {k(t): t for t in traj}
    RF = {k(r): r for r in refs}
    S_ = {(s["world"], s["role"], s["env"], s["channel"]): s for s in sels}
    FE = {(f["world"], f["role"], f["env"]): f for f in feas}
    gates, fails = {}, []

    def gate(name, bad, total):
        gates[name] = {"pass": not bad, "failures": len(bad), "checked": total, "examples": [str(b) for b in bad[:10]]}
        if bad:
            fails.append(name)
    gate("S1 support, candidate classes and choice equal the independent reference given the same evidence (both channels)",
         [x for x in T if skey(T[x]["states"]) != skey(RF[x]["states"]) or T[x]["candidates"] != RF[x]["classes"]
          or T[x]["plan"] != RF[x]["choice"]], len(T))
    gate("S2 structured channel: actual state in support; no unsupported choice, invalid attempt or false completion",
         [x for x in T if x[3] == "structured" and (not T[x]["actual_in_support"] or T[x]["invalid_attempt"] or
                                                     T[x]["false_completion"] or T[x]["status"] == "limit_exceeded")],
         sum(x[3] == "structured" for x in T))
    bad = [("selector_reference", c["world"], c["role"], c["env"], c["channel"]) for c in selc if not c["all_ok"]]
    for x, s in S_.items():
        q0, dep = s["Q0"], s["fields"]["DEPENDENCY"]
        if s["fields"]["BASE"] != q0 or dep[:len(q0)] != q0 or len(dep) > DQ.CAP or \
                dep[len(q0):] != s["D"][:max(0, DQ.CAP - len(q0))]:
            bad.append(("rule", x))
        if x[3] == "structured" and x[2] == "stable" and s["e"]:
            bad.append(("structured_stable_augmentation", x))
    gate("S3 frozen selector rule on each channel's evidence (Q0 preserved, cap 2, registry order), matches the independent check",
         bad, len(S_))
    bad = [("perfect_parity", p["world"], p["role"], p["env"]) for p in par
           if not (p["q0"] and p["fields"] and p["s2"] and all(all(v.values()) for v in p["trajectories"].values()))]
    bad += [("gold_poison_changed_text", p["world"], p["role"], p["env"]) for p in poi
            if not (p["q0"] and p["fields"] and all(p["trajectories"].values()))]
    gate("S4 perfect extraction reproduces structured; poisoning the gold reports does not change any text result",
         bad, len(par) + len(poi))
    bad = []
    exp = TM.schedule_clock(DQ.SCHEDULE)
    for x, t in T.items():
        if t["clock"] != exp or t["pre_action_wait"] != 4 or t["queried"] != t["fields"] or len(t["fields"]) > DQ.CAP:
            bad.append(("clock_or_fields", x))
        if any(r["measured_at"] != 14 or r["received_at"] != 16 or not r["context"].startswith(f"{x[0]}|{x[1]}|")
               for r in t["receipts"]):
            bad.append(("receipt_time_or_context", x))
        if not (t["history_preserved"] and t["log_unchanged_by_projection"] and t["receipt_absent_before_reception"]):
            bad.append(("history", x))
        if any(AS.violations(pubs[x[0]]["spec"], s) for s in t["states"]):
            bad.append(("inadmissible", x))
        if abs(t["utility"]["1"] - (t["utility_base"] - 4)) > 1e-9 or \
                t["utility_base"] != 10 * t["success"] - t["action_cost"] - 3 * t["invalid_attempt"] - t["queried_facts"]:
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
        for s, alts in row["by_list"].items():
            g2 = collections.defaultdict(set)
            for b in alts.values():
                g2[json.dumps(b["readings"])].add((b["states_sha256"], b["plan"]))
            if any(len(v) != 1 for v in g2.values()) or len({json.dumps(b["queried"]) for b in alts.values()}) != 1:
                bad.append(("hidden_tape_leak", row["world"], row["role"], row["channel"], s))
    for c in chans:
        if len(c["rows"]) != c["n_reports"] or [r["k"] for r in c["rows"]] != list(range(1, c["n_reports"] + 1)):
            bad.append(("channel_length", c["world"]))
    gate("S5 clock, fees, receipt timing and context isolation, history, invariants, cost identity, shared actual state and "
         "readings, hidden-tape independence, channel lengths", bad, len(T))
    n_calls = commit["calls"]
    ok_calls = sum(e["call_status"] == "ok" for e in ext)
    complete = ok_calls == n_calls and len(ext) == n_calls
    res = {"set": set_name, "stage": stage, "worlds": len(W), "eval_meta": meta, "gates": gates,
           "software_gates_pass": not fails, "failed_gates": fails,
           "calls": {"committed": n_calls, "records": len(ext), "ok": ok_calls, "complete": complete,
                     "missing_or_failed": [e["call_id"] for e in ext if e["call_status"] != "ok"]}}

    # ------------------------------------------------------------------ outcomes
    U = lambda w, env, ch, s: sum(T[(w, r, env, ch, s)]["utility"]["1"] for r in ROLES) / 2

    def est(dd):
        m = domain_weighted(dd, gdom)
        return {"mean": None if m is None else round(m, 4), "ci95": bootstrap(dd, gdom, B, sd)}

    def contrast(fn, ws=None):
        ws = ws or W
        dd = {w: round(fn(w), 6) for w in ws}
        x = est(dd) if ws == W else {"mean": round(statistics.mean(dd.values()), 4), "ci95": bootstrap(dd, gdom, B, sd)}
        x.update(better=sum(v > 0 for v in dd.values()), equal=sum(v == 0 for v in dd.values()),
                 worse=sum(v < 0 for v in dd.values()), per_world=dd)
        return x
    con = {}
    for env in ("changing", "stable"):
        pre = "PRIMARY " if env == "changing" else ""
        con[f"{pre}{env}: text DEPENDENCY - BASE"] = contrast(lambda w, e=env: U(w, e, "text", "DEPENDENCY") - U(w, e, "text", "BASE"))
        con[f"{env}: structured DEPENDENCY - BASE"] = contrast(lambda w, e=env: U(w, e, "structured", "DEPENDENCY") - U(w, e, "structured", "BASE"))
        for s in SEL:
            con[f"{env}: interface loss text - structured, {s}"] = contrast(lambda w, e=env, s=s: U(w, e, "text", s) - U(w, e, "structured", s))
        con[f"{env}: change in augmentation benefit (text - structured)"] = contrast(
            lambda w, e=env: (U(w, e, "text", "DEPENDENCY") - U(w, e, "text", "BASE")) -
            (U(w, e, "structured", "DEPENDENCY") - U(w, e, "structured", "BASE")))
    for role in ROLES:
        con[f"changing: text DEPENDENCY - BASE, goal {role}"] = contrast(
            lambda w, r=role: T[(w, r, "changing", "text", "DEPENDENCY")]["utility"]["1"] - T[(w, r, "changing", "text", "BASE")]["utility"]["1"])
    for dom in ("delivery", "assembly"):
        dw = [w for w in W if gdom[w] == dom]
        for ch in CH:
            con[f"changing: {ch} DEPENDENCY - BASE, {dom} only"] = contrast(
                lambda w, c=ch: U(w, "changing", c, "DEPENDENCY") - U(w, "changing", c, "BASE"), dw)
        con[f"changing: change in augmentation benefit, {dom} only"] = contrast(
            lambda w: (U(w, "changing", "text", "DEPENDENCY") - U(w, "changing", "text", "BASE")) -
            (U(w, "changing", "structured", "DEPENDENCY") - U(w, "changing", "structured", "BASE")), dw)
    res["contrasts"] = con
    cells = {}
    for env in TM.ENVS:
        for ch in CH:
            for s in SEL:
                rs = [(T[(w, r, env, ch, s)], FE[(w, r, env)]) for w in W for r in ROLES]
                c = collections.Counter()
                for t, fe in rs:
                    c["U"] += t["utility"]["1"]; c["success"] += t["success"]; c["goal_true_at_boundary"] += t["goal_true_at_boundary"]
                    c["selected_empty_plans"] += t["empty_plan"]; c["false_completions"] += t["false_completion"]
                    c["invalid_attempts"] += t["invalid_attempt"]; c["declines"] += t["outcome_kind"] == "decline"
                    c["missed_menu_feasible"] += t["missed_opportunity"]; c["menu_feasible_at_action"] += t["menu_feasible"]
                    c["full_domain_feasible"] += fe["optimum_at_action"] is not None
                    c["fees"] += t["queried_facts"]; c["waiting"] += t["pre_action_wait"]; c["action_cost"] += t["action_cost"]
                    c["actual_in_support"] += t["actual_in_support"]; c["fully_represented"] += t["fully_represented"]
                    c["empty_support"] += t["n_states"] == 0; c["with_pending"] += bool(t["pending"])
                    c["with_historical_conflict"] += bool(t["historical_conflict_fields"])
                    c["limit_exceeded"] += t["status"] == "limit_exceeded"
                    c["decline_goal_already_true"] += t["decline_goal_already_true"]
                    dr = decline_reason(t, fe)
                    if dr:
                        c[f"decline: {dr}"] += 1
                cells[f"{env}|{ch}|{s}"] = dict(c, n=len(rs))
    res["cells"] = cells

    # agreement and traces (text vs structured, same world/goal/env/selector)
    gx = {e["call_id"]: e for e in ext}
    agree = collections.Counter()
    traces = []
    for w in W:
        for r in ROLES:
            for env in TM.ENVS:
                ss, st = S_[(w, r, env, "structured")], S_[(w, r, env, "text")]
                for s in SEL:
                    a, b = T[(w, r, env, "structured", s)], T[(w, r, env, "text", s)]
                    same = {"Q0": ss["Q0"] == st["Q0"], "S2": skey(ss["s2_states"]) == skey(st["s2_states"]),
                            "fields": a["fields"] == b["fields"], "support": a["states_sha256"] == b["states_sha256"],
                            "plan": a["plan"] == b["plan"], "outcome": (a["outcome_kind"], a["success"]) == (b["outcome_kind"], b["success"]),
                            "utility": a["utility"]["1"] == b["utility"]["1"]}
                    for kk, v in same.items():
                        agree[f"{env}|{s}|{kk}"] += v
                    agree[f"{env}|{s}|n"] += 1
                    if not all(same.values()):
                        rel = set(a["relevant"])
                        errs = [e for e in ext if e["world"] == w and not e["denotation_equal"]]
                        traces.append({"copy": f"{w}/{r}", "env": env, "selector": s, "same": same,
                                       "first_divergence": next((kk for kk in ("Q0", "S2", "fields", "support", "plan", "outcome", "utility")
                                                                 if not same[kk]), None),
                                       "structured": brief(a, FE[(w, r, env)]), "text": brief(b, FE[(w, r, env)]),
                                       "text_Q0": st["Q0"], "struct_Q0": ss["Q0"], "text_D": st["D"], "struct_D": ss["D"],
                                       "text_s2_size": len(st["s2_states"]), "struct_s2_size": len(ss["s2_states"]),
                                       "world_extraction_errors": [{"call": e["call_id"], "k": e["k"], "gold_kind": e["gold_kind"],
                                                                    "accepted": e["accepted"], "code": e["code"],
                                                                    "coverage": round(e["coverage"], 3), "status_wrong": e["status_wrong"]}
                                                                   for e in errs],
                                       "utility_delta_text_minus_structured": b["utility"]["1"] - a["utility"]["1"]})
    res["agreement"] = dict(agree)
    res["divergence_traces"] = traces
    # query effects per channel (changing)
    qe = {}
    for ch in CH:
        c = collections.Counter()
        lists = collections.defaultdict(list)
        for w in W:
            for r in ROLES:
                b, d = T[(w, r, "changing", ch, "BASE")], T[(w, r, "changing", ch, "DEPENDENCY")]
                e = len(d["fields"]) - len(b["fields"])
                if not e:
                    continue
                c["augmented_copies"] += 1; c["added_facts"] += e
                du = d["utility"]["1"] - b["utility"]["1"]
                if d["success"] and not b["success"]:
                    key = "success gain"
                elif b["success"] and not d["success"]:
                    key = "success loss"
                elif d["plan"] != b["plan"] or d["action_cost"] != b["action_cost"]:
                    key = "same success, plan/cost change"
                else:
                    key = "no decision change"
                c[f"{key}: copies"] += 1; c[f"{key}: added facts"] += e
                if du < 0:
                    c["lower utility than BASE: copies"] += 1
                    lists["lower utility than BASE"].append(f"{w}/{r}")
                lists[key].append(f"{w}/{r}")
        qe[ch] = {"counts": dict(c), "copies": {kk: sorted(v) for kk, v in lists.items()}}
    res["query_effects_changing"] = qe
    # extraction audit
    ea = collections.Counter()
    by_kind = collections.defaultdict(collections.Counter)
    for e in ext:
        for kk in ("parsed", "mapped", "accepted", "denotation_equal", "type_class_equal", "status_wrong"):
            ea[kk] += bool(e[kk]); by_kind[e["gold_kind"]][kk] += bool(e[kk])
        ea["n"] += 1; by_kind[e["gold_kind"]]["n"] += 1
        ea[f"code:{e['code']}"] += 1
        ea["spurious_atoms"] += e["spurious"]
    ea["mean_coverage"] = round(statistics.mean(e["coverage"] for e in ext), 4) if ext else None
    tok_out = [e["output_tokens"] for e in ext if e["output_tokens"] is not None]
    secs = [e["seconds"] for e in ext if e["seconds"] is not None]
    res["extraction"] = {"overall": dict(ea), "by_gold_kind": {kk: dict(v) for kk, v in by_kind.items()},
                         "truncated": sum(e["stop"] == "length" for e in ext),
                         "output_tokens_total": sum(tok_out), "generation_seconds_total": round(sum(secs), 1),
                         "per_world_accepted": {w: sum(e["accepted"] for e in ext if e["world"] == w) for w in W},
                         "per_world_reports": {w: sum(e["world"] == w for e in ext) for w in W}}
    return res


def brief(t, fe):
    return {"Q_fields": t["fields"], "plan": t["plan"], "outcome": t["outcome_kind"], "success": t["success"],
            "U": t["utility"]["1"], "n_states": t["n_states"], "status": t["status"], "actual_in_support": t["actual_in_support"],
            "fully_represented": t["fully_represented"], "pending": t["pending"], "invalid": t["invalid_attempt"],
            "false_completion": t["false_completion"], "decline_reason": decline_reason(t, fe)}


def fmt(x):
    ci = "—" if x["ci95"] is None else f"[{x['ci95'][0]:+.2f}, {x['ci95'][1]:+.2f}]"
    return f"{x['mean']:+.4f} | {ci} | {x['better']} / {x['equal']} / {x['worse']}"


def tables(res):
    Lx = [f"# V1.15.0 frozen-text integration: {res['set']} / {res['stage']}", "",
          f"Software gates pass: **{res['software_gates_pass']}**. Calls: {res['calls']}.", "",
          "## Software / readiness gates", "", "| Gate | Pass | Failures / checked |", "|---|---|---|"]
    for kk, g in res["gates"].items():
        Lx.append(f"| {kk} | {'PASS' if g['pass'] else 'FAIL'} | {g['failures']} / {g['checked']} |")
    Lx += ["", "## Contrasts (λ = 1; mean over goals within world; descriptive domain-stratified bootstrap)", "",
           "| Contrast | Mean | 95% interval | better / equal / worse |", "|---|---|---|---|"]
    for kk, x in res["contrasts"].items():
        Lx.append(f"| {kk} | {fmt(x)} |")
    keys = ["U", "success", "goal_true_at_boundary", "selected_empty_plans", "false_completions", "invalid_attempts", "declines",
            "missed_menu_feasible", "menu_feasible_at_action", "full_domain_feasible", "fees", "waiting", "action_cost",
            "actual_in_support", "fully_represented", "empty_support", "with_pending", "with_historical_conflict", "limit_exceeded"]
    Lx += ["", "## Cells (sums over 48 goal copies)", "", "| cell | " + " | ".join(keys) + " |", "|---|" + "---|" * len(keys)]
    for kk, c in res["cells"].items():
        Lx.append(f"| {kk} | " + " | ".join(str(c.get(x, 0)) for x in keys) + " |")
    Lx += ["", "### Decline reasons", ""]
    for kk, c in res["cells"].items():
        d = {x: v for x, v in c.items() if x.startswith("decline:")}
        if d:
            Lx.append(f"- {kk}: " + "; ".join(f"{x[9:]} {v}" for x, v in sorted(d.items())))
    Lx += ["", "## Query effects (changing; DEPENDENCY vs BASE within channel)", ""]
    for ch, q in res["query_effects_changing"].items():
        Lx.append(f"- **{ch}**: {q['counts']}")
        for kk, v in q["copies"].items():
            Lx.append(f"  - {kk}: {', '.join(v)}")
    Lx += ["", "## Text vs structured agreement (counts of equal pairs)", "", "```", json.dumps(res["agreement"], indent=0), "```",
           "", f"## Divergence traces ({len(res['divergence_traces'])})", ""]
    for t in res["divergence_traces"]:
        Lx.append(f"- {t['copy']} {t['env']} {t['selector']}: first divergence **{t['first_divergence']}**; "
                  f"structured {t['structured']['plan']}/{t['structured']['outcome']} U={t['structured']['U']} "
                  f"Q={t['structured']['Q_fields']} → text {t['text']['plan']}/{t['text']['outcome']} U={t['text']['U']} "
                  f"Q={t['text']['Q_fields']} (status {t['text']['status']}, |S|={t['text']['n_states']}, actual in support "
                  f"{t['text']['actual_in_support']}, pending {t['text']['pending']}, decline {t['text']['decline_reason']})")
    Lx += ["", "## Extraction audit (deterministic scorer)", "", "```", json.dumps(res["extraction"], indent=1), "```"]
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
    p = res["contrasts"]["PRIMARY changing: text DEPENDENCY - BASE"]
    print(json.dumps({"software_gates_pass": res["software_gates_pass"], "failed": res["failed_gates"],
                      "calls": {k: res["calls"][k] for k in ("committed", "ok", "complete")},
                      "primary": {k: p[k] for k in ("mean", "ci95")}}))


if __name__ == "__main__":
    main()
