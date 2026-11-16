#!/usr/bin/env python3
"""E1 confirmatory pairwise-v1 driver (PREREGISTRATION_E1_E5.md). Judges fresh, unseen E1 outputs with the FROZEN
pairwise-v1 instrument, without modifying it.

The frozen runner (judging/pairwise-v1/scripts/run_pairwise_v1.py) hard-codes the pilot paths and two baselines,
so it cannot itself build E1 pairs. This driver imports its judge functions (verify_freeze, final_text,
judge_pair) read-only, builds pairs targeted-vs-{strong_prompt, high_temperature, random} with the same seeded
order procedure, and writes every output under --out (never inside the instrument directory).

  run_e1_pairwise.py --instrument .../judging/pairwise-v1 --tasks tasks_e1_24.json --lock steering_lock.json \
      --units qwen3-8b=DIR --units mistral-7b=DIR --out OUTDIR [--dry-run]

Refuses to make any call unless: the instrument's frozen hashes verify and it is qualified; the task file, steering
lock and analysis script match the hashes registered below; every model has a unit for all 24 tasks x 3 seeds x 4
arms (generation complete = the prospective hold rule); every unit's task text matches the task file; and every
unit's steering and sampling records match the steering lock.
"""
import argparse
import hashlib
import importlib.util
import json
import random
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.dont_write_bytecode = True          # importing the frozen runner must not write __pycache__ into its directory

HERE = Path(__file__).resolve().parent
REGISTERED = {
    "tasks_e1_24.json": "bafe147e4cc3dceba64b978f5f2c5c8379d3ece7e14479e951919786488a641c",
    "steering_lock.json": "2361358bec3d8b2b4ee236f7cda9b6616b67cd2618a59f2c8a749915a65c18b2",
    "analyze_e1_pairwise.py": "7331c6e5fcc711f8e89665951146d17ab738b54ae82cd7e71e1204e584fdfade",
    "pairwise-v1/SPEC.json": "9a4e7aedd12c087da1ebe9276e668bcf470ee639743c2c8647785a74c0dcb22e",
}
STEER, COMPARISONS = "targeted", ("strong_prompt", "high_temperature", "random")
ARMS = (STEER,) + COMPARISONS
SEEDS_PER_TASK = 3


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def check_registered(path, key):
    got = sha(path)
    if got != REGISTERED[key]:
        raise SystemExit(f"{key}: sha256 {got} != registered {REGISTERED[key]}; run is outside the preregistration")


