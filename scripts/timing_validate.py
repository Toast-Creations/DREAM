"""Pre-run validation for V1.13.0 (no model; no comparison of controller outputs on the committed panel).
Usage: timing_validate.py --hub HUB --set timing [--out HUB/phase0]
Checks:
  1 declarations: well formed, invariant-preserving, no agent state, publicly allowed values, <= 2 fields per world,
    fixed numeric window (12, 14), one-shot (no-change branch exists)
  2 fixed environment: every tape event at a half-tick inside (12, 14) happens; the actual pre-action state is
    identical for every schedule (t = 2 and t = 4); stable variants realize nothing; the sensor's measured value at
    t = 0 and t = 2 is the actual environment value then
  3 initial support (public view at the origin) contains the actual initial state on the closed scope
  4 P2 request from public input at t = 0: 1 or 2 facts per goal copy, equal to the intended status
  5 allocation counts by intended label
  6 reference only: DEFER-changing goal copies with and without a guaranteed candidate both occur; EARLY likewise
  7 public/hidden separation
  8 compatibility: (a) the 1.12.0 scored panel re-run through the unchanged 1.12.0 code reproduces its 384 stored
    trajectories (plan, utility, states); (b) TIMING EARLY on the 1.12.0 panel equals 1.12.0 temporal delay 2 in
    both environments (96 trajectories: states, plan, utility, success)
"""
import argparse
import collections
import json
import os
import sys
from pathlib import Path

from _bootstrap import ROOT  # noqa: F401
from dream_core import localpaths as LP  # public release: local paths from environment
from tempo import freshgen as FG, freshness as F, freshref as FREF, recovery as R, timing as TM, timinggen as TG

RUNS = Path(os.environ.get("DREAM_RUNS", f"{LP.RUNS}"))
FRESH = RUNS / "temporal-observation-freshness-20261105-213302"
HIDDEN_KEYS = {"truth", "tape", "seed", "labels", "intended_status", "records_v02"}


