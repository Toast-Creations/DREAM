"""Record current checks; distinguish logic, tiny-model tests and real pilot evidence."""
import json
from pathlib import Path
import subprocess
import sys
from _bootstrap import ROOT
from dream_core.ledger import atomic_json


def main():
    result = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/run_tests.py"), "--require-ml"], cwd=ROOT, capture_output=True, text=True)
    tests = json.loads((ROOT / "test-results/latest.json").read_text())
    if result.returncode or not tests["success"] or tests["skipped"]:
        raise RuntimeError("Run release QA in the qualified ML environment: " + result.stderr)
    checks = []
    for name in ("dream-smoke", "dream2-smoke", "dream-pilot", "dream2-pilot", "concepts-smoke", "concepts-pilot", "concepts-steering",
                 "decat-smoke", "decat-dosefind", "decat-highdose", "decat-pilot",
                 "decat-explore-smoke", "decat-explore-pilot"):
        command = [sys.executable, "-B", str(ROOT / "scripts/run_experiment.py"), "--config", str(ROOT / "configs" / (name + ".json")), "--plan-only"]
        out = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        if out.returncode:
            raise RuntimeError(out.stderr)
        checks.append({"configuration":name, "exit_code":out.returncode, "stdout":out.stdout})
    atomic_json(ROOT / "test-results/release-qa.json", {"version":"1.3.1", "tests":tests, "plans":checks,
                "coverage":"ML tests construct tiny Qwen2 fixtures. Exact Qwen3-8B study evidence is reported separately."})
    body = f"""# Implementation and Testing — V1.3.1

Current source passed {tests['passed']} tests with {tests['failures']} failures, {tests['errors']} errors and {tests['skipped']} skips in the local ML environment. {len(checks)} plans passed without loading a model. Machine-readable reports are in test-results/latest.json and test-results/release-qa.json.

The ML tests use tiny random Qwen2 fixtures. They exercise target-only loss, masked intervention, allowed adapter parameters, updates and rollback. They do not establish Qwen3 reasoning-format compatibility or scientific effectiveness.

V1.2.0 checks cover the decategorization study: smooth and linear trip curves in absolute tokens (rise, plateau, fall, zero tail), bit-for-bit preservation of the legacy curve, signed generation steering that flips the activation change on a tiny Qwen2 block, a recorded trace and come-down flag through real Hugging Face generation, named contrast poles, direction-kind binding of vector artifacts, the hot-to-cold temperature processor (temperature before top-k/top-p, with a trace), config bounds and required zero-dose and two-step controls, strict KEEPERS and sober-pass parsers, reasoning off in every arm, an unsteered sober pass, and the blinded export. V1.3.1 shortens the trip curve to fit observed answer lengths and copies the contrast files into the worker's data view; the 1.2.0 smoke and vector qualification are the only exact-model decategorization evidence.

Inherited checks cover exactly five association objects, duplicate and malformed output rejection, paired prompts and decoding, EOS-qualified direct JSON, preservation and stopping on incomplete answers, unique numeric probes, plan-only world caps, and source evidence covering launchers.

The concept runner freezes model weights and creates no adapter. Each response uses a fresh context/cache. The primary contrast is reasoning on versus off at zero steering, with equal prompts, seeds, sampling and caps. Schema validity is separate from semantic quality. Ratings stay pending until independently reviewed.

Evidence hashes cover src, tests, scripts and dependency declarations. Per-run records separately identify model, data, configuration and any vector. Hashes detect changes; they are not authenticated security attestations.

See document 13 for the fixed development protocol, document 14 for the older pilot's limitations, and document 16 for the exact-model comparison status/results. No public registration, model merge or deployment is implied. Previous versions and runs remain preserved.
"""
    (ROOT / "documents/10-Implementation-and-Testing.md").write_text(body)
    print(json.dumps({"passed":tests["passed"], "skipped":tests["skipped"], "plans":len(checks)}))


if __name__ == "__main__":
    main()
