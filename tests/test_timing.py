"""No-model fixtures for V1.13.0 query timing (brief section 7, items 1-11). Every projection is also compared with
the independent reference (tempo.freshref)."""
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tempo import freshgen as FG, freshness as F, freshref as FREF, recovery as R, timing as TM, \
    timinggen as TG  # noqa: E402
from tempo.engine import EMPTY, NO, YES  # noqa: E402

POOL, SEED = "timingsmoke", 5151
D = lambda wid, a, b, trs, tape: (wid, a, b, trs, tape, ("fx", "fx"))
A_ = lambda wid, a, b, trs, tape: (wid, a, b, trs, tape, ("fx", "fx"))


def make(domain, row):
    for att in range(60):
        try:
            return TG.build(row, domain, SEED + att, POOL)[1:]
        except AssertionError:
            continue
    raise AssertionError("cannot build")


def runs(tc, pub, hid, role, env="changing", tape=None, check_ref=True, request=None):
    ep, gc, env_ep = TG.goal_copy(pub, hid, role)
    req = request or F.p2_request(ep, gc)
    tp = hid["tape"] if tape is None else tape
    out = {s: TM.run(ep, gc, req, env, pub["transitions"], env_ep, tp, s) for s in TM.ORDER}
    if check_ref:
        for s, t in out.items():
            rf = FREF.reference_for(ep, gc, t["receipts"], pub["transitions"] if env == "changing" else [],
                                    t["projection_clock"])
            tc.assertEqual(sorted(map(str, rf["states"])), sorted(map(str, t["states"])), s)
            tc.assertEqual((rf["classes"], rf["choice"]), (t["candidates"], t["plan"]), s)
    return ep, gc, out


