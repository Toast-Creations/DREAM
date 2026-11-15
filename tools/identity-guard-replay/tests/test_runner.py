"""Driver tests for run_replay.sh: stage-failure gating, honest failure status, whole-run cap and child cleanup.

Each test builds an ISOLATED temporary git copy of the utility in which the real run_replay.sh, ig_report.py and
guard/studies.py are used unchanged, while the other stage scripts are small stubs (scripts/_stub.py) and a fake
`distrobox` on PATH runs the stage command on the current interpreter. No real hub, model, GPU or network is used.
The cap is only ever TIGHTENED via IGUARD_CAP_SECONDS (the driver refuses anything above 1800). Every test is short.
"""
import os as _os  # public release: local paths from environment
import sys as _sys
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
REAL_PY = _os.environ.get("DREAM_PY", _sys.executable)

STUB = r'''import json, os, subprocess, sys, time, hashlib
from pathlib import Path
name = Path(sys.argv[0]).stem
args = sys.argv[1:]
mode = os.environ.get("STUB_" + name.upper(), "ok")
opt = lambda k: args[args.index(k) + 1] if k in args else None
if mode == "fail":
    print(name, "stub failing"); sys.exit(2)
if mode == "hang":
    child = subprocess.Popen(["sleep", "300"])
    Path(os.environ["STUB_PIDFILE"]).write_text(f"{os.getpid()} {child.pid}")
    time.sleep(300)
if name == "ig_preserve":
    if args[0] == "snapshot":
        Path(args[1]).write_text("{}")
    else:
        Path(args[3]).write_text(json.dumps({"unchanged": True, "roots": {}}))
elif name == "ig_plan":
    hub = Path(opt("--hub"))
    (hub / "PLAN.json").write_text(json.dumps({"utility_commit": opt("--commit")}))
    (hub / "INPUT-MANIFEST.json").write_text(json.dumps({"disclosure": "stub disclosure", "studies": {}}))
elif name == "ig_controls":
    out = Path(opt("--out")); out.mkdir(parents=True, exist_ok=True)
    (out / "CONTROLS.json").write_text(json.dumps({"status": "PASS", "failures": [], "n": 0, "rows": []}))
elif name == "ig_decide":
    out, s = Path(opt("--out")), opt("--study"); out.mkdir(parents=True, exist_ok=True)
    body = b"y\n" if mode == "nondeterministic" and out.name == "decisions-repeat" else b"x\n"
    (out / f"DECISIONS-{s}.jsonl").write_bytes(body)
    (out / f"SEAL-{s}.json").write_text(json.dumps({"decisions_sha256": hashlib.sha256(body).hexdigest()}))
elif name == "ig_evaluate":
    Path(os.environ["STUB_EVAL_LOG"]).open("a").write(opt("--study") + "\n")
'''

FAKE_DISTROBOX = r'''#!/usr/bin/env bash
# test stand-in for `distrobox enter NAME -- CMD...`: runs CMD here, using the test interpreter for the venv python
while [ $# -gt 0 ] && [ "$1" != "--" ]; do shift; done; shift
args=(); for a in "$@"; do if [ "$a" = "@REAL_PY@" ]; then args+=("$STUB_PYTHON"); else args+=("$a"); fi; done
exec "${args[@]}"
'''


def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    try:   # a zombie is dead for our purposes
        return Path(f"/proc/{pid}/stat").read_text().split(")")[1].split()[0] != "Z"
    except OSError:
        return False


@unittest.skipUnless(shutil.which("git") and shutil.which("timeout") and Path("/proc/self/environ").exists(),
                     "needs git, coreutils timeout and /proc")
