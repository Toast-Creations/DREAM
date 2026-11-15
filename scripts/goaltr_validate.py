"""Pre-run checks for the deferred-goal transfer study (no model). Writes OUT/VALIDATION.{json,md}; exits non-zero
if any check fails.

Usage: goaltr_validate.py --hub HUB --set goaltr [--out HUB/phase0] [--samples 300]
Checks:
  1 goal eligibility (fully specified targets; disjoint relevant fields; exactly one of E/E2 qualifies for B)
  2 candidate legality: on every episode's true state, each goal's candidate plans agree in validity and cost
    across engine v0.3 (environment), solver 1 (ectx.world) and solver 2 (ectx.keycheck)
  3 optimality and coverage: cheapest valid candidate vs the independent optimum of both solvers; every gap listed
  4 dependency correctness: varying a non-relevant registry field (over its public allowed values; "carried by
    you" excluded as agent-owned) never changes any candidate plan's outcome; each relevant field changes it in
    some sampled state
  5 isolation: the extraction prompts are rebuilt from each goal clone and are byte-identical to the committed
    calls; no prompt contains a goal statement
  6 structured run integrity: earlier-information view preserved, planning never changes the log (asserted),
    sensor within budget; feasibility / no-plan rates per goal
  7 original-goal parity: goal A on the committed 1.9.0 and 1.9.1 episodes (structured, and 1.9.1's saved text
    extractions) reproduces policy.run_policy exactly, and its relevant fields equal the old favoured fields
"""
import argparse
import collections
import json
import os
import random
import sys
from pathlib import Path

from _bootstrap import ROOT  # noqa: F401
from dream_core import localpaths as LP  # public release: local paths from environment
from ectx import keycheck, world as ectx_world
from tempo import engine as E, goals as GL, history as Hm, policy as P, text_channel as TC, transfer as T
from tempo.worlds import CARRIED

RUNS = Path(os.environ.get("DREAM_RUNS", f"{LP.RUNS}"))


def load(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]


def rebuild(ep, set_name):
    w, ep2 = T.build(ep["episode_id"], ep["domain"], ep["a_type"], ep["b_type"], ep["b_j"], ep["a_item_is_x"],
                     ep["seed"], set_name)
    assert json.dumps(ep2["reports"], sort_keys=True) == json.dumps(ep["reports"], sort_keys=True)
    return w, ep2


def outcome(ep, gc, s):
    env = E.Engine(ep["spec"])
    out = []
    for k, p in gc["plans"].items():
        st, ok = dict(s), True
        for step in p:
            _, allowed, eff = env._eval(st, list(step))
            if not allowed:
                ok = False
                break
            st = eff(st, *step[1:])
        out.append(ok and GL.goal_ok(ep["world"], gc["goal"], st))
    return tuple(out)


