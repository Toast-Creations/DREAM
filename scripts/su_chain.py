"""EVT-suite chain: run the frozen study hubs back to back (A -> B -> C), each through its own guarded driver.

Host stdlib only; no model imports. Revised after the Codex pre-freeze review (F2, F3):
  - exclusive chain claim: a lock plus a create-once start marker; no resume, even after an interrupted chain;
  - before any study starts: exactly three distinct hubs with keys A, B, C in that order, no prior output or
    terminal artifacts, and valid complete freezes for all three; a pre-output chain commitment records the chain
    spec, the source hash and each frozen-protocol hash, and every later launch re-verifies them;
  - overall 24-hour ceiling: a study starts only if its conservative estimate fits; each child gets the absolute
    chain deadline (minus a grace) in its environment and enforces min(own 8 h, chain deadline) with a watchdog;
    the chain itself waits with a timeout and terminates the child's process group at the chain deadline;
  - a child counts as COMPLETE only with exit 0, one valid matching success certificate, a legal reading, no
    failure marker and a clean completion validation (su_certify); anything contradictory is a fault;
  - stop-on-fault: a freeze or GPU-availability failure, a contradictory terminal state or a chain-deadline kill
    stops the chain; any other INCOMPLETE study is recorded and the next, independent study still runs.
"""
import argparse
import contextlib
import fcntl
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from _bootstrap import ROOT
from dream_core.ledger import atomic_json, release_source_hash
from tempo import evsuite as S

NY = ZoneInfo("America/New_York")
CHAIN_CEILING_S = 24 * 3600
CHILD_GRACE_S = 300      # child deadline = chain deadline - 300 s (its own watchdog fires 60 s before that)
KILL_RESERVE_S = 150     # TERM at chain deadline - 150 s, KILL by chain deadline - 30 s: grace inside the ceiling
STATUS_CUTOFF_S = 30     # after the bounded kill (<= 37 s, run once): status work must finish by chain deadline - 83 s
LIFELINE_SETTLE_S = 30   # su_lifeline: TERM grace 10 s + KILL wait 5 s, with margin
PGID_POLL_S = 2          # the chain caches the driver's current worker PGID this often, outside any critical section
SECONDS_PER_CALL_CONSERVATIVE = 14.5
FIXED_OVERHEAD_S = 1200
STOP_STEPS = ("freeze", "GPU availability")
KEYS = ("A", "B", "C")


class ChainDeadline(BaseException):
    """Whole-chain watchdog (validation, launches, certification, status writing): fires at ceiling - reserve."""


class ChainTerminated(ChainDeadline):
    """SIGTERM/SIGINT to the chain (V1.28.0, Codex review R2): same bounded cleanup as the deadline."""


_CRITICAL = {"depth": 0, "pending": None}


def _hold_or_raise(exc):
    if _CRITICAL["depth"]:
        _CRITICAL["pending"] = _CRITICAL["pending"] or exc
        return
    raise exc


def _chain_alarm(signum, frame):
    """Held (not dropped) inside a critical section; see su_run._alarm for why a flag, not a signal mask."""
    _hold_or_raise(ChainDeadline("chain ceiling reached"))


_STOPPING = {"on": False}


def _chain_term(signum, frame):
    if _STOPPING["on"]:
        return   # already stopping: a repeated TERM/INT must not cut the remaining cleanup short (Codex RC1)
    _hold_or_raise(ChainTerminated(f"chain stopped by signal {signum}"))


@contextlib.contextmanager
def uninterruptible():
    _CRITICAL["depth"] += 1
    try:
        yield
    finally:
        _CRITICAL["depth"] -= 1
        if not _CRITICAL["depth"] and _CRITICAL["pending"] is not None:
            exc, _CRITICAL["pending"] = _CRITICAL["pending"], None
            raise exc


def stamp():
    return datetime.now(NY).isoformat(timespec="seconds")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def estimate_s(hub):
    cfg = S.validate_config(json.loads((Path(hub) / "config/PANEL.json").read_text()))
    return (cfg["main_calls"] + cfg["smoke_calls"]) * SECONDS_PER_CALL_CONSERVATIVE + FIXED_OVERHEAD_S


def _pristine(hub):
    hub = Path(hub)
    return not any((hub / p).exists() for p in ("config/DEADLINE.json", "DRIVER-SUCCESS.json", "DRIVER-FAILURE.json",
                                                 "runtime", "analysis")) and \
        not any(p.is_file() for p in (hub / "stages").rglob("*"))


