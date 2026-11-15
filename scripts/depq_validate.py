"""Pre-run validation for V1.14.0 (no model; no controller outcome on the committed panel is computed or compared).
Usage: depq_validate.py --hub HUB --set depq [--out HUB/phase0]
Checks:
  1 declarations: well formed, invariant-preserving, no agent state, publicly allowed values, fixed numeric window
    (12, 14), one-shot
  2 fixed environment: every tape event happens at a half-tick inside (12, 14); stable variants realize nothing
  3 initial support (public view at the origin) contains the actual initial state on the closed scope
  4 S2 (public, t = 2): non-empty; every registry field represented in every S2 state (no partial or missing
    representation); the actual state at t = 2 is in S2; every R field has a well-defined true value; finite
    declared value lists; production S2/R/D/subsets equal the independent selector reference (tempo.depref)
  5 allocation from public inputs: competing-addition worlds per domain (e > 0 and > 1 eligible subset), singleton
    pools, full Q0, e = 0 with uncertainty elsewhere, two-field additions, stable exact-parity subset (every stable
    copy has e = 0), random-subset execution count; scorer-side controls from the hidden truth at the action
    boundary (menu gaps, full-domain infeasible goals) -- no controller is run
  6 public/hidden separation
  7 compatibility on the stored 1.13.0 panel: BASE (this code path, DEFER clock, Q0) reproduces all 96 stored DEFER
    trajectories (fields, readings, support, plan, success, utility), including the eight residual declines and
    every zero-query path; the regression fixture a06/B (DEPENDENCY measures the unqueried stock field)
"""
import argparse
import collections
import json
import math
import os
import sys
from pathlib import Path

from _bootstrap import ROOT  # noqa: F401
from dream_core import localpaths as LP  # public release: local paths from environment
from tempo import agentstate as AS, depgen as DG, depquery as DQ, depref as DR, freshness as F, recovery as R, \
    timing as TM, timinggen as TG
from timing_run import full_domain

RUNS = Path(os.environ.get("DREAM_RUNS", f"{LP.RUNS}"))
TIMING = RUNS / "temporal-query-timing-20261105-221636"
HIDDEN_KEYS = {"truth", "tape", "seed", "labels", "intended_status", "records_v02"}


