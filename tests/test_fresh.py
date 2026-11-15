"""No-model fixtures for V1.12.0 observation freshness (brief section 5, items 1-12, plus limits and zero-query).
Every fixture that produces a temporal projection is also checked against the independent reference
(tempo.freshref): exact reachable set, candidate classes and choice."""
import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tempo import freshgen as FG, freshness as F, freshref as FREF, recovery as R  # noqa: E402
from tempo.engine import CARRIED, EMPTY, NO, YES  # noqa: E402

POOL, SEED = "freshsmoke", 4242


def make(domain, row):
    for att in range(60):
        try:
            return FG.build(row, domain, SEED + att, POOL)
        except AssertionError:
            continue
    raise AssertionError("cannot build fixture world")


def go(pub, hid, role, env_kind="changing", delay=2, gap=0, tape=None, transitions=None, clock=None,
       request=None):
    ep, gc, env_ep = FG.goal_copy(pub, hid, role)
    trs = pub["transitions"] if transitions is None else transitions
    clk = clock or F.make_clock(delay, gap)
    tp = hid["tape"] if tape is None else tape
    env = F.Environment(env_ep, trs if env_kind == "changing" else [], tp if env_kind == "changing" else [], clk)
    req = request or F.p2_request(ep, gc)
    out = F.run(ep, gc, req, env_kind, trs, env, clk)
    return ep, gc, out


def ref(tc, ep, gc, out, env_kind="changing", transitions=None):
    """Assert the temporal arm equals the independent reference; return the reference."""
    t = out["temporal"]
    trs = (ep["transitions"] if transitions is None else transitions) if env_kind == "changing" else []
    rf = FREF.reference_for(ep, gc, t["receipts"], trs, t["clock"])
    key = lambda ss: sorted(tuple(sorted(s.items())) for s in ss)
    tc.assertEqual(key(t["states"]), key(rf["states"]))
    tc.assertEqual(t["candidates"], rf["classes"])
    tc.assertEqual(t["plan"], rf["choice"])
    return rf


D = lambda wid, a, b, trs, tape: (wid, a, b, trs, tape, ("fx", "fx"))


class Clock(unittest.TestCase):
    def test_clock_fields_and_ordering(self):
        c = F.make_clock(2)
        self.assertEqual((c["requested_at"], c["measured_at"], c["received_at"], c["execute_at"], c["offset"]),
                         (12, 12, 14, 14, 12))
        self.assertEqual(c["elapsed"], {"requested_at": 0, "measured_at": 0, "received_at": 2, "decision_at": 2,
                                        "execute_at": 2})
        c0 = F.make_clock(0)
        tr = {"window": {"from": "requested_at", "to": "execute_at"}}
        lo, hi = F.window(tr, c0)
        self.assertFalse(lo < 12.5 < hi)  # delay 0: empty window, nothing precedes action

    def test_environment_tape_respects_window_and_guard(self):
        pub, hid = make("delivery", D("f-env", ("B", "prov"), ("YOU", "prov"), [("EA", "B", "C")], [(0, 0.5)]))[1:]
        ep, gc, env_ep = FG.goal_copy(pub, hid, "A")
        f = gc["relevant"][0]
        for d, moved in ((0, False), (2, True)):
            env = F.Environment(env_ep, pub["transitions"], hid["tape"], F.make_clock(d))
            s, applied = env.state_at(F.make_clock(d)["execute_at"])
            self.assertEqual(bool(applied), moved)
            self.assertEqual(s[f] == pub["transitions"][0]["effect"][f], moved)
        late = F.Environment(env_ep, pub["transitions"], [{"transition": "x1", "elapsed": 2.5}], F.make_clock(2))
        self.assertEqual(late.state_at(14)[1], [])  # after the first action: disabled


