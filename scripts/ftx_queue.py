"""V1.15.1 overnight text-replication queue: a thin wrapper around the frozen 1.15.0 pipeline (study behaviour unchanged;
every 1.15.0 file is byte-identical in this source).

Usage (inside the dream-research container, offline):
  ftx_queue.py prepare --queue QDIR --manifest MANIFEST.json [--set ftx] [--blocks N]
      generate every block hub (ftx_generate.py --base-seed), validate each (ftx_validate.py --skip-regressions),
      refuse overwrites, then write QDIR/config/QUEUE-FROZEN.json (source, model config, every block commitment,
      exact total calls) and a filled manifest copy QDIR/config/MANIFEST-FROZEN.json. Also writes each block's
      config/FROZEN-PROTOCOL.json (source hash) so ftx_evaluate --require-freeze binds to the frozen source.
  ftx_queue.py run --queue QDIR [--fake REPLIES.json]
      fixed block order; per block: tempo_run.py (resumes: only missing calls are collected), then ftx_evaluate.py
      --require-freeze and ftx_analyze.py. Before each block the remaining time is checked against a forecast; a block
      that cannot fit (cap minus reporting reserve) is not started (clean incomplete stop). Software-gate failure,
      persistent infrastructure failure, source/config drift or a resource limit stops the queue. Utility never
      decides whether a block runs. Ends with ftx_pool.py (pooled analysis + MORNING-REPORT.md).
Status: QDIR/RUN-STATUS.json (machine) and QDIR/RUN-STATUS.md, refreshed after every block."""
import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

from _bootstrap import ROOT
from dream_core.ledger import atomic_json, release_source_hash

PY = sys.executable
SCRIPTS = ROOT / "scripts"
RESERVE_S = 1500          # reporting/pooling reserve inside the cap
LOAD_S, EVAL_S = 30, 60   # per-block forecast overheads (measured: load ~22 s, evaluate+analyze ~20 s)
SMOKE_S_PER_CALL = 3.14   # V1.15.0 smoke: 78.5 s / 25 calls (forecast until a block has been measured)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def sh(args, log):
    with open(log, "a") as fh:
        fh.write(f"\n$ {' '.join(map(str, args))}\n")
        fh.flush()
        return subprocess.run([str(a) for a in args], stdout=fh, stderr=subprocess.STDOUT, cwd=ROOT).returncode


def prepare(a):
    q = Path(a.queue)
    man = json.loads(Path(a.manifest).read_text())
    (q / "config").mkdir(parents=True, exist_ok=True)
    if (q / "config" / "QUEUE-FROZEN.json").exists():
        raise SystemExit("queue already frozen")
    src = release_source_hash(ROOT)
    model_cfg = json.loads(Path(a.stage_template).read_text())
    blocks = man["blocks"][:a.blocks] if a.blocks else man["blocks"]
    rec = []
    for b in blocks:
        hub = q / b["relative_hub"]
        if (hub / "data").exists():
            raise SystemExit(f"{hub} exists; refusing to overwrite")
        (hub / "config").mkdir(parents=True)
        log = hub / "prepare.log"
        if sh([PY, "-B", SCRIPTS / "ftx_generate.py", "--hub", hub, "--set", a.set, "--base-seed", b["base_seed"]], log):
            raise SystemExit(f"{b['block_id']}: generation failed (see {log})")
        commit = json.loads((hub / "data" / f"COMMITMENT-{a.set}.json").read_text())
        cfg = dict(model_cfg, set=a.set, max_calls=commit["calls"], max_seconds=1800)
        (hub / "config" / "stage-main.json").write_text(json.dumps(cfg))
        if sh([PY, "-B", SCRIPTS / "ftx_validate.py", "--hub", hub, "--set", a.set, "--skip-regressions",
               "--stage-config", hub / "config" / "stage-main.json"], log):
            raise SystemExit(f"{b['block_id']}: validation failed (see {hub}/phase0/VALIDATION.md)")
        (hub / "config" / "FROZEN-PROTOCOL.json").write_text(json.dumps(
            {"source_sha256": src, "queue": str(q), "block_id": b["block_id"], "note": "binds ftx_evaluate --require-freeze"}, indent=1))
        rec.append({"block_id": b["block_id"], "base_seed": b["base_seed"], "hub": str(hub), "calls": commit["calls"], "worlds": commit["worlds"],
                    "rejected_redraws": len(commit["rejected_attempts"]),
                    "redraw_reasons": sorted({r["reason"] for r in commit["rejected_attempts"]}),
                    "commitment_sha256": sha(hub / "data" / f"COMMITMENT-{a.set}.json"),
                    "calls_sha256": commit["calls_sha256"], "stage_config_sha256": sha(hub / "config" / "stage-main.json"),
                    "validation_sha256": sha(hub / "phase0" / "VALIDATION.json")})
        print(b["block_id"], commit["calls"], flush=True)
    total = sum(r["calls"] for r in rec)
    if total > man["limits"]["scheduled_replication_calls_max"]:
        raise SystemExit(f"{total} calls exceed the manifest maximum")
    model_sha = hashlib.sha256(json.dumps(model_cfg["model"], sort_keys=True).encode()).hexdigest()
    inputs_sha = hashlib.sha256(json.dumps([r["commitment_sha256"] for r in rec]).encode()).hexdigest()
    fz = {"frozen_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "source_dir": str(ROOT), "source_sha256": src,
          "set": a.set, "blocks": rec, "total_calls": total, "worlds": sum(r["worlds"] for r in rec),
          "model": model_cfg["model"], "model_config_sha256": model_sha, "input_commitment_sha256": inputs_sha,
          "wall_seconds_max": man["limits"]["wall_seconds_max"], "reserve_s": RESERVE_S,
          "forecast_s": round(total * SMOKE_S_PER_CALL + len(rec) * (LOAD_S + EVAL_S)),
          "queue_code": {f: sha(SCRIPTS / f) for f in ("ftx_queue.py", "ftx_pool.py")},
          "manifest_source": a.manifest, "manifest_sha256": sha(a.manifest)}
    atomic_json(q / "config" / "QUEUE-FROZEN.json", fz)
    man2 = dict(man, status="frozen_runnable", source_sha256=src, model_config_sha256=model_sha,
                input_commitment_sha256=inputs_sha, integration_source=str(ROOT), frozen_queue=str(q / "config" / "QUEUE-FROZEN.json"))
    atomic_json(q / "config" / "MANIFEST-FROZEN.json", man2)
    print(json.dumps({k: fz[k] for k in ("total_calls", "worlds", "forecast_s", "source_sha256")}))