def load(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", required=True)
    ap.add_argument("--set", required=True)
    ap.add_argument("--out")
    ap.add_argument("--skip-compat", action="store_true")
    a = ap.parse_args()
    hub = Path(a.hub)
    out = Path(a.out) if a.out else hub / "phase0"
    out.mkdir(parents=True, exist_ok=True)
    pubs = load(hub / "data" / "public" / f"{a.set}-worlds.jsonl")
    hids = {h["world_id"]: h for h in load(hub / "data" / "hidden" / f"{a.set}-hidden.jsonl")}
    rows = {r[0]: (d, r) for d, r, _ in DG.specs(a.set, 0, smoke=a.set.endswith("smoke"))}
    res, failures = {}, []

    def check(cond, msg):
        if not cond:
            failures.append(msg)
        return cond
    # 1
    for pub in pubs:
        for tr in pub["transitions"]:
            try:
                F.check_declaration(pub["spec"], tr, pub["registry_allowed"])
            except F.DeclarationError as e:
                check(False, f"{pub['world_id']}: {e}")
            check(tr["window"] == {"lo": 12, "hi": 14} and tr.get("max_occurrences") == 1, f"{pub['world_id']}: window")
    res["1_declarations"] = {"worlds": len(pubs), "transitions": collections.Counter(len(p["transitions"]) for p in pubs)}
    # 2
    n_ev = 0
    sc = TM.schedule_clock(DQ.SCHEDULE)
    for pub in pubs:
        hid = hids[pub["world_id"]]
        _, _, env_ep = DG.goal_copy(pub, hid, "A")
        for env_kind in TM.ENVS:
            env = TM.environment(env_ep, env_kind, pub["transitions"], hid["tape"], sc)
            _, applied = env.state_at(sc["execute_at"])
            if env_kind == "changing":
                check(len(applied) == len(hid["tape"]) and all((e["at"] * 2) % 2 == 1 and 12 < e["at"] < 14
                                                               for e in applied), f"{pub['world_id']}: tape")
                n_ev += len(applied)
            else:
                check(not applied, f"{pub['world_id']}: stable realized an event")
    res["2_fixed_environment"] = {"realized_events": n_ev,
                                  "worlds_without_realized_change": sum(not hids[p["world_id"]]["tape"] for p in pubs)}
    # 3, 4, 5, 6
    cover = 0
    alloc = collections.defaultdict(list)
    n_exec = collections.Counter()
    max_s2 = 0
    for pub in pubs:
        hid = hids[pub["world_id"]]
        domain = pub["domain"]
        w = DG.build(rows[pub["world_id"]][1], domain, hid["seed"], a.set)[0]
        check(not (HIDDEN_KEYS & set(pub)), f"{pub['world_id']}: hidden key in public file")
        v = R.engine_from(pub, None, "v").view("earlier", TM.ORIGIN, cutoff=TM.ORIGIN)
        scope = set()
        for role in ("A", "B"):
            ep, gc, env_ep = DG.goal_copy(pub, hid, role)
            check(not (HIDDEN_KEYS & set(ep)), f"{ep['episode_id']}: hidden key")
            scope |= set(gc["relevant"])
            q0 = F.p2_request(ep, gc)["fields"]
            reg = DQ.sensor_registry(ep)
            for env_kind in TM.ENVS:
                tag = f"{pub['world_id']}/{role}/{env_kind}"
                sel = DQ.selection_for(ep, gc, q0, env_kind)
                max_s2 = max(max_s2, sel["s2_size"])
                ref = DR.selection_reference(ep, gc["relevant"], q0, env_kind, TM.ORIGIN, DQ.SELECT_AT, DQ.CAP,
                                             set(AS.agent_fields(ep["spec"])))
                sk = lambda S: sorted(json.dumps(sorted(s.items())) for s in S)
                check(sk(sel["s2_states"]) == sk(ref["s2_states"]) and sel["R"] == ref["R"] and sel["D"] == ref["D"]
                      and sel["fields"]["DEPENDENCY"] == ref["DEPENDENCY"] and
                      (not sel["e"] or sel["random_subsets"] == ref["random_subsets"]), f"{tag}: selector reference")
                check(sel["s2_status"] == "ok" and sel["s2_size"] > 0, f"{tag}: S2 empty")
                check(not sel["partially_represented"] and not sel["unrepresented"], f"{tag}: S2 representation")
                check(all(isinstance(reg[f], list) and reg[f] for f in reg), f"{tag}: registry values")
                env = TM.environment(env_ep, env_kind, pub["transitions"], hid["tape"], sc)
                s2_true = env.state_at(DQ.SELECT_AT)[0]
                check(any(all(s2_true.get(f) == x for f, x in s.items()) for s in sel["s2_states"]), f"{tag}: actual not in S2")
                check(all(f in s2_true for f in sel["R"] + sel["Q0"]), f"{tag}: R field without a true value")
                n_exec[env_kind] += 2 + (sel["n_random_subsets"] if sel["e"] else 0)
                key = f"{pub['world_id']}/{role}"
                if env_kind == "stable":
                    check(sel["e"] == 0, f"{tag}: stable augmentation")
                    alloc["stable: exact-parity copies (e = 0)"].append(key)
                    continue
                if sel["e"] and sel["n_random_subsets"] > 1:
                    alloc[f"changing: e>0 and >1 subset ({domain})"].append(key)
                if sel["e"] and sel["n_random_subsets"] == 1:
                    alloc["changing: singleton random pool (tie)"].append(key)
                if sel["e"] == 2:
                    alloc["changing: two fields added"].append(key)
                if len(q0) >= DQ.CAP:
                    alloc["changing: full Q0 (no spare capacity)"].append(key)
                if not sel["e"] and sel["R"] and len(q0) < DQ.CAP:
                    alloc["changing: e = 0, uncertainty only outside own dependencies"].append(key)
                if not q0:
                    alloc["changing: Q0 empty"].append(key)
                # scorer-side controls (hidden truth at the action boundary; no controller)
                sx = env.state_at(sc["execute_at"])[0]
                menu = F.valid_plans_at(ep, gc, sx)
                opt = full_domain(w, domain, gc["goal"], sx)
                if opt is None:
                    alloc["changing: full-domain infeasible at action"].append(key)
                elif not menu:
                    alloc["changing: menu gap at action (full-domain feasible)"].append(key)
        for tr in pub["transitions"]:
            scope |= set(tr["guard"]) | set(tr["effect"])
        for f in scope:
            cover += check(f in v["op_options"] and hid["truth"][f] in v["op_options"][f],
                           f"{pub['world_id']}: support misses {f}")
    comp_worlds = {d: sorted({k.split("/")[0] for k in alloc[f"changing: e>0 and >1 subset ({d})"]})
                   for d in ("delivery", "assembly")}
    check(sum(len(v) for v in comp_worlds.values()) >= (8 if not a.set.endswith("smoke") else 1) and
          all(comp_worlds.values()), f"competing-addition worlds {comp_worlds}")
    res["3_initial_support_contains_actual"] = f"{cover} closed-scope fields covered"
    res["4_S2"] = {"max_S2": max_s2, "independent_selector_reference": "equal for every copy" if not any(
        "selector reference" in x for x in failures) else "DIFFERS"}
    res["5_allocation"] = {"competing_addition_worlds": comp_worlds,
                           "competing_addition_world_count": sum(len(v) for v in comp_worlds.values()),
                           **{k: {"n": len(v), "copies": sorted(v)} for k, v in sorted(alloc.items())},
                           "executions": {"BASE+DEPENDENCY": 8 * len(pubs),
                                          "random_subset_trajectories": sum(n_exec.values()) - 8 * len(pubs),
                                          "total": sum(n_exec.values())},
                           "labels_hidden": dict(sorted(collections.Counter(
                               hids[p["world_id"]]["labels"][r] for p in pubs for r in ("A", "B")).items()))}
    res["6_public_hidden_separation"] = "no hidden key in public worlds or goal copies; selection reads public copies only"
    # 7 compatibility
    if not a.skip_compat:
        if (TIMING / "stages" / "main" / "trajectories.jsonl").exists():
            tpubs = load(TIMING / "data" / "public" / "timing-worlds.jsonl")
            thids = {h["world_id"]: h for h in load(TIMING / "data" / "hidden" / "timing-hidden.jsonl")}
            stored = {(t["world"], t["role"], t["env"]): t for t in load(TIMING / "stages" / "main" / "trajectories.jsonl")
                      if t["schedule"] == "DEFER"}
            diffs, n, zero_q, declines = [], 0, 0, []
            fix = {}
            for pub in tpubs:
                for role in ("A", "B"):
                    ep, gc, env_ep = TG.goal_copy(pub, thids[pub["world_id"]], role)
                    q0 = F.p2_request(ep, gc)["fields"]
                    for env_kind in TM.ENVS:
                        sel = DQ.selection_for(ep, gc, q0, env_kind)
                        t = DQ.run_arm(ep, gc, sel["fields"]["BASE"], env_kind, env_ep, thids[pub["world_id"]]["tape"], "|BASE")
                        o = stored[(pub["world_id"], role, env_kind)]
                        n += 1
                        zero_q += not q0
                        sig = lambda x: (x["queried"], [(r["field"], r["measured_at"], r["value"]) for r in x["readings"]],
                                         x["states_sha256"], x["plan"], x["success"], x["utility_base"], x["utility"]["1"],
                                         x["outcome_kind"])
                        if sig(t) != sig(o):
                            diffs.append((pub["world_id"], role, env_kind))
                        if env_kind == "changing" and t["outcome_kind"] == "decline":
                            declines.append(f"{pub['world_id']}/{role}")
                        if (pub["world_id"], role, env_kind) == ("a06", "B", "changing"):
                            d = DQ.run_arm(ep, gc, sel["fields"]["DEPENDENCY"], env_kind, env_ep,
                                           thids[pub["world_id"]]["tape"], "|DEP")
                            fix = {"Q0": q0, "D": sel["D"], "DEPENDENCY_fields": sel["fields"]["DEPENDENCY"],
                                   "BASE": [t["outcome_kind"], t["plan"], t["utility"]["1"]],
                                   "DEPENDENCY": [d["outcome_kind"], d["plan"], d["utility"]["1"], d["success"]]}
            check(not diffs and n == 96, f"BASE vs 1.13.0 DEFER differences {diffs[:5]} (n={n})")
            check(sorted(declines) == sorted(["a03/A", "a04/A", "a06/B", "a12/A", "a03/B", "d01/A", "d06/A", "d08/B"]),
                  f"residual declines {declines}")
            check(fix and "Nedudefe.on_hand" in fix["DEPENDENCY_fields"] and fix["DEPENDENCY"][3],
                  f"a06/B fixture {fix}")
            res["7_compatibility"] = {"BASE_vs_1.13.0_DEFER": f"{n - len(diffs)}/{n} identical",
                                      "zero_query_copies_in_1.13.0_panel": zero_q,
                                      "residual_changing_declines_reproduced": sorted(declines),
                                      "regression_fixture_a06/B": fix}
        else:
            check(False, "1.13.0 hub missing")
    res["failures"], res["pass"] = failures, not failures
    (out / "VALIDATION.json").write_text(json.dumps(res, indent=1, default=str) + "\n")
    L = [f"# V1.14.0 pre-run validation ({a.set})", "", f"**{'PASS' if not failures else 'FAIL'}** ({len(failures)} "
         "failures). No model call; no controller outcome on the committed panel was computed or compared.", ""]
    for k, v in res.items():
        if k not in ("failures", "pass"):
            L += [f"## {k}", "```", json.dumps(v, indent=1, default=str)[:4000], "```"]
    if failures:
        L += ["## Failures", *[f"- {f}" for f in failures]]
    (out / "VALIDATION.md").write_text("\n".join(L) + "\n")
    print("PASS" if not failures else f"FAIL {len(failures)}: {failures[:5]}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
