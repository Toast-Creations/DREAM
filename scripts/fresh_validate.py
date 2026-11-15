"""Pre-run validation for V1.12.0 (no model; no comparison of controller outputs on the committed panel).
Usage: fresh_validate.py --hub HUB --set fresh [--out HUB/phase0]
Checks:
  1 declarations: well formed, invariant-preserving on every admissible state, never agent state, publicly
    allowed effect values, at most two entity fields per world, window = (requested_at, execute_at), one-shot
    (so the no-change branch always exists)
  2 hidden tape: every realized event lies strictly inside the delay-2 window at a half-tick and its guard holds
    in the actual state at its time (it really happens); delay 0 realizes nothing
  3 initial support (public view at the request time) contains the actual initial state on the closed scope:
    relevant fields of both goals and every field a declaration reads or writes
  4 P2 requests from public inputs: 1 or 2 relevant facts per goal copy, equal to the allocation's intended
    status (prov / unres), budget never exhausted
  5 allocation counts by intended label; every changing world declares 1-2 transitions
  6 reference only (no controller): delayed-changing goal copies with and without a guaranteed candidate both
    occur; opportunities at the actual action time (environment evaluator) in every condition; candidate-family
    coverage gaps (independent optimum from both solvers outside the menu) listed separately from infeasibility
  7 public/hidden separation: no truth, tape, seed or label key in the public file; goal copies carry no hidden key
  8 stable-condition parity with 1.11.0: every committed 1.11.0 scoped trajectory (24 worlds x 2 goals x
    structured/text, real extractions) replayed with the 1.12.0 temporal projection (stable, delay 1) and the
    carry-forward ablation reproduces queried, plan, success, invalid attempt and utility
"""
import argparse
import collections
import json
import os
import sys
from pathlib import Path

from _bootstrap import ROOT  # noqa: F401
from dream_core import localpaths as LP  # public release: local paths from environment
from ectx import keycheck, world as ectx_world
from tempo import freshgen as FG, freshness as F, freshref as FREF, policy as P, recovery as R, text_channel as TC, \
    transfer as T

RUNS = Path(os.environ.get("DREAM_RUNS", f"{LP.RUNS}"))
DEPREC = RUNS / "temporal-dependency-recovery-20261105-170340"
HIDDEN_KEYS = {"truth", "tape", "seed", "labels", "intended_status", "records_v02"}


def load(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]


