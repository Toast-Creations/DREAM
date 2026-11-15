"""Contract tests for state engine v0.1 (hand fixtures; expected values written by hand from the rules).

Numbered by the acceptance checks in TEMPORAL-STATE-ENGINE-BRIEF.md.
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tempo import engine as E  # noqa: E402

DELIV = {"domain": "delivery", "places": ["P", "Q", "R"], "roads": [["P", "Q", 1], ["Q", "R", 2], ["P", "R", 4]],
         "closed": [], "agent_at": "P", "crates": ["A", "B", "C"], "non_portable": []}
ASSEM = {"domain": "assembly", "slots": {"T": "K1", "S": "K2"},
         "parts": {"G": {"type": "K1", "rating": 8}, "W": {"type": "K1", "rating": 2}, "D": {"type": "K2", "rating": 5}},
         "prices": {"G": 3}, "adapters": {}, "fitted": {}, "extra_parts": []}


def rec(rid, kind, e, r, payload, status="verified"):
    return {"rid": rid, "kind": kind, "status": status, "event_at": e, "received_at": r, "payload": payload}


def deliv(*records, ctx="t"):
    eng = E.Engine(DELIV, ctx)
    for x in records:
        eng.ingest_report(x)
    return eng


INIT = rec("r01", "initial", 0, 0, {"assign": {"A.location": "P", "B.location": "Q", "C.location": "R"}})


class C1Blocked(unittest.TestCase):
    def test_blocked_action_has_no_effect_even_if_model_claims_success(self):
        eng = deliv(rec("r01", "initial", 0, 0, {"assign": {"A.location": "Q", "B.location": "Q", "C.location": "R"}}))
        b = eng.branch(12)
        chk = eng.check_action(b, ["take", "A"])
        self.assertEqual(chk["verdict"], "blocked")
        self.assertEqual(chk["prerequisites"], {"crate_at_your_place": False, "hands_empty": True,
                                                "crate_portable": True})
        self.assertEqual(eng.predict_action(b, ["take", "A"]).states, b.states)
        claim = json.dumps({"applicable": False, "predicted_next_facts": {"A.location": "carried by you"}})
        a = E.audit_model_action(eng, 12, ["take", "A"], claim, {"applicable": False,
                                                                 "predicted": {"A.location": E.CARRIED}})
        self.assertEqual(a["raw"], claim)
        self.assertEqual(a["engine_successor"]["A.location"], "Q")
        self.assertTrue(a["successor_differs"])

    def test_assembly_blocked_by_occupied_slot_and_missing_part(self):
        eng = E.Engine(ASSEM)
        eng.ingest_report(rec("r01", "initial", 0, 0, {"assign": {"T.part": "W", "G.on_hand": "yes", "S.part": "empty"}}))
        b = eng.branch(12)
        self.assertEqual(eng.check_action(b, ["install", "G", "T"])["verdict"], "blocked")
        self.assertEqual(eng.predict_action(b, ["install", "G", "T"]).summary()["T.part"], "W")
        self.assertEqual(eng.check_action(b, ["order", "G"])["verdict"], "blocked")  # already on hand
        self.assertEqual(eng.check_action(b, ["fit", "X", "T"])["verdict"], "blocked")  # no adapters exist
        b2 = eng.predict_action(b, ["remove", "T"])
        self.assertEqual(b2.summary(), {"T.part": "empty", "W.on_hand": "yes", "G.on_hand": "yes",
                                        "S.part": "empty"})
        b3 = eng.predict_action(b2, ["install", "G", "T"])
        self.assertEqual(b3.summary()["T.part"], "G")


class C2Allowed(unittest.TestCase):
    def test_effects_preserve_and_no_double_execution(self):
        eng = deliv(INIT)
        b = eng.branch(12)
        self.assertEqual(eng.check_action(b, ["take", "A"])["verdict"], "allowed")
        s = eng.predict_action(b, ["take", "A"]).summary()
        self.assertEqual(s, {"A.location": E.CARRIED, "B.location": "Q", "C.location": "R", "agent.at": "P"})
        r1 = eng.commit_execution("x1", ["take", "A"], 12)
        v = eng.log.version
        r2 = eng.commit_execution("x1", ["take", "A"], 12)
        self.assertFalse(r1["duplicate"]); self.assertTrue(r2["duplicate"])
        self.assertEqual(eng.log.version, v)
        now = eng.view("current", 12)["per_field"]
        self.assertEqual(now, {"A.location": E.CARRIED, "B.location": "Q", "C.location": "R"})
        # now hands are full: a second take is blocked, and its execution commits no change
        r3 = eng.commit_execution("x2", ["take", "B"], 12)
        self.assertEqual(r3["verdict"], "blocked"); self.assertEqual(r3["records"], [])
        self.assertEqual(eng.view("current", 12)["per_field"]["B.location"], "Q")

    def test_moves_are_predicted_not_committed(self):
        eng = deliv(INIT)
        b = eng.predict_action(eng.branch(12), ["go", "P", "Q"])
        self.assertEqual(b.summary()["agent.at"], "Q")
        with self.assertRaises(E.EngineError):
            eng.commit_execution("m1", ["go", "P", "Q"], 12)


class C3Unresolved(unittest.TestCase):
    def unresolved(self, b_value="Q"):
        return deliv(rec("r01", "initial", 0, 0, {"assign": {"A.location": "R", "B.location": b_value,
                                                             "C.location": "R"}}),
                     rec("r02", "uncertain_change", 3, 3, {"field": "A.location", "from": "R", "options": ["P", "Q"]}))

    def test_unknown_only_keeps_alternatives_and_correlation(self):
        eng = self.unresolved()
        b = eng.branch(12)
        chk = eng.check_action(b, ["take", "A"])
        self.assertEqual(chk["verdict"], "unresolved")
        self.assertEqual(chk["prerequisites"]["crate_at_your_place"], E.UNKNOWN)
        self.assertEqual(chk["prerequisites"]["hands_empty"], True)
        nb = eng.predict_action(b, ["take", "A"])
        self.assertEqual(sorted(s["A.location"] for s in nb.states), sorted([E.CARRIED, "Q"]))
        self.assertEqual(nb.summary()["B.location"], "Q")  # unaffected known fact stays known
        # correlation retained: in the branch where A was taken, a second take is blocked; elsewhere allowed
        follow = eng.check_action(nb, ["take", "C"])  # C at R, agent at P: blocked in every alternative anyway
        self.assertEqual(follow["verdict"], "blocked")
        nb2 = eng.predict_action(nb, ["take", "B"])  # B at Q != P: blocked
        self.assertEqual(nb2.states, nb.states)
        with self.assertRaises(E.EngineError):
            eng.commit_execution("u1", ["take", "A"], 12)

    def test_false_plus_unknown_is_blocked(self):
        eng = self.unresolved(b_value=E.CARRIED)  # hands full, A's place unresolved
        b = eng.branch(12)
        chk = eng.check_action(b, ["take", "A"])
        self.assertEqual(chk["verdict"], "blocked")
        self.assertEqual(chk["prerequisites"], {"crate_at_your_place": E.UNKNOWN, "hands_empty": False,
                                                "crate_portable": True})
        self.assertEqual(eng.predict_action(b, ["take", "A"]).states, b.states)

    def test_later_observation_settles_retroactively(self):
        eng = self.unresolved()
        eng.commit_observation(rec("r03", "observation", 6, 6, {"field": "A.location", "value": "P"}))
        self.assertEqual(eng.view("current", 12)["per_field"]["A.location"], "P")
        self.assertEqual(eng.view("retrospective", 4)["per_field"]["A.location"], "P")
        self.assertEqual(eng.view("earlier", 4, cutoff=5)["per_field"]["A.location"], E.UNKNOWN)


class C4NoHypotheticalCommit(unittest.TestCase):
    def test_predict_does_not_touch_log_or_views(self):
        eng = deliv(INIT)
        head, v = eng.log.head(), eng.view("current", 12)
        b = eng.branch(12)
        for act in (["take", "A"], ["go", "P", "Q"], ["put", "A"]):
            b = eng.predict_action(b, act)
        self.assertEqual(b.summary()["A.location"], "Q")
        self.assertEqual((eng.log.head(), eng.view("current", 12)), (head, v))
        self.assertEqual(eng.log.executions(), [])


class C5Corrections(unittest.TestCase):
    def test_correction_revises_past_not_earlier_information_and_keeps_original(self):
        eng = deliv(rec("r01", "initial", 0, 0, {"assign": {"A.location": "P", "B.location": "Q",
                                                            "C.location": "R"}}, status="provisional"))
        before = eng.view("earlier", 3, cutoff=4)
        eng.apply_correction(rec("r02", "correction", None, 6, {"target": "r01", "field": "A.location", "value": "Q",
                                                                 "valid_from": 0, "valid_to": None}))
        self.assertEqual(eng.view("retrospective", 3)["per_field"]["A.location"], "Q")
        self.assertEqual(eng.view("current", 12)["per_field"]["B.location"], "Q")  # scoped: other fields kept
        self.assertEqual(eng.view("earlier", 3, cutoff=4), before)  # C6 as well
        self.assertEqual(before["per_field"]["A.location"], "P")
        self.assertEqual(eng.log.records()[0]["payload"]["assign"]["A.location"], "P")  # original preserved
        self.assertEqual(eng.log.records()[0]["status"], "provisional")
        roles = {x["rid"]: x["role"] for x in eng.explain("A.location", 12)}
        self.assertEqual(roles, {"r01": "withdrawn by r02", "r02": "correction"})

    def test_delayed_old_report_does_not_override_and_moves_count(self):
        eng = deliv(INIT, rec("r02", "change", 5, 5, {"field": "A.location", "from": "P", "to": "Q"}),
                    rec("r03", "observation", 2, 9, {"field": "A.location", "value": "P"}))
        self.assertEqual(eng.view("current", 12)["per_field"]["A.location"], "Q")
        self.assertEqual(eng.view("retrospective", 3)["per_field"]["A.location"], "P")

    def test_corrections_must_target_an_asserting_report_in_context(self):
        eng = deliv(INIT)
        for bad in ({"target": "r09", "field": "A.location", "value": "Q", "valid_from": 0, "valid_to": None},
                    {"target": "r01", "field": "A.location", "value": "Q", "valid_from": 0, "valid_to": 8}):
            with self.assertRaises(E.RecordRejected):
                eng.apply_correction(rec("rX", "correction", None, 6, bad))
        self.assertEqual(eng.log.version, 1)

    def test_inconsistent_evidence_rejected_and_not_appended(self):
        eng = deliv(INIT)
        for bad in (rec("r02", "observation", 3, 3, {"field": "A.location", "value": "Q"}),  # no recorded move
                    rec("r02", "change", 3, 3, {"field": "A.location", "from": "R", "to": "Q"})):  # wrong 'from'
            with self.assertRaises(E.RecordRejected):
                eng.ingest_report(bad)
        self.assertEqual(eng.log.version, 1)


class C7ScopeAndPersistence(unittest.TestCase):
    def test_contexts_are_separate(self):
        a, b = deliv(INIT, ctx="a"), deliv(ctx="b")
        with self.assertRaises(E.RecordRejected):
            b.apply_correction(rec("r02", "correction", None, 6, {"target": "r01", "field": "A.location",
                                                                   "value": "Q", "valid_from": 0, "valid_to": None}))
        with self.assertRaises(E.RecordRejected):
            a.ingest_report(rec("r01", "observation", 1, 1, {"field": "B.location", "value": "Q"}))  # dup rid
        with self.assertRaises(E.RecordRejected):
            a.ingest_report(rec("r05", "observation", 1, 1, {"field": "Zed.location", "value": "Q"}))  # unregistered
        with self.assertRaises(E.RecordRejected):
            a.ingest_report(rec("r06", "observation", 1, 1, {"field": "B.location", "value": "Mars"}))

    def test_reception_order_and_time_sanity(self):
        eng = deliv(INIT, rec("r02", "change", 5, 5, {"field": "A.location", "from": "P", "to": "Q"}))
        with self.assertRaises(E.RecordRejected):
            eng.ingest_report(rec("r03", "observation", 1, 4, {"field": "B.location", "value": "Q"}))
        with self.assertRaises(E.RecordRejected):
            eng.ingest_report(rec("r03", "observation", 9, 7, {"field": "B.location", "value": "Q"}))

    def test_save_load_replay_and_incomplete_writes(self):
        eng = deliv(INIT, rec("r02", "uncertain_change", 3, 3, {"field": "B.location", "from": "Q",
                                                                  "options": ["P", "R"]}))
        eng.commit_execution("x1", ["take", "A"], 4)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "log.jsonl")
            eng.save(p)
            back = E.Engine.load(p)
            self.assertEqual(back.log.head(), eng.log.head())
            for args in (("current", 12), ("retrospective", 2), ("earlier", 3, 3)):
                self.assertEqual(back.view(*args), eng.view(*args))
            self.assertTrue(back.commit_execution("x1", ["take", "A"], 4)["duplicate"])
            raw = Path(p).read_text()
            Path(p).write_text(raw[:-25])  # torn final write
            with self.assertRaises(E.IncompleteWrite):
                E.Engine.load(p)
            lines = raw.split("\n")
            e = json.loads(lines[2]); e["body"]["payload"]["to"] = "R"  # tampered committed event
            lines[2] = json.dumps(e, sort_keys=True)
            Path(p).write_text("\n".join(lines))
            with self.assertRaises(E.IncompleteWrite):
                E.Engine.load(p)


class C8Separation(unittest.TestCase):
    def test_scorer_and_simulator_keys_rejected(self):
        eng = deliv()
        for extra in ({"_src": "base"}, {"ordinal": 1}, {"key": "init"}, {"hidden": "P"}):
            with self.assertRaises(E.RecordRejected):
                eng.ingest_report(dict(INIT, **extra))
        with self.assertRaises(E.RecordRejected):
            eng.ingest_report(dict(INIT, payload={"assign": {"A.location": "P"}, "truth": "Q"}))

    def test_engine_imports_only_public_resolvers(self):
        src = (ROOT / "src" / "tempo" / "engine.py").read_text()
        imports = [l for l in src.splitlines() if l.startswith(("import", "from"))]
        self.assertEqual([l for l in imports if l.startswith("from")], ["from . import enumcheck, resolve"])
        for word in ("generate", "gold", "probe", "diag", "score"):
            self.assertFalse(any(word in l for l in imports))

    def test_audit_keeps_raw_decision_and_state_apart(self):
        eng = deliv(INIT)
        a = E.audit_model_action(eng, 12, ["take", "A"], "not json at all", None)
        self.assertEqual(set(a), {"raw", "model", "engine_check", "engine_successor", "log_version_unchanged"})
        self.assertEqual(a["raw"], "not json at all")
        self.assertIsNone(a["model"])
        self.assertTrue(a["log_version_unchanged"])


if __name__ == "__main__":
    unittest.main()
