"""ESUB-v1 resource guard (8-hour hard ceiling from driver start, analysis included). No inference or model imports."""
import argparse
import json
import math
import statistics
import time
from pathlib import Path

from _bootstrap import ROOT  # noqa: F401
from tempo import refguard


POLICY = {"total_attempts": 1476, "ceiling_s": 28800, "planning_limit_s": 27000,
          "feasibility_slowdown": 1.10, "main_overhead_s": 600, "retry_limit": 0,
          "analysis_reserve_s": 600, "kill_grace_s": 60}


def check(hub, stage, now=None):
    hub = Path(hub)
    now = time.time() if now is None else now
    policy = json.loads((hub / "config/RESOURCE-GUARD.json").read_text())
    if policy != POLICY:
        raise ValueError("unsupported ESUB resource policy")
    deadline = json.loads((hub / "config/DEADLINE.json").read_text())
    cfg = json.loads((hub / f"config/stage-{stage}.json").read_text())
    planned = len(cfg["select"])
    used = refguard.used_attempts(hub)  # conservative after any failed attempt
    remaining = deadline["deadline_epoch"] - now
    elapsed = now - deadline["driver_start_epoch"]
    problems = []
    if not all(math.isfinite(v) for v in (now, remaining, elapsed)) or elapsed < 0:
        problems.append("invalid resource clock")
    if planned > policy["total_attempts"] - used:
        problems.append("attempt ceiling")
    if any(path.read_text().strip() for path in (hub / "stages").glob("*/attempts.jsonl")):
        problems.append("failed attempts are not allowed")
    if remaining <= policy["analysis_reserve_s"] + policy["kill_grace_s"]:
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
        if len(times) != 36:
            problems.append("exactly 36 smoke timings required")
        if times:
            projected = elapsed + statistics.mean(times) * planned * policy["feasibility_slowdown"] + policy["main_overhead_s"]
            out["smoke_mean_s"] = statistics.mean(times)
            out["projected_total_s"] = projected
            if not math.isfinite(projected):
                problems.append("invalid projected time")
            if projected > policy["planning_limit_s"]:
                problems.append("projected total exceeds 7.5-hour planning reserve")
            if projected > policy["ceiling_s"]:
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
