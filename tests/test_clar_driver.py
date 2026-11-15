"""The guarded production driver, with a CPU-only stage fixture. No model calls."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from dream_core.ledger import release_source_hash  # noqa: E402
import clar_prepare as CP  # noqa: E402
import kconf_generate as KG  # noqa: E402


class ClarDriver(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.base = Path(cls.temp.name) / "base"
        cfg = {"base_seed": 882001, "pool": "clarstub", "smoke_base_seed": 882002, "smoke_pool": "clarstubs",
               "consonants": "bcdfhjk", "id_prefix": "clarstub-g", "smoke_prefix": "clarstub-s",
               "n_correction_groups": 8, "n_arrival_groups": 8, "smoke_groups": 4, "schedule_seed": 882003}
        panel = KG.generate(cfg)
        for part, (_, pubs, hidden, calls, _) in panel.items():
            KG.write(cls.base / f"data/public/{part}-targets.jsonl", pubs)
            KG.write(cls.base / f"data/hidden/{part}-cases.jsonl", hidden)
            KG.write(cls.base / f"data/{part}-calls.jsonl", calls)
            (cls.base / f"data/COMMITMENT-{part}.json").write_text(json.dumps(
                {"calls_sha256": CP.sha(cls.base / f"data/{part}-calls.jsonl")}))
        (cls.base / "config").mkdir()
        for part in ("smoke", "main"):
            calls = [c["call_id"] for c in panel[part][3]]
            (cls.base / f"config/stage-{part}.json").write_text(json.dumps({"set": part, "select": calls}))
        (cls.base / "config/RESOURCE-GUARD.json").write_text(json.dumps(
            {"total_attempts": sum(len(v[3]) for v in panel.values()), "ceiling_s": 14400,
             "feasibility_slowdown": 1.1, "main_overhead_s": 600, "retry_limit": 0}))
        cls.manifest = Path(cls.temp.name) / "manifest.json"
        cls.manifest.write_text('{}')
        cls.serial = 0

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def drive(self, flag=None, tamper=None):
        type(self).serial += 1
        hub = Path(self.temp.name) / str(self.serial)
        shutil.copytree(self.base, hub)
        driver = hub / "run_clar.sh"
        text = CP.render_driver(hub, ROOT, __PY__=sys.executable, __CTR__="bash -c", __INHIBIT__="",
                                __RUNNER__="tests/fixtures/driver_stubs/stub_runner.py", __GPUCHECK__="0")
        text = text.replace("scripts/clar_analyze.py", "tests/fixtures/clar_driver_analyzer_stub.py")
        driver.write_text(text)
        frozen = {"source_sha256": release_source_hash(ROOT), "design": {}, "config": {},
                  "data": {"main-calls.jsonl": CP.sha(hub / "data/main-calls.jsonl")}, "phase0": {},
                  "driver_sha256": CP.sha(driver), "model_manifest_path": str(self.manifest),
                  "model_manifest_sha256": CP.sha(self.manifest)}
        (hub / "config/FROZEN-PROTOCOL.json").write_text(json.dumps(frozen))
        if tamper == "data":
            (hub / "data/main-calls.jsonl").write_text("tampered\n")
        if tamper == "driver":
            driver.write_text(driver.read_text() + "\n# changed\n")
        env = dict(os.environ)
        for name in ("KCONF_STUB_FAIL", "CLAR_STUB_ANALYZER_FAIL", "CLAR_STUB_INCOMPLETE"):
            env.pop(name, None)
        if flag:
            env.update(flag)
        proc = subprocess.run(["bash", str(driver)], env=env, capture_output=True, text=True, timeout=120)
        log = (hub / "driver.log").read_text()
        return proc.returncode, hub, log

    def test_complete_is_required_for_success(self):
        rc, hub, log = self.drive()
        self.assertEqual(rc, 0, log[-3000:])
        self.assertTrue((hub / "DRIVER-SUCCESS.json").exists())
        rc2 = subprocess.run(["bash", str(hub / "run_clar.sh")], capture_output=True, timeout=10).returncode
        self.assertEqual(rc2, 9)

    def test_smoke_failure_stops_main(self):
        rc, hub, log = self.drive({"KCONF_STUB_FAIL": "smoke"})
        self.assertEqual(rc, 10, log[-3000:])
        self.assertFalse((hub / "stages/main").exists())
        self.assertFalse((hub / "DRIVER-SUCCESS.json").exists())

    def test_main_failure_cannot_write_success(self):
        rc, hub, log = self.drive({"KCONF_STUB_FAIL": "main"})
        self.assertEqual(rc, 11, log[-3000:])
        self.assertFalse((hub / "DRIVER-SUCCESS.json").exists())
        self.assertEqual(json.loads((hub / "analysis/dev/ANALYSIS.json").read_text())["status"], "INCOMPLETE")

    def test_analyzer_failure_cannot_write_success(self):
        rc, hub, log = self.drive({"CLAR_STUB_ANALYZER_FAIL": "1"})
        self.assertEqual(rc, 5, log[-3000:])
        self.assertFalse((hub / "DRIVER-SUCCESS.json").exists())

    def test_incomplete_analysis_cannot_write_success(self):
        rc, hub, log = self.drive({"CLAR_STUB_INCOMPLETE": "1"})
        self.assertEqual(rc, 12, log[-3000:])
        self.assertFalse((hub / "DRIVER-SUCCESS.json").exists())

    def test_frozen_data_tamper_blocks_collection(self):
        rc, hub, log = self.drive(tamper="data")
        self.assertEqual(rc, 3, log[-3000:])
        self.assertFalse((hub / "stages").exists())

    def test_driver_tamper_blocks_collection(self):
        rc, hub, log = self.drive(tamper="driver")
        self.assertEqual(rc, 3, log[-3000:])
        self.assertFalse((hub / "stages").exists())


if __name__ == "__main__":
    unittest.main()
