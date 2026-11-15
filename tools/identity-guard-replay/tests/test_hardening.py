"""Regression tests for the review fixes (stale-output refusal, evaluator provenance, readiness gating, table escaping).

All tests run the real ig_decide / ig_evaluate / ig_report code on isolated temporary subset hubs copied from the
V1.24 inputs (the real hubs are only read). Run: PYTHONDONTWRITEBYTECODE=1 python -B -m unittest discover -s tests -v
"""
import copy
import hashlib
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "scripts"))
sys.path.insert(0, str(HERE / "tests"))
from guard import pins  # noqa: E402

pins.activate()
from guard import studies as ST  # noqa: E402
import ig_decide  # noqa: E402
import ig_evaluate  # noqa: E402
import ig_report  # noqa: E402
from test_guard import REAL, SUBSET_STEMS, build_hub  # noqa: E402


def build_eval_hub(root):
    """Subset hub plus the REAL hidden gold and saved scores for exactly those targets/calls (copied, read-only)."""
    hub, n = build_hub(root)
    keep = lambda t: t.split("|")[0] in SUBSET_STEMS
    (hub / "data" / "hidden").mkdir()
    (hub / "analysis" / "confirm").mkdir(parents=True)
    for src, dst, key in (("data/hidden/main-cases.jsonl", "data/hidden/main-cases.jsonl", "target"),
                          ("analysis/confirm/scored.jsonl", "analysis/confirm/scored.jsonl", "call_id")):
        rows = [x for x in (REAL / src).read_text().splitlines() if x and keep(json.loads(x)[key])]
        (hub / dst).write_text("\n".join(rows) + "\n")
    return hub, n


def jl(path):
    return [json.loads(x) for x in Path(path).read_text().splitlines() if x]


def wjl(path, rows):
    Path(path).write_text("".join(json.dumps(r) + "\n" for r in rows))


def files(d):
    return {p.name: p.read_bytes() for p in sorted(Path(d).iterdir())}


