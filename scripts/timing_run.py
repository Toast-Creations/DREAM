"""Run the V1.13.0 CPU panel (zero model calls): per base world, goal, environment and schedule one temporal
trajectory, its independent reference, scorer-side full-domain feasibility, and the hidden-tape leakage check.
Usage: timing_run.py --hub HUB --set SET --stage STAGE [--require-freeze]
Writes HUB/stages/STAGE/{trajectories,reference,requests,leakage,feasibility}.jsonl and RUN-META.json."""
import argparse
import json
import time
from pathlib import Path

from _bootstrap import ROOT
from dream_core.ledger import release_source_hash
from ectx import keycheck, world as ectx_world
from tempo import freshness as F, freshref as FREF, timing as TM, timinggen as TG

ROLES = ("A", "B")


def load(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]


def solver_goal(goal):
    return {"item": goal["item"], "place": goal["place"]} if goal["kind"] == "deliver" else \
        {"slot": goal["slot"], "min_rating": goal["min_rating"]}


def full_domain(w, domain, goal, s):
    static, state, _ = w.to_planner(s)
    sg = solver_goal(goal)
    ground = (ectx_world.ground_delivery if domain == "delivery" else ectx_world.ground_assembly)(static, state, sg)
    o1, o2 = ground.optimum()[0], keycheck.optimum(domain, static, {"state": state, "goal": sg})
    if o1 != o2:
        raise AssertionError("solver optima differ")
    return o1


def run_panel(pubs, hiddens, set_name):
    hid_by = {h["world_id"]: h for h in hiddens}
    rows = {r[0]: (d, r) for d, r, _ in TG.specs(set_name, 0, smoke=set_name.endswith("smoke"))}
    traj, refs, reqs, leak, feas = [], [], [], [], []
    for pub in pubs:
        hid = hid_by[pub["world_id"]]
        domain, row = rows[pub["world_id"]]
        w = TG.build(row, domain, hid["seed"], set_name)[0]
        trs = pub["transitions"]
        for role in ROLES:
            ep, gc, env_ep = TG.goal_copy(pub, hid, role)
            req = F.p2_request(ep, gc)  # once, at t = 0, before any schedule
            reqs.append({"world": pub["world_id"], "role": role, "relevant": gc["relevant"], **req})
            for env_kind in TM.ENVS:
                key0 = {"world": pub["world_id"], "domain": domain, "role": role, "env": env_kind}
                for s in TM.ORDER:
                    t = TM.run(ep, gc, req, env_kind, trs, env_ep, hid["tape"], s)
                    c0 = time.process_time()
                    rf = FREF.reference_for(ep, gc, t["receipts"], trs if env_kind == "changing" else [],
                                            t["projection_clock"])
                    refs.append(dict(key0, schedule=s, states=rf["states"], classes=rf["classes"], choice=rf["choice"],
                                     cpu_s=time.process_time() - c0))
                    traj.append(dict(t, **key0, relevant=gc["relevant"], label=hid["labels"][role]))
                sc = TM.schedule_clock("EARLY")
                env = TM.environment(env_ep, env_kind, trs, hid["tape"], sc)
                s0, s2 = env.state_at(TM.ORIGIN)[0], env.state_at(TM.WINDOW[1])[0]
                feas.append(dict(key0, optimum_at_origin=full_domain(w, domain, gc["goal"], s0),
                                 optimum_at_action=full_domain(w, domain, gc["goal"], s2)))
                if env_kind == "changing":
                    alts = {"realized": hid["tape"], "none": [],
                            "all": [{"transition": x["id"], "elapsed": 0.5 + i % 2} for i, x in enumerate(trs)],
                            "all_late": [{"transition": x["id"], "elapsed": 1.5} for x in trs]}
                    row_ = dict(key0, by_schedule={})
                    for s in TM.ORDER:
                        row_["by_schedule"][s] = {}
                        for name, tp in alts.items():
                            o = TM.run(ep, gc, req, env_kind, trs, env_ep, tp, s)
                            row_["by_schedule"][s][name] = {k: o[k] for k in ("receipts_sha256", "ledger_sha256",
                                                                              "states_sha256", "plan", "log_head")}
                            row_["by_schedule"][s][name]["candidates"] = o["candidates"]
                    leak.append(row_)
    return traj, refs, reqs, leak, feas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", required=True)
    ap.add_argument("--set", required=True)
    ap.add_argument("--stage", required=True)
    ap.add_argument("--require-freeze", action="store_true")
    a = ap.parse_args()
    hub = Path(a.hub)
    src = release_source_hash(ROOT)
    if a.require_freeze:
        fz = json.loads((hub / "config" / "FROZEN-PROTOCOL.json").read_text())
        if fz["source_sha256"] != src:
            raise SystemExit(f"source {src} differs from the frozen {fz['source_sha256']}")
    out = hub / "stages" / a.stage
    if (out / "trajectories.jsonl").exists():
        raise SystemExit(f"{out} already has trajectories")
    out.mkdir(parents=True, exist_ok=True)
    pubs = load(hub / "data" / "public" / f"{a.set}-worlds.jsonl")
    hids = load(hub / "data" / "hidden" / f"{a.set}-hidden.jsonl")
    t0, c0 = time.perf_counter(), time.process_time()
    traj, refs, reqs, leak, feas = run_panel(pubs, hids, a.set)
    meta = {"set": a.set, "stage": a.stage, "source_sha256": src, "trajectories": len(traj), "references": len(refs),
            "model_calls": 0, "wall_s": time.perf_counter() - t0, "cpu_s": time.process_time() - c0,
            "max_reachable_set": max(t["max_set"] for t in traj), "max_projection_cpu_s": max(t["cpu_s"] for t in traj),
            "limits": {"MAX_STATES": F.MAX_STATES, "CPU_LIMIT_S": F.CPU_LIMIT_S},
            "started": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    for name, rows in (("trajectories", traj), ("reference", refs), ("requests", reqs), ("leakage", leak),
                       ("feasibility", feas)):
        with open(out / f"{name}.jsonl", "w") as fh:
            for r in rows:
                fh.write(json.dumps(r, default=str, sort_keys=True) + "\n")
    (out / "RUN-META.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(json.dumps(meta))


if __name__ == "__main__":
    main()
