"""No-model tests for the V1.7.2 diagnostic. Reads the 1.7.1 pilot hub read-only (path below)."""
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
PILOT = Path(os.environ.get("DREAM_TEMPORAL_PILOT_HUB",
                            f"{LP.RUNS}/temporal-pilot-20261104-232811"))

from tempo import diag as D, render  # noqa: E402
import diag_generate as DG  # noqa: E402

PY = sys.executable
SCORER_TOKENS = ["_src", "lure", "key_plan", "intended", "hidden", "ordinal", "acceptable", "plan_valid",
                 "pair_other", "origin"]


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
        for s in ("diag", "diagsmoke"):
            run("scripts/diag_generate.py", "--pilot-hub", PILOT, "--hub", cls.hub, "--set", s)
        d = cls.hub / "data"
        cls.calls = load(d / "diag-calls.jsonl")
        cls.gold = {g["call_id"]: g for g in load(d / "diag-gold.jsonl")}
        cls.tmpl = load(d / "diag-step2-templates.jsonl")
        cls.smoke = load(d / "diagsmoke-calls.jsonl")
        cls.main_calls = {c["call_id"]: c for c in load(PILOT / "data" / "main-calls.jsonl")}
        cls.main_gold = {c["call_id"]: c for c in load(PILOT / "data" / "main-gold.jsonl")}
        cls.built = DG.rebuild(PILOT / "data", "main")[1]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()