class Timing(unittest.TestCase):
    def test_01_fixed_event_timing_and_clock(self):
        pub, hid = make("delivery", D("t1", ("B", "prov"), ("YOU", "prov"), [("EA", "B", "C")], [(0, 1.5)]))
        self.assertEqual(pub["transitions"][0]["window"], {"lo": 12, "hi": 14})
        ep, gc, out = runs(self, pub, hid, "A")
        self.assertEqual(len({t["actual_preaction_state_sha256"] for t in out.values()}), 1)
        for s, t in out.items():
            c = t["clock"]
            self.assertEqual((c["offset"], c["episode_origin"]), (12, 12))
            self.assertEqual(t["applied_events"], [{"transition": "x1", "at": 13.5}])
        self.assertEqual([out[s]["clock"]["elapsed"]["execute_at"] for s in TM.ORDER], [2, 4, 4])
        self.assertEqual([out[s]["pre_action_wait"] for s in TM.ORDER], [2, 4, 4])
        self.assertEqual((out["DEFER"]["clock"]["measured_at"], out["DEFER"]["clock"]["received_at"]), (14, 16))
        late = TM.environment(TG.goal_copy(pub, hid, "A")[2], "changing", pub["transitions"],
                              [{"transition": "x1", "elapsed": 2.5}], TM.schedule_clock("DEFER"))
        self.assertEqual(late.state_at(16)[1], [])  # after the window: never

    def test_02_late_request_keeps_origin_base_and_window(self):
        row = A_("t2", {"T": ("empty", "ver"), "G": ("yes", "prov")}, {"S2": ("empty", "ver"), "D": ("no", "prov")},
                 [("install", "T", "W")], [])
        pub, hid = make("assembly", row)
        ep, gc, out = runs(self, pub, hid, "A")
        fT = f"{pub['world']['t']}.part"
        d = out["DEFER"]
        self.assertEqual(d["projection_clock"]["requested_at"], 12)
        self.assertEqual(d["relevant_support"][fT], "unknown")  # not reloaded as the stale verified singleton
        self.assertIn(fT, d["uncertain_unqueried"])
        self.assertIsNone(d["plan"])

    def test_03_sampling_at_request_time_differs(self):
        pub, hid = make("delivery", D("t3", ("B", "prov"), ("YOU", "prov"), [("EA", "B", "G")], [(0, 0.5)]))
        ep, gc, out = runs(self, pub, hid, "A")
        self.assertEqual(out["EARLY"]["receipts"][0]["value"], pub["world"]["b"])
        self.assertEqual(out["DEFER"]["receipts"][0]["value"], pub["world"]["g"])
        self.assertEqual(out["DEFER"]["plan"], "already")
        self.assertTrue(out["DEFER"]["success"] and out["DEFER"]["outcome_kind"] == "complete")
        self.assertIsNone(out["EARLY"]["plan"])

    def test_04_reception_cutoff_and_one_shot_counts(self):
        row = D("t4", ("B", "prov"), ("YOU", "prov"), [("EA", "B", "C"), ("EA", "C", "B")], [(0, 0.5), (1, 1.5)])
        pub, hid = make("delivery", row)
        f = f"{pub['goals']['A']['item']}.location"
        for tape, n_defer in (([{"transition": "x1", "elapsed": 0.5}, {"transition": "x2", "elapsed": 1.5}], 1),
                              ([{"transition": "x1", "elapsed": 0.5}], 1), ([], 1)):
            ep, gc, out = runs(self, pub, hid, "A", tape=tape)
            for t in out.values():
                self.assertTrue(t["receipt_absent_before_reception"] and t["history_preserved"])
            self.assertEqual(out["DEFER"]["n_states"], n_defer)
            self.assertEqual(sorted(s[f] for s in out["EARLY"]["states"]), sorted([pub["world"]["b"], pub["world"]["c"]]))
        # B at 14 after both changes: certain B (each change happens at most once)
        ep, gc, out = runs(self, pub, hid, "A", tape=[{"transition": "x1", "elapsed": 0.5},
                                                     {"transition": "x2", "elapsed": 1.5}])
        self.assertEqual([s[f] for s in out["DEFER"]["states"]], [pub["world"]["b"]])

    def test_05_stable_and_early_wait_equalities(self):
        pub, hid = make("delivery", D("t5", ("B", "prov"), ("YOU", "unres:B"), [("EA", "B", "C")], [(0, 0.5)]))
        for role in "AB":
            _, _, st = runs(self, pub, hid, role, "stable")
            self.assertEqual(len({(t["states_sha256"], t["plan"], t["success"], t["action_cost"], t["queried_facts"])
                                  for t in st.values()}), 1)
            for lam in TM.LAMBDAS:
                self.assertEqual(TM.utility(st["DEFER"], lam) - TM.utility(st["EARLY_WAIT"], lam), 0)
                self.assertEqual(TM.utility(st["DEFER"], lam) - TM.utility(st["EARLY"], lam), -2 * lam)
            _, _, ch = runs(self, pub, hid, role, "changing")
            self.assertEqual((ch["EARLY"]["states_sha256"], ch["EARLY"]["plan"]),
                             (ch["EARLY_WAIT"]["states_sha256"], ch["EARLY_WAIT"]["plan"]))
            for lam in TM.LAMBDAS:
                self.assertEqual(TM.utility(ch["EARLY_WAIT"], lam) - TM.utility(ch["EARLY"], lam), -2 * lam)

    def test_06_defer_resolves_queried_not_independent_unqueried_but_correlated(self):
        pub, hid = make("delivery", D("t6a", ("YOU", "prov"), ("B", "prov"), [("EA", "YOU", "G")], [(0, 1.5)]))
        _, _, out = runs(self, pub, hid, "A")
        self.assertEqual((out["EARLY"]["plan"], out["DEFER"]["plan"]), (None, "already"))
        row = A_("t6b", {"T": ("empty", "ver"), "G": ("yes", "prov")}, {"S2": ("empty", "ver"), "D": ("no", "prov")},
                 [("install", "T", "W")], [(0, 0.5)])
        pub, hid = make("assembly", row)
        _, _, out = runs(self, pub, hid, "A")
        self.assertIsNone(out["DEFER"]["plan"])
        self.assertEqual(out["DEFER"]["uncertain_unqueried"], [f"{pub['world']['t']}.part"])
        row = A_("t6c", {"T": ("G", "ver"), "G": ("no", "prov")}, {"S2": ("HI", "prov"), "D": ("no", "ver")},
                 [("return", "T", "G")], [(0, 0.5)])
        pub, hid = make("assembly", row)
        _, gc, out = runs(self, pub, hid, "A")
        fT = f"{pub['world']['t']}.part"
        self.assertNotIn(fT, out["DEFER"]["queried"])
        self.assertEqual(out["DEFER"]["relevant_support"][fT], EMPTY)  # inferred through the joint transition
        self.assertEqual(out["DEFER"]["plan"], "install")
        self.assertTrue(out["DEFER"]["success"])
        self.assertIsNone(out["EARLY"]["plan"])

    def test_07_outcome_kinds_scored_distinctly(self):
        row = A_("t7", {"T": ("G", "ver"), "G": ("no", "prov")}, {"S2": ("HI", "prov"), "D": ("no", "ver")},
                 [("return", "T", "G")], [(0, 0.5)])
        pub, hid = make("assembly", row)
        ep, gc, env_ep = TG.goal_copy(pub, hid, "A")
        req = F.p2_request(ep, gc)
        def run(plan, env="changing", tape=hid["tape"]):
            with mock.patch.object(TM.R, "choose", return_value=plan):
                return TM.run(ep, gc, req, env, pub["transitions"], env_ep, tape, "EARLY")
        if True:
            fc = run("already")
            self.assertEqual((fc["outcome_kind"], fc["false_completion"], fc["invalid_attempt"], fc["success"]),
                             ("complete", True, False, False))
            tc = run("already", "stable", [])
            self.assertEqual((tc["outcome_kind"], tc["false_completion"], tc["success"]), ("complete", False, True))
            dec = run(None, "stable", [])
            self.assertEqual((dec["outcome_kind"], dec["selected"], dec["decline_goal_already_true"], dec["success"]),
                             ("decline", False, True, False))
        pub2, hid2 = make("delivery", D("t7b", ("B", "prov"), ("YOU", "prov"), [("EA", "B", "C")], [(0, 0.5)]))
        ep2, gc2, env2 = TG.goal_copy(pub2, hid2, "A")
        with mock.patch.object(TM.R, "choose", return_value="b_cheap"):
            bad = TM.run(ep2, gc2, F.p2_request(ep2, gc2), "changing", pub2["transitions"], env2, hid2["tape"], "EARLY")
        self.assertEqual((bad["outcome_kind"], bad["invalid_attempt"], bad["false_completion"]), ("execute", True, False))

    def test_08_candidate_changes_vs_feasibility(self):
        row = A_("t8", {"T": ("empty", "prov"), "G": ("no", "prov")}, {"S2": ("empty", "ver"), "D": ("yes", "prov")},
                 [("on_hand", "G", "no", "yes")], [(0, 0.5)])
        pub, hid = make("assembly", row)
        _, _, out = runs(self, pub, hid, "A")
        t = out["DEFER"]
        self.assertEqual((t["candidate_gain"], t["candidate_loss"]), (["install"], ["order_install"]))
        self.assertTrue(t["menu_feasible"] and t["menu_feasible_at_origin"])  # feasible throughout
        self.assertEqual(t["plan"], "install")
        pub, hid = make("delivery", D("t8b", ("C", "prov"), ("YOU", "prov"), [("EA", "C", "YOU")], [(0, 0.5)]))
        _, _, out = runs(self, pub, hid, "A")
        t = out["DEFER"]
        self.assertTrue(t["menu_feasible"] and not t["menu_feasible_at_origin"])  # genuinely newly feasible
        self.assertEqual(t["plan"], "here")

    def test_09_conflicts_zero_query_and_prior_behaviour(self):
        pub, hid = make("delivery", D("t9", ("B", "prov"), ("YOU", "prov"), [("EA", "B", "C")], []))
        ep, gc, out = runs(self, pub, hid, "A", request={"fields": [], "budget_exhausted": False})
        for t in out.values():
            self.assertEqual((t["queried"], t["receipts"], t["queried_facts"]), ([], [], 0))
        ep, gc, env_ep = TG.goal_copy(pub, hid, "A")
        sc = TM.schedule_clock("DEFER")
        pc = TM.projection_clock(sc)
        env = TM.environment(env_ep, "changing", pub["transitions"], [], sc)
        eng, led = R.engine_from(ep, None, "c"), F.new_ledger("c")
        _, rec = F.sensor_query(env, led, "c", gc["relevant"], 14, 2)
        F.ingest_receipts(eng, led, rec, "q1")
        other = next(p for p in pub["spec"]["places"] if p != rec[0]["value"])
        led["receipts"].append(dict(rec[0], receipt_id="contra", value=other))
        pr = F.temporal_project(eng, led, "c", pub["transitions"], pc)
        self.assertEqual([c["field"] for c in pr["authority_conflicts"]], gc["relevant"])
        self.assertEqual(pr["n_states"] if "n_states" in pr else len(pr["states"]), 2)  # unresolved, not anchored

    def test_10_hidden_schedule_leakage(self):
        pub, hid = make("delivery", D("t10", ("B", "prov"), ("YOU", "prov"), [("EA", "B", "C")], []))
        same = [[{"transition": "x1", "elapsed": 0.5}], [{"transition": "x1", "elapsed": 1.5}]]
        a = runs(self, pub, hid, "A", tape=same[0])[2]
        b = runs(self, pub, hid, "A", tape=same[1])[2]
        for s in TM.ORDER:  # identical observations -> identical beliefs and choice
            self.assertEqual((a[s]["receipts_sha256"], a[s]["states_sha256"], a[s]["plan"]),
                             (b[s]["receipts_sha256"], b[s]["states_sha256"], b[s]["plan"]))
        n = runs(self, pub, hid, "A", tape=[])[2]
        for s in ("EARLY", "EARLY_WAIT"):
            self.assertEqual((a[s]["states_sha256"], a[s]["plan"]), (n[s]["states_sha256"], n[s]["plan"]))
        self.assertNotEqual(a["DEFER"]["receipts_sha256"], n["DEFER"]["receipts_sha256"])  # allowed to differ

    def test_11_early_equals_1_12_0_temporal_delay2(self):
        rows = [("delivery", FG.DELIVERY[0]), ("delivery", FG.DELIVERY[7]), ("assembly", FG.ASSEMBLY[9]),
                ("assembly", FG.ASSEMBLY[5])]
        for domain, row in rows:
            for att in range(60):
                try:
                    _, pub0, hid = FG.build(row, domain, 777 + att, "freshsmoke")
                    break
                except AssertionError:
                    continue
            pub = dict(pub0, transitions=TM.fixed_windows(pub0["transitions"]))
            for role in "AB":
                ep, gc, env_ep = FG.goal_copy(pub0, hid, role)
                req = F.p2_request(ep, gc)
                for env in TM.ENVS:
                    clk = F.make_clock(2)
                    old = F.run(ep, gc, req, env, pub0["transitions"],
                                F.Environment(env_ep, pub0["transitions"] if env == "changing" else [],
                                              hid["tape"] if env == "changing" else [], clk), clk)["temporal"]
                    new = TM.run(ep, gc, req, env, pub["transitions"], env_ep, hid["tape"], "EARLY")
                    self.assertEqual((old["states_sha256"], old["plan"], old["utility"], old["success"]),
                                     (new["states_sha256"], new["plan"], new["utility_base"], new["success"]))


if __name__ == "__main__":
    unittest.main()
