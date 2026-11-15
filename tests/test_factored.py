"""Hand-worked fixtures for the V1.18.0 compiler and the common meaning score (brief section 4). Test-only pool."""
import copy
import difflib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from tempo import ctxablate as CA, factored as FA, freshgen as FG, prose  # noqa: E402
from contract_validate import score_record  # noqa: E402

FG.CONS["factest"] = "bcdfghk"


class Factored(unittest.TestCase):
    def setUp(self):
        self.w, self.out, self.rs, self.meta = FA.build_group("t", 777, ("D", 3, "P_first"), "lure_G", "factest", 4)
        self.reg = CA.registry(self.w, self.out["arrival"])
        self.g = {v: CA.public(r)[-1] for v, r in self.out.items()}
        self.text = {v: prose.prose_line(self.w, r[-1], self.rs) for v, r in self.out.items()}

    def run_(self, v, obj):
        rep, tr = FA.compile_reply(json.dumps(obj), self.reg)
        return score_record(rep, self.g[v], self.text[v])["denotation_equal"], rep, tr

    def base(self, v):
        return FA.canonical_factored(self.g[v])

    def test_01_event_plus_result_state_is_the_event(self):
        ok, rep, tr = self.run_("arrival", self.base("arrival"))
        self.assertTrue(ok)
        self.assertEqual([x["rule"] for x in tr["reduce"]], ["R2"])
        o = self.base("arrival"); o["states"] = []
        self.assertTrue(self.run_("arrival", o)[0])
        o["events"][0]["from"] = None
        self.assertTrue(self.run_("arrival", o)[0])  # unstated stock prior: null credited (existing convention)

    def test_02_state_only_arrival_is_not_exact(self):
        o = self.base("arrival"); o["events"] = []
        ok, rep, _ = self.run_("arrival", o)
        self.assertFalse(ok)
        self.assertEqual(rep["type"], "state")

    def test_03_removal_versus_retraction(self):
        o = self.base("removal"); rv = {"target": "r01", "field": self.meta["P"], "value": "no", "valid_from": self.g["removal"]["event_at"], "valid_to": None}
        o["events"], o["states"], o["revisions"] = [], [], [rv]
        self.assertFalse(self.run_("removal", o)[0])
        c = self.base("correction"); p = self.g["correction"]["payload"]
        c["revisions"] = []
        c["events"] = [{"field": p["field"], "at": self.g["correction"]["received_at"], "from": None, "to": p["value"]}]
        self.assertFalse(self.run_("correction", c)[0])
        self.assertTrue(self.run_("correction", self.base("correction"))[0])

    def test_04_wrong_entity_with_exact_quote(self):
        o = self.base("arrival")
        other = next(f for f in self.reg if f.endswith(".on_hand") and f != self.meta["P"])
        for x in o["events"] + o["states"]:
            x["field"] = other
        o["evidence"] = self.text["arrival"]
        self.assertFalse(self.run_("arrival", o)[0])

    def test_05_contradictory_or_extra_claims(self):
        o = self.base("arrival")
        o["revisions"] = [{"target": "r01", "field": self.meta["P"], "value": "yes", "valid_from": 1, "valid_to": None}]
        ok, rep, tr = self.run_("arrival", o)
        self.assertFalse(ok); self.assertEqual(tr["code"], "mixed_acts")
        o = self.base("arrival"); o["states"][0]["value"] = "no"
        ok, rep, tr = self.run_("arrival", o)
        self.assertFalse(ok); self.assertEqual(tr["code"], "mixed_acts")
        o = self.base("observation"); o["states"].append({"field": self.w.slot_f, "at": o["states"][0]["at"], "value": "empty"})
        self.assertFalse(self.run_("observation", o)[0])  # unsupported extra state counts as an error

    def test_06_missing_or_invalid_times(self):
        o = self.base("arrival"); del o["events"][0]["at"]
        self.assertEqual(self.run_("arrival", o)[2]["code"], "invalid_assertion")
        o = self.base("arrival"); o["events"][0]["at"] = "5"
        ok, rep, tr = self.run_("arrival", o)
        self.assertTrue(any(x["rule"] == "N2" for x in tr["norm"]))
        o = self.base("correction"); o["revisions"][0]["valid_from"] = "soon"
        self.assertEqual(self.run_("correction", o)[2]["code"], "invalid_assertion")

    def test_07_redundant_duplicates_and_revision_state(self):
        o = self.base("observation"); o["states"] = o["states"] * 2
        ok, rep, tr = self.run_("observation", o)
        self.assertTrue(ok); self.assertEqual([x["rule"] for x in tr["reduce"]], ["R1"])
        c = self.base("correction"); r = c["revisions"][0]
        c["states"] = [{"field": r["field"], "at": r["valid_from"], "value": r["value"]}]
        ok, rep, tr = self.run_("correction", c)
        self.assertTrue(ok); self.assertEqual([x["rule"] for x in tr["reduce"]], ["R3"])
        c["states"] = [{"field": r["field"], "at": self.g["correction"]["received_at"], "value": r["value"]}]
        self.assertEqual(self.run_("correction", c)[2]["code"], "mixed_acts")  # a reception-time state is not dropped

    def test_08_empty_and_prompt_diff(self):
        o = self.base("arrival"); o["events"] = []; o["states"] = []
        self.assertEqual(self.run_("arrival", o)[2]["code"], "empty")
        ex = CA.full_prompt(self.w, self.out["arrival"], self.rs)
        fa = FA.factored_prompt(ex)
        d = [x for x in difflib.ndiff(ex.splitlines(), fa.splitlines()) if x[:1] in "+-"]
        self.assertEqual(sum(x.startswith("-") for x in d), 5)
        self.assertEqual(sum(x.startswith("+") for x in d), 5)
        self.assertEqual(ex.split("New record to convert:")[0], fa.split("New record to convert:")[0])
        self.assertNotIn("arrived", "\n".join(FA.FACT_QUERY + FA.FACT_REPLY))


if __name__ == "__main__":
    unittest.main()
