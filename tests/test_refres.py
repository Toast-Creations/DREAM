"""No-model fixtures for V1.20.0 REFRES-v1 (Codex review 01 items 1-6 plus parser, rewrite and bypass checks).
Records are hand-written in the frozen public template forms; nothing is generated from hidden cases."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tempo import refres as RR  # noqa: E402

REG = ["Tolo.part", "Alpa.on_hand", "Sidi.part", "Beta.on_hand", "Gama.on_hand"]


def pi(records, target):
    return RR.PublicInput.make([{"record_id": r, "raw_text": t} for r, t in records], target, REG)


def res(records, target):
    d = RR.detect(target)
    assert d["route"] == "resolve", d
    return RR.resolve_det(pi(records, target), d)


HIST = "Message r09, received at time 9: it is verified that at time 9 the part that slot Tolo held at time {t} was delivered to you, so it is now on hand."
MEAS = "Message r09, received at time 9: a confirmed check shows that at time 9 the part whose stock check, of r01 and r02, was measured earlier is on hand."
ONE = "Message r09, received at time 9: a confirmed check shows that at time 9 the part whose stock was checked in r01 is on hand."


class RefRes(unittest.TestCase):
    def test_01_event_substring_is_not_a_stock_check(self):
        recs = [("r01", "Message r01, received at time 3: it is verified that at time 3 part Alpa was delivered to you, so it is now on hand."),
                ("r02", "Message r02, received at time 4: a confirmed check shows that at time 2 part Beta is on hand.")]
        r = res(recs, MEAS)
        self.assertIsNone(r["field"]); self.assertEqual(r["reason"], "wrong_predicate")
        self.assertIsNone(res(recs, ONE)["field"])

    def test_02_observations_are_constraints_not_setters(self):
        recs = [("r01", "Message r01, received at time 1: a confirmed check shows that at time 1 slot Tolo holds part Alpa."),
                ("r02", "Message r02, received at time 3: a confirmed check shows that at time 3 slot Tolo holds part Beta.")]
        r = res(recs, HIST.format(t=3))
        self.assertIsNone(r["field"]); self.assertEqual(r["reason"], "inconsistent_evidence")

    def test_03_transition_priors_are_checked(self):
        recs = [("r01", "Message r01, received at time 1: a confirmed check shows that at time 1 slot Tolo holds part Alpa."),
                ("r02", "Message r02, received at time 3: confirmed (verified) event: at time 3, another technician swapped part Beta in slot Tolo for part Gama, taking Beta away.")]
        self.assertEqual(res(recs, HIST.format(t=4))["reason"], "prior_mismatch")
        recs2 = [("r01", "Message r01, received at time 1: a confirmed check shows that at time 1 slot Tolo holds part Alpa."),
                 ("r02", "Message r02, received at time 3: confirmed (verified) event: at time 3, another technician pulled part Beta out of slot Tolo and took it away, leaving the slot empty.")]
        self.assertEqual(res(recs2, HIST.format(t=4))["reason"], "prior_mismatch")
        ok = [("r01", "Message r01, received at time 1: confirmed (verified) event: at time 1, another technician fitted part Alpa into slot Tolo, using their own stock."),
              ("r02", "Message r02, received at time 3: confirmed (verified) event: at time 3, another technician swapped part Alpa in slot Tolo for part Beta, taking Alpa away.")]
        self.assertEqual(res(ok, HIST.format(t=2))["field"], "Alpa.on_hand")   # historical, not the latest occupant
        self.assertEqual(res(ok, HIST.format(t=3))["field"], "Beta.on_hand")

    def test_04_relevant_unsupported_or_correction_reports_refuse(self):
        base = [("r01", "Message r01, received at time 1: confirmed (verified) event: at time 1, another technician fitted part Alpa into slot Tolo, using their own stock.")]
        prov = base + [("r02", "Message r02, received at time 2: a provisional report, not yet verified, states that as of time 2 slot Tolo holds part Beta.")]
        self.assertEqual(res(prov, HIST.format(t=3))["reason"], "unsupported_relevant_report")
        corr = base + [("r02", "Message r02, received at time 2: this is a verified correction of r01. r01 got what slot Tolo held wrong: actually, from time 1 on, slot Tolo is empty (until a recorded event changes it). Nothing physically changed when this correction arrived.")]
        self.assertEqual(res(corr, HIST.format(t=3))["reason"], "unsupported_relevant_report")
        odd = base + [("r02", "Message r02, received at time 2: somebody mentioned slot Tolo in passing.")]
        self.assertEqual(res(odd, HIST.format(t=3))["reason"], "unsupported_relevant_report")
        stock = [("r01", "Message r01, received at time 2: a confirmed check shows that at time 2 part Alpa is not on hand."),
                 ("r02", "Message r02, received at time 3: this is a verified correction of r01. r01 got whether part Alpa was on hand wrong: actually, from time 2 on, you have part Alpa on hand (until a recorded event changes it). Nothing physically changed when this correction arrived.")]
        self.assertEqual(res(stock, ONE)["reason"], "unsupported_relevant_report")

    def test_04b_unknown_header_still_relevant(self):
        recs = [("r01", "Message r01, received at time 1: a confirmed check shows that at time 1 slot Tolo holds part Alpa."),
                ("r02", "Report r02 received at time 3: slot Tolo suffered an unrecorded change at time 3")]
        r = res(recs, HIST.format(t=4))
        self.assertIsNone(r["field"]); self.assertEqual(r["reason"], "unsupported_relevant_report")

    def test_05_duplicate_or_mismatched_ids(self):
        dup = [("r01", "Message r01, received at time 2: a confirmed check shows that at time 2 part Alpa is not on hand."),
               ("r01", "Message r01, received at time 3: a confirmed check shows that at time 3 part Beta is on hand.")]
        self.assertEqual(res(dup, ONE)["reason"], "duplicate_record_ids")
        mis = [("r01", "Message r07, received at time 2: a confirmed check shows that at time 2 part Alpa is not on hand.")]
        self.assertEqual(res(mis, ONE)["reason"], "record_id_mismatch")

    def test_06_measurement_order_not_position(self):
        recs = [("r01", "Message r01, received at time 4: a confirmed check shows that at time 4 part Alpa is not on hand."),
                ("r02", "Message r02, received at time 5: a confirmed check shows that at time 2 part Beta is on hand.")]
        self.assertEqual(res(recs, MEAS)["field"], "Beta.on_hand")
        self.assertEqual(res(recs, MEAS.replace("earlier", "later"))["field"], "Alpa.on_hand")

    def test_07_resolver_reply_parsing(self):
        p = pi([("r01", "Message r01, received at time 2: a confirmed check shows that at time 2 part Alpa is not on hand.")], ONE)
        self.assertEqual(RR.parse_resolver('{"field": "Alpa.on_hand", "records": ["r01"]}', p)["status"], "resolved")
        self.assertEqual(RR.parse_resolver('{"field": null, "records": []}', p)["status"], "unresolved")
        for bad in ('{}', '{"field": null}', '{"records": []}', '{"field": null, "records": "r01"}', 'not json', '{"field": "Tolo.part", "records": ["r01"]}', '{"field": "Alpa.on_hand", "records": []}',
                    '{"field": "Alpa.on_hand", "records": ["r05"]}', '{"field": "Zeta.on_hand", "records": ["r01"]}', None):
            self.assertEqual(RR.parse_resolver(bad, p)["status"], "invalid", bad)
        self.assertEqual(RR.parse_resolver('{"field": "Beta.on_hand", "records": ["r01"]}', p)["field"], "Beta.on_hand")  # legal wrong field kept

    def test_08_rewrite_span_and_bypass(self):
        d = RR.detect(ONE)
        new, lg = RR.rewrite(ONE, d, "Beta.on_hand")
        s, e = d["span"]
        self.assertEqual(new, ONE[:s] + "part Beta" + ONE[e:])
        self.assertEqual(lg["original_phrase"], "the part whose stock was checked in r01")
        corr = "Message r09, received at time 9: this is a verified correction of r04. r04 got whether part Alpa was on hand wrong: actually, from time 4 on, it was not on hand. Nothing physically changed when this correction arrived."
        self.assertEqual(RR.detect(corr)["route"], "bypass")
        self.assertEqual(RR.detect("Message r09, received at time 9: nothing named here.")["route"], "pending")
        two = ONE.replace("is on hand.", "and the part described in r02 is on hand.")
        self.assertEqual(RR.detect(two)["route"], "pending")

    def test_08b_quote_ledger_is_per_arm(self):
        d = RR.detect(ONE)
        _, det_l = RR.rewrite(ONE, d, "Alpa.on_hand")
        _, mod_l = RR.rewrite(ONE, d, "Beta.on_hand")        # learned resolver chose a different legal field
        det_quote = "a confirmed check shows that at time 9 part Alpa is on hand"
        mod_quote = "a confirmed check shows that at time 9 part Beta is on hand"
        L = lambda arm, src="call": RR.ledger_for_arm(arm, src, det_l, mod_l)
        self.assertTrue(RR.quote_contains_replacement(det_quote, L("RES_DET")))
        self.assertFalse(RR.quote_contains_replacement(det_quote, L("RES_MODEL")))
        self.assertTrue(RR.quote_contains_replacement(mod_quote, L("RES_MODEL")))
        self.assertFalse(RR.quote_contains_replacement(det_quote, L("BASE")))
        self.assertFalse(RR.quote_contains_replacement(det_quote, L("RES_MODEL", "use_BASE")))

    def test_09_resolver_prompt_uses_only_public_input(self):
        p = pi([("r01", "Message r01, received at time 2: a confirmed check shows that at time 2 part Alpa is not on hand.")], ONE)
        u = RR.resolver_prompt(p, RR.detect(ONE))
        self.assertIn("r01", u); self.assertIn(ONE, u)
        self.assertNotIn("Fixed facts", u)
        import inspect
        self.assertEqual(list(inspect.signature(RR.resolver_prompt).parameters), ["pi", "det"])


if __name__ == "__main__":
    unittest.main()
