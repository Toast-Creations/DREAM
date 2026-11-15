"""CPU stub fixtures for the V1.22.0 driver (no model, no container): the real driver template, with the runner and
analyzer replaced by stubs and the container prefix by plain bash. Checks that a failed stage, a failed analyzer and an
incomplete run all exit nonzero without DRIVER-SUCCESS.json, and that a complete run writes it only at the end."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from dream_core.ledger import release_source_hash  # noqa: E402
from tempo import kidconfdone as KD  # noqa: E402
import kconf_generate as KGEN  # noqa: E402
import kconf_prepare as KP  # noqa: E402

CFG = {"base_seed": 999011, "pool": "kcdrv", "smoke_base_seed": 999012, "smoke_pool": "kcdrvs",
       "consonants": "bcdfhjk", "id_prefix": "d22-g", "smoke_prefix": "d22-s", "n_correction_groups": 16,
       "n_arrival_groups": 8, "smoke_groups": 4, "schedule_seed": 999013}
PLAN = {"arrival": {"rule": ["P", 0.025], "threshold": "0"}, "correction": {"rule": ["P", 0.01], "threshold": "-3/64"},
        "reference": ["P", 0.025], "B": 1000, "seed": 5}
STUBS = "tests/fixtures/driver_stubs"


class Driver(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.td = tempfile.TemporaryDirectory()
        base = Path(cls.td.name) / "base"
        out = KGEN.generate(dict(CFG))
        data = base / "data"
        for part, (groups, pubs, hid, calls, rej) in out.items():
            KGEN.write(data / f"public/{part}-targets.jsonl", pubs)
            KGEN.write(data / f"hidden/{part}-cases.jsonl", hid)
            KGEN.write(data / f"{part}-calls.jsonl", calls)
            (data / f"COMMITMENT-{part}.json").write_text(json.dumps(
                {"set": part, "calls": len(calls), "calls_sha256": KGEN.sha(data / f"{part}-calls.jsonl")}))
        cfgd = base / "config"
        cfgd.mkdir()
        for part in ("smoke", "main"):
            (cfgd / f"stage-{part}.json").write_text(json.dumps({"set": part, "select": [c["call_id"] for c in out[part][3]]}))
        (cfgd / "RESOURCE-GUARD.json").write_text(json.dumps({"total_attempts": 128, "ceiling_s": 43200,
                                                              "feasibility_slowdown": 1.1, "main_overhead_s": 600,
                                                              "retry_limit": 0}))
        (cfgd / "ANALYSIS-PLAN.json").write_text(json.dumps(PLAN))
        (cfgd / "FROZEN-PROTOCOL.json").write_text(json.dumps(
            {"source_sha256": release_source_hash(ROOT), "analysis_plan_sha256": KD.plan_sha256(PLAN),
             "design": {}, "config": {"RESOURCE-GUARD.json": KGEN.sha(cfgd / "RESOURCE-GUARD.json")},
             "data": {"main-calls.jsonl": KGEN.sha(data / "main-calls.jsonl")}, "phase0": {}}))
        cls.base = base
        cls.n = 0

    @classmethod
    def tearDownClass(cls):
        cls.td.cleanup()

    def run_driver(self, analyzer="scripts/kconf_analyze.py", fail_stage=None, tamper=False):
        Driver.n += 1
        hub = Path(self.td.name) / f"h{Driver.n}"
        shutil.copytree(self.base, hub)
        if tamper:
            (hub / "data" / "main-calls.jsonl").write_text("tampered\n")
        drv = hub / "run.sh"
        drv.write_text(KP.render_driver(hub, ROOT, __PY__=sys.executable, __CTR__="bash -c", __INHIBIT__="",
                                        __RUNNER__=f"{STUBS}/stub_runner.py", __ANALYZER__=analyzer, __GPUCHECK__="0"))
        env = dict(os.environ)
        env.pop("KCONF_STUB_FAIL", None)
        if fail_stage:
            env["KCONF_STUB_FAIL"] = fail_stage
        rc = subprocess.run(["bash", str(drv)], env=env, capture_output=True, timeout=600).returncode
        log = (hub / "driver.log").read_text() if (hub / "driver.log").exists() else ""
        return rc, hub, log

    def test_success(self):
        rc, hub, log = self.run_driver()
        self.assertEqual(rc, 0, log[-2000:])
        self.assertTrue((hub / "DRIVER-SUCCESS.json").exists())
        a = json.loads((hub / "analysis" / "confirm" / "ANALYSIS.json").read_text())
        self.assertEqual(a["status"], "COMPLETE")
        self.assertIn("qualification", a)
        self.assertTrue(log.rstrip().endswith("done"))

    def test_failed_main_stage(self):
        rc, hub, log = self.run_driver(fail_stage="main")
        self.assertEqual(rc, 11, log[-2000:])
        self.assertFalse((hub / "DRIVER-SUCCESS.json").exists())
        a = json.loads((hub / "analysis" / "confirm" / "ANALYSIS.json").read_text())
        self.assertEqual(a["status"], "INCOMPLETE")
        self.assertNotIn("qualification", a)
        self.assertNotIn(" done", log)

    def test_failed_smoke_stage(self):
        rc, hub, log = self.run_driver(fail_stage="smoke")
        self.assertEqual(rc, 10, log[-2000:])
        self.assertFalse((hub / "DRIVER-SUCCESS.json").exists())
        self.assertFalse((hub / "stages" / "main").exists())

    def test_failed_analyzer(self):
        rc, hub, log = self.run_driver(analyzer=f"{STUBS}/stub_analyzer_fail.py")
        self.assertEqual(rc, 5, log[-2000:])
        self.assertFalse((hub / "DRIVER-SUCCESS.json").exists())

    def test_frozen_file_tamper(self):
        rc, hub, log = self.run_driver(tamper=True)
        self.assertEqual(rc, 3)
        self.assertFalse((hub / "stages").exists())

    def test_no_resume(self):
        rc, hub, log = self.run_driver()
        self.assertEqual(rc, 0)
        drv = hub / "run.sh"
        rc2 = subprocess.run(["bash", str(drv)], capture_output=True, timeout=120).returncode
        self.assertEqual(rc2, 9)


if __name__ == "__main__":
    unittest.main()
