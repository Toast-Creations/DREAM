"""Declared-membership checks (review item: totals alone allowed a substituted condition/call/target).

Full-size isolated temporary copies of the V1.24 public decision inputs are used so the expected totals are enforced;
the real hubs are only read.
"""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "scripts"))
from guard import pins  # noqa: E402

pins.activate()
from guard import studies as ST  # noqa: E402
import ig_decide  # noqa: E402
import ig_plan  # noqa: E402

SPEC = ST.STUDIES["V1.24"]
REAL = SPEC["hub"]


def full_copy(root):
    root = Path(root)
    (root / "data" / "public").mkdir(parents=True)
    shutil.copy(REAL / "data" / "public" / "main-targets.jsonl", root / "data" / "public")
    shutil.copy(REAL / "data" / "main-calls.jsonl", root / "data")
    shutil.copytree(REAL / "stages" / "main" / "calls", root / "stages" / "main" / "calls")
    return root


def rename_call(hub, old, new):
    """Rename one scheduled call consistently in the schedule, its record and its file name (totals unchanged)."""
    p = hub / "data" / "main-calls.jsonl"
    rows = [json.loads(x) for x in p.read_text().splitlines() if x]
    for r in rows:
        if r["call_id"] == old:
            r["call_id"] = new
    p.write_text("".join(json.dumps(r) + "\n" for r in rows))
    d = hub / "stages" / "main" / "calls"
    rec = json.loads((d / (old.replace("|", "__") + ".json")).read_text())
    rec["call_id"] = new
    (d / (old.replace("|", "__") + ".json")).unlink()
    (d / (new.replace("|", "__") + ".json")).write_text(json.dumps(rec))


def schedule(hub):
    return [json.loads(x)["call_id"] for x in (hub / "data" / "main-calls.jsonl").read_text().splitlines() if x]


