"""V1.14.0 analysis: correctness gates first, then development outcomes (descriptive). No model.
Usage: depq_analyze.py --hub HUB --set SET --stage STAGE [--boot 10000] [--seed 20261105]
Unit: the base world (n = 24). RANDOM_EXTRA subsets are averaged with their exact weights within world/goal/
environment first; goals are then averaged within world; only then is any interval computed."""
import argparse
import collections
import json
import math
import statistics
from pathlib import Path

from _bootstrap import ROOT  # noqa: F401
from tempo import agentstate as AS, depquery as DQ, timing as TM
from tempo_analyze import bootstrap, domain_weighted

ROLES = ("A", "B")


def load(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]


def skey(states):
    return sorted(json.dumps(sorted(s.items())) for s in states)


def analyse(hub, set_name, stage, B=10000, sd=20261105):
    st = hub / "stages" / stage
    sels, chk = load(st / "selections.jsonl"), load(st / "selcheck.jsonl")
    traj, refs = load(st / "trajectories.jsonl"), load(st / "reference.jsonl")
    feas, leak = load(st / "feasibility.jsonl"), load(st / "leakage.jsonl")
    meta = json.loads((st / "RUN-META.json").read_text())
    pubs = {p["world_id"]: p for p in load(hub / "data" / "public" / f"{set_name}-worlds.jsonl")}
    W = sorted(pubs)
    gdom = {w: pubs[w]["domain"] for w in W}
    k4 = lambda r: (r["world"], r["role"], r["env"])
    SEL = {k4(s): s for s in sels}
    CHK = {k4(c): c for c in chk}
    FE = {k4(f): f for f in feas}
    T, RF = {}, {}
    for t in traj:
        T[k4(t) + (t["arm"], t["subset"])] = t
    for r in refs:
        RF[k4(r) + (r["arm"], r["subset"])] = r
    gates, fails = {}, []

    def gate(name, bad, total):
        gates[name] = {"pass": not bad, "failures": len(bad), "checked": total, "examples": [str(b) for b in bad[:10]]}
        if bad:
            fails.append(name)
    ks = list(T)
    gate("G1 every arm and random subset: exact support, candidate classes and choice vs independent reference",
         [k for k in ks if skey(T[k]["states"]) != skey(RF[k]["states"]) or T[k]["candidates"] != RF[k]["classes"]
          or T[k]["plan"] != RF[k]["choice"]], len(ks))
    gate("G2 actual state in support; no unsupported choice, invalid attempt or false completion",
         [k for k in ks if not T[k]["actual_in_support"] or T[k]["invalid_attempt"] or T[k]["false_completion"] or
          (T[k]["plan"] is not None and RF[k]["classes"][T[k]["plan"]] != "guaranteed")], len(ks))
    bad = []
    for k in ks:
        t, rf = T[k], RF[k]
        if rf["choice"] is not None and t["plan"] != rf["choice"]:
            bad.append(("not_cheapest_guaranteed", k))
        if t["outcome_kind"] == "decline" and FE[k[:3]]["optimum_at_action"] is not None and \
                decline_reason(t, FE[k[:3]]) == "full_domain_infeasible":
            bad.append(("menu_gap_labelled_infeasible", k))
    gate("G3 cheapest guaranteed candidate whenever one exists; menu gaps not labelled infeasible", bad, len(ks))
    bad = []
    for kk, s in SEL.items():
        c = CHK[kk]
        if not c["all_ok"]:
            bad.append(("independent_selector_check", kk, [x for x, v in c["ok"].items() if not v]))
        q0 = s["Q0"]
        dep = s["fields"]["DEPENDENCY"]
        if s["fields"]["BASE"] != q0 or dep[:len(q0)] != q0 or len(dep) > DQ.CAP:
            bad.append(("Q0_or_cap", kk))
        if dep[len(q0):] != s["D"][:max(0, DQ.CAP - len(q0))]:
            bad.append(("dependency_rule", kk))
        if any(f not in s["registry"] for f in dep):
            bad.append(("unregistered_field", kk))
        if s["e"]:
            subs = s["random_subsets"]
            if len(subs) != math.comb(len(s["R"]), s["e"]) or any(x[:len(q0)] != q0 or len(x) != len(dep) for x in subs) \
                    or len({tuple(x) for x in subs}) != len(subs) or abs(s["random_weight"] * len(subs) - 1) > 1e-12 \
                    or dep not in subs:
                bad.append(("random_enumeration", kk))
            ws = [T[kk + ("RANDOM_EXTRA", i)]["weight"] for i in range(len(subs))]
            if abs(sum(ws) - 1) > 1e-9:
                bad.append(("random_weights", kk))
        if s["partially_represented"] or s["s2_status"] != "ok":
            bad.append(("s2_representation", kk, s["partially_represented"], s["s2_status"]))
        if s["env"] == "stable" and s["e"] != 0:
            bad.append(("stable_augmentation", kk))
    for row in leak:
        for nm, alts in row["by_list"].items():
            groups = collections.defaultdict(set)
            for tn, b in alts.items():
                groups[json.dumps(b["readings"])].add(json.dumps({x: b[x] for x in ("states_sha256", "plan", "candidates")},
                                                                  sort_keys=True))
            if any(len(v) != 1 for v in groups.values()):
                bad.append(("hidden_tape_leak", k4(row), nm))
            if len({json.dumps(b["queried"]) for b in alts.values()}) != 1:
                bad.append(("selection_depends_on_tape", k4(row), nm))
    gate("G4 selector obeys its frozen rule, preserves Q0, respects the cap, exact random enumeration, no hidden inputs",
         bad, len(SEL))
    bad = []
    exp_clock = TM.schedule_clock(DQ.SCHEDULE)
    for k, t in T.items():
        if t["clock"] != exp_clock or t["pre_action_wait"] != 4 or t["projection_clock"]["requested_at"] != TM.ORIGIN:
            bad.append(("clock", k))
        if t["queried"] != t["fields"] or t["queried_facts"] != len(t["fields"]):
            bad.append(("fields", k))
        if any(r["measured_at"] != DQ.SELECT_AT or r["received_at"] != DQ.SELECT_AT + 2 for r in t["receipts"]):
            bad.append(("sensor_times", k))
        if bool(t["receipts"]) != bool(t["fields"]) or (t["request"] is None) != (not t["fields"]):
            bad.append(("empty_list_request", k))
        if not (t["history_preserved"] and t["log_unchanged_by_projection"] and t["receipt_absent_before_reception"]):
            bad.append(("history", k))
        if t["refused"] or t["authority_conflicts"] or (t["status"] != "ok" and t["n_states"]):
            bad.append(("refused_or_status", k))
        if any(AS.violations(pubs[k[0]]["spec"], x) for x in t["states"]):
            bad.append(("inadmissible", k))
        if abs(t["utility"]["1"] - (t["utility_base"] - 4)) > 1e-9:
            bad.append(("cost_identity", k))
    by_we = collections.defaultdict(list)
    for k, t in T.items():
        by_we[(k[0], k[2])].append(t)
    for (w, env), ts in by_we.items():
        if len({t["actual_preaction_state_sha256"] for t in ts}) != 1:
            bad.append(("preaction_state_differs", w, env))
        vals = collections.defaultdict(set)
        for t in ts:
            for r in t["receipts"]:
                vals[(r["field"], r["measured_at"])].add(json.dumps(r["value"]))
        if any(len(v) != 1 for v in vals.values()):
            bad.append(("common_field_readings_differ", w, env))
        for role in ROLES:
            if len({t["origin_view_sha256"] for t in ts if t["role"] == role}) != 1:
                bad.append(("origin_view_differs", w, env, role))
    gate("G5 shared clock, actual pre-action states, common-field readings, provenance, history, invariants, costs",
         bad, len(T))
    res = {"set": set_name, "stage": stage, "worlds": len(W), "model_calls": 0, "run_meta": meta, "gates": gates,
           "all_gates_pass": not fails, "failed_gates": fails}

    # ------------------------------------------------------------------ outcomes
    def cell(w, r, env, arm):
        s = SEL[(w, r, env)]
        if arm == "RANDOM_EXTRA":
            if not s["e"]:
                ts = [(1.0, T[(w, r, env, "BASE", None)])]
            else:
                ts = [(T[(w, r, env, arm, i)]["weight"], T[(w, r, env, arm, i)]) for i in range(s["n_random_subsets"])]
        else:
            ts = [(1.0, T[(w, r, env, arm, None)])]
        avg = lambda f: sum(wt * f(t) for wt, t in ts)
        return {"U": avg(lambda t: t["utility"]["1"]), "U0": avg(lambda t: t["utility_base"]),
                "success": avg(lambda t: t["success"]), "action_cost": avg(lambda t: t["action_cost"]),
                "queried_facts": avg(lambda t: t["queried_facts"]), "waiting": avg(lambda t: t["pre_action_wait"]),
                "declines": avg(lambda t: t["outcome_kind"] == "decline"),
                "empty_completions": avg(lambda t: t["empty_plan"] and t["success"]),
                "false_completions": avg(lambda t: t["false_completion"]),
                "invalid_attempts": avg(lambda t: t["invalid_attempt"]),
                "menu_feasible_at_action": avg(lambda t: t["menu_feasible"]),
                "missed_menu_feasible": avg(lambda t: t["missed_opportunity"])}
    C = {(w, r, env, arm): cell(w, r, env, arm) for w in W for r in ROLES for env in TM.ENVS for arm in DQ.ARMS}
    cells = {}
    for env in TM.ENVS:
        for arm in DQ.ARMS:
            for role in ROLES + ("both",):
                rs = [C[(w, r, env, arm)] for w in W for r in (ROLES if role == "both" else (role,))]
                cells[f"{env}|{arm}|{role}"] = {k: round(sum(x[k] for x in rs), 4) for k in rs[0]}
                cells[f"{env}|{arm}|{role}"]["n"] = len(rs)
                cells[f"{env}|{arm}|{role}"]["full_domain_feasible_at_action"] = sum(
                    FE[(w, r, env)]["optimum_at_action"] is not None for w in W for r in (ROLES if role == "both" else (role,)))
    res["cells"] = cells

    def est(gv):
        m = domain_weighted(gv, gdom)
        return {"mean": None if m is None else round(m, 4), "ci95": bootstrap(gv, gdom, B, sd)}

    def contrast(fn, worlds=None):
        ws = worlds or W
        dd = {w: round(fn(w), 6) for w in ws}
        x = est(dd)
        x.update(better=sum(v > 0 for v in dd.values()), equal=sum(v == 0 for v in dd.values()),
                 worse=sum(v < 0 for v in dd.values()), per_world=dd)
        return x
    U = lambda w, env, arm: sum(C[(w, r, env, arm)]["U"] for r in ROLES) / 2
    con = {"PRIMARY changing DEPENDENCY - BASE": contrast(lambda w: U(w, "changing", "DEPENDENCY") - U(w, "changing", "BASE")),
           "SELECTION changing DEPENDENCY - RANDOM_EXTRA (exact average)": contrast(
               lambda w: U(w, "changing", "DEPENDENCY") - U(w, "changing", "RANDOM_EXTRA")),
           "changing RANDOM_EXTRA - BASE": contrast(lambda w: U(w, "changing", "RANDOM_EXTRA") - U(w, "changing", "BASE"))}
    for role in ROLES:
        con[f"changing DEPENDENCY - BASE, goal {role}"] = contrast(
            lambda w, r=role: C[(w, r, "changing", "DEPENDENCY")]["U"] - C[(w, r, "changing", "BASE")]["U"])
        con[f"changing DEPENDENCY - RANDOM_EXTRA, goal {role}"] = contrast(
            lambda w, r=role: C[(w, r, "changing", "DEPENDENCY")]["U"] - C[(w, r, "changing", "RANDOM_EXTRA")]["U"])
    for dom in ("delivery", "assembly"):
        dw = [w for w in W if gdom[w] == dom]
        for nm, a1, a2 in (("DEPENDENCY - BASE", "DEPENDENCY", "BASE"), ("DEPENDENCY - RANDOM_EXTRA", "DEPENDENCY", "RANDOM_EXTRA")):
            dd = {w: U(w, "changing", a1) - U(w, "changing", a2) for w in dw}
            con[f"changing {nm}, {dom} only"] = {"mean": round(statistics.mean(dd.values()), 4),
                                                 "ci95": bootstrap(dd, gdom, B, sd), "better": sum(v > 0 for v in dd.values()),
                                                 "equal": sum(v == 0 for v in dd.values()),
                                                 "worse": sum(v < 0 for v in dd.values()), "per_world": dd}
    con["control stable DEPENDENCY - BASE (expected exactly 0)"] = contrast(lambda w: U(w, "stable", "DEPENDENCY") - U(w, "stable", "BASE"))
    con["control stable RANDOM_EXTRA - BASE (expected exactly 0)"] = contrast(lambda w: U(w, "stable", "RANDOM_EXTRA") - U(w, "stable", "BASE"))
    res["contrasts"] = con

    # ------------------------------------------------------------------ diagnostics (post hoc; never fed back)
    diag = collections.defaultdict(list)
    per_copy = []
    for w in W:
        for r in ROLES:
            for env in TM.ENVS:
                s = SEL[(w, r, env)]
                b, d = T[(w, r, env, "BASE", None)], T[(w, r, env, "DEPENDENCY", None)]
                fe = FE[(w, r, env)]
                row = {"copy": f"{w}/{r}", "env": env, "domain": gdom[w], "Q0": s["Q0"], "G": s["G"], "R": s["R"],
                       "D": s["D"], "e": s["e"], "added": s["added"], "random_pool": s["random_pool_size"],
                       "n_random_subsets": s["n_random_subsets"], "random_tie": s["e"] > 0 and s["n_random_subsets"] == 1,
                       "s2_size": s["s2_size"], "s2_uncertain": s["s2_uncertain"],
                       "BASE": arm_row(b, fe), "DEPENDENCY": arm_row(d, fe),
                       "RANDOM_EXTRA_expected": {k: round(v, 4) for k, v in C[(w, r, env, "RANDOM_EXTRA")].items()},
                       "RANDOM_EXTRA_subsets": [dict(arm_row(T[(w, r, env, "RANDOM_EXTRA", i)], fe),
                                                     weight=T[(w, r, env, "RANDOM_EXTRA", i)]["weight"])
                                                for i in range(s["n_random_subsets"])] if s["e"] else [],
                       "label_hidden": b["label"]}
                if s["e"]:
                    lab = added_label(s, b, d)
                    row["added_measurement"] = lab
                    diag[f"{env}: added measurement {lab}"].append(f"{w}/{r}")
                    if d["utility"]["1"] < b["utility"]["1"]:
                        diag[f"{env}: DEPENDENCY costs more without helping"].append(f"{w}/{r}")
                    if d["outcome_kind"] == "decline":
                        diag[f"{env}: added check, DEPENDENCY still declines ({decline_reason(d, fe)})"].append(f"{w}/{r}")
                    if s["n_random_subsets"] == 1:
                        diag[f"{env}: RANDOM_EXTRA single eligible subset (tie with DEPENDENCY)"].append(f"{w}/{r}")
                elif s["R"]:
                    diag[f"{env}: e = 0 with uncertain fields elsewhere ({'full Q0' if len(s['Q0']) >= DQ.CAP else 'no uncovered own dependency'})"].append(f"{w}/{r}")
                for nm, t in (("BASE", b), ("DEPENDENCY", d)):
                    if t["outcome_kind"] == "decline":
                        diag[f"{env}: {nm} decline: {decline_reason(t, fe)}"].append(f"{w}/{r}")
                if d["success"] and not b["success"]:
                    diag[f"{env}: DEPENDENCY succeeds where BASE does not"].append(f"{w}/{r}")
                if b["success"] and not d["success"]:
                    diag[f"{env}: BASE succeeds where DEPENDENCY does not"].append(f"{w}/{r}")
                per_copy.append(row)
    res["diagnostics"] = {k: sorted(v) for k, v in sorted(diag.items())}
    res["per_copy"] = per_copy
    res["allocation"] = {
        "worlds_with_competing_addition (changing, e>0, >1 subset)": sorted(
            {w for w in W for r in ROLES if SEL[(w, r, "changing")]["e"] and SEL[(w, r, "changing")]["n_random_subsets"] > 1}),
        "copies_e_positive_changing": sum(bool(SEL[(w, r, "changing")]["e"]) for w in W for r in ROLES),
        "random_ties_changing": sum(SEL[(w, r, "changing")]["e"] > 0 and SEL[(w, r, "changing")]["n_random_subsets"] == 1
                                    for w in W for r in ROLES)}
    return res


