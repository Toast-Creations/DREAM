"""V1.12.0 analysis: correctness gates first, then development outcomes (descriptive). No model.
Usage: fresh_analyze.py --hub HUB --set SET --stage STAGE [--boot 10000] [--seed 20261105]
Reads HUB/stages/STAGE/{trajectories,reference,requests,leakage}.jsonl; writes HUB/analysis/STAGE/{ANALYSIS.json,
TABLES.md}. Unit of inference: the base world (n = 24 in the main panel); goals are averaged within a world
before any interval; conditions are paired, never pooled.
"""
import argparse
import collections
import json
from pathlib import Path

from _bootstrap import ROOT  # noqa: F401
from tempo import agentstate as AS, freshness as F
from tempo_analyze import bootstrap, domain_weighted

ROLES = ("A", "B")
CONDS = [(e, d) for e in ("changing", "stable") for d in (2, 0)]  # delayed-changing first


def load(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]


def skey(states):
    return sorted(json.dumps(sorted(s.items())) for s in states)


def analyse(hub, set_name, stage, B=10000, sd=20261105):
    st = hub / "stages" / stage
    traj, refs = load(st / "trajectories.jsonl"), load(st / "reference.jsonl")
    reqs, leak = load(st / "requests.jsonl"), load(st / "leakage.jsonl")
    meta = json.loads((st / "RUN-META.json").read_text())
    pubs = {p["world_id"]: p for p in load(hub / "data" / "public" / f"{set_name}-worlds.jsonl")}
    T = {(t["world"], t["role"], t["env"], t["delay"], t["projection"]): t for t in traj}
    RF = {(r["world"], r["role"], r["env"], r["delay"]): r for r in refs}
    worlds_ = sorted(pubs)
    gdom = {w: pubs[w]["domain"] for w in worlds_}
    gates, fails = {}, []

    def gate(name, bad, total, detail=None):
        gates[name] = {"pass": not bad, "failures": len(bad), "checked": total, "examples": bad[:10],
                       **({"detail": detail} if detail else {})}
        if bad:
            fails.append(name)

    # G1 exact agreement with the independent reference
    bad, n = [], 0
    for k, r in RF.items():
        t = T[k + ("temporal",)]
        n += 1
        if skey(t["states"]) != skey(r["states"]) or t["candidates"] != r["classes"] or t["plan"] != r["choice"]:
            bad.append({"key": k, "temporal_plan": t["plan"], "reference_choice": r["choice"]})
    gate("G1_reference_exact_agreement (states, candidate classes, choice)", bad, n)
    # G2 no unsupported permission; no invalid attempt under the declared contract
    bad = [k for k, r in RF.items() if T[k + ("temporal",)]["plan"] is not None and
           r["classes"][T[k + ("temporal",)]["plan"]] != "guaranteed"]
    bad += [k for k in RF if T[k + ("temporal",)]["invalid_attempt"]]
    gate("G2_no_unsupported_permission_and_no_invalid_attempt (temporal)", bad, len(RF))
    # G3 picks a cheapest guaranteed candidate whenever the reference has one (no pass by declining)
    bad = [k for k, r in RF.items() if r["choice"] is not None and T[k + ("temporal",)]["plan"] != r["choice"]]
    has = sum(r["choice"] is not None for r in RF.values())
    gate("G3_selects_reference_choice_when_one_exists", bad, has)
    # G4 controls
    bad = []
    for w in worlds_:
        for role in ROLES:
            for d in F.DELAYS:
                a, b = T[(w, role, "stable", d, "carry_forward")], T[(w, role, "stable", d, "temporal")]
                if (a["states_sha256"], a["plan"], a["utility"]) != (b["states_sha256"], b["plan"], b["utility"]):
                    bad.append(("stable", w, role, d))
            for p in F.PROJECTIONS:
                a, b = T[(w, role, "stable", 0, p)], T[(w, role, "changing", 0, p)]
                if (a["states_sha256"], a["plan"], a["utility"], a["success"]) != \
                        (b["states_sha256"], b["plan"], b["utility"], b["success"]):
                    bad.append(("delay0", w, role, p))
    gate("G4_controls (stable: temporal = carry-forward; delay 0: changing = stable)", bad,
         len(worlds_) * 2 * (len(F.DELAYS) + len(F.PROJECTIONS)))
    # G5 matching, provenance, history, invariants, hidden information
    bad = []
    rq = {(r["world"], r["role"]): r for r in reqs}
    for w in worlds_:
        for role in ROLES:
            vals = set()
            for e, d in CONDS:
                a, b = T[(w, role, e, d, "carry_forward")], T[(w, role, e, d, "temporal")]
                for k in ("queried", "receipts_sha256", "ledger_sha256", "log_head", "historical_detail_sha256"):
                    if a[k] != b[k]:
                        bad.append(("projection_mismatch", w, role, e, d, k))
                if a["queried"] != rq[(w, role)]["fields"]:
                    bad.append(("request_not_cloned", w, role, e, d))
                vals.add(json.dumps([(x["field"], x["measured_at"], x["value"]) for x in a["receipts"]]))
                if [x["received_at"] - x["measured_at"] for x in a["receipts"]] != [d] * len(a["receipts"]):
                    bad.append(("delivery_time", w, role, e, d))
                for t in (a, b):
                    if not (t["earlier_view_preserved"] and t["log_unchanged_by_projection"]):
                        bad.append(("history", w, role, e, d, t["projection"]))
                    if any(AS.violations(pubs[w]["spec"], s) for s in t["states"]):
                        bad.append(("inadmissible_state", w, role, e, d, t["projection"]))
                    if t["refused"] or t["authority_conflicts"]:
                        bad.append(("refused_or_conflict", w, role, e, d, t["projection"]))
                if not b["actual_in_support"]:
                    bad.append(("actual_state_outside_temporal_support", w, role, e, d))
            if len(vals) != 1:
                bad.append(("receipt_values_differ_across_conditions", w, role))
    for row in leak:
        bl = row["beliefs"]
        for p in F.PROJECTIONS:
            if len({json.dumps(bl[n][p], sort_keys=True) for n in bl}) != 1:
                bad.append(("hidden_tape_leak", row["world"], row["role"], p))
    gate("G5_matching_provenance_history_invariants_hidden_information", bad, len(worlds_) * 2)
    res = {"set": set_name, "stage": stage, "worlds": len(worlds_), "trajectories": len(traj), "model_calls": 0,
           "run_meta": meta, "gates": gates, "all_gates_pass": not fails, "failed_gates": fails}
    # ---------------------------------------------------------------- outcomes
    cells = {}
    for e, d in CONDS:
        for p in F.PROJECTIONS:
            for role in ROLES + ("both",):
                rs = [T[(w, r_, e, d, p)] for w in worlds_ for r_ in (ROLES if role == "both" else (role,))]
                rk = [RF[(w, r_, e, d)] for w in worlds_ for r_ in (ROLES if role == "both" else (role,))]
                unsupported = sum(t["plan"] is not None and r["classes"][t["plan"]] != "guaranteed"
                                  for t, r in zip(rs, rk))
                cells[f"{e}|d{d}|{p}|{role}"] = {
                    "n": len(rs), "utility_total": sum(t["utility"] for t in rs),
                    "success": sum(t["success"] for t in rs), "invalid_attempts": sum(t["invalid_attempt"] for t in rs),
                    "unsupported_permissions": unsupported, "declines": sum(t["declined"] for t in rs),
                    "declines_reference_has_no_guaranteed": sum(t["declined"] and r["choice"] is None
                                                                for t, r in zip(rs, rk)),
                    "declines_reference_has_guaranteed": sum(t["declined"] and r["choice"] is not None
                                                             for t, r in zip(rs, rk)),
                    "opportunities_at_action_time": sum(t["opportunity"] for t in rs),
                    "missed_menu_feasible_opportunities": sum(t["missed_opportunity"] for t in rs),
                    "queried_facts": sum(len(t["queried"]) for t in rs),
                    "action_cost": sum(t["action_cost"] for t in rs),
                    "mean_states": round(sum(t["n_states"] for t in rs) / len(rs), 3),
                    "max_set": max(t["max_set"] for t in rs),
                    "relevant_fields_uncertain": sum(len(t["uncertain_relevant"]) for t in rs),
                    "actual_state_in_support": sum(t["actual_in_support"] for t in rs),
                    "exact_set_agreement_with_reference": sum(skey(t["states"]) == skey(r["states"])
                                                              for t, r in zip(rs, rk))}
    res["cells"] = cells

    def est(gv):
        m = domain_weighted(gv, gdom)
        return {"mean": None if m is None else round(m, 4), "ci95": bootstrap(gv, gdom, B, sd)}

    def contrast(fn):
        dd = {w: fn(w) for w in worlds_}
        x = est(dd)
        x.update(better=sum(v > 0 for v in dd.values()), equal=sum(v == 0 for v in dd.values()),
                 worse=sum(v < 0 for v in dd.values()))
        return x
    U = lambda w, e, d, p: sum(T[(w, r, e, d, p)]["utility"] for r in ROLES) / 2
    C = {}
    C["PRIMARY changing d2: temporal - carry_forward"] = contrast(lambda w: U(w, "changing", 2, "temporal") -
                                                                  U(w, "changing", 2, "carry_forward"))
    for role in ROLES:
        C[f"changing d2, goal {role}: temporal - carry_forward"] = contrast(
            lambda w, r=role: T[(w, r, "changing", 2, "temporal")]["utility"] -
            T[(w, r, "changing", 2, "carry_forward")]["utility"])
    for e, d in CONDS[1:]:
        C[f"control {e} d{d}: temporal - carry_forward"] = contrast(lambda w, e=e, d=d: U(w, e, d, "temporal") -
                                                                     U(w, e, d, "carry_forward"))
    for p in F.PROJECTIONS:
        C[f"{p}: changing d2 - stable d2"] = contrast(lambda w, p=p: U(w, "changing", 2, p) - U(w, "stable", 2, p))
    res["contrasts"] = C
    # ---------------------------------------------------------------- categories (delayed-changing)
    cat = collections.defaultdict(list)
    for w in worlds_:
        decl = pubs[w]["transitions"]
        for role in ROLES:
            t = T[(w, role, "changing", 2, "temporal")]
            c = T[(w, role, "changing", 2, "carry_forward")]
            s = T[(w, role, "stable", 2, "temporal")]
            touched = any(f in t["relevant"] for tr in decl for f in list(tr["guard"]) + list(tr["effect"]))
            k = f"{w}|{role}"
            if s["plan"] is not None and t["plan"] is None:
                cat["guaranteed_candidate_lost_to_possible_change"].append(k)
            if touched and t["plan"] is not None:
                cat["candidate_preserved_despite_relevant_declaration"].append(k)
            if set(t["valid_at_execute"]) - set(t["valid_at_measure"]):
                cat["opportunity_opened_by_actual_change"].append(k)
            if set(t["valid_at_measure"]) - set(t["valid_at_execute"]):
                cat["opportunity_closed_by_actual_change"].append(k)
            if t["declined"] and t["opportunity"]:
                cat["temporal_justified_decline_with_hidden_opportunity"].append(k)
            if c["invalid_attempt"]:
                cat["carry_forward_invalid_attempt"].append(k)
            if c["plan"] is not None and RF[(w, role, "changing", 2)]["classes"][c["plan"]] != "guaranteed" \
                    and c["success"]:
                cat["carry_forward_unsupported_but_lucky"].append(k)
            if t["uncertain_relevant"] and not t["applied_events"]:
                cat["uncertain_although_nothing_happened"].append(k)
            unq = [f for f in t["relevant"] if f not in t["queried"]]
            if any(f in unq for tr in decl for f in tr["effect"]):
                cat["declared_change_to_unqueried_prerequisite"].append(k)
    res["categories_changing_d2"] = {k: {"count": len(v), "items": v} for k, v in sorted(cat.items())}
    # per label
    lab = collections.defaultdict(lambda: collections.Counter())
    for w in worlds_:
        for role in ROLES:
            t, c = T[(w, role, "changing", 2, "temporal")], T[(w, role, "changing", 2, "carry_forward")]
            L = lab[t["label"]]
            L["n"] += 1
            L["temporal_success"] += t["success"]; L["temporal_decline"] += t["declined"]
            L["cf_success"] += c["success"]; L["cf_invalid"] += c["invalid_attempt"]; L["cf_decline"] += c["declined"]
            L["temporal_utility"] += t["utility"]; L["cf_utility"] += c["utility"]
    res["by_label_changing_d2"] = {k: dict(v) for k, v in sorted(lab.items())}
    # disagreement traces
    dis = []
    for e, d in CONDS:
        for w in worlds_:
            for role in ROLES:
                a, b = T[(w, role, e, d, "carry_forward")], T[(w, role, e, d, "temporal")]
                if (a["plan"], a["utility"]) != (b["plan"], b["utility"]):
                    dis.append({"world": w, "role": role, "env": e, "delay": d, "label": b["label"],
                                "queried": b["queried"], "declared": b["declared_transitions"],
                                "applied_events": b["applied_events"],
                                "carry_forward": {"plan": a["plan"], "utility": a["utility"], "invalid": a["invalid_attempt"],
                                                  "support": a["relevant_support"]},
                                "temporal": {"plan": b["plan"], "utility": b["utility"], "n_states": b["n_states"],
                                             "support": b["relevant_support"], "candidates": b["candidates"]},
                                "actual_at_execute": b["actual_relevant_at_execute"], "valid_at_execute": b["valid_at_execute"]})
    res["disagreements"] = dis
    res["requests"] = {"fields_per_goal": dict(collections.Counter(len(r["fields"]) for r in reqs)),
                       "total_fields": sum(len(r["fields"]) for r in reqs)}
    return res


