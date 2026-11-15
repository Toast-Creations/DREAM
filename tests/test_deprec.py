"""No-model tests for V1.11.0: dependency/invariant parity and the scoped current-observation authority rule."""
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from tempo import agentstate as AS, goals as GL, recovery as R, text_channel as TC, transfer as T  # noqa: E402
from tempo.engine import CARRIED, EMPTY, NO, YES  # noqa: E402
from dream_core import localpaths as LP  # public release: local paths from environment

PY = sys.executable
RUNS = Path(os.environ.get("DREAM_RUNS", f"{LP.RUNS}"))
GOALTR = RUNS / "temporal-deferred-goal-20261105-154052"


def load(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]


def run(*args):
    r = subprocess.run([PY, "-B", *map(str, args)], cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        raise AssertionError(r.stdout[-3000:] + r.stderr[-3000:])
    return r


def state_rep(rid, rec, status, assertions):
    return {"rid": rid, "received_at": rec, "status": status, "type": "state", "source": "extractor:qwen3-8b",
            "assertions": assertions}


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.hub = Path(cls.tmp.name)
        run("scripts/deprec_generate.py", "--hub", cls.hub, "--set", "deprec")
        d = cls.hub / "data"
        cls.eps = load(d / "deprec-episodes.jsonl")
        cls.calls = load(d / "deprec-calls.jsonl")
        cls.gold = {g["call_id"]: g for g in load(d / "deprec-gold.jsonl")}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def ctx(self, ep, role):
        ge, gc = T.goal_episode(ep, role)
        return ge, R.context(ge, gc["goal"])

    def channel(self, ep, replace=None, extra=None):
        """Text channel from gold replies, with some replaced; extra: reports appended after the six."""
        cids = [f"{ep['episode_id']}|prose|r{k}" for k in range(1, 7)]
        raws = [(replace or {}).get(c, json.dumps(self.gold[c]["gold"])) for c in cids]
        ch = TC.build_channel(ep, raws, [self.gold[c]["registry"] for c in cids], ep["prose_texts"])
        for rep in extra or []:
            ch["sequence"].append({"kind": "report", "report": rep})
        return ch

    def delivery(self, b_type=None):
        return next(e for e in self.eps if e["domain"] == "delivery" and (b_type is None or e["b_type"] == b_type)
                    and R.true_valid_plans(*self.ctx(e, "A")) and R.true_valid_plans(*self.ctx(e, "B")))

    def assembly_with(self, cond):
        return next(e for e in self.eps if e["domain"] == "assembly" and cond(e))


class Invariants(Base):
    def test_take_put_sequences_and_capacity(self):
        ep = self.delivery()
        spec = ep["spec"]
        s = R.truth_state(ep)
        xa, xb = ep["goals"]["A"]["item"], ep["goals"]["B"]["item"]
        s = dict(s, **{f"{xa}.location": s["agent.at"], f"{xb}.location": s["agent.at"]})
        self.assertTrue(AS.admissible(spec, s))
        _, ok, s1 = AS.evaluate(spec, s, ["take", xa])
        self.assertTrue(ok)
        self.assertEqual((s1["agent.hands"], s1[f"{xa}.location"]), (xa, CARRIED))
        self.assertTrue(AS.admissible(spec, s1))
        vals, ok, _ = AS.evaluate(spec, s1, ["take", xb])  # one item at a time
        self.assertFalse(ok)
        self.assertFalse(vals["hands_empty"])
        _, ok, s2 = AS.evaluate(spec, s1, ["put", xa])
        self.assertTrue(ok)
        self.assertEqual((s2["agent.hands"], s2[f"{xa}.location"]), ("empty", s["agent.at"]))
        _, ok, s3 = AS.evaluate(spec, s2, ["take", xb])
        self.assertTrue(ok and AS.admissible(spec, s3))
        self.assertFalse(AS.admissible(spec, dict(s3, **{f"{xa}.location": CARRIED})))  # two carried

    def test_initial_state_consistency(self):
        ep = copy.deepcopy(self.delivery())
        R.truth_state(ep)
        ep["truth"][f"{ep['goals']['B']['item']}.location"] = CARRIED
        with self.assertRaises(AssertionError):
            R.truth_state(ep)
        ep2 = copy.deepcopy(self.delivery())
        ep2["truth"]["agent.at"] = next(p for p in ep2["spec"]["places"] if p != ep2["spec"]["agent_at"])
        with self.assertRaises(AssertionError):
            R.truth_state(ep2)

    def test_observed_cross_goal_case_synthetic(self):
        """An unrelated crate's location becomes unknown including "carried by you" (as in 1.10.0
        del-corrected-0): the frozen 1.10.0 loop declines goal A; the repaired one plans, and records why."""
        for ep in self.eps:
            if ep["domain"] != "delivery":
                continue
            ge, gc = self.ctx(ep, "A")
            if R.run(ge, gc, "P0_accepted")["strict"]["plan"] is None:
                continue
            xb = ep["goals"]["B"]["item"]
            fb = f"{xb}.location"
            unk = {"rid": "x1", "received_at": 12, "status": "verified", "type": "event", "source": "extractor:qwen3-8b",
                   "assertions": [{"field": fb, "at": 11, "to_options": [ep["spec"]["places"][0], CARRIED]}]}
            ch = self.channel(ep, extra=[unk])
            old = GL.run_policy(ge, T.goal_episode(ep, "A")[1], "P0_accepted", channel=ch)
            new = R.run(ge, gc, "P0_accepted", channel=ch)["strict"]
            self.assertIsNone(old["plan"])  # 1.10.0: derived hands unresolved
            self.assertIsNotNone(new["plan"])
            self.assertEqual(new["invariant_before"][fb]["excluded"], [CARRIED])
            self.assertEqual(new["invariant_before"][fb]["status"], "narrowed")
            self.assertEqual(new["historical_before"][fb], "unknown")  # history unchanged
            return
        self.fail("no delivery world to test")

    @unittest.skipUnless((GOALTR / "stages" / "main" / "calls").exists(), "1.10.0 hub not present")
    def test_observed_cross_goal_case_real(self):
        ep = next(e for e in load(GOALTR / "data" / "goaltr-episodes.jsonl") if e["episode_id"] == "goaltr-del-corrected-0")
        gold = {g["call_id"]: g for g in load(GOALTR / "data" / "goaltr-gold.jsonl")}
        cids = [f"{ep['episode_id']}|prose|r{k}" for k in range(1, 7)]
        raw = {c: json.loads((GOALTR / "stages" / "main" / "calls" / f).read_text())["raw"]
               for c in cids for f in [next(p.name for p in (GOALTR / "stages" / "main" / "calls").glob("*.json")
                                            if json.loads(p.read_text())["call_id"] == c)]}
        ch = TC.build_channel(ep, [raw[c] for c in cids], [gold[c]["registry"] for c in cids], ep["prose_texts"])
        ge, gc = T.goal_episode(ep, "A")
        self.assertIsNone(GL.run_policy(ge, gc, "P2_selective", channel=ch)["plan"])
        x = R.run(ge, R.context(ge, gc["goal"]), "P2_selective", channel=ch)["strict"]
        self.assertEqual((x["plan"], x["success"]), ("here", True))

    def test_unsupported_carrying_is_a_diagnosable_inconsistency(self):
        ep = self.delivery()
        xb = ep["goals"]["B"]["item"]
        fb = f"{xb}.location"
        bad = state_rep("x1", 12, "verified", [{"field": fb, "at": 2, "value": CARRIED}])
        ch = self.channel(ep, extra=[bad])
        ga, gca = self.ctx(ep, "A")
        sa = R.run(ga, gca, "P2_selective")["strict"]
        ta = R.run(ga, gca, "P2_selective", channel=ch)["strict"]
        self.assertEqual((ta["plan"], ta["utility"]), (sa["plan"], sa["utility"]))  # A unaffected
        self.assertEqual(ta["invariant_before"][fb]["status"], "invariant_conflict")
        self.assertIn("x1", ta["invariant_before"][fb]["support"])  # provenance kept
        gb, gcb = self.ctx(ep, "B")
        x = R.run(gb, gcb, "P2_selective", channel=ch)
        self.assertIn(fb, x["strict"]["queried"])
        self.assertEqual(x["strict"]["state_before"][fb], "conflict")
        self.assertEqual(x["strict"]["historical_before"][fb], CARRIED)  # the assertion itself is not discarded
        self.assertEqual(x["strict"]["queried"], x["scoped"]["queried"])

    def test_connector_invariant_and_transitive_order_relevance(self):
        ep = self.assembly_with(lambda e: "order_install" in R.context(T.goal_episode(e, "A")[0], e["goals"]["A"])["plans"])
        ge, gc = self.ctx(ep, "A")
        spec = AS._spec(ep["spec"])
        g = gc["goal"]["part"]
        holders = AS.actions(spec)["order"][0][2][2](g)
        self.assertTrue(set(holders) <= set(gc["relevant"]))
        other = [sl for sl in spec.slots if f"{sl}.part" not in holders]
        self.assertTrue(other)
        f = f"{other[0]}.part"
        self.assertFalse(AS.admissible(spec, {f: g}))  # incompatible connector
        bad = {"rid": "x1", "received_at": 12, "status": "verified", "type": "event", "source": "extractor:qwen3-8b",
               "assertions": [{"field": f, "at": 11, "to": g}]}  # consistent history, physically impossible value
        t = R.run(ge, gc, "P0_accepted", channel=self.channel(ep, extra=[bad]))["strict"]
        self.assertEqual(t["historical_before"][f], g)
        s = R.run(ge, gc, "P0_accepted")["strict"]
        self.assertEqual((t["plan"], t["utility"]), (s["plan"], s["utility"]))
        self.assertEqual(t["invariant_before"][f]["status"], "invariant_conflict")

    def test_absent_field_is_unknown_to_the_planner(self):
        ep = self.assembly_with(lambda e: "order_install" in R.context(T.goal_episode(e, "A")[0], e["goals"]["A"])["plans"])
        ge, gc = self.ctx(ep, "A")
        g, sl = gc["goal"]["part"], gc["goal"]["slot"]
        s = {f"{sl}.part": EMPTY, f"{g}.on_hand": NO}
        table = AS.actions(ep["spec"])
        plan = gc["plans"]["order_install"]
        self.assertTrue(R.guaranteed(ep["spec"], [s], ep["world"], gc["goal"], plan, table))
        s.pop(f"{g}.on_hand")  # conflicted: absent from the compatible states
        self.assertFalse(R.guaranteed(ep["spec"], [s], ep["world"], gc["goal"], plan, table))

    def test_relevance_equals_frozen_rule_and_agent_reads_are_declared(self):
        for ep in self.eps:
            for role in ("A", "B"):
                ge, gco = T.goal_episode(ep, role)
                gc = R.context(ge, gco["goal"])
                self.assertEqual(gc["relevant"], gco["relevant"])
                self.assertEqual(gc["agent_reads"], ["agent.at", "agent.hands"] if ep["domain"] == "delivery" else [])

    def test_view_refuses_after_an_action(self):
        ep = self.delivery()
        eng = R.engine_from(ep)
        eng.log.append("execution", {"exec_id": "e1"})
        with self.assertRaises(AS.InvariantViolationInPhase):
            eng.view("current", 12)


class Authority(Base):
    def conflict_case(self):
        """A delivery world where goal B's crate gets a verified-verified conflict (event read as a state)."""
        for ep in self.eps:
            if ep["domain"] != "delivery" or ep["b_type"] != "b_changed":
                continue
            gb, gcb = self.ctx(ep, "B")
            if not R.true_valid_plans(gb, gcb):
                continue
            fb = gcb["relevant"][0]
            ks = [i for i, r in enumerate(ep["records_v02"], 1) if r["kind"] == "change" and r["payload"]["field"] == fb]
            if not ks:
                continue
            cid = f"{ep['episode_id']}|prose|r{max(ks)}"
            bad = copy.deepcopy(self.gold[cid]["gold"])
            bad["kind"], bad["payload"] = "observation", {"field": fb, "value": bad["payload"]["to"]}
            ch = self.channel(ep, {cid: json.dumps(bad)})
            x = R.run(gb, gcb, "P2_selective", channel=ch)
            if x["strict"]["conflict_at_decision"] == [fb]:
                return ep, gb, gcb, fb, ch, x
        self.fail("no conflict case")

    def test_conflict_recovered_history_kept(self):
        ep, gb, gcb, fb, ch, x = self.conflict_case()
        s, c = x["strict"], x["scoped"]
        self.assertEqual(s["queried"], [fb])
        self.assertEqual(s["receipts"], c["receipts"])
        self.assertIsNone(s["plan"])
        self.assertTrue(c["success"])
        self.assertEqual(c["anchors"][fb]["historical_status"], "conflict")
        self.assertTrue(c["anchors"][fb]["historical_culprits"])
        self.assertIn(fb, c["historical_conflicts_at_decision"])  # the historical reconstruction stays conflicted
        self.assertEqual(s["historical_detail_sha256"], c["historical_detail_sha256"])
        self.assertEqual(s["log_head"], c["log_head"])
        self.assertTrue(c["earlier_view_preserved"] and c["unanchored_fields_unchanged"])

    def test_structured_and_perfect_extraction_unchanged_by_rule(self):
        for ep in self.eps:
            ch = self.channel(ep)
            for role in ("A", "B"):
                ge, gc = self.ctx(ep, role)
                xs, xt = R.run(ge, gc), R.run(ge, gc, channel=ch)
                for k in ("queried", "plan", "success", "utility"):
                    self.assertEqual(xs["strict"][k], xs["scoped"][k])
                    self.assertEqual(xs["strict"][k], xt["strict"][k])
                    self.assertEqual(xs["strict"][k], xt["scoped"][k])

    def test_query_free_and_settled_wrong_extraction_untouched(self):
        ep, gb, gcb, fb, _, _ = self.conflict_case()
        ks = [i for i, r in enumerate(ep["records_v02"], 1) if r["kind"] == "change" and r["payload"]["field"] == fb]
        cid = f"{ep['episode_id']}|prose|r{max(ks)}"
        wrong = copy.deepcopy(self.gold[cid]["gold"])
        others = [p for p in ep["spec"]["places"] if p != wrong["payload"]["to"]]
        wrong["payload"]["to"] = others[0]  # a coherent, verified-looking wrong event
        x = R.run(gb, gcb, "P2_selective", channel=self.channel(ep, {cid: json.dumps(wrong)}))
        self.assertEqual(x["strict"]["queried"], [])
        self.assertEqual(x["scoped"]["anchors"], {})
        for k in ("plan", "success", "utility"):
            self.assertEqual(x["strict"][k], x["scoped"][k])

    def _setup(self):
        ep, gb, gcb, fb, ch, _ = self.conflict_case()
        ctx = "c"
        eng = R.engine_from(gb, ch, ctx)
        view = eng.view("current", 13)
        led = R.new_ledger(ctx)
        return gb, fb, eng, view, led, ctx

    def test_stale_other_context_unregistered_and_unrequested_receipts_refused(self):
        gb, fb, eng, view, led, ctx = self._setup()
        _, recs = R.sensor_query(gb, led, ctx, [fb], 12)
        led["receipts"].append(dict(recs[0], receipt_id="o", context="other"))
        led["receipts"].append(dict(recs[0], receipt_id="u", sensor_id="report-says-sensor"))
        other = next(f for f in view["detail"] if f != fb)
        led["receipts"].append(dict(recs[0], receipt_id="n", field=other))
        p = R.project(eng, view, led, 13, ctx)
        self.assertEqual(list(p["anchors"]), [fb])
        reasons = {r["receipt_id"]: r["reason"] for r in p["refused"]}
        self.assertEqual(reasons, {"o": "other_context", "u": "unregistered_sensor", "n": "unrequested_field"})
        # stale: later evidence about the field than the measurement
        eng.ingest(state_rep("late", 13, "verified", [{"field": fb, "at": 13, "value": recs[0]["value"]}]))
        p2 = R.project(eng, eng.view("current", 13), led, 13, ctx)
        self.assertNotIn(fb, p2["anchors"])
        self.assertTrue(any(r["reason"].startswith("stale") for r in p2["refused"]))

    def test_before_stability_and_contradictory_equal_time_receipts(self):
        gb, fb, eng, view, led, ctx = self._setup()
        _, recs = R.sensor_query(gb, led, ctx, [fb], 12)
        alt = next(p for p in gb["spec"]["places"] if p != recs[0]["value"])
        led["receipts"].append(dict(recs[0], receipt_id="x", value=alt))
        p = R.project(eng, view, led, 13, ctx)
        self.assertEqual(p["anchors"], {})
        self.assertEqual(p["authority_conflicts"][0]["field"], fb)
        led2 = R.new_ledger(ctx)
        R.sensor_query(gb, led2, ctx, [fb], 11)
        p2 = R.project(eng, view, led2, 13, ctx)
        self.assertEqual(p2["anchors"], {})
        self.assertEqual(p2["refused"][0]["reason"], "outside_stable_interval")

    def test_inadmissible_receipt_and_text_claiming_sensor(self):
        gb, fb, eng, view, led, ctx = self._setup()
        _, recs = R.sensor_query(gb, led, ctx, [fb], 12)
        led["receipts"][0] = dict(recs[0], value=CARRIED)
        p = R.project(eng, view, led, 13, ctx)
        self.assertEqual(p["refused"][0]["reason"], "inadmissible_value")
        fake = dict(state_rep("f1", 13, "verified", [{"field": fb, "at": 12, "value": recs[0]["value"]}]), source="sensor")
        eng.ingest(fake)  # extracted text that calls itself a sensor: no ledger receipt, so no authority
        p2 = R.project(eng, eng.view("current", 13), R.new_ledger(ctx), 13, ctx)
        self.assertEqual(p2["anchors"], {})

    def test_incomplete_field_anchored_only_in_projection(self):
        ep = next(e for e in self.eps if e["domain"] == "assembly")
        ge, gc = self.ctx(ep, "B")
        fd = next(f for f in gc["relevant"] if f.endswith(".on_hand"))
        ks = [i for i, r in enumerate(ep["records_v02"], 1) if r["kind"] != "initial" and r["payload"]["field"] == fd]
        ch = self.channel(ep, {f"{ep['episode_id']}|prose|r{k}": "garbled" for k in ks})
        x = R.run(ge, gc, "P2_selective", channel=ch)
        self.assertIn(fd, x["strict"]["queried"])
        self.assertIn(fd, x["strict"]["incomplete_at_decision"])
        self.assertNotIn(fd, x["scoped"]["incomplete_at_decision"])
        self.assertTrue(x["scoped"]["anchors"][fd]["incomplete_without_rule"])
        self.assertFalse(x["scoped"]["invalid_attempt"])


class Pipeline(Base):
    @unittest.skipUnless((RUNS / "temporal-contract-policy-20261105-121257").is_dir(), "saved run hub not present; set DREAM_RUNS to the run archive")
    def test_validation_passes(self):
        run("scripts/deprec_validate.py", "--hub", self.hub, "--set", "deprec", "--samples", "20")
        res = json.loads((self.hub / "phase0" / "VALIDATION.json").read_text())
        self.assertEqual(res["failures"], [])

    def test_fake_pipeline_end_to_end(self):
        rep = {c["call_id"]: json.dumps(self.gold[c["call_id"]]["gold"]) for c in self.calls}
        (self.hub / "r.json").write_text(json.dumps(rep))
        cfg = self.hub / "cfg.json"
        cfg.write_text(json.dumps({"set": "deprec", "select": "all", "order_seed": 1, "max_seconds": 600, "max_calls": 999,
                                   "max_input_tokens": 8192, "retry_limit": 1, "model": {}}))
        run("scripts/tempo_run.py", "--hub", self.hub, "--stage", "s", "--config", cfg, "--fake", self.hub / "r.json")
        run("scripts/deprec_analyze.py", "--hub", self.hub, "--set", "deprec", "--stage", "s", "--boot", "200")
        res = json.loads((self.hub / "analysis-deprec" / "ANALYSIS.json").read_text())
        self.assertEqual(res["trajectories"], 192)
        self.assertEqual(res["extraction"]["denotation_equal"], 144)
        self.assertEqual(res["matching"]["identical_queries_and_receipts"], 96)
        self.assertEqual(res["scoped_vs_strict_differences"], [])
        self.assertEqual(res["primary"]["mean"], 0.0)


if __name__ == "__main__":
    unittest.main()
