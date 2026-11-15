"""EVT-suite fixed guarded supervisor for one study hub (adapted from ev_run.py; V1.28.0 cutoff fixes C4-N/C4-K). Host stdlib; model workers run offline in research container.

No production CLI supports fake runners, alternate analyzers or bypassing guards.
Function injection is for isolated CPU integration fixtures only.
"""
import argparse
import contextlib
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
import su_guard as cc_guard
from tempo import evsuite as S

NY = ZoneInfo("America/New_York")
PY = LP.PY


def stamp():
    return datetime.now(NY).isoformat(timespec="seconds")


def log(hub, message):
    with (Path(hub) / "driver.log").open("a") as out:
        out.write(f"{stamp()} {message}\n")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def panel(hub):
    return S.validate_config(json.loads((Path(hub) / "config/PANEL.json").read_text()))


def verify_freeze(hub):
    """Complete freeze validation (schema, full file coverage, source/driver/manifest/plan hashes; su_certify)."""
    from su_certify import check_freeze
    from su_prepare import validate_stage_configs
    problems = []
    frozen, _cfg = check_freeze(hub, problems)
    if problems:
        raise ValueError("; ".join(problems)[:1500])
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
    soft = int(remaining_s) - cc_guard.policy(panel(hub)["key"])["analysis_reserve_s"] - cc_guard.policy(panel(hub)["key"])["kill_grace_s"]
    if soft <= 0:
        raise RuntimeError("insufficient deadline reserve for worker")
    command = ["systemd-inhibit", "--what=sleep:idle", "--who=DREAM EVT suite", "--why=EVT suite collection", "--mode=block",
               "distrobox", "enter", "dream-research", "--", "unshare", "-rn", "env", "TZ=America/New_York",
               PY, "-B", str(ROOT / "scripts/su_lifeline.py"), "--",
               "timeout", "-k", "60", str(soft), PY, "-B", str(ROOT / "scripts/hold_run.py"),
               "--hub", str(hub), "--stage", stage, "--config", str(Path(hub) / f"config/stage-{stage}.json")]
    return command


def execute(command, hub, timeout_s):
    """Launch, register and wait for one worker. V1.28.0 (Codex review R5): launch and ownership are one critical
    step, and PGID registration is inside the region whose handlers guarantee the group kill, so a cutoff or
    TERM at any point after the child exists still kills its group.

    Lifeline (V1.28.0): the worker's stdin is a pipe whose only write end this driver holds (non-inheritable). The
    production worker runs under scripts/su_lifeline.py inside the container, which kills the in-container worker
    group when that pipe reaches EOF: when _kill_group closes it, or when this driver exits or is killed for any
    reason. Host-side signals alone do not reach the in-container process (V1.28.0 probe)."""
    process = None
    with (Path(hub) / "driver.log").open("a") as out:
        try:
            with uninterruptible():
                process = subprocess.Popen(command, cwd=ROOT, stdout=out, stderr=subprocess.STDOUT,
                                           stdin=subprocess.PIPE, start_new_session=True)
            atomic_json(Path(hub) / "runtime/WORKER-PGID.json", {"pgid": process.pid, "at": stamp()})
            rc = process.wait(timeout=max(1, timeout_s))
            _close_lifeline(process)
            return rc
        except subprocess.TimeoutExpired:
            _kill_group(process)
            return 124
        except BaseException:
            if process is not None:
                _kill_group(process)
            raise


KILL_TERM_WAIT_S = 10
KILL_REAP_WAIT_S = 5


def _kill_group(process):
    """TERM the group, give the leader up to 10 s, then KILL the whole group regardless (descendants may ignore
    TERM after the leader exits; leader exit is not proof that the group is gone).

    V1.28.0 (Codex C4 follow-up): the whole sequence is a critical section of the watchdog (see _alarm), so a
    cutoff or a second TERM arriving during the TERM wait can no longer pre-empt the group KILL. It is bounded (at
    most KILL_TERM_WAIT_S + KILL_REAP_WAIT_S of waiting); a cutoff that arrived meanwhile is raised at its end."""
    with uninterruptible():
        _close_lifeline(process)   # first: this is what reaches the in-container worker
        for sig in (signal.SIGTERM, signal.SIGKILL):
            try:
                os.killpg(process.pid, sig)
            except (ProcessLookupError, PermissionError):
                pass
            if sig == signal.SIGTERM:
                try:
                    process.wait(timeout=KILL_TERM_WAIT_S)
                except subprocess.TimeoutExpired:
                    pass
        try:
            process.wait(timeout=KILL_REAP_WAIT_S)
        except subprocess.TimeoutExpired:
            pass


