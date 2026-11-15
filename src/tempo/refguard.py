"""V1.20.0 shared resource guard (Codex review 06). No model.

Policy (declared before main):
  deadline   absolute: first smoke driver start + 12 h (43,200 s). Stricter than the brief (includes setup and review
             pauses). Every main model stage is wrapped by `timeout <remaining seconds>` (watchdog); a stage killed by
             the deadline leaves its per-call records and is reported incomplete.
  attempts   at most 1,744 generation attempts in total (smoke + main), counting infrastructure attempts:
             used = sum over every stage directory of (final call records + logged failed attempts in attempts.jsonl),
             a conservative upper bound. Main runs with retry_limit 0 (no infrastructure retry, no auto-resume), so a
             main call is at most one attempt. Before a main stage starts, its scheduled calls must fit the remaining
             attempts, or the stage is not started.
"""
import json
import time
from pathlib import Path

TOTAL_ATTEMPTS = 1744
TOTAL_SECONDS = 43200


def used_attempts(hub):
    n = 0
    for st in (Path(hub) / "stages").glob("*"):
        c = st / "calls"
        if c.exists():
            n += sum(1 for _ in c.glob("*.json"))
        a = st / "attempts.jsonl"
        if a.exists():
            n += sum(1 for l in a.read_text().splitlines() if l.strip())
    return n


def check(hub, calls_file, deadline_epoch, now=None):
    now = time.time() if now is None else now
    sched = sum(1 for l in Path(calls_file).read_text().splitlines() if l.strip())
    used = used_attempts(hub)
    remaining_attempts = TOTAL_ATTEMPTS - used
    remaining_s = int(deadline_epoch - now)
    ok = sched <= remaining_attempts and remaining_s > 0
    return {"ok": ok, "scheduled": sched, "used_attempts": used, "remaining_attempts": remaining_attempts,
            "remaining_seconds": remaining_s,
            "reason": None if ok else ("attempt budget" if sched > remaining_attempts else "deadline")}
