"""Run qualification, then the hub's planned stages in order; stop on failure.

Stages, study and expected trial counts come from the hub's run-plan.json.
A decategorization hub first builds and qualifies its vectors in the worker.

Run on the host with an explicitly prepared hub. This never resumes a failed or
paused hub. Sleep inhibition is scoped to this process and released on exit.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("hub")
    args = parser.parse_args(); hub = Path(args.hub).resolve()
    run = hub / "run"; out = hub / "output"; plan = out / "run-plan.json"
    env = {**os.environ, "DREAM_RUN_PLAN":str(plan), "PYTHONDONTWRITEBYTECODE":"1"}
    progress = []; progress_path = out / "queue-progress.json"
    if progress_path.exists():
        raise FileExistsError("Queue records already exist; do not automatically resume")
    def step(phase, seconds, options, expected=0, preflight=False, memory=False, alternate_plan=None):
        command = [sys.executable, "-B", str(run / "controller/pilot_supervisor.py"), "--phase", phase,
                   "--seconds", str(seconds), *(["--preflight"] if preflight else []),
                   *(["--require-memory"] if memory else []), *options]
        print("Starting " + phase, flush=True)
        code = subprocess.run(command, env={**env, "DREAM_RUN_PLAN":str(alternate_plan or plan)}).returncode
        progress.append({"phase":phase, "exit_code":code, "expected_exit_code":expected})
        progress_path.write_text(json.dumps(progress, indent=2) + "\n")
        if code != expected:
            raise RuntimeError(f"Queue halted at {phase}: exit {code}; preserve for review")
    try:
        step("ack-fixture", 20, ["--ack-fixture"], preflight=True)
        step("pause-fixture", 20, ["--pause-fixture"], expected=73, preflight=True)
        step("thinking-pause-fixture", 20, ["--thinking-pause-fixture"], expected=73, preflight=True)
        step("deadline-fixture", 2, ["--sleep-fixture", "30"], expected=124, preflight=True)
        tight = json.loads(plan.read_text()); tight["limits"]["worker_rss_bytes"] = 1
        tight_path = out / "resource-stop-plan.json"; tight_path.write_text(json.dumps(tight, indent=2) + "\n")
        step("resource-stop-fixture", 30, ["--sleep-fixture", "20"], expected=77, preflight=True, alternate_plan=tight_path)
        step("ml-suite", 300, ["--script", "run_tests.py", "--require-ml", "--report", "/results/testing/fresh-ml.json"], preflight=True)
        report = json.loads((run / "results/testing/fresh-ml.json").read_text())
        if not report["success"] or any(report[k] for k in ("skipped", "failures", "errors")):
            raise RuntimeError("ML-inclusive qualification failed")
        meta = json.loads(plan.read_text())
        stages = meta.get("stages", ["concepts-smoke", "concepts-pilot"])
        for stage in stages:
            step(stage + "-plan", 60, ["--script", "run_experiment.py", "--config", f"/inputs/configs/{stage}.json", "--plan-only"])
        step("boundary", 20, ["--probe"])
        inhibitor = subprocess.Popen(["systemd-inhibit", "--what=sleep:idle", "--why=DREAM research queue", "sleep", "36000"], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        try:
            # Check that inhibition started instead of silently running asleep.
            import time
            time.sleep(.2)
            if inhibitor.poll() is not None:
                raise RuntimeError("Could not establish scoped sleep inhibition: " + inhibitor.stderr.read().decode())
            if meta.get("vector_direction"):
                step("vector-qualification", 1800, ["--script", "build_steering_vector.py", "--config",
                     f"/inputs/configs/{stages[0]}.json", "--direction", meta["vector_direction"], "--qualify-full"], memory=True)
            for stage in stages:
                cfg = json.loads((run / "inputs/configs" / f"{stage}.json").read_text())
                step(stage, cfg["limits"]["max_seconds"] + 60,
                     ["--script", "run_experiment.py", "--config", f"/inputs/configs/{stage}.json"], memory=True)
                dirs = list((run / "results/runs" / stage).iterdir())
                rows = [json.loads(p.read_text()) for p in dirs[0].glob("trial-*.json")]
                expected = meta.get("expected_trials", {}).get(stage, 4 if stage == "concepts-smoke" else 12)
                # Concept stages require every answer complete. In the
                # decategorization study, broken format under steering is an
                # outcome; only a missing record stops the queue.
                complete = all(x.get("completed_five_item_answer", True) for x in rows)
                if len(rows) != expected or (meta.get("study", "concepts") == "concepts" and not complete):
                    raise RuntimeError("Structural qualification failed; no next stage")
        finally:
            inhibitor.terminate(); inhibitor.wait(timeout=5)
        (out / "COMPLETE.json").write_text(json.dumps({"status":"completed", "semantic_ratings":"pending blinded review"}, indent=2) + "\n")
        print("Queued stages completed. Semantic review remains separate.", flush=True)
    except BaseException as exc:
        (out / "STOPPED.json").write_text(json.dumps({"error_type":type(exc).__name__, "message":str(exc), "automatic_resume":False}, indent=2) + "\n")
        raise


if __name__ == "__main__":
    main()
