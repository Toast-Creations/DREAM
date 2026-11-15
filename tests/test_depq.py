"""No-model fixtures for V1.14.0 dependency-aware query selection (brief section 7, items 2-12; item 1, BASE =
1.13.0 DEFER on its stored panel, is checked by scripts/depq_validate.py against the stored traces). Fixture worlds
use a test-only pool and rows; they are not the committed panel. Every trajectory is compared with the independent
reference (tempo.freshref) and every selection with the independent selector check (tempo.depref)."""
import itertools
import json
import sys
import unittest
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tempo import agentstate as AS, depgen as DG, depquery as DQ, depref as DR, freshgen as FG, freshness as F, \
    freshref as FREF, timing as TM  # noqa: E402

POOL, SEED = "depqtest", 7171
FG.CONS[POOL] = "cgmpqtx"
fx = lambda *r: tuple(r) + (("fx", "fx"),)


def make(domain, row):
    for att in range(60):
        try:
            return DG.build(row, domain, SEED + att, POOL)[1:]
        except AssertionError:
            continue
    raise AssertionError("cannot build")


def sel_for(pub, hid, role, env="changing"):
    ep, gc, env_ep = DG.goal_copy(pub, hid, role)
    q0 = F.p2_request(ep, gc)["fields"]
    return ep, gc, env_ep, q0, DQ.selection_for(ep, gc, q0, env)


def arm(tc, pub, hid, role, fields, env="changing", tape=None):
    ep, gc, env_ep = DG.goal_copy(pub, hid, role)
    t = DQ.run_arm(ep, gc, fields, env, env_ep, hid["tape"] if tape is None else tape, "|fx")
    rf = FREF.reference_for(ep, gc, t["receipts"], pub["transitions"] if env == "changing" else [], t["projection_clock"])
    tc.assertEqual(sorted(map(str, rf["states"])), sorted(map(str, t["states"])))
    tc.assertEqual((rf["classes"], rf["choice"]), (t["candidates"], t["plan"]))
    tc.assertTrue(t["actual_in_support"])
    tc.assertFalse(t["invalid_attempt"] or t["false_completion"])
    return t


def selref(tc, ep, gc, q0, sel, env="changing"):
    ref = DR.selection_reference(ep, gc["relevant"], q0, env, TM.ORIGIN, DQ.SELECT_AT, DQ.CAP,
                                 set(AS.agent_fields(ep["spec"])))
    sk = lambda S: sorted(json.dumps(sorted(s.items())) for s in S)
    tc.assertEqual(sk(ref["s2_states"]), sk(sel["s2_states"]))
    tc.assertEqual((ref["R"], ref["D"], ref["DEPENDENCY"], ref["e"]), (sel["R"], sel["D"], sel["fields"]["DEPENDENCY"], sel["e"]))
    if sel["e"]:
        tc.assertEqual(ref["random_subsets"], sel["random_subsets"])
        tc.assertEqual(Fraction(ref["random_weight"]), Fraction(1, sel["n_random_subsets"]))


COMPETE_D = fx("t-d1", ("B", "ver"), ("YOU", "ver"), [("EA", "B", "YOU"), ("EB", "YOU", "B")], [(0, 0.5)])
JOINT_A = fx("t-a1", {"T": ("G", "ver"), "G": ("no", "prov")}, {"S2": ("empty", "ver"), "D": ("no", "ver")},
             [("return", "T", "G")], [(0, 0.5)])
STOCK_A = fx("t-a2", {"T": ("empty", "prov"), "G": ("yes", "ver")}, {"S2": ("empty", "ver"), "D": ("yes", "ver")},
             [("on_hand", "G", "yes", "no"), ("on_hand", "D", "yes", "no")], [(0, 0.5)])
FULL_A = fx("t-a3", {"T": ("empty", "prov"), "G": ("yes", "prov")}, {"S2": ("empty", "ver"), "D": ("yes", "ver")},
            [("on_hand", "D", "yes", "no"), ("install", "T", "W")], [])