class Membership(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.real_calls = schedule(REAL)

    def _decide(self, hub, out):
        return ig_decide.run("V1.24", hub, out, use_expected=True)

    def test_real_membership_passes(self):
        self.assertEqual(ST.membership_problems(
            [json.loads(x)["target"] for x in (REAL / "data/public/main-targets.jsonl").read_text().splitlines() if x],
            self.real_calls, SPEC), [])

    def test_unmodified_full_copy_seals(self):
        with tempfile.TemporaryDirectory() as t:
            hub = full_copy(Path(t) / "hub")
            s = self._decide(hub, Path(t) / "o")
            self.assertEqual(s["status"], "SEALED", s.get("problems"))
            self.assertEqual(s["n_decisions"], SPEC["calls"])

    def test_count_preserving_substitution_within_condition_is_incomplete(self):
        # Move one SUB_CLAR reference call onto a target outside the reference subset: every total and every
        # per-condition count is unchanged; only the exact membership differs.
        ref = sorted(c for c in self.real_calls if c.endswith("|SUB_CLAR"))
        ref_targets = {ST.target_of(c) for c in ref}
        outside = sorted(ST.target_of(c) for c in self.real_calls
                         if c.endswith("|KEEP_CLAR") and ST.target_of(c) not in ref_targets)
        old, new = ref[0], outside[0] + "|SUB_CLAR"
        with tempfile.TemporaryDirectory() as t:
            hub = full_copy(Path(t) / "hub")
            rename_call(hub, old, new)
            calls = schedule(hub)
            self.assertEqual(len(calls), SPEC["calls"])
            s = self._decide(hub, Path(t) / "o")
            self.assertEqual(s["status"], "INCOMPLETE")
            self.assertIn("scheduled call IDs differ from the pinned declared membership", s["problems"])
            self.assertFalse(any(p.startswith("condition ") for p in s["problems"]), s["problems"])
            self.assertFalse(list((Path(t) / "o").glob("SEAL-*.json")))

    def test_substituted_condition_is_incomplete(self):
        old = sorted(c for c in self.real_calls if c.endswith("|SUB_CLAR"))[0]
        new = old.rsplit("|", 1)[0] + "|KEEP_ORIG"
        with tempfile.TemporaryDirectory() as t:
            hub = full_copy(Path(t) / "hub")
            rename_call(hub, old, new)
            s = self._decide(hub, Path(t) / "o")
            self.assertEqual(s["status"], "INCOMPLETE")
            self.assertTrue(any("undeclared condition KEEP_ORIG" in p for p in s["problems"]), s["problems"])
            self.assertTrue(any("condition SUB_CLAR: 127" in p for p in s["problems"]), s["problems"])

    def test_substituted_target_is_incomplete(self):
        with tempfile.TemporaryDirectory() as t:
            hub = full_copy(Path(t) / "hub")
            p = hub / "data" / "public" / "main-targets.jsonl"
            rows = [json.loads(x) for x in p.read_text().splitlines() if x]
            old = rows[0]["target"]
            new = old.replace("c24-g", "c24-x")
            rows[0]["target"] = new
            p.write_text("".join(json.dumps(r) + "\n" for r in rows))
            for c in [c for c in schedule(hub) if ST.target_of(c) == old]:
                rename_call(hub, c, new + "|" + ST.arm_of(c))
            s = self._decide(hub, Path(t) / "o")
            self.assertEqual(s["status"], "INCOMPLETE")
            self.assertIn("public target IDs differ from the pinned declared membership", s["problems"])

    def test_cli_has_no_unchecked_mode(self):
        import subprocess
        p = subprocess.run([sys.executable, "-B", str(HERE / "scripts" / "ig_decide.py"), "--study", "V1.24",
                            "--out", "/nonexistent-never-created", "--no-expected"],
                           capture_output=True, text=True, env={"PYTHONDONTWRITEBYTECODE": "1", "PATH": "/usr/bin"})
        self.assertEqual(p.returncode, 2)
        self.assertIn("unrecognized arguments: --no-expected", p.stderr)
        self.assertFalse(Path("/nonexistent-never-created").exists())

    def test_unchecked_mode_refused_on_real_study_hub(self):
        with tempfile.TemporaryDirectory() as t:
            s = ig_decide.run("V1.24", REAL, Path(t) / "o", use_expected=False)
            self.assertEqual(s["status"], "REFUSED")
            self.assertFalse(any((Path(t) / "o").glob("*")))

    def test_production_evaluator_refuses_unchecked_seal(self):
        import ig_evaluate
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            hub = full_copy(t / "hub")   # full real membership, but sealed through the unchecked fixture path
            self.assertEqual(ig_decide.run("V1.24", hub, t / "d", use_expected=False)["status"], "SEALED")
            self.assertIs(json.loads((t / "d" / "SEAL-V1.24.json").read_text())["membership_checked"], False)
            r = ig_evaluate.evaluate("V1.24", t / "d", t / "o", hub=hub, use_expected=True)
            self.assertEqual(r["status"], "REFUSED")
            self.assertIn("seal was produced without the declared-membership checks", r["problems"])
            self.assertFalse((t / "o" / "RESULTS-V1.24.json").exists())

    def test_checked_seal_records_membership(self):
        with tempfile.TemporaryDirectory() as t:
            hub = full_copy(Path(t) / "hub")
            self.assertEqual(self._decide(hub, Path(t) / "o")["status"], "SEALED")
            self.assertIs(json.loads((Path(t) / "o" / "SEAL-V1.24.json").read_text())["membership_checked"], True)

    def test_plan_rederives_pinned_digests_from_frozen_select(self):
        for study in ("V1.24", "V1.22"):
            v = ig_plan.verify_frozen(study)
            self.assertEqual(v["problems"], [], study)
            m = v["membership"]
            self.assertEqual(m["frozen_select_sha256"], ST.STUDIES[study]["calls_sha256"])
            self.assertEqual(m["targets_from_select_sha256"], ST.STUDIES[study]["targets_sha256"])


if __name__ == "__main__":
    unittest.main()