def _close_lifeline(process):
    pipe = getattr(process, "stdin", None)
    if pipe is not None:
        try:
            pipe.close()
        except OSError:
            pass


def smoke_check(hub):
    from tempo import factored as FA
    from kconf_analyze import recipe_ok
    hub = Path(hub)
    n = panel(hub)["smoke_calls"]
    calls = {r["call_id"]: r for r in (json.loads(l) for l in (hub / "data/smoke-calls.jsonl").read_text().splitlines())}
    public = {r["target"]: r for r in (json.loads(l) for l in (hub / "data/public/smoke-targets.jsonl").read_text().splitlines())}
    records = [json.loads(p.read_text()) for p in (hub / "stages/smoke/calls").glob("*.json")]
    if len(calls) != n or len(records) != n or {r["call_id"] for r in records} != set(calls):
        raise ValueError(f"smoke records do not exactly match the {n}-call schedule")
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
    result = {"pass": True, "scheduled": n, "records": n, "semantic_accuracy_used": False}
    atomic_json(hub / "runtime/SMOKE-CHECK.json", result)
    return result


def default_analyze(hub):
    from su_analyze import write_artifacts
    return write_artifacts(hub, during_driver=True)


def default_stage_check(hub):
    from su_stage_check import check
    from su_certify import is_freeze_fault
    result = check(hub, during_driver=True)
    if not result["complete"]:
        problems = result.get("problems", [])
        raise (FreezeFault if is_freeze_fault(problems) else RuntimeError)("stage integrity: " + repr(problems)[:1200])
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
        out.write(f"\n\n### {stamp()}: {panel(hub)['study']} {status} (guarded EVT-suite driver)\n\n"
                  f"Run hub: `{hub}`. See `REPORT.md` and `RUN-STATUS.md`. "
                  "This is the single terminal notice for this study.\n")


def _invalidate_success(hub):
    """Archive, then remove, any success certificate. Idempotent: safe to resume after an interruption."""
    success, archive = hub / "DRIVER-SUCCESS.json", hub / "runtime/INVALIDATED-SUCCESS.json"
    if success.exists():
        if not archive.exists():
            archive.write_bytes(success.read_bytes())
        success.unlink()


def _failure_transition_began(hub):
    return any((hub / p).exists() for p in ("runtime/INVALIDATED-SUCCESS.json", "runtime/DRIVER-ERROR.json",
                                            "DRIVER-FAILURE.json"))


def fail(hub, step, error, analyzer):
    hub = Path(hub)
    error = repr(error)[:2000]
    log(hub, f"FAILED step={step}: {error}")
    _invalidate_success(hub)   # before any failure marker (V1.28.0, Codex recheck RC3)
    atomic_json(hub / "runtime/DRIVER-ERROR.json", {"at": stamp(), "step": step, "error": error})
    analysis_ok = False
    try:
        analyzer(hub)  # produces only incomplete descriptives when collection is incomplete
        path = hub / "analysis/dev/ANALYSIS.json"
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
        analysis_path = hub / "analysis/dev/ANALYSIS.json"
        if analysis_path.is_file():
            archive = hub / "analysis/failure"
            archive.mkdir(parents=True, exist_ok=True)
            backup = archive / "ANALYSIS-before-terminal-error.json"
            if not backup.exists():
                backup.write_bytes(analysis_path.read_bytes())
        analysis_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_json(analysis_path, {"study": panel(hub)["study"], "status": "INCOMPLETE",
                    "reading": {"status": "NOT_EVALUATED"},
                    "infrastructure": {"complete": False, "problems": [f"{step}: {error}"],
                                       "saved_record_files": count},
                    "inference_suppressed": "Supervisor failure; no reading."})
        planned = cc_guard.policy(panel(hub)["key"])["total_attempts"]
        (hub / "REPORT.md").write_text(f"# {panel(hub)['study']} incomplete run\n\nControlled failure at **{step}**.\n\n"
                                      f"{error}\n\nSaved call-record files: {count}; planned {planned} calls. "
                                      "No reading or interval statements. Preserve all partial outputs.\n")
    (hub / "RUN-STATUS.md").write_text(f"# Run status\n\n**INCOMPLETE — {step}, {stamp()}.**\n\n"
                                      f"{error}\n\nSee `REPORT.md` and `driver.log`. No automatic retry, resume or next stage.\n")
    atomic_json(hub / "DRIVER-FAILURE.json", {"at": stamp(), "step": step, "error": error,
                                             "status": "INCOMPLETE", "automatic_resume": False})