def arm_row(t, fe):
    return {"fields": t["fields"], "added": t["added_fields"], "fees": t["queried_facts"], "plan": t["plan"],
            "outcome": t["outcome_kind"], "success": t["success"], "empty_completion": t["empty_plan"] and t["success"],
            "decline_reason": decline_reason(t, fe) if t["outcome_kind"] == "decline" else None,
            "post_support_size": t["n_states"], "uncertain_relevant": t["uncertain_relevant"],
            "menu_feasible": t["menu_feasible"], "full_domain_feasible": fe["optimum_at_action"] is not None,
            "action_cost": t["action_cost"], "waiting": t["pre_action_wait"], "U": t["utility"]["1"]}


def decline_reason(t, fe):
    if fe["optimum_at_action"] is None:
        return "full_domain_infeasible"
    if not t["menu_feasible"]:
        return "menu_gap (full-domain feasible, no valid menu plan)"
    return "information_insufficient" + (" (unqueried uncertain prerequisite)" if t["uncertain_unqueried"] else
                                         " (queried prerequisite still uncertain)" if t["uncertain_queried"] else "")


def added_label(s, b, d):
    """Post-hoc label for DEPENDENCY's added fields (matched saved outcomes; never an input to selection)."""
    if d["plan"] != b["plan"]:
        return "decision-changing"
    if all(len({x.get(f, "<absent>") for x in b["states"]}) == 1 for f in s["added"]):
        return "redundant given Q0's readings"
    if b["plan"] is not None:
        return "unnecessary (plan already guaranteed)"
    return "insufficient (decision unchanged, still declines)"


