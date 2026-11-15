"""No-model fixtures for V1.19.0 HOLD-v1 construction and HOLD-EVAL-v1 scoring (test-only pool)."""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tempo import factored as FA, freshgen as FG, holdeval as HE, holdout as HO  # noqa: E402

FG.CONS["holdtest"] = "bcdfghk"


def group(fam, rec="delayed", bits=(1, 1, 1)):
    for att in range(80):
        try:
            return HO.build_group("t", 3000 + att, fam, rec, bits, "holdtest")
        except AssertionError:
            continue
    raise AssertionError("cannot build")


class Holdout(unittest.TestCase):
    def sc(self, g, act, hist, obj, stop=None):
        c = g["cases"][(act, hist)]
        return HE.score(None if obj is None else json.dumps(obj), c, g["world"], HO.registry(g["world"], c), stop)[0]

    def canon(self, g, act, hist):
        c = g["cases"][(act, hist)]
        return dict(FA.canonical_factored(HO.public(c)[-1]), evidence=c["text"][-25:])

    def test_01_construction_invariants(self):
        for fam in HO.FAMILIES + HO.CAL_FAMILIES:
            g = group(fam)
            for act in HO.ACTS:
                a, b = g["cases"][(act, "A")], g["cases"][(act, "B")]
                self.assertNotEqual(a["field"], b["field"])
                if fam != "CN_explicit_name":
                    self.assertEqual(a["text"], b["text"])
                    self.assertEqual(HO.prompt(g["world"], a, g["render_seed"]).split("New record to convert:")[1],
                                     HO.prompt(g["world"], b, g["render_seed"]).split("New record to convert:")[1])
                self.assertEqual(HO.registry(g["world"], a), HO.registry(g["world"], b))
                self.assertIn(FA.FACT_REPLY[1], HO.prompt(g["world"], a, g["render_seed"]))

    def test_02_canonical_exact_and_replay(self):
        for fam in HO.FAMILIES:
            for bits in ((0, 0, 0), (1, 1, 1)):
                g = group(fam, "immediate", bits)
                for (act, hist), c in g["cases"].items():
                    s = self.sc(g, act, hist, self.canon(g, act, hist))
                    self.assertTrue(s["exact"] and s["replay_ok"], (fam, act, hist, s["replay"], s["replay_ref"]))

    def test_03_swapped_referent_and_wrong_field_with_correct_quote(self):
        g = group("F2_slot_join")
        o = self.canon(g, "arrival", "B")  # history B's canonical meaning scored against history A
        o["evidence"] = g["cases"][("arrival", "A")]["text"][-40:]
        s = self.sc(g, "arrival", "A", o)
        self.assertFalse(s["exact"]); self.assertFalse(s["bound_ok_raw"]); self.assertTrue(s["quote_valid"])
        o = self.canon(g, "arrival", "A")
        slot = g["world"].slot_f
        for x in o["events"] + o["states"]:
            x["field"] = slot
            x["to" if "to" in x else "value"] = g["cases"][("arrival", "A")]["selected"]
            if "from" in x:
                x["from"] = None
        s = self.sc(g, "arrival", "A", o)
        self.assertFalse(s["exact"]); self.assertTrue(s.get("slot_field_claimed"))

    def test_04_stated_prior_required_unstated_null_ok(self):
        g = group("F1_two_hop", bits=(0, 1, 0))
        o = self.canon(g, "arrival", "A"); o["events"][0]["from"] = None
        self.assertTrue(g["cases"][("arrival", "A")]["prior_stated"])
        self.assertFalse(self.sc(g, "arrival", "A", o)["exact"])
        g2 = group("F1_two_hop", bits=(0, 0, 0))
        o = self.canon(g2, "arrival", "A"); o["events"][0]["from"] = None
        self.assertTrue(self.sc(g2, "arrival", "A", o)["exact"])

    def test_05_revision_target_and_finite_boundaries(self):
        g = group("F4_measurement_order", bits=(1, 0, 1))
        c = g["cases"][("correction", "A")]
        self.assertIsNotNone(c["records"][-1]["payload"]["valid_to"])
        o = self.canon(g, "correction", "A"); o["revisions"][0]["valid_to"] = None
        s = self.sc(g, "correction", "A", o)
        self.assertFalse(s["exact"]); self.assertFalse(s["rev_to_ok"]); self.assertTrue(s["rev_from_ok"])
        o = self.canon(g, "correction", "A"); o["revisions"][0]["target"] = "r01" if o["revisions"][0]["target"] != "r01" else "r02"
        s = self.sc(g, "correction", "A", o)
        self.assertFalse(s["exact"])
        o = self.canon(g, "correction", "A"); o["revisions"][0]["valid_from"] += 1
        self.assertFalse(self.sc(g, "correction", "A", o)["exact"])

    def test_06_unsupported_extra_and_state_only_event(self):
        g = group("F3_historical_occupant", bits=(0, 0, 0))
        o = self.canon(g, "observation", "A")
        o["states"].append({"field": g["world"].slot_f, "at": o["states"][0]["at"], "value": "empty"})
        self.assertFalse(self.sc(g, "observation", "A", o)["exact"])
        o = self.canon(g, "removal", "A"); o["events"] = []
        s = self.sc(g, "removal", "A", o)
        self.assertFalse(s["exact"]); self.assertTrue(s["state_only_event_accepted"] or not s["accepted"])
        self.assertTrue(s["endpoint_ok"])
        o = self.canon(g, "arrival", "A")
        o["revisions"] = [{"target": "r01", "field": g["cases"][("arrival", "A")]["field"], "value": "yes",
                           "valid_from": 1, "valid_to": None}]
        s = self.sc(g, "arrival", "A", o)
        self.assertTrue(s["false_revision_raw"]); self.assertFalse(s["false_revision_accepted"])

    def test_07_reception_and_truncation(self):
        g = group("C1_one_hop", "delayed", (0, 0, 0))
        c = g["cases"][("arrival", "A")]
        self.assertEqual(c["recv"], c["t_event"] + 2)
        o = self.canon(g, "arrival", "A"); o["received_at"] = c["t_event"]
        s = self.sc(g, "arrival", "A", o)
        self.assertFalse(s["exact"]); self.assertFalse(s["reception_ok"])
        self.assertFalse(self.sc(g, "arrival", "A", self.canon(g, "arrival", "A"), stop="length")["exact"])
        self.assertFalse(self.sc(g, "arrival", "A", None)["exact"])


if __name__ == "__main__":
    unittest.main()
