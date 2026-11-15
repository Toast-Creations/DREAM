"""CPU-only checks of CLAR-v1 paired development analysis; no model."""
import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import clar_analyze as CA  # noqa: E402
from tempo import kidconfdone as KD  # noqa: E402


def cell_rows(stem, family="F2", reception="immediate", fn=None, arrival=True):
    rows = []
    for act, directions in (("correction", CA.DIRECTIONS), ("arrival", ("na",))):
        if act == "arrival" and not arrival:
            continue
        for direction in directions:
            for history in CA.HISTORIES:
                for arm in CA.ARMS:
                    rows.append({"stem": stem, "family": family, "reception": reception, "act": act,
                                 "direction": direction, "history": history, "arm": arm,
                                 "exact": bool(fn(act, direction, history, arm)) if fn else False,
                                 "withdrawn_value_error": False, "incomplete": False})
    return rows


def fixture_call(cid="stem|correction|yes_to_no|A|KEEP_ORIG"):
    return {"call_id": cid, "user": "example prompt",
            "user_sha256": hashlib.sha256(b"example prompt").hexdigest()}


def fixture_record(call):
    return {"call_id": call["call_id"], "status": "ok", "complete": True, "user_sha256": call["user_sha256"],
            "model": {"revision": "9216db5781bf21249d130ec9da846c4624c16137", "quantization": "nf4",
                      "enable_thinking": False, "decoding": "greedy", "dtype": "bfloat16",
                      "load": {"devices": ["cuda:0"], "quantization": {"bnb_4bit_compute_dtype": "bfloat16",
                               "bnb_4bit_use_double_quant": True}}}, "max_new_tokens": 256, "attempts": 1}


def correction_fixture():
    case = {"records": [{"rid": "r1", "payload": {"field": "X.on_hand", "value": "yes"}},
                        {"kind": "correction", "payload": {"target": "r1", "field": "X.on_hand", "value": "no",
                                                             "valid_from": 2, "valid_to": None}}]}
    claims = {"events": [], "states": [{"field": "X.on_hand", "at": 2, "value": "no"}],
              "revisions": [{"target": "r1", "field": "X.on_hand", "value": "yes", "valid_from": 2, "valid_to": None}]}
    return case, claims


class PairedDevelopmentAnalysis(unittest.TestCase):
    def test_direction_and_history_weighting_and_f2_only(self):
        fn = lambda act, d, h, a: act == "correction" and d == "yes_to_no" and h == "A" and a == "KEEP_CLAR"
        rows = cell_rows("f2i", fn=fn) + cell_rows("f2d", reception="delayed", fn=fn)
        # Enriched/sentinel family sizes must never dilute the primary F2 estimand.
        for index in range(6):
            rows += cell_rows(f"f1-{index}", "F1", fn=lambda act, d, h, a: a == "KEEP_ORIG")
        res = CA.contrasts(rows, intervals=False)
        primary = res["correction|exact|F2|KEEP_clar_minus_orig"]
        self.assertEqual(primary["estimate"], .25)
        self.assertEqual(primary["targets_per_arm"], 8)
        self.assertEqual(primary["independent_stems"], 2)
        self.assertEqual(primary["paired_counts"], {"positive_only": 2, "neither": 6})
        self.assertEqual(res["correction|exact|F2|KEEP_clar_minus_orig|direction=yes_to_no"]["estimate"], .5)
        self.assertEqual(res["correction|exact|F2|KEEP_clar_minus_orig|direction=no_to_yes"]["estimate"], 0)

    def test_whole_stems_not_independent_history_rows_and_shared_interaction(self):
        def first(act, direction, history, arm):
            return arm.endswith("CLAR")
        def second(act, direction, history, arm):
            return arm.endswith("ORIG")
        rows = cell_rows("one", fn=first) + cell_rows("two", fn=second)
        res = CA.contrasts(rows, B=400, seed=4)
        primary = res["correction|exact|F2|KEEP_clar_minus_orig"]
        # Each stem's 4 correction outputs move together, so draws span -1 to 1.
        self.assertEqual(primary["reference_95_interval"], [-1, 1])
        # KEEP and SUB effects are identical inside EVERY stem; interaction is 0
        # in every resample, which independent arm bootstraps would not preserve.
        self.assertEqual(res["correction|exact|F2|interaction"]["reference_95_interval"], [0, 0])
        self.assertEqual(res, CA.contrasts(rows, B=400, seed=4))

    def test_nested_arrival_panel_has_fixed_denominator(self):
        rows = cell_rows("selected", fn=lambda act, d, h, a: a == "KEEP_CLAR")
        rows += cell_rows("not-selected", arrival=False)
        res = CA.contrasts(rows, B=200, seed=5)
        guard = res["arrival|exact|F2|KEEP_clar_minus_orig"]
        self.assertEqual(guard["targets_per_arm"], 2)
        self.assertEqual(guard["independent_stems"], 1)
        self.assertEqual(guard["reference_95_interval"], [1, 1])

    def test_incomplete_or_mismatched_cells_cannot_enter_intervals(self):
        rows = cell_rows("one")
        rows[0]["incomplete"] = True
        with self.assertRaises(ValueError):
            CA.contrasts(rows, B=10)
        rows = cell_rows("one")
        rows.pop(0)
        with self.assertRaises(ValueError):
            CA.contrasts(rows, B=10)


