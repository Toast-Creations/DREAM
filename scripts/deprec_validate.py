"""Pre-run checks for V1.11.0 (no model). Writes OUT/VALIDATION.{json,md}; exits non-zero if any check fails.

Usage: deprec_validate.py --hub HUB --set deprec [--out HUB/phase0] [--samples 300]
Checks:
  1 goal eligibility; repaired relevance (recovery.context, shared predicate table) equals the 1.10.0 rule on every
    goal clone; relevant fields disjoint across goals; agent reads are declared pre-action facts
  2 candidate legality: on every true state the shared-table executor, solver 1 (ectx.world) and solver 2
    (ectx.keycheck) agree on validity and cost of every candidate
  3 menu coverage: cheapest valid candidate vs both solvers' independent optimum; every gap is listed as a
    candidate-family coverage gap with its independent optimum (not an infeasible world)
  4 shared definitions and invariants:
      a true states admissible and complete for every field a candidate reads
      b the declared agent state is stated in the fixed facts of every prompt; no record describes an action of yours
      c every registered field's public values are admissible (phase-independent); every holder slot of an
        orderable part is a registered field
      d declared prerequisite reads are complete: on sampled admissible states (pre- and post-action agent states),
        changing a field outside a prerequisite's declared reads never changes its value
      e joint admissibility equals per-field admissibility given the agent state
  5 dependency sensitivity over the FULL engine domains (including "carried by you" and connector-incompatible
    parts): samples are classified by the shared admissibility test (the inadmissible share is reported, not hidden);
    on admissible samples, varying a non-relevant field over its admissible values never changes any candidate's
    outcome, and every relevant field changes one in some state
  6 isolation: extraction prompts rebuilt from each goal clone equal the committed calls; no goal token
  7 structured reference (no model): P2 strict vs scoped per goal (negative control: no history conflict, so the
    rule should change nothing), earlier view preserved, receipts identical across contracts, budget
  8 versioned-repair parity: the strict contract against 1.9.0/1.9.1 (216 trajectories) and 1.10.0 (288, with the
    committed real extractions); every difference must be explained by a repair category (an invariant-excluded
    value, or a prerequisite read of an absent field) and is listed
"""
import argparse
import collections
import glob
import itertools
import json
import os
import random
import sys
from pathlib import Path

from _bootstrap import ROOT  # noqa: F401
from dream_core import localpaths as LP  # public release: local paths from environment
from ectx import keycheck, world as ectx_world
from tempo import agentstate as AS, engine as E, goals as GL, history as Hm, policy as P, recovery as R, \
    text_channel as TC, transfer as T

RUNS = Path(os.environ.get("DREAM_RUNS", f"{LP.RUNS}"))
GOALTR = "temporal-deferred-goal-20261105-154052"
CMP = ("queried", "plan", "success", "invalid_attempt", "utility")


def load(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]


def outcome(ep, gc, s):
    table = AS.actions(ep["spec"])
    out = []
    for p in gc["plans"].values():
        st, ok = dict(s), True
        for step in p:
            _, ok, nxt = AS.evaluate(ep["spec"], st, list(step), table)
            if not ok:
                break
            st = nxt
        out.append(ok and GL.goal_ok(ep["world"], gc["goal"], st))
    return tuple(out)


def solver_goal(goal):
    return {"item": goal["item"], "place": goal["place"]} if goal["kind"] == "deliver" else \
        {"slot": goal["slot"], "min_rating": goal["min_rating"]}


