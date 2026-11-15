"""V1.13.0 analysis: correctness gates per schedule, then development outcomes (descriptive). No model.
Usage: timing_analyze.py --hub HUB --set SET --stage STAGE [--boot 10000] [--seed 20261105]
Unit: the base world (n = 24); contrasts within world and goal, goals averaged within world before any interval."""
import argparse
import collections
import json
import statistics
from pathlib import Path

from _bootstrap import ROOT  # noqa: F401
from tempo import agentstate as AS, timing as TM
from tempo_analyze import bootstrap, domain_weighted

ROLES = ("A", "B")


def load(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]


def skey(states):
    return sorted(json.dumps(sorted(s.items())) for s in states)


def analyse(hub, set_name, stage, B=10000, sd=20261105):
    st = hub / "stages" / stage
    traj, refs = load(st / "trajectories.jsonl"), load(st / "reference.jsonl")
    reqs, leak, feas = load(st / "requests.jsonl"), load(st / "leakage.jsonl"), load(st / "feasibility.jsonl")
    meta = json.loads((st / "RUN-META.json").read_text())
    pubs = {p["world_id"]: p for p in load(hub / "data" / "public" / f"{set_name}-worlds.jsonl")}
    T = {(t["world"], t["role"], t["env"], t["schedule"]): t for t in traj}
    RF = {(r["world"], r["role"], r["env"], r["schedule"]): r for r in refs}
    FE = {(f["world"], f["role"], f["env"]): f for f in feas}
    W = sorted(pubs)
    gdom = {w: pubs[w]["domain"] for w in W}
    gates, fails = {}, []

    def gate(name, bad, total):
        gates[name] = {"pass": not bad, "failures": len(bad), "checked": total, "examples": [str(b) for b in bad[:10]]}
        if bad:
            fails.append(name)
    for s in TM.ORDER:
        ks = [k for k in RF if k[3] == s]
        gate(f"G1[{s}] exact states, classes, choice vs reference",
             [k for k in ks if skey(T[k]["states"]) != skey(RF[k]["states"]) or T[k]["candidates"] != RF[k]["classes"]
              or T[k]["plan"] != RF[k]["choice"]], len(ks))
        gate(f"G2[{s}] actual in support; no unsupported choice, invalid attempt or false completion",
             [k for k in ks if not T[k]["actual_in_support"] or T[k]["invalid_attempt"] or T[k]["false_completion"] or
              (T[k]["plan"] is not None and RF[k]["classes"][T[k]["plan"]] != "guaranteed")], len(ks))
        gate(f"G3[{s}] selects the reference choice whenever one exists",
             [k for k in ks if RF[k]["choice"] is not None and T[k]["plan"] != RF[k]["choice"]],
             sum(RF[k]["choice"] is not None for k in ks))
    bad, n = [], 0
    rq = {(r["world"], r["role"]): r for r in reqs}
    for w in W:
        for role in ROLES:
            for env in TM.ENVS:
                n += 1
                ts = {s: T[(w, role, env, s)] for s in TM.ORDER}
                if len({t["actual_preaction_state_sha256"] for t in ts.values()}) != 1:
                    bad.append(("preaction_state_differs", w, role, env))
                for s, t in ts.items():
                    c = t["clock"]
                    exp = TM.schedule_clock(s)
                    if c != exp or t["projection_clock"]["requested_at"] != TM.ORIGIN:
                        bad.append(("clock", w, role, env, s))
                    if t["queried"] != rq[(w, role)]["fields"]:
                        bad.append(("request_not_cloned", w, role, env, s))
                    if [r["received_at"] - r["measured_at"] for r in t["receipts"]] != [2] * len(t["receipts"]):
                        bad.append(("delivery", w, role, env, s))
                    if not (t["history_preserved"] and t["log_unchanged_by_projection"] and
                            t["receipt_absent_before_reception"]):
                        bad.append(("history", w, role, env, s))
                    if t["refused"] or t["authority_conflicts"] or t["status"] != "ok" and t["n_states"]:
                        bad.append(("refused_or_status", w, role, env, s))
                    if any(AS.violations(pubs[w]["spec"], x) for x in t["states"]):
                        bad.append(("inadmissible", w, role, env, s))
                    for lam in TM.LAMBDAS:
                        if abs(t["utility"][str(lam)] - (t["utility_base"] - lam * t["pre_action_wait"])) > 1e-9:
                            bad.append(("cost", w, role, env, s, lam))
                if len({t["origin_view_sha256"] for t in ts.values()}) != 1:
                    bad.append(("origin_view_differs", w, role, env))
                e, ew, d = ts["EARLY"], ts["EARLY_WAIT"], ts["DEFER"]
                if (e["states_sha256"], e["plan"], e["success"], e["action_cost"], e["queried_facts"]) != \
                        (ew["states_sha256"], ew["plan"], ew["success"], ew["action_cost"], ew["queried_facts"]):
                    bad.append(("EARLY!=EARLY_WAIT", w, role, env))
                for lam in TM.LAMBDAS:
                    if TM.utility(ew, lam) - TM.utility(e, lam) != -2 * lam:
                        bad.append(("EW-E cost identity", w, role, env, lam))
                if env == "stable":
                    if (d["states_sha256"], d["plan"], d["success"], d["action_cost"], d["queried_facts"]) != \
                            (e["states_sha256"], e["plan"], e["success"], e["action_cost"], e["queried_facts"]):
                        bad.append(("stable DEFER!=EARLY", w, role))
                    for lam in TM.LAMBDAS:
                        if TM.utility(d, lam) - TM.utility(ew, lam) != 0 or TM.utility(d, lam) - TM.utility(e, lam) != -2 * lam:
                            bad.append(("stable cost identity", w, role, lam))
    for row in leak:
        for s, alts in row["by_schedule"].items():
            groups = collections.defaultdict(set)
            for name, b in alts.items():
                groups[b["receipts_sha256"]].add(json.dumps({k: b[k] for k in ("states_sha256", "plan", "candidates")},
                                                             sort_keys=True))
            if any(len(v) != 1 for v in groups.values()):
                bad.append(("hidden_tape_leak", row["world"], row["role"], s))
    gate("G4 fixed clock, controls, cost identities, provenance, history, invariants, hidden information", bad, n)
    res = {"set": set_name, "stage": stage, "worlds": len(W), "trajectories": len(traj), "model_calls": 0,
           "run_meta": meta, "gates": gates, "all_gates_pass": not fails, "failed_gates": fails}
    # cells
    cells = {}
    for env in TM.ENVS:
        for s in TM.ORDER:
            for role in ROLES + ("both",):
                ks = [(w, r, env, s) for w in W for r in (ROLES if role == "both" else (role,))]
                rs = [T[k] for k in ks]
                cells[f"{env}|{s}|{role}"] = {
                    "n": len(rs), **{f"U_lambda_{l}": sum(t["utility"][str(l)] for t in rs) for l in TM.LAMBDAS},
                    "U_0_total": sum(t["utility_base"] for t in rs), "success": sum(t["success"] for t in rs),
                    "goal_true_at_boundary": sum(t["goal_true_at_boundary"] for t in rs),
                    "selected_empty_plans": sum(t["empty_plan"] for t in rs),
                    "false_completions": sum(t["false_completion"] for t in rs),
                    "invalid_attempts": sum(t["invalid_attempt"] for t in rs),
                    "unsupported_choices": sum(t["plan"] is not None and RF[k]["classes"][t["plan"]] != "guaranteed"
                                               for k, t in zip(ks, rs)),
                    "declines": sum(t["outcome_kind"] == "decline" for t in rs),
                    "justified_declines": sum(t["outcome_kind"] == "decline" and RF[k]["choice"] is None
                                              for k, t in zip(ks, rs)),
                    "declines_goal_already_true": sum(t["decline_goal_already_true"] for t in rs),
                    "menu_feasible_at_action": sum(t["menu_feasible"] for t in rs),
                    "missed_menu_feasible": sum(t["missed_opportunity"] for t in rs),
                    "full_domain_feasible_at_action": sum(FE[k[:3]]["optimum_at_action"] is not None for k in ks),
                    "queried_facts": sum(t["queried_facts"] for t in rs), "action_cost": sum(t["action_cost"] for t in rs),
                    "waiting": sum(t["pre_action_wait"] for t in rs),
                    "mean_states": round(statistics.mean(t["n_states"] for t in rs), 3),
                    "max_set": max(t["max_set"] for t in rs),
                    "actual_in_support": sum(t["actual_in_support"] for t in rs),
                    "uncertain_queried": sum(len(t["uncertain_queried"]) for t in rs),
                    "uncertain_unqueried": sum(len(t["uncertain_unqueried"]) for t in rs),
                    "max_projection_cpu_s": max(t["cpu_s"] for t in rs)}
    res["cells"] = cells

    def est(gv):
        m = domain_weighted(gv, gdom)
        return {"mean": None if m is None else round(m, 4), "ci95": bootstrap(gv, gdom, B, sd)}

    def contrast(fn):
        dd = {w: fn(w) for w in W}
        x = est(dd)
        x.update(better=sum(v > 0 for v in dd.values()), equal=sum(v == 0 for v in dd.values()),
                 worse=sum(v < 0 for v in dd.values()), per_world=dd)
        return x
    U = lambda w, env, s, lam: sum(T[(w, r, env, s)]["utility"][str(lam)] for r in ROLES) / 2
    C = {"PRIMARY changing DEFER - EARLY (lambda 1)": contrast(lambda w: U(w, "changing", "DEFER", 1) - U(w, "changing", "EARLY", 1)),
         "MECHANISM changing DEFER - EARLY_WAIT (lambda 1)": contrast(
             lambda w: U(w, "changing", "DEFER", 1) - U(w, "changing", "EARLY_WAIT", 1))}
    for role in ROLES:
        C[f"changing DEFER - EARLY, goal {role} (lambda 1)"] = contrast(
            lambda w, r=role: T[(w, r, "changing", "DEFER")]["utility"]["1"] - T[(w, r, "changing", "EARLY")]["utility"]["1"])
    C["control changing EARLY_WAIT - EARLY (lambda 1; expected -2)"] = contrast(
        lambda w: U(w, "changing", "EARLY_WAIT", 1) - U(w, "changing", "EARLY", 1))
    C["control stable DEFER - EARLY_WAIT (lambda 1; expected 0)"] = contrast(
        lambda w: U(w, "stable", "DEFER", 1) - U(w, "stable", "EARLY_WAIT", 1))
    C["control stable DEFER - EARLY (lambda 1; expected -2)"] = contrast(
        lambda w: U(w, "stable", "DEFER", 1) - U(w, "stable", "EARLY", 1))
    res["contrasts"] = C
    sens = {}
    for lam in TM.LAMBDAS:
        sens[str(lam)] = {"changing DEFER - EARLY": contrast(lambda w, l=lam: U(w, "changing", "DEFER", l) - U(w, "changing", "EARLY", l)),
                          "changing DEFER - EARLY_WAIT": contrast(lambda w, l=lam: U(w, "changing", "DEFER", l) - U(w, "changing", "EARLY_WAIT", l))}
    res["lambda_sensitivity"] = {l: {k: {kk: v[kk] for kk in ("mean", "ci95", "better", "equal", "worse")}
                                     for k, v in x.items()} for l, x in sens.items()}
    d0 = {w: U(w, "changing", "DEFER", 0) - U(w, "changing", "EARLY", 0) for w in W}
    be = {w: (v / 2 if v > 0 else ("tie only at 0" if v == 0 else "none (DeltaU0 < 0)")) for w, v in d0.items()}
    panel = domain_weighted(d0, gdom)
    res["break_even"] = {"per_world_DeltaU0": d0, "per_world_lambda_star": be, "panel_mean_DeltaU0": round(panel, 4),
                         "panel_lambda_star": round(panel / 2, 4),
                         "per_goal_copy": {f"{w}|{r}": (T[(w, r, "changing", "DEFER")]["utility_base"] -
                                                        T[(w, r, "changing", "EARLY")]["utility_base"]) / 2
                                           for w in W for r in ROLES},
                         "note": "Delta U_lambda = Delta U_0 - 2 lambda; panel value is for this designed allocation only"}
    # diagnostics (changing)
    diag = collections.defaultdict(list)
    for w in W:
        for r in ROLES:
            e, ew, d = (T[(w, r, "changing", s)] for s in TM.ORDER)
            k = f"{w}|{r}"
            if d["success"] and not ew["success"]:
                diag["DEFER_succeeds_where_EARLY_WAIT_does_not"].append(k)
            if ew["success"] and not d["success"]:
                diag["EARLIER_measurement_more_useful (EARLY_WAIT succeeds, DEFER not)"].append(k)
            if d["n_states"] > ew["n_states"]:
                diag["DEFER_support_larger_than_EARLY_WAIT"].append(k)
            if d["outcome_kind"] == "decline":
                why = "unqueried prerequisite uncertain" if d["uncertain_unqueried"] else \
                    "queried prerequisite uncertain" if d["uncertain_queried"] else "no menu candidate valid in support"
                diag[f"DEFER residual decline: {why}"].append(k)
            if any(f not in d["queried"] and d["relevant_support"][f] not in ("unknown", "conflict_or_absent") and
                   e["relevant_support"][f] == "unknown" for f in d["relevant"]):
                diag["unqueried prerequisite resolved indirectly by the late reading"].append(k)
            if d["candidate_gain"]:
                diag["candidate_gain (vs t=0)"].append(k)
            if d["candidate_loss"]:
                diag["candidate_loss (vs t=0)"].append(k)
            if d["menu_feasible"] and not d["menu_feasible_at_origin"]:
                diag["newly_menu_feasible"].append(k)
            if d["menu_feasible_at_origin"] and not d["menu_feasible"]:
                diag["newly_menu_infeasible"].append(k)
            fe = FE[(w, r, "changing")]
            if fe["optimum_at_action"] is not None and not d["menu_feasible"]:
                diag["full_domain_feasible_but_no_menu_candidate"].append(k)
            if d["empty_plan"]:
                diag["DEFER selected empty plan (already)"].append(k)
    res["diagnostics_changing"] = {k: {"count": len(v), "items": v} for k, v in sorted(diag.items())}
    dis = []
    for env in TM.ENVS:
        for w in W:
            for r in ROLES:
                ts = {s: T[(w, r, env, s)] for s in TM.ORDER}
                if len({(t["plan"], t["success"]) for t in ts.values()}) > 1:
                    dis.append({"world": w, "role": r, "env": env, "label": ts["DEFER"]["label"],
                                "events": ts["DEFER"]["applied_events"],
                                "timeline": {s: {"measure": t["clock"]["measured_at"], "receive": t["clock"]["received_at"],
                                                 "act": t["clock"]["execute_at"],
                                                 "reading": [(x["field"], x["value"]) for x in t["receipts"]],
                                                 "n_states": t["n_states"], "plan": t["plan"], "kind": t["outcome_kind"],
                                                 "success": t["success"], "U1": t["utility"]["1"]}
                                             for s, t in ts.items()}})
    res["schedule_disagreements"] = dis
    res["requests"] = {"fields_per_goal": dict(collections.Counter(len(r["fields"]) for r in reqs))}
    return res