class Fixtures(unittest.TestCase):
    # 1 stable parity
    def test_01_stable_parity_with_scoped_1_11_0(self):
        rows = [("delivery", D("f1d", ("B", "prov"), ("YOU", "unres:B"), [("EA", "B", "C")], [(0, 0.5)])),
                ("assembly", ("f1a", {"T": ("W", "prov"), "G": ("yes", "ver")},
                              {"S2": ("LO", "unres:HI"), "D": ("yes", "prov")}, [("remove", "T", "W")], [(0, 0.5)],
                              ("fx", "fx")))]
        for domain, row in rows:
            _, pub, hid = make(domain, row)
            for role in "AB":
                for d in (0, 1, 2):
                    ep, gc, out = go(pub, hid, role, "stable", d)
                    cf, tp = out["carry_forward"], out["temporal"]
                    self.assertEqual(cf["states_sha256"], tp["states_sha256"])
                    self.assertEqual((cf["plan"], cf["utility"]), (tp["plan"], tp["utility"]))
                    ref(self, ep, gc, out, "stable")
                    if d == 1:  # 1.11.0's own clock: identical to recovery.run's scoped contract
                        env_ep = FG.goal_copy(pub, hid, role)[2]
                        old = R.run(env_ep, gc)["scoped"]
                        self.assertEqual((old["queried"], old["plan"], old["utility"]),
                                         (tp["queried"], tp["plan"], tp["utility"]))

    def test_01b_stable_recovers_a_verified_conflict_like_1_11_0(self):
        _, pub, hid = make("delivery", D("f1c", ("B", "prov"), ("YOU", "prov"), [], []))
        pub = copy.deepcopy(pub)
        ep0, gc0, _ = FG.goal_copy(pub, hid, "A")
        f = gc0["relevant"][0]
        wrong = next(p for p in pub["spec"]["places"] if p not in (hid["truth"][f], pub["world"]["c"]))
        last = max(r["received_at"] for r in pub["reports"])
        pub["reports"] = [r for r in pub["reports"] if not any(a["field"] == f for a in r["assertions"])] + [
            {"rid": "v1", "received_at": last, "status": "verified", "type": "state", "source": "env",
             "assertions": [{"field": f, "at": 3, "value": wrong}]},
            {"rid": "v2", "received_at": last, "status": "verified", "type": "state", "source": "env",
             "assertions": [{"field": f, "at": 4, "value": hid["truth"][f]}]}]
        pub["reports"][-2]["assertions"][0]["at"] = 4  # same time, contradictory: a verified-verified conflict
        ep, gc, out = go(pub, hid, "A", "stable", 1)
        self.assertEqual(out["temporal"]["queried"], [f])
        old = R.run(FG.goal_copy(pub, hid, "A")[2], gc)
        self.assertIsNone(old["strict"]["plan"])
        self.assertEqual(old["scoped"]["plan"], out["temporal"]["plan"])
        self.assertIsNotNone(out["temporal"]["plan"])
        ref(self, ep, gc, out, "stable")

    # 2 relevant change makes the old plan illegal
    def test_02_relevant_change_during_delivery(self):
        _, pub, hid = make("delivery", D("f2", ("B", "prov"), ("YOU", "prov"), [("EA", "B", "C")], [(0, 0.5)]))
        ep, gc, out = go(pub, hid, "A")
        cf, tp = out["carry_forward"], out["temporal"]
        self.assertTrue(cf["invalid_attempt"])
        self.assertIsNone(tp["plan"])
        self.assertFalse(tp["false_permission"])
        self.assertEqual(tp["n_states"], 2)
        self.assertTrue(tp["actual_in_support"])
        ref(self, ep, gc, out)

    # 3 possible change, none realized
    def test_03_possible_change_not_realized_keeps_uncertainty(self):
        _, pub, hid = make("delivery", D("f3", ("B", "prov"), ("YOU", "prov"), [("EA", "B", "C")], []))
        ep, gc, out = go(pub, hid, "A")
        cf, tp = out["carry_forward"], out["temporal"]
        self.assertTrue(cf["success"])
        self.assertIsNone(tp["plan"])
        self.assertEqual(tp["uncertain_relevant"], gc["relevant"])
        self.assertTrue(tp["missed_opportunity"])
        ref(self, ep, gc, out)

    # 4 unrelated change
    def test_04_unrelated_change_keeps_decision(self):
        _, pub, hid = make("delivery", D("f4", ("B", "prov"), ("YOU", "prov"), [("EB", "YOU", "C")], [(0, 0.5)]))
        ep, gc, out = go(pub, hid, "A")
        st = go(pub, hid, "A", "stable")[2]
        self.assertEqual(out["temporal"]["plan"], st["temporal"]["plan"])
        self.assertIsNotNone(out["temporal"]["plan"])
        self.assertEqual(out["temporal"]["utility"], st["temporal"]["utility"])
        ref(self, ep, gc, out)

    # 5 a transition that changes a value but preserves the needed predicate; age alone is not uncertainty
    def test_05_preserving_transition_and_age(self):
        row = ("f5", {"T": ("G", "prov"), "G": ("no", "ver")}, {"S2": ("empty", "prov"), "D": ("no", "ver")},
               [("on_hand", "G", "no", "yes")], [(0, 0.5)], ("fx", "fx"))
        _, pub, hid = make("assembly", row)
        ep, gc, out = go(pub, hid, "A")
        tp = out["temporal"]
        self.assertEqual(tp["plan"], "already")
        self.assertTrue(tp["success"])
        self.assertEqual(tp["n_states"], 2)  # G.on_hand is genuinely uncertain, the plan does not care
        ref(self, ep, gc, out)
        # a declared change whose guard is false in every supported state: the old reading stays decisive
        _, pub2, hid2 = make("delivery", D("f5b", ("YOU", "prov"), ("B", "prov"), [("EA", "B", "C")], []))
        ep2, gc2, out2 = go(pub2, hid2, "A", delay=2)
        self.assertEqual(out2["temporal"]["plan"], "here")
        self.assertEqual(out2["temporal"]["n_states"], 1)
        ref(self, ep2, gc2, out2)

    # 6 delayed old reading vs an immediate reading after the change, separate reset branches
    def test_06_delayed_vs_fresh_reading_branches(self):
        _, pub, hid = make("delivery", D("f6", ("B", "prov"), ("YOU", "prov"), [("EA", "B", "G")], [(0, 0.5)]))
        ep, gc, out = go(pub, hid, "A", delay=2)
        f = gc["relevant"][0]
        self.assertEqual(out["temporal"]["receipts"][0]["value"], pub["world"]["b"])
        self.assertEqual(sorted(s[f] for s in out["temporal"]["states"]), sorted([pub["world"]["b"], pub["world"]["g"]]))
        self.assertIsNone(out["temporal"]["plan"])
        ref(self, ep, gc, out)
        # reset branch: same world and tape, a reading measured at 13 (after the 12.5 change), received at 13
        clk = dict(F.make_clock(0), measured_at=13, received_at=13, decision_at=13, execute_at=13)
        ep2, gc2, env_ep = FG.goal_copy(pub, hid, "A")
        env = F.Environment(env_ep, pub["transitions"], hid["tape"], clk)
        eng = R.engine_from(ep2, None, "f6b")
        led = F.new_ledger("f6b")
        _, rec = F.sensor_query(env, led, "f6b", [f], 12, 0, measured_at=13)
        F.ingest_receipts(eng, led, rec, "q1")
        pr = F.temporal_project(eng, led, "f6b", pub["transitions"], clk)
        self.assertEqual(pr["states"], [dict(pr["states"][0], **{f: pub["world"]["g"]})])
        self.assertEqual(len(pr["states"]), 1)  # hand-worked: the change happened before 13 and cannot recur
        self.assertEqual(R.choose(ep2, gc2, pr["states"]), "already")
        rf = FREF.reference_for(ep2, gc2, rec, pub["transitions"], clk)
        self.assertEqual(rf["states"], pr["states"])

    # 7 change between receipt and execution
    def test_07_propagation_ends_at_action_time(self):
        _, pub, hid = make("delivery", D("f7", ("B", "prov"), ("YOU", "prov"), [("EA", "B", "C")], []))
        ep, gc, out0 = go(pub, hid, "A", delay=0, gap=0)
        self.assertEqual(out0["temporal"]["n_states"], 1)
        ep, gc, out1 = go(pub, hid, "A", delay=0, gap=1)
        t = out1["temporal"]
        self.assertEqual((t["clock"]["received_at"], t["clock"]["execute_at"]), (12, 13))
        self.assertEqual(t["n_states"], 2)
        self.assertIsNone(t["plan"])
        ref(self, ep, gc, out1)

    # 8 an unqueried verified prerequisite becomes uncertain while a different fact is in transit
    def test_08_unqueried_prerequisite_no_fallback(self):
        row = ("f8", {"T": ("empty", "ver"), "G": ("yes", "prov")}, {"S2": ("empty", "ver"), "D": ("no", "prov")},
               [("install", "T", "W")], [], ("fx", "fx"))
        _, pub, hid = make("assembly", row)
        ep, gc, out = go(pub, hid, "A")
        fT = f"{pub['world']['t']}.part"
        self.assertNotIn(fT, out["temporal"]["queried"])
        self.assertEqual(out["temporal"]["relevant_support"][fT], "unknown")
        self.assertEqual(out["carry_forward"]["relevant_support"][fT], EMPTY)
        self.assertIsNone(out["temporal"]["plan"])
        ref(self, ep, gc, out)

    # 9 two accurate readings at different times processed jointly
    def test_09_readings_at_different_times(self):
        row = ("f9", {"T": ("G", "prov"), "G": ("no", "prov")}, {"S2": ("HI", "ver"), "D": ("no", "ver")},
               [("return", "T", "G")], [(0, 0.5)], ("fx", "fx"))
        _, pub, hid = make("assembly", row)
        ep, gc, env_ep = FG.goal_copy(pub, hid, "A")
        fT, fG = f"{pub['world']['t']}.part", f"{pub['world']['g']}.on_hand"
        clk = F.make_clock(1, 1)  # execute at 14
        for tape, want in (([{"transition": "x1", "elapsed": 0.5}], [{fT: EMPTY, fG: YES}]),
                           ([], [{fT: "G", fG: NO}, {fT: EMPTY, fG: YES}])):
            env = F.Environment(env_ep, pub["transitions"], tape, clk)
            eng = R.engine_from(ep, None, "f9")
            led = F.new_ledger("f9")
            _, r1 = F.sensor_query(env, led, "f9", [fT], 12, 1, measured_at=12)
            _, r2 = F.sensor_query(env, led, "f9", [fG], 12, 0, measured_at=13)
            F.ingest_receipts(eng, led, r1, "q1")
            F.ingest_receipts(eng, led, r2, "q2")
            pr = F.temporal_project(eng, led, "f9", pub["transitions"], clk)
            got = sorted(({fT: s[fT], fG: s[fG]} for s in pr["states"]), key=str)
            want = sorted(({fT: (pub["world"]["g"] if v[fT] == "G" else v[fT]), fG: v[fG]} for v in want), key=str)
            self.assertEqual(got, want)
            rf = FREF.reference_for(ep, gc, r1 + r2, pub["transitions"], clk)
            self.assertEqual(sorted(map(str, rf["states"])), sorted(map(str, pr["states"])))
            # the naive simultaneous snapshot (carry-forward) asserts T holds G, contradicting the first branch
            cf = R.project(eng, eng.view("current", 13), led, 13, "f9")
            self.assertEqual({s[fT] for s in cf["states"]}, {pub["world"]["g"]})

    # 10 an arrival after measurement opens a legal opportunity
    def test_10_arrival_opens_opportunity_counted(self):
        _, pub, hid = make("delivery", D("f10", ("C", "prov"), ("YOU", "prov"), [("EA", "C", "YOU")], [(0, 0.5)]))
        ep, gc, out = go(pub, hid, "A")
        for p in F.PROJECTIONS:
            self.assertIsNone(out[p]["plan"])
            self.assertTrue(out[p]["opportunity"] and out[p]["missed_opportunity"])
        self.assertEqual(out["temporal"]["valid_at_execute"], ["here"])
        self.assertEqual(out["temporal"]["valid_at_measure"], [])
        ref(self, ep, gc, out)

    # 11 missing fields, empty support, joint invariants, equal-time contradictions, sensor refusals
    def test_11a_guard_on_absent_field_makes_effect_unknown(self):
        _, pub, hid = make("delivery", D("f11a", ("B", "prov"), ("YOU", "prov"), [("EB", "YOU", "C")], []))
        spec = pub["spec"]
        fb = f"{pub['goals']['B']['item']}.location"
        tr = pub["transitions"][0]
        s = {"agent.at": pub["world"]["you"], "agent.hands": "empty"}
        self.assertEqual(F._succ(spec, s, tr), s)  # absent guard field: effect field stays absent
        self.assertIsNone(F._succ(spec, dict(s, **{fb: pub["world"]["b"]}), tr))
        self.assertEqual(len(F.reach(spec, {(F._key(s), frozenset())}, [(tr, (12, 14))], 12, 14)), 2)
        self.assertEqual(FREF.reachable(spec, {}, s, [], [(tr, 12, 14)], 12, 14), [s])

    def test_11b_empty_support_is_a_conflict(self):
        _, pub, hid = make("delivery", D("f11b", ("B", "prov"), ("YOU", "prov"), [], []))
        ep, gc, env_ep = FG.goal_copy(pub, hid, "A")
        f = gc["relevant"][0]
        clk = dict(F.make_clock(1), received_at=13, decision_at=13, execute_at=13)
        env = F.Environment(env_ep, [], [], clk)
        eng, led = R.engine_from(ep, None, "f11b"), F.new_ledger("f11b")
        _, r1 = F.sensor_query(env, led, "f11b", [f], 12, 1, measured_at=12)
        _, r2 = F.sensor_query(env, led, "f11b", [f], 12, 0, measured_at=13)
        r2[0]["value"] = led["receipts"][-1]["value"] = pub["world"]["g"]  # an impossible later value (no change declared)
        F.ingest_receipts(eng, led, r1, "q1")
        pr = F.temporal_project(eng, led, "f11b", [], clk)
        self.assertEqual((pr["status"], pr["states"]), ("empty_support", []))
        self.assertIsNone(R.choose(ep, gc, pr["states"]))
        self.assertEqual(FREF.reference_for(ep, gc, led["receipts"], [], clk)["states"], [])

    def test_11c_declarations_must_preserve_invariants(self):
        _, pub, _ = make("delivery", D("f11c", ("B", "prov"), ("YOU", "prov"), [], []))
        f = f"{pub['goals']['A']['item']}.location"
        bad = {"id": "bad", "guard": {f: pub["world"]["b"]}, "effect": {f: CARRIED},
               "window": {"from": "requested_at", "to": "execute_at"}}
        with self.assertRaises(F.DeclarationError):
            F.check_declaration(pub["spec"], bad)
        with self.assertRaises(F.DeclarationError):
            F.check_declaration(pub["spec"], dict(bad, effect={"agent.hands": pub["goals"]["A"]["item"]}))
        _, apub, _ = make("assembly", ("f11c2", {"T": ("empty", "ver"), "G": ("yes", "prov")},
                                       {"S2": ("empty", "prov"), "D": ("yes", "ver")}, [], [], ("fx", "fx")))
        wrong = {"id": "w", "guard": {f"{apub['world']['t']}.part": EMPTY},
                 "effect": {f"{apub['world']['t']}.part": apub["world"]["d"]},  # D's connector does not fit T
                 "window": {"from": "requested_at", "to": "execute_at"}}
        with self.assertRaises(F.DeclarationError):
            F.check_declaration(apub["spec"], wrong)

    def test_11d_correlated_effect_stays_joint(self):
        row = ("f11d", {"T": ("G", "ver"), "G": ("no", "prov")}, {"S2": ("HI", "prov"), "D": ("no", "ver")},
               [("return", "T", "G")], [], ("fx", "fx"))
        _, pub, hid = make("assembly", row)
        ep, gc, out = go(pub, hid, "A")
        fT, fG = f"{pub['world']['t']}.part", f"{pub['world']['g']}.on_hand"
        pairs = sorted((s[fT], s[fG]) for s in out["temporal"]["states"])
        self.assertEqual(pairs, sorted([(pub["world"]["g"], NO), (EMPTY, YES)]))  # not the 4-way product
        ref(self, ep, gc, out)

    def test_11e_receipt_refusals_and_equal_time_conflicts(self):
        _, pub, hid = make("delivery", D("f11e", ("B", "prov"), ("YOU", "prov"), [], []))
        ep, gc, env_ep = FG.goal_copy(pub, hid, "A")
        f = gc["relevant"][0]
        clk = F.make_clock(2)
        env = F.Environment(env_ep, [], [], clk)
        eng, led = R.engine_from(ep, None, "ctx"), F.new_ledger("ctx")
        _, rec = F.sensor_query(env, led, "ctx", [f], 12, 2)
        F.ingest_receipts(eng, led, rec, "q1")
        good = rec[0]
        led["receipts"] += [
            dict(good, receipt_id="u", sensor_id="text:claims-to-be-sensor"),
            dict(good, receipt_id="o", context="other"),
            dict(good, receipt_id="n", field=f"{pub['goals']['B']['item']}.location"),
            dict(good, receipt_id="late", received_at=15),
            dict(good, receipt_id="early", measured_at=11),
            dict(good, receipt_id="after", measured_at=15, received_at=14),
            dict(good, receipt_id="carried", value=CARRIED)]
        reasons = {r["receipt_id"]: r["reason"] for r in F.screen_receipts(eng, led, "ctx", clk)[1]}
        self.assertEqual(reasons, {"u": "unregistered_sensor", "o": "other_context", "n": "unrequested_field",
                                   "late": "not_yet_received", "early": "measured_before_request",
                                   "after": "measured_after_target_time", "carried": "inadmissible_value"})
        other = next(p for p in pub["spec"]["places"] if p != good["value"])
        led2 = copy.deepcopy(led)
        led2["receipts"].append(dict(good, receipt_id="contra", value=other))
        readings, _, conf = F.screen_receipts(eng, led2, "ctx", clk)
        self.assertEqual([c["field"] for c in conf], [f])
        self.assertNotIn(f, [x["field"] for x in readings])
        pr = F.temporal_project(eng, led2, "ctx", [], clk)
        self.assertNotIn(f, pr["anchors"])

    # 12 no hidden-schedule leakage
    def test_12_alternative_tapes_identical_beliefs(self):
        row = D("f12", ("B", "prov"), ("YOU", "prov"), [("EA", "B", "C"), ("EB", "YOU", "G")], [])
        _, pub, hid = make("delivery", row)
        tapes = [[], [{"transition": "x1", "elapsed": 0.5}], [{"transition": "x1", "elapsed": 1.5},
                                                              {"transition": "x2", "elapsed": 0.5}]]
        for role in "AB":
            outs = [go(pub, hid, role, tape=tp)[2] for tp in tapes]
            for p in F.PROJECTIONS:
                for k in ("receipts_sha256", "ledger_sha256", "states_sha256", "candidates", "plan", "log_head"):
                    self.assertEqual(len({str(o[p][k]) for o in outs}), 1, (role, p, k))
            self.assertEqual(len({str(o["temporal"]["applied_events"]) for o in outs}), 3)


