"""ESUB-v1: prompt/allocation units, unchanged-pipeline pins, and the actual supervisor + analyzer on CPU fixtures.

CPU fixtures emit canonical replies through the real runner record schema; never study evidence.
"""
import collections
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
from tempo import clarify as CL, esubject as ES, kidconfdone as KD  # noqa: E402
import es_analyze as EA  # noqa: E402
import es_guard as EG  # noqa: E402
import es_prepare as EP  # noqa: E402
import es_run as ER  # noqa: E402
from dream_core import localpaths as LP  # public release: local paths from environment

V124 = Path(f"{LP.CODE}/DREAM-project-1.24.0-clarified-keep-confirm-20261111")
UNCHANGED = ["src/tempo/factored.py", "src/tempo/refres.py", "src/tempo/holdeval.py", "src/tempo/kidconfscore.py",
             "src/tempo/score.py", "src/tempo/holdout.py", "src/tempo/kidconfgen.py", "src/tempo/keepid.py",
             "src/tempo/clarify.py", "src/tempo/kidconf.py", "src/tempo/assertions.py", "src/tempo/engine.py",
             "src/dream_core/modeling.py", "src/dream_core/modeling_q.py", "scripts/hold_run.py",
             "scripts/clar_analyze.py", "scripts/kconf_analyze.py"]


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=1) + "\n")


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


