"""Focused tests for IGUARD-v0.1. Run: PYTHONDONTWRITEBYTECODE=1 python -B -m unittest discover -s tests -v

All file-system tests use isolated temporary copies of a small subset of the V1.24 public inputs. The real hubs are
only read; nothing is written to them.
"""
import copy
import inspect
import itertools
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
from guard import decide as D, studies as ST  # noqa: E402
import ig_controls  # noqa: E402
import ig_decide  # noqa: E402
import ig_evaluate  # noqa: E402

REAL = ST.STUDIES["V1.24"]["hub"]
SUBSET_STEMS = ("c24-g0001", "c24-g0045", "c24-g0120", "c24-g0125")


def build_hub(root, poison=False, with_hidden=False):
    """Copy the public inputs of a few stems into root (all their targets and calls)."""
    root = Path(root)
    (root / "data" / "public").mkdir(parents=True)
    (root / "stages" / "main" / "calls").mkdir(parents=True)
    keep = lambda t: t.split("|")[0] in SUBSET_STEMS
    pubs = [json.loads(x) for x in (REAL / "data" / "public" / "main-targets.jsonl").read_text().splitlines() if x]
    pubs = [p for p in pubs if keep(p["target"])]
    if poison:
        for i, p in enumerate(pubs):   # every non-decision field garbled or swapped
            p["identity"] = {"field": "Poison.on_hand", "detection": None}
            p["family"], p["history"], p["reception"] = "F9_poison", "Z", "never"
            p["component"], p["bits"], p["stratum"] = "poison", [9, 9, 9], "poison"
            p["gold_field"] = "Poison.on_hand"
            p["base_prompt"] = "poisoned"
    (root / "data" / "public" / "main-targets.jsonl").write_text("".join(json.dumps(p) + "\n" for p in pubs))
    calls = [json.loads(x) for x in (REAL / "data" / "main-calls.jsonl").read_text().splitlines() if x]
    calls = [c for c in calls if keep(c["call_id"])]
    if poison:
        for c in calls:
            c.update(arm="POISON", pattern="POISON", family="F9", history="Z", system="poison", user="poison")
    (root / "data" / "main-calls.jsonl").write_text("".join(json.dumps(c) + "\n" for c in calls))
    for c in calls:
        name = c["call_id"].replace("|", "__") + ".json"
        r = json.loads((REAL / "stages" / "main" / "calls" / name).read_text())
        if poison:
            r.update(arm="POISON", pattern="POISON", variant="poison", model={"poison": True})
        (root / "stages" / "main" / "calls" / name).write_text(json.dumps(r))
    if with_hidden:   # bogus hidden labels and scores: must not change any decision
        (root / "data" / "hidden").mkdir()
        (root / "data" / "hidden" / "main-cases.jsonl").write_text(
            "".join(json.dumps({"target": p["target"], "gold_field": "Poison.on_hand"}) + "\n" for p in pubs))
        (root / "analysis" / "confirm").mkdir(parents=True)
        (root / "analysis" / "confirm" / "scored.jsonl").write_text('{"call_id": "x", "exact": true}\n')
    return root, len(calls)


def decisions_bytes(out):
    return next(Path(out).glob("DECISIONS-*.jsonl")).read_bytes()


class Interface(unittest.TestCase):
    def test_decision_interface_is_public_only(self):
        self.assertEqual(list(inspect.signature(D.decide).parameters),
                         ["prefix", "target_text", "registry", "registry_order", "raw"])

    def test_loader_keeps_only_public_keys(self):
        with tempfile.TemporaryDirectory() as t:
            hub, _ = build_hub(Path(t) / "hub", poison=True)
            pubs, calls, problems, _ = ST.load_public_inputs(hub, None)
            self.assertEqual(problems, [])
            for p in pubs.values():
                self.assertEqual(set(p), set(ST.PUBLIC_KEYS))
            for _, r in calls:
                self.assertEqual(set(r), set(ST.RECORD_KEYS))

    def test_forbidden_paths_refused(self):
        for bad in ("/x/hub/data/hidden/main-cases.jsonl", "/x/hub/analysis/confirm/scored.jsonl"):
            with self.assertRaises(PermissionError):
                ST._guard_path(bad)

    def test_decide_does_not_mutate_inputs_and_is_deterministic(self):
        c = json.loads((HERE / "fixtures" / "controls-inputs.jsonl").read_text().splitlines()[0])
        before = copy.deepcopy(c)
        a = D.decide(c["prefix"], c["target_text"], c["registry"], c["registry_order"], c["raw"])
        b = D.decide(c["prefix"], c["target_text"], c["registry"], c["registry_order"], c["raw"])
        self.assertEqual(c, before)
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))


class Controls(unittest.TestCase):
    def test_controls_match_expected_labels(self):
        r = ig_controls.run()
        self.assertEqual(r["failures"], [])
        self.assertTrue(r["supported_matches_pass"])
        self.assertTrue(r["refusals_abstain"])
        self.assertTrue(r["no_refusal_passes"])