class Other(unittest.TestCase):
    def test_zero_query_unqueried_facts_still_propagate(self):
        row = ("fz", {"T": ("empty", "ver"), "G": ("yes", "ver")}, {"S2": ("empty", "ver"), "D": ("yes", "prov")},
               [("install", "T", "W")], [], ("fx", "fx"))
        _, pub, hid = make("assembly", row)
        ep, gc, out = go(pub, hid, "A")
        self.assertEqual(out["temporal"]["queried"], [])
        self.assertEqual(out["temporal"]["receipts"], [])
        self.assertEqual(out["carry_forward"]["plan"], "install")
        self.assertIsNone(out["temporal"]["plan"])
        ref(self, ep, gc, out)
        st = go(pub, hid, "A", "stable")[2]
        self.assertEqual(st["temporal"]["plan"], "install")

    def test_state_limit_raises(self):
        _, pub, hid = make("delivery", D("fl", ("B", "prov"), ("YOU", "prov"), [("EA", "B", "C")], []))
        old = F.MAX_STATES
        try:
            F.MAX_STATES = 1
            with self.assertRaises(F.LimitExceeded):
                go(pub, hid, "A")
        finally:
            F.MAX_STATES = old

    def test_out_of_scope_later_report(self):
        _, pub, hid = make("delivery", D("fo", ("B", "prov"), ("YOU", "prov"), [], []))
        pub = copy.deepcopy(pub)
        f = f"{pub['goals']['A']['item']}.location"
        ep, gc, env_ep = FG.goal_copy(pub, hid, "A")
        clk = F.make_clock(2)
        eng, led = R.engine_from(ep, None, "c"), F.new_ledger("c")
        eng.ingest({"rid": "late", "received_at": 13, "status": "verified", "type": "state", "source": "env",
                    "assertions": [{"field": f, "at": 13, "value": pub["world"]["b"]}]})
        pr = F.temporal_project(eng, led, "c", [], clk)
        self.assertEqual((pr["status"], pr["states"]), ("out_of_scope_later_report", []))

    def test_history_and_log_preserved(self):
        _, pub, hid = make("delivery", D("fh", ("B", "prov"), ("YOU", "prov"), [("EA", "B", "C")], [(0, 0.5)]))
        ep, gc, out = go(pub, hid, "A")
        for p in F.PROJECTIONS:
            self.assertTrue(out[p]["earlier_view_preserved"] and out[p]["log_unchanged_by_projection"])
        self.assertEqual(out["carry_forward"]["log_head"], out["temporal"]["log_head"])
        self.assertEqual(out["carry_forward"]["historical_detail_sha256"], out["temporal"]["historical_detail_sha256"])


if __name__ == "__main__":
    unittest.main()
