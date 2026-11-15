"""V1.15.1 pooled analysis of the overnight text replication (no model).
Usage: ftx_pool.py --queue QDIR [--boot 10000] [--seed 20261105]
Pools every block whose RUN-STATUS entry is "complete", in the declared order. Global keys: (block_id, world_id) for
worlds and (block_id, call_id) for calls; local ids are never merged across blocks. Interval: case-stratified instance
bootstrap (24 predeclared families = local world ids; resample instances within family with its count preserved; goals
stay paired inside each world value), 10,000 resamples, seed 20261105; conditional on the designed family mixture.
If fewer than all 32 blocks are complete, every value is labelled INCOMPLETE (interim, descriptive).
Writes QDIR/POOLED/{ANALYSIS.json, FAMILY-TABLE.md} and QDIR/MORNING-REPORT.md."""
import argparse
import collections
import json
import random
import statistics
from pathlib import Path

ROLES = ("A", "B")


def load(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]


def strat_boot(vals, B, seed):
    """vals: {(block, family): v}. Resample instances within each family; mean over all instances."""
    fam = collections.defaultdict(list)
    for (b, f), v in vals.items():
        fam[f].append(v)
    rng = random.Random(seed)
    n = sum(len(v) for v in fam.values())
    est = []
    for _ in range(B):
        s = 0.0
        for vs in fam.values():
            s += sum(rng.choice(vs) for _ in vs)
        est.append(s / n)
    est.sort()
    return [round(est[int(0.025 * B)], 4), round(est[int(0.975 * B) - 1], 4)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--queue", required=True)
    ap.add_argument("--boot", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=20261105)
    a = ap.parse_args()
    q = Path(a.queue)
    fz = json.loads((q / "config" / "QUEUE-FROZEN.json").read_text())
    st = json.loads((q / "RUN-STATUS.json").read_text())
    done = [b for b in fz["blocks"] if b["block_id"] in st["complete"]]
    complete = len(done) == len(fz["blocks"]) and st["state"] == "complete"
    T, EXT, GATES, META = {}, [], {}, {}
    for b in done:
        hub = Path(b["hub"])
        bid = b["block_id"]
        for t in load(hub / "stages" / "main" / "eval" / "trajectories.jsonl"):
            T[(bid, t["world"], t["role"], t["env"], t["channel"], t["selector"])] = t
        for e in load(hub / "stages" / "main" / "eval" / "extraction.jsonl"):
            EXT.append(dict(e, block=bid))
        an = json.loads((hub / "analysis" / "main" / "ANALYSIS.json").read_text())
        GATES[bid] = {"pass": an["software_gates_pass"], "failed": an["failed_gates"],
                      "gates": {k: (g["failures"], g["checked"]) for k, g in an["gates"].items()}}
        META[bid] = json.loads((hub / "stages" / "main" / "eval" / "EVAL-META.json").read_text())
    worlds = sorted({(k[0], k[1]) for k in T})
    dom = {(k[0], k[1]): t["domain"] for k, t in T.items()}
    U = lambda w, env, ch, s: sum(T[(w[0], w[1], r, env, ch, s)]["utility"]["1"] for r in ROLES) / 2
    res = {"complete": complete, "label": "COMPLETE" if complete else "INCOMPLETE (interim, descriptive)",
           "blocks_pooled": [b["block_id"] for b in done], "blocks_target": len(fz["blocks"]), "worlds": len(worlds),
           "worlds_target": fz["worlds"], "trajectories": len(T), "queue_state": st["state"], "stop_reason": st.get("stop_reason"),
           "elapsed_s": st["elapsed_s"], "calls_ok": st["calls_ok"], "calls_total": fz["total_calls"],
           "software_gates_all_blocks": all(g["pass"] for g in GATES.values()) if GATES else None, "gates_by_block": GATES}
    if not worlds:
        (q / "POOLED").mkdir(exist_ok=True)
        (q / "POOLED" / "ANALYSIS.json").write_text(json.dumps(res, indent=1))
        (q / "MORNING-REPORT.md").write_text(f"# Overnight text replication: MORNING REPORT\n\nNo block completed. State: {st['state']}; "
                                             f"stop reason: {st.get('stop_reason')}.\n")
        return

    def contrast(fn, ws=None):
        ws = ws or worlds
        v = {w: fn(w) for w in ws}
        return {"mean": round(statistics.mean(v.values()), 4), "ci95": strat_boot(v, a.boot, a.seed),
                "better": sum(x > 0 for x in v.values()), "equal": sum(x == 0 for x in v.values()),
                "worse": sum(x < 0 for x in v.values()), "n_worlds": len(v)}
    con = {}
    for env in ("changing", "stable"):
        pre = "PRIMARY " if env == "changing" else ""
        con[f"{pre}{env}: text DEPENDENCY - BASE"] = contrast(lambda w, e=env: U(w, e, "text", "DEPENDENCY") - U(w, e, "text", "BASE"))
        con[f"{env}: structured DEPENDENCY - BASE"] = contrast(lambda w, e=env: U(w, e, "structured", "DEPENDENCY") - U(w, e, "structured", "BASE"))
        for s in ("BASE", "DEPENDENCY"):
            con[f"{env}: interface loss text - structured, {s}"] = contrast(lambda w, e=env, s=s: U(w, e, "text", s) - U(w, e, "structured", s))
        con[f"{env}: change in augmentation benefit (text - structured)"] = contrast(
            lambda w, e=env: (U(w, e, "text", "DEPENDENCY") - U(w, e, "text", "BASE")) - (U(w, e, "structured", "DEPENDENCY") - U(w, e, "structured", "BASE")))
    for d in ("delivery", "assembly"):
        ws = [w for w in worlds if dom[w] == d]
        con[f"changing: text DEPENDENCY - BASE, {d}"] = contrast(lambda w: U(w, "changing", "text", "DEPENDENCY") - U(w, "changing", "text", "BASE"), ws)
        con[f"changing: structured DEPENDENCY - BASE, {d}"] = contrast(lambda w: U(w, "changing", "structured", "DEPENDENCY") - U(w, "changing", "structured", "BASE"), ws)
        con[f"changing: change in augmentation benefit, {d}"] = contrast(
            lambda w: (U(w, "changing", "text", "DEPENDENCY") - U(w, "changing", "text", "BASE")) - (U(w, "changing", "structured", "DEPENDENCY") - U(w, "changing", "structured", "BASE")), ws)
    res["contrasts"] = con
    fams = sorted({w[1] for w in worlds}, key=lambda f: (f[0] != "d", f))
    ft = {}
    for f in fams:
        ws = [w for w in worlds if w[1] == f]
        m = lambda fn: round(statistics.mean(fn(w) for w in ws), 3)
        ft[f] = {"n": len(ws), "text_D_minus_B": m(lambda w: U(w, "changing", "text", "DEPENDENCY") - U(w, "changing", "text", "BASE")),
                 "structured_D_minus_B": m(lambda w: U(w, "changing", "structured", "DEPENDENCY") - U(w, "changing", "structured", "BASE")),
                 "text_minus_structured_DEP": m(lambda w: U(w, "changing", "text", "DEPENDENCY") - U(w, "changing", "structured", "DEPENDENCY")),
                 "text_minus_structured_BASE": m(lambda w: U(w, "changing", "text", "BASE") - U(w, "changing", "structured", "BASE")),
                 "text_empty_support_copies": sum(T[(w[0], w[1], r, "changing", "text", "DEPENDENCY")]["n_states"] == 0 for w in ws for r in ROLES)}
    res["families"] = ft
    cells = {}
    for env in ("stable", "changing"):
        for ch in ("structured", "text"):
            for s in ("BASE", "DEPENDENCY"):
                ts = [t for k, t in T.items() if k[3] == env and k[4] == ch and k[5] == s]
                cells[f"{env}|{ch}|{s}"] = {
                    "n": len(ts), "U": sum(t["utility"]["1"] for t in ts), "success": sum(t["success"] for t in ts),
                    "invalid_attempts": sum(t["invalid_attempt"] for t in ts), "false_completions": sum(t["false_completion"] for t in ts),
                    "declines": sum(t["outcome_kind"] == "decline" for t in ts), "fees": sum(t["queried_facts"] for t in ts),
                    "action_cost": sum(t["action_cost"] for t in ts), "empty_support": sum(t["n_states"] == 0 for t in ts),
                    "actual_in_support": sum(t["actual_in_support"] for t in ts),
                    "fully_represented": sum(t["fully_represented"] for t in ts),
                    "with_pending": sum(bool(t["pending"]) for t in ts),
                    "with_historical_conflict": sum(bool(t["historical_conflict_fields"]) for t in ts),
                    "limit_exceeded": sum(t["status"] == "limit_exceeded" for t in ts),
                    "menu_feasible": sum(t["menu_feasible"] for t in ts), "missed_menu_feasible": sum(t["missed_opportunity"] for t in ts)}
    res["cells"] = cells
    ea = collections.Counter()
    bykind = collections.defaultdict(collections.Counter)
    for e in EXT:
        for k in ("parsed", "mapped", "accepted", "denotation_equal", "status_wrong"):
            ea[k] += bool(e[k]); bykind[e["gold_kind"]][k] += bool(e[k])
        ea["n"] += 1; bykind[e["gold_kind"]]["n"] += 1
        ea[f"code:{e['code']}"] += 1
        ea["truncated"] += e["stop"] == "length"
    res["extraction"] = {"overall": dict(ea), "by_gold_kind": {k: dict(v) for k, v in bykind.items()},
                         "output_tokens": sum(e["output_tokens"] or 0 for e in EXT),
                         "generation_seconds": round(sum(e["seconds"] or 0 for e in EXT), 1)}
    res["verification_runs"] = {b: m["verification_runs"] for b, m in META.items()}
    (q / "POOLED").mkdir(exist_ok=True)
    (q / "POOLED" / "ANALYSIS.json").write_text(json.dumps(res, indent=1, default=str) + "\n")
    fmt = lambda x: f"{x['mean']:+.3f} [{x['ci95'][0]:+.3f}, {x['ci95'][1]:+.3f}] ({x['better']}/{x['equal']}/{x['worse']}, n={x['n_worlds']})"
    L = [f"# Overnight text replication: MORNING REPORT ({res['label']})", "",
         f"- Queue state: **{st['state']}**; stop reason: {st.get('stop_reason')}; elapsed {round(st['elapsed_s'])} s (cap {fz['wall_seconds_max']} s).",
         f"- Blocks pooled: {len(done)}/{len(fz['blocks'])}; worlds {len(worlds)}/{fz['worlds']}; model calls collected "
         f"{st['calls_ok']}/{fz['total_calls']}; scored decision trajectories {len(T)} (verification runs separate).",
         f"- Software gates passed in every pooled block: **{res['software_gates_all_blocks']}**.",
         f"- Source {fz['source_sha256']}; model config {fz['model_config_sha256']}; inputs {fz['input_commitment_sha256']}.",
         "- Automatically generated by ftx_pool.py; interpretation is added by hand below if the session is available.", "",
         "## Contrasts (λ = 1; case-stratified instance bootstrap, 10,000 resamples, seed 20261105; conditional on the 24 designed families)", ""]
    for k, x in con.items():
        L.append(f"- {k}: {fmt(x)}")
    L += ["", "## Cells (sums over goal copies)", "", "```", json.dumps(cells, indent=1), "```", "",
          "## Extraction audit", "", "```", json.dumps(res["extraction"], indent=1), "```", "",
          "## Per-family (changing; means over instances)", "", "| family | n | text D−B | structured D−B | text−struct DEP | text−struct BASE | text empty-support copies |",
          "|---|---|---|---|---|---|---|"]
    for f, x in ft.items():
        L.append(f"| {f} | {x['n']} | {x['text_D_minus_B']:+.3f} | {x['structured_D_minus_B']:+.3f} | {x['text_minus_structured_DEP']:+.3f} | "
                 f"{x['text_minus_structured_BASE']:+.3f} | {x['text_empty_support_copies']} |")
    L += ["", "## Blocks", ""] + [f"- {b['block_id']}: {b['result']} ({b.get('calls_ok')}/{b.get('calls')} calls, {b.get('seconds')} s)"
                                   for b in st["log"]]
    L += ["", f"Artifacts: each block hub under {q}/blocks/ (data/, stages/main/calls, stages/main/eval, analysis/main)."]
    (q / "MORNING-REPORT.md").write_text("\n".join(L) + "\n")
    print(json.dumps({"label": res["label"], "worlds": len(worlds), "primary": con["PRIMARY changing: text DEPENDENCY - BASE"]["mean"]}))


if __name__ == "__main__":
    main()
