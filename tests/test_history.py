"""No-model checks for milestone 2 (HISTORY-INTERPRETATION-PROTOCOL.md, 'No-model checks before inputs are committed')."""
import collections
import json
import os
import re
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

from tempo import engine as E, history as Hm, render  # noqa: E402
import hist_analyze as HA  # noqa: E402

PY = sys.executable
SCORER_TOKENS = ["_src", "ordinal", "true_state", "gold", "hidden", "lure", "intended", '"key"']


def load(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]


def run(*args):
    r = subprocess.run([PY, "-B", *map(str, args)], cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        raise AssertionError(r.stdout + r.stderr)
    return r.stdout


def perfect_record_reply(gold_row):
    return json.dumps(dict(gold_row["gold"], evidence=gold_row["text"].split(": ", 1)[-1].rstrip(".")))


def perfect_readout(gold_row):
    return json.dumps({"facts": gold_row["gold"]})


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.hub = Path(cls.tmp.name)
        for s in ("hist", "histsmoke"):
            run("scripts/hist_generate.py", "--hub", cls.hub, "--set", s)
        d = cls.hub / "data"
        cls.hs = load(d / "hist-histories.jsonl")
        cls.calls = load(d / "hist-calls.jsonl")
        cls.gold = {g["call_id"]: g for g in load(d / "hist-gold.jsonl")}
        cls.smoke = load(d / "histsmoke-calls.jsonl")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def fake_run(self, stage, replies):
        (self.hub / f"{stage}.json").write_text(json.dumps(replies))
        cfg = self.hub / f"cfg-{stage}.json"
        cfg.write_text(json.dumps({"set": "hist", "select": "all", "order_seed": 1, "max_seconds": 600,
                                   "max_calls": 999, "max_input_tokens": 8192, "retry_limit": 1, "model": {}}))
        run("scripts/tempo_run.py", "--hub", self.hub, "--stage", stage, "--config", cfg, "--fake",
            self.hub / f"{stage}.json")
        run("scripts/hist_analyze.py", "--hub", self.hub, "--set", "hist", "--stage", stage, "--boot", "200")
        res = json.loads((self.hub / "analysis-hist" / "ANALYSIS.json").read_text())
        rows = load(self.hub / "analysis-hist" / "checkpoints.jsonl")
        recs = load(self.hub / "analysis-hist" / "records.jsonl")
        return res, rows, recs


class TestGeneration(Base):
    def test_matrix(self):
        self.assertEqual(len(self.hs), 24)
        self.assertEqual(collections.Counter(c["system_name"] for c in self.calls), {"X": 144, "R": 72})
        self.assertEqual(len(self.smoke), 24)
        fam = collections.Counter((h["domain"], h["focal_kind"], h["pattern"]) for h in self.hs)
        self.assertEqual(sum(v for (d, _, _), v in fam.items() if d == "delivery"), 12)
        self.assertEqual({p for (d, _, p) in fam}, set(range(1, 7)))
        for h in self.hs:
            self.assertEqual(len(h["records"]), 6)
            self.assertEqual([cp["k"] for cp in h["checkpoints"]], [2, 4, 6])

    @unittest.skipUnless((RUNS / "temporal-pilot-20261104-232811").is_dir(), "saved run hub not present; set DREAM_RUNS to the run archive")
    def test_names_fresh(self):
        new = set()
        for h in self.hs:
            new |= {f.split(".")[0] for r in h["public_records"] for f in
                    (r["payload"].get("assign") or {r["payload"].get("field", ""): 0})}
        old = set()
        for p in (RUNS / "temporal-pilot-20261104-232811" / "data" / "main-groups.jsonl",
                  RUNS / "temporal-precondition-probe-20261105-085932" / "data" / "probe-worlds.jsonl"):
            for g in load(p):
                old |= {x for x in g["world"].values() if isinstance(x, str) and x[:1].isupper()}
        self.assertFalse({n for n in new & old if not re.fullmatch(r"K\d", n)})
        self.assertTrue(all(len(n) == 6 for n in new))

    def test_prompts_see_only_their_prefix(self):
        byh = {h["history_id"]: h for h in self.hs}
        for c in self.calls:
            h = byh[c["group_id"]]
            w_lines = [render.record_line(type("W", (), {}), r) if False else None for r in []]
            k = c["k"]
            for j, r in enumerate(h["records"], 1):
                present = f"{r['rid']} | received at time" in c["user"]
                self.assertEqual(present, j <= k, (c["call_id"], j))
            for tok in SCORER_TOKENS:
                self.assertNotIn(tok, c["user"], (c["call_id"], tok))
            if c["system_name"] == "X":
                fut = {f.split(".")[0] for r in h["records"][k:] for f in
                       (r["payload"].get("assign") or {r["payload"].get("field"): 0})}
                seen = {f.split(".")[0] for r in h["records"][:k] for f in
                        (r["payload"].get("assign") or {r["payload"].get("field"): 0})}
                for name in fut - seen - {x for x in h["world"].values() if isinstance(x, str)}:
                    self.assertNotIn(name, c["user"])


class TestSystems(Base):
    def test_structured_reference_reproduces_gold(self):
        for h in self.hs:
            rows = HA.run_engine_system(h, [dict(r, source="env") for r in h["public_records"]], "S", None)
            for r in rows:
                self.assertTrue(r["score"]["exact"], (h["history_id"], r["k"]))
                self.assertTrue(all(t["correct"] for t in r["tests"]), (h["history_id"], r["k"], r["tests"]))
                self.assertTrue(r["log_unchanged_by_tests"])

    def test_perfect_replies_give_one_everywhere(self):
        rep = {}
        for c in self.calls:
            g = self.gold[c["call_id"]]
            rep[c["call_id"]] = perfect_record_reply(g) if c["system_name"] == "X" else perfect_readout(g)
        res, rows, recs = self.fake_run("perfect", rep)
        self.assertEqual(res["X_records"]["exact"], 144)
        self.assertEqual(res["X_records"]["engine_accepted"], 144)
        self.assertEqual(res["X_records"]["evidence_linked"], 144)
        for s in ("S", "X", "R"):
            self.assertEqual(res["systems"][s]["PRIMARY_final_state_exact"]["mean"], 1.0, s)
            self.assertEqual(res["systems"][s]["log_unchanged_by_tests"], "72/72")
        for s in ("S", "X"):
            self.assertEqual(res["systems"][s]["PRIMARY_verdict_accuracy"]["mean"], 1.0, s)
        # R format ceiling (declared before any output): a readout "unknown" names no options, so it expands to
        # every allowed value, including "carried by you"; with a perfect readout 142/144 verdicts are correct.
        self.assertEqual(res["systems"]["R"]["verdict_correct"], 142)
        # S, X states identical at every checkpoint
        st = {(r["history_id"], r["k"], r["system"]): r["state"] for r in rows}
        for (hid, k, s), v in st.items():
            if s == "X":
                self.assertEqual(v, st[(hid, k, "S")])

    def test_injected_errors_are_classified_and_propagate(self):
        rep = {}
        for c in self.calls:
            g = self.gold[c["call_id"]]
            rep[c["call_id"]] = perfect_record_reply(g) if c["system_name"] == "X" else perfect_readout(g)
        # (a) wrong value in a change record; (b) correction without a target; (c) provisional -> verified
        byk = collections.defaultdict(list)
        for cid, g in self.gold.items():
            if g["type"] == "record":
                byk[g["gold"]["kind"]].append(cid)
        ch = byk["change"][0]
        g = json.loads(rep[ch]); g["payload"]["to"] = next(x for x in self.gold[ch]["registry"][g["payload"]["field"]]
                                                            if x not in (g["payload"]["to"], g["payload"]["from"]))
        rep[ch] = json.dumps(g)
        co = byk["correction"][0]
        g = json.loads(rep[co]); g["payload"].pop("target"); rep[co] = json.dumps(g)
        pv = next(cid for cid in byk["initial"] if self.gold[cid]["gold"]["status"] == "provisional")
        g = json.loads(rep[pv]); g["status"] = "verified"; rep[pv] = json.dumps(g)
        rep[next(c["call_id"] for c in self.calls if c["system_name"] == "R")] = "not json"
        res, rows, recs = self.fake_run("injected", rep)
        rr = {r["call_id"]: r for r in recs}
        self.assertIn("value", rr[ch]["errors"]); self.assertTrue(rr[ch]["engine_accepted"])
        self.assertIn("target", rr[co]["errors"]); self.assertFalse(rr[co]["engine_accepted"])
        self.assertEqual(rr[pv]["errors"], ["status"]); self.assertTrue(rr[pv]["engine_accepted"])
        self.assertEqual(res["X_records"]["accepted_but_wrong"], 2)
        self.assertEqual(res["systems"]["R"]["invalid_replies"], 1)
        # the wrong change value reaches X's state at the final checkpoint unless overwritten later
        hid = rr[ch]["history_id"]
        x6 = next(r for r in rows if r["system"] == "X" and r["history_id"] == hid and r["k"] == 6)
        s6 = next(r for r in rows if r["system"] == "S" and r["history_id"] == hid and r["k"] == 6)
        fld = json.loads(rep[ch])["payload"]["field"]
        if fld in x6["state"]:
            self.assertNotEqual(x6["state"], s6["state"])
        # the dropped correction leaves X believing the provisional report at the final checkpoint
        hid2 = rr[co]["history_id"]
        x6 = next(r for r in rows if r["system"] == "X" and r["history_id"] == hid2 and r["k"] == 6)
        self.assertFalse(x6["score"]["exact"])
        self.assertEqual(res["systems"]["S"]["PRIMARY_final_state_exact"]["mean"], 1.0)


if __name__ == "__main__":
    unittest.main()