def solver_goal(goal):
    return {"item": goal["item"], "place": goal["place"]} if goal["kind"] == "deliver" else \
        {"slot": goal["slot"], "min_rating": goal["min_rating"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", required=True)
    ap.add_argument("--set", required=True)
    ap.add_argument("--out")
    a = ap.parse_args()
    hub = Path(a.hub)
    out = Path(a.out) if a.out else hub / "phase0"
    out.mkdir(parents=True, exist_ok=True)
    pubs = load(hub / "data" / "public" / f"{a.set}-worlds.jsonl")
    hids = {h["world_id"]: h for h in load(hub / "data" / "hidden" / f"{a.set}-hidden.jsonl")}
    rows = {r[0]: (d, r) for d, r, _ in FG.specs(a.set, 0, smoke=a.set == "freshsmoke")}
    res, failures = {}, []

    def check(cond, msg):
        if not cond:
            failures.append(msg)
        return cond

    # 1 declarations
    nfields, ndecl = {}, {}
    for pub in pubs:
        fs = set()
        for tr in pub["transitions"]:
            try:
                F.check_declaration(pub["spec"], tr, pub["registry_allowed"])
            except F.DeclarationError as e:
                check(False, f"{pub['world_id']}: {e}")
            check(tr["window"] == {"from": "requested_at", "to": "execute_at"} and tr.get("max_occurrences") == 1,
                  f"{pub['world_id']} {tr['id']}: window/occurrence")
            fs |= set(tr["guard"]) | set(tr["effect"])
        nfields[pub["world_id"]], ndecl[pub["world_id"]] = len(fs), len(pub["transitions"])
        check(1 <= len(pub["transitions"]) <= 2 and len(fs) <= 2, f"{pub['world_id']}: {len(fs)} fields")
    res["1_declarations"] = {"worlds": len(pubs), "transitions_per_world": dict(collections.Counter(ndecl.values())),
                             "entity_fields_per_world": dict(collections.Counter(nfields.values())),
                             "invariant_preserving": "all (exhaustive over admissible states of the involved fields)"}
    # 2 tape
    n_ev = 0
    for pub in pubs:
        hid = hids[pub["world_id"]]
        ep, gc, env_ep = FG.goal_copy(pub, hid, "A")
        for d in F.DELAYS:
            clk = F.make_clock(d)
            env = F.Environment(env_ep, pub["transitions"], hid["tape"], clk)
            _, applied = env.state_at(clk["execute_at"])
            if d == 0:
                check(applied == [], f"{pub['world_id']}: event realized with delay 0")
            else:
                check(len(applied) == len(hid["tape"]), f"{pub['world_id']}: tape event did not occur {hid['tape']} {applied}")
                check(all((e["at"] * 2) % 2 == 1 for e in applied), f"{pub['world_id']}: event not at a half tick")
                n_ev += len(applied)
    res["2_tape"] = {"realized_events_delay2": n_ev,
                     "worlds_no_change_realized": sum(not hids[p["world_id"]]["tape"] for p in pubs)}
    # 3 support contains the actual initial state on the closed scope; 4 requests; 7 separation
    q_counts, intended_ok, cover = collections.Counter(), 0, 0
    for pub in pubs:
        hid = hids[pub["world_id"]]
        check(not (HIDDEN_KEYS & set(pub)), f"{pub['world_id']}: hidden key in public file")
        eng = R.engine_from(pub, None, "v")
        v = eng.view("earlier", F.REQUEST_AT, cutoff=F.REQUEST_AT)
        scope = set()
        for role in ("A", "B"):
            ep, gc, _ = FG.goal_copy(pub, hid, role)
            check(not (HIDDEN_KEYS & set(ep)), f"{ep['episode_id']}: hidden key in goal copy")
            scope |= set(gc["relevant"])
            req = F.p2_request(ep, gc)
            q_counts[len(req["fields"])] += 1
            check(1 <= len(req["fields"]) <= 2 and not req["budget_exhausted"], f"{ep['episode_id']}: request {req}")
            want = [f for f in gc["relevant"] if hid["intended_status"].get(f, "ver") != "ver"]
            intended_ok += check(req["fields"] == want, f"{ep['episode_id']}: request {req['fields']} != intended {want}")
        for tr in pub["transitions"]:
            scope |= set(tr["guard"]) | set(tr["effect"])
        for f in scope:
            ok = f in v["op_options"] and hid["truth"][f] in v["op_options"][f]
            cover += check(ok, f"{pub['world_id']}: initial support misses actual {f}={hid['truth'][f]}")
    res["3_initial_support_contains_actual"] = f"{cover} closed-scope fields, all covered" if not failures else cover
    res["4_requests"] = {"fields_per_goal_copy": dict(q_counts), "equal_to_intended_status": f"{intended_ok}/{2 * len(pubs)}"}
    res["7_public_hidden_separation"] = "no hidden key in public worlds or goal copies"
    # 5 allocation
    lab = collections.Counter(hids[p["world_id"]]["labels"][r] for p in pubs for r in ("A", "B"))
    res["5_allocation"] = {"labels": dict(sorted(lab.items())),
                           "by_domain": {d: sum(p["domain"] == d for p in pubs) for d in ("delivery", "assembly")}}
    # 6 reference-only checks and coverage at the actual action time
    has, none_, opp, gaps = 0, 0, collections.Counter(), []
    for pub in pubs:
        hid = hids[pub["world_id"]]
        domain, row = rows[pub["world_id"]]
        w = FG.build(row, domain, hid["seed"], a.set)[0]
        for role in ("A", "B"):
            ep, gc, env_ep = FG.goal_copy(pub, hid, role)
            req = F.p2_request(ep, gc)
            for env_kind in F.ENVS:
                for d in F.DELAYS:
                    clk = F.make_clock(d)
                    trs = pub["transitions"] if env_kind == "changing" else []
                    env = F.Environment(env_ep, trs, hid["tape"] if trs else [], clk)
                    led = F.new_ledger("v")
                    _, rec = F.sensor_query(env, led, "v", req["fields"], F.REQUEST_AT, d)
                    rf = FREF.reference_for(ep, gc, rec, trs, clk)
                    if env_kind == "changing" and d == 2:
                        has += rf["choice"] is not None
                        none_ += rf["choice"] is None
                    sx, _ = env.state_at(clk["execute_at"])
                    valid = F.valid_plans_at(ep, gc, sx)
                    opp[f"{env_kind}|d{d}"] += bool(valid)
                    static, state, _ = w.to_planner(sx)
                    sg = solver_goal(gc["goal"])
                    ground = (ectx_world.ground_delivery if domain == "delivery" else ectx_world.ground_assembly)(
                        static, state, sg)
                    o1 = ground.optimum()[0]
                    o2 = keycheck.optimum(domain, static, {"state": state, "goal": sg})
                    check(o1 == o2, f"{ep['episode_id']}: solver optima differ")
                    best = min((P.plan_cost(ep["spec"], gc["plans"][k]) for k in valid), default=None)
                    if best != o1:
                        gaps.append({"goal_copy": ep["episode_id"], "condition": f"{env_kind}|d{d}", "menu_best": best,
                                     "independent_optimum": o1})
    check(has > 0 and none_ > 0, f"delayed-changing: reference guaranteed {has}, none {none_}")
    res["6_reference_and_coverage"] = {
        "delayed_changing_reference_has_guaranteed": has, "delayed_changing_reference_has_none": none_,
        "menu_feasible_at_action_time": dict(opp),
        "candidate_family_coverage_gaps": len(gaps), "gaps": gaps,
        "note": "a gap is a condition where a valid plan exists outside the supplied menu (not infeasibility)"}
    # 8 parity with 1.11.0
    if (DEPREC / "analysis-deprec" / "trajectories.jsonl").exists():
        old = {(t["world"], t["role"], t["channel"]): t for t in load(DEPREC / "analysis-deprec" / "trajectories.jsonl")
               if t["contract"] == "scoped"}
        eps = load(DEPREC / "data" / "deprec-episodes.jsonl")
        gold = {g["call_id"]: g for g in load(DEPREC / "data" / "deprec-gold.jsonl")}
        recs = {}
        for p in (DEPREC / "stages" / "main" / "calls").glob("*.json"):
            r = json.loads(p.read_text()); recs[r["call_id"]] = r
        same, n, diffs = 0, 0, []
        for ep0 in eps:
            cids = [f"{ep0['episode_id']}|prose|r{k}" for k in range(1, len(ep0["records_v02"]) + 1)]
            raws = [recs[c]["raw"] if c in recs and recs[c]["status"] == "ok" else None for c in cids]
            ch = TC.build_channel(ep0, raws, [gold[c]["registry"] for c in cids], ep0["prose_texts"])
            for role in ("A", "B"):
                ge, gc0 = T.goal_episode(ep0, role)
                gc = R.context(ge, gc0["goal"])
                for chn in ("structured", "text"):
                    chan = None if chn == "structured" else ch
                    clk = F.make_clock(1)
                    req = F.p2_request(ge, gc, chan)
                    o = F.run(ge, gc, req, "stable", [], F.Environment(ge, [], [], clk), clk, channel=chan)
                    ref_ = old[(ep0["episode_id"], role, chn)]
                    for p in F.PROJECTIONS:
                        n += 1
                        got = tuple(o[p][k] for k in ("queried", "plan", "success", "invalid_attempt", "utility"))
                        want = tuple(ref_[k] for k in ("queried", "plan", "success", "invalid_attempt", "utility"))
                        if got == want:
                            same += 1
                        else:
                            diffs.append({"world": ep0["episode_id"], "role": role, "channel": chn, "projection": p,
                                          "got": got, "want": want})
        check(not diffs, f"1.11.0 parity: {len(diffs)} differences")
        rec_worlds = ["deprec-ass-verified_settled-0|A", "deprec-ass-corrected-0|B", "deprec-ass-no_plan-0|B",
                      "deprec-del-verified_settled-1|B"]
        res["8_parity_1.11.0"] = {"replayed": n, "identical": same, "differences": diffs,
                                  "includes_the_four_recovery_worlds": rec_worlds,
                                  "compared": "queried, plan, success, invalid_attempt, utility vs 1.11.0 scoped"}
    else:
        check(False, "1.11.0 hub missing: parity not checked")
    res["failures"] = failures
    res["pass"] = not failures
    (out / "VALIDATION.json").write_text(json.dumps(res, indent=1, default=str) + "\n")
    L = [f"# V1.12.0 pre-run validation ({a.set})", "", f"**{'PASS' if not failures else 'FAIL'}** "
         f"({len(failures)} failures). No model call; no controller output on the committed panel was compared.", ""]
    for k, v in res.items():
        if k in ("failures", "pass"):
            continue
        L.append(f"## {k}")
        L.append("```")
        L.append(json.dumps(v, indent=1, default=str)[:4000])
        L.append("```")
    if failures:
        L += ["## Failures", *[f"- {f}" for f in failures]]
    (out / "VALIDATION.md").write_text("\n".join(L) + "\n")
    print("PASS" if not failures else f"FAIL {len(failures)}: {failures[:5]}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
