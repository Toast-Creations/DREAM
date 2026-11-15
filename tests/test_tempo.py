"""Temporal pilot (V1.7.0) tests. Expected values in the fixtures were worked out by hand from the printed rules,
not produced by the implementation. No model is loaded (the pipeline test uses tempo_run.py's fake model)."""
import copy
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tempo import enumcheck, generate as G, render, resolve, score  # noqa: E402


def rec(rid, kind, e, r, payload, status="verified"):
    n = int(rid[1:])
    return {"rid": rid, "kind": kind, "status": status, "event_at": e, "received_at": r, "ordinal": n,
            "payload": payload, "key": None, "_src": "base"}


def both(records, field, t):
    a, b = resolve.value_at(records, field, t), enumcheck.supported(records, field, t)
    return a, b


X = "X.location"
Y = "Y.location"


class ResolverFixtures(unittest.TestCase):
    def check(self, records, field, t, expected):
        a, b = both(records, field, t)
        self.assertEqual(a, expected, "resolver 1")
        self.assertEqual(b, expected, "resolver 2")

    def test_correction_changes_past_but_not_supported_then(self):
        rs = [rec("r01", "initial", 0, 0, {"assign": {X: "A"}}, "provisional"),
              rec("r02", "correction", None, 5, {"target": "r01", "field": X, "value": "B", "valid_from": 0,
                                                  "valid_to": None})]
        self.check(rs, X, 12, ("value", "B"))
        self.check(rs, X, 3, ("value", "B"))                       # P0: today's evidence about time 3
        self.check(resolve.prefix(rs, 3), X, 3, ("value", "A"))    # K0: supported then

    def test_real_move_same_present_different_past(self):
        rs = [rec("r01", "initial", 0, 0, {"assign": {X: "A"}}),
              rec("r02", "change", 5, 5, {"field": X, "from": "A", "to": "B"})]
        self.check(rs, X, 12, ("value", "B"))
        self.check(rs, X, 3, ("value", "A"))

    def test_delayed_old_observation_does_not_override(self):
        rs = [rec("r01", "initial", 0, 0, {"assign": {X: "A"}}),
              rec("r02", "change", 5, 5, {"field": X, "from": "A", "to": "B"}),
              rec("r03", "observation", 2, 8, {"field": X, "value": "A"})]
        self.check(rs, X, 12, ("value", "B"))
        self.check(rs, X, 3, ("value", "A"))

    def test_return_to_earlier_state(self):
        rs = [rec("r01", "initial", 0, 0, {"assign": {X: "A"}}),
              rec("r02", "change", 3, 3, {"field": X, "from": "A", "to": "B"}),
              rec("r03", "change", 6, 6, {"field": X, "from": "B", "to": "A"})]
        self.check(rs, X, 12, ("value", "A"))
        self.check(rs, X, 4, ("value", "B"))

    def test_uncertain_change_and_retroactive_resolution(self):
        base = [rec("r01", "initial", 0, 0, {"assign": {X: "C"}}),
                rec("r02", "uncertain_change", 3, 3, {"field": X, "from": "C", "options": ["A", "B"]})]
        self.check(base, X, 12, ("unknown", ["A", "B"]))
        rs = base + [rec("r03", "observation", 6, 6, {"field": X, "value": "B"})]
        self.check(rs, X, 12, ("value", "B"))
        self.check(rs, X, 4, ("value", "B"))                    # settled back to the event
        self.check(resolve.prefix(rs, 5), X, 4, ("unknown", ["A", "B"]))
        self.check(rs, X, 2, ("value", "C"))

    def test_scoped_correction_leaves_other_field(self):
        rs = [rec("r01", "initial", 0, 0, {"assign": {X: "A", Y: "D"}}, "provisional"),
              rec("r02", "correction", None, 6, {"target": "r01", "field": Y, "value": "E", "valid_from": 0,
                                                  "valid_to": None})]
        self.check(rs, X, 12, ("value", "A"))
        self.check(rs, Y, 12, ("value", "E"))
        self.check(resolve.prefix(rs, 4), Y, 3, ("value", "D"))

    def test_inconsistent_history_is_rejected_by_resolver_2(self):
        rs = [rec("r01", "initial", 0, 0, {"assign": {X: "A"}}),
              rec("r02", "change", 4, 4, {"field": X, "from": "B", "to": "C"})]
        with self.assertRaises(enumcheck.Inconsistent):
            enumcheck.supported(rs, X, 12)

    def test_contradicting_verified_observation_is_rejected(self):
        rs = [rec("r01", "initial", 0, 0, {"assign": {X: "A"}}),
              rec("r02", "observation", 4, 4, {"field": X, "value": "B"})]
        with self.assertRaises(enumcheck.Inconsistent):
            enumcheck.supported(rs, X, 12)

    def test_same_time_assertions_are_rejected(self):
        rs = [rec("r01", "initial", 0, 0, {"assign": {X: "A"}}),
              rec("r02", "change", 4, 4, {"field": X, "from": "A", "to": "B"}),
              rec("r03", "observation", 4, 6, {"field": X, "value": "B"})]
        with self.assertRaises(AssertionError):
            G.check_no_ties(rs)

    def test_correction_of_missing_report_rejected(self):
        rs = [rec("r01", "initial", 0, 0, {"assign": {X: "A"}}, "provisional"),
              rec("r02", "correction", None, 5, {"target": "r09", "field": X, "value": "B", "valid_from": 0,
                                                  "valid_to": None})]
        with self.assertRaises(enumcheck.Inconsistent):
            enumcheck.supported(rs, X, 12)