def tables(res):
    L = [f"# V1.12.0 observation freshness: {res['set']} / {res['stage']}", "",
         f"Worlds {res['worlds']}, trajectories {res['trajectories']}, model calls 0. "
         f"Run wall {res['run_meta']['wall_s']:.1f} s, max reachable set {res['run_meta']['max_reachable_set']}, "
         f"max projection CPU {res['run_meta']['max_projection_cpu_s']:.4f} s.", "", "## Correctness gates", "",
         "| Gate | Pass | Failures / checked |", "|---|---|---|"]
    for k, g in res["gates"].items():
        L.append(f"| {k} | {'yes' if g['pass'] else '**NO**'} | {g['failures']} / {g['checked']} |")
    L += ["", f"All gates pass: **{res['all_gates_pass']}**", "", f"## Cells (both goals; {2 * res['worlds']} goal copies per cell)", "",
          "| Env | Delay | Projection | Utility | Success | Invalid | Unsupported perm. | Declines (ref none / ref has) |"
          " Missed opp. | Queried | Mean states | Uncertain rel. fields | Actual in support |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for k, c in res["cells"].items():
        e, d, p, role = k.split("|")
        if role != "both":
            continue
        L.append(f"| {e} | {d} | {p} | {c['utility_total']} | {c['success']} | {c['invalid_attempts']} | "
                 f"{c['unsupported_permissions']} | {c['declines']} ({c['declines_reference_has_no_guaranteed']} / "
                 f"{c['declines_reference_has_guaranteed']}) | {c['missed_menu_feasible_opportunities']} | "
                 f"{c['queried_facts']} | {c['mean_states']} | {c['relevant_fields_uncertain']} | "
                 f"{c['actual_state_in_support']}/{c['n']} |")
    L += ["", "## Contrasts (per world, goals averaged; domain-stratified bootstrap, n = 24 worlds; descriptive)", "",
          "| Contrast | Mean [95%] | Better / equal / worse |", "|---|---|---|"]
    for k, c in res["contrasts"].items():
        L.append(f"| {k} | {c['mean']} {c['ci95']} | {c['better']} / {c['equal']} / {c['worse']} |")
    L += ["", "## Delayed-changing categories", ""]
    for k, v in res["categories_changing_d2"].items():
        L.append(f"- {k}: {v['count']} ({', '.join(v['items'])})")
    L += ["", "## By intended label (changing, delay 2)", "", "| Label | n | Temporal success / decline / utility | "
          "Carry-forward success / invalid / decline / utility |", "|---|---|---|---|"]
    for k, v in res["by_label_changing_d2"].items():
        L.append(f"| {k} | {v.get('n', 0)} | {v.get('temporal_success', 0)} / {v.get('temporal_decline', 0)} / "
                 f"{v.get('temporal_utility', 0)} | {v.get('cf_success', 0)} / {v.get('cf_invalid', 0)} / "
                 f"{v.get('cf_decline', 0)} / {v.get('cf_utility', 0)} |")
    L += ["", f"## Every disagreement between projections ({len(res['disagreements'])})", ""]
    for x in res["disagreements"]:
        L.append(f"- {x['world']}/{x['role']} {x['env']} d{x['delay']} [{x['label']}]: carry-forward "
                 f"{x['carry_forward']['plan']} (U {x['carry_forward']['utility']}"
                 f"{', invalid' if x['carry_forward']['invalid'] else ''}) vs temporal {x['temporal']['plan']} "
                 f"(U {x['temporal']['utility']}, {x['temporal']['n_states']} states); events "
                 f"{[e['transition'] for e in x['applied_events']] or 'none'}; valid at action {x['valid_at_execute']}")
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
                      "primary": res["contrasts"]["PRIMARY changing d2: temporal - carry_forward"]}))


if __name__ == "__main__":
    main()