def validate_chain(chain_dir):
    """-> (hubs, commitment) or raise ValueError before any study starts."""
    from su_run import verify_freeze
    spec = json.loads((chain_dir / "CHAIN.json").read_text())
    names = spec.get("hubs")
    if not isinstance(names, list) or len(names) != 3 or len(set(names)) != 3:
        raise ValueError("CHAIN.json must list exactly three distinct hubs")
    hubs = [(chain_dir / n).resolve() for n in names]
    if len(set(hubs)) != 3 or any(h.parent != chain_dir for h in hubs):
        raise ValueError("chain hubs must be distinct direct children of the chain directory")
    for key, hub in zip(KEYS, hubs):
        cfg = S.validate_config(json.loads((hub / "config/PANEL.json").read_text()))
        if cfg["key"] != key:
            raise ValueError(f"{hub.name}: key {cfg['key']} out of the required A, B, C order")
        if not _pristine(hub):
            raise ValueError(f"{hub.name}: prior output or terminal artifacts exist")
        verify_freeze(hub)
    commitment = {"suite": S.SUITE, "chain_spec_sha256": sha(chain_dir / "CHAIN.json"),
                  "source_sha256": release_source_hash(ROOT),
                  "hubs": [{"name": h.name, "key": k, "frozen_protocol_sha256": sha(h / "config/FROZEN-PROTOCOL.json")}
                           for k, h in zip(KEYS, hubs)]}
    return hubs, commitment


def _freeze_ok(hub):
    from su_run import verify_freeze
    try:
        verify_freeze(hub)
        return True
    except Exception:
        return False


def _killpg(pgid, sig):
    try:
        os.killpg(pgid, sig)
    except (ProcessLookupError, PermissionError):
        pass


TERM_WAIT_MAX_S = 30      # driver's own cleanup: worker kill <= 15 s, then terminal records under its 40 s cutoff
REAP_WAIT_S = 5
WORKER_TERM_WAIT_S = 2


def read_worker_pgid(hub):
    """The driver's current worker PGID, or None. File I/O: never called inside a critical section (R1)."""
    try:
        pgid = json.loads((Path(hub) / "runtime/WORKER-PGID.json").read_text())["pgid"]
        return pgid if isinstance(pgid, int) and pgid > 1 else None
    except (OSError, ValueError, KeyError, TypeError):
        return None


def terminate_study(proc, hub, grace_s, running=None):
    """TERM the driver group (its handler kills its worker group), then KILL both groups.

    V1.28.0: the whole sequence is a critical section of the chain watchdog and of SIGTERM/SIGINT (C4-K, R2), so
    no cutoff or stop signal can pre-empt either group KILL. It contains no file I/O (R1): the worker PGID is the
    one the chain cached while it waited (running["worker_pgid"]). The group KILL is sent whether or not the
    leader is still alive (R3); a dead leader only skips the waits. Waiting is bounded by
    min(TERM_WAIT_MAX_S, grace_s) + REAP_WAIT_S + WORKER_TERM_WAIT_S; a cutoff that arrived meanwhile is raised at
    the end, after both KILLs. running["cleaned"] is set inside the section so cleanup is never repeated."""
    running = running if running is not None else {}
    with uninterruptible():
        leader_alive = proc.poll() is None
        _killpg(proc.pid, signal.SIGTERM)
        if leader_alive:
            try:
                proc.wait(timeout=max(0, min(TERM_WAIT_MAX_S, grace_s)))
            except subprocess.TimeoutExpired:
                pass
        _killpg(proc.pid, signal.SIGKILL)   # always: descendants may outlive the leader
        try:
            proc.wait(timeout=REAP_WAIT_S)
        except subprocess.TimeoutExpired:
            pass
        pgid = running.get("worker_pgid")
        if pgid is not None:   # the worker runs in its own session; never leave it orphaned
            _killpg(pgid, signal.SIGTERM)
            time.sleep(WORKER_TERM_WAIT_S)
            _killpg(pgid, signal.SIGKILL)
        running["cleaned"] = True