CHAIN_ENV = "DREAM_SUITE_CHAIN_DEADLINE_EPOCH"
STUDY_CEILING_S = 28800
WATCHDOG_GRACE_S = 60
CLEANUP_CUTOFF_S = 40


class FreezeFault(Exception):
    """Any failed freeze validation, wherever it occurs (Codex F3)."""


class DeadlineExceeded(BaseException):
    """Raised by the watchdog; BaseException so that no inner handler can swallow it (Codex F2)."""


def checked_freeze(hub):
    try:
        return verify_freeze(hub)
    except Exception as exc:
        raise FreezeFault(repr(exc)[:1500]) from exc


def effective_deadline(start, key=None, ceiling_s=None):
    deadline = start + (ceiling_s if ceiling_s is not None else
                        cc_guard.policy(key)["ceiling_s"] if key else STUDY_CEILING_S)
    chain = os.environ.get(CHAIN_ENV)
    if chain:
        deadline = min(deadline, int(chain))
    return deadline


_CRITICAL = {"depth": 0, "pending": None}


def _alarm(signum, frame):
    """Watchdog handler. Python runs signal handlers in the main thread whichever OS thread received the signal,
    so a flag checked here protects a critical section regardless of threads (a pthread_sigmask on the main
    thread does not: V1.28.0 test finding). Inside a critical section the cutoff is held, never dropped."""
    exc = DeadlineExceeded("study deadline reached" if signum == signal.SIGALRM else f"stopped by signal {signum}")
    if _CRITICAL["depth"]:
        _CRITICAL["pending"] = _CRITICAL["pending"] or exc
        return
    raise exc


@contextlib.contextmanager
def uninterruptible():
    """Bounded critical section: a watchdog cutoff that arrives inside is raised when the section ends."""
    _CRITICAL["depth"] += 1
    try:
        yield
    finally:
        _CRITICAL["depth"] -= 1
        if not _CRITICAL["depth"] and _CRITICAL["pending"] is not None:
            exc, _CRITICAL["pending"] = _CRITICAL["pending"], None
            raise exc


def deadline_fail(hub, step):
    """Deadline expiry: preserve partial records, report INCOMPLETE, and run no analyzer.

    Returns True, writing nothing, when the success certificate was already committed (V1.28.0, Codex review R4):
    atomic_json publishes DRIVER-SUCCESS.json by os.replace, so its presence is the durable commit point, and a
    cutoff arriving after it must not rewrite the artifacts it binds. The check runs under the cleanup cutoff."""
    hub = Path(hub)
    signal.setitimer(signal.ITIMER_REAL, CLEANUP_CUTOFF_S)   # hard cutoff for cleanup, inside the 60 s grace
    if (hub / "DRIVER-SUCCESS.json").is_file():
        if not _failure_transition_began(hub):
            return True
        _invalidate_success(hub)   # a failure transition had begun: finish it consistently (RC3)
    log(hub, f"DEADLINE reached during step={step}; partial records preserved; no analysis run")
    atomic_json(hub / "runtime/DEADLINE-EXCEEDED.json", {"at": stamp(), "step": step})
    out = hub / "analysis/dev"
    out.mkdir(parents=True, exist_ok=True)
    for name in ("scored.jsonl",):
        if (out / name).exists():
            archive = hub / "analysis/invalidated" / datetime.now().strftime("%Y%m%dT%H%M%S")
            archive.mkdir(parents=True, exist_ok=True)
            (out / name).rename(archive / name)
    count = sum(1 for _ in (hub / "stages").glob("*/calls/*.json"))
    atomic_json(out / "ANALYSIS.json", {"study": panel(hub)["study"], "status": "INCOMPLETE",
                "reading": {"status": "NOT_EVALUATED"},
                "infrastructure": {"complete": False, "problems": [f"deadline reached during {step}"],
                                   "saved_record_files": count},
                "inference_suppressed": "Deadline reached; no reading."})
    (hub / "REPORT.md").write_text(f"# {panel(hub)['study']} incomplete run\n\nThe study deadline was reached during "
                                  f"**{step}**. Saved call-record files: {count}. No reading. Partial outputs are "
                                  "preserved.\n")
    (hub / "RUN-STATUS.md").write_text(f"# Run status\n\n**INCOMPLETE — deadline reached during {step}, {stamp()}.**\n")
    atomic_json(hub / "DRIVER-FAILURE.json", {"at": stamp(), "step": step, "error": "deadline reached",
                                             "status": "INCOMPLETE", "automatic_resume": False})
    return False


