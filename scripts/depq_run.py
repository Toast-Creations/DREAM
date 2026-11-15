"""Run the V1.14.0 CPU panel (zero model calls).
Usage: depq_run.py --hub HUB --set SET --stage STAGE [--require-freeze]

Pass 1 (before any sensor answer exists): per base world, goal and environment, P2's Q0 (t = 0), S2, R, G, D, the
DEPENDENCY list and every RANDOM_EXTRA subset with its weight -> selections.jsonl; the independent selector check
(tempo.depref) -> selcheck.jsonl.
Pass 2: one DEFER-clock trajectory for BASE, DEPENDENCY and every RANDOM_EXTRA subset with e > 0 (e = 0: RANDOM_EXTRA
is the BASE outcome, not re-executed), each with its independent temporal reference; scorer-side full-domain
feasibility; and the hidden-tape leakage check over four alternative tapes for every distinct field list.
Writes HUB/stages/STAGE/{selections,selcheck,trajectories,reference,feasibility,leakage}.jsonl and RUN-META.json."""
import argparse
import json
import time
from fractions import Fraction
from pathlib import Path

from _bootstrap import ROOT
from dream_core.ledger import release_source_hash
from tempo import agentstate as AS, depgen as DG, depquery as DQ, depref as DR, freshness as F, freshref as FREF, \
    recovery as R, timing as TM
from timing_run import full_domain

ROLES = ("A", "B")


def load(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]


def field_lists(sel):
    """Distinct executed field lists: (arm, subset index or None, fields, weight)."""
    out = [("BASE", None, sel["fields"]["BASE"], None), ("DEPENDENCY", None, sel["fields"]["DEPENDENCY"], None)]
    if sel["e"]:
        for i, fs in enumerate(sel["random_subsets"]):
            out.append(("RANDOM_EXTRA", i, fs, sel["random_weight"]))
    return out


def alt_tapes(hid, trs):
    return {"realized": hid["tape"], "none": [],
            "all": [{"transition": x["id"], "elapsed": 0.5 + i % 2} for i, x in enumerate(trs)],
            "all_late": [{"transition": x["id"], "elapsed": 1.5} for x in trs]}