def child_outcome(hub, rc):
    """Classify one finished child strictly (Codex F3.3)."""
    from su_analyze import PLANS
    from su_certify import certify
    key = S.validate_config(json.loads((hub / "config/PANEL.json").read_text()))["key"]
    success, failure = hub / "DRIVER-SUCCESS.json", hub / "DRIVER-FAILURE.json"
    if success.exists() and failure.exists():
        return {"state": "FAULT", "reason": "contradictory terminal records"}, True
    if success.exists():
        try:
            s = json.loads(success.read_text())
        except ValueError:
            return {"state": "FAULT", "reason": "unreadable success certificate"}, True
        problems = certify(hub)
        if rc != 0 or s.get("study") != S.SPECS[key]["study"] or s.get("reading") not in PLANS[key]["statuses"] \
                or problems:
            return {"state": "FAULT", "reason": f"success certificate not valid (exit {rc})",
                    "problems": problems[:5]}, True
        return {"state": "COMPLETE", "reading": s["reading"]}, False
    if failure.exists():
        try:
            step = json.loads(failure.read_text()).get("step")
        except ValueError:
            return {"state": "FAULT", "reason": "unreadable failure record"}, True
        return {"state": "INCOMPLETE", "step": step, "exit": rc}, step in STOP_STEPS
    return {"state": "FAULT", "reason": f"no terminal record (exit {rc})"}, True


def run_chain(chain_dir, command=None, ceiling_s=CHAIN_CEILING_S, estimate=estimate_s):
    """command/ceiling_s/estimate exist for isolated CPU fixtures; the CLI exposes none of them."""
    chain_dir = Path(chain_dir).resolve()
    lock = (chain_dir / "CHAIN.lock").open("a+")
    try:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock.close()
        raise SystemExit("chain already active")
    try:
        try:
            with (chain_dir / "CHAIN-STARTED.json").open("x") as out:
                out.write(json.dumps({"started": stamp(), "pid": os.getpid()}) + "\n")
        except FileExistsError:
            raise SystemExit("chain already started once; no resume")
        command = command or (lambda hub: [str(hub / "run_su.sh")])
        start = time.time()
        mono_end = time.monotonic() + ceiling_s     # immutable monotonic budget for every wait
        chain_deadline = start + ceiling_s          # epoch, for audit and the children's deadlines
        previous = {sig: signal.signal(sig, handler) for sig, handler in
                    ((signal.SIGALRM, _chain_alarm), (signal.SIGTERM, _chain_term), (signal.SIGINT, _chain_term))}
        signal.setitimer(signal.ITIMER_REAL, max(1, ceiling_s - KILL_RESERVE_S))
        running = {}
        try:
            return _run(chain_dir, command, start, mono_end, chain_deadline, estimate, running)
        except ChainDeadline as stopped:
            # Kill first (bounded, uncut by design, once), then arm one fixed cutoff for the rest (C4-K, R1-R3).
            # From here on, TERM/INT are ignored; only the fixed status cutoff (SIGALRM) can end this handler.
            _STOPPING["on"] = True
            _CRITICAL["pending"] = None if isinstance(_CRITICAL["pending"], ChainTerminated) else _CRITICAL["pending"]
            hub = running.get("hub")
            status = {"started": stamp(), "start_epoch": start, "ceiling_epoch": chain_deadline,
                      "state": "CHAIN_TERMINATED" if isinstance(stopped, ChainTerminated) else "CHAIN_DEADLINE",
                      "reason": str(stopped), "running": hub.name if hub else None}
            try:
                if running.get("proc") is not None and not running.get("cleaned"):
                    terminate_study(running["proc"], hub, TERM_WAIT_MAX_S, running)
                signal.setitimer(signal.ITIMER_REAL, STATUS_CUTOFF_S)
                if running.get("proc") is not None:
                    # A worker registered after the last poll: read under the cutoff (not uninterruptible), then
                    # KILL its group at once (R1, R5).
                    late = read_worker_pgid(hub)
                    if late is not None and late != running.get("worker_pgid"):
                        with uninterruptible():
                            _killpg(late, signal.SIGKILL)
                        status["late_worker_group_killed"] = late
                status["finished"] = stamp()
                try:
                    old = json.loads((chain_dir / "CHAIN-STATUS.json").read_text())
                    status["studies"] = old.get("studies", [])
                except (OSError, ValueError):
                    status["studies"] = []
                atomic_json(chain_dir / "CHAIN-STATUS.json", status)
            except ChainDeadline:
                status["status_write"] = "cut off"   # a cutoff after the kill: stop at once, no more writes
            return status
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            for sig, handler in previous.items():
                signal.signal(sig, handler)
            _CRITICAL.update(depth=0, pending=None)
            _STOPPING["on"] = False
    finally:
        lock.close()


