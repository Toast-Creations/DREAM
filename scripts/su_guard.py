"""EVT-suite resource guard (8-hour hard ceiling per study from its driver start, analysis included).

No inference or model imports. Adapted from ev_guard.py; the policy differs only in the declared call counts.
"""
import argparse
import json
import math
import statistics
import time
from pathlib import Path

from _bootstrap import ROOT  # noqa: F401
from tempo import evsuite as S, refguard


def policy(key):
    spec = S.SPECS[key]
    return {"study": spec["study"], "total_attempts": spec["main_calls"] + spec["smoke_calls"],
            "smoke_calls": spec["smoke_calls"], "ceiling_s": 28800, "planning_limit_s": 27000,
            "feasibility_slowdown": 1.10, "main_overhead_s": 600, "retry_limit": 0,
            "analysis_reserve_s": 600, "kill_grace_s": 60}


def check(hub, stage, now=None):
    hub = Path(hub)
    now = time.time() if now is None else now
    key = S.validate_config(json.loads((hub / "config/PANEL.json").read_text()))["key"]
    pol = json.loads((hub / "config/RESOURCE-GUARD.json").read_text())
    if pol != policy(key):
        raise ValueError("unsupported EVT-suite resource policy")
    deadline = json.loads((hub / "config/DEADLINE.json").read_text())
    cfg = json.loads((hub / f"config/stage-{stage}.json").read_text())
    planned = len(cfg["select"])
    used = refguard.used_attempts(hub)  # conservative after any failed attempt
    remaining = deadline["deadline_epoch"] - now
    elapsed = now - deadline["driver_start_epoch"]
    problems = []
    if not 0 < deadline["deadline_epoch"] - deadline["driver_start_epoch"] <= pol["ceiling_s"]:
        problems.append("deadline/start relationship exceeds the declared ceiling")
    if not all(math.isfinite(v) for v in (now, remaining, elapsed)) or elapsed < 0:
        problems.append("invalid resource clock")
    if planned > pol["total_attempts"] - used:
        problems.append("attempt ceiling")
    if any(path.read_text().strip() for path in (hub / "stages").glob("*/attempts.jsonl")):
        problems.append("failed attempts are not allowed")
    if remaining <= pol["analysis_reserve_s"] + pol["kill_grace_s"]:
        problems.append("deadline too close")
    out = {"stage": stage, "planned": planned, "used_attempts_conservative": used,
           "remaining_s": remaining, "elapsed_s": elapsed}
    if stage == "main":
        times = []
        for path in (hub / "stages/smoke/calls").glob("*.json"):
            rec = json.loads(path.read_text())
            if rec.get("status") != "ok" or type(rec.get("seconds")) not in (int, float) \
                    or not math.isfinite(rec["seconds"]) or rec["seconds"] <= 0:
                problems.append("invalid smoke timing/status")
            else:
                times.append(rec["seconds"])
        if len(times) != pol["smoke_calls"]:
            problems.append(f"exactly {pol['smoke_calls']} smoke timings required")
        if times:
            projected = elapsed + statistics.mean(times) * planned * pol["feasibility_slowdown"] + pol["main_overhead_s"]
            out["smoke_mean_s"] = statistics.mean(times)
            out["projected_total_s"] = projected
            if not math.isfinite(projected):
                problems.append("invalid projected time")
            if projected > pol["planning_limit_s"]:
                problems.append("projected total exceeds 7.5-hour planning reserve")
            if projected > pol["ceiling_s"]:
                problems.append("projected total exceeds hard deadline")
    out.update(ok=not problems, problems=problems)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("hub")
    ap.add_argument("stage", choices=("smoke", "main"))
    a = ap.parse_args()
    result = check(a.hub, a.stage)
    print(json.dumps(result))
    raise SystemExit(0 if result["ok"] else 1)
