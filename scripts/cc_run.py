"""CCONF-v1 fixed guarded supervisor. Host stdlib; model workers run offline in research container.

No production CLI supports fake runners, alternate analyzers or bypassing guards.
Function injection is for isolated CPU integration fixtures only.
"""
import argparse
from datetime import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from zoneinfo import ZoneInfo

from _bootstrap import ROOT
from dream_core import localpaths as LP  # public release: local paths from environment
from dream_core.ledger import atomic_json, release_source_hash
import cc_guard

NY = ZoneInfo("America/New_York")
PY = LP.PY


def stamp():
    return datetime.now(NY).isoformat(timespec="seconds")


def log(hub, message):
    with (Path(hub) / "driver.log").open("a") as out:
        out.write(f"{stamp()} {message}\n")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_freeze(hub):
    from cc_prepare import validate_stage_configs
    hub = Path(hub)
    frozen = json.loads((hub / "config/FROZEN-PROTOCOL.json").read_text())
    if frozen.get("study") != "CCONF-v1" or frozen.get("source_sha256") != release_source_hash(ROOT):
        raise ValueError("study/source differs from freeze")
    for section in ("design", "config", "data", "phase0"):
        if not frozen.get(section):
            raise ValueError(f"missing frozen {section} mapping")
        for rel, digest in frozen[section].items():
            if sha(hub / section / rel) != digest:
                raise ValueError(f"frozen file mismatch: {section}/{rel}")
    if sha(hub / "run_cc.sh") != frozen["driver_sha256"]:
        raise ValueError("driver differs from freeze")
    if sha(frozen["model_manifest_path"]) != frozen["model_manifest_sha256"]:
        raise ValueError("model manifest differs from freeze")
    validate_stage_configs(hub)
    return frozen


def gpu_available():
    used = subprocess.check_output(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                                   text=True, timeout=20).strip().splitlines()
    processes = subprocess.check_output(["nvidia-smi", "--query-compute-apps=process_name", "--format=csv,noheader"],
                                        text=True, timeout=20).lower()
    if not used or int(used[0]) > 3072 or "python" in processes:
        raise RuntimeError("GPU is busy; existing applications were not interrupted")
    return {"memory_used_mib": int(used[0]), "python_compute_present": False}


def production_worker(hub, stage, remaining_s):
    soft = int(remaining_s) - cc_guard.POLICY["analysis_reserve_s"] - cc_guard.POLICY["kill_grace_s"]
    if soft <= 0:
        raise RuntimeError("insufficient deadline reserve for worker")
    command = ["systemd-inhibit", "--what=sleep:idle", "--who=DREAM CCONF", "--why=CCONF collection", "--mode=block",
               "distrobox", "enter", "dream-research", "--", "unshare", "-rn", "env", "TZ=America/New_York",
               "timeout", "-k", "60", str(soft), PY, "-B", str(ROOT / "scripts/hold_run.py"),
               "--hub", str(hub), "--stage", stage, "--config", str(Path(hub) / f"config/stage-{stage}.json")]
    return command


def execute(command, hub, timeout_s):
    with (Path(hub) / "driver.log").open("a") as out:
        process = subprocess.Popen(command, cwd=ROOT, stdout=out, stderr=subprocess.STDOUT,
                                   stdin=subprocess.DEVNULL, start_new_session=True)
        try:
            return process.wait(timeout=max(1, timeout_s))
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            return 124


def smoke_check(hub):
    from tempo import factored as FA
    from kconf_analyze import recipe_ok
    hub = Path(hub)
    calls = {r["call_id"]: r for r in (json.loads(l) for l in (hub / "data/smoke-calls.jsonl").read_text().splitlines())}
    public = {r["target"]: r for r in (json.loads(l) for l in (hub / "data/public/smoke-targets.jsonl").read_text().splitlines())}
    records = [json.loads(p.read_text()) for p in (hub / "stages/smoke/calls").glob("*.json")]
    if len(calls) != 36 or len(records) != 36 or {r["call_id"] for r in records} != set(calls):
        raise ValueError("smoke records do not exactly match 36-call schedule")
    end = json.loads((hub / "stages/smoke/END.json").read_text())
    if end.get("finished") is not True or (hub / "stages/smoke/STOP.json").exists():
        raise ValueError("smoke stage did not finish")
    for rec in records:
        cid = rec["call_id"]
        if rec.get("status") != "ok" or rec.get("complete") is not True or rec.get("stop") != "eos" \
                or not recipe_ok(rec) or rec.get("user_sha256") != calls[cid]["user_sha256"] \
                or rec.get("input_tokens", 10**9) > 2048:
            raise ValueError(f"smoke record recipe/status mismatch: {cid}")
        if FA.compile_reply(rec["raw"], public[cid.rsplit("|", 1)[0]]["registry"])[1]["claims"] is None:
            raise ValueError(f"smoke output cannot normalize: {cid}")
    result = {"pass": True, "scheduled": 36, "records": 36, "semantic_accuracy_used": False}
    atomic_json(hub / "runtime/SMOKE-CHECK.json", result)
    return result