def solver_goal(goal):
    return {"item": goal["item"], "place": goal["place"]} if goal["kind"] == "deliver" else \
        {"slot": goal["slot"], "min_rating": goal["min_rating"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", required=True)
    ap.add_argument("--set", default="goaltr")
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
    # 1 eligibility
    elig = 0
    for ep in eps:
        spec, wd = ep["spec"], ep["world"]
        rel = {}
        for role, g in ep["goals"].items():
            if g["kind"] == "deliver":
                ok = g["item"] in spec["crates"] and g["item"] not in spec["non_portable"] and g["place"] in spec["places"]
            else:
                pt = spec["parts"].get(g["part"])
                ok = g["slot"] in spec["slots"] and pt is not None and pt["type"] == spec["slots"][g["slot"]] and \
                    pt["rating"] >= g["min_rating"]
            check(ok, f"{ep['episode_id']} {role}: goal not fully specified")
            rel[role] = set(T.goal_context(ep, role)["relevant"])
            elig += ok
        check(not (rel["A"] & rel["B"]), f"{ep['episode_id']}: goals share relevant fields")
        if ep["domain"] == "assembly":
            g = ep["goals"]["B"]
            q = [p for p in (wd["e"], wd["e2"]) if spec["parts"][p]["rating"] >= g["min_rating"]]
            check(len(q) == 1, f"{ep['episode_id']}: B threshold admits {q}")
    res["1_eligibility"] = {"goals_fully_specified": f"{elig}/{2 * len(eps)}"}
    # 2 + 3 legality, optimality, coverage
    agree, gaps, n_plans = 0, [], 0
    for ep in eps:
        w, _ = rebuild(ep, a.set)
        for role in ("A", "B"):
            ge, gc = T.goal_episode(ep, role)
            static, state, _ = w.to_planner(ep["truth"])
            sg = solver_goal(gc["goal"])
            ground = (ectx_world.ground_delivery if ep["domain"] == "delivery" else ectx_world.ground_assembly)(
                static, state, sg)
            valid = set(GL.true_valid_plans(ge, gc))
            best = None
            for k, p in gc["plans"].items():
                n_plans += 1
                s1 = ground.simulate([tuple(s) for s in p])
                s2 = keycheck.run_plan(ep["domain"], static, {"state": state, "goal": sg}, p)
                c_eng = P.plan_cost(ep["spec"], p)
                trio = ((k in valid), bool(s1[0]), bool(s2[0]))
                ok = len(set(trio)) == 1 and (not s1[0] or (s1[1] == c_eng and s2[1] == c_eng))
                check(ok, f"{ge['episode_id']} {k}: engine/solver disagreement {trio} {s1} {s2} {c_eng}")
                agree += ok
                if k in valid and (best is None or c_eng < best[0]):
                    best = (c_eng, k)
            o1 = ground.optimum()[0]
            o2 = keycheck.optimum(ep["domain"], static, {"state": state, "goal": sg})
            check(o1 == o2, f"{ge['episode_id']}: optima differ {o1} {o2}")
            if (best[0] if best else None) != o1:
                gaps.append({"episode": ge["episode_id"], "type": ge["type"], "candidate_best": best, "optimum": o1})
    res["2_legality"] = {"plans_checked": n_plans, "three_way_agreement": agree}
    res["3_coverage_gaps"] = {"n": len(gaps), "list": gaps,
                              "note": "declared family gaps: delivery item at C (no candidate); assembly slot holding a "
                                      "low part with the part not on hand (A: remove + order + install is not a "
                                      "candidate). Kept visible as no-plan."}
    # 4 dependency (sampled sensitivity)
    rng = random.Random(20261105)
    dep_bad, dep_relevant_seen = 0, collections.Counter()
    for ep in eps:
        allowed = {f: [v for v in vals if v != CARRIED] for f, vals in ep["registry_allowed"].items()}
        fields = list(allowed)
        for role in ("A", "B"):
            gc = T.goal_context(ep, role)
            rel = set(gc["relevant"])
            moved = set()
            for _ in range(a.samples):
                s = {f: rng.choice(allowed[f]) for f in fields}
                if ep["domain"] == "delivery":
                    s["agent.at"] = ep["world"]["you"]
                base = outcome(ep, gc, s)
                for f in fields:
                    for v in allowed[f]:
                        if v != s[f] and outcome(ep, gc, dict(s, **{f: v})) != base:
                            moved.add(f)
                            break
            bad = moved - rel
            missing = rel - moved
            check(not bad, f"{ep['episode_id']} {role}: non-relevant fields change outcomes {sorted(bad)}")
            check(not missing, f"{ep['episode_id']} {role}: relevant fields never change outcomes {sorted(missing)}")
            dep_bad += bool(bad or missing)
            dep_relevant_seen[role] += len(rel & moved)
    res["4_dependency"] = {"samples_per_goal": a.samples, "goal_contexts_failing": dep_bad,
                           "relevant_fields_confirmed": dict(dep_relevant_seen)}
    # 5 isolation
    same = 0
    for ep in eps:
        # in-memory rebuild (the episode file is written with sorted keys, which reorders multi-fact reports)
        w, mem = rebuild(ep, a.set)
        check([TC.prose_texts(w, mem)[k] for k in range(len(mem["records_v02"]))] == ep["prose_texts"],
              f"{ep['episode_id']}: committed prose texts not reproduced")
        built = {}
        for role in ("A", "B"):
            ge, _ = T.goal_episode(mem, role)
            built[role] = TC.prompts(w, ge)
        committed = [calls[f"{ep['episode_id']}|prose|r{k}"]["user"] for k in range(1, len(ep["records_v02"]) + 1)]
        ok = built["A"] == built["B"] == committed and not any("Goal" in u or "goal" in u for u in committed)
        check(ok, f"{ep['episode_id']}: prompts differ across goal clones or name a goal")
        same += ok
    res["5_isolation"] = {"episodes_identical_packets": f"{same}/{len(eps)}"}
    # 6 structured integrity
    rows = []
    for ep in eps:
        for role in ("A", "B"):
            ge, gc = T.goal_episode(ep, role)
            for pol in P.POLICIES:
                r = GL.run_policy(ge, gc, pol)
                rows.append(dict(r, role=role))
                check(r["earlier_view_preserved"], f"{ge['episode_id']} {pol}: earlier view changed")
                check(len(r["queried"]) <= P.QUERY_BUDGET, "budget")
    feas = {role: f"{sum(r['opportunity'] for r in rows if r['role'] == role and r['policy'] == 'P0_accepted')}/{len(eps)}"
            for role in ("A", "B")}
    res["6_structured"] = {"trajectories": len(rows), "earlier_view_preserved": sum(r["earlier_view_preserved"] for r in rows),
                           "feasible_by_goal": feas,
                           "utility_by_goal_policy": {f"{role}:{pol}": sum(r["utility"] for r in rows if r["role"] == role
                                                                            and r["policy"] == pol)
                                                      for role in ("A", "B") for pol in P.POLICIES}}
    # 7 parity with the 1.9.x committed episodes
    n_par = 0
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
            allowed = {f: Hm.allowed_values(w, f) for f in Hm.registry_fields(w, ep["records_v02"])}
            gc = GL.context(ep["world"], ep["domain"], GL.goal_a_of(ep), allowed)
            check(gc["relevant"] == ep["relevant"], f"{ep['episode_id']}: relevance parity")
            check(all(gc["plans"][k] == p for k, p in ep["world"]["plans"].items()), f"{ep['episode_id']}: plans")
            chans = [None]
            if st == "textpol":
                cids = [f"{ep['episode_id']}|prose|r{k}" for k in range(1, 7)]
                chans.append(TC.build_channel(ep, [recs[c]["raw"] for c in cids], [gold[c]["registry"] for c in cids],
                                              ep["prose_texts"]))
            for ch in chans:
                for pol in P.POLICIES:
                    x, y = P.run_policy(ep, pol, channel=ch), GL.run_policy(ep, gc, pol, channel=ch)
                    for k in GL.PARITY_EXTRA:
                        y.pop(k)
                    check(x == y, f"{ep['episode_id']} {pol}: trajectory parity")
                    n_par += x == y
    res["7_parity"] = {"trajectories_identical": n_par, "expected": 72 + 144}
    res["failures"] = fails
    (out / "VALIDATION.json").write_text(json.dumps(res, indent=1, default=str) + "\n")
    L = ["# Deferred-goal transfer: pre-run validation (generated)", ""]
    for k, v in res.items():
        if k in ("failures",):
            continue
        vv = {kk: vv for kk, vv in v.items() if kk != "list"} if isinstance(v, dict) else v
        L.append(f"- **{k}**: {json.dumps(vv, default=str)}")
    L += ["", "Coverage gaps:"] + [f"- {g}" for g in res["3_coverage_gaps"]["list"]]
    L += ["", f"Failures: {len(fails)}"] + [f"- {f}" for f in fails[:50]]
    (out / "VALIDATION.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