class ParserTests(unittest.TestCase):
    def test_decisions(self):
        g = {"acceptable": ["B"], "lure_option": "A", "pair_other_option": "A", "obs_option": "D"}
        ids = ["A", "B", "C", "D"]
        self.assertTrue(score.score_decision('{"choice": "B"}', ids, g)["correct"])
        self.assertTrue(score.score_decision('```json\n{"choice": "b"}\n```', ids, g)["correct"])
        self.assertFalse(score.score_decision('I think {"choice": "B"}', ids, g)["valid"])
        self.assertFalse(score.score_decision('{"choice": "B"} because', ids, g)["valid"])
        self.assertFalse(score.score_decision('{"choice": "B", "choice": "A"}', ids, g)["valid"])
        self.assertFalse(score.score_decision('{"choice": "E"}', ids, g)["valid"])
        self.assertFalse(score.score_decision('{"choice": "B"', ids, g)["valid"])   # truncated
        self.assertTrue(score.score_decision('{"choice": "A"}', ids, g)["lure"])

    def test_facts(self):
        allowed = {"X.location": ["Kemi", "Bado", "carried by you", "unknown"], "P.on_hand": ["yes", "no", "unknown"]}
        gold = {"X.location": "Bado", "P.on_hand": "unknown"}
        r = score.score_facts('{"facts": {"X.location": "place bado.", "P.on_hand": "Unknown"}}', allowed, gold)
        self.assertTrue(r["exact"] and r["valid"])
        r = score.score_facts('{"facts": {"X.location": "Bado"}}', allowed, gold)
        self.assertFalse(r["exact"]); self.assertFalse(r["valid"])
        r = score.score_facts('{"facts": {"X.location": "Bado", "P.on_hand": false, "Z": 1}}', allowed,
                              {"X.location": "Bado", "P.on_hand": "no"})
        self.assertTrue(r["exact"]); self.assertEqual(r["extra_fields"], ["Z"])
        self.assertFalse(score.score_facts("not json", allowed, gold)["valid"])

    def test_action(self):
        allowed = {"X.location": ["A", "carried by you", "unknown"]}
        gold = {"applicable": True, "predicted": {"X.location": "carried by you"}, "observed": {"X.location": "A"}}
        t = '{"applicable": true, "predicted_next_facts": {"X.location": "carried by you"}, "observed_world_facts": {"X.location": "A"}}'
        r = score.score_action(t, allowed, gold)
        self.assertTrue(r["valid"] and r["applicable_correct"])
        r = score.score_action(t.replace('"A"}', '"carried by you"}'), allowed, gold)
        self.assertFalse(r["observed"]["X.location"]["correct"])   # branch conflated with the observed world


class GeneratedSetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        hub = Path(cls.tmp.name)
        for s in ("main", "smoke"):
            subprocess.run([sys.executable, "-B", str(ROOT / "scripts" / "tempo_generate.py"), "--hub", str(hub),
                            "--set", s], check=True, capture_output=True)
        load = lambda p: [json.loads(l) for l in (hub / "data" / p).read_text().splitlines()]
        cls.hub = hub
        cls.calls, cls.gold, cls.groups = load("main-calls.jsonl"), load("main-gold.jsonl"), load("main-groups.jsonl")
        cls.smoke_calls, cls.smoke_groups = load("smoke-calls.jsonl"), load("smoke-groups.jsonl")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_matrix(self):
        self.assertEqual(len(self.groups), 24)
        self.assertEqual(sum(g["domain"] == "delivery" for g in self.groups), 12)
        self.assertEqual(len(self.calls), 792)
        self.assertEqual(sum(c["arm"] == "C0" for c in self.calls), 288)
        self.assertEqual(sum(c["arm"] == "C1" for c in self.calls), 504)
        self.assertEqual(len(self.smoke_calls), 52)
        self.assertEqual(len({c["call_id"] for c in self.calls}), 792)

    def test_smoke_names_disjoint_from_main(self):
        def names(groups):
            out = set()
            for g in groups:
                for v in g["world"].values():
                    if isinstance(v, str) and re.fullmatch(r"[A-Z][a-z]{3}", v):
                        out.add(v)
                for L in g["variants"].values():
                    for r in L["a"]["records"]:
                        out.add(r["payload"].get("field", "").split(".")[0])
            return out - {""}
        m, s = names(self.groups), names(self.smoke_groups)
        self.assertGreater(len(m), 100)
        self.assertEqual(m & s, set())

    def test_lengths_and_prefix_isolation(self):
        for c in self.calls:
            if c["arm"] != "C1":
                self.assertNotIn("Records received", c["user"])
                continue
            times = [int(t) for t in re.findall(r"\| received at time (\d+) \|", c["user"])]
            self.assertEqual(len(times), c["n_records"])
            self.assertTrue(all(t <= c["evidence_cutoff"] for t in times))
            self.assertEqual(times, sorted(times))
            if c["qtype"] == "K0":
                self.assertNotIn("verified correction", c["user"].split("Records received")[1]
                                 if c["pattern"] in (3, 5) else "")
            elif c["qtype"] != "I1":
                self.assertEqual(c["n_records"], G.LENGTHS[c["length"]])
            else:
                self.assertEqual(c["n_records"], G.LENGTHS[c["length"]] + 1)

    def test_no_scorer_fields_in_prompts(self):
        for c in self.calls:
            for bad in ("_src", "lure", "key_plan", "intended", "hidden", "ordinal", "acceptable"):
                self.assertNotIn(bad, c["user"])

    def test_pair_and_invariance_keys(self):
        gold = {g["call_id"]: g for g in self.gold}
        for c in self.calls:
            if c["qtype"] == "D0":
                d1 = gold[c["call_id"].replace("|D0", "|D1")]
                i1 = gold[c["call_id"].replace("|D0", "|I1")]
                g0 = gold[c["call_id"]]
                self.assertNotEqual(g0["acceptable"], d1["acceptable"])
                self.assertEqual(g0["acceptable"], i1["acceptable"])

    def test_c0_and_c1_share_options_and_wording(self):
        by = {c["call_id"]: c for c in self.calls}
        for c in self.calls:
            if c["arm"] == "C0":
                twin = by[c["call_id"].replace("|C0|", "|C1|")]
                self.assertEqual(c["user"].split("QUERY")[1], twin["user"].split("QUERY")[1])
                self.assertEqual(c["system"], twin["system"])

    def test_c0_state_order_same_on_both_sides(self):
        by = {c["call_id"]: c for c in self.calls}
        for c in self.calls:
            if c["arm"] == "C0" and c["qtype"] == "D0":
                other = by[c["call_id"].replace("|D0", "|D1")]
                subj = lambda u: [re.sub(r"(rests at|holds part|is|:).*", "", ln).strip() for ln in
                                  u.split("Current state")[1].split("QUERY")[0].splitlines() if ln.startswith("- ")]
                self.assertEqual(subj(c["user"]), subj(other["user"]), c["call_id"])

    def test_uncertain_c0_does_not_reveal_hidden_value(self):
        for g in self.groups:
            if g["pattern"] != 6:
                continue
            for c in self.calls:
                if c["group_id"] == g["group_id"] and c["arm"] == "C0" and c["variant"] == "a":
                    self.assertIn("not known", c["user"])

    def test_every_pattern_has_its_temporal_contrast(self):
        for g in self.groups:
            v = g["variants"]["short"]
            if g["pattern"] in (3, 5) and g["focal_field"] in v["P0"]:
                f = g["focal_field"] if g["pattern"] == 3 else g["focal_field"]
                self.assertNotEqual(v["P0"][f], v["K0"][f], g["group_id"])   # correction changes the past
            if g["pattern"] == 4:
                self.assertNotEqual(v["P0"][g["focal_field"]], v["S0"][g["focal_field"]])
            if g["pattern"] == 6:
                self.assertEqual(v["S0"][g["focal_field"]], "unknown")
                self.assertEqual(v["a"]["key"], "OBS")

    def test_generation_is_deterministic_and_branch_safe(self):
        spec = G.group_specs("main", 20261105)[0]
        w1, g1 = G.build_group(spec[0], spec[1], spec[2], spec[3], "main", spec[4])
        w2, g2 = G.build_group(spec[0], spec[1], spec[2], spec[3], "main", spec[4])
        self.assertEqual(json.dumps(g1["variants"], sort_keys=True), json.dumps(g2["variants"], sort_keys=True))
        recs = g1["variants"]["short"]["a"]["records"]
        before = copy.deepcopy(recs)
        G.a0_gold(w1, recs); G.decide(w1, recs)
        self.assertEqual(recs, before)   # considering an action never mutates the observed history