class StaleOutputRefusal(unittest.TestCase):
    def test_complete_then_bad_rerun_is_refused_and_old_ledger_untouched(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            hub, _ = build_hub(t / "hub")
            s1 = ig_decide.run("V1.24", hub, t / "o", use_expected=False)
            self.assertEqual(s1["status"], "SEALED")
            before = files(t / "o")
            next((hub / "stages" / "main" / "calls").glob("*.json")).unlink()   # now an INCOMPLETE input
            s2 = ig_decide.run("V1.24", hub, t / "o", use_expected=False)
            self.assertEqual(s2["status"], "REFUSED")
            self.assertTrue(all("refusing to overwrite" in p for p in s2["problems"]))
            self.assertEqual(files(t / "o"), before)

    def test_complete_then_complete_rerun_is_refused(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            hub, _ = build_hub(t / "hub")
            ig_decide.run("V1.24", hub, t / "o", use_expected=False)
            before = files(t / "o")
            self.assertEqual(ig_decide.run("V1.24", hub, t / "o", use_expected=False)["status"], "REFUSED")
            self.assertEqual(files(t / "o"), before)

    def test_incomplete_then_good_rerun_is_refused(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            hub, _ = build_hub(t / "hub")
            self.assertEqual(ig_decide.run("V1.24", hub, t / "o", use_expected=True)["status"], "INCOMPLETE")
            self.assertEqual(ig_decide.run("V1.24", hub, t / "o", use_expected=False)["status"], "REFUSED")
            self.assertFalse((t / "o" / "SEAL-V1.24.json").exists())

    def test_other_study_in_same_dir_is_not_blocked(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            hub, _ = build_hub(t / "hub")
            ig_decide.run("V1.24", hub, t / "o", use_expected=False)
            before = files(t / "o")
            self.assertEqual(ig_decide.run("V1.22", hub, t / "o", use_expected=False)["status"], "SEALED")
            after = files(t / "o")
            self.assertEqual({k: v for k, v in after.items() if "V1.24" in k}, before)


class EvaluatorProvenance(unittest.TestCase):
    """A valid seal must not be joined to scoring if the public inputs or raw replies under the same IDs differ."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        t = Path(cls.tmp.name)
        cls.hub, cls.n = build_eval_hub(t / "clean")
        cls.dec = t / "dec"
        assert ig_decide.run("V1.24", cls.hub, cls.dec, use_expected=False)["status"] == "SEALED"

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def evaluate(self, hub=None, ddir=None):
        out = Path(tempfile.mkdtemp(dir=self.tmp.name))
        r = ig_evaluate.evaluate("V1.24", ddir or self.dec, out, hub=hub or self.hub, use_expected=False)
        return r, out

    def copy_hub(self):
        import shutil
        d = Path(tempfile.mkdtemp(dir=self.tmp.name)) / "hub"
        shutil.copytree(self.hub, d)
        return d

    def copy_dec(self):
        import shutil
        d = Path(tempfile.mkdtemp(dir=self.tmp.name)) / "dec"
        shutil.copytree(self.dec, d)
        return d

    def assertRefused(self, r, out, needle):
        self.assertEqual(r["status"], "REFUSED", r.get("problems"))
        self.assertTrue(any(needle in p for p in r["problems"]), r["problems"][:5])
        self.assertFalse((out / "RESULTS-V1.24.json").exists())
        self.assertFalse((out / "TRACE-V1.24.jsonl").exists())
        st = json.loads((out / "EVALUATION-STATUS-V1.24.json").read_text())
        self.assertEqual((st["status"], st["composed"]), ("REFUSED", False))

    def test_clean_inputs_compose_with_every_row_verified(self):
        r, out = self.evaluate()
        self.assertEqual(r["status"], "COMPLETE", r["problems"])
        self.assertEqual(r["provenance"]["rows_verified"], self.n)
        self.assertEqual(r["provenance"]["hashed_inputs"], ["prefix", "target_text", "registry", "registry_order", "raw"])
        self.assertEqual(r["totals"]["responses"], self.n)
        self.assertEqual(r["integrity"]["n_mismatches"], 0)

    def _mutate_public(self, hub, fn):
        p = hub / "data" / "public" / "main-targets.jsonl"
        rows = jl(p)
        fn(rows[0])
        wjl(p, rows)

    def test_each_of_the_five_inputs_changed_after_sealing_is_refused(self):
        def raw(hub):
            f = sorted((hub / "stages" / "main" / "calls").glob("*.json"))[0]
            r = json.loads(f.read_text())
            r["raw"] = r["raw"] + " "
            f.write_text(json.dumps(r))
        cases = {
            "raw": raw,
            "target_text": lambda h: self._mutate_public(h, lambda r: r.update(target_text=r["target_text"] + " ")),
            "prefix": lambda h: self._mutate_public(
                h, lambda r: r["prefix"][0].update(raw_text=r["prefix"][0]["raw_text"] + " ")),
            "registry": lambda h: self._mutate_public(h, lambda r: r["registry"].update({"Zzzz.on_hand": []})),
            "registry_order": lambda h: self._mutate_public(
                h, lambda r: r.update(registry_order=list(reversed(r["registry_order"])))),
        }
        for key, mutate in cases.items():
            with self.subTest(changed=key):
                hub = self.copy_hub()
                mutate(hub)
                r, out = self.evaluate(hub=hub)
                self.assertRefused(r, out, f"decision input hash mismatch on ['{key}']")

    def test_valid_seal_built_from_altered_inputs_is_refused_against_the_original(self):
        hub = self.copy_hub()
        f = sorted((hub / "stages" / "main" / "calls").glob("*.json"))[3]
        rec = json.loads(f.read_text())
        rec["raw"] = '{"forged": true}'
        f.write_text(json.dumps(rec))
        d = Path(tempfile.mkdtemp(dir=self.tmp.name)) / "dec"
        self.assertEqual(ig_decide.run("V1.24", hub, d, use_expected=False)["status"], "SEALED")   # seal is valid
        r, out = self.evaluate(hub=self.hub, ddir=d)
        self.assertRefused(r, out, f"{rec['call_id']}: decision input hash mismatch on ['raw']")

    def _reseal(self, d, rows=None, **seal_changes):
        body = (d / "DECISIONS-V1.24.jsonl").read_bytes() if rows is None else \
            ("\n".join(rows) + "\n").encode()
        (d / "DECISIONS-V1.24.jsonl").write_bytes(body)
        sha = hashlib.sha256(body).hexdigest()
        seal = json.loads((d / "SEAL-V1.24.json").read_text())
        seal["decisions_sha256"] = sha
        seal.update(seal_changes)
        (d / "SEAL-V1.24.json").write_text(json.dumps(seal))
        st = json.loads((d / "DECISION-STATUS-V1.24.json").read_text())
        st["decisions_sha256"] = sha
        (d / "DECISION-STATUS-V1.24.json").write_text(json.dumps(st))

    def test_duplicate_rows_under_a_valid_seal_are_refused(self):
        d = self.copy_dec()
        lines = (d / "DECISIONS-V1.24.jsonl").read_text().splitlines()
        seal = json.loads((d / "SEAL-V1.24.json").read_text())
        disp = dict(seal["dispositions"])
        k = json.loads(lines[0])["decision"]["disposition"]
        disp[k] += 1
        self._reseal(d, lines + [lines[0]], n_decisions=len(lines) + 1, dispositions=disp)
        r, out = self.evaluate(ddir=d)
        self.assertRefused(r, out, "decisions: duplicate call_id")

    def test_inconsistent_seal_metadata_is_refused(self):
        lines = (self.dec / "DECISIONS-V1.24.jsonl").read_text().splitlines()
        cases = {"n_decisions": ({"n_decisions": len(lines) - 1}, "seal n_decisions"),
                 "dispositions": ({"dispositions": {"pass": len(lines)}}, "seal dispositions"),
                 "study": ({"study": "V1.22"}, "seal study"),
                 "rule": ({"rule": "IGUARD-v0.0"}, "seal rule"),
                 "decisions_file": ({"decisions_file": "../DECISIONS-V1.24.jsonl"}, "seal decisions_file"),
                 "utility_source": ({"utility_source_sha256": "0" * 64}, "utility_source_sha256 differs"),
                 "dependencies": ({"dependency_sha256": {}}, "dependency_sha256 differs")}
        for name, (change, needle) in cases.items():
            with self.subTest(field=name):
                d = self.copy_dec()
                self._reseal(d, **change)
                r, out = self.evaluate(ddir=d)
                self.assertRefused(r, out, needle)

    def test_dropped_row_and_unsealed_body_edit_are_refused(self):
        d = self.copy_dec()
        lines = (d / "DECISIONS-V1.24.jsonl").read_text().splitlines()
        seal = json.loads((d / "SEAL-V1.24.json").read_text())
        disp = dict(seal["dispositions"])
        disp[json.loads(lines[-1])["decision"]["disposition"]] -= 1
        self._reseal(d, lines[:-1], n_decisions=len(lines) - 1, dispositions={k: v for k, v in disp.items() if v})
        r, out = self.evaluate(ddir=d)
        self.assertRefused(r, out, "decision membership differs from schedule")
        d = self.copy_dec()
        (d / "DECISIONS-V1.24.jsonl").write_bytes((d / "DECISIONS-V1.24.jsonl").read_bytes() + b"\n")
        r, out = self.evaluate(ddir=d)
        self.assertRefused(r, out, "sealed decision hash mismatch")

    def test_decision_status_disagreeing_with_seal_is_refused(self):
        d = self.copy_dec()
        st = json.loads((d / "DECISION-STATUS-V1.24.json").read_text())
        st["status"] = "INCOMPLETE"
        (d / "DECISION-STATUS-V1.24.json").write_text(json.dumps(st))
        r, out = self.evaluate(ddir=d)
        self.assertRefused(r, out, "decision status")

    def test_evaluator_refuses_to_overwrite_results(self):
        r, out = self.evaluate()
        self.assertEqual(r["status"], "COMPLETE")
        before = files(out)
        r2 = ig_evaluate.evaluate("V1.24", self.dec, out, hub=self.hub, use_expected=False)
        self.assertEqual(r2["status"], "REFUSED")
        self.assertEqual(files(out), before)

    def test_report_tables_escape_pipes_and_keep_ids(self):
        """Real report from a real subset evaluation (V1.22 missing): every table keeps its column count."""
        r, out = self.evaluate()
        hub = Path(tempfile.mkdtemp(dir=self.tmp.name))
        (hub / "results").mkdir()
        (hub / "results" / "RESULTS-V1.24.json").write_text((out / "RESULTS-V1.24.json").read_text())
        ready = ig_report.write(hub)
        self.assertFalse(ready["technically_complete"])
        self.assertFalse(ready["ready_for_further_consideration"])
        text = (hub / "REPORT.md").read_text()
        self.assertIn("INCOMPLETE / PROTOTYPE NOT READY", text)
        split = lambda line: [c.strip() for c in re.split(r"(?<!\\)\|", line.strip())[1:-1]]
        tables, cur = [], []
        for line in text.splitlines() + [""]:
            if line.startswith("|"):
                cur.append(line)
            elif cur:
                tables.append(cur)
                cur = []
        self.assertGreaterEqual(len(tables), 4)
        joint_seen = False
        for tb in tables:
            width = len(split(tb[0]))
            self.assertTrue(re.fullmatch(r"\|(-{3}:?\|)+", tb[1].replace("---:", "---:")), tb[1])
            self.assertEqual(len(split(tb[1])), width, tb[1])
            for line in tb[2:]:
                self.assertEqual(len(split(line)), width, line)
            hdr = [c.replace("\\|", "|") for c in split(tb[0])]
            if "accepted|pass" in hdr:
                joint_seen = True
        self.assertTrue(joint_seen)
        shown = {c.replace("\\|", "|").strip("`") for tb in tables for line in tb[2:] for c in split(line)}
        for f in r["known_fixtures"]:
            self.assertIn(f["call_id"], shown)
        for m in r["identity_mismatches"]:
            self.assertIn(m["call_id"], shown)
        self.assertNotIn("`c24-g0045|", text)   # raw unescaped pipes inside a code span would split the row


GOOD_SHA = {"V1.24": "a" * 64, "V1.22": "b" * 64}


def good_hub(root):
    root = Path(root)
    for d in ("results", "controls", "tests", "decisions"):
        (root / d).mkdir(parents=True, exist_ok=True)
    put = lambda rel, obj: (root / rel).write_text(json.dumps(obj))
    for s, k in (("V1.24", 4), ("V1.22", 3)):
        n = ST.STUDIES[s]["calls"]
        put(f"results/RESULTS-{s}.json", {
            "status": "COMPLETE", "problems": [], "totals": {"responses": n, "exact_blocked": 0, "acceptance_expanded": 0},
            "seal": {"n_decisions": n, "decisions_sha256": GOOD_SHA[s]},
            "provenance": {"verified_before_composition": True, "rows_verified": n},
            "known_fixtures_all_blocked": True, "known_fixtures": [{"present": True, "blocked": True}] * k,
            "exact_blocked": [], "acceptance_expanded": []})
        put(f"decisions/SEAL-{s}.json", {"decisions_sha256": GOOD_SHA[s]})
    put("controls/CONTROLS.json", {"status": "PASS", "failures": [], "n": 2, "supported_matches_pass": True,
                                   "refusals_abstain": True, "no_refusal_passes": True,
                                   "rows": [{"expected": {"disposition": "pass"}, "ok": True},
                                            {"expected": {"disposition": "abstain"}, "ok": True}]})
    put("PRESERVATION.json", {"unchanged": True, "roots": {f"r{i}": {"unchanged": True, "files": 3} for i in range(4)}})
    put("tests/TESTS.json", {"ok": True, "commit": "c0"})
    put("PLAN.json", {"utility_commit": "c0"})
    put("INPUT-MANIFEST.json", {"disclosure": "d", "studies": {s: {"frozen_manifest_check": {"ok": True}}
                                                               for s in ST.STUDIES}})
    put("RUNTIME.json", {"status": "STAGES_COMPLETE", "failed_steps": [], "any_step_failed": False, "within_cap": True,
                         "cap_seconds": 1800})
    put("DETERMINISM.json", {s: {"first": GOOD_SHA[s], "repeat": GOOD_SHA[s], "equal": True} for s in GOOD_SHA})
    return root


def edit(root, rel, fn):
    p = Path(root) / rel
    obj = json.loads(p.read_text())
    fn(obj)
    p.write_text(json.dumps(obj))


class Readiness(unittest.TestCase):
    def check(self, mutate, complete, ready=False):
        with tempfile.TemporaryDirectory() as t:
            hub = good_hub(t)
            mutate(hub)
            rd = ig_report.readiness(hub)[0]
            self.assertEqual(rd["technically_complete"], complete, rd["failed_technical"])
            self.assertEqual(rd["ready_for_further_consideration"], ready, rd["criteria"])
            return rd

    def test_baseline_is_ready(self):
        rd = self.check(lambda h: None, True, True)
        self.assertEqual(ig_report.status_line(rd), "COMPLETE / PROTOTYPE READY FOR FURTHER CONSIDERATION")

    def test_technical_failures_never_ready(self):
        cases = {
            "step failed": lambda h: edit(h, "RUNTIME.json", lambda o: o.update(any_step_failed=True)),
            "failed steps listed": lambda h: edit(h, "RUNTIME.json", lambda o: o.update(failed_steps=["plan rc=2"])),
            "runtime missing": lambda h: (h / "RUNTIME.json").unlink(),
            "over cap": lambda h: edit(h, "RUNTIME.json", lambda o: o.update(within_cap=False)),
            "controls FAIL": lambda h: edit(h, "controls/CONTROLS.json", lambda o: o.update(status="FAIL")),
            "controls failures": lambda h: edit(h, "controls/CONTROLS.json", lambda o: o.update(failures=[{"x": 1}])),
            "controls empty": lambda h: edit(h, "controls/CONTROLS.json", lambda o: o.update(n=0, rows=[])),
            "controls missing": lambda h: (h / "controls" / "CONTROLS.json").unlink(),
            "repeat differs": lambda h: edit(h, "DETERMINISM.json", lambda o: o["V1.22"].update(repeat="c" * 64)),
            "repeat flag false": lambda h: edit(h, "DETERMINISM.json", lambda o: o["V1.24"].update(equal=False)),
            "determinism missing": lambda h: (h / "DETERMINISM.json").unlink(),
            "seal differs": lambda h: edit(h, "decisions/SEAL-V1.24.json", lambda o: o.update(decisions_sha256="d")),
            "results missing": lambda h: (h / "results" / "RESULTS-V1.22.json").unlink(),
            "results empty file": lambda h: (h / "results" / "RESULTS-V1.22.json").write_text(""),
            "results incomplete": lambda h: edit(h, "results/RESULTS-V1.24.json", lambda o: o.update(status="INCOMPLETE")),
            "subset denominator": lambda h: edit(h, "results/RESULTS-V1.24.json",
                                                 lambda o: o["totals"].update(responses=10)),
            "provenance absent": lambda h: edit(h, "results/RESULTS-V1.24.json", lambda o: o.pop("provenance")),
            "preservation changed": lambda h: edit(h, "PRESERVATION.json", lambda o: o.update(unchanged=False)),
            "preservation no roots": lambda h: edit(h, "PRESERVATION.json", lambda o: o.update(roots={})),
            "tests failed": lambda h: edit(h, "tests/TESTS.json", lambda o: o.update(ok=False)),
            "tests other commit": lambda h: edit(h, "tests/TESTS.json", lambda o: o.update(commit="zz")),
            "manifest check failed": lambda h: edit(h, "INPUT-MANIFEST.json",
                                                    lambda o: o["studies"]["V1.22"]["frozen_manifest_check"].update(ok=False)),
            "manifest missing study": lambda h: edit(h, "INPUT-MANIFEST.json", lambda o: o["studies"].pop("V1.22")),
        }
        for name, mutate in cases.items():
            with self.subTest(case=name):
                rd = self.check(mutate, False)
                self.assertTrue(ig_report.status_line(rd).startswith("INCOMPLETE / PROTOTYPE NOT READY"))

    def test_unfavourable_outcomes_are_complete_but_not_ready(self):
        cases = {
            "exact blocked": lambda h: edit(h, "results/RESULTS-V1.22.json",
                                            lambda o: (o["totals"].update(exact_blocked=1), o.update(exact_blocked=[{}]))),
            "acceptance expanded": lambda h: edit(h, "results/RESULTS-V1.24.json",
                                                  lambda o: o.update(acceptance_expanded=["x"])),
            "fixture not blocked": lambda h: edit(h, "results/RESULTS-V1.24.json",
                                                  lambda o: o.update(known_fixtures=[{"present": True, "blocked": False}] * 4)),
            "vacuous fixtures": lambda h: edit(h, "results/RESULTS-V1.24.json", lambda o: o.update(known_fixtures=[])),
            "no refusal controls": lambda h: edit(h, "controls/CONTROLS.json",
                                                  lambda o: o.update(rows=o["rows"][:1], n=1)),
        }
        for name, mutate in cases.items():
            with self.subTest(case=name):
                rd = self.check(mutate, True, False)
                self.assertEqual(ig_report.status_line(rd), "COMPLETE / PROTOTYPE NOT READY UNDER THE STATED CRITERIA")

    def test_report_written_for_empty_hub(self):
        with tempfile.TemporaryDirectory() as t:
            rd = ig_report.write(Path(t))
            self.assertFalse(rd["technically_complete"] or rd["ready_for_further_consideration"])
            for name in ("REPORT.md", "READINESS.json", "RUN-STATUS.md", "CLAIM-EVIDENCE.md", "READER-TAKEAWAY.md"):
                self.assertTrue((Path(t) / name).exists(), name)
            self.assertIn("INCOMPLETE", (Path(t) / "RUN-STATUS.md").read_text())
            self.assertIn("earlier decision generation cannot be ruled out", (Path(t) / "REPORT.md").read_text())

    def test_report_discloses_manifest_smoke_verbatim(self):
        with tempfile.TemporaryDirectory() as t:
            hub = good_hub(t)
            edit(hub, "INPUT-MANIFEST.json", lambda o: o.update(disclosure="a decision-only scratch smoke happened"))
            ig_report.provenance_lines(hub)
            text = "\n".join(ig_report.provenance_lines(hub))
            self.assertIn("INPUT-MANIFEST disclosure (verbatim): a decision-only scratch smoke happened", text)
            self.assertIn("preceded the original formal commit and replay", text)


class CellEscaping(unittest.TestCase):
    def test_cell_escapes_every_pipe(self):
        self.assertEqual(ig_report.cell("a|b|c"), "a\\|b\\|c")
        self.assertEqual(ig_report.code("c24-g0045|arrival|na|B|KEEP_CLAR"), "`c24-g0045\\|arrival\\|na\\|B\\|KEEP_CLAR`")
        self.assertEqual(ig_report.cell("x\ny"), "x y")


if __name__ == "__main__":
    unittest.main()
