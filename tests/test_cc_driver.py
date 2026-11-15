"""CCONF's actual supervisor with isolated CPU response workers, never real observations."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from dream_core.ledger import release_source_hash  # noqa: E402
from tempo import bounded_mean as BM, clarconfirm as CC, kidconfdone as KD  # noqa: E402
import cc_analyze as CA  # noqa: E402
import cc_guard as CG  # noqa: E402
import cc_prepare as CP  # noqa: E402
import cc_run as CR  # noqa: E402


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=1) + "\n")


class Driver(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.base = Path(cls.temp.name) / "base"
        (cls.base / "config").mkdir(parents=True)
        dump(cls.base / "config/PANEL.json", copy.deepcopy(CC.DEFAULT_CONFIG))
        subprocess.run([sys.executable, "-B", str(ROOT / "scripts/cc_generate.py"), "--hub", str(cls.base),
                        "--config", str(cls.base / "config/PANEL.json")], check=True, capture_output=True)
        dump(cls.base / "config/RULE.json", BM.rule_config())
        dump(cls.base / "config/ANALYSIS-PLAN.json", CA.DEFAULT_PLAN)
        dump(cls.base / "config/RESOURCE-GUARD.json", CG.POLICY)
        model_from = cls.base / "fixture-model.json"
        dump(model_from, {"model": CP.MODEL})
        CP.configs(cls.base, model_from)
        (cls.base / "design").mkdir()
        (cls.base / "design/PROTOCOL.md").write_text("CPU FIXTURE, not study evidence\n")
        dump(cls.base / "phase0/VALIDATION.json", {"all_pass": True, "fixture": True})
        cls.manifest = Path(cls.temp.name) / "model-manifest.json"
        cls.manifest.write_text('{}')
        cls.serial = 0

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def hub(self, notice_directory=False):
        type(self).serial += 1
        hub = Path(self.temp.name) / f"h{self.serial}"
        shutil.copytree(self.base, hub)
        (hub / "run_cc.sh").write_text(CP.launcher(hub))
        if notice_directory:
            dump(hub / "config/COORDINATION.json", {"path": str(hub / "design")})
        sections = {s: {str(p.relative_to(hub / s)): CP.sha(p) for p in sorted((hub / s).rglob('*')) if p.is_file()}
                    for s in ("design", "config", "data", "phase0")}
        dump(hub / "config/FROZEN-PROTOCOL.json", {"study": "CCONF-v1", "source_dir": str(ROOT),
             "source_sha256": release_source_hash(ROOT), "analysis_plan": CA.DEFAULT_PLAN,
             "analysis_plan_sha256": KD.plan_sha256(CA.DEFAULT_PLAN), "rule_sha256": CP.sha(hub / "config/RULE.json"),
             "driver_sha256": CP.sha(hub / "run_cc.sh"), "model_manifest_path": str(self.manifest),
             "model_manifest_sha256": CP.sha(self.manifest), **sections})
        return hub

    @staticmethod
    def worker(modes=None):
        modes = modes or {}
        def make(hub, stage, remaining):
            return [sys.executable, "-B", str(ROOT / "tests/fixtures/cc_cpu_runner.py"), "--hub", str(hub),
                    "--stage", stage, "--config", str(hub / f"config/stage-{stage}.json"),
                    "--mode", modes.get(stage, "qualified")]
        return make

    def run_hub(self, hub, modes=None, **kwargs):
        return CR.drive(hub, worker=self.worker(modes), gpu_probe=lambda: {"fixture": True}, **kwargs)

    def assert_failed(self, hub):
        self.assertTrue((hub / "DRIVER-FAILURE.json").exists())
        self.assertFalse((hub / "DRIVER-SUCCESS.json").exists())
        a = json.loads((hub / "analysis/confirm/ANALYSIS.json").read_text())
        self.assertEqual(a["status"], "INCOMPLETE")
        self.assertEqual(a["qualification"]["status"], "NOT_EVALUATED")
        self.assertNotIn("gates", a)
        self.assertIn("INCOMPLETE", (hub / "RUN-STATUS.md").read_text())

    def test_qualified_completion_and_refused_resume(self):
        hub = self.hub()
        self.assertEqual(self.run_hub(hub, notify=False), 0, (hub / "driver.log").read_text()[-5000:])
        self.assertTrue((hub / "DRIVER-SUCCESS.json").exists())
        a = json.loads((hub / "analysis/confirm/ANALYSIS.json").read_text())
        self.assertEqual(a["status"], "COMPLETE")
        self.assertEqual(a["qualification"]["status"], "QUALIFIED")
        self.assertEqual(self.run_hub(hub, notify=False), 9)

    def test_not_qualified_is_successful_execution(self):
        hub = self.hub()
        self.assertEqual(self.run_hub(hub, {"main": "negative"}, notify=False), 0,
                         (hub / "driver.log").read_text()[-5000:])
        self.assertEqual(json.loads((hub / "DRIVER-SUCCESS.json").read_text())["qualification"], "NOT_QUALIFIED")

    def test_smoke_worker_failure(self):
        hub = self.hub()
        self.assertEqual(self.run_hub(hub, {"smoke": "fail"}, notify=False), 1)
        self.assert_failed(hub)
        self.assertFalse((hub / "stages/main").exists())

    def test_slow_smoke_stops_before_main(self):
        hub = self.hub()
        self.assertEqual(self.run_hub(hub, {"smoke": "slow"}, notify=False), 1)
        self.assert_failed(hub)
        self.assertFalse((hub / "stages/main").exists())
        self.assertIn("10.2-hour", (hub / "driver.log").read_text())

    def test_main_failure_preserves_incomplete_counts(self):
        hub = self.hub()
        self.assertEqual(self.run_hub(hub, {"main": "fail"}, notify=False), 1)
        self.assert_failed(hub)
        self.assertGreater(len(list((hub / "stages/main/calls").glob('*.json'))), 0)

    def test_analyzer_exception_cannot_leave_stale_qualification(self):
        hub = self.hub()
        def broken(path):
            CR.default_analyze(path)
            raise RuntimeError("after-analysis fixture failure")
        self.assertEqual(self.run_hub(hub, analyzer=broken, notify=False), 1)
        self.assert_failed(hub)
        self.assertTrue((hub / "analysis/failure/ANALYSIS-before-terminal-error.json").exists())

    def test_frozen_tamper_blocks_workers(self):
        hub = self.hub()
        with (hub / "data/main-calls.jsonl").open('a') as out:
            out.write('\n')
        self.assertEqual(self.run_hub(hub, notify=False), 1)
        self.assert_failed(hub)
        self.assertFalse((hub / "stages").exists())

    def test_orphan_outputs_block_relaunch_without_overwrite(self):
        hub = self.hub()
        dump(hub / "stages/main/calls/orphan.json", {"incomplete": True})
        self.assertEqual(self.run_hub(hub, notify=False), 9)
        self.assertFalse((hub / "DRIVER-FAILURE.json").exists())

    def test_notice_delivery_failure_keeps_protocol_complete(self):
        hub = self.hub(notice_directory=True)
        self.assertEqual(self.run_hub(hub), 0, (hub / "driver.log").read_text()[-5000:])
        self.assertTrue((hub / "DRIVER-SUCCESS.json").exists())
        self.assertTrue((hub / "runtime/NOTICE-ERROR.json").exists())
        self.assertFalse((hub / "DRIVER-FAILURE.json").exists())

    def test_nan_smoke_time_and_failed_attempts_rejected(self):
        hub = self.hub()
        start = int(time.time())
        dump(hub / "config/DEADLINE.json", {"driver_start_epoch": start, "deadline_epoch": start+43200})
        for i in range(36):
            dump(hub / f"stages/smoke/calls/{i}.json", {"status": "ok", "seconds": float('nan') if i==0 else 12.})
        result = CG.check(hub, "main")
        self.assertFalse(result["ok"])
        self.assertIn("invalid smoke timing/status", result["problems"])
        (hub / "stages/smoke/attempts.jsonl").write_text('{"call_id":"failed"}\n')
        self.assertIn("failed attempts are not allowed", CG.check(hub, "main")["problems"])


if __name__ == "__main__":
    unittest.main()