def tables(res):
    L = [f"# V1.13.0 query timing: {res['set']} / {res['stage']}", "",
         f"Worlds {res['worlds']}, trajectories {res['trajectories']}, model calls 0; run wall "
         f"{res['run_meta']['wall_s']:.1f} s; max reachable set {res['run_meta']['max_reachable_set']}; max projection "
         f"CPU {res['run_meta']['max_projection_cpu_s']:.4f} s.", "", "## Correctness gates", "",
         "| Gate | Pass | Failures / checked |", "|---|---|---|"]
    for k, g in res["gates"].items():
        L.append(f"| {k} | {'yes' if g['pass'] else '**NO**'} | {g['failures']} / {g['checked']} |")
    L += ["", f"All gates pass: **{res['all_gates_pass']}**", "",
          f"## Cells (both goals, {2 * res['worlds']} goal copies each)", "",
          "| Env | Schedule | U λ=0 | U λ=1 | Success | Goal true | Empty plans | False compl. | Invalid | Declines (justified) |"
          " Missed menu-feasible | Menu / full-domain feasible | Queried | Wait | Mean states | Uncertain q / unq | Actual in support |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for k, c in res["cells"].items():
        env, s, role = k.split("|")
        if role == "both":
            L.append(f"| {env} | {s} | {c['U_lambda_0']} | {c['U_lambda_1']} | {c['success']} | {c['goal_true_at_boundary']} | "
                     f"{c['selected_empty_plans']} | {c['false_completions']} | {c['invalid_attempts']} | {c['declines']} "
                     f"({c['justified_declines']}) | {c['missed_menu_feasible']} | {c['menu_feasible_at_action']} / "
                     f"{c['full_domain_feasible_at_action']} | {c['queried_facts']} | {c['waiting']} | {c['mean_states']} | "
                     f"{c['uncertain_queried']} / {c['uncertain_unqueried']} | {c['actual_in_support']}/{c['n']} |")
    L += ["", "## Contrasts (per world, goals averaged; domain-stratified bootstrap, n = 24 worlds; descriptive)", "",
          "| Contrast | Mean [95%] | Better / equal / worse |", "|---|---|---|"]
    for k, c in res["contrasts"].items():
        L.append(f"| {k} | {c['mean']} {c['ci95']} | {c['better']} / {c['equal']} / {c['worse']} |")
    L += ["", "## Waiting-price sensitivity (same trajectories, analytic)", "",
          "| λ | DEFER − EARLY | DEFER − EARLY_WAIT |", "|---|---|---|"]
    for l, x in res["lambda_sensitivity"].items():
        a, b = x["changing DEFER - EARLY"], x["changing DEFER - EARLY_WAIT"]
        L.append(f"| {l} | {a['mean']} {a['ci95']} ({a['better']}/{a['equal']}/{a['worse']}) | {b['mean']} {b['ci95']} "
                 f"({b['better']}/{b['equal']}/{b['worse']}) |")
    be = res["break_even"]
    L += ["", f"## Break-even (changing, DEFER − EARLY): panel ΔU₀ = {be['panel_mean_DeltaU0']}, λ* = {be['panel_lambda_star']}",
          "", "| World | ΔU₀ (goals averaged) | λ* |", "|---|---|---|"]
    for w, v in be["per_world_DeltaU0"].items():
        L.append(f"| {w} | {v} | {be['per_world_lambda_star'][w]} |")
    L += ["", "## Diagnostics (changing)", ""]
    for k, v in res["diagnostics_changing"].items():
        L.append(f"- {k}: {v['count']} ({', '.join(v['items'])})")
    L += ["", f"## Schedule disagreements with timelines ({len(res['schedule_disagreements'])})", ""]
    for x in res["schedule_disagreements"]:
        tl = "; ".join(f"{s} m{v['measure']}/r{v['receive']}/a{v['act']} read {v['reading']} → {v['n_states']} st, "
                       f"{v['plan']} ({v['kind']}, {'ok' if v['success'] else 'fail'}, U1 {v['U1']})"
                       for s, v in x["timeline"].items())
        L.append(f"- {x['world']}/{x['role']} {x['env']} [{x['label']}], events "
                 f"{[(e['transition'], e['at']) for e in x['events']] or 'none'}: {tl}")
    return "\n".join(L) + "\n"


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
    print(json.dumps({"all_gates_pass": res["all_gates_pass"], "failed": res["failed_gates"],
                      "primary": {k: v for k, v in res["contrasts"]["PRIMARY changing DEFER - EARLY (lambda 1)"].items()
                                  if k != "per_world"}}))


if __name__ == "__main__":
    main()
