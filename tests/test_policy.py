"""No-model tests for the observation-policy study."""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tempo import assertions as A, policy as P  # noqa: E402


def build(pool="policy", base=20261111):
    eps = []
    for eid, dom, et, seed in P.episode_specs(pool, base):
        for att in range(60):
            try:
                eps.append(P.build_episode(eid, dom, et, seed + att, pool))
                break
            except AssertionError:
                pass
    return eps


class Policy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.eps = build()

    def test_allocation_and_type_semantics(self):
        self.assertEqual(len(self.eps), 24)
        self.assertEqual(sum(e["domain"] == "delivery" for e in self.eps), 12)
        for e in self.eps:
            acc, tru = e["accepted_relevant"], {f: e["truth"][f] for f in e["relevant"]}
            valid = P.true_valid_plans(e)
            t = e["type"]
            prov = any(r["status"] == "provisional" for r in e["reports"])
            if t in ("false_block", "false_permission"):
                self.assertTrue(prov); self.assertNotEqual(acc, tru)
            if t in ("provisional_correct",):
                self.assertTrue(prov); self.assertEqual(acc, tru)
            if t in ("verified_settled", "no_plan", "unresolved"):
                self.assertFalse(prov)
            if t == "no_plan":
                self.assertEqual(valid, [])
            if t in ("false_block", "unresolved", "provisional_correct", "verified_settled", "corrected"):
                self.assertTrue(valid, e["episode_id"])
            if t == "false_block":
                eng = self.engine(e)
                self.assertIsNone(P.choose(eng, P.DECIDE, e))  # accepted evidence blocks a real opportunity
            if t == "false_permission":
                eng = self.engine(e)
                k = P.choose(eng, P.DECIDE, e)
                self.assertIsNotNone(k); self.assertNotIn(k, valid)

    def engine(self, e):
        eng = A.AssertionEngine(e["spec"], "t")
        for r in e["reports"]:
            eng.ingest(r)
        return eng

    def test_selective_trigger_never_reads_truth(self):
        for e in self.eps:
            flipped = copy.deepcopy(e)
            for f in e["relevant"]:
                flipped["truth"][f] = "something else"
            eng = self.engine(e)
            self.assertEqual(P.needs_verification(eng, P.DECIDE, e["relevant"]),
                             P.needs_verification(self.engine(flipped), P.DECIDE, flipped["relevant"]))

    def test_selective_queries_by_evidence_including_blocked_opportunities(self):
        for e in self.eps:
            q = P.run_policy(e, "P2_selective")["queried"]
            if e["type"] in ("false_block", "false_permission", "provisional_correct", "unresolved"):
                self.assertTrue(q, e["episode_id"])
            if e["type"] in ("verified_settled", "no_plan"):
                self.assertEqual(q, [], e["episode_id"])

    def test_matched_clones_sensor_scope_and_integrity(self):
        for e in self.eps:
            snap = json.dumps(e, sort_keys=True)
            outs = {p: P.run_policy(e, p) for p in P.POLICIES}
            self.assertEqual(json.dumps(e, sort_keys=True), snap)  # episodes are not mutated between policies
            for p, r in outs.items():
                self.assertTrue(r["earlier_view_preserved"])
                self.assertEqual(r["log_reports"], len(e["reports"]) + (1 if r["queried"] else 0))
                self.assertLessEqual(len(r["queried"]), P.QUERY_BUDGET)
                self.assertTrue(set(r["queried"]) <= set(e["relevant"]))
                u = P.SUCCESS_REWARD * r["success"] - r["action_cost"] - P.INVALID_PENALTY * r["invalid_attempt"] - \
                    P.QUERY_COST * len(r["queried"])
                self.assertEqual(u, r["utility"])
            self.assertEqual(outs["P1_always"]["queried"], e["relevant"])

    def test_query_reveals_only_current_value_and_no_move(self):
        e = next(x for x in self.eps if x["type"] == "false_permission")
        eng = self.engine(e)
        f = e["relevant"][0]
        eng.ingest({"rid": "q1", "received_at": 13, "status": "verified", "type": "state", "source": "sensor",
                    "assertions": [{"field": f, "at": 12, "value": e["truth"][f]}]})
        d = eng.view("current", 13)["detail"][f]
        self.assertEqual(d["value"], e["truth"][f])
        self.assertTrue(d["suspended"])  # the contradicted provisional claim, not a fabricated event
        self.assertFalse(any(x["type"] == "event" and x["rid"] == "q1" for x in eng.reports()))
        self.assertEqual(eng.view("earlier", 12, cutoff=12)["per_field"][f], e["accepted_relevant"][f])

    def test_deterministic(self):
        again = build()
        self.assertEqual([json.dumps(x, sort_keys=True) for x in again], [json.dumps(x, sort_keys=True) for x in self.eps])


if __name__ == "__main__":
    unittest.main()