def load_frozen(instrument):
    check_registered(instrument / "SPEC.json", "pairwise-v1/SPEC.json")
    spec = importlib.util.spec_from_file_location("pairwise_v1_frozen", instrument / "scripts/run_pairwise_v1.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.verify_freeze()                                      # all four frozen files match SPEC.json
    q = instrument / "results/qual_report.json"
    if not q.exists() or not json.loads(q.read_text()).get("qualified"):
        raise SystemExit("pairwise-v1 is not qualified")
    return mod


def check_unit(u, model, lock, task):
    """Return a list of problems with this unit against the task file and the steering lock (empty = OK)."""
    bad = []
    if u["task"].get("prompt") != task["prompt"]:
        bad.append("task prompt differs from tasks_e1_24.json")
    m, g = lock["models"][model], lock["generation"]
    for c in u["calls"]:
        st, arm = c.get("steering"), u["arm"]
        want_t = g["high_temperature"] if (arm == "high_temperature" and c["stage"] == "ideation") else g["temperature"]
        if (c.get("temperature"), c.get("top_p"), c.get("top_k")) != (want_t, g["top_p"], g["top_k"]):
            bad.append(f"{c['stage']}: sampling {c.get('temperature'), c.get('top_p'), c.get('top_k')}")
        steered = arm in (STEER, "random") and c["stage"] == lock["steered_stage"]
        if not steered:
            if st is not None:
                bad.append(f"{c['stage']}: unexpected steering {st}")
            continue
        if st is None:
            bad.append(f"{c['stage']}: steering missing")
            continue
        if (st.get("layer_index"), st.get("peak_strength"), st.get("schedule")) != \
                (lock["layer_index"], lock["peak_strength"], lock["schedule"]):
            bad.append(f"{c['stage']}: steering settings {st}")
        if arm == STEER and (st.get("vector_role"), st.get("vector_sha256")) != ("targeted", m["targeted_vector_sha256"]):
            bad.append("targeted vector differs from lock")
        if arm == "random" and (st.get("vector_role") != "random" or st.get("vector_sha256") not in m["random_vector_sha256"]):
            bad.append("random vector not in locked set")
    return bad


def build_pairs(mod, units_by_model, tasks, lock):
    tasks_by_id = {t["id"]: t for t in tasks}
    pairs, missing, problems, hold = [], [], [], []
    for model, d in units_by_model.items():
        if model not in lock["models"]:
            raise SystemExit(f"model {model} is not in the steering lock")
        cell = {}
        for p in sorted(Path(d).glob("*.json")):
            u = json.loads(p.read_text())
            if u["task_id"] not in tasks_by_id:
                problems.append([model, u["unit_id"], "task not in tasks_e1_24.json"]); continue
            cell.setdefault((u["task_id"], u["seed"]), {})[u["arm"]] = u
            problems += [[model, u["unit_id"], b] for b in check_unit(u, model, lock, tasks_by_id[u["task_id"]])]
        seeds = {}
        for (t, s) in cell:
            seeds.setdefault(t, set()).add(s)
        for t in tasks_by_id:
            if len(seeds.get(t, ())) != SEEDS_PER_TASK:
                hold.append([model, t, f"{len(seeds.get(t, ()))} seeds"])
        for (t, s), arms in sorted(cell.items()):
            absent = [a for a in ARMS if a not in arms]
            if absent:
                hold.append([model, t, s, f"arms missing {absent}"]); continue
            us = arms[STEER]
            for base in COMPARISONS:
                ub = arms[base]
                ts, tb = mod.final_text(us), mod.final_text(ub)
                if not ts or not tb:
                    missing.append([model, t, s, base]); continue       # a generation failure stays an outcome
                pid = f"{model}.{t}.s{s}.{STEER}-vs-{base}"
                rng = random.Random(int(hashlib.sha256(pid.encode()).hexdigest()[:16], 16))
                c = [(us["unit_id"], ts), (ub["unit_id"], tb)]
                rng.shuffle(c)                                         # same procedure as the frozen pilot builder
                pairs.append({"pair_id": pid, "task": us["task"]["prompt"], "c1": c[0][0], "text1": c[0][1],
                              "c2": c[1][0], "text2": c[1][1],
                              "meta": {"model": model, "task_id": t, "family": us["task"].get("family"), "seed": s,
                                       "baseline": base, "steer_id": us["unit_id"], "baseline_id": ub["unit_id"]}})
    return pairs, missing, problems, hold


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--instrument", required=True, type=Path)
    ap.add_argument("--tasks", default=HERE / "tasks_e1_24.json", type=Path)
    ap.add_argument("--lock", default=HERE / "steering_lock.json", type=Path)
    ap.add_argument("--units", action="append", required=True, help="model=units_dir (repeat per model)")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    inst, out = a.instrument.resolve(), a.out.resolve()
    if out == inst or inst in out.parents:
        raise SystemExit("--out must be outside the frozen instrument directory")
    check_registered(a.tasks, "tasks_e1_24.json")
    check_registered(a.lock, "steering_lock.json")
    check_registered(HERE / "analyze_e1_pairwise.py", "analyze_e1_pairwise.py")
    mod = load_frozen(inst)
    tasks, lock = json.loads(a.tasks.read_text()), json.loads(a.lock.read_text())
    units = dict(x.split("=", 1) for x in a.units)
    if set(units) != set(lock["models"]):
        raise SystemExit(f"--units must cover exactly {sorted(lock['models'])}")

    pairs, missing, problems, hold = build_pairs(mod, units, tasks, lock)
    print(f"pairs {len(pairs)} ({2 * len(pairs)} calls); missing finals {len(missing)}; "
          f"lock/task problems {len(problems)}; hold-rule gaps {len(hold)}")
    for x in (problems + hold)[:20]:
        print("  ", x)
    if a.dry_run:
        return
    if problems or hold:
        raise SystemExit("REFUSED: lock/task problems or incomplete generation (prospective hold rule)")

    out.mkdir(parents=True, exist_ok=True)
    manifest = out / "MANIFEST.json"
    record = {"registered_sha256": REGISTERED, "driver_sha256": sha(__file__),
              "frozen_files_sha256": json.loads((inst / "SPEC.json").read_text())["files_sha256"],
              "units": {m: sorted(p.name for p in Path(d).glob("*.json")) for m, d in units.items()},
              "pairs": len(pairs), "missing_finals": missing}
    if manifest.exists() and json.loads(manifest.read_text()) != record:
        raise SystemExit("MANIFEST.json differs from this invocation; refusing to mix runs")
    manifest.write_text(json.dumps(record, indent=1) + "\n")

    raw_dir, ckpt = out / "raw", out / "e1_pairs.jsonl"
    raw_dir.mkdir(exist_ok=True)
    done = set()
    if ckpt.exists():
        done = {json.loads(l)["pair_id"] for l in ckpt.read_text().splitlines() if l.strip() and json.loads(l).get("complete")}
    todo = [p for p in pairs if p["pair_id"] not in done]
    print(f"{len(done)} complete, {len(todo)} to judge")
    with ThreadPoolExecutor(mod.WORKERS) as ex:
        for rec in ex.map(lambda p: mod.judge_pair(p, raw_dir, ckpt), todo):
            print(rec["pair_id"], "ok" if rec["complete"] else "INCOMPLETE", flush=True)
    print("done; analyse with analyze_e1_pairwise.py --pairs", ckpt, "--e4-record <completed E4 record>")


if __name__ == "__main__":
    main()
