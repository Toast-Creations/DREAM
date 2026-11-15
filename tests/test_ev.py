"""EVT-v1: prompt/allocation units, unchanged-pipeline pins, and the actual supervisor + analyzer on CPU fixtures.

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
from tempo import clarify as CL, esubject as ESUB, evreport as ES, kidconfdone as KD  # noqa: E402
import ev_analyze as EA  # noqa: E402
import ev_guard as EG  # noqa: E402
import ev_prepare as EP  # noqa: E402
import ev_run as ER  # noqa: E402
from dream_core import localpaths as LP  # public release: local paths from environment

V124 = Path(f"{LP.CODE}/DREAM-project-1.24.0-clarified-keep-confirm-20261111")
V125 = Path(f"{LP.CODE}/DREAM-project-1.25.0-explicit-subject-dev-20261111")
UNCHANGED_FROM_V125 = ["src/tempo/esubject.py", "scripts/es_analyze.py", "scripts/es_run.py", "scripts/es_prepare.py",
                       "scripts/es_guard.py", "scripts/es_generate.py", "scripts/es_stage_check.py",
                       "tests/test_es.py", "tests/fixtures/es_cpu_runner.py"]
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
        self.assertEqual(len(m["calls"]), 960)
        self.assertEqual(len(s["calls"]), 24)
        self.assertEqual(collections.Counter(c["arm"] for c in m["calls"]), {a: 480 for a in ES.ARMS})
        acts = collections.Counter((t["family"][:2], t["act"]) for t in m["public"])
        self.assertEqual(acts, {("F1", "arrival"): 48, ("F2", "arrival"): 48, ("F3", "arrival"): 192,
                                ("F1", "correction"): 32, ("F2", "correction"): 32, ("F3", "correction"): 128})
        words = collections.Counter((t["family"], t["reception"], ES.wording(t["bits"])) for t in m["public"]
                                    if t["act"] == "arrival")
        for (fam, rec, w), n in words.items():
            self.assertEqual(n, words[(fam, rec, "TRANSITION" if w == "RESULT" else "RESULT")])
        self.assertEqual(sum(words.values()), 288)

    def test_wording_label_matches_public_text(self):
        for part in ("main", "smoke"):
            for t in self.panel[part]["public"]:
                if t["act"] == "arrival":
                    phrase = "so it is now on hand" if ES.wording(t["bits"]) == "RESULT" else \
                        "went from not on hand to on hand"
                    self.assertIn(phrase, t["target_text"])

    def test_candidate_prompt_is_current_plus_one_sentence_line(self):
        calls = {c["call_id"]: c for c in self.panel["main"]["calls"] + self.panel["smoke"]["calls"]}
        n = 0
        for cid, c in calls.items():
            if c["arm"] != "KEEP_EVT":
                continue
            cur = calls[cid.rsplit("|", 1)[0] + "|KEEP_CLAR"]
            self.assertEqual(ES.strip_event(c["user"]), cur["user"])
            self.assertEqual(c["system"], cur["system"])
            self.assertEqual(c["user"].count(ES.EVENT_SENTENCE), 1)
            line = c["user"].split("\n")
            i = line.index(ES.EVENT_SENTENCE)
            self.assertTrue(line[i - 1].startswith(ES.ANCHOR_PREFIX))
            n += 1
        self.assertEqual(n, 492)

    def test_current_prompt_is_unchanged_v124_builder(self):
        for pub in self.panel["main"]["public"][:60]:
            p124, _ = CL.prompts_from_public(pub)
            p, _ = ES.prompts_from_public(pub)
            self.assertEqual(p["KEEP_CLAR"], p124["KEEP_CLAR"])
            self.assertEqual(set(p), set(ES.ARMS))

    def test_fresh_against_esub_namespace(self):
        old = ESUB.generate()
        self.assertFalse({p["base_prompt"] for x in old.values() for p in x["public"]} &
                         {p["base_prompt"] for x in self.panel.values() for p in x["public"]})
        self.assertFalse({h["world_seed"] for x in old.values() for h in x["hidden"]} &
                         {h["world_seed"] for x in self.panel.values() for h in x["hidden"]})

    @unittest.skipUnless(os.environ.get("DREAM_VERIFY_ARCHIVE") == "1" and V124.is_dir(),
                         "archive pin check: set DREAM_VERIFY_ARCHIVE=1 and DREAM_CODE to the private per-version archive")
    def test_esub_files_unchanged_from_v125(self):
        for rel in UNCHANGED_FROM_V125:
            self.assertEqual(sha(ROOT / rel), sha(V125 / rel), rel)

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
            EA.validate_plan(dict(EA.PLAN, candidate="KEEP_CLAR"))

    def test_guard_decide_pin(self):
        self.assertEqual(sha(EA.GUARD_DECIDE), EA.GUARD_DECIDE_SHA256)


class Driver(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.base = Path(cls.temp.name) / "base"
        (cls.base / "config").mkdir(parents=True)
        dump(cls.base / "config/PANEL.json", copy.deepcopy(ES.DEFAULT_CONFIG))
        subprocess.run([sys.executable, "-B", str(ROOT / "scripts/ev_generate.py"), "--hub", str(cls.base),
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
        (hub / "run_ev.sh").write_text(EP.launcher(hub))
        sections = {s: {str(p.relative_to(hub / s)): sha(p) for p in sorted((hub / s).rglob("*")) if p.is_file()}
                    for s in ("design", "config", "data", "phase0")}
        dump(hub / "config/FROZEN-PROTOCOL.json", {"study": "EVT-v1", "source_dir": str(ROOT),
             "source_sha256": release_source_hash(ROOT), "analysis_plan": EA.PLAN,
             "analysis_plan_sha256": KD.plan_sha256(EA.PLAN), "driver_sha256": sha(hub / "run_ev.sh"),
             "model_manifest_path": str(self.manifest), "model_manifest_sha256": sha(self.manifest), **sections})
        return hub

    @staticmethod
    def worker(modes=None):
        modes = modes or {}
        def make(hub, stage, remaining):
            return [sys.executable, "-B", str(ROOT / "tests/fixtures/ev_cpu_runner.py"), "--hub", str(hub),
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

    def test_equal_arms_do_not_warrant_and_resume_refused(self):
        hub = self.hub()
        self.assertEqual(self.run_hub(hub), 0, (hub / "driver.log").read_text()[-4000:])
        a = self.analysis(hub)
        self.assertEqual(a["status"], "COMPLETE")
        for arm in ES.ARMS:
            self.assertEqual(a["by_arm_act"][f"{arm}|arrival"]["exact"], 288)
            self.assertEqual(a["by_arm_act"][f"{arm}|correction"]["exact"], 192)
            self.assertEqual(a["by_arm_act"][f"{arm}|arrival"]["exact_blocked"], 0)
        # nothing to reduce: the state-only baseline criterion (>= 10) fails
        self.assertFalse(a["screen"]["criteria"]["state_only_halved_with_baseline_at_least_10"])
        self.assertEqual(a["screen"]["status"], "DOES_NOT_WARRANT")
        self.assertEqual(self.run_hub(hub), 9)

    def test_candidate_restores_events_warrants(self):
        hub = self.hub()
        self.assertEqual(self.run_hub(hub, {"main": "better"}), 0, (hub / "driver.log").read_text()[-4000:])
        a = self.analysis(hub)
        self.assertEqual(a["by_arm_act"]["KEEP_CLAR|arrival"]["state_only_event_accepted"], 144)
        self.assertEqual(a["by_arm_act"]["KEEP_EVT|arrival"]["state_only_event_accepted"], 0)
        bw = a["breakdowns_descriptive"]["wording"]
        self.assertEqual(bw["KEEP_CLAR|arrival|RESULT"]["state_only_event_accepted"], 144)
        self.assertEqual(bw["KEEP_CLAR|arrival|TRANSITION"]["state_only_event_accepted"], 0)
        self.assertAlmostEqual(a["contrasts"]["arrival|KEEP_EVT-KEEP_CLAR"]["difference_points"], 50.0)
        self.assertAlmostEqual(a["contrasts"]["arrival|RESULT|KEEP_EVT-KEEP_CLAR"]["difference_points"], 100.0)
        self.assertAlmostEqual(a["contrasts"]["arrival|TRANSITION|KEEP_EVT-KEEP_CLAR"]["difference_points"], 0.0)
        self.assertEqual(a["screen"]["status"], "WARRANTS_CONFIRMATION_DESIGN")
        self.assertIn("WARRANTS_CONFIRMATION_DESIGN", (hub / "REPORT.md").read_text())

    def test_candidate_state_only_regression_does_not_warrant(self):
        hub = self.hub()
        self.assertEqual(self.run_hub(hub, {"main": "worse"}), 0)
        a = self.analysis(hub)
        self.assertEqual(a["by_arm_act"]["KEEP_EVT|arrival"]["state_only_event_accepted"], 288)
        self.assertEqual(a["screen"]["status"], "DOES_NOT_WARRANT")
        self.assertFalse(a["screen"]["criteria"]["arrival_exact_not_lower"])

    def test_three_candidate_wrong_bindings_fail_screen(self):
        hub = self.hub()
        self.assertEqual(self.run_hub(hub, {"main": "wrongbind3"}), 0)
        a = self.analysis(hub)
        self.assertEqual(a["screen"]["accepted_wrong_bindings"], {"KEEP_CLAR": 0, "KEEP_EVT": 3})
        self.assertFalse(a["screen"]["criteria"]["wrong_bindings_not_more_than_plus_2"])
        self.assertEqual(a["screen"]["status"], "DOES_NOT_WARRANT")
        self.assertEqual(a["by_arm_act"]["KEEP_EVT|arrival"]["post_wrong_binding"], 0)

    def test_spurious_correction_events_fail_screen(self):
        hub = self.hub()
        self.assertEqual(self.run_hub(hub, {"main": "corrections_event"}), 0)
        a = self.analysis(hub)
        c = a["by_arm_act"]["KEEP_EVT|correction"]
        self.assertEqual(c["responses_with_event_objects"], 192)
        self.assertLess(c["exact"], 192)
        self.assertFalse(a["screen"]["criteria"]["correction_exact_not_lower_than_3_64"])
        self.assertEqual(a["screen"]["status"], "DOES_NOT_WARRANT")

    def test_truncation_is_scored_and_flags_new_class(self):
        hub = self.hub()
        self.assertEqual(self.run_hub(hub, {"main": "truncate"}), 0, (hub / "driver.log").read_text()[-4000:])
        a = self.analysis(hub)
        self.assertEqual(a["by_arm_act"]["KEEP_EVT|arrival"]["truncated"], 1)
        self.assertEqual(len(a["truncated"]), 1)
        self.assertEqual(a["screen"]["status"], "REVIEW_NEW_FAILURE_TYPES")

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
        self.assertEqual(EG.POLICY["total_attempts"], 984)
        hub = self.hub()
        start = int(time.time())
        dump(hub / "config/DEADLINE.json", {"driver_start_epoch": start, "deadline_epoch": start + 28800})
        for i in range(24):
            dump(hub / f"stages/smoke/calls/{i}.json", {"status": "ok", "seconds": 12.6})
        r = EG.check(hub, "main")
        self.assertTrue(r["ok"], r["problems"])
        self.assertLess(r["projected_total_s"], 27000)


if __name__ == "__main__":
    unittest.main()
