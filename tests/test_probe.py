"""No-model tests for the V1.7.3 precondition probe."""
import collections
import hashlib
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
PILOT = RUNS / "temporal-pilot-20261104-232811"
DIAG = RUNS / "temporal-diagnostic-20261105-081325"

from tempo import enumcheck, generate as G, probe as P, probe_score as PS, render  # noqa: E402
from tempo.worlds import UNKNOWN  # noqa: E402

PY = sys.executable
SCORER_TOKENS = ["_src", "lure", "key_plan", "intended", "hidden", "ordinal", "acceptable", "origin",
                 "unknown_only", "false_unknown", "effect_fields", "preserve_fields"]


def load(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]


def run(*args):
    r = subprocess.run([PY, "-B", *map(str, args)], cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        raise AssertionError(r.stdout + r.stderr)
    return r.stdout


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.hub = Path(cls.tmp.name)
        for s in ("probe", "probesmoke"):
            run("scripts/probe_generate.py", "--hub", cls.hub, "--set", s)
        d = cls.hub / "data"
        cls.calls = load(d / "probe-calls.jsonl")
        cls.gold = {g["call_id"]: g for g in load(d / "probe-gold.jsonl")}
        cls.smoke = load(d / "probesmoke-calls.jsonl")
        import probe_generate as PG
        cls.built = PG.build("probe", 20261108, False)[0]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()


class TestProbe(Base):
    def test_matrix_and_allocation(self):
        self.assertEqual(len(self.calls), 280)
        self.assertLessEqual(len(self.smoke), 24)
        c = collections.Counter((x["condition"], x["arm"]) for x in self.calls)
        self.assertEqual(set(c.values()), {56})
        fam = collections.Counter(m["family"] for _, m, _ in self.built)
        self.assertEqual(fam, {"location": 12, "slot occupancy": 6, "stock availability": 6})
        ctl = collections.Counter((m["domain"], m["control"]) for _, m, _ in self.built if m["control"])
        self.assertEqual(ctl, {("delivery", "unknown_only"): 2, ("delivery", "false_unknown"): 2,
                               ("assembly", "unknown_only"): 2, ("assembly", "false_unknown"): 2})
        pats = collections.Counter((m["family"], m["pair_pattern"]) for _, m, _ in self.built)
        for f in ("location", "slot occupancy", "stock availability"):
            self.assertEqual({p for (ff, p) in pats if ff == f}, {1, 2, 3, 4, 5})
        rows = collections.Counter(x["row"] for x in self.calls if x["condition"] == "direct" and x["arm"] == "C0")
        self.assertEqual(rows, {"valid": 24, "invalid": 24, "unknown_only": 4, "false_unknown": 4})

    def test_deterministic(self):
        import probe_generate as PG
        again = PG.build("probe", 20261108, False)[0]
        a = [json.dumps(r, sort_keys=True, default=str) for _, _, r in self.built]
        b = [json.dumps(r, sort_keys=True, default=str) for _, _, r in again]
        self.assertEqual(a, b)

    def test_pairs_balanced_matched(self):
        for w, m, rows in self.built:
            v, i = rows["valid"], rows["invalid"]
            self.assertIs(v["a0"]["applicable"], True)
            self.assertIs(i["a0"]["applicable"], False)
            self.assertEqual(i["a0"]["predicted"], i["a0"]["observed"])  # blocked: no effect
            self.assertEqual(len(v["records"]), len(i["records"]))
            self.assertEqual(len(v["records"]), P.N_RECORDS)
            self.assertIsNone(v["carried"]); self.assertIsNone(i["carried"])
            pv, pi = v["predicates"], i["predicates"]
            self.assertEqual([k for k in pv if pv[k] != pi[k]], [{"location": "crate_at_your_place",
                                                                   "slot occupancy": "slot_empty",
                                                                   "stock availability": "part_on_hand"}[m["family"]]])
            self.assertTrue(all(x is True for x in pv.values()))

    def test_controls(self):
        for w, m, rows in self.built:
            if not m["control"]:
                self.assertEqual(set(rows), {"valid", "invalid"})
                continue
            r = rows[m["control"]]
            vals = list(r["predicates"].values())
            if m["control"] == "unknown_only":
                self.assertEqual(r["a0"]["applicable"], UNKNOWN)
                self.assertEqual((vals.count(UNKNOWN), vals.count(False)), (1, 0))
            else:
                self.assertIs(r["a0"]["applicable"], False)
                self.assertEqual((vals.count(UNKNOWN), vals.count(False)), (1, 1))
            # unknown applicability does not make every successor field unknown
            known = [f for f in w.asked if r["a0"]["observed"][f] != UNKNOWN]
            self.assertTrue(known)
            for f in known:
                if f not in r["a0"]["effect_fields"]:
                    self.assertEqual(r["a0"]["predicted"][f], r["a0"]["observed"][f])

    def test_predicates_vs_enumeration_independent(self):
        for w, m, rows in self.built:
            for rk, r in rows.items():
                _, states = enumcheck.supported_set(r["records"], w.asked, G.NOW)
                apps = {w.apply_keycheck(s)[0] for s in states}
                app = apps.pop() if len(apps) == 1 else UNKNOWN
                self.assertEqual(app, r["a0"]["applicable"])
                self.assertEqual(P.conj3(r["predicates"].values()), app)

    def test_hands_statement_matches_state(self):
        for c in self.calls + self.smoke:
            if c["domain"] != "delivery":
                continue
            u = c["user"]
            carrying = "carrying crate" in u.split("Records received so far")[0].split("It is now time")[0]
            empty = "with empty hands" in u
            self.assertNotEqual(carrying, empty, c["call_id"])
            self.assertEqual(carrying, c["row"] == "false_unknown", c["call_id"])

    def test_prompts(self):
        by = collections.defaultdict(dict)
        for c in self.calls:
            self.assertIn("If the action is not allowed right now it fails and changes nothing.", c["user"])
            for tok in SCORER_TOKENS:
                self.assertNotIn(tok, c["user"], (c["call_id"], tok))
            by[(c["group_id"], c["row"])][(c["condition"], c["arm"])] = c
        for (gid, rk), d in by.items():
            w = next(x[0] for x in self.built if x[1]["world_id"] == gid)
            for k, t in P.predicate_spec(w):
                self.assertIn(f"- {json.dumps(k)}: {t}", d[("checklist", "C0")]["user"])
                self.assertIn(f"- {t}: ", d[("supplied", "C0")]["user"])
                self.assertNotIn('"preconditions"', d[("direct", "C0")]["user"])
            for cond in ("direct", "checklist"):
                a, b = d[(cond, "C0")]["user"], d[(cond, "C1")]["user"]
                q = "\n\nQUERY ("
                self.assertEqual(a[a.index(q):], b[b.index(q):])
                self.assertEqual(a.split("\n\nIt is now time")[0], b.split("\n\nRecords received so far:")[0])
            # supplied = C0 direct prompt plus the requirement block only
            s, dc = d[("supplied", "C0")]["user"], d[("direct", "C0")]["user"]
            blk = "\n".join(P.supplied_checklist(w, next(r for x in self.built if x[1]["world_id"] == gid
                                                           for k2, r in x[2].items() if k2 == rk)["predicates"]))
            self.assertEqual(s.replace("\n" + blk, ""), dc)
            if rk in ("unknown_only", "false_unknown"):
                self.assertIn(": unknown", s)
        # pair sides share action text
        for (gid, rk), d in by.items():
            if rk == "valid":
                inv = by[(gid, "invalid")]
                act = lambda u: [l for l in u.splitlines() if l.startswith("Suppose")]
                self.assertEqual(act(d[("direct", "C0")]["user"]), act(inv[("direct", "C0")]["user"]))

    @unittest.skipUnless(PILOT.is_dir(), "saved run hub not present; set DREAM_RUNS to the run archive")
    def test_fresh_names_disjoint_from_earlier_runs(self):
        old = set()
        for p in ("main", "smoke"):
            for g in load(PILOT / "data" / f"{p}-groups.jsonl"):
                old |= {x for x in g["world"].values() if isinstance(x, str) and x[:1].isupper()}
                for L in g["variants"].values():
                    for r in L["a"]["records"]:
                        old |= {f.split(".")[0] for f in (r["payload"].get("assign") or {r["payload"].get("field", ""): 0})}
        new = set()
        for w, m, rows in self.built:
            new |= {x for x in vars(w).values() if isinstance(x, str) and x[:1].isupper()}
            for r in rows.values():
                new |= {f.split(".")[0] for f in r["now_state"]}
        import re
        clash = {x for x in new & old if not re.fullmatch(r"K\d", x)}  # connector labels are shared types
        self.assertFalse(clash)

    @unittest.skipUnless(PILOT.is_dir() and DIAG.is_dir(), "saved run hub not present; set DREAM_RUNS to the run archive")
    def test_earlier_artifacts_untouched(self):
        for hub, sets in ((PILOT, ("main", "smoke")), (DIAG, ("diag", "diagsmoke"))):
            for s in sets:
                cm = json.loads((hub / "data" / f"COMMITMENT-{s}.json").read_text())
                h = hashlib.sha256((hub / "data" / f"{s}-calls.jsonl").read_bytes()).hexdigest()
                self.assertEqual(h, cm["calls_sha256"])

    def test_scorer_fixtures(self):
        w, m, rows = next(x for x in self.built if x[1]["control"] == "false_unknown" and x[1]["domain"] == "assembly")
        cid = f"{m['world_id']}|checklist|C0|invalid"
        g = self.gold[cid]
        keys = list(g["predicates"])
        good = {"preconditions": g["predicates"], "applicable": g["applicable"],
                "predicted_next_facts": g["predicted"], "observed_world_facts": g["observed"]}
        r = PS.score_probe(json.dumps(good), g, "checklist", keys)
        self.assertTrue(r["valid"] and r["pred_vector_exact"] and r["consistent_with_own_predicates"]
                        and r["blocked_and_no_effect"])
        # order recorded; strings accepted
        alt = {"applicable": "false", "preconditions": {k: str(v).lower() for k, v in g["predicates"].items()},
               "predicted_next_facts": g["predicted"], "observed_world_facts": g["observed"]}
        r = PS.score_probe(json.dumps(alt), g, "checklist", keys)
        self.assertTrue(r["valid"]); self.assertEqual(r["order"][0], "applicable")
        # amendment P1: yes/no accepted for requirement values (not for "applicable")
        yn = dict(good, preconditions={k: ("unknown" if v == UNKNOWN else ("Yes" if v else "no"))
                                       for k, v in g["predicates"].items()})
        self.assertTrue(PS.score_probe(json.dumps(yn), g, "checklist", keys)["pred_vector_exact"])
        self.assertFalse(PS.score_probe(json.dumps(dict(good, applicable="no")), g, "checklist", keys)["valid"])
        # wrong premise (all true) + consistent wrong conclusion
        bad = dict(good, preconditions={k: True for k in keys}, applicable=True)
        r = PS.score_probe(json.dumps(bad), g, "checklist", keys)
        self.assertFalse(r["applicable_correct"]); self.assertTrue(r["consistent_with_own_predicates"])
        # right premise, inconsistent conclusion; rejected but effects applied = gating inconsistency
        inc = dict(good, applicable=True)
        r = PS.score_probe(json.dumps(inc), g, "checklist", keys)
        self.assertFalse(r["consistent_with_own_predicates"])
        eff = dict(good, predicted_next_facts=dict(g["predicted"], **{w.slot_f: w.g}))
        self.assertTrue(PS.score_probe(json.dumps(eff), g, "checklist", keys)["gating_inconsistent"])
        # missing key / extra key / bad value -> invalid
        for b in (dict(good, preconditions={k: True for k in keys[:2]}),
                  dict(good, preconditions=dict(g["predicates"], extra=True)),
                  dict(good, preconditions=dict(g["predicates"], **{keys[0]: "maybe"}))):
            self.assertFalse(PS.score_probe(json.dumps(b), g, "checklist", keys)["valid"])
        self.assertFalse(PS.score_probe("{}", g, "checklist", keys)["valid"])


def gold_reply(c, g):
    o = {"applicable": g["applicable"], "predicted_next_facts": g["predicted"], "observed_world_facts": g["observed"]}
    if c["condition"] == "checklist":
        o = {"preconditions": g["predicates"], **o}
    return json.dumps(o)


class TestPipeline(Base):
    def test_end_to_end(self):
        rep = {c["call_id"]: gold_reply(c, self.gold[c["call_id"]]) for c in self.calls}
        (self.hub / "r.json").write_text(json.dumps(rep))
        cfg = self.hub / "cfg.json"
        cfg.write_text(json.dumps({"set": "probe", "select": "all", "order_seed": 1, "max_seconds": 600,
                                   "max_calls": 999, "max_input_tokens": 8192, "retry_limit": 1, "model": {}}))
        run("scripts/tempo_run.py", "--hub", self.hub, "--stage", "s", "--config", cfg, "--fake", self.hub / "r.json")
        run("scripts/probe_analyze.py", "--hub", self.hub, "--set", "probe", "--stage", "s", "--boot", "200")
        res = json.loads((self.hub / "analysis-probe" / "ANALYSIS.json").read_text())
        for k, v in res["cells"].items():
            self.assertEqual(v["PRIMARY_pair_applicability"]["mean"], 1.0, k)
            self.assertEqual(v["PRIMARY_invalid_blocked_no_effect"]["mean"], 1.0, k)
            self.assertEqual(v["invalid_replies"], 0)
            for rk in ("unknown_only", "false_unknown"):
                self.assertEqual(v[rk]["applicable_correct"], 4)
                self.assertEqual(v[rk]["all_three"], 4)
        for arm in ("C0", "C1"):
            p = res["cells"][f"checklist:{arm}"]["predicates"]
            self.assertEqual((p["vector_exact"], p["applicability_consistent_with_own_predicates"]), (56, 56))
        self.assertEqual(len(res["contrasts"]), 4)


if __name__ == "__main__":
    unittest.main()
