"""No-model tests for the deferred-goal transfer study (V1.10.0)."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import os  # noqa: E402
from dream_core import localpaths as LP  # noqa: E402  public release: local paths from environment
RUNS = Path(os.environ.get("DREAM_RUNS", LP.RUNS))
from tempo import goals as GL, policy as P, text_channel as TC, transfer as T  # noqa: E402

PY = sys.executable


def load(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]


def run(*args, check=True):
    r = subprocess.run([PY, "-B", *map(str, args)], cwd=ROOT, capture_output=True, text=True)
    if check and r.returncode:
        raise AssertionError(r.stdout[-3000:] + r.stderr[-3000:])
    return r


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.hub = Path(cls.tmp.name)
        run("scripts/goaltr_generate.py", "--hub", cls.hub, "--set", "goaltr")
        d = cls.hub / "data"
        cls.eps = load(d / "goaltr-episodes.jsonl")
        cls.calls = load(d / "goaltr-calls.jsonl")
        cls.gold = {g["call_id"]: g for g in load(d / "goaltr-gold.jsonl")}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def channel(self, ep, replace=None):
        cids = [f"{ep['episode_id']}|prose|r{k}" for k in range(1, 7)]
        raws = [(replace or {}).get(c, json.dumps(self.gold[c]["gold"])) for c in cids]
        return TC.build_channel(ep, raws, [self.gold[c]["registry"] for c in cids], ep["prose_texts"])


class Design(Base):
    def test_matrix_and_allocation(self):
        self.assertEqual(len(self.eps), 24)
        self.assertEqual(len(self.calls), 144)
        for dom in ("delivery", "assembly"):
            e = [x for x in self.eps if x["domain"] == dom]
            self.assertEqual(len(e), 12)
            self.assertEqual(sorted(x["b_type"] for x in e), sorted(t for t in T.B_TYPES for _ in range(T.B_ALLOC[t])))
            self.assertEqual(sorted(x["a_type"] for x in e), sorted(t for t in P.TYPES for _ in range(P.ALLOC[t])))
        self.assertEqual(sum(x["a_item_is_x"] for x in self.eps if x["domain"] == "delivery"), 6)

    def test_generation_is_deterministic(self):
        with tempfile.TemporaryDirectory() as h2:
            run("scripts/goaltr_generate.py", "--hub", h2, "--set", "goaltr")
            a = json.loads((self.hub / "data" / "COMMITMENT-goaltr.json").read_text())
            b = json.loads((Path(h2) / "data" / "COMMITMENT-goaltr.json").read_text())
            for k in ("episodes_sha256", "calls_sha256", "gold_sha256"):
                self.assertEqual(a[k], b[k])

    def test_no_goal_or_role_label_reaches_the_extractor(self):
        for c in self.calls:
            for tok in ("Goal", "goal", "focal", "padding", "b_changed", "relevant", "truth", "_src"):
                self.assertNotIn(tok, c["user"])

    def test_relevance_is_disjoint_and_follows_the_goal(self):
        for ep in self.eps:
            ra, rb = T.goal_context(ep, "A")["relevant"], T.goal_context(ep, "B")["relevant"]
            self.assertFalse(set(ra) & set(rb))
            if ep["domain"] == "delivery":
                self.assertEqual(ra, [f"{ep['goals']['A']['item']}.location"])
                self.assertEqual(rb, [f"{ep['goals']['B']['item']}.location"])
            else:
                self.assertEqual(set(rb), {f"{ep['world']['s2']}.part", f"{ep['world']['d']}.on_hand"})

    @unittest.skipUnless((RUNS / "temporal-contract-policy-20261105-121257").is_dir(), "saved run hub not present; set DREAM_RUNS to the run archive")
    def test_validation_passes(self):
        r = run("scripts/goaltr_validate.py", "--hub", self.hub, "--set", "goaltr", "--samples", "40")
        res = json.loads((self.hub / "phase0" / "VALIDATION.json").read_text())
        self.assertEqual(res["failures"], [])
        self.assertEqual(res["7_parity"]["trajectories_identical"], 216)


class Loop(Base):
    def test_perfect_extraction_reproduces_structured_for_both_goals(self):
        for ep in self.eps:
            ch = self.channel(ep)
            for role in ("A", "B"):
                ge, gc = T.goal_episode(ep, role)
                for pol in P.POLICIES:
                    s, t = GL.run_policy(ge, gc, pol), GL.run_policy(ge, gc, pol, channel=ch)
                    for k in ("plan", "success", "invalid_attempt", "queried", "utility", "belief_correct_before"):
                        self.assertEqual(s[k], t[k], (ep["episode_id"], role, pol, k))

    def test_goal_clones_are_isolated(self):
        ep = self.eps[0]
        ch = self.channel(ep)
        before = json.dumps(ch, sort_keys=True, default=str)
        ge, gc = T.goal_episode(ep, "B")
        alone = GL.run_policy(ge, gc, "P1_always", channel=ch)
        ga, gca = T.goal_episode(ep, "A")
        GL.run_policy(ga, gca, "P1_always", channel=ch)
        self.assertEqual(GL.run_policy(ge, gc, "P1_always", channel=ch), alone)
        self.assertEqual(json.dumps(ch, sort_keys=True, default=str), before)

    def test_error_on_a_B_fact_matters_only_under_B(self):
        ep = next(e for e in self.eps if e["domain"] == "delivery" and e["b_type"] == "b_changed")
        fb = T.goal_context(ep, "B")["relevant"][0]
        k = max(i for i, r in enumerate(ep["records_v02"], 1) if r["kind"] == "change" and r["payload"]["field"] == fb)
        cid = f"{ep['episode_id']}|prose|r{k}"
        bad = copy.deepcopy(self.gold[cid]["gold"])
        bad["kind"], bad["payload"] = "observation", {"field": fb, "value": bad["payload"]["to"]}  # event read as a state
        ch = self.channel(ep, {cid: json.dumps(bad)})
        ga, gca = T.goal_episode(ep, "A")
        s, t = GL.run_policy(ga, gca, "P0_accepted"), GL.run_policy(ga, gca, "P0_accepted", channel=ch)
        self.assertEqual((s["plan"], s["utility"]), (t["plan"], t["utility"]))  # irrelevant under A
        ge, gc = T.goal_episode(ep, "B")
        t = GL.run_policy(ge, gc, "P0_accepted", channel=ch)
        self.assertEqual(t["conflict_at_decision"], [fb])  # verified-verified conflict under B (kept, not repaired)
        self.assertIsNone(t["plan"])
        t2 = GL.run_policy(ge, gc, "P2_selective", channel=ch)
        self.assertEqual(t2["queried"], [fb])
        self.assertTrue(t2["earlier_view_preserved"])

    def test_already_holding_goal_takes_the_empty_plan(self):
        hits = 0
        for ep in self.eps:
            for role in ("A", "B"):
                ge, gc = T.goal_episode(ep, role)
                if "already" in GL.true_valid_plans(ge, gc):
                    r = GL.run_policy(ge, gc, "P0_accepted")
                    if r["plan"] == "already":
                        self.assertEqual((r["success"], r["action_cost"], r["utility"]), (True, 0, 10))
                        hits += 1
        self.assertGreater(hits, 0)

    def test_relevant_field_never_described_by_text_does_not_raise(self):  # amendment S1
        ep = next(e for e in self.eps if e["domain"] == "assembly")
        fd = f"{ep['world']['d']}.on_hand"
        ks = [i for i, r in enumerate(ep["records_v02"], 1) if r["kind"] != "initial" and r["payload"]["field"] == fd]
        ch = self.channel(ep, {f"{ep['episode_id']}|prose|r{k}": "garbled" for k in ks})
        ge, gc = T.goal_episode(ep, "B")
        for pol in P.POLICIES:
            r = GL.run_policy(ge, gc, pol, channel=ch)
            self.assertIn(fd, r["incomplete_at_decision"])
            self.assertFalse(r["invalid_attempt"])

    def test_fake_pipeline_end_to_end(self):
        rep = {c["call_id"]: json.dumps(self.gold[c["call_id"]]["gold"]) for c in self.calls}
        (self.hub / "r.json").write_text(json.dumps(rep))
        cfg = self.hub / "cfg.json"
        cfg.write_text(json.dumps({"set": "goaltr", "select": "all", "order_seed": 1, "max_seconds": 600, "max_calls": 999,
                                   "max_input_tokens": 8192, "retry_limit": 1, "model": {}}))
        run("scripts/tempo_run.py", "--hub", self.hub, "--stage", "s", "--config", cfg, "--fake", self.hub / "r.json")
        run("scripts/goaltr_analyze.py", "--hub", self.hub, "--set", "goaltr", "--stage", "s", "--boot", "200")
        res = json.loads((self.hub / "analysis-goaltr" / "ANALYSIS.json").read_text())
        self.assertEqual(res["trajectories"], 288)
        self.assertEqual(res["extraction"]["denotation_equal"], 144)
        self.assertEqual(sum(v["trajectories"] for v in res["text_vs_structured_differences"]["by_goal"].values()), 0)
        self.assertEqual(res["primary"]["mean"], 0.0)


if __name__ == "__main__":
    unittest.main()
