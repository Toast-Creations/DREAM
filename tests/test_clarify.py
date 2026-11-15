"""CPU-only semantic, factorial, public-input and schedule fixtures for V1.23."""
import collections
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tempo import clarify as CL, factored as FA, holdeval as HE, holdout as HO, kidconfgen as KG
from tempo.worlds import YES, NO


class ClarificationPanel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.panel = CL.generate()

    def test_allocation_and_balances(self):
        p = self.panel["main"]["plan"]
        self.assertEqual(len(p), 32)
        self.assertEqual(collections.Counter(x["family"] for x in p),
                         {"F2_slot_join": 24, "F1_two_hop": 4, "F3_historical_occupant": 4})
        self.assertEqual(sum(x["arrival_selected"] for x in p), 16)
        for reception in HO.RECEPTION:
            f2 = [x for x in p if x["family"] == "F2_slot_join" and x["reception"] == reception]
            self.assertEqual(collections.Counter(tuple(x["bits"]) for x in f2),
                             {(0, 0, 0): 3, (1, 0, 0): 3, (0, 1, 0): 3, (1, 1, 0): 3})
            self.assertEqual(sum(x["arrival_selected"] for x in f2), 6)
        arrivals = [x for x in p if x["family"] == "F2_slot_join" and x["arrival_selected"]]
        self.assertEqual(set(collections.Counter(tuple(x["bits"]) for x in arrivals).values()), {3})
        for part, count in (("main", 640), ("smoke", 48)):
            calls = self.panel[part]["calls"]
            self.assertEqual(len(calls), count)
            self.assertEqual(len({c["call_id"] for c in calls}), count)
            self.assertEqual(collections.Counter(c["arm"] for c in calls), {a: count // 4 for a in CL.ARMS})
        self.assertEqual(collections.Counter(c["direction"] for c in self.panel["main"]["calls"]),
                         {"yes_to_no": 256, "no_to_yes": 256, "na": 128})

    def test_exactly_one_sentence_and_public_only(self):
        for pub in self.panel["main"]["public"]:
            prompts, ledger = CL.prompts_from_public(pub)
            for representation in ("SUB", "KEEP"):
                original, clarified = prompts[representation + "_ORIG"], prompts[representation + "_CLAR"]
                self.assertEqual(clarified.replace("\n" + CL.CLARIFICATION, ""), original)
                self.assertEqual(clarified.count(CL.CLARIFICATION), 1)
            poisoned = copy.deepcopy(pub)
            poisoned.update(gold_field="poison.on_hand", case={"records": []}, identity={"field": "poison"})
            self.assertEqual(CL.prompts_from_public(poisoned), (prompts, ledger))

    def test_pairing_and_direction_consistency(self):
        hids = {r["target"]: r for r in self.panel["main"]["hidden"]}
        publics = {r["target"]: r for r in self.panel["main"]["public"]}
        for spec in self.panel["main"]["plan"]:
            for direction in CL.DIRECTIONS:
                a = hids[f"{spec['stem']}|correction|{direction}|A"]
                b = hids[f"{spec['stem']}|correction|{direction}|B"]
                self.assertEqual(a["case"]["text"], b["case"]["text"])
                self.assertNotEqual(a["gold_field"], b["gold_field"])
                for h in (a, b):
                    case, gold = h["case"], h["case"]["records"][-1]
                    old = next(x for x in case["records"] if x["rid"] == gold["payload"]["target"])
                    expected_old, expected_new = (YES, NO) if direction == "yes_to_no" else (NO, YES)
                    self.assertEqual(old["payload"]["value"], expected_old)
                    self.assertEqual(gold["payload"]["value"], expected_new)
                    self.assertIsNone(gold["payload"]["valid_to"])
                    self.assertIn("it was not on hand." if expected_new == NO else "it was on hand.", case["text"])
                    w = HO._world(h["world_seed"], h["pool"])[0]
                    self.assertEqual(HO.prompt(w, case, h["render_seed"]), publics[h["target"]]["base_prompt"])
                    if h["family"] == "F1_two_hop":
                        rendered = next(e["raw_text"] for e in publics[h["target"]]["prefix"] if e["record_id"] == old["rid"])
                        self.assertTrue(rendered.endswith(" is on hand." if expected_old == YES else " is not on hand."))
            for history in HO.HISTORIES:
                old = hids[f"{spec['stem']}|correction|yes_to_no|{history}"]["case"]
                new = hids[f"{spec['stem']}|correction|no_to_yes|{history}"]["case"]
                self.assertEqual([(r["rid"], r["event_at"], r["received_at"]) for r in old["records"]],
                                 [(r["rid"], r["event_at"], r["received_at"]) for r in new["records"]])
                self.assertEqual(old["desc"], new["desc"])

    def test_canonical_exact_and_value_mutations_inexact(self):
        # Cover every family, reception, direction and history. Compiler/evaluator are unchanged imports.
        for h in self.panel["main"]["hidden"]:
            case = h["case"]
            w = HO._world(h["world_seed"], h["pool"])[0]
            reg = HO.registry(w, case)
            reply = FA.canonical_factored(case["records"][-1])
            score, _, _ = HE.score(json.dumps(reply), case, w, reg, "eos")
            self.assertTrue(score["exact"], h["target"])
            bad = copy.deepcopy(reply)
            if h["act"] == "correction":
                value = bad["revisions"][0]["value"]
                bad["revisions"][0]["value"] = NO if value == YES else YES
            else:
                bad["events"][0]["to"] = NO
            score, _, _ = HE.score(json.dumps(bad), case, w, reg, "eos")
            self.assertFalse(score["exact"], h["target"])

    def test_schedule_units_and_reproducibility(self):
        for part in self.panel.values():
            calls = part["calls"]
            for i in range(0, len(calls), 8):
                unit = calls[i:i + 8]
                self.assertEqual(len({(c["stem"], c["act"], c["direction"]) for c in unit}), 1)
                self.assertEqual({c["arm"] for c in unit}, set(CL.ARMS))
                for j in range(0, 8, 2):
                    self.assertEqual([c["history"] for c in unit[j:j + 2]], ["A", "B"])
                    self.assertEqual(unit[j]["arm"], unit[j + 1]["arm"])
        repeated = CL.generate()
        self.assertEqual(repeated, self.panel)

    def test_historical_disjointness_rejects_collision(self):
        p = self.panel["main"]["public"][0]["base_prompt"]
        s = self.panel["main"]["hidden"][0]["world_seed"]
        with self.assertRaisesRegex(AssertionError, "historical panel"):
            CL.generate(historical_prompts=[p])
        with self.assertRaisesRegex(AssertionError, "world seed"):
            CL.generate(historical_seeds=[s])

    def test_clarification_fails_closed_on_changed_schema(self):
        with self.assertRaises(AssertionError):
            CL.clarify_prompt("no FACT schema")
        pub = self.panel["main"]["public"][0]
        prompt = CL.prompts_from_public(pub)[0]["SUB_CLAR"]
        with self.assertRaises(AssertionError):
            CL.clarify_prompt(prompt)


if __name__ == "__main__":
    unittest.main()