@unittest.skipUnless(PILOT.is_dir(), "saved run hub not present; set DREAM_RUNS to the run archive")
class TestDiag(Base):
    def test_matrix_counts(self):
        c = collections.Counter(x["block"] for x in self.calls)
        self.assertEqual(dict(c), {"A": 96, "B": 96, "C": 48, "D": 104, "E": 88})
        self.assertEqual(len(self.tmpl), 48)
        self.assertEqual(len(self.smoke) + 2, 24)  # + two step-2 smoke calls
        self.assertEqual(len({x["group_id"] for x in self.calls}), 24)

    def test_old_prompt_path_unchanged(self):
        for w, g in self.built:
            for arm in ("C0", "C1"):
                for q in ("D0", "D1", "A0"):
                    cid = f"{g['group_id']}|short|{arm}|{q}"
                    c = self.main_calls[cid]
                    var = g["variants"]["short"][c["variant"]]
                    u = render.user_prompt(w, arm, q, var["records"], var["now_state"] if arm == "C0" else None,
                                           g["now"], option_map=g["option_map"])
                    self.assertEqual(u, c["user"], cid)
            self.assertEqual(D.decision_query(w, g["option_map"], D.POLICY_ORIGINAL),
                             render.decision_query(w, g["option_map"]))

    def test_domain_facts_in_every_diag_prompt_only(self):
        for c in self.calls + [x for x in self.smoke if x["block"] != "R"]:
            for line in D.DOMAIN_FACTS[c["domain"]]:
                self.assertEqual(c["user"].count("- " + line + "\n"), 1, c["call_id"])
        for t in self.tmpl:
            for line in D.DOMAIN_FACTS[t["domain"]]:
                self.assertIn("- " + line + "\n", t["head"])
        for c in self.main_calls.values():
            self.assertNotIn("roads are open", c["user"])
            self.assertNotIn("no adapters", c["user"])

    def test_every_action_prerequisite_has_a_model_facing_statement(self):
        for w, g in self.built:
            text = "\n".join(D.header_complete(w))
            if w.domain == "delivery":
                needs = ["All crates are portable.", f"You are at {w.you}, with empty hands.",
                         "All listed roads are open.", "nothing changes except through your own actions"]
                needs += [f"Road between {a} and {b}: cost {c}." for a, b, c in w.roads]
            else:
                needs = [f"Slot {w.t}: connector {w.k}.", f"Part {w.g}: connector {w.k}, rating",
                         f"Price of {w.g}: {w.price}. No other part can be ordered.",
                         "no adapter is fitted to any slot", "nothing changes except through your own actions"]
                st, s, _ = w.to_planner({f: v for f, v in w.fixed_other.items()} | {
                    w.slot_f: "empty", w.stock_f: "yes", w.side: "empty", f"{w.d}.on_hand": "no"})
                self.assertEqual(st["adapters"], {})
                self.assertEqual(s["slot_adapter"], {})
            for n in needs:
                self.assertIn(n, text, (g["group_id"], n))
            if w.domain == "delivery":
                self.assertEqual(w.to_planner({f"{e}.location": w.you for e in (w.x, w.y, w.z)})[1]["closed"], [])

    def test_arm_twins_share_header_and_query(self):
        by = collections.defaultdict(dict)
        for c in self.calls:
            if c["block"] in ("A", "B", "E", "D"):
                by[(c["group_id"], c["block"], c["qtype"], c["variant"])][c["arm"]] = c
        n = 0
        for k, v in by.items():
            a, b = v["C0"]["user"], v["C1"]["user"]
            self.assertEqual(v["C0"]["system"], v["C1"]["system"])
            self.assertEqual(a.split("\n\nIt is now time")[0], b.split("\n\nRecords received so far:")[0])
            q = "\n\nQUERY ("
            self.assertEqual(a[a.index(q):], b[b.index(q):], k)
            n += 1
        self.assertEqual(n, 48 + 48 + 52 + 44)  # A, B sides; D pairs + uncertain; E rows

    def test_gold_sets_equal_across_original_A_B_E(self):
        for c in self.calls:
            if c["block"] not in ("A", "B", "E"):
                continue
            g = self.gold[c["call_id"]]
            old = self.main_gold[f"{c['group_id']}|short|{c['arm']}|{c['qtype']}"]
            self.assertEqual(g["acceptable"], old["acceptable"])
            self.assertEqual(g["key_plan"], old["key_plan"])
            if c["block"] == "E":
                self.assertTrue(g["determined"])
                self.assertIsNone(g["obs_option"])
                self.assertNotIn(old["obs_option"], c["option_ids"])
                self.assertEqual(len(c["option_ids"]), 3)
                bq = next(x for x in self.calls if x["call_id"] == c["call_id"].replace("|E|", "|B|"))
                bl = [l for l in bq["user"].splitlines() if l.startswith("[")]
                el = [l for l in c["user"].splitlines() if l.startswith("[")]
                self.assertEqual(el, [l for l in bl if not l.startswith(f"[{old['obs_option']}]")])
            else:
                self.assertEqual(g["obs_option"], old["obs_option"])
            # policy sanity: the acceptable plan is valid; OBS only when no plan is valid in every state
            if g["key_plan"] == "OBS":
                self.assertFalse(any(g["plan_valid"].values()))
            else:
                self.assertTrue(g["plan_valid"][g["acceptable"][0]])

    def test_determined_split(self):
        for b in ("A", "B"):
            for arm in ("C0", "C1"):
                rows = [c for c in self.calls if c["block"] == b and c["arm"] == arm]
                det = [c for c in rows if self.gold[c["call_id"]]["determined"]]
                self.assertEqual((len(rows), len(det)), (48, 44))
                self.assertTrue(all(c["pattern"] == 6 and c["qtype"] == "D0" for c in rows if c not in det))

    def test_D_pairs_balanced_and_matched(self):
        d = [c for c in self.calls if c["block"] == "D"]
        cnt = collections.Counter((c["arm"], c["variant"]) for c in d)
        self.assertEqual(cnt, {("C0", "valid"): 24, ("C0", "invalid"): 24, ("C1", "valid"): 24,
                               ("C1", "invalid"): 24, ("C0", "uncertain"): 4, ("C1", "uncertain"): 4})
        app = {"valid": True, "invalid": False, "uncertain": "unknown"}
        for c in d:
            self.assertEqual(self.gold[c["call_id"]]["applicable"], app[c["variant"]], c["call_id"])
            if c["variant"] == "invalid":
                g = self.gold[c["call_id"]]
                self.assertEqual(g["predicted"], g["observed"])  # no effect
        by = collections.defaultdict(dict)
        for c in d:
            by[(c["group_id"], c["arm"])][c["variant"]] = c
        alloc = collections.Counter()
        for (gid, arm), v in by.items():
            a, b = v["valid"]["user"], v["invalid"]["user"]
            act = lambda u: [l for l in u.splitlines() if l.startswith("Suppose you were to do")]
            self.assertEqual(act(a), act(b))
            self.assertEqual(a.split("\n\n")[:3], b.split("\n\n")[:3])  # same world, rules and fixed facts
            if arm == "C1":
                self.assertEqual(v["valid"]["n_records"], v["invalid"]["n_records"])
            w, g = next(x for x in self.built if x[1]["group_id"] == gid)
            alloc[(w.domain, g["focal_kind"])] += arm == "C0"
        self.assertEqual(alloc, {("delivery", None): 12, ("assembly", "slot"): 6, ("assembly", "stock"): 6})

    def test_no_scorer_tokens_in_prompts(self):
        texts = [c["user"] for c in self.calls + self.smoke] + [t["head"] + t["tail"] for t in self.tmpl]
        for t in texts:
            for tok in SCORER_TOKENS:
                self.assertNotIn(tok, t)

    def test_pilot_artifacts_untouched(self):
        for s in ("main", "smoke"):
            cm = json.loads((PILOT / "data" / f"COMMITMENT-{s}.json").read_text())
            for p in ("groups", "calls", "gold"):
                h = hashlib.sha256((PILOT / "data" / f"{s}-{p}.jsonl").read_bytes()).hexdigest()
                self.assertEqual(h, cm[f"{p}_sha256"])
        self.assertEqual(len(list((PILOT / "stages" / "main" / "calls").glob("*.json"))), 792)

    def test_refuses_overwrite(self):
        with self.assertRaises(AssertionError):
            run("scripts/diag_generate.py", "--pilot-hub", PILOT, "--hub", self.hub, "--set", "diag")


