"""Hand fixtures for contract v1 / assertion engine v0.3 (expected values written by hand from EVENT-CONTRACT.md)."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tempo import assertions as A, engine as E  # noqa: E402

DELIV = {"domain": "delivery", "places": ["P", "Q", "R"], "roads": [["P", "Q", 1], ["Q", "R", 2]], "closed": [],
         "agent_at": "P", "crates": ["A", "B", "C"], "non_portable": []}
ASSEM = {"domain": "assembly", "slots": {"T": "K1", "S": "K2"},
         "parts": {"G": {"type": "K1", "rating": 8}, "W": {"type": "K1", "rating": 2}}, "prices": {"G": 3},
         "adapters": {}, "fitted": {}, "extra_parts": []}


def st(rid, r, assertions, status="verified"):
    return {"rid": rid, "received_at": r, "status": status, "type": "state", "assertions": assertions}


def ev(rid, r, assertions, status="verified"):
    return {"rid": rid, "received_at": r, "status": status, "type": "event", "assertions": assertions}


def corr(rid, r, assertions):
    return {"rid": rid, "received_at": r, "status": "verified", "type": "correction", "assertions": assertions}


def eng(spec, *reports):
    a = A.AssertionEngine(spec)
    for r in reports:
        a.ingest(r)
    return a


R1 = st("r01", 0, [{"field": "A.location", "at": 0, "value": "P"}, {"field": "B.location", "at": 0, "value": "Q"}])


class Contract(unittest.TestCase):
    def per(self, a, t, kind="current", cutoff=None):
        return a.view(kind, t, cutoff)["per_field"]

    def test_multi_fact_bundle_and_scoped_correction(self):
        a = eng(DELIV, dict(R1, status="provisional"),
                corr("r02", 6, [{"field": "A.location", "target": "r01", "value": "R", "valid_from": 0}]))
        self.assertEqual(self.per(a, 12), {"A.location": "R", "B.location": "Q"})  # B's claim in r01 stands
        d = a.view("current", 12)["detail"]["A.location"]
        self.assertEqual(d["withdrawn"], [{"rid": "r01", "by": "r02"}])
        self.assertEqual(self.per(a, 3, "earlier", cutoff=5)["A.location"], "P")  # correction not yet received

    def test_event_with_unstated_prior_value(self):
        a = eng(ASSEM, st("r01", 0, [{"field": "G.on_hand", "at": 0, "value": "no"},
                                     {"field": "T.part", "at": 0, "value": "empty"}]),
                ev("r02", 5, [{"field": "G.on_hand", "at": 5, "to": "yes"}]))  # "delivered to you": no 'from'
        self.assertEqual(self.per(a, 12)["G.on_hand"], "yes")
        self.assertEqual(self.per(a, 4, "retrospective")["G.on_hand"], "no")
        # an event alone describes a part never mentioned before, from its time on
        b = eng(ASSEM, ev("r01", 5, [{"field": "W.on_hand", "at": 5, "to": "yes"}]))
        self.assertEqual(self.per(b, 12)["W.on_hand"], "yes")
        self.assertNotIn("W.on_hand", self.per(b, 4, "retrospective"))

    def test_later_statement_never_resets_a_timeline(self):
        a = eng(DELIV, R1, ev("r02", 5, [{"field": "A.location", "at": 5, "from": "P", "to": "Q"}]),
                st("r03", 6, [{"field": "A.location", "at": 6, "value": "Q"}]),  # a one-fact "first-style" report
                st("r04", 9, [{"field": "A.location", "at": 2, "value": "P"}]))  # delayed old report
        self.assertEqual(self.per(a, 12)["A.location"], "Q")
        self.assertEqual(self.per(a, 3, "retrospective")["A.location"], "P")
        self.assertEqual(a.view("current", 12)["conflict_fields"], [])

    def test_uncertain_event_without_from(self):
        a = eng(DELIV, R1, ev("r02", 3, [{"field": "A.location", "at": 3, "to_options": ["Q", "R"]}]))
        v = a.view("current", 12)["detail"]["A.location"]
        self.assertEqual((v["status"], v["options"]), ("unknown", ["Q", "R"]))
        a.ingest(st("r03", 6, [{"field": "A.location", "at": 6, "value": "R"}]))
        self.assertEqual(self.per(a, 4, "retrospective")["A.location"], "R")
        self.assertEqual(self.per(a, 4, "earlier", cutoff=5)["A.location"], "unknown")

    def test_verified_observation_suspends_contradicted_provisional_without_inventing_a_move(self):
        a = eng(DELIV, dict(R1, status="provisional"))
        self.assertTrue(a.view("current", 12)["detail"]["A.location"]["provisional_support"])
        a.ingest(st("r02", 13, [{"field": "A.location", "at": 12, "value": "Q"}]))
        d = a.view("current", 13)["detail"]["A.location"]
        self.assertEqual((d["value"], d["suspended"], d.get("derived_by_persistence")), ("Q", ["r01"], True))
        self.assertFalse(d["provisional_support"])
        self.assertEqual(self.per(a, 5, "earlier", cutoff=11)["A.location"], "P")  # earlier information preserved
        self.assertEqual(self.per(a, 13)["B.location"], "Q")  # the same report's other claim is not suspended
        self.assertFalse(any(e["body"]["type"] == "event" for e in a.log.entries))

    def test_verified_conflict_is_kept_with_culprits(self):
        a = eng(DELIV, R1, st("r02", 3, [{"field": "A.location", "at": 3, "value": "Q"}]))  # no move recorded
        v = a.view("current", 12)
        self.assertEqual(v["per_field"]["A.location"], "conflict")
        self.assertEqual(v["detail"]["A.location"]["culprits"], ["r01", "r02"])
        a.ingest(st("r03", 6, [{"field": "A.location", "at": 6, "value": "P"}]))  # correct later report kept
        v = a.view("current", 12)
        self.assertEqual(v["detail"]["A.location"]["culprits"], ["r02"])
        self.assertEqual(len(a.reports()), 3)
        self.assertEqual(v["per_field"]["B.location"], "Q")
        chk = a.check_action(a.branch(12), ["take", "A"])
        self.assertEqual(chk["verdict"], "unresolved_conflict")
        self.assertEqual(a.check_action(a.branch(12), ["take", "B"])["verdict"], "blocked")  # B settled at Q

    def test_structural_rejections(self):
        a = eng(DELIV, R1)
        bad = [(dict(R1, rid="r09", assertions=[]), "schema"),
               (st("r09", 1, [{"field": "A.location", "at": "1", "value": "P"}]), "time_type"),
               (st("r09", 1, [{"field": "A.location", "at": 4, "value": "P"}]), "time_order"),
               (st("r09", 1, [{"field": "Z.location", "at": 1, "value": "P"}]), "unregistered_field"),
               (st("r09", 1, [{"field": "A.location", "at": 1, "value": "Mars"}]), "value"),
               (st("r09", 1, [{"field": "A.location", "at": 1, "value": "P", "options": ["P", "Q"]}]), "schema"),
               (corr("r09", 1, [{"field": "C.location", "target": "r01", "value": "P", "valid_from": 0}]),
                "correction_target"),
               (st("r01", 1, [{"field": "A.location", "at": 1, "value": "P"}]), "duplicate_rid"),
               (dict(st("r09", 1, [{"field": "A.location", "at": 1, "value": "P"}]), _src="base"), "schema")]
        for r, code in bad:
            with self.assertRaises(A.ContractRejected) as c:
                a.ingest(r)
            self.assertEqual(c.exception.code, code, r)
        self.assertEqual(a.log.version, 1)

    def test_pending_incomplete_and_persistence(self):
        a = eng(DELIV, R1)
        a.record_unprocessed("r02", 4, "message about crate A", None, "parse", "x")
        v = a.view("current", 12)
        self.assertEqual(v["complete_per_field"], {"A.location": "incomplete", "B.location": "Q"})
        self.assertEqual(a.check_action(a.branch(12), ["take", "A"])["verdict"], "unresolved_pending")
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "l.jsonl")
            a.save(p)
            b = A.AssertionEngine.load(p)
            self.assertEqual(b.view("current", 12), v)

    def test_mapping_from_v02_and_action_parity(self):
        old = [{"rid": "r01", "kind": "initial", "status": "verified", "event_at": 0, "received_at": 0,
                "payload": {"assign": {"A.location": "P", "B.location": "Q"}}},
               {"rid": "r02", "kind": "change", "status": "verified", "event_at": 4, "received_at": 4,
                "payload": {"field": "B.location", "from": "Q", "to": "P"}}]
        e2 = E.Engine(DELIV)
        a = A.AssertionEngine(DELIV)
        for r in old:
            e2.ingest_report(r)
            a.ingest(A.from_v02(r))
        self.assertEqual(e2.view("current", 12)["per_field"], a.view("current", 12)["per_field"])
        for act in (["take", "A"], ["take", "B"], ["go", "P", "Q"], ["put", "A"]):
            self.assertEqual(e2.check_action(e2.branch(12), act)["verdict"], a.check_action(a.branch(12), act)["verdict"])


if __name__ == "__main__":
    unittest.main()