class Isolation(unittest.TestCase):
    def test_poisoned_metadata_and_bogus_hidden_labels_do_not_change_decisions(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            clean, n = build_hub(t / "clean")
            dirty, _ = build_hub(t / "dirty", poison=True, with_hidden=True)
            s1 = ig_decide.run("V1.24", clean, t / "o1", use_expected=False)
            s2 = ig_decide.run("V1.24", dirty, t / "o2", use_expected=False)
            self.assertEqual((s1["status"], s2["status"]), ("SEALED", "SEALED"))
            self.assertEqual(s1["n_decisions"], n)
            self.assertEqual(decisions_bytes(t / "o1"), decisions_bytes(t / "o2"))

    def test_runs_without_hidden_or_score_files(self):
        with tempfile.TemporaryDirectory() as t:
            hub, n = build_hub(Path(t) / "hub")
            self.assertFalse((hub / "data" / "hidden").exists())
            self.assertFalse((hub / "analysis").exists())
            s = ig_decide.run("V1.24", hub, Path(t) / "o", use_expected=False)
            self.assertEqual(s["status"], "SEALED")
            self.assertEqual(s["n_decisions"], n)


class Composition(unittest.TestCase):
    def test_composition_never_expands_acceptance_or_creates_exactness(self):
        for acc, exact, gp in itertools.product((False, True), repeat=3):
            c = ig_evaluate.compose(acc, exact, gp)
            self.assertLessEqual(c["final_accepted"], acc)
            self.assertLessEqual(c["usable_exact"], exact)
            self.assertEqual(c["final_accepted"], acc and gp)

    def test_only_pass_disposition_passes(self):
        for name in ("abstain", "compile_rejected", "no_compiled_fields", "identity_mismatch"):
            self.assertNotEqual(name, "pass")
        r = ig_controls.run()
        for row in r["rows"]:
            d = row["got"]["disposition"]
            self.assertIn(d, ("pass", "abstain", "compile_rejected", "no_compiled_fields", "identity_mismatch"))


class Completeness(unittest.TestCase):
    """Each corruption must make the decision stage INCOMPLETE (no SEAL), never shrink the denominator."""

    def _corrupt(self, mutate):
        with tempfile.TemporaryDirectory() as t:
            hub, _ = build_hub(Path(t) / "hub")
            mutate(hub)
            s = ig_decide.run("V1.24", hub, Path(t) / "o", use_expected=False)
            self.assertEqual(s["status"], "INCOMPLETE", s.get("problems"))
            self.assertFalse(list((Path(t) / "o").glob("SEAL-*.json")))
            return s["problems"]

    def _files(self, hub):
        return sorted((hub / "stages" / "main" / "calls").glob("*.json"))

    def test_missing_record(self):
        p = self._corrupt(lambda h: self._files(h)[0].unlink())
        self.assertTrue(any("missing record" in x for x in p))

    def test_duplicate_record(self):
        def m(h):
            f = self._files(h)[0]
            shutil.copy(f, f.with_name("dup__" + f.name))
        p = self._corrupt(m)
        self.assertTrue(any("duplicate record" in x for x in p))

    def test_extra_record(self):
        def m(h):
            f = self._files(h)[0]
            r = json.loads(f.read_text())
            r["call_id"] = r["call_id"] + "X"
            (f.parent / (r["call_id"].replace("|", "__") + ".json")).write_text(json.dumps(r))
        p = self._corrupt(m)
        self.assertTrue(any("extra record" in x for x in p))

    def test_non_ok_record(self):
        def m(h):
            f = self._files(h)[0]
            r = json.loads(f.read_text())
            r["status"] = "error"
            f.write_text(json.dumps(r))
        p = self._corrupt(m)
        self.assertTrue(any("non-ok" in x for x in p))

    def test_corrupt_record(self):
        p = self._corrupt(lambda h: self._files(h)[0].write_text("{not json"))
        self.assertTrue(any("corrupt record" in x for x in p))

    def test_prompt_hash_mismatch(self):
        def m(h):
            f = self._files(h)[0]
            r = json.loads(f.read_text())
            r["user_sha256"] = "0" * 64
            f.write_text(json.dumps(r))
        p = self._corrupt(m)
        self.assertTrue(any("prompt hash mismatch" in x for x in p))

    def test_duplicate_scheduled_call(self):
        def m(h):
            p = h / "data" / "main-calls.jsonl"
            lines = p.read_text().splitlines()
            p.write_text("\n".join(lines + [lines[0]]) + "\n")
        p = self._corrupt(m)
        self.assertTrue(any("duplicate scheduled call" in x for x in p))

    def test_duplicate_and_missing_target(self):
        def m(h):
            p = h / "data" / "public" / "main-targets.jsonl"
            lines = p.read_text().splitlines()
            p.write_text("\n".join(lines[1:] + [lines[1]]) + "\n")
        p = self._corrupt(m)
        self.assertTrue(any("duplicate target" in x for x in p))
        self.assertTrue(any("has no public target" in x for x in p))

    def test_expected_counts_enforced(self):
        with tempfile.TemporaryDirectory() as t:
            hub, _ = build_hub(Path(t) / "hub")
            s = ig_decide.run("V1.24", hub, Path(t) / "o", use_expected=True)
            self.assertEqual(s["status"], "INCOMPLETE")


if __name__ == "__main__":
    unittest.main()
