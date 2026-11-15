"""V1.6.4: multi-seed analysis on a synthetic hub (no model)."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CONDS = ("W", "W+A", "W+X", "W+Y")


def episode(eid, fam, flips):
    qs = []
    for i, f in enumerate(flips):
        for side in "AB":
            qs.append({"qid": f"{eid}-p{i}{side}", "kind": "pair", "pair_id": f"{eid}-p{i}", "flip": f, "side": side})
    qs += [{"qid": f"{eid}-i0", "kind": "irrelevant"}, {"qid": f"{eid}-c0", "kind": "correction"}]
    return {"episode_id": eid, "family": fam, "queries": qs}


class SeedAnalysis(unittest.TestCase):
    def test_flip_present_in_some_episodes_and_seed_averaging(self):
        eps = [episode("d0", "delivery", ["closed", "goalplace"]), episode("d1", "delivery", ["closed", "stock"]),
               episode("a0", "assembly", ["rating"]), episode("a1", "assembly", ["rating", "occupied"])]
        ids = [e["episode_id"] for e in eps]
        with tempfile.TemporaryDirectory() as td:
            hub = Path(td)
            (hub / "data").mkdir()
            (hub / "data" / "toy.jsonl").write_text("".join(json.dumps(e) + "\n" for e in eps))
            # seed s1: W+A right on every query of d0 only; seed s2: W+A right everywhere. W always wrong.
            for st, good in (("s1", {"d0"}), ("s2", set(ids))):
                d = hub / "stages" / st / "eval"
                d.mkdir(parents=True)
                (hub / "stages" / st / "config.json").write_text(json.dumps({"split": "toy", "episodes": ids}))
                for e in eps:
                    rows = [{"qid": q["qid"], "condition": c, "choice": "A",
                             "correct": c == "W+A" and e["episode_id"] in good, "stale": False}
                            for q in e["queries"] for c in CONDS]
                    rows.append({"qid": "_reset"})
                    (d / f"{e['episode_id']}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
            out = hub / "out.json"
            subprocess.run([sys.executable, "-B", str(ROOT / "scripts" / "ectx_seed_analysis.py"), "--hub", str(hub),
                            "--seed", "s1=s1", "--seed", "s2=s2", "--out", str(out)], check=True, capture_output=True)
            rep = json.loads(out.read_text())
        cp = rep["contrasts"]["W+A - W"]["complete_pair"]
        # per-episode seed means: d0 1.0, d1 0.5, a0 0.5, a1 0.5 -> delivery 0.75, assembly 0.5 -> 0.625
        self.assertAlmostEqual(cp["diff"], 0.625)
        self.assertEqual(rep["episodes"], 4)
        # 'stock' exists only in d1 (seed mean 0.5); 'closed' in d0 and d1 (mean of 1.0 and 0.5)
        self.assertAlmostEqual(rep["means"]["W+A"]["flip:stock"]["pooled"], 0.5)
        self.assertAlmostEqual(rep["means"]["W+A"]["flip:closed"]["pooled"], 0.75)
        self.assertEqual(rep["means"]["W+A"]["flip:occupied"]["by_world"], {"assembly": 0.5})


if __name__ == "__main__":
    unittest.main()