class Driver(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="iguard-runner-test-"))
        u = self.tmp / "util"
        (u / "scripts").mkdir(parents=True)
        (u / "guard").mkdir()
        (u / "tests").mkdir()
        shutil.copy(HERE / "run_replay.sh", u / "run_replay.sh")
        shutil.copy(HERE / ".gitignore", u / ".gitignore")
        shutil.copy(HERE / "scripts" / "ig_report.py", u / "scripts" / "ig_report.py")
        shutil.copy(HERE / "guard" / "studies.py", u / "guard" / "studies.py")
        for n in ("ig_preserve", "ig_plan", "ig_controls", "ig_decide", "ig_evaluate"):
            (u / "scripts" / f"{n}.py").write_text(STUB)
        (u / "tests" / "test_stub.py").write_text(
            "import os, unittest\nclass T(unittest.TestCase):\n    def test_stub(self):\n"
            "        self.assertNotEqual(os.environ.get('STUB_TESTS'), 'fail')\n")
        g = ["git", "-C", str(u), "-c", "user.name=iguard-test", "-c", "user.email=iguard-test@example.invalid"]
        subprocess.run(g[:3] + ["init", "-q"], check=True)
        subprocess.run(g + ["add", "-A"], check=True)
        subprocess.run(g + ["commit", "-qm", "stub utility"], check=True)
        b = self.tmp / "bin"
        b.mkdir()
        (b / "distrobox").write_text(FAKE_DISTROBOX.replace("@REAL_PY@", REAL_PY))
        (b / "distrobox").chmod(0o755)
        self.util, self.hub = u, self.tmp / "hub"
        self.env = {k: v for k, v in os.environ.items() if not k.startswith(("IGUARD_", "STUB_"))}
        self.env.update(PATH=f"{b}:{os.environ['PATH']}", STUB_PYTHON=sys.executable, PYTHONDONTWRITEBYTECODE="1",
                        STUB_PIDFILE=str(self.tmp / "pids"), STUB_EVAL_LOG=str(self.tmp / "evaluated"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def drive(self, timeout=40, **env):
        t0 = time.time()
        p = subprocess.run(["bash", str(self.util / "run_replay.sh"), str(self.hub)], env={**self.env, **env},
                           capture_output=True, text=True, timeout=timeout)
        return p.returncode, time.time() - t0, p.stdout + p.stderr

    def j(self, rel):
        return json.loads((self.hub / rel).read_text())

    def log(self):
        return (self.hub / "replay.log").read_text()

    def evaluated(self):
        p = self.tmp / "evaluated"
        return p.read_text().split() if p.exists() else []

    def assert_failed_honestly(self, rc, expect_rc=2):
        self.assertEqual(rc, expect_rc, self.log())
        rd = self.j("READINESS.json")
        self.assertFalse(rd["ready_for_further_consideration"])
        self.assertFalse(rd["technically_complete"])
        self.assertIn("INCOMPLETE", (self.hub / "RUN-STATUS.md").read_text())
        self.assertNotIn("READY FOR FURTHER CONSIDERATION", (self.hub / "RUN-STATUS.md").read_text())
        self.assertTrue((self.hub / "REPORT.md").exists())
        self.assertEqual(self.j("TERMINAL.json")["remaining_run_processes"], 0)

    def test_cap_can_only_be_tightened(self):
        for bad in ("1801", "3600", "0", "", "abc", "-5"):
            with self.subTest(cap=bad):
                rc, _, out = self.drive(IGUARD_CAP_SECONDS=bad)
                self.assertEqual(rc, 1, out)
                self.assertIn("refusing", out)
                self.assertFalse(self.hub.exists())

    def test_existing_hub_and_dirty_tree_refused(self):
        self.hub.mkdir()
        rc, _, out = self.drive()
        self.assertEqual((rc, "exists" in out), (1, True))
        self.hub.rmdir()
        (self.util / "scratch.txt").write_text("x")
        rc, _, out = self.drive()
        self.assertEqual((rc, "uncommitted" in out), (1, True))

    def test_plan_failure_stops_dependent_stages_and_fails(self):
        rc, _, _ = self.drive(STUB_IG_PLAN="fail")
        self.assert_failed_honestly(rc)
        log = self.log()
        self.assertNotIn("BEGIN decide", log)
        self.assertIn("SKIP decide-V1.24", log)
        self.assertEqual(self.evaluated(), [])
        rt = self.j("RUNTIME.json")
        self.assertTrue(rt["any_step_failed"])
        self.assertIn("plan rc=2", rt["failed_steps"])
        self.assertEqual(self.j("TERMINAL.json")["terminal"], "COMPLETED")   # driver ran to its end, but failed
        self.assertIn("all_stages_succeeded", self.j("READINESS.json")["failed_technical"])

    def test_tests_failure_stops_decisions(self):
        rc, _, _ = self.drive(STUB_TESTS="fail")
        self.assert_failed_honestly(rc)
        self.assertNotIn("BEGIN decide", self.log())
        self.assertFalse(self.j("tests/TESTS.json")["ok"])

    def test_decide_failure_skips_repeat_and_evaluation(self):
        rc, _, _ = self.drive(STUB_IG_DECIDE="fail")
        self.assert_failed_honestly(rc)
        self.assertNotIn("BEGIN decide-repeat", self.log())
        self.assertEqual(self.evaluated(), [])
        self.assertFalse(self.j("DETERMINISM.json")["V1.24"]["equal"])

    def test_nondeterministic_ledger_blocks_evaluation(self):
        rc, _, _ = self.drive(STUB_IG_DECIDE="nondeterministic")
        self.assert_failed_honestly(rc)
        self.assertIn("not deterministic for V1.24", self.log())
        self.assertEqual(self.evaluated(), [])
        self.assertIn("determinism-V1.24", self.j("RUNTIME.json")["failed_steps"])

    def test_successful_stages_with_missing_results_are_incomplete(self):
        rc, _, _ = self.drive()
        self.assert_failed_honestly(rc)
        self.assertEqual(self.evaluated(), ["V1.24", "V1.22"])   # evaluator ran after sealed, deterministic ledgers
        self.assertIn("coverage_complete", self.j("READINESS.json")["failed_technical"])
        self.assertIn("report rc=3", self.log())

    def test_preserve_failure_runs_nothing_else_but_report(self):
        rc, _, _ = self.drive(STUB_IG_PRESERVE="fail")
        self.assert_failed_honestly(rc)
        log = self.log()
        for stage in ("plan", "tests", "controls", "decide-V1.24", "evaluate-V1.24", "preserve-compare"):
            self.assertNotIn(f"BEGIN {stage}\n", log)
        self.assertIn("BEGIN report", log)

    def _pids(self):
        for _ in range(100):
            if (self.tmp / "pids").exists() and len((self.tmp / "pids").read_text().split()) == 2:
                return [int(x) for x in (self.tmp / "pids").read_text().split()]
            time.sleep(0.05)
        self.fail("stub never started")

    def _assert_dead(self, pids):
        deadline = time.time() + 5
        while time.time() < deadline and any(alive(p) for p in pids):
            time.sleep(0.05)
        self.assertEqual([p for p in pids if alive(p)], [])

    def test_whole_run_cap_terminates_children_and_fails(self):
        rc, elapsed, _ = self.drive(IGUARD_CAP_SECONDS="4", STUB_IG_CONTROLS="hang")
        self.assertEqual(rc, 124, self.log())
        self.assertLess(elapsed, 4 + 5 + 6)   # cap + kill grace + slack; the stub alone would sleep 300 s
        self._assert_dead(self._pids())
        term = self.j("TERMINAL.json")
        self.assertEqual((term["terminal"], term["exit_code"], term["cap_seconds"]), ("TIMEOUT", 124, 4))
        self.assertTrue(term["cap_tightened_for_test"])
        self.assertEqual(term["remaining_run_processes"], 0)
        self.assertFalse(self.j("READINESS.json")["ready_for_further_consideration"])
        self.assertEqual(self.j("RUNTIME.json")["status"], "TIMEOUT")
        self.assertIn("TIMEOUT", (self.hub / "RUN-STATUS.md").read_text())
        self.assertIn("INCOMPLETE / PROTOTYPE NOT READY", (self.hub / "REPORT.md").read_text())
        self.assertNotIn("BEGIN decide", self.log())

    def test_cap_also_bounds_reporting(self):
        rc, elapsed, _ = self.drive(IGUARD_CAP_SECONDS="3", STUB_IG_EVALUATE="hang")
        self.assertEqual(rc, 124, self.log())
        self._assert_dead(self._pids())
        self.assertNotIn("BEGIN report", self.log())
        self.assertEqual(self.j("TERMINAL.json")["terminal"], "TIMEOUT")

    def test_interruption_terminates_children_and_fails(self):
        p = subprocess.Popen(["bash", str(self.util / "run_replay.sh"), str(self.hub)],
                             env={**self.env, "STUB_IG_CONTROLS": "hang"},
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        pids = self._pids()
        p.send_signal(signal.SIGTERM)
        rc = p.wait(timeout=20)
        self.assertEqual(rc, 130)
        self._assert_dead(pids)
        term = self.j("TERMINAL.json")
        self.assertEqual((term["terminal"], term["remaining_run_processes"]), ("INTERRUPTED", 0))
        self.assertFalse(self.j("READINESS.json")["ready_for_further_consideration"])
        self.assertIn("INTERRUPTED", (self.hub / "RUN-STATUS.md").read_text())


if __name__ == "__main__":
    unittest.main()