class RawRevisionDiagnostics(unittest.TestCase):
    def test_raw_old_value_and_correct_state_pattern(self):
        case, claims = correction_fixture()
        d = CA.revision_diagnostics(claims, case)
        self.assertTrue(d["withdrawn_value_error"])
        self.assertTrue(d["state_correct_revision_withdrawn"])
        self.assertTrue(d["raw_revision_interval_ok"])
        self.assertFalse(d["raw_revision_value_correct"])
        self.assertTrue(d["simultaneous_value_conflict"])
        claims["states"][0]["at"] = 7
        self.assertFalse(CA.revision_diagnostics(claims, case)["state_correct_revision_withdrawn"])
        claims["states"][0]["at"] = 2
        # This predicate is symmetric when correction direction is reversed.
        case["records"][0]["payload"]["value"] = "no"
        case["records"][-1]["payload"]["value"] = "yes"
        claims["revisions"][0]["value"] = "no"
        claims["states"][0]["value"] = "yes"
        self.assertTrue(CA.revision_diagnostics(claims, case)["withdrawn_value_error"])

    def test_absent_multiple_wrong_field_target_separate_from_primary_error(self):
        case, claims = correction_fixture()
        variants = [(None, "invalid_extraction")]
        v = copy.deepcopy(claims); v["revisions"] = []; variants.append((v, "absent"))
        v = copy.deepcopy(claims); v["revisions"] *= 2; variants.append((v, "multiple"))
        v = copy.deepcopy(claims); v["revisions"][0]["field"] = "Y.on_hand"; variants.append((v, "wrong_field"))
        v = copy.deepcopy(claims); v["revisions"][0]["target"] = "r2"; variants.append((v, "wrong_target"))
        for variant, category in variants:
            with self.subTest(category=category):
                d = CA.revision_diagnostics(variant, case)
                self.assertEqual(d["revision_category"], category)
                self.assertFalse(d["withdrawn_value_error"])

    def test_half_open_intervals_empty_intervals_and_points(self):
        _, claims = correction_fixture()
        claims["revisions"][0]["valid_to"] = 7
        claims["states"][0]["at"] = 7
        self.assertFalse(CA.simultaneous_conflict(claims))
        claims["states"][0]["at"] = 6
        self.assertTrue(CA.simultaneous_conflict(claims))
        claims["revisions"][0]["valid_to"] = 2
        claims["states"][0]["at"] = 2
        self.assertFalse(CA.simultaneous_conflict(claims))
        claims["revisions"] = []
        claims["states"].append({"field": "X.on_hand", "at": 3, "value": "yes"})
        self.assertFalse(CA.simultaneous_conflict(claims))
        claims["states"][-1]["at"] = 2
        self.assertTrue(CA.simultaneous_conflict(claims))


class CollectionCompleteness(unittest.TestCase):
    def test_missing_extra_duplicate_nonok_and_prompt_mutations(self):
        call = fixture_call()
        record = fixture_record(call)
        self.assertEqual(CA.check_records([call], {call["call_id"]: record}), [])
        self.assertTrue(CA.check_records([call], {}))
        self.assertTrue(CA.check_records([call], {call["call_id"]: record, "extra": record}))
        self.assertTrue(CA.check_records([call], {call["call_id"]: record}, [call["call_id"]]))
        for key, value in (("status", "failed"), ("user_sha256", "changed"), ("attempts", 2), ("complete", False)):
            changed = dict(record, **{key: value})
            self.assertTrue(CA.check_records([call], {call["call_id"]: changed}))
        changed = dict(call, user="tampered prompt")
        self.assertTrue(CA.check_records([changed], {call["call_id"]: record}))

    def test_crossing_requires_both_directions_histories_and_all_four_arms(self):
        pubs, calls = [], []
        for row in cell_rows("one"):
            target = "|".join((row["stem"], row["act"], row["direction"], row["history"]))
            if not any(p["target"] == target for p in pubs):
                pubs.append(dict(row, target=target, group=row["stem"]))
            calls.append(fixture_call(target+"|"+row["arm"]))
        self.assertEqual(CA.check_crossing(pubs, calls), [])
        self.assertTrue(CA.check_crossing(pubs, calls[:-1]))
        selected = [p for p in pubs if p["direction"] != "no_to_yes"]
        self.assertTrue(CA.check_crossing(selected, [c for c in calls if "no_to_yes" not in c["call_id"]]))

    def test_frozen_current_bytes_and_canonical_plan_hash_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            hub = Path(tmp)
            frozen = {"source_sha256": "source", "analysis_plan_sha256": KD.plan_sha256(CA.DEFAULT_PLAN)}
            for section in ("design", "config", "data", "phase0"):
                (hub / section).mkdir()
                path = hub / section / "frozen.json"
                path.write_text("{}")
                frozen[section] = {"frozen.json": CA.sha(path)}
            with patch.object(CA, "release_source_hash", return_value="source"):
                self.assertEqual(CA.freeze_problems(hub, frozen, CA.DEFAULT_PLAN), [])
                (hub / "data/frozen.json").write_text('{"changed":true}')
                self.assertIn("frozen file mismatch: data/frozen.json", CA.freeze_problems(hub, frozen, CA.DEFAULT_PLAN))
                frozen["analysis_plan_sha256"] = "wrong"
                self.assertIn("analysis-plan hash differs from freeze", CA.freeze_problems(hub, frozen, CA.DEFAULT_PLAN))

    def test_plan_cannot_enable_qualification_or_change_bootstrap(self):
        CA.validate_plan(CA.DEFAULT_PLAN)
        for field, value in (("qualification", True), ("B", 999), ("primary_family", "all")):
            with self.assertRaises(ValueError):
                CA.validate_plan(dict(CA.DEFAULT_PLAN, **{field: value}))


if __name__ == "__main__":
    unittest.main()