def default_analyze(hub):
    from cc_analyze import write_artifacts
    return write_artifacts(hub)


def default_stage_check(hub):
    from cc_stage_check import check
    result = check(hub)
    if not result["complete"]:
        raise RuntimeError("stage integrity: " + repr(result.get("problems", []))[:1200])
    return result


def notify_once(hub, status):
    hub = Path(hub)
    if not (hub / "RUN-STATUS.md").is_file() or not (hub / "REPORT.md").is_file():
        raise ValueError("terminal artifacts must exist before notification")
    marker = hub / "runtime/NOTICE-SENT.json"
    if marker.exists():
        return
    cfg = hub / "config/COORDINATION.json"
    if not cfg.is_file():
        return
    path = Path(json.loads(cfg.read_text())["path"])
    with marker.open("x") as out:
        out.write(json.dumps({"at": stamp(), "status": status}) + "\n")
    with path.open("a") as out:
        out.write(f"\n\n### {stamp()}: CCONF-v1 {status} (guarded driver)\n\n"
                  f"Run hub: `{hub}`. See `REPORT.md` and `RUN-STATUS.md`. "
                  "This is the single terminal notice; no next study was started.\n")


def fail(hub, step, error, analyzer):
    hub = Path(hub)
    error = repr(error)[:2000]
    log(hub, f"FAILED step={step}: {error}")
    atomic_json(hub / "runtime/DRIVER-ERROR.json", {"at": stamp(), "step": step, "error": error})
    success = hub / "DRIVER-SUCCESS.json"
    if success.exists():
        (hub / "runtime/INVALIDATED-SUCCESS.json").write_bytes(success.read_bytes())
        success.unlink()
    analysis_ok = False
    try:
        analyzer(hub)  # produces only incomplete descriptives when collection is incomplete
        path = hub / "analysis/confirm/ANALYSIS.json"
        analysis_ok = path.is_file() and json.loads(path.read_text()).get("status") == "INCOMPLETE"
    except Exception as exc:
        log(hub, f"incomplete analyzer unavailable: {exc!r}")
    if not analysis_ok or not (hub / "REPORT.md").is_file():
        count = sum(1 for _ in (hub / "stages").glob("*/calls/*.json"))
        old_report = hub / "REPORT.md"
        if old_report.is_file():
            archive = hub / "analysis/failure"
            archive.mkdir(parents=True, exist_ok=True)
            backup = archive / "REPORT-before-terminal-error.md"
            if not backup.exists():
                backup.write_bytes(old_report.read_bytes())
        analysis_path = hub / "analysis/confirm/ANALYSIS.json"
        if analysis_path.is_file():
            archive = hub / "analysis/failure"
            archive.mkdir(parents=True, exist_ok=True)
            backup = archive / "ANALYSIS-before-terminal-error.json"
            if not backup.exists():
                backup.write_bytes(analysis_path.read_bytes())
        analysis_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_json(analysis_path, {"study": "CCONF-v1", "status": "INCOMPLETE",
                    "qualification": {"status": "NOT_EVALUATED"},
                    "infrastructure": {"complete": False, "problems": [f"{step}: {error}"],
                                       "saved_record_files": count},
                    "inference_suppressed": "Supervisor failure; no gates or bounds."})
        (hub / "REPORT.md").write_text(f"# CCONF-v1 incomplete run\n\nControlled failure at **{step}**.\n\n"
                                      f"{error}\n\nSaved call-record files: {count}; planned 2,340 calls. "
                                      "No qualification or confidence statements. Preserve all partial outputs.\n")
    (hub / "RUN-STATUS.md").write_text(f"# Run status\n\n**INCOMPLETE — {step}, {stamp()}.**\n\n"
                                      f"{error}\n\nSee `REPORT.md` and `driver.log`. No automatic retry, resume or next stage.\n")
    atomic_json(hub / "DRIVER-FAILURE.json", {"at": stamp(), "step": step, "error": error,
                                             "status": "INCOMPLETE", "automatic_resume": False})