def run_panel(pubs, hiddens, set_name):
    hid_by = {h["world_id"]: h for h in hiddens}
    rows = {r[0]: (d, r) for d, r, _ in DG.specs(set_name, 0, smoke=set_name.endswith("smoke"))}
    sels, checks, traj, refs, feas, leak = [], [], [], [], [], []
    ctxs = []
    # pass 1: selection from public inputs only (the hidden record is not touched here)
    for pub in pubs:
        domain = pub["domain"]
        for role in ROLES:
            ep = {k: v for k, v in pub.items() if k != "goals"}
            ep = dict(ep, episode_id=f"{pub['world_id']}|{role}", group_id=pub["world_id"], goal_role=role)
            gc = R.context(ep, pub["goals"][role])
            q0 = F.p2_request(ep, gc)["fields"]
            for env in TM.ENVS:
                key = {"world": pub["world_id"], "domain": domain, "role": role, "env": env}
                c0 = time.process_time()
                sel = DQ.selection_for(ep, gc, q0, env)
                sel_cpu = time.process_time() - c0
                ref = DR.selection_reference(ep, gc["relevant"], q0, env, TM.ORIGIN, DQ.SELECT_AT, DQ.CAP,
                                             set(AS.agent_fields(ep["spec"])))
                sk = lambda S: sorted(json.dumps(sorted(s.items())) for s in S)
                ok = {"s2": sk(sel["s2_states"]) == sk(ref["s2_states"]), "R": sel["R"] == ref["R"],
                      "D": sel["D"] == ref["D"], "DEPENDENCY": sel["fields"]["DEPENDENCY"] == ref["DEPENDENCY"],
                      "e": sel["e"] == ref["e"],
                      "random_subsets": (sel["random_subsets"] == ref["random_subsets"]) if sel["e"] else
                      ref["random_subsets"] == [list(q0)],
                      "weight": abs(sel["random_weight"] - float(Fraction(ref["random_weight"]))) < 1e-12}
                checks.append(dict(key, ok=ok, all_ok=all(ok.values()), reference=ref))
                sels.append(dict(key, **sel, cpu_s=sel_cpu, made_before_any_sensor_answer=True))
                ctxs.append((pub, role, env, sel))
    # pass 2: trajectories
    for pub, role, env, sel in ctxs:
        hid = hid_by[pub["world_id"]]
        domain, row = rows[pub["world_id"]]
        ep, gc, env_ep = DG.goal_copy(pub, hid, role)
        if F.p2_request(ep, gc)["fields"] != sel["Q0"] or gc["relevant"] != sel["G"]:
            raise AssertionError("controller copy differs from the selection copy")
        trs = pub["transitions"]
        key = {"world": pub["world_id"], "domain": domain, "role": role, "env": env}
        for arm, idx, fs, wgt in field_lists(sel):
            tag = f"|{arm}" + ("" if idx is None else f"#{idx}")
            t = DQ.run_arm(ep, gc, fs, env, env_ep, hid["tape"], tag)
            c0 = time.process_time()
            rf = FREF.reference_for(ep, gc, t["receipts"], trs if env == "changing" else [], t["projection_clock"])
            refs.append(dict(key, arm=arm, subset=idx, states=rf["states"], classes=rf["classes"], choice=rf["choice"],
                             cpu_s=time.process_time() - c0))
            traj.append(dict(t, **key, arm=arm, subset=idx, weight=wgt, fields=list(fs), relevant=gc["relevant"],
                             e=sel["e"], Q0=sel["Q0"], added_fields=[f for f in fs if f not in sel["Q0"]],
                             label=hid["labels"][role]))
        if env == "changing":
            row_ = dict(key, by_list={})
            for arm, idx, fs, _ in field_lists(sel):
                nm = f"{arm}" + ("" if idx is None else f"#{idx}")
                row_["by_list"][nm] = {}
                for tn, tp in alt_tapes(hid, trs).items():
                    o = DQ.run_arm(ep, gc, fs, env, env_ep, tp, f"|leak|{nm}|{tn}")
                    row_["by_list"][nm][tn] = {k: o[k] for k in ("states_sha256", "plan", "log_head")}
                    row_["by_list"][nm][tn]["readings"] = [(r["field"], r["measured_at"], r["value"])
                                                           for r in o["readings"]]
                    row_["by_list"][nm][tn]["candidates"] = o["candidates"]
                    row_["by_list"][nm][tn]["queried"] = o["queried"]
            leak.append(row_)
    for pub in pubs:
        hid = hid_by[pub["world_id"]]
        domain, row = rows[pub["world_id"]]
        w = DG.build(row, domain, hid["seed"], set_name)[0]
        for role in ROLES:
            ep, gc, env_ep = DG.goal_copy(pub, hid, role)
            for env in TM.ENVS:
                sc = TM.schedule_clock(DQ.SCHEDULE)
                envo = TM.environment(env_ep, env, pub["transitions"], hid["tape"], sc)
                s0, s4 = envo.state_at(TM.ORIGIN)[0], envo.state_at(sc["execute_at"])[0]
                feas.append({"world": pub["world_id"], "domain": domain, "role": role, "env": env,
                             "optimum_at_origin": full_domain(w, domain, gc["goal"], s0),
                             "optimum_at_action": full_domain(w, domain, gc["goal"], s4)})
    return sels, checks, traj, refs, feas, leak


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
    sels, checks, traj, refs, feas, leak = run_panel(pubs, hids, a.set)
    n_rand = sum(t["arm"] == "RANDOM_EXTRA" for t in traj)
    meta = {"set": a.set, "stage": a.stage, "source_sha256": src, "rule": DQ.RULE, "selections": len(sels),
            "policy_cells": 3 * len(sels), "trajectories_total": len(traj),
            "trajectories_by_arm": {arm: sum(t["arm"] == arm for t in traj) for arm in DQ.ARMS},
            "random_subset_trajectories": n_rand, "references": len(refs),
            "leakage_runs": sum(len(v) for r in leak for v in r["by_list"].values()),
            "model_calls": 0, "wall_s": time.perf_counter() - t0, "cpu_s": time.process_time() - c0,
            "max_reachable_set": max(t["max_set"] for t in traj), "max_s2": max(s["s2_size"] for s in sels),
            "max_projection_cpu_s": max(t["cpu_s"] for t in traj),
            "limits": {"MAX_STATES": F.MAX_STATES, "CPU_LIMIT_S": F.CPU_LIMIT_S},
            "started": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    for name, rows in (("selections", sels), ("selcheck", checks), ("trajectories", traj), ("reference", refs),
                       ("feasibility", feas), ("leakage", leak)):
        with open(out / f"{name}.jsonl", "w") as fh:
            for r in rows:
                fh.write(json.dumps(r, default=str, sort_keys=True) + "\n")
    (out / "RUN-META.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(json.dumps(meta))


if __name__ == "__main__":
    main()
