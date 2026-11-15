"""No-model checks for V1.16.0 (brief section 3). Fixture worlds use a test-only pool."""
import copy
import difflib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from tempo import assertions as A, freshgen as FG, nullprior as NP, text_channel as TC, textdep as TD  # noqa: E402
from tempo.engine import NO, YES  # noqa: E402
from contract_validate import score_record  # noqa: E402
from nul_evaluate import record_diag  # noqa: E402

POOL, SEED = "nultest", 9191
FG.CONS[POOL] = "bcdfgjk"
fx = lambda *r: tuple(r) + (("fx", "fx"),)
ARRIVE = fx("n-a1", {"T": ("empty", "ver"), "G": ("yes", "ver")}, {"S2": ("empty", "ver"), "D": ("yes", "ver")},
            [("on_hand", "D", "yes", "no")], [])
MOVE = fx("n-d1", ("B", "ver"), ("YOU", "ver"), [("EA", "B", "YOU")], [])


def make(domain, row):
    for att in range(80):
        try:
            w, pub, hid = NP.build(row, domain, SEED + att, POOL)
            recs, texts, prompts, regs = NP.text_inputs(w, hid)
            if any(r["kind"] == "change" for r in recs):
                return w, pub, hid, recs, texts, prompts, regs
        except AssertionError:
            continue
    raise AssertionError("cannot build")


def first(recs, pred):
    return next(i for i, r in enumerate(recs) if pred(r))


class NullPrior(unittest.TestCase):
    def setUp(self):
        self.a = make("assembly", ARRIVE)
        self.d = make("delivery", MOVE)

    def _stock_change(self, recs):
        return first(recs, lambda r: r["kind"] == "change" and r["payload"]["field"].endswith(".on_hand"))

    def test_01_null_prior_event_maps_and_applies(self):
        w, pub, hid, recs, texts, prompts, regs = self.a
        i = self._stock_change(recs)
        raws = TD.perfect_raws(recs)
        r = copy.deepcopy(recs[i]); r["payload"]["from"] = None
        raws[i] = json.dumps(r)
        rep, log = TC.adapt(raws[i], regs[i])
        self.assertIsNotNone(rep)
        self.assertIsNone(rep["assertions"][0]["from"])
        ch = TD.build_channel("x", pub["spec"], raws, regs, texts, [x["received_at"] for x in recs])
        self.assertTrue(all(x["accepted"] for x in ch["rows"]))
        perf = TD.build_channel("x", pub["spec"], TD.perfect_raws(recs), regs, texts, [x["received_at"] for x in recs])
        from tempo import recovery as R
        f = recs[i]["payload"]["field"]
        v1 = R.engine_from(TD.text_copy(pub), ch, "a").view("current", 12)
        v2 = R.engine_from(TD.text_copy(pub), perf, "b").view("current", 12)
        self.assertEqual(v1["op_per_field"][f], v2["op_per_field"][f])
        self.assertNotIn(f, v1["conflict_fields"])

    def test_02_scorer_credits_null_prior_stock_event(self):
        w, pub, hid, recs, texts, *_ = self.a
        i = self._stock_change(recs)
        r = copy.deepcopy(recs[i]); r["payload"]["from"] = None
        self.assertTrue(score_record(A.from_v02(r), recs[i], texts[i])["denotation_equal"])

    def test_03_stated_prior_still_required(self):
        w, pub, hid, recs, texts, *_ = self.d
        i = first(recs, lambda r: r["kind"] == "change" and r["payload"]["field"].endswith(".location"))
        self.assertIn(recs[i]["payload"]["from"], texts[i])
        r = copy.deepcopy(recs[i]); r["payload"]["from"] = None
        self.assertFalse(score_record(A.from_v02(r), recs[i], texts[i])["denotation_equal"])
        self.assertEqual(record_diag(A.from_v02(r), recs[i], texts[i])["prior"], "dropped_explicit")

    def test_04_missing_from_key_unmapped_uncertain_unchanged(self):
        w, pub, hid, recs, texts, prompts, regs = self.a
        i = self._stock_change(recs)
        r = copy.deepcopy(recs[i]); del r["payload"]["from"]
        rep, log = TC.adapt(json.dumps(r), regs[i])
        self.assertIsNone(rep)
        self.assertIsNotNone(log["unmapped"])
        u = {"rid": "r09", "kind": "uncertain_change", "status": "verified", "event_at": 3, "received_at": 3,
             "payload": {"field": recs[i]["payload"]["field"], "options": [YES, NO]}}
        rep2, _ = TC.adapt(json.dumps(u), regs[i])
        self.assertIsNotNone(rep2)  # M1 unchanged

    def test_05_prompt_difference_is_only_the_declared_clarification(self):
        for w, pub, hid, recs, texts, prompts, regs in (self.a, self.d):
            self.assertEqual(prompts, TC.prompts(w, {"records_v02": recs, "seed": hid["seed"]}))  # ORIGINAL = 1.15.1
            for u in prompts:
                n = NP.null_prompt(u)
                d = [x for x in difflib.ndiff(u.splitlines(), n.splitlines()) if x[:1] in "+-"]
                self.assertEqual(d, ["- " + NP.PAYLOAD_LINE, "+ " + NP.NULL_PAYLOAD_LINE, "+ " + NP.CLARIFICATION])
                for t in texts:
                    self.assertEqual(u.count(t), n.count(t))

    def test_06_errors_visible_with_exact_quote(self):
        w, pub, hid, recs, texts, prompts, regs = self.a
        i = self._stock_change(recs)
        g = recs[i]
        slot = next(f for f in regs[i] if f.endswith(".part"))
        wrong = {"rid": g["rid"], "kind": "correction", "status": "verified", "event_at": None,
                 "received_at": g["received_at"], "payload": {"target": "r01", "field": slot, "value": "empty",
                                                              "valid_from": g["event_at"], "valid_to": None},
                 "evidence": texts[i]}
        rep, _ = TC.adapt(json.dumps(wrong), regs[i])
        dg = record_diag(rep, g, texts[i])
        self.assertFalse(dg["denotation_equal"] or dg["field_attribution_ok"] or dg["kind_correct"])
        state = {"rid": g["rid"], "kind": "initial", "status": "verified", "event_at": g["event_at"],
                 "received_at": g["received_at"], "payload": {"assign": {g["payload"]["field"]: g["payload"]["to"]}},
                 "evidence": texts[i]}
        rep, _ = TC.adapt(json.dumps(state), regs[i])
        dg = record_diag(rep, g, texts[i])
        self.assertTrue(dg["field_attribution_ok"])
        self.assertFalse(dg["kind_correct"] or dg["denotation_equal"])

    def test_07_families_and_ids(self):
        self.assertEqual(len(NP.ROWS), 96)
        self.assertEqual(len({r[0] for _, r in NP.ROWS}), 96)
        self.assertEqual(NP.family("a12i3"), "a12")
        self.assertEqual(len({NP.family(r[0]) for _, r in NP.ROWS}), 24)


if __name__ == "__main__":
    unittest.main()