def drive(hub, *, worker=production_worker, gpu_probe=gpu_available, analyzer=default_analyze,
          stage_checker=default_stage_check, smoke_checker=smoke_check, notify=True, guard=None, ceiling_s=None):
    """guard and ceiling_s exist for isolated CPU fixtures only; the production CLI exposes neither."""
    from su_analyze import PLANS
    from su_certify import certify, inventory
    guard = guard or cc_guard.check
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
    # Match the inherited worker's second-resolution timestamps exactly.
    start = int(time.time())
    step = "freeze"
    previous = signal.signal(signal.SIGALRM, _alarm)
    previous_term = signal.signal(signal.SIGTERM, _alarm)
    previous_int = signal.signal(signal.SIGINT, _alarm)
    # Supervision starts before any validation and stays active through terminal artifacts (recheck R5).
    signal.setitimer(signal.ITIMER_REAL, max(1, effective_deadline(start, None, ceiling_s) - time.time()
                                              - WATCHDOG_GRACE_S))
    try:
        study, key = panel(hub)["study"], panel(hub)["key"]
        total = cc_guard.policy(key)["total_attempts"]
        checked_freeze(hub)
        log(hub, "freeze and driver/model hashes passed")
        step = "GPU availability"
        log(hub, "GPU check " + json.dumps(gpu_probe()))
        step = "budget"
        deadline = effective_deadline(start, key, ceiling_s)
        if deadline - start <= WATCHDOG_GRACE_S:
            raise RuntimeError("no usable time inside the study/chain deadline")
        budget = {"driver_start_epoch": start, "deadline_epoch": deadline,
                  "deadline_iso": datetime.fromtimestamp(deadline, NY).isoformat(), "timezone": "America/New_York",
                  "study_ceiling_s": ceiling_s if ceiling_s is not None else cc_guard.policy(key)["ceiling_s"],
                  "chain_deadline_epoch": int(os.environ[CHAIN_ENV]) if os.environ.get(CHAIN_ENV) else None}
        with (hub / "config/DEADLINE.json").open("x") as out:
            out.write(json.dumps(budget, indent=2) + "\n")
        for stage in ("smoke", "main"):
            step = f"{stage} guard"
            checked_freeze(hub)
            if json.loads((hub / "config/DEADLINE.json").read_text()) != budget:
                raise FreezeFault("DEADLINE.json differs from the supervisor's budget")
            result = guard(hub, stage)
            atomic_json(hub / f"runtime/GUARD-{stage}.json", result)
            log(hub, "guard " + json.dumps(result))
            if not result["ok"]:
                raise RuntimeError(result["problems"])
            (hub / "RUN-STATUS.md").write_text(f"# Run status\n\n**RUNNING — {stage}, {stamp()}.**\n\n"
                                              f"{study}: {total} scheduled calls; no retries. "
                                              f"Hard deadline {datetime.fromtimestamp(deadline, NY).isoformat()}.\n")
            step = f"{stage} worker"
            remaining = min(result["remaining_s"], deadline - time.time())
            command = worker(hub, stage, remaining)
            rc = execute(command, hub, remaining - 90)
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
        handoff = analyzer(hub)
        step = "final check"
        checked_freeze(hub)
        result = json.loads((hub / "analysis/dev/ANALYSIS.json").read_text())
        problems = certify(hub, during_driver=True)
        from su_certify import is_freeze_fault
        if is_freeze_fault(problems):
            raise FreezeFault("final check: " + repr(problems)[:800])
        current = inventory(hub)
        commit = handoff.get("artifact_commitment") if isinstance(handoff, dict) else None
        if not isinstance(commit, dict) or commit.get("status") != "COMPLETE" or \
                commit.get("reading") != result.get("reading", {}).get("status") or \
                commit.get("evidence_inventory_sha256") != current or \
                commit.get("analysis_sha256") != sha(hub / "analysis/dev/ANALYSIS.json") or \
                commit.get("report_sha256") != sha(hub / "REPORT.md") or \
                not (hub / "analysis/dev/scored.jsonl").is_file() or \
                commit.get("scored_sha256") != sha(hub / "analysis/dev/scored.jsonl"):
            raise RuntimeError("analysis artifacts differ from the analyzer's handoff commitment")
        if problems or result.get("study") != study or result.get("status") != "COMPLETE" \
                or result.get("infrastructure", {}).get("problems") \
                or result.get("evidence_inventory_sha256") != current \
                or result.get("reading", {}).get("status") not in PLANS[key]["statuses"]:
            raise RuntimeError("final analysis is not a complete valid decision for the current evidence: "
                               + repr(problems)[:800])
        if time.time() > deadline:
            raise RuntimeError("analysis finished after absolute deadline")
        log(hub, "COMPLETE " + result["reading"]["status"])
        certificate = {
            "finished": True, "at": stamp(), "study": study, "key": key, "reading": result["reading"]["status"],
            "frozen_protocol_sha256": sha(hub / "config/FROZEN-PROTOCOL.json"), "inventory_sha256": current,
            "analysis_sha256": commit["analysis_sha256"], "scored_sha256": commit["scored_sha256"],
            "report_sha256": commit["report_sha256"],
            "certifies": ["freeze", "GPU", "budget", "guards", "smoke", "feasibility", "main", "integrity",
                          "analysis", "final check"]}
        try:
            atomic_json(hub / "DRIVER-SUCCESS.json", certificate)
        except Exception as commit_error:
            # The commit point is os.replace inside atomic_json: if the certificate is in place, an error after it
            # (e.g. temporary-file cleanup) is auxiliary and must not turn a committed success into a failure.
            try:
                committed = json.loads((hub / "DRIVER-SUCCESS.json").read_text()) == certificate
            except (OSError, ValueError):
                committed = False
            if not committed:
                raise
            try:
                log(hub, f"success committed; auxiliary error after commit: {commit_error!r}")
            except OSError:
                pass
        step = "notification"
        if notify:
            try:
                notify_once(hub, "COMPLETE / " + result["reading"]["status"])
            except DeadlineExceeded:
                return 0  # cutoff during the notice: stop at once; the certified success above stands
            except Exception as notice_error:
                try:
                    log(hub, f"protocol complete; local notice failed: {notice_error!r}")
                    atomic_json(hub / "runtime/NOTICE-ERROR.json", {"at": stamp(), "error": repr(notice_error)})
                except OSError:
                    pass  # A delivery/logging failure cannot undo the valid completed analysis.
                except DeadlineExceeded:
                    return 0
        return 0
    except DeadlineExceeded:
        if _terminal(hub, step, notify, analyzer, None):
            return 0
    except Exception as exc:
        if _terminal(hub, "freeze" if isinstance(exc, FreezeFault) else step, notify, analyzer, exc):
            return 0
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)
        signal.signal(signal.SIGTERM, previous_term)
        signal.signal(signal.SIGINT, previous_int)
        _CRITICAL.update(depth=0, pending=None)
        lock.close()
    return 1