def write_status(q, st):
    atomic_json(q / "RUN-STATUS.json", st)
    L = ["# RUN STATUS: overnight text replication (V1.15.1 queue over the frozen 1.15.0 pipeline)", "",
         f"- state: **{st['state']}**; started {st['started']}; elapsed {round(st['elapsed_s'])} s of {st['cap_s']} s",
         f"- blocks complete: {len(st['complete'])}/{st['n_blocks']}; calls collected {st['calls_ok']}/{st['calls_total']}",
         f"- stop reason: {st.get('stop_reason')}", ""]
    for b in st["log"]:
        L.append(f"- {b['block_id']}: {b['result']} (calls {b.get('calls_ok')}/{b.get('calls')}, {b.get('seconds')} s"
                 f"{', gates ' + str(b.get('gates')) if 'gates' in b else ''})")
    (q / "RUN-STATUS.md").write_text("\n".join(L) + "\n")


def run(a):
    q = Path(a.queue)
    fz = json.loads((q / "config" / "QUEUE-FROZEN.json").read_text())
    if release_source_hash(ROOT) != fz["source_sha256"] or \
            any(sha(SCRIPTS / f) != h for f, h in fz["queue_code"].items()):
        raise SystemExit("source differs from the frozen queue")
    prev = json.loads((q / "RUN-STATUS.json").read_text()) if (q / "RUN-STATUS.json").exists() else None
    t0 = time.time()
    spent_before = prev["elapsed_s"] if prev else 0.0
    st = {"state": "running", "started": prev["started"] if prev else time.strftime("%Y-%m-%dT%H:%M:%S%z"),
          "elapsed_s": spent_before, "cap_s": fz["wall_seconds_max"], "n_blocks": len(fz["blocks"]),
          "complete": prev["complete"] if prev else [], "calls_total": fz["total_calls"],
          "calls_ok": prev["calls_ok"] if prev else 0, "log": prev["log"] if prev else [], "stop_reason": None,
          "rate_s_per_call": prev.get("rate_s_per_call") if prev else None}
    write_status(q, st)
    for b in fz["blocks"]:
        if b["block_id"] in st["complete"]:
            continue
        hub = Path(b["hub"])
        if sha(hub / "data" / f"COMMITMENT-{fz['set']}.json") != b["commitment_sha256"] or \
                sha(hub / "config" / "stage-main.json") != b["stage_config_sha256"]:
            st.update(state="stopped", stop_reason=f"{b['block_id']}: input/config drift")
            break
        rate = st["rate_s_per_call"] or SMOKE_S_PER_CALL
        done_calls = len(list((hub / "stages" / "main" / "calls").glob("*.json"))) if (hub / "stages" / "main" / "calls").exists() else 0
        forecast = (b["calls"] - done_calls) * rate * 1.15 + LOAD_S + EVAL_S
        elapsed = spent_before + (time.time() - t0)
        if elapsed + forecast > fz["wall_seconds_max"] - RESERVE_S:
            st.update(state="incomplete", stop_reason=f"time: {b['block_id']} forecast {round(forecast)} s does not fit "
                                                       f"(elapsed {round(elapsed)} s, cap {fz['wall_seconds_max']} s, reserve {RESERVE_S} s)")
            break
        bt = time.time()
        log = hub / "queue.log"
        cmd = [PY, "-B", SCRIPTS / "tempo_run.py", "--hub", hub, "--stage", "main", "--config", hub / "config" / "stage-main.json"]
        if a.fake:
            cmd += ["--fake", a.fake]
        rc = sh(cmd, log)
        gen_s = time.time() - bt
        calls = [json.loads(p.read_text()) for p in (hub / "stages" / "main" / "calls").glob("*.json")] \
            if (hub / "stages" / "main" / "calls").exists() else []
        ok = sum(c.get("status") == "ok" for c in calls)
        entry = {"block_id": b["block_id"], "calls": b["calls"], "calls_ok": ok, "runner_rc": rc}
        if rc != 0 or not (hub / "stages" / "main" / "END.json").exists() or ok != b["calls"]:
            entry.update(result="stopped: extraction incomplete or infrastructure failure", seconds=round(gen_s))
            st["log"].append(entry)
            st.update(state="stopped", stop_reason=f"{b['block_id']}: runner rc {rc}, {ok}/{b['calls']} ok "
                                                    f"(partial replies preserved in {hub}/stages/main/calls)")
            break
        gen_secs = sum(c.get("seconds") or 0 for c in calls)
        if ok and not a.fake:
            n_prev = st.get("rate_n", 0)
            st["rate_s_per_call"] = ((st["rate_s_per_call"] or 0) * n_prev + gen_secs) / (n_prev + ok)
            st["rate_n"] = n_prev + ok
        if (hub / "stages" / "main" / "eval" / "trajectories.jsonl").exists():
            rc2 = 0
        else:
            rc2 = sh([PY, "-B", SCRIPTS / "ftx_evaluate.py", "--hub", hub, "--set", fz["set"], "--stage", "main",
                      "--require-freeze"], log)
        rc3 = rc2 or sh([PY, "-B", SCRIPTS / "ftx_analyze.py", "--hub", hub, "--set", fz["set"], "--stage", "main",
                         "--boot", "1000"], log)
        res = json.loads((hub / "analysis" / "main" / "ANALYSIS.json").read_text()) if not rc3 else None
        entry.update(seconds=round(time.time() - bt), generation_s=round(gen_secs, 1))
        if rc3 or not res["software_gates_pass"]:
            entry.update(result="stopped: software gate failure or evaluation error",
                         gates=None if res is None else res["failed_gates"])
            st["log"].append(entry)
            st.update(state="stopped", stop_reason=f"{b['block_id']}: software gate failure / evaluation error (see {log})")
            break
        entry.update(result="complete", gates="all pass")
        st["log"].append(entry)
        st["complete"].append(b["block_id"])
        st["calls_ok"] += ok
        st["elapsed_s"] = spent_before + (time.time() - t0)
        write_status(q, st)
    else:
        st.update(state="complete")
    st["elapsed_s"] = spent_before + (time.time() - t0)
    write_status(q, st)
    rcp = sh([PY, "-B", SCRIPTS / "ftx_pool.py", "--queue", q], q / "pool.log")
    st["pool_rc"] = rcp
    st["elapsed_s"] = spent_before + (time.time() - t0)
    write_status(q, st)
    print(json.dumps({k: st[k] for k in ("state", "stop_reason", "calls_ok", "elapsed_s")}))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--queue", required=True)
    p.add_argument("--manifest", required=True)
    p.add_argument("--stage-template", required=True)
    p.add_argument("--set", default="ftx")
    p.add_argument("--blocks", type=int)
    r = sub.add_parser("run")
    r.add_argument("--queue", required=True)
    r.add_argument("--fake")
    a = ap.parse_args()
    prepare(a) if a.cmd == "prepare" else run(a)


if __name__ == "__main__":
    main()