def drive(hub, *, worker=production_worker, gpu_probe=gpu_available, analyzer=default_analyze,
          stage_checker=default_stage_check, smoke_checker=smoke_check, notify=True):
    os.environ["TZ"] = "America/New_York"
    time.tzset()
    hub = Path(hub).resolve()
    (hub / "runtime").mkdir(exist_ok=True)
    lock = (hub / "runtime/DRIVER.lock").open("a+")
    try:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock.close()
        print("run already active; no state changed", file=sys.stderr)
        return 9
    if any((hub / p).exists() for p in ("config/DEADLINE.json", "DRIVER-SUCCESS.json", "DRIVER-FAILURE.json")) \
            or any(path.is_file() for path in (hub / "stages").rglob("*")):
        lock.close()
        print("prior run artifacts exist; automatic resume refused", file=sys.stderr)
        return 9
    # Match the inherited worker's second-resolution timestamps exactly. An
    # arbitrary float epoch cannot round-trip through a microsecond ISO string.
    start = int(time.time())
    step = "freeze"
    try:
        verify_freeze(hub)
        log(hub, "freeze and driver/model hashes passed")
        step = "GPU availability"
        log(hub, "GPU check " + json.dumps(gpu_probe()))
        deadline = start + cc_guard.POLICY["ceiling_s"]
        with (hub / "config/DEADLINE.json").open("x") as out:
            out.write(json.dumps({"driver_start_epoch": start, "deadline_epoch": deadline,
                                  "deadline_iso": datetime.fromtimestamp(deadline, NY).isoformat(),
                                  "timezone": "America/New_York"}, indent=2) + "\n")
        for stage in ("smoke", "main"):
            step = f"{stage} guard"
            verify_freeze(hub)
            result = cc_guard.check(hub, stage)
            atomic_json(hub / f"runtime/GUARD-{stage}.json", result)
            log(hub, "guard " + json.dumps(result))
            if not result["ok"]:
                raise RuntimeError(result["problems"])
            (hub / "RUN-STATUS.md").write_text(f"# Run status\n\n**RUNNING — {stage}, {stamp()}.**\n\n"
                                              "CCONF-v1: 2,340 scheduled calls; no retries. "
                                              f"Hard deadline {datetime.fromtimestamp(deadline, NY).isoformat()}.\n")
            step = f"{stage} worker"
            command = worker(hub, stage, result["remaining_s"])
            rc = execute(command, hub, result["remaining_s"] - 90)
            log(hub, f"{stage} worker exit={rc}")
            if rc != 0:
                raise RuntimeError(f"{stage} worker exited {rc}")
            if stage == "smoke":
                step = "structural smoke"
                smoke_checker(hub)
                log(hub, "structural smoke passed; semantic accuracy not used")
        step = "stage integrity"
        stage_checker(hub)
        step = "analysis"
        analyzer(hub)
        step = "final check"
        result = json.loads((hub / "analysis/confirm/ANALYSIS.json").read_text())
        if result.get("study") != "CCONF-v1" or result.get("status") != "COMPLETE" \
                or result.get("infrastructure", {}).get("problems") \
                or result.get("qualification", {}).get("status") not in ("QUALIFIED", "NOT_QUALIFIED"):
            raise RuntimeError("final analysis is not a complete valid decision")
        verify_freeze(hub)
        if time.time() > deadline:
            raise RuntimeError("analysis finished after absolute deadline")
        log(hub, "COMPLETE " + result["qualification"]["status"])
        atomic_json(hub / "DRIVER-SUCCESS.json", {"finished": True, "at": stamp(), "study": "CCONF-v1",
                    "qualification": result["qualification"]["status"], "certifies":
                    ["freeze", "GPU", "guards", "smoke", "feasibility", "main", "integrity", "analysis", "final check"]})
        if notify:
            try:
                notify_once(hub, "COMPLETE / " + result["qualification"]["status"])
            except Exception as notice_error:
                try:
                    log(hub, f"protocol complete; local notice failed: {notice_error!r}")
                    atomic_json(hub / "runtime/NOTICE-ERROR.json", {"at": stamp(), "error": repr(notice_error)})
                except OSError:
                    pass  # A delivery/logging failure cannot undo the valid completed analysis.
        return 0
    except Exception as exc:
        fail(hub, step, exc, analyzer)
        if notify:
            try:
                notify_once(hub, "INCOMPLETE")
            except Exception as notice_error:
                log(hub, f"local notice failed: {notice_error!r}")
        return 1
    finally:
        lock.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--hub", required=True)
    args = parser.parse_args()
    raise SystemExit(drive(args.hub))