def _terminal(hub, step, notify, analyzer, exc):
    """Write terminal records and the failure notice without ever outliving the cutoff (Codex C4-N).

    exc is None for a deadline; otherwise fail() runs under the still-armed study alarm. If that alarm fires
    during fail(), the deadline path takes over. deadline_fail() arms the one fixed cleanup cutoff; nothing
    re-arms or extends it afterwards. When any cutoff fires, the driver stops at once: no further log, record
    or notice writes. A terminal record that was not yet written stays missing, which the chain treats as a
    FAULT (fail-closed). Returns True when a success certificate was already committed (R4): it stands, and no
    failure record or notice is written."""
    try:
        if exc is not None:
            try:
                fail(hub, step, exc, analyzer)
            except DeadlineExceeded:
                exc = None
        if exc is None and deadline_fail(hub, step):
            return True
        _notify_incomplete(hub, notify)
    except DeadlineExceeded:
        pass
    return False


def _notify_incomplete(hub, notify):
    """Ordinary notice/log failures are recorded; the watchdog's DeadlineExceeded always propagates (C4-N)."""
    if not notify:
        return
    try:
        notify_once(hub, "INCOMPLETE")
    except Exception as notice_error:
        try:
            log(hub, f"local notice failed: {notice_error!r}")
        except OSError:
            pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--hub", required=True)
    args = parser.parse_args()
    raise SystemExit(drive(args.hub))
