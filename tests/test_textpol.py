"""No-model tests for the text-interface policy study."""
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
from dream_core import localpaths as LP  # public release: local paths from environment
RUNS = Path(os.environ.get("DREAM_RUNS", f"{LP.RUNS}"))

from tempo import policy as P, prose_study as PS, text_channel as TC  # noqa: E402

PY = sys.executable


def load(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]


def run(*args):
    r = subprocess.run([PY, "-B", *map(str, args)], cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        raise AssertionError(r.stdout + r.stderr)
    return r.stdout


def perfect(g):
    return json.dumps(g["gold"])


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.hub = Path(cls.tmp.name)
        run("scripts/textpol_generate.py", "--hub", cls.hub, "--set", "textpol")
        d = cls.hub / "data"
        cls.eps = load(d / "textpol-episodes.jsonl")
        cls.calls = load(d / "textpol-calls.jsonl")
        cls.gold = {g["call_id"]: g for g in load(d / "textpol-gold.jsonl")}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def channel(self, ep, replace=None):
        cids = [f"{ep['episode_id']}|prose|r{k}" for k in range(1, 7)]
        raws = [(replace or {}).get(c, perfect(self.gold[c])) for c in cids]
        return TC.build_channel(ep, raws, [self.gold[c]["registry"] for c in cids], ep["prose_texts"])


class Frozen(Base):
    @unittest.skipUnless((RUNS / "temporal-repair-prose-20261105-111843").is_dir(), "saved run hub not present; set DREAM_RUNS to the run archive")
    def test_extraction_prompt_identical_to_the_scored_1_8_2_channel(self):
        import hist_generate as HG
        built = HG.build("prose", 20261110, False)[0]
        committed = {c["call_id"]: c["user"] for c in
                     load(RUNS / "temporal-repair-prose-20261105-111843" / "data" / "prose-calls.jsonl")}
        n = 0
        for w, h in built:
            for k in range(1, 7):
                self.assertEqual(PS.extraction_prompt(w, h, "prose", k), committed[f"{h['history_id']}|prose|r{k}"])
                n += 1
        self.assertEqual(n, 144)

    def test_matrix(self):
        self.assertEqual(len(self.eps), 24)
        self.assertEqual(len(self.calls), 144)
        for e in self.eps:
            for r, t in zip(e["records_v02"], e["prose_texts"]):
                PS.check_equivalent(r, t)
            for tok in ("truth", "accepted_relevant", "_src", "hidden"):
                for c in self.calls:
                    self.assertNotIn(tok, c["user"])


class Adapter(unittest.TestCase):
    REG = {"A.location": ["P", "Q", "carried by you"]}

    def test_declared_mappings_only(self):
        unc = {"rid": "r02", "kind": "uncertain_change", "status": "verified", "event_at": 3, "received_at": 3,
               "payload": {"field": "A.location", "options": ["P", "Q"]}}
        rep, log = TC.adapt(json.dumps(unc), self.REG)
        self.assertEqual(rep["type"], "event"); self.assertNotIn("from", rep["assertions"][0])  # M1
        cor = {"rid": "r03", "kind": "correction", "status": "verified", "event_at": 5, "received_at": 6,
               "payload": {"target": "r01", "field": "A.location", "value": "Q", "valid_from": 0, "valid_to": None}}
        self.assertIsNone(TC.adapt(json.dumps(cor), self.REG)[0])  # M2: conflicting time fields
        cor["event_at"] = 0
        rep, log = TC.adapt(json.dumps(cor), self.REG)
        self.assertEqual(rep["type"], "correction"); self.assertIn("N3", [n["rule"] for n in log["norm"]])
        self.assertIsNone(TC.adapt("prose, not json", self.REG)[0])
        self.assertIsNone(TC.adapt(json.dumps({"kind": "teleport", "payload": {}}), self.REG)[0])
        obs = {"rid": "r04", "kind": "observation", "status": "verified", "event_at": None, "received_at": 6,
               "payload": {"field": "A.location", "value": "crate q"}}
        rep, log = TC.adapt(json.dumps(obs), self.REG)
        self.assertEqual(rep["assertions"][0]["value"], "Q")  # N1 only
        self.assertIsNone(rep["assertions"][0]["at"])  # missing time is not invented (engine will reject it)


class Pipeline(Base):
    def test_perfect_extraction_reproduces_structured_channel(self):
        for ep in self.eps:
            ch = self.channel(ep)
            self.assertTrue(all(r["accepted"] for r in ch["rows"]))
            for pol in P.POLICIES:
                s, t = P.run_policy(ep, pol), P.run_policy(ep, pol, channel=ch)
                for k in ("plan", "success", "invalid_attempt", "queried", "utility", "belief_correct_before"):
                    self.assertEqual(s[k], t[k], (ep["episode_id"], pol, k))

    def test_wrong_verified_extraction_stays_in_conflict_after_sensor(self):
        ep = next(e for e in self.eps if e["type"] == "verified_settled" and e["domain"] == "delivery")
        k = next(i for i, r in enumerate(ep["records_v02"], 1) if r["kind"] == "change"
                 and r["payload"]["field"] == ep["relevant"][0])
        cid = f"{ep['episode_id']}|prose|r{k}"
        bad = copy.deepcopy(self.gold[cid]["gold"])
        bad["payload"]["to"] = next(v for v in self.gold[cid]["registry"][bad["payload"]["field"]]
                                    if v not in (bad["payload"]["to"], bad["payload"]["from"]))
        ch = self.channel(ep, {cid: json.dumps(bad)})
        r1 = P.run_policy(ep, "P1_always", channel=ch)
        self.assertEqual(r1["conflict_at_decision"], ep["relevant"])  # not silently overridden by the sensor
        self.assertIsNone(r1["plan"])
        self.assertFalse(r1["invalid_attempt"])
        r0 = P.run_policy(ep, "P0_accepted", channel=ch)
        self.assertNotEqual(r0["belief_correct_before"], P.run_policy(ep, "P0_accepted")["belief_correct_before"])
        r2 = P.run_policy(ep, "P2_selective", channel=ch)
        self.assertEqual(r2["queried"], [])  # the wrong verified claim looks settled: selective trigger cannot see it

    def test_unparsed_report_leaves_field_incomplete(self):
        ep = next(e for e in self.eps if e["type"] == "false_permission")
        cid = f"{ep['episode_id']}|prose|r1"
        ch = self.channel(ep, {cid: "garbled"})
        self.assertFalse(ch["rows"][0]["accepted"])
        r = P.run_policy(ep, "P2_selective", channel=ch)
        self.assertTrue(set(ep["relevant"]) <= set(r["incomplete_at_decision"]) | set(r["queried"]))
        self.assertTrue(r["earlier_view_preserved"])

    def test_fake_pipeline_end_to_end(self):
        rep = {c["call_id"]: perfect(self.gold[c["call_id"]]) for c in self.calls}
        (self.hub / "r.json").write_text(json.dumps(rep))
        cfg = self.hub / "cfg.json"
        cfg.write_text(json.dumps({"set": "textpol", "select": "all", "order_seed": 1, "max_seconds": 600,
                                   "max_calls": 999, "max_input_tokens": 8192, "retry_limit": 1, "model": {}}))
        run("scripts/tempo_run.py", "--hub", self.hub, "--stage", "s", "--config", cfg, "--fake", self.hub / "r.json")
        run("scripts/textpol_analyze.py", "--hub", self.hub, "--set", "textpol", "--stage", "s", "--boot", "200")
        res = json.loads((self.hub / "analysis-textpol" / "ANALYSIS.json").read_text())
        self.assertEqual(res["text_vs_structured_differences"]["trajectories_differing"], 0)
        self.assertEqual(res["extraction"]["denotation_equal"], 144)
        for pol in P.POLICIES:
            self.assertEqual(res["cells"][f"text:{pol}"]["utility_total"], res["cells"][f"structured:{pol}"]["utility_total"])


if __name__ == "__main__":
    unittest.main()