def _wait_caching_worker(proc, hub, running, wait_end):
    """Wait for the driver until the monotonic wait_end, caching its current worker PGID every PGID_POLL_S under
    the chain watchdog (bounded by it, never inside a critical section). Raises TimeoutExpired at wait_end."""
    while True:
        remaining = wait_end - time.monotonic()
        if remaining <= 0:
            raise subprocess.TimeoutExpired(proc.args, 0)
        try:
            return proc.wait(timeout=min(PGID_POLL_S, remaining))
        except subprocess.TimeoutExpired:
            pgid = read_worker_pgid(hub)
            if pgid is not None:
                running["worker_pgid"] = pgid


def _run(chain_dir, command, start, mono_end, chain_deadline, estimate, running):
    status = {"started": stamp(), "start_epoch": start, "ceiling_epoch": chain_deadline, "studies": []}

    def log(msg):
        with (chain_dir / "chain.log").open("a") as out:
            out.write(f"{stamp()} {msg}\n")
    try:
        hubs, commitment = validate_chain(chain_dir)
    except Exception as exc:
        status.update(state="REFUSED", reason=repr(exc)[:1000], finished=stamp())
        atomic_json(chain_dir / "CHAIN-STATUS.json", status)
        log(f"chain refused: {exc!r}")
        return status
    commitment["committed_at"] = stamp()
    with (chain_dir / "CHAIN-COMMITMENT.json").open("x") as out:
        out.write(json.dumps(commitment, indent=2) + "\n")
    committed_bytes = (chain_dir / "CHAIN-COMMITMENT.json").read_bytes()
    atomic_json(chain_dir / "CHAIN-STATUS.json", status)
    stop = None
    for hub, pinned in zip(hubs, commitment["hubs"]):
        entry = {"hub": hub.name, "key": pinned["key"]}
        if stop:
            entry.update(state="NOT_STARTED", reason=stop)
        elif sha(hub / "config/FROZEN-PROTOCOL.json") != pinned["frozen_protocol_sha256"] or \
                release_source_hash(ROOT) != commitment["source_sha256"] or not _pristine(hub) or \
                sha(chain_dir / "CHAIN.json") != commitment["chain_spec_sha256"] or \
                (chain_dir / "CHAIN-COMMITMENT.json").read_bytes() != committed_bytes or not _freeze_ok(hub):
            entry.update(state="NOT_STARTED", reason="freeze/source/commitment changed after chain start")
            stop = f"{hub.name}: freeze fault before launch; chain stopped"
        elif time.monotonic() + estimate(hub) > mono_end:
            entry.update(state="NOT_STARTED", reason="would not fit the 24-hour chain ceiling")
        else:
            log(f"start {hub.name}")
            entry["started"] = stamp()
            env = dict(os.environ, DREAM_SUITE_CHAIN_DEADLINE_EPOCH=str(int(chain_deadline - CHILD_GRACE_S)))
            with uninterruptible():   # launch and ownership are one step: no unowned driver (R5)
                proc = subprocess.Popen(command(hub), env=env, stdin=subprocess.DEVNULL, start_new_session=True)
                running.update(proc=proc, hub=hub, worker_pgid=None, cleaned=False)
            try:
                rc = _wait_caching_worker(proc, hub, running, mono_end - KILL_RESERVE_S)
                outcome, halt = child_outcome(hub, rc)
            except subprocess.TimeoutExpired:
                terminate_study(proc, hub, max(1, mono_end - 30 - time.monotonic()), running)
                outcome, halt = {"state": "KILLED_AT_CHAIN_DEADLINE"}, True
            running.update(proc=None, hub=None, worker_pgid=None, cleaned=False)
            if outcome.get("state") != "COMPLETE":
                # The driver is gone, so its lifeline pipe is closed and the in-container worker is being killed
                # (<= ~15 s). Wait before any next launch so its GPU check does not see a dying worker (RC2).
                time.sleep(max(0, min(LIFELINE_SETTLE_S, mono_end - KILL_RESERVE_S - time.monotonic())))
            entry.update(finished=stamp(), **outcome)
            if halt:
                stop = f"{hub.name}: {outcome['state']} {outcome.get('step') or outcome.get('reason') or ''}; " \
                       "chain stopped"
            log(f"end {hub.name}: {entry}")
        status["studies"].append(entry)
        atomic_json(chain_dir / "CHAIN-STATUS.json", status)
    status["finished"] = stamp()
    atomic_json(chain_dir / "CHAIN-STATUS.json", status)
    log("chain finished")
    return status


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--chain", required=True)
    a = ap.parse_args()
    result = run_chain(a.chain)
    print(json.dumps(result))
    sys.exit(0)
