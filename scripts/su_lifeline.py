"""In-container lifeline for one EVT-suite worker (V1.28.0). Stdlib only; no model imports.

Usage: su_lifeline.py -- COMMAND [ARGS...]

Why: the worker runs inside the research container via `distrobox enter` / `podman exec`. A host-side signal to the
worker's process group reaches only the host clients (distrobox shell, podman exec); it does not reach the process
inside the container (V1.28.0 probe: a TERM-ignoring in-container process survived host TERM and KILL, and only its
own in-container `timeout` ended it). So containment has to come from inside the container.

What it does: runs COMMAND in its own process group and treats its own stdin as a lifeline. The driver holds the
only write end of that pipe. When the pipe closes for any reason (the driver closes it deliberately, exits, or is
killed, or the podman/distrobox client dies), stdin reaches EOF, and the lifeline TERMs the command's group, waits up
to GRACE_S, then KILLs it, and exits. If COMMAND ends first, the lifeline exits with its status. The worker never
reads stdin itself (it gets /dev/null).

Limits (documented, Codex recheck 2): if the lifeline itself is killed (e.g. a direct SIGKILL inside the container),
nobody reads the EOF; the worker is then bounded only by the inner `timeout`. A descendant that deliberately leaves
the process group/session escapes PGID-based cleanup. A group KILL after the leader is reaped cannot rule out PGID
reuse. Nothing launched from this process may fork without exec while holding the driver's pipe writer.
"""
import os
import signal
import subprocess
import sys
import threading

GRACE_S = 10


def _finalize(child, grace_s):
    """Bounded group cleanup: TERM (if the leader is still running), wait, KILL; then KILL the group once more for
    descendants that outlive their leader (Codex recheck 2, N3). Idempotent."""
    if child.poll() is None:
        for sig, wait_s in ((signal.SIGTERM, grace_s), (signal.SIGKILL, 5)):
            try:
                os.killpg(child.pid, sig)
            except ProcessLookupError:
                break
            try:
                child.wait(timeout=wait_s)
                break
            except subprocess.TimeoutExpired:
                pass
    try:
        os.killpg(child.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def main(argv):
    if len(argv) < 3 or argv[1] != "--":
        print("usage: su_lifeline.py -- COMMAND [ARGS...]", file=sys.stderr)
        return 2
    # Stop state and handlers exist before the child does (Codex recheck 2, N1).
    cut = threading.Event()

    def stop(signum, frame):  # a signal that does reach the lifeline is treated like a cut lifeline
        cut.set()
    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(sig, stop)
    child = subprocess.Popen(argv[2:], stdin=subprocess.DEVNULL, start_new_session=True)
    try:
        def watch():
            try:
                while os.read(0, 4096):
                    pass
            except OSError:
                pass
            cut.set()
        threading.Thread(target=watch, daemon=True).start()
        while child.poll() is None and not cut.wait(0.5):
            pass
        if child.poll() is None:
            _finalize(child, GRACE_S)
            print("lifeline cut: worker group terminated", file=sys.stderr, flush=True)
            return 125
        rc = child.returncode
        _finalize(child, 0)   # leader exited first: still clean up same-group descendants (N3)
        return rc if rc >= 0 else 128 - rc
    except BaseException:
        _finalize(child, GRACE_S)   # any setup or loop failure: the acquired child never outlives the lifeline
        raise


if __name__ == "__main__":
    sys.exit(main(sys.argv))