class DepQuery(unittest.TestCase):
    def test_02_empty_q0_adds_now_uncertain_verified_fact(self):
        pub, hid = make("delivery", COMPETE_D)
        ep, gc, _, q0, sel = sel_for(pub, hid, "A")
        self.assertEqual(q0, [])
        fa = f"{pub['goals']['A']['item']}.location"
        self.assertEqual(sel["D"], [fa])
        self.assertEqual(sel["fields"]["DEPENDENCY"], [fa])
        self.assertEqual(sel["fields"]["BASE"], [])
        selref(self, ep, gc, q0, sel)
        _, _, _, _, st = sel_for(pub, hid, "A", "stable")
        self.assertEqual((st["R"], st["e"]), ([], 0))  # stable: nothing changes, nothing is added

    def test_03_goal_changes_dependency_query_not_state(self):
        pub, hid = make("delivery", COMPETE_D)
        _, _, _, _, sa = sel_for(pub, hid, "A")
        _, _, _, _, sb = sel_for(pub, hid, "B")
        self.assertEqual(sorted(map(str, sa["s2_states"])), sorted(map(str, sb["s2_states"])))
        self.assertEqual(sorted(sa["R"]), sorted(sb["R"]))
        self.assertNotEqual(sa["added"], sb["added"])
        self.assertEqual(sa["added"], [f"{pub['goals']['A']['item']}.location"])
        self.assertEqual(sb["added"], [f"{pub['goals']['B']['item']}.location"])

    def test_04_unqueried_prerequisite_measured_resolves_decision(self):
        pub, hid = make("assembly", STOCK_A)
        ep, gc, _, q0, sel = sel_for(pub, hid, "A")
        selref(self, ep, gc, q0, sel)
        fG = f"{pub['goals']['A']['part']}.on_hand"
        self.assertEqual(sel["added"], [fG])
        b = arm(self, pub, hid, "A", sel["fields"]["BASE"])
        d = arm(self, pub, hid, "A", sel["fields"]["DEPENDENCY"])
        self.assertIsNone(b["plan"])
        self.assertIn(fG, b["uncertain_unqueried"])
        self.assertIsNotNone(d["plan"])
        self.assertEqual(d["queried_facts"], b["queried_facts"] + 1)

    def test_05_other_goal_uncertainty_in_pool_not_dependency(self):
        pub, hid = make("assembly", STOCK_A)
        _, gc, _, _, sel = sel_for(pub, hid, "A")
        fD = f"{pub['goals']['B']['part']}.on_hand"
        self.assertIn(fD, sel["R"])
        self.assertNotIn(fD, sel["D"])
        self.assertNotIn(fD, gc["relevant"])
        self.assertEqual(sel["n_random_subsets"], 2)

    def test_06_joint_transition_redundant_extra_is_charged(self):
        pub, hid = make("assembly", JOINT_A)
        ep, gc, _, q0, sel = sel_for(pub, hid, "A")
        selref(self, ep, gc, q0, sel)
        fT, fG = f"{pub['goals']['A']['slot']}.part", f"{pub['goals']['A']['part']}.on_hand"
        self.assertEqual(q0, [fG])
        self.assertEqual(sel["added"], [fT])
        b = arm(self, pub, hid, "A", sel["fields"]["BASE"])
        d = arm(self, pub, hid, "A", sel["fields"]["DEPENDENCY"])
        self.assertEqual(len({s[fT] for s in b["states"]}), 1)  # Q0's late stock reading already determines the slot
        self.assertEqual((b["plan"], b["success"]), (d["plan"], d["success"]))
        self.assertEqual(d["utility"]["1"], b["utility"]["1"] - 1)

    def test_07_full_q0_leaves_no_room(self):
        pub, hid = make("assembly", FULL_A)
        ep, gc, _, q0, sel = sel_for(pub, hid, "A")
        self.assertEqual(len(q0), 2)
        self.assertEqual((sel["spare_capacity"], sel["e"], sel["fields"]["DEPENDENCY"]), (0, 0, q0))
        self.assertTrue(sel["R"])  # uncertainty exists elsewhere, nothing is dropped to make room
        _, _, _, q0b, selb = sel_for(pub, hid, "B")
        self.assertEqual(q0b, [])
        self.assertEqual(selb["e"], 1)

    def test_08_registry_order_and_cap(self):
        reg = {"a.part": [], "b.on_hand": [], "c.part": [], "d.on_hand": []}
        S = [{"a.part": x, "b.on_hand": y, "c.part": z, "d.on_hand": "yes"}
             for x in ("p", "q") for y in ("yes", "no") for z in ("r", "s")]
        s = DQ.select(["d.on_hand"], S, reg, ["c.part", "b.on_hand", "a.part"])
        self.assertEqual(s["R"], ["a.part", "b.on_hand", "c.part"])
        self.assertEqual(s["D"], ["a.part", "b.on_hand", "c.part"])  # registry order, not dependency-list order
        self.assertEqual(s["fields"]["DEPENDENCY"], ["d.on_hand", "a.part"])
        s0 = DQ.select([], S, reg, ["c.part", "b.on_hand"])
        self.assertEqual(s0["fields"]["DEPENDENCY"], ["b.on_hand", "c.part"])
        # values never influence the order
        S2 = [{k: (v[::-1] if isinstance(v, str) else v) for k, v in x.items()} for x in S]
        self.assertEqual(DQ.select([], S2, reg, ["c.part", "b.on_hand"])["fields"], s0["fields"])

    def test_09_exact_uniform_subset_enumeration(self):
        reg = {f"f{i}.part": [] for i in range(4)}
        S = [dict(zip(reg, c)) for c in itertools.product("xy", repeat=4)]
        s = DQ.select([], S, reg, ["f1.part", "f3.part"])
        self.assertEqual(s["e"], 2)
        self.assertEqual(s["n_random_subsets"], 6)
        self.assertEqual(s["random_added"], [list(c) for c in itertools.combinations(list(reg), 2)])
        self.assertEqual(sum(Fraction(1, 6) for _ in s["random_added"]), 1)
        self.assertIn(s["fields"]["DEPENDENCY"], s["random_subsets"])
        z = DQ.select([], S, reg, [])
        self.assertEqual((z["e"], z["random_subsets"], z["random_weight"]), (0, [[]], 1.0))
        one = DQ.select([], [dict(S[0], **{"f0.part": "x"}), dict(S[0], **{"f0.part": "y"})], reg, ["f0.part"])
        self.assertEqual((one["n_random_subsets"], one["random_tie_with_dependency"]), (1, True))

    def test_10_no_hidden_leakage(self):
        pub, hid = make("delivery", COMPETE_D)
        ep, gc, env_ep, q0, sel = sel_for(pub, hid, "A")
        self.assertFalse({"truth", "tape", "labels", "seed"} & set(ep))
        fa = f"{pub['goals']['A']['item']}.location"
        other = next(p for p in pub["world"]["places"] if p != hid["truth"][fa])
        hid2 = dict(hid, truth={**hid["truth"], fa: other}, tape=[])
        _, _, _, _, sel2 = sel_for(pub, hid2, "A")
        self.assertEqual(sel["fields"], sel2["fields"])
        self.assertEqual(sel["random_subsets"], sel2["random_subsets"])
        tapes = {"realized": hid["tape"], "none": [], "both": [{"transition": "x1", "elapsed": 0.5},
                                                                {"transition": "x2", "elapsed": 1.5}]}
        for fields in (sel["fields"]["BASE"], sel["fields"]["DEPENDENCY"], *sel["random_subsets"]):
            seen = {}
            for tn, tp in tapes.items():
                t = arm(self, pub, hid, "A", fields, tape=tp)
                k = json.dumps([(r["field"], r["value"]) for r in t["readings"]])
                seen.setdefault(k, set()).add((t["states_sha256"], t["plan"]))
            self.assertTrue(all(len(v) == 1 for v in seen.values()))

    def test_11_empty_or_partial_support_is_conservative(self):
        reg = {"a.part": [], "b.part": []}
        s = DQ.select(["a.part"], [], reg, ["b.part"], status="empty_support")
        self.assertEqual((s["fields"]["DEPENDENCY"], s["e"], s["s2_status"]), (["a.part"], 0, "empty_support"))
        p = DQ.select([], [{"a.part": "x", "b.part": "y"}, {"a.part": "x"}], reg, ["b.part"])
        self.assertEqual(p["partially_represented"], ["b.part"])
        self.assertEqual(p["added"], ["b.part"])  # absence is never read as certainty
        u = DQ.select([], [{"a.part": "x"}], reg, ["b.part"])
        self.assertEqual((u["unrepresented"], u["R"], u["e"]), (["b.part"], [], 0))
        pub, hid = make("delivery", COMPETE_D)
        ep, gc, env_ep = DG.goal_copy(pub, hid, "A")
        with self.assertRaises(F.LimitExceeded):
            old = F.MAX_STATES
            try:
                F.MAX_STATES = 1
                DQ.selection_for(ep, gc, [], "changing")
            finally:
                F.MAX_STATES = old

    def test_12_zero_query_arm_waits_and_scorer_kinds(self):
        pub, hid = make("delivery", COMPETE_D)
        b = arm(self, pub, hid, "A", [])
        self.assertEqual((b["request"], b["receipts"], b["queried_facts"], b["pre_action_wait"]), (None, [], 0, 4))
        self.assertEqual(b["clock"]["execute_at"], 16)
        self.assertEqual(b["utility"]["1"], b["utility_base"] - 4)
        self.assertEqual(b["outcome_kind"], "decline")
        done = make("delivery", fx("t-d2", ("B", "ver"), ("G", "ver"), [("EA", "B", "C")], []))
        t = arm(self, *done, "B", [])
        self.assertEqual((t["outcome_kind"], t["empty_plan"], t["success"], t["false_completion"]),
                         ("complete", True, True, False))

    def test_13_sensor_identity_and_history_preserved(self):
        pub, hid = make("delivery", COMPETE_D)
        _, _, _, _, sel = sel_for(pub, hid, "A")
        t = arm(self, pub, hid, "A", sel["fields"]["DEPENDENCY"])
        self.assertTrue(t["history_preserved"] and t["log_unchanged_by_projection"] and t["receipt_absent_before_reception"])
        self.assertEqual([(r["measured_at"], r["received_at"]) for r in t["receipts"]], [(14, 16)])
        self.assertFalse(t["refused"] or t["authority_conflicts"])


if __name__ == "__main__":
    unittest.main()
