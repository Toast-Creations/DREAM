"""EVT suite (V1.27.0; V1.28.0 adds the C4-N/C4-K cutoff regressions; V1.29.0 adds study D, EVTT-v1): allocation/prompt units, unchanged-pipeline pins, the actual supervisor + analyzer on CPU
fixtures for studies A, B and C, and the back-to-back chain.

CPU fixtures emit canonical replies through the real runner record schema; never study evidence.
"""
import collections
import copy
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime
import os
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from dream_core.ledger import release_source_hash  # noqa: E402
from tempo import clarify as CL, esubject as ESUB, evreport as ES, evsuite as S, kidconfdone as KD  # noqa: E402
import ev_prepare as EVP  # noqa: E402
import su_analyze as SA  # noqa: E402
import su_certify as SCERT  # noqa: E402
import su_chain as SC  # noqa: E402
import su_guard as SG  # noqa: E402
import su_phase0 as P0  # noqa: E402
import su_prepare as SP  # noqa: E402
import su_run as SR  # noqa: E402
from dream_core import localpaths as LP  # public release: local paths from environment

V124 = Path(f"{LP.CODE}/DREAM-project-1.24.0-clarified-keep-confirm-20261111")
V125 = Path(f"{LP.CODE}/DREAM-project-1.25.0-explicit-subject-dev-20261111")
V126 = Path(f"{LP.CODE}/DREAM-project-1.26.0-event-report-dev-20261112")
V127 = Path(f"{LP.CODE}/DREAM-project-1.27.0-event-suite-20261112")
EVT_HUB = Path(f"{LP.RUNS}/temporal-event-report-dev-20261112-070245")
UNCHANGED_FROM_V126 = ["src/tempo/evreport.py", "scripts/ev_analyze.py", "scripts/ev_run.py", "scripts/ev_prepare.py",
                       "scripts/ev_guard.py", "scripts/ev_generate.py", "scripts/ev_stage_check.py",
                       "tests/test_ev.py", "tests/fixtures/ev_cpu_runner.py"]
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


def synthetic_history(root):
    """A small stand-in for Runs/ with every hub su_phase0 requires (CPU fixture; not study evidence).
    -> generator input files (all files of prompt-bearing hubs)."""
    inputs, seed = [], 10 ** 15
    seed_only = {"temporal-factored-assertions-20261106-101739", "temporal-larger-extractor-20261106-123049",
                 "temporal-record-context-20261106-075907"}
    for name in sorted(P0.REQUIRED_HUBS_D):
        files = ("data/hidden/main-cases.jsonl",) if name in seed_only else P0.PANEL_FILES
        for rel in files:
            rows = []
            for i in range(3):
                seed += 1
                row = {"world_seed": seed}
                if "public" in rel:
                    row["base_prompt"] = f"synthetic historical prompt {name} {rel} {i}"
                rows.append(row)
            path = Path(root) / name / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("".join(json.dumps(r) + "\n" for r in rows))
            if name not in seed_only:
                inputs.append(str(path.resolve()))
    return inputs