def repair_cause(new_traj, old_ep, channel):
    """Why a strict 1.11.0 trajectory may differ from the frozen one: an invariant-excluded value in the belief, or a
    prerequisite read of an absent field (conflicted / never described) along some candidate."""
    causes = []
    if new_traj["invariant_before"] or new_traj["invariant_at_decision"]:
        causes.append("invariant_excluded_value")
    eng = R.engine_from(old_ep, channel, "cause")
    v = eng.view("current", P.DECIDE)
    spec, table = old_ep["spec"], AS.actions(old_ep["spec"])
    for s in v["states"]:
        for p in GL.candidate_plans(old_ep["world"], old_ep["domain"], new_traj["_goal"]).values():
            cur = dict(s)
            for st in p:
                if AS.missing_reads(spec, cur, list(st), table):
                    causes.append("absent_field_read")
                    return causes
                _, ok, cur = AS.evaluate(spec, cur, list(st), table)
                if not ok:
                    break
    return causes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", required=True)
    ap.add_argument("--set", default="deprec")
    ap.add_argument("--out")
    ap.add_argument("--samples", type=int, default=300)
    a = ap.parse_args()
    hub = Path(a.hub)
    out = Path(a.out) if a.out else hub / "phase0"
    out.mkdir(parents=True, exist_ok=True)
    eps = load(hub / "data" / f"{a.set}-episodes.jsonl")
    calls = {c["call_id"]: c for c in load(hub / "data" / f"{a.set}-calls.jsonl")}
    fails, res = [], collections.OrderedDict()

    def check(cond, msg):
        if not cond:
            fails.append(msg)

    def ctxs(ep):
        for role in ("A", "B"):
            ge, gc_old = T.goal_episode(ep, role)
            yield role, ge, gc_old, R.context(ge, gc_old["goal"])
    # 1 eligibility and relevance
    elig, rel_same = 0, 0
    for ep in eps:
        spec, wd, rel = ep["spec"], ep["world"], {}
        for role, ge, gco, gc in ctxs(ep):
            g = gc["goal"]
            if g["kind"] == "deliver":
                ok = g["item"] in spec["crates"] and g["item"] not in spec["non_portable"] and g["place"] in spec["places"]
            else:
                pt = spec["parts"].get(g["part"])
                ok = g["slot"] in spec["slots"] and pt is not None and pt["type"] == spec["slots"][g["slot"]] and \
                    pt["rating"] >= g["min_rating"]
            check(ok, f"{ge['episode_id']}: goal not fully specified")
            elig += ok
            check(gc["relevant"] == gco["relevant"], f"{ge['episode_id']}: repaired relevance differs from 1.10.0")
            rel_same += gc["relevant"] == gco["relevant"]
            check(set(gc["agent_reads"]) <= set(AS.declared_agent_state(spec)), f"{ge['episode_id']}: agent reads")
            rel[role] = set(gc["relevant"])
        check(not (rel["A"] & rel["B"]), f"{ep['episode_id']}: goals share relevant fields")
        if ep["domain"] == "assembly":
            g = ep["goals"]["B"]
            q = [p for p in (wd["e"], wd["e2"]) if spec["parts"][p]["rating"] >= g["min_rating"]]
            check(len(q) == 1, f"{ep['episode_id']}: B threshold admits {q}")
    res["1_eligibility"] = {"goals_fully_specified": f"{elig}/{2 * len(eps)}",
                            "repaired_relevance_equals_1.10.0_rule": f"{rel_same}/{2 * len(eps)}",
                            "agent_reads": "delivery: agent.at, agent.hands (declared pre-action facts); assembly: none"}
    # 2 + 3 legality and menu coverage
    agree, gaps, n_plans = 0, [], 0
    for ep in eps:
        w, _ = T.build(ep["episode_id"], ep["domain"], ep["a_type"], ep["b_type"], ep["b_j"], ep["a_item_is_x"],
                       ep["seed"], a.set)
        for role, ge, _, gc in ctxs(ep):
            static, state, _ = w.to_planner(ep["truth"])
            sg = solver_goal(gc["goal"])
            ground = (ectx_world.ground_delivery if ep["domain"] == "delivery" else ectx_world.ground_assembly)(
                static, state, sg)
            valid, best = set(R.true_valid_plans(ge, gc)), None
            for k, p in gc["plans"].items():
                n_plans += 1
                s1 = ground.simulate([tuple(s) for s in p])
                s2 = keycheck.run_plan(ep["domain"], static, {"state": state, "goal": sg}, p)
                c = P.plan_cost(ep["spec"], p)
                trio = ((k in valid), bool(s1[0]), bool(s2[0]))
                ok = len(set(trio)) == 1 and (not s1[0] or (s1[1] == c and s2[1] == c))
                check(ok, f"{ge['episode_id']} {k}: executor/solver disagreement {trio}")
                agree += ok
                if k in valid and (best is None or c < best[0]):
                    best = (c, k)
            o1, o2 = ground.optimum()[0], keycheck.optimum(ep["domain"], static, {"state": state, "goal": sg})
            check(o1 == o2, f"{ge['episode_id']}: optima differ {o1} {o2}")
            if (best[0] if best else None) != o1:
                gaps.append({"goal_clone": ge["episode_id"], "type": ge["type"], "menu_best": best,
                             "independent_optimum": o1})
    res["2_legality"] = {"plans_checked": n_plans, "three_way_agreement": agree}
    res["3_menu_coverage"] = {"candidate_family_coverage_gaps": len(gaps), "list": gaps,
                              "note": "a gap is a goal clone with a valid plan outside the supplied candidate menu; "
                                      "a decline there is correct relative to the menu, not evidence of infeasibility"}
    # 4 shared definitions and invariants
    rng = random.Random(20261105)
    n4 = collections.Counter()
    for ep in eps:
        spec = E.WorldSpec(ep["spec"])
        try:
            R.truth_state(ep)
            for _, ge, _, gc in ctxs(ep):
                R.true_valid_plans(ge, gc)
            n4["a_truth_admissible_complete"] += 1
        except AssertionError as e:
            check(False, f"{ep['episode_id']}: 4a {e}")
        users = [calls[f"{ep['episode_id']}|prose|r{k}"]["user"] for k in range(1, 7)]
        if ep["domain"] == "delivery":
            ok = all("with empty hands" in u and "You do not move unless you act" in u for u in users)
        else:
            ok = True
        ok = ok and not any(r["payload"].get("field") in AS.agent_fields(spec) for r in ep["records_v02"]
                            if r["kind"] != "initial")
        check(ok, f"{ep['episode_id']}: 4b declared agent state")
        n4["b_declared_agent_state"] += ok
        for f, vals in ep["registry_allowed"].items():
            adm = AS.admissible_values(spec, f)
            check(set(vals) <= set(adm), f"{ep['episode_id']}: 4c registry {f} has inadmissible {set(vals) - set(adm)}")
        for p in (spec.prices if spec.domain == "assembly" else []):
            for f in AS.actions(spec)["order"][0][2][2](p):
                check(f in ep["registry_allowed"], f"{ep['episode_id']}: 4c holder {f} not registered")
        n4["c_registry"] += 1
        # d declared reads complete
        table, fields = AS.actions(spec), AS.entity_fields(spec)
        agents = AS._agent_states(spec)
        args_of = {"take": [(c,) for c in spec.registry if spec.registry[c] == "crate"],
                   "put": [(c,) for c in spec.registry if spec.registry[c] == "crate"],
                   "go": [(x, y) for x, y, _ in spec.roads] if spec.domain == "delivery" else [],
                   "install": [(p, sl) for p in spec.parts for sl in spec.slots] if spec.domain == "assembly" else [],
                   "remove": [(sl,) for sl in spec.slots] if spec.domain == "assembly" else [],
                   "order": [(p,) for p in spec.parts] if spec.domain == "assembly" else []}
        bad_reads = 0
        for _ in range(40):
            ag = rng.choice(agents)
            s = dict(ag, **{f: rng.choice(AS.admissible_values(spec, f, ag)) for f in fields})
            if not AS.admissible(spec, s):
                continue
            for name, arglist in args_of.items():
                for args in arglist:
                    for pn, fn, rd in table[name][0]:
                        base, reads = fn(s, *args), set(rd(*args))
                        for f in fields + AS.agent_fields(spec):
                            if f in reads:
                                continue
                            for v in AS.domain(spec, f):
                                s2 = dict(s, **{f: v})
                                if AS.admissible(spec, s2) and fn(s2, *args) != base:
                                    bad_reads += 1
        check(bad_reads == 0, f"{ep['episode_id']}: 4d {bad_reads} undeclared prerequisite reads")
        n4["d_reads_complete"] += bad_reads == 0
        # e joint == per-field admissibility
        bad_e = 0
        for _ in range(200):
            ag = rng.choice(agents)
            s = dict(ag, **{f: rng.choice(spec.domain_values(f)) for f in fields})
            per = all(AS.admissible(spec, dict(ag, **{f: s[f]})) for f in fields)
            bad_e += per != AS.admissible(spec, s) and ag == AS.declared_agent_state(spec)
        check(bad_e == 0, f"{ep['episode_id']}: 4e joint admissibility differs from per-field")
        n4["e_unary_given_declared_agent"] += bad_e == 0
    res["4_shared_definitions"] = {k: f"{v}/{len(eps)}" for k, v in n4.items()}
    # 5 dependency sensitivity over full domains
    dep_bad, seen, inadm = 0, collections.Counter(), collections.Counter()
    for ep in eps:
        spec = E.WorldSpec(ep["spec"])
        fields, agent = AS.entity_fields(spec), AS.declared_agent_state(spec)
        adm = {f: AS.admissible_values(spec, f, agent) for f in fields}
        for role, ge, _, gc in ctxs(ep):
            rel, moved, n_ok = set(gc["relevant"]), set(), 0
            for _ in range(a.samples):
                s = dict(agent, **{f: rng.choice(spec.domain_values(f)) for f in fields})
                if not AS.admissible(spec, s):
                    inadm[ep["domain"]] += 1
                    continue
                n_ok += 1
                base = outcome(ge, gc, s)
                for f in fields:
                    if any(v != s[f] and outcome(ge, gc, dict(s, **{f: v})) != base for v in adm[f]):
                        moved.add(f)
            bad, missing = moved - rel, rel - moved
            check(not bad, f"{ge['episode_id']}: non-relevant fields change outcomes {sorted(bad)}")
            check(not missing, f"{ge['episode_id']}: relevant fields never change outcomes {sorted(missing)}")
            check(n_ok > 0, f"{ge['episode_id']}: no admissible samples")
            dep_bad += bool(bad or missing)
            seen[role] += len(rel & moved)
    res["5_dependency"] = {"samples_per_goal": a.samples, "goal_contexts_failing": dep_bad,
                           "relevant_fields_confirmed": dict(seen),
                           "inadmissible_samples_by_domain": dict(inadm),
                           "note": "sampled over the engine's full domains; inadmissible samples (e.g. a crate carried "
                                   "while the declared hands are empty) are classified by agentstate.admissible, the "
                                   "same test the engine view and the executor use"}
    # 6 isolation
    same = 0
    for ep in eps:
        w, mem = T.build(ep["episode_id"], ep["domain"], ep["a_type"], ep["b_type"], ep["b_j"], ep["a_item_is_x"],
                         ep["seed"], a.set)
        check(TC.prose_texts(w, mem) == ep["prose_texts"], f"{ep['episode_id']}: prose not reproduced")
        built = {role: TC.prompts(w, T.goal_episode(mem, role)[0]) for role in ("A", "B")}
        committed = [calls[f"{ep['episode_id']}|prose|r{k}"]["user"] for k in range(1, 7)]
        ok = built["A"] == built["B"] == committed and not any("Goal" in u or "goal" in u for u in committed)
        check(ok, f"{ep['episode_id']}: prompts differ across goal clones or name a goal")
        same += ok
    res["6_isolation"] = {"episodes_identical_packets": f"{same}/{len(eps)}"}
    # 7 structured reference
    util, diff, n7 = collections.Counter(), 0, 0
    for ep in eps:
        for role, ge, _, gc in ctxs(ep):
            x = R.run(ge, gc, "P2_selective")
            n7 += 1
            for con in R.CONTRACTS:
                r = x[con]
                util[f"{role}:{con}"] += r["utility"]
                check(r["earlier_view_preserved"] and r["unanchored_fields_unchanged"], f"{ge['episode_id']}: 7 views")
                check(len(r["queried"]) <= R.QUERY_BUDGET, "budget")
            check(x["strict"]["receipts_sha256"] == x["scoped"]["receipts_sha256"], "receipts differ")
            d = any(x["strict"][k] != x["scoped"][k] for k in CMP)
            diff += d
            check(not d, f"{ge['episode_id']}: structured strict and scoped differ")
    res["7_structured_reference"] = {"goal_clones": n7, "strict_vs_scoped_differences": diff,
                                     "p2_utility_totals": dict(util),
                                     "menu_feasible_by_goal": {role: sum(bool(R.true_valid_plans(*_ge(ep, role)))
                                                                         for ep in eps) for role in ("A", "B")}}
    # 8 versioned-repair parity
    par = collections.Counter()
    changed = []

    def compare(ep, gc_old, goal, chan, label, old_fn):
        nc = R.context(ep, goal)
        check(nc["relevant"] == gc_old, f"{label}: relevance")
        for pol in P.POLICIES:
            o = old_fn(pol)
            x = R.run(ep, nc, pol, channel=chan)
            for con in R.CONTRACTS:
                par[f"{con}:trajectories"] += 1
                if all(o[k] == x[con][k] for k in CMP):
                    par[f"{con}:identical"] += 1
                    continue
                if con == "scoped":
                    continue
                y = dict(x[con], _goal=goal)
                causes = repair_cause(y, ep, chan)
                check(bool(causes), f"{label} {pol}: unexplained strict difference")
                changed.append({"trajectory": f"{label}|{pol}", "old": {k: o[k] for k in CMP},
                                "new": {k: y[k] for k in CMP}, "causes": causes,
                                "invariant": y["invariant_before"]})
    for hubname, st in (("temporal-contract-policy-20261105-121257", "policy"),
                        ("temporal-text-policy-20261105-124150", "textpol")):
        old = load(RUNS / hubname / "data" / f"{st}-episodes.jsonl")
        recs, gold = {}, {}
        if st == "textpol":
            for p in (RUNS / hubname / "stages" / "main" / "calls").glob("*.json"):
                r = json.loads(p.read_text()); recs[r["call_id"]] = r
            gold = {g["call_id"]: g for g in load(RUNS / hubname / "data" / "textpol-gold.jsonl")}
        for ep in old:
            w, _ = P.build_episode_world(ep["episode_id"], ep["domain"], ep["type"], ep["seed"], ep["pool"])
            ep = dict(ep, registry_allowed={f: Hm.allowed_values(w, f) for f in Hm.registry_fields(w, ep["records_v02"])})
            chans = [("structured", None)]
            if st == "textpol":
                cids = [f"{ep['episode_id']}|prose|r{k}" for k in range(1, 7)]
                chans.append(("text", TC.build_channel(ep, [recs[c]["raw"] for c in cids],
                                                       [gold[c]["registry"] for c in cids], ep["prose_texts"])))
            for cname, ch in chans:
                compare(ep, ep["relevant"], GL.goal_a_of(ep), ch, f"{st}|{ep['episode_id']}|{cname}",
                        lambda pol, ep=ep, ch=ch: P.run_policy(ep, pol, channel=ch))
    gh = RUNS / GOALTR
    geps = load(gh / "data" / "goaltr-episodes.jsonl")
    ggold = {g["call_id"]: g for g in load(gh / "data" / "goaltr-gold.jsonl")}
    graw = {}
    for p in glob.glob(str(gh / "stages" / "main" / "calls" / "*.json")):
        r = json.loads(Path(p).read_text()); graw[r["call_id"]] = r["raw"]
    for ep in geps:
        cids = [f"{ep['episode_id']}|prose|r{k}" for k in range(1, 7)]
        ch = TC.build_channel(ep, [graw[c] for c in cids], [ggold[c]["registry"] for c in cids], ep["prose_texts"])
        for role in ("A", "B"):
            ge, gc = T.goal_episode(ep, role)
            for cname, c in (("structured", None), ("text", ch)):
                compare(ge, gc["relevant"], gc["goal"], c, f"goaltr|{ge['episode_id']}|{cname}",
                        lambda pol, ge=ge, gc=gc, c=c: GL.run_policy(ge, gc, pol, channel=c))
    res["8_repair_parity"] = {"counts": dict(par), "strict_changed": changed,
                              "rule": "strict must equal the frozen trajectory unless a repair category applies"}
    res["failures"] = fails
    (out / "VALIDATION.json").write_text(json.dumps(res, indent=1, default=str) + "\n")
    L = ["# V1.11.0 dependency parity and current-observation recovery: pre-run validation (generated)", ""]
    for k, v in res.items():
        if k == "failures":
            continue
        vv = {kk: vv for kk, vv in v.items() if kk not in ("list", "strict_changed")} if isinstance(v, dict) else v
        L.append(f"- **{k}**: {json.dumps(vv, default=str)}")
    L += ["", "Candidate-family coverage gaps (valid plans exist outside the menu):"]
    L += [f"- {g}" for g in res["3_menu_coverage"]["list"]]
    L += ["", "Strict trajectories changed by the repair (versioned; not a retrospective change to old runs):"]
    L += [f"- {c['trajectory']}: {c['old']} -> {c['new']}; causes {c['causes']}; invariant {json.dumps(c['invariant'])}"
          for c in changed]
    L += ["", f"Failures: {len(fails)}"] + [f"- {f}" for f in fails[:50]]
    (out / "VALIDATION.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))
    sys.exit(1 if fails else 0)


def _ge(ep, role):
    ge, gc = T.goal_episode(ep, role)
    return ge, R.context(ge, gc["goal"])


if __name__ == "__main__":
    main()
