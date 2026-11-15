"""Run the V1.12.0 CPU panel (zero model calls) and the independent reference for every trajectory.
Usage: fresh_run.py --hub HUB --set SET --stage STAGE [--require-freeze]
Per base world, goal copy (A/B), environment (stable/changing) and delay (0/2): one engine log, the frozen P2
request (computed once per world and goal from the initial structured view, cloned into every condition), one
set of receipts; then both projections (carry_forward, temporal). The reference is computed from public inputs
only and stored next to each trajectory. Writes HUB/stages/STAGE/{trajectories,reference,requests}.jsonl and
RUN-META.json."""
import argparse
import json
import time
from pathlib import Path

from _bootstrap import ROOT
from dream_core.ledger import release_source_hash
from tempo import freshgen as FG, freshness as F, freshref as FREF

ROLES = ("A", "B")


def load(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]


def run_panel(pubs, hiddens):
    hid_by = {h["world_id"]: h for h in hiddens}
    traj, refs, reqs, leak = [], [], [], []
    for pub in pubs:
        hid = hid_by[pub["world_id"]]
        for role in ROLES:
            ep, gc, env_ep = FG.goal_copy(pub, hid, role)
            req = F.p2_request(ep, gc)  # once per base world and goal, before any condition or receipt
            reqs.append({"world": pub["world_id"], "role": role, "relevant": gc["relevant"], **req})
            for env_kind in F.ENVS:
                trs = pub["transitions"]
                for d in F.DELAYS:
                    clk = F.make_clock(d)
                    env = F.Environment(env_ep, trs if env_kind == "changing" else [],
                                        hid["tape"] if env_kind == "changing" else [], clk)
                    t0 = time.perf_counter()
                    out = F.run(ep, gc, req, env_kind, trs, env, clk)
                    wall = time.perf_counter() - t0
                    t1 = time.process_time()
                    rf = FREF.reference_for(ep, gc, out["temporal"]["receipts"],
                                            trs if env_kind == "changing" else [], clk)
                    ref_cpu = time.process_time() - t1
                    key = {"world": pub["world_id"], "domain": pub["domain"], "role": role, "env": env_kind, "delay": d}
                    refs.append(dict(key, states=rf["states"], classes=rf["classes"], choice=rf["choice"],
                                     cpu_s=ref_cpu))
                    for p in F.PROJECTIONS:
                        traj.append(dict(out[p], **key, relevant=gc["relevant"], label=hid["labels"][role],
                                         run_wall_s=wall))
                    if env_kind == "changing" and d == max(F.DELAYS):
                        # hidden-schedule leakage check: alternative tapes sharing these public inputs
                        alts = {"realized": hid["tape"], "none": [],
                                "all": [{"transition": tr["id"], "elapsed": 0.5 + i % 2} for i, tr in enumerate(trs)]}
                        row = dict(key, beliefs={})
                        for name, tp in alts.items():
                            o = F.run(ep, gc, req, env_kind, trs, F.Environment(env_ep, trs, tp, clk), clk)
                            row["beliefs"][name] = {p: {k: o[p][k] for k in ("receipts_sha256", "ledger_sha256",
                                                                               "states_sha256", "plan", "log_head")}
                                                    | {"candidates": o[p]["candidates"]} for p in F.PROJECTIONS}
                            row.setdefault("applied", {})[name] = o["temporal"]["applied_events"]
                        leak.append(row)
    return traj, refs, reqs, leak


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
    traj, refs, reqs, leak = run_panel(pubs, hids)
    meta = {"set": a.set, "stage": a.stage, "source_sha256": src, "trajectories": len(traj), "references": len(refs),
            "model_calls": 0, "wall_s": time.perf_counter() - t0, "cpu_s": time.process_time() - c0,
            "max_reachable_set": max(t["max_set"] for t in traj),
            "max_projection_cpu_s": max(t["cpu_s"] for t in traj),
            "limits": {"MAX_STATES": F.MAX_STATES, "CPU_LIMIT_S": F.CPU_LIMIT_S},
            "started": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    for name, rows in (("trajectories", traj), ("reference", refs), ("requests", reqs), ("leakage", leak)):
        with open(out / f"{name}.jsonl", "w") as fh:
            for r in rows:
                fh.write(json.dumps(r, default=str, sort_keys=True) + "\n")
    (out / "RUN-META.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(json.dumps(meta))


if __name__ == "__main__":
    main()