def d_phase0(hub, root):
    """Consistent, passing phase0 evidence for a D fixture hub (shapes of the real records)."""
    cfg = S.default_config("D")
    source = release_source_hash(ROOT)
    full = {"version": "fixture", "tests_run": 5, "failures": 0, "errors": 0, "skipped": 0,
            "ml_dependencies_available": True, "passed": 5, "skipped_tests": [], "success": True,
            "source_sha256": source}
    cells = {f"{st}|{arm}": {"count": cfg[f"{st}_calls"] // 3, "min": 1300, "max": 1600}
             for st in ("smoke", "main") for arm in cfg["arms"]}
    tokens = {"all_pass": True, "calls_checked": cfg["main_calls"] + cfg["smoke_calls"], "by_stage_arm": cells,
              "calls_sha256": {st: sha(Path(hub) / f"data/{st}-calls.jsonl") for st in ("smoke", "main")}}
    validation = {"all_pass": True, "fixture": True, "source_sha256": source,
                  "components": {"full_test_suite": {"tests_run": 5, "passed": 5, "env": "fixture --require-ml"},
                                 "tokens": {"calls_checked": tokens["calls_checked"], "max_input_tokens": 1600}}}
    dump(Path(hub) / "phase0/FULL-TESTS.json", full)
    dump(Path(hub) / "phase0/TOKENS.json", tokens)
    dump(Path(hub) / "phase0/VALIDATION.json", validation)
    dump(Path(hub) / "phase0/HISTORICAL.json", P0.build_historical(hub, root))


class Units(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.panels = {k: S.generate(S.default_config(k)) for k in S.SPECS}

    def test_counts_and_balance(self):
        want = {"A": (1536, 24, 768), "B": (1440, 36, 480), "C": (1152, 12, 384), "D": (1620, 36, 540)}
        for key, (main, smoke, per_arm) in want.items():
            m, s = self.panels[key]["main"], self.panels[key]["smoke"]
            self.assertEqual(len(m["calls"]), main, key)
            self.assertEqual(len(s["calls"]), smoke, key)
            self.assertEqual(collections.Counter(c["arm"] for c in m["calls"]),
                             {a: per_arm for a in S.SPECS[key]["arms"]})
            words = collections.Counter((t["family"], t["reception"], t["history"], ES.wording(t["bits"]))
                                        for t in m["public"] if t["act"] == "arrival")
            for (fam, rec, hist, w), n in words.items():
                self.assertEqual(n, words[(fam, rec, hist, "TRANSITION" if w == "RESULT" else "RESULT")])
        c = self.panels["C"]["main"]["public"]
        self.assertEqual({t["history"] for t in c}, {"B"})
        self.assertEqual({t["act"] for t in c}, {"arrival"})
        self.assertEqual(collections.Counter(t["family"][:2] for t in c), {"F2": 96, "F3": 288})
        d = collections.Counter((t["family"][:2], t["reception"], ES.wording(t["bits"]), t["act"])
                                for t in self.panels["D"]["main"]["public"])
        self.assertEqual(d[("F3", "delayed", "RESULT", "arrival")], 144)
        self.assertEqual(sum(v for k, v in d.items() if k[1:] == ("immediate", "RESULT", "arrival")), 64)
        self.assertEqual(sum(v for k, v in d.items() if k[3] == "correction"), 60)
        self.assertEqual(sum(v for k, v in d.items() if k[2] == "TRANSITION" and k[3] == "arrival"), 240)
        a = collections.Counter((t["family"][:2], t["act"]) for t in self.panels["A"]["main"]["public"])
        self.assertEqual(a, {("F1", "arrival"): 96, ("F2", "arrival"): 96, ("F3", "arrival"): 384,
                             ("F1", "correction"): 32, ("F2", "correction"): 32, ("F3", "correction"): 128})

    def test_wording_label_matches_public_text(self):
        for panel in self.panels.values():
            for part in ("main", "smoke"):
                for t in panel[part]["public"]:
                    if t["act"] == "arrival":
                        phrase = "so it is now on hand" if ES.wording(t["bits"]) == "RESULT" else \
                            "went from not on hand to on hand"
                        self.assertIn(phrase, t["target_text"])

    def test_candidate_prompts_are_current_plus_one_line(self):
        n = collections.Counter()
        for panel in self.panels.values():
            calls = {c["call_id"]: c for c in panel["main"]["calls"] + panel["smoke"]["calls"]}
            for cid, c in calls.items():
                if c["arm"] == "KEEP_CLAR":
                    continue
                cur = calls[cid.rsplit("|", 1)[0] + "|KEEP_CLAR"]
                sentence = S.SENTENCES[c["arm"]]
                self.assertEqual(S.strip_line(c["user"], sentence), cur["user"])
                self.assertEqual(c["system"], cur["system"])
                lines = c["user"].split("\n")
                self.assertTrue(lines[lines.index(sentence) - 1].startswith(S.ANCHOR_PREFIX))
                other = [x for x in S.SENTENCES.values() if x != sentence and x not in sentence]
                self.assertFalse(any(x in c["user"] for x in other))
                if c["arm"] == "KEEP_EVT":
                    self.assertEqual(c["user"], ES.event_prompt(cur["user"]))
                if c["arm"] == "KEEP_EVTT":   # KEEP_EVT's line plus one appended sentence, nothing else
                    evt = calls[cid.rsplit("|", 1)[0] + "|KEEP_EVT"]["user"]
                    self.assertEqual(c["user"].replace(" " + S.EVTT_CLAUSE + "\n", "\n", 1), evt)
                    self.assertEqual(c["user"].count(S.EVTT_CLAUSE), 1)
                n[c["arm"]] += 1
        self.assertEqual(n["KEEP_EVT"], 768 + 12 + 480 + 12 + 384 + 4 + 540 + 12)
        self.assertEqual(n["KEEP_EVTR"], 480 + 12 + 384 + 4)
        self.assertEqual(n["KEEP_EVTT"], 540 + 12)

    def test_evtt_sentence_is_evt_plus_evtr_time_clause(self):
        self.assertEqual(S.EVTT_SENTENCE, S.EVENT_SENTENCE + " " + S.EVTT_CLAUSE)
        tail = S.EVTR_SENTENCE.split("; ", 1)[1]
        self.assertEqual(S.EVTT_CLAUSE, tail[0].upper() + tail[1:])
        self.assertNotIn("revision", S.EVTT_SENTENCE.lower())

    @unittest.skipUnless((V127 / "src/tempo/evsuite.py").is_file(), "V1.27.0 tree not present")
    def test_studies_A_to_C_are_unchanged_from_v127(self):
        code = ("import json,sys; sys.path[:0]=[sys.argv[1]+'/src', sys.argv[1]+'/scripts'];"
                "from tempo import evsuite as S; import su_analyze as A, su_guard as G;"
                "print(json.dumps({k: [S.default_config(k), A.PLANS[k], A.PAIRS[k], G.policy(k), "
                "[S.plan(S.default_config(k), smoke=x) for x in (False, True)]] for k in 'ABC'}, sort_keys=True))")
        out = {}
        for tree in (V127, ROOT):
            r = subprocess.run([sys.executable, "-B", "-c", code, str(tree)], capture_output=True, text=True,
                               check=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
            out[tree] = r.stdout
        self.assertEqual(out[V127], out[ROOT])

    def test_evtr_sentence_wording_constraints(self):
        self.assertNotIn("revision", S.EVTR_SENTENCE.lower())
        self.assertNotIn("deliver", S.EVTR_SENTENCE.lower())
        self.assertEqual(S.EVENT_SENTENCE, ES.EVENT_SENTENCE)

    def test_current_prompt_is_unchanged_v124_builder(self):
        for key in S.SPECS:
            cfg = S.default_config(key)
            for pub in self.panels[key]["main"]["public"][:40]:
                p124, _ = CL.prompts_from_public(pub)
                p, _ = S.prompts_from_public(pub, cfg)
                self.assertEqual(p["KEEP_CLAR"], p124["KEEP_CLAR"])
                self.assertEqual(set(p), set(S.SPECS[key]["arms"]))

    def test_fresh_against_each_other_and_earlier_namespaces(self):
        sets = {k: ({p["base_prompt"] for x in v.values() for p in x["public"]},
                    {h["world_seed"] for x in v.values() for h in x["hidden"]}) for k, v in self.panels.items()}
        for old in (ESUB.generate(), ES.generate()):
            sets[id(old)] = ({p["base_prompt"] for x in old.values() for p in x["public"]},
                             {h["world_seed"] for x in old.values() for h in x["hidden"]})
        keys = list(sets)
        for i, a in enumerate(keys):
            for b in keys[i + 1:]:
                self.assertFalse(sets[a][0] & sets[b][0], (a, b))
                self.assertFalse(sets[a][1] & sets[b][1], (a, b))

    @unittest.skipUnless(os.environ.get("DREAM_VERIFY_ARCHIVE") == "1" and V124.is_dir(),
                         "archive pin check: set DREAM_VERIFY_ARCHIVE=1 and DREAM_CODE to the private per-version archive")
    def test_unchanged_files(self):
        for rel in UNCHANGED:
            self.assertEqual(sha(ROOT / rel), sha(V124 / rel), rel)
        for rel in UNCHANGED_FROM_V125:
            self.assertEqual(sha(ROOT / rel), sha(V125 / rel), rel)
        for rel in UNCHANGED_FROM_V126:
            self.assertEqual(sha(ROOT / rel), sha(V126 / rel), rel)

    def test_config_and_plan_closed(self):
        bad = copy.deepcopy(S.default_config("A"))
        bad["arrival_blocks"] = 12
        with self.assertRaises(ValueError):
            S.validate_config(bad)
        bad = copy.deepcopy(S.default_config("C"))
        bad["arms"] = ["KEEP_CLAR", "KEEP_EVT"]
        with self.assertRaises(ValueError):
            S.validate_config(bad)
        with self.assertRaises(ValueError):
            SA.validate_plan(dict(SA.PLANS["B"], candidate="KEEP_EVT"), "B")
        for key in S.SPECS:
            self.assertEqual(SA.PLANS[key]["study"], S.SPECS[key]["study"])

    def test_guard_decide_pin(self):
        from ev_analyze import GUARD_DECIDE
        self.assertEqual(sha(GUARD_DECIDE), SA.GUARD_DECIDE_SHA256)

    def test_pooled_wrong_binding_tolerance(self):
        lam = 288 * 17 / 2000
        p = [math.exp(-lam) * lam ** k / math.factorial(k) for k in range(60)]
        tail = lambda k: sum(p[x] * p[y] for x in range(60) for y in range(60) if x - y > k)  # noqa: E731
        k = next(k for k in range(20) if tail(k) <= 0.05)
        self.assertEqual(k, SA.POOLED_WB["k"])

    def test_interval_helpers(self):
        lo, hi = SA.clopper_pearson(0, 384)
        self.assertEqual(lo, 0.0)
        self.assertAlmostEqual(hi, 1 - 0.025 ** (1 / 384), places=6)
        lo, hi = SA.clopper_pearson(4, 288)
        self.assertTrue(0.003 < lo < 0.004 and 0.035 < hi < 0.036, (lo, hi))
        self.assertAlmostEqual(SA.sign_test(3, 0), 0.25)
        self.assertEqual(SA.sign_test(0, 0), 1.0)

    @unittest.skipUnless((EVT_HUB / "analysis/dev/scored.jsonl").is_file(), "EVT-v1 hub not present")
    def test_subpattern_reproduces_reviewed_evt_v1_classification(self):
        pubs, hids = {}, {}
        for line in (EVT_HUB / "data/public/main-targets.jsonl").read_text().splitlines():
            r = json.loads(line)
            pubs[r["target"]] = r
        for line in (EVT_HUB / "data/hidden/main-cases.jsonl").read_text().splitlines():
            r = json.loads(line)
            hids[r["target"]] = r
        got, rows = {}, {}
        for line in (EVT_HUB / "analysis/dev/scored.jsonl").read_text().splitlines():
            r = json.loads(line)
            if r["rejected"]:
                t = r["call_id"].rsplit("|", 1)[0]
                got[r["call_id"]] = SA.subpattern(r, r["raw"], pubs[t], hids[t])
                rows[r["call_id"]] = (r, pubs[t], hids[t])
        reviewed = {"v26-g0050|arrival|na|A|KEEP_CLAR": "arrival with spurious revisions",
                    "v26-g0098|arrival|na|A|KEEP_CLAR": "arrival with spurious revisions",
                    "v26-g0098|arrival|na|B|KEEP_CLAR": "arrival with spurious revisions",
                    "v26-g0105|arrival|na|B|KEEP_EVT": SA.RECEPTION_DATED,
                    "v26-g0110|arrival|na|A|KEEP_EVT": "arrival with spurious revisions",
                    "v26-g0118|arrival|na|A|KEEP_EVT": SA.RECEPTION_DATED,
                    "v26-g0118|arrival|na|B|KEEP_EVT": SA.RECEPTION_DATED,
                    "v26-g0134|arrival|na|A|KEEP_EVT": "arrival with spurious revisions"}
        self.assertEqual(got, reviewed)
        # negative controls (Codex F4): each perturbation of a reviewed positive must not get the narrow label
        r, pub, hid = rows["v26-g0105|arrival|na|B|KEEP_EVT"]
        base = json.loads(r["raw"].strip().strip("`").removeprefix("json"))
        other = next(f for f in pub["registry_order"] if f.endswith(".on_hand") and f != base["states"][0]["field"])

        def label(obj=None, case_edit=None):
            h = copy.deepcopy(hid)
            if case_edit:
                case_edit(h["case"])
            return SA.subpattern(r, json.dumps(obj or base), pub, h)
        self.assertEqual(label(), SA.RECEPTION_DATED)

        def immediate(case):
            case["recv"] = case["records"][-1]["event_at"]
        variants = {
            "immediate reception": label(case_edit=immediate),
            "wrong event time": label(dict(base, events=[dict(base["events"][0], at=base["events"][0]["at"] - 1)])),
            "wrong state field": label(dict(base, states=[dict(base["states"][0], field=other)])),
            "wrong state value": label(dict(base, states=[dict(base["states"][0], value="no")])),
            "false reply receipt": label(dict(base, received_at=base["received_at"] + 1)),
            "extra unrelated event": label(dict(base, events=base["events"] + [
                {"field": other, "at": base["states"][0]["at"], "from": "no", "to": "yes"}])),
        }
        for name, value in variants.items():
            self.assertNotEqual(value, SA.RECEPTION_DATED, name)


class Driver(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.manifest = (Path(cls.temp.name) / "model-manifest.json").resolve()
        cls.manifest.write_text("{}")
        SCERT.MANIFEST_PATH = str(cls.manifest)   # explicit fixture injection (production uses the model manifest)
        cls.bases = {}
        cls.history = Path(cls.temp.name) / "runs"
        cls._hist_root = P0.HISTORICAL_ROOT
        P0.HISTORICAL_ROOT = cls.history   # explicit fixture injection, like MANIFEST_PATH
        history_inputs = synthetic_history(cls.history)
        for key in S.SPECS:
            base = Path(cls.temp.name) / f"base{key}"
            (base / "config").mkdir(parents=True)
            dump(base / "config/PANEL.json", S.default_config(key))
            subprocess.run([sys.executable, "-B", str(ROOT / "scripts/su_generate.py"), "--hub", str(base),
                            "--config", str(base / "config/PANEL.json")]
                           + (["--historical", *history_inputs] if key == "D" else []), check=True,
                           capture_output=True)
            dump(base / "config/ANALYSIS-PLAN.json", SA.PLANS[key])
            dump(base / "config/RESOURCE-GUARD.json", SG.policy(key))
            model_from = base / "fixture-model.json"
            dump(model_from, {"model": EVP.MODEL})
            SP.configs(base, model_from)
            (base / "design").mkdir()
            for name in ("PROTOCOL.md", "SUITE-PROTOCOL.md", "AUTHORIZATION.md"):
                (base / "design" / name).write_text("CPU FIXTURE, not study evidence\n")
            dump(base / "config/COORDINATION.json", {"path": "/nonexistent/fixture-notice.md"})
            dump(base / "phase0/VALIDATION.json", {"all_pass": True, "fixture": True,
                                                   "source_sha256": release_source_hash(ROOT)})
            for name in ("FULL-TESTS.json", "TOKENS.json", "HISTORICAL.json"):
                dump(base / "phase0" / name, {"fixture": True})
            if key == "D":
                d_phase0(base, cls.history)
            cls.bases[key] = base
        cls.serial = 0
        cls._settle = SC.LIFELINE_SETTLE_S
        SC.LIFELINE_SETTLE_S = 0.2   # fixture children have no lifeline worker; the settle test sets its own value

    @classmethod
    def tearDownClass(cls):
        SC.LIFELINE_SETTLE_S = cls._settle
        P0.HISTORICAL_ROOT = cls._hist_root
        cls.temp.cleanup()

    def hub(self, key, parent=None, name=None, edit=None):
        type(self).serial += 1
        hub = Path(parent or self.temp.name) / (name or f"h{self.serial}")
        shutil.copytree(self.bases[key], hub)
        if edit:   # pre-freeze edit, hashed into the fixture freeze like an erroneous record would be
            edit(hub)
        (hub / "run_su.sh").write_text(SP.launcher(hub))
        sections = {s: {str(p.relative_to(hub / s)): sha(p) for p in sorted((hub / s).rglob("*")) if p.is_file()}
                    for s in ("design", "config", "data", "phase0")}
        frozen_at = datetime.fromtimestamp(time.time() - 5, ZoneInfo("America/New_York")).isoformat()
        dump(hub / "config/FROZEN-PROTOCOL.json", {"study": S.SPECS[key]["study"], "suite": S.SUITE, "key": key,
             "status": "CPU FIXTURE", "frozen_at": frozen_at, "source_dir": str(ROOT),
             "source_sha256": release_source_hash(ROOT), "analysis_plan": SA.PLANS[key],
             "analysis_plan_sha256": KD.plan_sha256(SA.PLANS[key]), "driver_sha256": sha(hub / "run_su.sh"),
             "model_manifest_path": str(self.manifest), "model_manifest_sha256": sha(self.manifest), **sections})
        return hub

    @staticmethod
    def worker(modes=None):
        modes = modes or {}

        def make(hub, stage, remaining):
            return [sys.executable, "-B", str(ROOT / "tests/fixtures/su_cpu_runner.py"), "--hub", str(hub),
                    "--stage", stage, "--config", str(hub / f"config/stage-{stage}.json"),
                    "--mode", modes.get(stage, "equal")]
        return make

    def run_hub(self, hub, modes=None, **kw):
        kw.setdefault("gpu_probe", lambda: {"fixture": True})
        return SR.drive(hub, worker=self.worker(modes), notify=False, **kw)

    def analysis(self, hub):
        return json.loads((hub / "analysis/dev/ANALYSIS.json").read_text())

    def ok(self, hub, modes=None):
        self.assertEqual(self.run_hub(hub, modes), 0, (hub / "driver.log").read_text()[-4000:])
        a = self.analysis(hub)
        self.assertEqual(a["status"], "COMPLETE")
        return a

    def assert_failed(self, hub):
        self.assertTrue((hub / "DRIVER-FAILURE.json").exists())
        self.assertFalse((hub / "DRIVER-SUCCESS.json").exists())
        a = self.analysis(hub)
        self.assertEqual(a["status"], "INCOMPLETE")
        self.assertEqual(a["reading"]["status"], "NOT_EVALUATED")
        self.assertIn("INCOMPLETE", (hub / "RUN-STATUS.md").read_text())

    # ---- study A: confirmation
    def test_A_equal_does_not_confirm_and_resume_refused(self):
        hub = self.hub("A")
        a = self.ok(hub)
        self.assertFalse(a["reading"]["criteria"]["usable_exact_arrival_gain"])
        self.assertEqual(a["reading"]["status"], "DOES_NOT_CONFIRM")
        self.assertEqual(self.run_hub(hub), 9)

    def test_A_better_confirms(self):
        a = self.ok(self.hub("A"), {"main": "better"})
        self.assertEqual(a["by_arm_act"]["KEEP_CLAR|arrival"]["state_only_event_accepted"], 288)
        self.assertAlmostEqual(a["contrasts"]["arrival|usable_exact|KEEP_EVT-KEEP_CLAR"]["difference_points"], 50.0)
        self.assertGreater(a["contrasts"]["arrival|usable_exact|KEEP_EVT-KEEP_CLAR"]["bootstrap95_points"][0], 0)
        self.assertEqual(a["reading"]["status"], "CONFIRMS_ON_THIS_PANEL")

    def test_A_wrong_bindings_are_guarded_but_flag_review(self):
        hub = self.hub("A")
        a = self.ok(hub, {"main": "wrongbind5"})
        self.assertEqual(a["reading"]["accepted_wrong_bindings"], {"KEEP_CLAR": 0, "KEEP_EVT": 5})
        self.assertEqual(a["reading"]["post_guard_wrong_bindings"], {"KEEP_CLAR": 0, "KEEP_EVT": 0})
        self.assertTrue(all(a["reading"]["criteria"].values()))
        self.assertEqual(a["reading"]["status"], "REVIEW_NEW_FAILURE_TYPES")
        self.assertIn("arrival|outcomes", a["reading"]["new_in_candidate"])

    def test_A_state_at_reception_subpattern_flags_review(self):
        a = self.ok(self.hub("A"), {"main": "stateatrecv"})
        self.assertEqual(a["by_arm_act"]["KEEP_EVT|arrival"]["subpatterns"].get(SA.RECEPTION_DATED), 2)
        self.assertEqual(a["reading"]["status"], "REVIEW_NEW_FAILURE_TYPES")
        self.assertIn("arrival|subpatterns", a["reading"]["new_in_candidate"])

    def test_A_spurious_correction_events_do_not_confirm(self):
        a = self.ok(self.hub("A"), {"main": "corrections_event"})
        self.assertFalse(a["reading"]["criteria"]["correction_usable_exact_not_lower_than_3_64"])
        self.assertEqual(a["reading"]["status"], "DOES_NOT_CONFIRM")

    def test_A_truncation_is_scored(self):
        a = self.ok(self.hub("A"), {"main": "truncate"})
        self.assertEqual(a["by_arm_act"]["KEEP_EVT|arrival"]["truncated"], 1)
        self.assertEqual(a["reading"]["status"], "REVIEW_NEW_FAILURE_TYPES")

    def test_A_main_failure_is_incomplete(self):
        hub = self.hub("A")
        self.assertEqual(self.run_hub(hub, {"main": "fail"}), 1)
        self.assert_failed(hub)

    def test_A_slow_smoke_stops_before_main(self):
        hub = self.hub("A")
        self.assertEqual(self.run_hub(hub, {"smoke": "slow"}), 1)
        self.assert_failed(hub)
        self.assertFalse((hub / "stages/main").exists())
        self.assertIn("7.5-hour", (hub / "driver.log").read_text())

    def test_A_frozen_tamper_blocks_workers(self):
        hub = self.hub("A")
        with (hub / "data/main-calls.jsonl").open("a") as out:
            out.write("\n")
        self.assertEqual(self.run_hub(hub), 1)
        self.assertFalse((hub / "stages").exists())

    # ---- study B: narrowed sentence screen
    def test_B_better_warrants(self):
        a = self.ok(self.hub("B"), {"main": "better"})
        self.assertEqual(a["reading"]["status"], "WARRANTS_CONFIRMATION_DESIGN")
        self.assertIn("arrival|TRANSITION|KEEP_EVTR-KEEP_EVT", a["contrasts"])

    def test_B_wrong_bindings_beyond_pooled_tolerance(self):
        a = self.ok(self.hub("B"), {"main": "wrongbind5"})
        self.assertEqual(a["reading"]["accepted_wrong_bindings"]["KEEP_EVTR"], 5)
        self.assertFalse(a["reading"]["criteria"]["wrong_bindings_within_pooled_tolerance"])
        self.assertEqual(a["reading"]["status"], "DOES_NOT_WARRANT")

    def test_B_transition_below_keep_evt_does_not_warrant(self):
        a = self.ok(self.hub("B"), {"main": "evtr_transition3"})
        crit = a["reading"]["criteria"]
        self.assertTrue(crit["transition_exact_not_lower_than_3_points"])
        self.assertFalse(crit["transition_exact_not_below_keep_evt"])
        self.assertEqual(a["reading"]["status"], "DOES_NOT_WARRANT")

    def test_B_missing_record_makes_analysis_incomplete(self):
        hub = self.hub("B")
        self.ok(hub)
        next((hub / "stages/main/calls").glob("*.json")).unlink()
        r = SA.write_artifacts(hub)
        self.assertEqual(r["status"], "INCOMPLETE")
        self.assertEqual(r["reading"]["status"], "NOT_EVALUATED")

    # ---- study C: descriptive wrong-binding panel
    def test_C_descriptive_rates(self):
        hub = self.hub("C")
        a = self.ok(hub, {"main": "wrongbind5"})
        rd = a["reading"]
        self.assertEqual(rd["status"], "DESCRIPTIVE_COMPLETE")
        self.assertEqual(sum(v["wrong_bindings"] for v in rd["wrong_binding_rates"].values()), 5)
        self.assertEqual(sum(v["post_guard"] for v in rd["wrong_binding_rates"].values()), 0)
        self.assertEqual(rd["wrong_binding_rates"]["KEEP_CLAR"]["n"], 384)
        self.assertIn("Clopper-Pearson", (hub / "REPORT.md").read_text())
        sub = rd["wrong_binding_rates_by_subgroup"]
        self.assertEqual(set(sub), {"wording", "family"})
        self.assertEqual(sum(v["n"] for v in sub["wording"].values()), 1152)
        self.assertEqual(sum(v["wrong_bindings"] for v in sub["family"].values()), 5)
        self.assertTrue(all(len(v["cp95"]) == 2 and len(v["post_guard_cp95"]) == 2 for v in sub["wording"].values()))

    # ---- study D (V1.29.0): combined sentence screen
    def test_D_warrants_when_reception_dating_is_halved(self):
        hub = self.hub("D")
        a = self.ok(hub, {"main": "d_warrants"})
        rd = a["reading"]
        self.assertEqual(rd["reception_dated"], {"KEEP_CLAR": 0, "KEEP_EVT": 8, "KEEP_EVTT": 2})
        self.assertTrue(all(rd["criteria"].values()), rd["criteria"])
        self.assertEqual(rd["status"], "WARRANTS_CONFIRMATION_DESIGN")
        self.assertIn("arrival|RESULT|immediate|KEEP_EVTT-KEEP_EVT", a["contrasts"])
        self.assertIn("KEEP_EVTT|RESULT|delayed", a["wording_x_reception"])
        disc = a["reception_dated_descriptive"]["stems_discordant"]["KEEP_EVTT-KEEP_EVT"]
        self.assertGreater(disc["only_KEEP_EVT"], 0)
        report = (hub / "REPORT.md").read_text()
        self.assertIn("wording x reception", report)
        self.assertIn("Target-error floor", report)

    def test_D_equal_and_few_target_errors_are_insufficient(self):
        for mode in ("equal", "d_insufficient"):
            a = self.ok(self.hub("D"), {"main": mode})
            self.assertFalse(a["reading"]["target_error_floor_met"], mode)
            self.assertEqual(a["reading"]["status"], "INSUFFICIENT_TARGET_ERRORS", mode)

    def test_D_not_halved_does_not_warrant(self):
        a = self.ok(self.hub("D"), {"main": "d_not_halved"})
        self.assertTrue(a["reading"]["target_error_floor_met"])
        self.assertFalse(a["reading"]["criteria"]["reception_dated_halved_with_keep_evt_at_least_6"])
        self.assertEqual(a["reading"]["status"], "DOES_NOT_WARRANT")

    def test_D_state_only_on_immediate_result_does_not_warrant(self):
        a = self.ok(self.hub("D"), {"main": "d_state_only"})
        crit = a["reading"]["criteria"]
        self.assertFalse(crit["state_only_within_2"])
        self.assertFalse(crit["immediate_result_exact_not_lower_than_3_points"])
        self.assertTrue(crit["arrival_exact_not_lower"])
        self.assertEqual(a["reading"]["status"], "DOES_NOT_WARRANT")

    def test_D_wrong_bindings_beyond_tolerance_and_guard_holds(self):
        a = self.ok(self.hub("D"), {"main": "d_wrongbind"})
        rd = a["reading"]
        self.assertGreaterEqual(rd["accepted_wrong_bindings"]["KEEP_EVTT"], 5)
        self.assertEqual(rd["post_guard_wrong_bindings"]["KEEP_EVTT"], 0)
        self.assertFalse(rd["criteria"]["wrong_bindings_within_4"])
        self.assertEqual(rd["status"], "DOES_NOT_WARRANT")

    def test_D_new_failure_type_flags_review(self):
        a = self.ok(self.hub("D"), {"main": "d_new_type"})
        self.assertTrue(all(a["reading"]["criteria"].values()), a["reading"]["criteria"])
        self.assertIn("arrival|subpatterns", a["reading"]["new_in_candidate"])
        self.assertEqual(a["reading"]["status"], "REVIEW_NEW_FAILURE_TYPES")

    def test_D_other_failure_precedes_insufficient(self):
        a = self.ok(self.hub("D"), {"main": "stateatrecv"})   # KEEP_EVTT reception-dated on 2, KEEP_EVT on 0
        self.assertFalse(a["reading"]["target_error_floor_met"])
        self.assertFalse(a["reading"]["criteria"]["arrival_exact_not_lower"])
        self.assertEqual(a["reading"]["status"], "DOES_NOT_WARRANT")

    def test_D_freeze_requires_the_suite_hubs_in_the_history_check(self):
        self.assertTrue(set(SP.SUITE_HUBS) <= SP.REQUIRED_HISTORICAL_HUBS_BY_KEY["D"])
        self.assertTrue(set(P0.SUITE_HUBS) <= P0.REQUIRED_HUBS_D)
        self.assertEqual(len(P0.REQUIRED_HUBS_D), 13)
        self.assertEqual(SP.REQUIRED_HISTORICAL_HUBS_BY_KEY["A"], SP.REQUIRED_HISTORICAL_HUBS)

    def _p0(self, hub):
        return P0.validate(hub, S.default_config("D"), release_source_hash(ROOT))

    def _p0_after(self, edit):
        hub = Path(self.temp.name) / f"p0-{self.serial}"
        type(self).serial += 1
        shutil.copytree(self.bases["D"], hub)
        edit(hub)
        return self._p0(hub)

    def test_D_phase0_fixture_evidence_passes(self):
        self.assertEqual(self._p0(self.bases["D"]), [])
        self.assertEqual(P0.validate(self.bases["A"], S.default_config("A"), "x"), [])   # A-C not checked here

    def test_D_phase0_rejects_failed_or_stale_full_tests(self):
        def change(**kw):
            def edit(h):
                f = json.loads((h / "phase0/FULL-TESTS.json").read_text())
                dump(h / "phase0/FULL-TESTS.json", dict(f, **kw))
            return edit
        for kw in ({"success": False, "failures": 1}, {"source_sha256": "0" * 64}, {"ml_dependencies_available": False},
                   {"skipped": 2, "passed": 3}, {"tests_run": 0, "passed": 0}, {"errors": 1}):
            self.assertTrue(any(p.startswith("FULL-TESTS") for p in self._p0_after(change(**kw))), kw)

    def test_D_phase0_rejects_failed_or_unbound_token_check(self):
        def change(fn):
            def edit(h):
                t = json.loads((h / "phase0/TOKENS.json").read_text())
                fn(t)
                dump(h / "phase0/TOKENS.json", t)
            return edit
        cases = {"failed": lambda t: t.update(all_pass=False, calls_checked=0),
                 "missing cell": lambda t: t["by_stage_arm"].pop("main|KEEP_EVTT"),
                 "over limit": lambda t: t["by_stage_arm"]["main|KEEP_EVT"].update(max=2049),
                 "wrong count": lambda t: t["by_stage_arm"]["smoke|KEEP_CLAR"].update(count=11),
                 "unbound": lambda t: t["calls_sha256"].update(main="0" * 64)}
        for name, fn in cases.items():
            self.assertTrue(any(p.startswith("TOKENS") for p in self._p0_after(change(fn))), name)

    def test_D_phase0_rejects_contradictory_validation_summary(self):
        def edit(h):
            v = json.loads((h / "phase0/VALIDATION.json").read_text())
            v["components"]["full_test_suite"]["tests_run"] = 999
            dump(h / "phase0/VALIDATION.json", v)
        self.assertTrue(any(p.startswith("VALIDATION") for p in self._p0_after(edit)))

    def test_D_phase0_rejects_each_omitted_nested_hub_file(self):
        for hubname in P0.SUITE_HUBS:
            for rel in P0.PANEL_FILES:
                def drop_inventory(h, hubname=hubname, rel=rel):
                    x = json.loads((h / "phase0/HISTORICAL.json").read_text())
                    x["inventory"] = [e for e in x["inventory"] if (e["hub"], e["file"]) != (hubname, rel)]
                    dump(h / "phase0/HISTORICAL.json", x)

                def drop_input(h, hubname=hubname, rel=rel):
                    c = json.loads((h / "data/COMMITMENT.json").read_text())
                    c["historical_checked"]["files"] = [f for f in c["historical_checked"]["files"]
                                                        if not f.endswith(f"{hubname}/{rel}")]
                    dump(h / "data/COMMITMENT.json", c)
                self.assertTrue(any(p.startswith("HISTORICAL") for p in self._p0_after(drop_inventory)), (hubname, rel))
                self.assertTrue(any(p.startswith("COMMITMENT") for p in self._p0_after(drop_input)), (hubname, rel))

    def test_D_phase0_rejects_malformed_history_and_wrong_hashes(self):
        bad = self.history / P0.SUITE_HUBS[0] / "data/public/smoke-targets.jsonl"
        good = bad.read_text()
        try:
            bad.write_text(good + "{not json\n")
            self.assertTrue(any("malformed" in p for p in self._p0(self.bases["D"])))
            with self.assertRaises(ValueError):
                P0.build_historical(self.bases["D"], self.history)
            bad.write_text(good + "[1, 2]\n")
            self.assertTrue(any("malformed" in p for p in self._p0(self.bases["D"])))
        finally:
            bad.write_text(good)
        self.assertEqual(self._p0(self.bases["D"]), [])

        def rehash(h):
            x = json.loads((h / "phase0/HISTORICAL.json").read_text())
            x["inventory"][0]["sha256"] = "0" * 64
            dump(h / "phase0/HISTORICAL.json", x)
        self.assertTrue(any("differs from the file" in p for p in self._p0_after(rehash)))

    def test_D_phase0_rejects_overlap_with_history(self):
        def overlap(h):   # put one of this panel's prompts into a historical file
            prompt = json.loads((h / "data/public/main-targets.jsonl").read_text().splitlines()[0])["base_prompt"]
            path = self.history / P0.SUITE_HUBS[1] / "data/public/main-targets.jsonl"
            self._saved = (path, path.read_text())
            path.write_text(self._saved[1] + json.dumps({"base_prompt": prompt}) + "\n")
        try:
            self.assertTrue(any("overlaps" in p for p in self._p0_after(overlap)))
        finally:
            self._saved[0].write_text(self._saved[1])

    def test_D_phase0_rejects_contradictory_historical_summaries(self):   # Codex recheck RC1
        def change(fn):
            def edit(h):
                x = json.loads((h / "phase0/HISTORICAL.json").read_text())
                fn(x)
                dump(h / "phase0/HISTORICAL.json", x)
            return edit
        cases = {"global counts": lambda x: x.update(unique_historical_base_prompts=0, unique_historical_world_seeds=0),
                 "overlap summary": lambda x: x["overlap_with_historical"].update(historical_prompts=1),
                 "declared hubs empty": lambda x: x.update(required_hubs=[]),
                 "overlap missing": lambda x: x.pop("overlap_with_historical")}
        for name, fn in cases.items():
            self.assertTrue(any(p.startswith("HISTORICAL") for p in self._p0_after(change(fn))), name)
            hub = self.hub("D", edit=change(fn))
            self.assertTrue(SCERT.is_freeze_fault(SCERT.certify(hub, during_driver=True)), name)

    def test_D_phase0_rejects_contradictory_validation_components(self):   # Codex recheck RC2
        def change(part, **kw):
            def edit(h):
                v = json.loads((h / "phase0/VALIDATION.json").read_text())
                v["components"][part].update(kw)
                dump(h / "phase0/VALIDATION.json", v)
            return edit
        cases = [("full_test_suite", {"success": False, "failures": 1, "errors": 1}),
                 ("full_test_suite", {"skipped": 3}), ("full_test_suite", {"status": "failed"}),
                 ("tokens", {"all_pass": False}), ("tokens", {"limit": 4096}), ("tokens", {"status": "failed"})]
        for part, kw in cases:
            self.assertTrue(any(p.startswith("VALIDATION") for p in self._p0_after(change(part, **kw))), (part, kw))
            hub = self.hub("D", edit=change(part, **kw))
            self.assertTrue(SCERT.is_freeze_fault(SCERT.certify(hub, during_driver=True)), (part, kw))
        ok = change("tokens", limit=2048, all_pass=True)   # agreeing optional fields are accepted
        self.assertEqual(self._p0_after(ok), [])

    def test_D_invalid_phase0_is_a_freeze_fault_in_certification(self):
        def fail_tests(h):
            f = json.loads((h / "phase0/FULL-TESTS.json").read_text())
            dump(h / "phase0/FULL-TESTS.json", dict(f, success=False, failures=1))
        hub = self.hub("D", edit=fail_tests)
        problems = SCERT.certify(hub, during_driver=True)
        self.assertTrue(SCERT.is_freeze_fault(problems), problems[:5])
        self.assertNotEqual(self.run_hub(hub, {"main": "d_warrants"}), 0)
        self.assertFalse((hub / "DRIVER-SUCCESS.json").exists())

    # ---- policy and chain
    def test_guard_policies(self):
        for key, total in (("A", 1560), ("B", 1476), ("C", 1164), ("D", 1656)):
            self.assertEqual(SG.policy(key)["total_attempts"], total)
            self.assertEqual(SG.policy(key)["ceiling_s"], 8 * 3600)
        hub = self.hub("A")
        start = int(time.time())
        dump(hub / "config/DEADLINE.json", {"driver_start_epoch": start, "deadline_epoch": start + 28800})
        for i in range(24):
            dump(hub / f"stages/smoke/calls/{i}.json", {"status": "ok", "seconds": 13.4})
        r = SG.check(hub, "main")
        self.assertTrue(r["ok"], r["problems"])
        self.assertLess(r["projected_total_s"], 27000)
        self.assertLess(sum(SC.estimate_s(self.bases[k]) for k in SC.KEYS), SC.CHAIN_CEILING_S)
        hub = self.hub("D")   # study D at the suite's slowest observed smoke mean stays inside the planning limit
        dump(hub / "config/DEADLINE.json", {"driver_start_epoch": start - 600, "deadline_epoch": start + 28200})
        for i in range(36):
            dump(hub / f"stages/smoke/calls/{i}.json", {"status": "ok", "seconds": 13.0})
        r = SG.check(hub, "main")
        self.assertTrue(r["ok"], r["problems"])
        self.assertLess(r["projected_total_s"], 25000)
        for i in range(36):   # and a 16 s/call smoke stops before main
            dump(hub / f"stages/smoke/calls/{i}.json", {"status": "ok", "seconds": 16.0})
        self.assertFalse(SG.check(hub, "main")["ok"])

    # ---- completion certification (Codex F1)
    def completed(self, key="A", mode="better"):
        if not hasattr(type(self), "_done"):
            type(self)._done = {}
        if (key, mode) not in self._done:
            hub = self.hub(key)
            self.ok(hub, {"main": mode})
            self._done[(key, mode)] = hub
        type(self).serial += 1
        copy_ = Path(self.temp.name) / f"m{self.serial}"
        shutil.copytree(self._done[(key, mode)], copy_)
        return copy_

    def assert_incomplete_after(self, mutate):
        hub = self.completed()
        mutate(hub)
        r = SA.write_artifacts(hub)
        self.assertEqual(r["status"], "INCOMPLETE", r["infrastructure"]["problems"][:3])
        self.assertEqual(r["reading"]["status"], "NOT_EVALUATED")
        self.assertIn("INCOMPLETE", (hub / "RUN-STATUS.md").read_text())
        self.assertFalse((hub / "analysis/dev/scored.jsonl").exists())
        return r

    def test_completed_hub_recertifies_cleanly(self):
        hub = self.completed()
        self.assertEqual(SCERT.certify(hub), [])
        self.assertEqual(SA.write_artifacts(hub)["status"], "COMPLETE")

    def test_missing_or_fake_stage_provenance_is_incomplete(self):
        for rel in ("LOCK.json", "LOAD.json", "config.json", "END.json"):
            self.assert_incomplete_after(lambda h, rel=rel: (h / "stages/main" / rel).unlink())
        self.assert_incomplete_after(lambda h: dump(h / "stages/main/LOCK.json", dict(
            json.loads((h / "stages/main/LOCK.json").read_text()), fake=True)))
        self.assert_incomplete_after(lambda h: [p.unlink() for p in (h / "stages/main").glob("start-*.json")])

    def test_extra_stage_and_late_output_are_incomplete(self):
        def extra(h):
            (h / "stages/extra/calls").mkdir(parents=True)
            shutil.copy(next((h / "stages/main/calls").glob("*.json")), h / "stages/extra/calls/x.json")
        self.assert_incomplete_after(extra)

        def late(h):
            p = next((h / "stages/main/calls").glob("*.json"))
            dump(p, dict(json.loads(p.read_text()), finished_at="2099-01-01T00:00:00"))
        self.assert_incomplete_after(late)
        self.assert_incomplete_after(lambda h: (h / "config/DEADLINE.json").unlink())

        def extended(h):
            d = json.loads((h / "config/DEADLINE.json").read_text())
            dump(h / "config/DEADLINE.json", dict(d, deadline_epoch=d["driver_start_epoch"] + 80 * 3600))
        self.assert_incomplete_after(extended)

    def test_invalid_transport_fields_are_incomplete(self):
        for field, value in (("raw", None), ("raw", {"x": 1}), ("input_tokens", 99999), ("output_tokens", True),
                             ("seconds", float("inf"))):
            def mutate(h, field=field, value=value):
                p = next((h / "stages/main/calls").glob("*.json"))
                r = json.loads(p.read_text())
                r[field] = value
                p.write_text(json.dumps(r))
            self.assert_incomplete_after(mutate)

        def load_protocol(h):
            p = next((h / "stages/main/calls").glob("*.json"))
            r = json.loads(p.read_text())
            r["model"]["load"]["protocol"] = "OTHER"
            p.write_text(json.dumps(r))
        self.assert_incomplete_after(load_protocol)

    def test_incomplete_freeze_coverage_is_rejected(self):
        def empty(h):
            f = json.loads((h / "config/FROZEN-PROTOCOL.json").read_text())
            dump(h / "config/FROZEN-PROTOCOL.json", dict(f, design={}, config={}, data={}, phase0={}))
        self.assert_incomplete_after(empty)

        def unlisted(h):
            (h / "design/EXTRA.md").write_text("added after freeze\n")
        self.assert_incomplete_after(unlisted)

    def test_post_fault_reanalysis_stays_incomplete(self):
        hub = self.hub("A")

        def bad_stage_check(h):
            raise RuntimeError("synthetic post-collection fault")
        self.assertEqual(self.run_hub(hub, {"main": "better"}, stage_checker=bad_stage_check), 1)
        self.assert_failed(hub)
        r = SA.write_artifacts(hub)
        self.assertEqual(r["status"], "INCOMPLETE")
        self.assertIn("INCOMPLETE", (hub / "RUN-STATUS.md").read_text())

    def test_success_binding_detects_changed_records(self):
        hub = self.completed()
        p = next((hub / "stages/main/calls").glob("*.json"))
        r = json.loads(p.read_text())
        r["seconds"] = r["seconds"] + 1
        p.write_text(json.dumps(r))
        self.assertTrue(any("inventory" in x for x in SCERT.certify(hub)))
        self.assertEqual(SA.write_artifacts(hub)["status"], "INCOMPLETE")

    # ---- deadlines (Codex F2)
    def test_overlong_analyzer_hits_watchdog(self):
        hub = self.hub("A")

        def slow_analyzer(h):
            time.sleep(120)

        def ok_guard(h, stage):
            return {"ok": True, "problems": [], "remaining_s": 100}
        t0 = time.time()
        rc = self.run_hub(hub, {"main": "better"}, analyzer=slow_analyzer, guard=ok_guard, ceiling_s=75)
        self.assertEqual(rc, 1)
        self.assertLess(time.time() - t0, 100)
        self.assertTrue((hub / "runtime/DEADLINE-EXCEEDED.json").exists())
        self.assert_failed(hub)

    def test_guard_rejects_extended_deadline(self):
        hub = self.hub("A")
        start = int(time.time())
        dump(hub / "config/DEADLINE.json", {"driver_start_epoch": start, "deadline_epoch": start + 80 * 3600})
        for i in range(24):
            dump(hub / f"stages/smoke/calls/{i}.json", {"status": "ok", "seconds": 13.0})
        self.assertFalse(SG.check(hub, "main")["ok"])

    def test_chain_deadline_env_shortens_study_deadline(self):
        start = int(time.time())
        os.environ["DREAM_SUITE_CHAIN_DEADLINE_EPOCH"] = str(start + 1000)
        try:
            self.assertEqual(SR.effective_deadline(start, "A"), start + 1000)
        finally:
            del os.environ["DREAM_SUITE_CHAIN_DEADLINE_EPOCH"]
        self.assertEqual(SR.effective_deadline(start, "A"), start + 28800)

    def test_freeze_failure_anywhere_is_classified_as_freeze(self):
        hub = self.hub("A")

        def tamper_then_ok():
            (hub / "design/PROTOCOL.md").write_text("changed during the run\n")
            return {"fixture": True}
        self.assertEqual(self.run_hub(hub, gpu_probe=tamper_then_ok), 1)
        self.assertEqual(json.loads((hub / "DRIVER-FAILURE.json").read_text())["step"], "freeze")

    # ---- recheck regressions (Codex R1-R7)
    def test_R1_invalidation_survives_repeated_reanalysis(self):
        hub = self.completed()
        p = next((hub / "stages/main/calls").glob("*.json"))
        r = json.loads(p.read_text())
        r["raw"] = r["raw"] + " "
        p.write_text(json.dumps(r))
        for _ in range(3):
            self.assertEqual(SA.write_artifacts(hub)["status"], "INCOMPLETE")
        self.assertTrue((hub / "runtime/INVALIDATED.json").exists())
        self.assertTrue(SCERT.certify(hub))

    def test_R1_complete_outside_driver_requires_success_certificate(self):
        hub = self.completed()
        (hub / "DRIVER-SUCCESS.json").unlink()
        self.assertIn("no terminal success certificate", SCERT.certify(hub))

    def test_R2_analysis_artifacts_are_bound(self):
        for rel, action in (("analysis/dev/ANALYSIS.json", "corrupt"), ("analysis/dev/ANALYSIS.json", "delete"),
                            ("analysis/dev/scored.jsonl", "corrupt"), ("REPORT.md", "corrupt")):
            hub = self.completed()
            if action == "delete":
                (hub / rel).unlink()
            else:
                (hub / rel).write_text("{not json")
            self.assertTrue(SCERT.certify(hub), rel)
            self.assertEqual(SC.child_outcome(hub, 0)[0]["state"], "FAULT", rel)

    def test_R2_contradictory_success_fields(self):
        for field, value in (("finished", False), ("key", "B"), ("at", "2099-01-01T00:00:00-05:00"),
                             ("reading", "DOES_NOT_CONFIRM")):
            hub = self.completed()
            s = json.loads((hub / "DRIVER-SUCCESS.json").read_text())
            s[field] = value
            dump(hub / "DRIVER-SUCCESS.json", s)
            self.assertTrue(SCERT.certify(hub), field)
            self.assertEqual(SC.child_outcome(hub, 0)[0]["state"], "FAULT", field)

    def test_R2_record_changed_between_analysis_and_success(self):
        hub = self.hub("A")

        def analyzer_then_tamper(h):
            out = SR.default_analyze(h)
            p = next((h / "stages/main/calls").glob("*.json"))
            r = json.loads(p.read_text())
            r["seconds"] = r["seconds"] + 1
            p.write_text(json.dumps(r))
            return out
        self.assertEqual(self.run_hub(hub, {"main": "better"}, analyzer=analyzer_then_tamper), 1)
        self.assertFalse((hub / "DRIVER-SUCCESS.json").exists())

    def test_R3_corrupt_end_invalidates_complete_artifacts(self):
        hub = self.completed()
        (hub / "stages/main/END.json").write_text("{corrupt")
        r = SA.write_artifacts(hub)
        self.assertEqual(r["status"], "INCOMPLETE")
        self.assertFalse((hub / "DRIVER-SUCCESS.json").exists())
        self.assertFalse((hub / "analysis/dev/scored.jsonl").exists())
        self.assertEqual(json.loads((hub / "analysis/dev/ANALYSIS.json").read_text())["status"], "INCOMPLETE")
        self.assertIn("INCOMPLETE", (hub / "REPORT.md").read_text())

    def test_R3_damaged_panel_fails_closed(self):
        hub = self.completed()
        (hub / "config/PANEL.json").write_text("[]")
        self.assertEqual(SA.write_artifacts(hub)["status"], "INCOMPLETE")
        self.assertFalse((hub / "DRIVER-SUCCESS.json").exists())

    def test_R4_invalid_start_and_inconsistent_load(self):
        self.assert_incomplete_after(lambda h: next((h / "stages/main").glob("start-*.json")).write_text("not json"))

        def load(h, field, value):
            d = json.loads((h / "stages/main/LOAD.json").read_text())
            d[field] = value
            dump(h / "stages/main/LOAD.json", d)
        for field, value in (("dtype", "float32"), ("enable_thinking", True), ("decoding", "sampled")):
            self.assert_incomplete_after(lambda h, f=field, v=value: load(h, f, v))

        def second_start(h):
            src = next((h / "stages/main").glob("start-*.json"))
            shutil.copy(src, h / "stages/main/start-2.json")
        self.assert_incomplete_after(second_start)

    def test_R4_system_text_and_manifest_path_are_checked(self):
        def system(h):
            p = h / "data/main-calls.jsonl"
            rows = [json.loads(x) for x in p.read_text().splitlines()]
            rows[0]["system"] = rows[0]["system"] + " "
            rows[0]["system_sha256"] = hashlib.sha256(rows[0]["system"].encode()).hexdigest()
            p.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))
        r = self.assert_incomplete_after(system)
        hub = self.completed()
        old = SCERT.MANIFEST_PATH
        SCERT.MANIFEST_PATH = f"{LP.MODELS}/Qwen3-32B/model-manifest.json"
        try:
            self.assertTrue(any("manifest" in x for x in SCERT.certify(hub)))
        finally:
            SCERT.MANIFEST_PATH = old

    def test_R5_early_failure_analysis_is_bounded(self):
        hub = self.hub("A")
        (hub / "design/PROTOCOL.md").write_text("tampered before start\n")

        def slow(h):
            time.sleep(120)
        t0 = time.time()
        self.assertEqual(self.run_hub(hub, analyzer=slow, ceiling_s=70), 1)
        self.assertLess(time.time() - t0, 60)
        self.assertTrue((hub / "runtime/DEADLINE-EXCEEDED.json").exists())

    def test_R5_terminating_a_study_kills_its_separate_session_worker(self):
        hub = self.hub("A")
        proc = subprocess.Popen([sys.executable, "-B", str(ROOT / "tests/fixtures/su_fixture_drive.py"), "--hub",
                                 str(hub), "--manifest", SCERT.MANIFEST_PATH, "--main-mode", "hang"],
                                start_new_session=True, stdin=subprocess.DEVNULL)
        marker = hub / "runtime/WORKER-PGID.json"
        for _ in range(240):
            if marker.exists() and (hub / "stages/smoke/END.json").exists() and \
                    json.loads(marker.read_text())["pgid"] != getattr(self, "_smoke_pgid", None):
                if (hub / "stages/main").exists():
                    break
            time.sleep(0.5)
        pgid = json.loads(marker.read_text())["pgid"]
        SC.terminate_study(proc, hub, 30)
        time.sleep(1)
        with self.assertRaises(ProcessLookupError):
            os.killpg(pgid, 0)
        self.assertTrue((hub / "DRIVER-FAILURE.json").exists())

    def test_R6_stage_check_freeze_fault_is_freeze(self):
        hub = self.hub("A")

        def worker(h, stage, remaining):
            cmd = self.worker({"main": "better"})(h, stage, remaining)
            if stage == "main":
                return ["bash", "-c", " ".join(map(repr, cmd)) + f" && echo x >> {h}/design/PROTOCOL.md"]
            return cmd
        self.assertEqual(SR.drive(hub, worker=worker, gpu_probe=lambda: {"fixture": True}, notify=False), 1)
        self.assertEqual(json.loads((hub / "DRIVER-FAILURE.json").read_text())["step"], "freeze")

    def test_R7_invariant_violation_cannot_be_certified(self):
        real = SA.load_guard

        def leaky():
            mod = real()
            orig = mod.decide
            state = {"n": 0}

            def decide(*args):
                d = orig(*args)
                state["n"] += 1
                if state["n"] <= 50 and d["guard_pass"]:
                    d = dict(d, guard_pass=False, disposition="identity_mismatch")
                return d
            mod.decide = decide
            return mod
        SA.load_guard = leaky
        try:
            hub = self.hub("A")
            self.assertEqual(self.run_hub(hub, {"main": "better"}), 1)
        finally:
            SA.load_guard = real
        self.assertFalse((hub / "DRIVER-SUCCESS.json").exists())
        a = self.analysis(hub)
        self.assertEqual(a["status"], "INCOMPLETE")

    # ---- third-check regressions (Codex C1-C4)
    def test_C1_artifacts_changed_at_handoff_block_success(self):
        def scored(h):
            (h / "analysis/dev/scored.jsonl").write_text("not json")

        def report(h):
            (h / "REPORT.md").write_text("replaced")

        def reading(h):
            p = h / "analysis/dev/ANALYSIS.json"
            a = json.loads(p.read_text())
            a["reading"]["status"] = "DOES_NOT_CONFIRM"
            p.write_text(json.dumps(a))
        for mutate in (scored, report, reading):
            hub = self.hub("A")

            def analyzer(h, mutate=mutate):
                out = SR.default_analyze(h)
                mutate(h)
                return out
            self.assertEqual(self.run_hub(hub, {"main": "better"}, analyzer=analyzer), 1)
            self.assertFalse((hub / "DRIVER-SUCCESS.json").exists())

    def test_C2_render_failure_blocks_success(self):
        real = SA.render

        def broken(result):
            if result["status"] == "COMPLETE":
                raise RuntimeError("synthetic renderer failure")
            return real(result)
        SA.render = broken
        try:
            hub = self.hub("A")
            self.assertEqual(self.run_hub(hub, {"main": "better"}), 1)
        finally:
            SA.render = real
        self.assertFalse((hub / "DRIVER-SUCCESS.json").exists())
        self.assertEqual(self.analysis(hub)["status"], "INCOMPLETE")
        self.assertTrue(SCERT.certify(hub))

    def test_C3_nested_load_and_response_after_end(self):
        for field, value in (("load_in_4bit", False), ("bnb_4bit_quant_type", "fp4"),
                             ("non_quantized_dtype", "float32")):
            def mutate(h, field=field, value=value):
                for p in [h / "stages/main/LOAD.json"] + sorted((h / "stages/main/calls").glob("*.json")):
                    d = json.loads(p.read_text())
                    target = d if p.name == "LOAD.json" else d["model"]
                    target["load"]["quantization"][field] = value
                    p.write_text(json.dumps(d))
            self.assert_incomplete_after(mutate)

        def late(h):
            p = next((h / "stages/main/calls").glob("*.json"))
            r = json.loads(p.read_text())
            end = SCERT.epoch(json.loads((h / "stages/main/END.json").read_text())["at"])
            r["finished_at"] = datetime.fromtimestamp(end + 3600, ZoneInfo("America/New_York")).strftime(
                "%Y-%m-%dT%H:%M:%S")
            p.write_text(json.dumps(r))
        self.assert_incomplete_after(late)

    def test_C4_term_resistant_descendant_is_killed(self):
        hub = self.hub("A")
        (hub / "runtime").mkdir(exist_ok=True)
        rc = SR.execute(["bash", "-c", "(trap '' TERM; exec sleep 300) & sleep 300"], hub, 1)
        self.assertEqual(rc, 124)
        pgid = json.loads((hub / "runtime/WORKER-PGID.json").read_text())["pgid"]
        time.sleep(0.5)
        with self.assertRaises(ProcessLookupError):
            os.killpg(pgid, 0)

    def test_C4_slow_failure_notification_is_bounded(self):
        hub = self.hub("A")
        (hub / "design/PROTOCOL.md").write_text("tampered before start\n")
        real = SR.notify_once
        SR.notify_once = lambda h, status: time.sleep(120)
        try:
            t0 = time.time()
            SR.drive(hub, worker=self.worker(), gpu_probe=lambda: {"fixture": True}, notify=True, ceiling_s=70)
            self.assertLess(time.time() - t0, 70)
        finally:
            SR.notify_once = real

    def test_C4_slow_chain_validation_is_bounded(self):
        chain, hubs = self.make_chain()
        real = SC.validate_chain
        SC.validate_chain = lambda d: (time.sleep(60), real(d))[1]
        try:
            t0 = time.time()
            st = SC.run_chain(chain, command=self.child(), ceiling_s=152)
            self.assertLess(time.time() - t0, 30)
            self.assertEqual(st["state"], "CHAIN_DEADLINE")
        finally:
            SC.validate_chain = real

    # ---- V1.28.0: Codex post-run code review C4-N / C4-K (each reproduces the failing probe, then real processes)
    def test_C4N_notice_helper_propagates_the_cutoff(self):
        import signal as sg
        logged = []
        old = sg.signal(sg.SIGALRM, SR._alarm)
        real_notify, real_log = SR.notify_once, SR.log
        SR.notify_once = lambda h, status: time.sleep(0.5)
        SR.log = lambda *a: (logged.append(a), time.sleep(0.5))
        try:
            t0 = time.monotonic()
            sg.setitimer(sg.ITIMER_REAL, 0.05)
            with self.assertRaises(SR.DeadlineExceeded):
                SR._notify_incomplete(Path(self.temp.name) / "no-hub", True)
            self.assertLess(time.monotonic() - t0, 0.4)
            self.assertEqual(logged, [])   # no unsupervised write after the cutoff
        finally:
            sg.setitimer(sg.ITIMER_REAL, 0)
            sg.signal(sg.SIGALRM, old)
            SR.notify_once, SR.log = real_notify, real_log

    def test_C4N_notice_helper_still_records_ordinary_failures(self):
        logged = []
        real_notify, real_log = SR.notify_once, SR.log
        SR.notify_once = lambda h, status: (_ for _ in ()).throw(OSError("disk"))
        SR.log = lambda *a: logged.append(a)
        try:
            SR._notify_incomplete(Path(self.temp.name) / "no-hub", True)
            self.assertEqual(len(logged), 1)
        finally:
            SR.notify_once, SR.log = real_notify, real_log

    def test_C4N_drive_stops_at_cleanup_cutoff_during_failure_notice(self):
        hub = self.hub("A")
        (hub / "design/PROTOCOL.md").write_text("tampered before start\n")   # fail() -> slow analyzer

        def slow(h):
            time.sleep(120)
        real_notify, real_cut = SR.notify_once, SR.CLEANUP_CUTOFF_S
        SR.notify_once = lambda h, status: time.sleep(120)
        SR.CLEANUP_CUTOFF_S = 3
        try:
            t0 = time.time()
            # ceiling 70 s -> study alarm at 10 s during the slow analyzer, then a 3 s cleanup cutoff in the notice
            rc = SR.drive(hub, worker=self.worker(), gpu_probe=lambda: {"fixture": True}, analyzer=slow,
                          notify=True, ceiling_s=70)
            elapsed = time.time() - t0
        finally:
            SR.notify_once, SR.CLEANUP_CUTOFF_S = real_notify, real_cut
        self.assertEqual(rc, 1)
        self.assertLess(elapsed, 30)
        self.assertTrue((hub / "DRIVER-FAILURE.json").exists())
        self.assertNotIn("notice failed", (hub / "driver.log").read_text())
        import signal as sg
        self.assertEqual(sg.getitimer(sg.ITIMER_REAL)[0], 0)

    def test_C4N_cutoff_during_success_notice_keeps_certified_success(self):
        hub = self.hub("A")
        import signal as sg
        real_notify = SR.notify_once

        def cut(h, status):
            sg.setitimer(sg.ITIMER_REAL, 0.05)
            time.sleep(1)
        SR.notify_once = cut
        try:
            rc = SR.drive(hub, worker=self.worker({"main": "better"}), gpu_probe=lambda: {"fixture": True},
                          notify=True)
        finally:
            SR.notify_once = real_notify
        self.assertEqual(rc, 0)
        self.assertTrue((hub / "DRIVER-SUCCESS.json").exists())
        self.assertFalse((hub / "DRIVER-FAILURE.json").exists())
        self.assertEqual(SCERT.certify(hub), [])

    def test_C4K_driver_group_kill_cannot_be_preempted(self):
        import signal as sg
        sent = []

        class SlowLeader:
            pid = 999999999

            def wait(self, timeout):
                time.sleep(min(timeout, 0.3))
                raise subprocess.TimeoutExpired("fake", timeout)
        old = sg.signal(sg.SIGALRM, SR._alarm)
        real = SR.os.killpg
        SR.os.killpg = lambda pgid, sig: sent.append(sig)
        try:
            sg.setitimer(sg.ITIMER_REAL, 0.02)
            with self.assertRaises(SR.DeadlineExceeded):   # delivered after the mask is restored
                SR._kill_group(SlowLeader())
        finally:
            sg.setitimer(sg.ITIMER_REAL, 0)
            sg.signal(sg.SIGALRM, old)
            SR.os.killpg = real
        self.assertEqual(sent, [sg.SIGTERM, sg.SIGKILL])

    def test_C4K_chain_cleanup_cutoff_cannot_preempt_kill(self):
        import signal as sg
        sent = []

        class SlowLeader:
            pid = 999999999

            def poll(self):
                return None

            def wait(self, timeout):
                time.sleep(min(timeout, 0.3))
                raise subprocess.TimeoutExpired("fake", timeout)
        hub = Path(self.temp.name) / "fake-hub"
        running = {"worker_pgid": 999999998}
        old = sg.signal(sg.SIGALRM, SC._chain_alarm)
        real_kill, real_wait = SC._killpg, SC.WORKER_TERM_WAIT_S
        SC._killpg = lambda pgid, sig: sent.append((pgid, sig))
        SC.WORKER_TERM_WAIT_S = 0.05
        try:
            sg.setitimer(sg.ITIMER_REAL, 0.02)
            with self.assertRaises(SC.ChainDeadline):
                SC.terminate_study(SlowLeader(), hub, 60, running)
            self.assertTrue(running["cleaned"])
        finally:
            sg.setitimer(sg.ITIMER_REAL, 0)
            sg.signal(sg.SIGALRM, old)
            SC._killpg, SC.WORKER_TERM_WAIT_S = real_kill, real_wait
        self.assertEqual(sent, [(999999999, sg.SIGTERM), (999999999, sg.SIGKILL),
                                (999999998, sg.SIGTERM), (999999998, sg.SIGKILL)])

    def test_C4K_kill_sections_hold_the_cutoff_with_other_threads_running(self):
        # A process-directed SIGALRM may be received by any thread; the critical section must still hold.
        import signal as sg
        import threading
        stop = threading.Event()
        helper = threading.Thread(target=stop.wait, args=(5,), daemon=True)
        helper.start()
        try:
            self.test_C4K_driver_group_kill_cannot_be_preempted()
            self.test_C4K_chain_cleanup_cutoff_cannot_preempt_kill()
        finally:
            stop.set()
            helper.join()
        self.assertEqual((SR._CRITICAL["depth"], SR._CRITICAL["pending"]), (0, None))
        self.assertEqual((SC._CRITICAL["depth"], SC._CRITICAL["pending"]), (0, None))
        self.assertEqual(sg.getitimer(sg.ITIMER_REAL)[0], 0)

    def test_C4K_term_resistant_child_is_killed_at_chain_deadline(self):
        chain, hubs = self.make_chain()
        pidfile = Path(self.temp.name) / f"resistant{self.serial}.pid"
        real = SC.TERM_WAIT_MAX_S
        SC.TERM_WAIT_MAX_S = 5
        try:
            t0 = time.time()
            st = SC.run_chain(chain, command=lambda hub: ["bash", "-c", f"echo $$ > {pidfile}; trap '' TERM; "
                                                                      "sleep 300 & wait; sleep 300"],
                              ceiling_s=152, estimate=lambda hub: 1)
            elapsed = time.time() - t0
        finally:
            SC.TERM_WAIT_MAX_S = real
        pgid = int(pidfile.read_text())
        time.sleep(0.5)
        with self.assertRaises(ProcessLookupError):
            os.killpg(pgid, 0)
        self.assertLess(elapsed, 40)
        self.assertTrue(st.get("state") == "CHAIN_DEADLINE" or
                        [e["state"] for e in st["studies"]][:1] == ["KILLED_AT_CHAIN_DEADLINE"], st)

    # ---- V1.28.0: Codex review of the first fix, R1-R5
    @staticmethod
    def _sleeper_group():
        """A harmless CPU process in its own session (stands in for a worker group)."""
        p = subprocess.Popen(["sleep", "300"], start_new_session=True, stdin=subprocess.DEVNULL)
        return p

    def assert_group_gone(self, pgid):
        for _ in range(50):
            try:
                os.killpg(pgid, 0)
            except ProcessLookupError:
                return
            time.sleep(0.1)
        os.killpg(pgid, 9)
        self.fail(f"process group {pgid} still alive")

    def test_V128R1_terminate_study_does_no_file_io(self):
        sleeper = self._sleeper_group()
        done = subprocess.Popen(["true"])
        done.wait()
        real_read = Path.read_text

        def no_io(self_path, *a, **k):
            raise AssertionError(f"file read inside the kill section: {self_path}")
        Path.read_text = no_io
        try:
            running = {"worker_pgid": sleeper.pid}
            SC.terminate_study(done, Path(self.temp.name) / "no-hub", 5, running)
        finally:
            Path.read_text = real_read
        sleeper.wait(timeout=10)
        self.assert_group_gone(sleeper.pid)
        self.assertTrue(running["cleaned"])

    def test_V128R1_chain_caches_the_worker_pgid_while_waiting(self):
        hub = Path(self.temp.name) / f"cache-hub{self.serial}"
        dump(hub / "runtime/WORKER-PGID.json", {"pgid": 424242})
        proc = subprocess.Popen(["sleep", "3"])
        running = {}
        real = SC.PGID_POLL_S
        SC.PGID_POLL_S = 0.5
        try:
            rc = SC._wait_caching_worker(proc, hub, running, time.monotonic() + 30)
        finally:
            SC.PGID_POLL_S = real
        self.assertEqual((rc, running.get("worker_pgid")), (0, 424242))
        proc2 = subprocess.Popen(["sleep", "30"])
        try:
            with self.assertRaises(subprocess.TimeoutExpired):
                SC._wait_caching_worker(proc2, hub, {}, time.monotonic() + 0.3)
        finally:
            proc2.kill()
            proc2.wait()

    def _chain_with_fake_run(self, populate):
        chain, hubs = self.make_chain()
        real = SC._run

        def fake(chain_dir, command, start, mono_end, chain_deadline, estimate, running):
            populate(running, hubs[0])
            raise SC.ChainDeadline("injected deadline")
        SC._run = fake
        try:
            return SC.run_chain(chain, command=self.child()), hubs
        finally:
            SC._run = real

    def test_V128R3_deadline_cleans_groups_even_when_the_leader_has_exited(self):
        sleeper = self._sleeper_group()
        exited = subprocess.Popen(["true"])
        exited.wait()
        st, _ = self._chain_with_fake_run(
            lambda running, hub: running.update(proc=exited, hub=hub, worker_pgid=sleeper.pid, cleaned=False))
        sleeper.wait(timeout=10)
        self.assert_group_gone(sleeper.pid)
        self.assertEqual(st["state"], "CHAIN_DEADLINE")

    def test_V128R1_R5_late_registered_worker_is_killed_after_the_main_kill(self):
        sleeper = self._sleeper_group()
        exited = subprocess.Popen(["true"])
        exited.wait()

        def populate(running, hub):
            dump(hub / "runtime/WORKER-PGID.json", {"pgid": sleeper.pid})   # registered after the last poll
            running.update(proc=exited, hub=hub, worker_pgid=None, cleaned=False)
        st, _ = self._chain_with_fake_run(populate)
        sleeper.wait(timeout=10)
        self.assert_group_gone(sleeper.pid)
        self.assertEqual(st.get("late_worker_group_killed"), sleeper.pid)

    def test_V128R3_cleanup_is_not_repeated_after_a_held_cutoff(self):
        calls = []
        real = SC.terminate_study
        SC.terminate_study = lambda *a, **k: calls.append(a)
        try:
            exited = subprocess.Popen(["true"])
            exited.wait()
            self._chain_with_fake_run(
                lambda running, hub: running.update(proc=exited, hub=hub, worker_pgid=None, cleaned=True))
        finally:
            SC.terminate_study = real
        self.assertEqual(calls, [])

    def test_V128R2_sigterm_to_the_chain_kills_both_groups_and_records_termination(self):
        import signal as sg
        import threading
        chain, hubs = self.make_chain()
        pidfile = Path(self.temp.name) / f"term{self.serial}.pid"
        real = SC.TERM_WAIT_MAX_S
        SC.TERM_WAIT_MAX_S = 3
        timers = [threading.Timer(2.0, os.kill, (os.getpid(), sg.SIGTERM)),
                  threading.Timer(3.5, os.kill, (os.getpid(), sg.SIGTERM))]   # second TERM during the TERM wait
        for t in timers:
            t.start()
        try:
            t0 = time.time()
            st = SC.run_chain(chain, command=lambda hub: ["bash", "-c", f"echo $$ > {pidfile}; trap '' TERM INT; "
                                                                      "sleep 300 & wait; sleep 300"],
                              estimate=lambda hub: 1)
            elapsed = time.time() - t0
        finally:
            for t in timers:
                t.cancel()
            SC.TERM_WAIT_MAX_S = real
        self.assert_group_gone(int(pidfile.read_text()))
        self.assertLess(elapsed, 30)
        self.assertEqual(st["state"], "CHAIN_TERMINATED", st)
        self.assertIs(sg.getsignal(sg.SIGTERM), sg.SIG_DFL)   # handlers restored
        self.assertEqual((SC._CRITICAL["depth"], SC._CRITICAL["pending"]), (0, None))

    def test_V128R4_cutoff_right_after_success_commit_keeps_the_success(self):
        hub = self.hub("A")
        real = SR.atomic_json

        def commit_then_cut(path, value):
            real(path, value)
            if Path(path).name == "DRIVER-SUCCESS.json":
                raise SR.DeadlineExceeded("injected cutoff after os.replace")
        SR.atomic_json = commit_then_cut
        try:
            rc = SR.drive(hub, worker=self.worker({"main": "better"}), gpu_probe=lambda: {"fixture": True},
                          notify=False)
        finally:
            SR.atomic_json = real
        self.assertEqual(rc, 0)
        self.assertTrue((hub / "DRIVER-SUCCESS.json").exists())
        self.assertFalse((hub / "DRIVER-FAILURE.json").exists())
        self.assertEqual(SCERT.certify(hub), [])
        self.assertEqual(SC.child_outcome(hub, rc)[0]["state"], "COMPLETE")

    def test_V128R5_cutoff_during_worker_registration_kills_the_worker(self):
        hub = Path(self.temp.name) / f"reg-hub{self.serial}"
        (hub / "runtime").mkdir(parents=True)
        seen = []
        real = SR.atomic_json

        def cut(path, value):
            if Path(path).name == "WORKER-PGID.json":
                seen.append(value["pgid"])
                raise SR.DeadlineExceeded("injected cutoff during registration")
            return real(path, value)
        SR.atomic_json = cut
        try:
            with self.assertRaises(SR.DeadlineExceeded):
                SR.execute(["bash", "-c", "trap '' TERM; sleep 300"], hub, 60)
        finally:
            SR.atomic_json = real
        self.assertEqual(len(seen), 1)
        self.assert_group_gone(seen[0])

    # ---- V1.28.0: Codex recheck RC1-RC3 and the in-container lifeline
    LIFELINE = str(ROOT / "scripts/su_lifeline.py")

    def _lifeline(self, body, stdin=subprocess.PIPE):
        return subprocess.Popen([sys.executable, "-B", self.LIFELINE, "--", "bash", "-c", body], stdin=stdin,
                                start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    @staticmethod
    def _pids(tag):
        r = subprocess.run(["pgrep", "-f", f"^sleep {tag}$"], capture_output=True, text=True)
        return [int(x) for x in r.stdout.split()]

    def _gone_within(self, tag, limit):
        t0 = time.time()
        while self._pids(tag) and time.time() - t0 < limit:
            time.sleep(0.2)
        left = self._pids(tag)
        for pid in left:
            os.kill(pid, 9)
        return not left

    def test_V128L_lifeline_close_kills_a_term_ignoring_worker(self):
        tag = 5000 + self.serial
        p = self._lifeline(f"trap '' TERM; sleep {tag}; true")
        time.sleep(1)
        self.assertTrue(self._pids(tag))
        p.stdin.close()
        self.assertTrue(self._gone_within(tag, 20))
        self.assertEqual(p.wait(timeout=20), 125)

    def test_V128L_lifeline_follows_the_holder_s_death(self):
        tag = 5100 + self.serial
        holder = subprocess.Popen([sys.executable, "-c", (
            "import subprocess, sys, time\n"
            f"p = subprocess.Popen([sys.executable, '-B', {self.LIFELINE!r}, '--', 'bash', '-c', "
            f"\"trap '' TERM; sleep {tag}; true\"], stdin=subprocess.PIPE, start_new_session=True)\n"
            "time.sleep(600)\n")], start_new_session=True)
        time.sleep(1.5)
        self.assertTrue(self._pids(tag))
        os.killpg(holder.pid, 9)
        holder.wait()
        self.assertTrue(self._gone_within(tag, 20))

    def test_V128L_lifeline_passes_the_exit_status_through(self):
        p = self._lifeline("exit 7")
        self.assertEqual(p.wait(timeout=20), 7)

    def test_V128N3_lifeline_cleans_descendants_when_the_leader_exits_first(self):
        tag = 5200 + self.serial
        p = self._lifeline(f"(trap '' TERM; sleep {tag}; true) & sleep 1; exit 0")
        self.assertEqual(p.wait(timeout=20), 0)
        self.assertTrue(self._gone_within(tag, 5))

    def test_V128N1_signal_right_after_start_still_cleans_the_child(self):
        import signal as sg
        tag = 5300 + self.serial
        p = self._lifeline(f"trap '' TERM; sleep {tag}; true")
        for _ in range(100):   # as soon as the child exists, TERM the lifeline itself
            if self._pids(tag):
                break
            time.sleep(0.05)
        os.kill(p.pid, sg.SIGTERM)
        self.assertEqual(p.wait(timeout=20), 125)
        self.assertTrue(self._gone_within(tag, 5))
        p.stdin.close()

    _INJECT = """
import importlib.util, os, pathlib, signal, sys, time
spec = importlib.util.spec_from_file_location("L", sys.argv[1]); L = importlib.util.module_from_spec(spec)
spec.loader.exec_module(L)
L.GRACE_S = 0.1
mode, pidfile, ready = sys.argv[2], pathlib.Path(sys.argv[3]), pathlib.Path(sys.argv[4])
real = L.subprocess.Popen
def launch(*args, **kwargs):
    p = real(*args, **kwargs)
    pidfile.write_text(str(p.pid))
    end = time.monotonic() + 5
    while not ready.exists() and time.monotonic() < end:
        time.sleep(0.01)
    if mode == "startup_signal":   # TERM arrives before Popen has even returned to the lifeline
        os.kill(os.getpid(), signal.SIGTERM)
    return p
L.subprocess.Popen = launch
if mode == "watcher_start_failure":
    def fail(*a, **k):
        raise RuntimeError("injected watcher-start failure")
    L.threading.Thread.start = fail
body = ("import signal, pathlib, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); "
        "pathlib.Path(" + repr(str(ready)) + ").write_text('ready'); time.sleep(60)")
try:
    rc = L.main(["lifeline", "--", sys.executable, "-B", "-c", body])
except RuntimeError:
    rc = 123
sys.exit(rc)
"""

    def _inject(self, mode):
        """Deterministic N1 injections (Codex V1.29.0 pre-freeze F6): the lifeline must clean up a ready,
        TERM-ignoring child when TERM lands before Popen returns, or when the watcher thread cannot start."""
        import signal as sg
        with tempfile.TemporaryDirectory() as d:
            pidfile, ready = Path(d) / "pid", Path(d) / "ready"
            p = subprocess.Popen([sys.executable, "-B", "-c", self._INJECT, self.LIFELINE, mode, str(pidfile),
                                  str(ready)], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, start_new_session=True)
            try:
                rc = p.wait(timeout=15)
                self.assertTrue(ready.exists())
                pgid = int(pidfile.read_text())
                gone = False
                for _ in range(50):
                    try:
                        os.killpg(pgid, 0)
                    except ProcessLookupError:
                        gone = True
                        break
                    time.sleep(0.1)
                return rc, gone
            finally:
                if p.poll() is None:
                    os.killpg(p.pid, sg.SIGKILL)
                    p.wait()
                if pidfile.exists():
                    try:
                        os.killpg(int(pidfile.read_text()), sg.SIGKILL)
                    except ProcessLookupError:
                        pass
                p.stdin.close()

    def test_V129F6_term_before_popen_returns_still_cleans_the_child(self):
        self.assertEqual(self._inject("startup_signal"), (125, True))

    def test_V129F6_watcher_start_failure_still_cleans_the_child(self):
        self.assertEqual(self._inject("watcher_start_failure"), (123, True))

    def test_V128L_production_worker_runs_under_the_lifeline(self):
        cmd = SR.production_worker(self.hub("A"), "smoke", 3600)
        i = cmd.index(str(ROOT / "scripts/su_lifeline.py"))
        self.assertEqual(cmd[i + 1], "--")
        self.assertEqual(cmd[i + 2:i + 4], ["timeout", "-k"])
        self.assertLess(cmd.index("distrobox"), i)

    def test_V128L_execute_gives_a_pipe_and_closes_it_before_any_signal(self):
        events = []

        class Pipe:
            def close(self):
                events.append("close")

        class Leader:
            pid = 999999999
            stdin = Pipe()

            def wait(self, timeout):
                raise subprocess.TimeoutExpired("fake", timeout)
        real = SR.os.killpg
        SR.os.killpg = lambda pgid, sig: events.append(int(sig))
        try:
            SR._kill_group(Leader())
        finally:
            SR.os.killpg = real
        self.assertEqual(events[:1], ["close"])
        hub = Path(self.temp.name) / f"pipe-hub{self.serial}"
        (hub / "runtime").mkdir(parents=True)
        # the worker's stdin is a pipe held open by the driver while it runs (the lifeline), not /dev/null
        self.assertEqual(SR.execute([sys.executable, "-c", "import os, stat, sys; "
                                     "sys.exit(0 if stat.S_ISFIFO(os.fstat(0).st_mode) else 3)"], hub, 30), 0)

    def test_V128RC3_ordinary_error_after_success_commit_keeps_the_success(self):
        hub = self.hub("A")
        real = SR.atomic_json

        def replace_then_error(path, value):
            real(path, value)
            if Path(path).name == "DRIVER-SUCCESS.json":
                raise OSError("injected temporary-file cleanup error after os.replace")
        SR.atomic_json = replace_then_error
        try:
            rc = SR.drive(hub, worker=self.worker({"main": "better"}), gpu_probe=lambda: {"fixture": True},
                          notify=False)
        finally:
            SR.atomic_json = real
        self.assertEqual(rc, 0)
        self.assertFalse((hub / "runtime/DRIVER-ERROR.json").exists())
        self.assertEqual(SCERT.certify(hub), [])
        self.assertEqual(SC.child_outcome(hub, rc)[0]["state"], "COMPLETE")

    def test_V128RC3_deadline_after_a_begun_failure_finishes_it_consistently(self):
        hub = self.hub("A")
        self.ok(hub, {"main": "better"})
        (hub / "runtime/INVALIDATED-SUCCESS.json").write_bytes((hub / "DRIVER-SUCCESS.json").read_bytes())
        import signal as sg
        try:
            committed = SR.deadline_fail(hub, "final check")
        finally:
            sg.setitimer(sg.ITIMER_REAL, 0)
        self.assertFalse(committed)
        self.assertFalse((hub / "DRIVER-SUCCESS.json").exists())
        self.assertTrue((hub / "DRIVER-FAILURE.json").exists())
        self.assertEqual(SC.child_outcome(hub, 1)[0]["state"], "INCOMPLETE")

    def test_V128RC3_fail_invalidates_success_before_any_failure_marker(self):
        hub = self.hub("A")
        self.ok(hub, {"main": "better"})
        order = []
        real = SR.atomic_json

        def watch(path, value):
            order.append((Path(path).name, (hub / "DRIVER-SUCCESS.json").exists()))
            return real(path, value)
        SR.atomic_json = watch
        try:
            SR.fail(hub, "notification", RuntimeError("injected"), lambda h: None)
        finally:
            SR.atomic_json = real
        self.assertEqual(order[0], ("DRIVER-ERROR.json", False))

    def test_V128RC1_repeated_term_does_not_skip_late_worker_cleanup(self):
        import signal as sg
        sleeper = self._sleeper_group()

        class TermAgainLeader:
            pid = 999999999

            def poll(self):
                return None

            def wait(self, timeout):
                os.kill(os.getpid(), sg.SIGTERM)   # a second TERM during the TERM wait
                time.sleep(0.2)
                raise subprocess.TimeoutExpired("fake", timeout)

        def populate(running, hub):
            dump(hub / "runtime/WORKER-PGID.json", {"pgid": sleeper.pid})   # registered after the last poll
            running.update(proc=TermAgainLeader(), hub=hub, worker_pgid=None, cleaned=False)
        chain, hubs = self.make_chain()
        real_run, real_kill = SC._run, SC._killpg

        def fake(chain_dir, command, start, mono_end, chain_deadline, estimate, running):
            populate(running, hubs[0])
            raise SC.ChainTerminated("injected first TERM")
        SC._run = fake
        SC._killpg = lambda pgid, sig: None if pgid == 999999999 else real_kill(pgid, sig)
        try:
            st = SC.run_chain(chain, command=self.child())
        finally:
            SC._run, SC._killpg = real_run, real_kill
        sleeper.wait(timeout=10)
        self.assert_group_gone(sleeper.pid)
        self.assertEqual((st["state"], st.get("late_worker_group_killed")), ("CHAIN_TERMINATED", sleeper.pid))
        self.assertNotIn("status_write", st)
        self.assertIs(sg.getsignal(sg.SIGTERM), sg.SIG_DFL)

    def test_V128RC2_chain_settles_after_a_failed_child(self):
        chain, hubs = self.make_chain()
        old = SC.LIFELINE_SETTLE_S
        SC.LIFELINE_SETTLE_S = 2
        try:
            t0 = time.time()
            st = SC.run_chain(chain, command=self.child({"A-confirm": "fail", "B-narrowed": "fail",
                                                        "C-wrongbind": "fail"}))
            elapsed = time.time() - t0
        finally:
            SC.LIFELINE_SETTLE_S = old
        self.assertEqual([e["state"] for e in st["studies"]], ["INCOMPLETE"] * 3, st)
        self.assertGreaterEqual(elapsed, 6)

    # ---- chain (Codex F2, F3)
    def make_chain(self, order="ABC"):
        type(self).serial += 1
        chain = Path(self.temp.name) / f"chain{self.serial}"
        chain.mkdir()
        names = {"A": "A-confirm", "B": "B-narrowed", "C": "C-wrongbind"}
        hubs = [self.hub(k, chain, names[k]) for k in order]
        dump(chain / "CHAIN.json", {"hubs": [names[k] for k in order]})
        return chain, hubs

    @staticmethod
    def child(modes=None, gpu=None):
        modes, gpu = modes or {}, gpu or {}

        def command(hub):
            return [sys.executable, "-B", str(ROOT / "tests/fixtures/su_fixture_drive.py"), "--hub", str(hub),
                    "--manifest", SCERT.MANIFEST_PATH,
                    "--main-mode", modes.get(hub.name, "better"), "--gpu", gpu.get(hub.name, "ok")]
        return command

    def test_chain_runs_all_three_back_to_back(self):
        chain, hubs = self.make_chain()
        st = SC.run_chain(chain, command=self.child())
        self.assertEqual([e["state"] for e in st["studies"]], ["COMPLETE"] * 3, st)
        self.assertEqual([e["reading"] for e in st["studies"]],
                         ["CONFIRMS_ON_THIS_PANEL", "WARRANTS_CONFIRMATION_DESIGN", "DESCRIPTIVE_COMPLETE"])
        self.assertTrue((chain / "CHAIN-COMMITMENT.json").exists())
        with self.assertRaises(SystemExit):
            SC.run_chain(chain, command=self.child())

    def test_chain_continues_after_incomplete_and_stops_on_gpu_fault(self):
        chain, hubs = self.make_chain()
        st = SC.run_chain(chain, command=self.child({"A-confirm": "fail"}, {"B-narrowed": "busy"}))
        self.assertEqual([e["state"] for e in st["studies"]], ["INCOMPLETE", "INCOMPLETE", "NOT_STARTED"], st)
        self.assertEqual(st["studies"][1]["step"], "GPU availability")

    def test_chain_ceiling_prevents_late_start(self):
        chain, hubs = self.make_chain()
        sizes = {"A-confirm": 10, "B-narrowed": 40000, "C-wrongbind": 10}
        st = SC.run_chain(chain, command=self.child(), ceiling_s=30000, estimate=lambda hub: sizes[hub.name])
        self.assertEqual([e["state"] for e in st["studies"]], ["COMPLETE", "NOT_STARTED", "COMPLETE"])
        self.assertIn("ceiling", st["studies"][1]["reason"])

    def test_chain_kills_child_at_chain_deadline(self):
        chain, hubs = self.make_chain()
        t0 = time.time()
        st = SC.run_chain(chain, command=lambda hub: [sys.executable, "-c", "import time; time.sleep(120)"],
                          ceiling_s=152, estimate=lambda hub: 1)
        self.assertLess(time.time() - t0, 90)
        self.assertTrue(st.get("state") == "CHAIN_DEADLINE" or
                        [e["state"] for e in st["studies"]][:1] == ["KILLED_AT_CHAIN_DEADLINE"], st)
        self.assertFalse((hubs[1] / "runtime").exists())

    def test_chain_refuses_reordered_or_unfrozen_hubs(self):
        chain, hubs = self.make_chain("BAC")
        self.assertEqual(SC.run_chain(chain, command=self.child())["state"], "REFUSED")
        chain, hubs = self.make_chain()
        (hubs[2] / "design/PROTOCOL.md").write_text("tampered before chain start\n")
        st = SC.run_chain(chain, command=self.child())
        self.assertEqual(st["state"], "REFUSED")
        self.assertFalse((hubs[0] / "stages").exists())

    def test_chain_stops_on_chain_spec_change_after_start(self):
        chain, hubs = self.make_chain()

        def command(hub):
            if hub.name == "A-confirm":
                (chain / "CHAIN.json").write_text((chain / "CHAIN.json").read_text() + " ")
            return self.child()(hub)
        st = SC.run_chain(chain, command=command)
        self.assertEqual([e["state"] for e in st["studies"]], ["COMPLETE", "NOT_STARTED", "NOT_STARTED"])

    def test_chain_stops_on_freeze_change_after_start(self):
        chain, hubs = self.make_chain()

        def command(hub):
            if hub.name == "A-confirm":
                (hubs[1] / "config/FROZEN-PROTOCOL.json").write_text(
                    (hubs[1] / "config/FROZEN-PROTOCOL.json").read_text() + " ")
            return self.child()(hub)
        st = SC.run_chain(chain, command=command)
        self.assertEqual([e["state"] for e in st["studies"]], ["COMPLETE", "NOT_STARTED", "NOT_STARTED"])

    def test_chain_treats_contradictory_or_nonzero_success_as_fault(self):
        hub = self.completed()
        outcome, halt = SC.child_outcome(hub, 99)
        self.assertEqual(outcome["state"], "FAULT")
        self.assertTrue(halt)
        dump(hub / "DRIVER-FAILURE.json", {"step": "analysis"})
        outcome, halt = SC.child_outcome(hub, 0)
        self.assertEqual(outcome["state"], "FAULT")
        hub = self.completed()
        self.assertEqual(SC.child_outcome(hub, 0)[0]["state"], "COMPLETE")


if __name__ == "__main__":
    unittest.main()