def load(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]


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
    res, failures = {}, []

    def check(cond, msg):
        if not cond:
            failures.append(msg)
        return cond

    # 1
    nf = collections.Counter()
    for pub in pubs:
        fs = set()
        for tr in pub["transitions"]:
            try:
                F.check_declaration(pub["spec"], tr, pub["registry_allowed"])
            except F.DeclarationError as e:
                check(False, f"{pub['world_id']}: {e}")
            check(tr["window"] == {"lo": 12, "hi": 14} and tr.get("max_occurrences") == 1, f"{pub['world_id']}: window")
            fs |= set(tr["guard"]) | set(tr["effect"])
        nf[len(fs)] += 1
        check(1 <= len(pub["transitions"]) <= 2 and len(fs) <= 2, f"{pub['world_id']}: scope")
    res["1_declarations"] = {"worlds": len(pubs), "entity_fields_per_world": dict(nf), "window": [12, 14]}
    # 2
    n_ev = 0
    for pub in pubs:
        hid = hids[pub["world_id"]]
        _, _, env_ep = TG.goal_copy(pub, hid, "A")
        for env_kind in TM.ENVS:
            shas, apps = set(), set()
            for s in TM.ORDER:
                sc = TM.schedule_clock(s)
                env = TM.environment(env_ep, env_kind, pub["transitions"], hid["tape"], sc)
                sx, applied = env.state_at(sc["execute_at"])
                shas.add(json.dumps(sorted(sx.items())))
                apps.add(json.dumps(applied))
                if env_kind == "changing":
                    check(len(applied) == len(hid["tape"]) and all((e["at"] * 2) % 2 == 1 and 12 < e["at"] < 14
                                                                   for e in applied), f"{pub['world_id']}: tape")
                else:
                    check(not applied, f"{pub['world_id']}: stable realized an event")
            check(len(shas) == 1 and len(apps) == 1, f"{pub['world_id']} {env_kind}: pre-action state differs by schedule")
            if env_kind == "changing":
                n_ev += len(hid["tape"])
    res["2_fixed_environment"] = {"realized_events": n_ev, "worlds_without_realized_change":
                                  sum(not hids[p["world_id"]]["tape"] for p in pubs),
                                  "preaction_state_identical_across_schedules": "all worlds, both variants"}
    # 3, 4, 7
    qc, ok_int, cover = collections.Counter(), 0, 0
    for pub in pubs:
        hid = hids[pub["world_id"]]
        check(not (HIDDEN_KEYS & set(pub)), f"{pub['world_id']}: hidden key in public file")
        v = R.engine_from(pub, None, "v").view("earlier", TM.ORIGIN, cutoff=TM.ORIGIN)
        scope = set()
        for role in ("A", "B"):
            ep, gc, _ = TG.goal_copy(pub, hid, role)
            check(not (HIDDEN_KEYS & set(ep)), f"{ep['episode_id']}: hidden key")
            scope |= set(gc["relevant"])
            req = F.p2_request(ep, gc)
            qc[len(req["fields"])] += 1
            want = [f for f in gc["relevant"] if hid["intended_status"].get(f, "ver") != "ver"]
            check(1 <= len(req["fields"]) <= 2 and not req["budget_exhausted"], f"{ep['episode_id']}: request")
            ok_int += check(req["fields"] == want, f"{ep['episode_id']}: request {req['fields']} != {want}")
        for tr in pub["transitions"]:
            scope |= set(tr["guard"]) | set(tr["effect"])
        for f in scope:
            cover += check(f in v["op_options"] and hid["truth"][f] in v["op_options"][f],
                           f"{pub['world_id']}: support misses {f}")
    res["3_initial_support_contains_actual"] = f"{cover} closed-scope fields covered"
    res["4_requests"] = {"fields_per_goal_copy": dict(qc), "equal_to_intended": f"{ok_int}/{2 * len(pubs)}"}
    res["7_public_hidden_separation"] = "no hidden key in public worlds or goal copies"
    # 5
    lab = collections.Counter(hids[p["world_id"]]["labels"][r] for p in pubs for r in ("A", "B"))
    res["5_allocation"] = {"labels": dict(sorted(lab.items()))}
    # 6 reference only
    cnt = collections.Counter()
    for pub in pubs:
        hid = hids[pub["world_id"]]
        for role in ("A", "B"):
            ep, gc, env_ep = TG.goal_copy(pub, hid, role)
            req = F.p2_request(ep, gc)
            for s in TM.ORDER:
                sc = TM.schedule_clock(s)
                env = TM.environment(env_ep, "changing", pub["transitions"], hid["tape"], sc)
                led = F.new_ledger("v")
                _, rec = F.sensor_query(env, led, "v", req["fields"], sc["requested_at"], TM.SENSOR_DELAY)
                actual_m = env.state_at(sc["measured_at"])[0]
                check(all(r["value"] == actual_m[r["field"]] for r in rec), f"{ep['episode_id']} {s}: sensor value")
                rf = FREF.reference_for(ep, gc, rec, pub["transitions"], TM.projection_clock(sc))
                cnt[f"{s}|{'has' if rf['choice'] is not None else 'none'}"] += 1
    check(cnt["DEFER|has"] > 0 and cnt["DEFER|none"] > 0, f"DEFER reference counts {dict(cnt)}")
    res["6_reference_changing"] = dict(sorted(cnt.items()))
    # 8 compatibility
    if (FRESH / "stages" / "main" / "trajectories.jsonl").exists():
        sys.path.insert(0, str(Path(__file__).parent))
        import fresh_run
        fpubs = load(FRESH / "data" / "public" / "fresh-worlds.jsonl")
        fhids = load(FRESH / "data" / "hidden" / "fresh-hidden.jsonl")
        stored = {(t["world"], t["role"], t["env"], t["delay"], t["projection"]): t
                  for t in load(FRESH / "stages" / "main" / "trajectories.jsonl")}
        traj = fresh_run.run_panel(fpubs, fhids)[0]
        diff_a = [k for t in traj for k in [(t["world"], t["role"], t["env"], t["delay"], t["projection"])]
                  if (t["plan"], t["utility"], t["states_sha256"]) != (stored[k]["plan"], stored[k]["utility"],
                                                                     stored[k]["states_sha256"])]
        check(not diff_a and len(traj) == len(stored) == 384, f"1.12.0 replay differences {len(diff_a)}")
        diff_b, n_b = [], 0
        fh = {h["world_id"]: h for h in fhids}
        for pub0 in fpubs:
            pub = dict(pub0, transitions=TM.fixed_windows(pub0["transitions"]))
            for role in ("A", "B"):
                ep, gc, env_ep = FG.goal_copy(pub, fh[pub0["world_id"]], role)
                req = F.p2_request(ep, gc)
                for env_kind in TM.ENVS:
                    new = TM.run(ep, gc, req, env_kind, pub["transitions"], env_ep, fh[pub0["world_id"]]["tape"], "EARLY")
                    old = stored[(pub0["world_id"], role, env_kind, 2, "temporal")]
                    n_b += 1
                    if (new["states_sha256"], new["plan"], new["utility_base"], new["success"]) != \
                            (old["states_sha256"], old["plan"], old["utility"], old["success"]):
                        diff_b.append((pub0["world_id"], role, env_kind))
        check(not diff_b, f"EARLY vs 1.12.0 temporal d2 differences {diff_b[:5]}")
        res["8_compatibility"] = {"1.12.0_replay": f"{len(traj) - len(diff_a)}/{len(traj)} identical",
                                  "EARLY_vs_1.12.0_temporal_d2": f"{n_b - len(diff_b)}/{n_b} identical"}
    else:
        check(False, "1.12.0 hub missing")
    res["failures"], res["pass"] = failures, not failures
    (out / "VALIDATION.json").write_text(json.dumps(res, indent=1, default=str) + "\n")
    L = [f"# V1.13.0 pre-run validation ({a.set})", "", f"**{'PASS' if not failures else 'FAIL'}** ({len(failures)} "
         "failures). No model call; no controller output on the committed panel was compared.", ""]
    for k, v in res.items():
        if k not in ("failures", "pass"):
            L += [f"## {k}", "```", json.dumps(v, indent=1, default=str)[:3000], "```"]
    if failures:
        L += ["## Failures", *[f"- {f}" for f in failures]]
    (out / "VALIDATION.md").write_text("\n".join(L) + "\n")
    print("PASS" if not failures else f"FAIL {len(failures)}: {failures[:5]}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