def fmt_ci(x):
    return "—" if x["ci95"] is None else f"[{x['ci95'][0]:+.2f}, {x['ci95'][1]:+.2f}]"


def tables(res):
    L = [f"# V1.14.0 dependency-aware query selection: {res['set']} / {res['stage']}", "",
         f"All gates pass: **{res['all_gates_pass']}**. Model calls: 0. Trajectories executed: "
         f"{res['run_meta']['trajectories_total']} ({res['run_meta']['trajectories_by_arm']}); policy cells "
         f"{res['run_meta']['policy_cells']}.", "", "## Gates", "", "| Gate | Pass | Failures / checked |", "|---|---|---|"]
    for k, g in res["gates"].items():
        L.append(f"| {k} | {'PASS' if g['pass'] else 'FAIL'} | {g['failures']} / {g['checked']} |")
    L += ["", "## Contrasts (λ = 1; mean over goals within world; domain-stratified bootstrap, descriptive)", "",
          "| Contrast | Mean | 95% interval | better / equal / worse |", "|---|---|---|---|"]
    for k, x in res["contrasts"].items():
        L.append(f"| {k} | {x['mean']:+.4f} | {fmt_ci(x)} | {x['better']} / {x['equal']} / {x['worse']} |")
    L += ["", "## Cells (sums over goal copies; RANDOM_EXTRA = exact expected value)", "",
          "| env | arm | goals | U | success | action cost | fees | waiting | declines | empty completions | false compl. | invalid | menu-feasible | full-domain feasible |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for k, c in res["cells"].items():
        env, arm, role = k.split("|")
        L.append(f"| {env} | {arm} | {role} | {c['U']:g} | {c['success']:g} | {c['action_cost']:g} | {c['queried_facts']:g} | "
                 f"{c['waiting']:g} | {c['declines']:g} | {c['empty_completions']:g} | {c['false_completions']:g} | "
                 f"{c['invalid_attempts']:g} | {c['menu_feasible_at_action']:g} | {c['full_domain_feasible_at_action']} |")
    L += ["", "## Allocation (from public inputs)", ""]
    for k, v in res["allocation"].items():
        L.append(f"- {k}: {v if not isinstance(v, list) else f'{len(v)} ' + ', '.join(v)}")
    L += ["", "## Diagnostics (post hoc)", ""]
    for k, v in res["diagnostics"].items():
        L.append(f"- **{k}** ({len(v)}): {', '.join(v)}")
    L += ["", "## Changing environment, goal copies with e > 0", "",
          "| copy | Q0 | added (DEP) | pool / subsets | BASE | DEPENDENCY | RANDOM E[U] | label |", "|---|---|---|---|---|---|---|---|"]
    sh = lambda fs: ", ".join(fs) or "—"
    for r in res["per_copy"]:
        if r["env"] != "changing" or not r["e"]:
            continue
        o = lambda a: f"{a['outcome']}{'' if a['plan'] is None else ' ' + a['plan']} U={a['U']:g}"
        L.append(f"| {r['copy']} | {sh(r['Q0'])} | {sh(r['added'])} | {r['random_pool']} / {r['n_random_subsets']} | "
                 f"{o(r['BASE'])} | {o(r['DEPENDENCY'])} | {r['RANDOM_EXTRA_expected']['U']:g} | {r.get('added_measurement')} |")
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
                      "primary": {k: res["contrasts"]["PRIMARY changing DEPENDENCY - BASE"][k] for k in ("mean", "ci95")}}))


if __name__ == "__main__":
    main()