class Units(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.panel = ES.generate()

    def test_counts_and_balance(self):
        m, s = self.panel["main"], self.panel["smoke"]
        self.assertEqual(len(m["calls"]), 1440)
        self.assertEqual(len(s["calls"]), 36)
        self.assertEqual(collections.Counter(c["arm"] for c in m["calls"]), {a: 480 for a in ES.ARMS})
        acts = collections.Counter((t["family"][:2], t["act"]) for t in m["public"])
        self.assertEqual(acts, {("F1", "arrival"): 48, ("F2", "arrival"): 48, ("F3", "arrival"): 192,
                                ("F1", "correction"): 32, ("F2", "correction"): 32, ("F3", "correction"): 128})
        for panel in ("primary_arrival", "primary_correction"):
            cells = collections.Counter((r["family"], r["reception"], tuple(r["bits"])) for r in ES.plan() if r[panel])
            for fam in {k[:2] for k in cells}:
                self.assertEqual(len({v for k, v in cells.items() if k[:2] == fam}), 1, (panel, fam))

    def test_candidate_prompt_is_current_plus_one_sentence_line(self):
        calls = {c["call_id"]: c for c in self.panel["main"]["calls"] + self.panel["smoke"]["calls"]}
        n = 0
        for cid, c in calls.items():
            if c["arm"] != "KEEP_SUBJ":
                continue
            base = cid.rsplit("|", 1)[0]
            cur, cand = calls[base + "|KEEP_CLAR"], c
            self.assertEqual(ES.strip_subject(cand["user"]), cur["user"])
            self.assertEqual(cand["system"], cur["system"])
            self.assertEqual(cand["user"].count(ES.SUBJECT_SENTENCE), 1)
            line = cand["user"].split("\n")
            i = line.index(ES.SUBJECT_SENTENCE)
            self.assertTrue(line[i - 1].startswith("Resolved reference: "))
            n += 1
        self.assertEqual(n, 492)

    def test_current_and_anchor_prompts_are_unchanged_v124_builders(self):
        for pub in self.panel["main"]["public"][:60]:
            p124, _ = CL.prompts_from_public(pub)
            p, _ = ES.prompts_from_public(pub)
            self.assertEqual(p["SUB_ORIG"], p124["SUB_ORIG"])
            self.assertEqual(p["KEEP_CLAR"], p124["KEEP_CLAR"])

    @unittest.skipUnless(os.environ.get("DREAM_VERIFY_ARCHIVE") == "1" and V124.is_dir(),
                         "archive pin check: set DREAM_VERIFY_ARCHIVE=1 and DREAM_CODE to the private per-version archive")
    def test_unchanged_pipeline_files_byte_identical_to_v124(self):
        for rel in UNCHANGED:
            self.assertEqual(sha(ROOT / rel), sha(V124 / rel), rel)

    def test_config_closed(self):
        bad = copy.deepcopy(ES.DEFAULT_CONFIG)
        bad["correction_blocks"] = 8
        with self.assertRaises(ValueError):
            ES.validate_config(bad)
        with self.assertRaises(ValueError):
            EA.validate_plan(dict(EA.PLAN, candidate="SUB_ORIG"))

    def test_guard_decide_pin(self):
        self.assertEqual(sha(EA.GUARD_DECIDE), EA.GUARD_DECIDE_SHA256)


class Driver(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.base = Path(cls.temp.name) / "base"
        (cls.base / "config").mkdir(parents=True)
        dump(cls.base / "config/PANEL.json", copy.deepcopy(ES.DEFAULT_CONFIG))
        subprocess.run([sys.executable, "-B", str(ROOT / "scripts/es_generate.py"), "--hub", str(cls.base),
                        "--config", str(cls.base / "config/PANEL.json")], check=True, capture_output=True)
        dump(cls.base / "config/ANALYSIS-PLAN.json", EA.PLAN)
        dump(cls.base / "config/RESOURCE-GUARD.json", EG.POLICY)
        model_from = cls.base / "fixture-model.json"
        dump(model_from, {"model": EP.MODEL})
        EP.configs(cls.base, model_from)
        (cls.base / "design").mkdir()
        (cls.base / "design/PROTOCOL.md").write_text("CPU FIXTURE, not study evidence\n")
        dump(cls.base / "phase0/VALIDATION.json", {"all_pass": True, "fixture": True})
        cls.manifest = Path(cls.temp.name) / "model-manifest.json"
        cls.manifest.write_text("{}")
        cls.serial = 0

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def hub(self):
        type(self).serial += 1
        hub = Path(self.temp.name) / f"h{self.serial}"
        shutil.copytree(self.base, hub)
        (hub / "run_es.sh").write_text(EP.launcher(hub))
        sections = {s: {str(p.relative_to(hub / s)): sha(p) for p in sorted((hub / s).rglob("*")) if p.is_file()}
                    for s in ("design", "config", "data", "phase0")}
        dump(hub / "config/FROZEN-PROTOCOL.json", {"study": "ESUB-v1", "source_dir": str(ROOT),
             "source_sha256": release_source_hash(ROOT), "analysis_plan": EA.PLAN,
             "analysis_plan_sha256": KD.plan_sha256(EA.PLAN), "driver_sha256": sha(hub / "run_es.sh"),
             "model_manifest_path": str(self.manifest), "model_manifest_sha256": sha(self.manifest), **sections})
        return hub

    @staticmethod
    def worker(modes=None):
        modes = modes or {}
        def make(hub, stage, remaining):
            return [sys.executable, "-B", str(ROOT / "tests/fixtures/es_cpu_runner.py"), "--hub", str(hub),
                    "--stage", stage, "--config", str(hub / f"config/stage-{stage}.json"),
                    "--mode", modes.get(stage, "equal")]
        return make

    def run_hub(self, hub, modes=None, **kw):
        return ER.drive(hub, worker=self.worker(modes), gpu_probe=lambda: {"fixture": True}, notify=False, **kw)

    def analysis(self, hub):
        return json.loads((hub / "analysis/dev/ANALYSIS.json").read_text())

    def assert_failed(self, hub):
        self.assertTrue((hub / "DRIVER-FAILURE.json").exists())
        self.assertFalse((hub / "DRIVER-SUCCESS.json").exists())
        a = self.analysis(hub)
        self.assertEqual(a["status"], "INCOMPLETE")
        self.assertEqual(a["screen"]["status"], "NOT_EVALUATED")
        self.assertIn("INCOMPLETE", (hub / "RUN-STATUS.md").read_text())

    def test_equal_arms_complete_and_resume_refused(self):
        hub = self.hub()
        self.assertEqual(self.run_hub(hub), 0, (hub / "driver.log").read_text()[-4000:])
        a = self.analysis(hub)
        self.assertEqual(a["status"], "COMPLETE")
        for arm in ES.ARMS:
            self.assertEqual(a["by_arm_act"][f"{arm}|arrival"]["exact"], 288)
            self.assertEqual(a["by_arm_act"][f"{arm}|correction"]["exact"], 192)
            self.assertEqual(a["by_arm_act"][f"{arm}|arrival"]["exact_blocked"], 0)
        self.assertEqual(a["screen"]["status"], "WARRANTS_CONFIRMATION_DESIGN")
        self.assertEqual(json.loads((hub / "DRIVER-SUCCESS.json").read_text())["screen"], "WARRANTS_CONFIRMATION_DESIGN")
        self.assertEqual(self.run_hub(hub), 9)

    def test_current_wrong_bindings_counted_and_guard_blocks_them(self):
        hub = self.hub()
        self.assertEqual(self.run_hub(hub, {"main": "better"}), 0)
        a = self.analysis(hub)
        c = a["by_arm_act"]["KEEP_CLAR|arrival"]
        self.assertEqual(c["accepted_wrong_binding"], 96)
        self.assertEqual(c["post_wrong_binding"], 0)
        self.assertEqual(c["guard"].get("identity_mismatch"), 96)
        self.assertEqual(a["screen"]["f3_history_b_arrival_wrong_bindings"]["KEEP_SUBJ"], 0)
        self.assertGreater(a["contrasts"]["arrival|KEEP_SUBJ-KEEP_CLAR"]["difference_points"], 0)

    def test_candidate_state_only_regression_does_not_warrant(self):
        hub = self.hub()
        self.assertEqual(self.run_hub(hub, {"main": "worse"}), 0)
        a = self.analysis(hub)
        self.assertEqual(a["by_arm_act"]["KEEP_SUBJ|arrival"]["state_only_event_accepted"], 288)
        self.assertEqual(a["screen"]["status"], "DOES_NOT_WARRANT")
        self.assertFalse(a["screen"]["criteria"]["state_only_not_more_than_plus_3"])

    def test_single_candidate_wrong_binding_fails_screen(self):
        hub = self.hub()
        self.assertEqual(self.run_hub(hub, {"main": "wrongbind"}), 0)
        a = self.analysis(hub)
        self.assertEqual(a["screen"]["accepted_wrong_bindings"], {"SUB_ORIG": 0, "KEEP_CLAR": 0, "KEEP_SUBJ": 1})
        self.assertEqual(a["screen"]["status"], "DOES_NOT_WARRANT")
        self.assertEqual(len(a["wrong_bindings"]), 1)
        self.assertEqual(a["wrong_bindings"][0]["guard_disposition"], "identity_mismatch")

    def test_main_failure_is_incomplete(self):
        hub = self.hub()
        self.assertEqual(self.run_hub(hub, {"main": "fail"}), 1)
        self.assert_failed(hub)

    def test_slow_smoke_stops_before_main(self):
        hub = self.hub()
        self.assertEqual(self.run_hub(hub, {"smoke": "slow"}), 1)
        self.assert_failed(hub)
        self.assertFalse((hub / "stages/main").exists())
        self.assertIn("7.5-hour", (hub / "driver.log").read_text())

    def test_frozen_tamper_blocks_workers(self):
        hub = self.hub()
        with (hub / "data/main-calls.jsonl").open("a") as out:
            out.write("\n")
        self.assertEqual(self.run_hub(hub), 1)
        self.assertFalse((hub / "stages").exists())

    def test_missing_record_makes_analysis_incomplete(self):
        hub = self.hub()
        self.assertEqual(self.run_hub(hub), 0)
        next((hub / "stages/main/calls").glob("*.json")).unlink()
        r = EA.write_artifacts(hub)
        self.assertEqual(r["status"], "INCOMPLETE")
        self.assertEqual(r["screen"]["status"], "NOT_EVALUATED")

    def test_guard_policy_and_deadline(self):
        self.assertEqual(EG.POLICY["ceiling_s"], 8 * 3600)
        self.assertEqual(EG.POLICY["total_attempts"], 1476)
        hub = self.hub()
        start = int(time.time())
        dump(hub / "config/DEADLINE.json", {"driver_start_epoch": start, "deadline_epoch": start + 28800})
        for i in range(36):
            dump(hub / f"stages/smoke/calls/{i}.json", {"status": "ok", "seconds": 12.6})
        r = EG.check(hub, "main")
        self.assertTrue(r["ok"], r["problems"])
        self.assertLess(r["projected_total_s"], 27000)


if __name__ == "__main__":
    unittest.main()
