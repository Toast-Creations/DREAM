"""No-model checks for V1.17.0 record-context ablation (test-only pools)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from tempo import assertions as A, ctxablate as CA, freshgen as FG, nullprior as NP, prose, prose_study as PS, \
    text_channel as TC  # noqa: E402
from contract_validate import score_record  # noqa: E402

FG.CONS["cabtest"] = "bcdfghk"


class CtxAblate(unittest.TestCase):
    def setUp(self):
        self.w, self.out, self.rs = CA.build_group("t1", 4242, (4, "P_first", "lure_P"), "cabtest", 7)

    def test_01_variants_share_skeleton_and_differ_in_target(self):
        P = f"{self.w.g}.on_hand"
        a, o, r, c = (self.out[v] for v in CA.VARIANTS)
        self.assertEqual([x["payload"].get("field") for x in a[:-1]], [x["payload"].get("field") for x in c[:-1]])
        self.assertEqual((a[-1]["kind"], o[-1]["kind"], r[-1]["kind"], c[-1]["kind"]),
                         ("change", "observation", "change", "correction"))
        pre = {v: next(x for x in self.out[v][:-1] if x["payload"].get("field") == P) for v in CA.VARIANTS}
        self.assertEqual(pre["arrival"]["payload"]["value"], "no")
        self.assertEqual(pre["correction"]["status"], "provisional")
        self.assertEqual(c[-1]["payload"]["target"], pre["correction"]["rid"])
        for v, recs in self.out.items():
            for x in recs:
                PS.check_equivalent(x, prose.prose_line(self.w, x, self.rs))

    def test_02_local_differs_only_in_context_and_keeps_registry(self):
        for v, recs in self.out.items():
            full = CA.full_prompt(self.w, recs, self.rs)
            loc = CA.local_prompt(full)
            ctx = CA.check_diff(full, loc)
            self.assertEqual(len(ctx), len(recs) - 1)
            self.assertIn(NP.CLARIFICATION, loc)
            self.assertEqual(full[full.index("Fields and allowed values:"):], loc[loc.index("Fields and allowed values:"):])
            self.assertIn(prose.prose_line(self.w, recs[-1], self.rs), loc)

    def test_03_template_targeting(self):
        self.assertEqual(CA.template_id(prose.prose_line(self.w, self.out["arrival"][-1], self.rs)), 7)
        seen = set()
        for t in range(12):
            w, out, rs = CA.build_group(f"t{t}", 5000 + t, (3, "Q_first", "lure_W"), "cabtest", t)
            seen.add(CA.template_id(prose.prose_line(w, out["arrival"][-1], rs)))
        self.assertEqual(seen, set(range(12)))

    def test_04_controls_identical_local_distinct_full(self):
        w, hist, rs, text = CA.build_control("c", 99, "cabtest")
        fa, fb = CA.full_prompt(w, hist["A"], rs, text), CA.full_prompt(w, hist["B"], rs, text)
        self.assertNotEqual(fa, fb)
        self.assertEqual(CA.local_prompt(fa), CA.local_prompt(fb))
        self.assertNotEqual(hist["A"][-1]["payload"]["field"], hist["B"][-1]["payload"]["field"])
        self.assertIn("checked in r02", text)

    def test_05_scorer_on_perfect_and_state_misread(self):
        g = A.from_v02(self.out["arrival"][-1])
        text = prose.prose_line(self.w, self.out["arrival"][-1], self.rs)
        self.assertTrue(score_record(g, self.out["arrival"][-1], text)["denotation_equal"])
        st = {"rid": g["rid"], "kind": "initial", "status": "verified", "event_at": g["assertions"][0]["at"],
              "received_at": g["received_at"], "payload": {"assign": {g["assertions"][0]["field"]: "yes"}}}
        self.assertFalse(score_record(A.from_v02(st), self.out["arrival"][-1], text)["denotation_equal"])


if __name__ == "__main__":
    unittest.main()