def gold_reply(g):
    if g["type"] == "decision":
        return json.dumps({"choice": g["acceptable"][0]})
    if g["type"] == "facts":
        return json.dumps({"facts": g["gold"]})
    return json.dumps({"applicable": g["applicable"], "predicted_next_facts": g["predicted"],
                       "observed_world_facts": g["observed"]})


@unittest.skipUnless(PILOT.is_dir(), "saved run hub not present; set DREAM_RUNS to the run archive")
class TestPipeline(Base):
    def cfg(self, s):
        p = self.hub / f"cfg-{s}.json"
        p.write_text(json.dumps({"set": s, "select": "all", "order_seed": 1, "max_seconds": 600, "max_calls": 999,
                                 "max_input_tokens": 8192, "retry_limit": 1, "model": {}}))
        return p

    def test_end_to_end_gold_replies(self):
        d = self.hub / "data"
        rep = {c: gold_reply(g) for c, g in self.gold.items()}
        weird = "```json\n{\"facts\": {\"x\": \"<odd> \\\"quoted\\\" text\"}}\n```\nand trailing prose"
        first = self.tmpl[0]["step1_call_id"]
        rep[first] = weird
        (self.hub / "r1.json").write_text(json.dumps(rep))
        run("scripts/tempo_run.py", "--hub", self.hub, "--stage", "s1", "--config", self.cfg("diag"),
            "--fake", self.hub / "r1.json")
        run("scripts/diag_step2.py", "--hub", self.hub, "--set", "diag", "--stage", "s1")
        c2 = load(d / "diagc2-calls.jsonl")
        self.assertEqual(len(c2), 48)
        t0 = self.tmpl[0]
        u = next(c for c in c2 if c["call_id"] == t0["call_id"])["user"]
        self.assertEqual(u, t0["head"] + "\n\n" + D.STATE_RECORD_INTRO + "\n" + weird + "\n" + t0["tail"])
        for c in c2:
            for tok in SCORER_TOKENS:
                self.assertNotIn(tok, c["user"])
        g2 = {g["call_id"]: g for g in load(d / "diagc2-gold.jsonl")}
        (self.hub / "r2.json").write_text(json.dumps({c: gold_reply(g) for c, g in g2.items()}))
        run("scripts/tempo_run.py", "--hub", self.hub, "--stage", "s2", "--config", self.cfg("diagc2"),
            "--fake", self.hub / "r2.json")
        with self.assertRaises(AssertionError):  # step 2 is committed once
            run("scripts/diag_step2.py", "--hub", self.hub, "--set", "diag", "--stage", "s1")
        run("scripts/diag_analyze.py", "--hub", self.hub, "--set", "diag", "--stage1", "s1", "--stage2", "s2",
            "--pilot-hub", PILOT, "--boot", "200")
        res = json.loads((self.hub / "analysis-diag" / "ANALYSIS.json").read_text())
        for k in ("A:C0", "A:C1", "B:C0", "B:C1", "C:C1"):
            self.assertEqual(res["decisions"][k]["complete_pair"]["mean"], 1.0, k)
        for k in ("E:C0", "E:C1"):
            self.assertEqual(res["decisions"][k]["determined_correct"], 44)
        self.assertEqual(res["C_workflow"]["readout_exact"], 47)  # the one weird readout is invalid
        self.assertEqual(res["C_workflow"]["decision_correct"], 48)
        for arm in ("C0", "C1"):
            a = res["actions"][arm]
            self.assertEqual(a["balanced_applicability"]["mean"], 1.0)
            self.assertEqual(a["pair_all_three_correct"]["mean"], 1.0)
            self.assertEqual(a["uncertain"]["applicable_correct"], 4)
        # old pilot rows are the saved outputs, so they reproduce the pilot's short-length counts
        self.assertEqual(res["decisions"]["old:C1"]["complete_pair_count"], "0/24")
        self.assertIn("A-old:C1:complete_pair", res["contrasts"])


if __name__ == "__main__":
    unittest.main()