class PipelineTests(unittest.TestCase):
    """Generate smoke, run the fake model with gold answers (expect perfect scores), then check lock/resume rules."""
    def test_pipeline(self):
        with tempfile.TemporaryDirectory() as d:
            hub = Path(d)
            py = [sys.executable, "-B"]
            subprocess.run(py + [str(ROOT / "scripts/tempo_generate.py"), "--hub", d, "--set", "smoke"], check=True,
                           capture_output=True)
            gold = [json.loads(l) for l in (hub / "data/smoke-gold.jsonl").read_text().splitlines()]
            replies = {}
            for g in gold:
                if g["type"] == "decision":
                    replies[g["call_id"]] = json.dumps({"choice": g["acceptable"][0]})
                elif g["type"] == "facts":
                    replies[g["call_id"]] = json.dumps({"facts": g["gold"]})
                else:
                    replies[g["call_id"]] = json.dumps({"applicable": g["applicable"],
                                                        "predicted_next_facts": g["predicted"],
                                                        "observed_world_facts": g["observed"]})
            first = gold[0]["call_id"]
            replies["_fail_once"] = [first]
            (hub / "fake.json").write_text(json.dumps(replies))
            cfg = {"set": "smoke", "select": "all", "order_seed": 1, "max_seconds": 3600, "max_calls": 10,
                   "max_input_tokens": 8192, "retry_limit": 1, "model": {}}
            (hub / "cfg.json").write_text(json.dumps(cfg))
            run = lambda c="cfg.json": subprocess.run(py + [str(ROOT / "scripts/tempo_run.py"), "--hub", d, "--stage",
                                                            "t", "--config", str(hub / c), "--fake",
                                                            str(hub / "fake.json")], capture_output=True, text=True)
            r = run()
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue((hub / "stages/t/STOP.json").exists())          # budget stop after 10 calls
            self.assertEqual(len(list((hub / "stages/t/calls").glob("*.json"))), 10)
            cfg2 = dict(cfg, max_calls=1000)
            (hub / "cfg2.json").write_text(json.dumps(cfg2))
            r = run("cfg2.json")
            self.assertNotEqual(r.returncode, 0)                            # changed config hash refused
            self.assertIn("locked", r.stderr)
            # resume under the original config is allowed; a budget is the config's, so raise it via a new stage
            (hub / "stages/t2").mkdir(parents=True)
            r = subprocess.run(py + [str(ROOT / "scripts/tempo_run.py"), "--hub", d, "--stage", "t2", "--config",
                                     str(hub / "cfg2.json"), "--fake", str(hub / "fake.json")],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue((hub / "stages/t2/END.json").exists())
            attempts = (hub / "stages/t2/attempts.jsonl").read_text().splitlines()
            self.assertEqual(len(attempts), 1)                              # infra failure retried once
            r = run()                                                       # resume t: skips 10 done, does 10 more
            self.assertEqual(len(list((hub / "stages/t/calls").glob("*.json"))), 20)
            # corrupted record detection
            p = next((hub / "stages/t/calls").glob("*.json"))
            p.write_text("{broken")
            r = run()
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("corrupted", r.stderr)
            r = subprocess.run(py + [str(ROOT / "scripts/tempo_analyze.py"), "--hub", d, "--stage", "t2", "--set",
                                     "smoke", "--boot", "200"], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            a = json.loads((hub / "stages/t2/analysis/ANALYSIS.json").read_text())
            for arm in ("C0", "C1"):
                self.assertEqual(a[arm]["complete_pair"]["mean"], 1.0)
                self.assertEqual(a[arm]["A0_a0_all"]["mean"], 1.0)
                self.assertEqual(a[arm]["i1_and_d0_both_correct"]["mean"], 1.0)
            for q in ("S0", "P0", "K0"):
                self.assertEqual(a["C1"][q]["exact"]["mean"], 1.0)
            self.assertEqual(a["status_counts"], {"ok": 52})


if __name__ == "__main__":
    unittest.main()
