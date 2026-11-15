"""V1.5.5 Stage A v2: held-out items, probes, release-steered membership readout, end-to-end resumable run."""
import importlib.util
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest import mock

from survival import categorization_items as ci
from survival import direction_screen as ds

ROOT = Path(__file__).resolve().parents[1]
AVAILABLE = all(importlib.util.find_spec(n) is not None for n in ("torch", "transformers", "safetensors"))


class StaticTests(unittest.TestCase):
    def test_sets_are_fresh_and_complete(self):
        prompts = json.loads((ROOT / "data/decategorization_prompts.json").read_text())
        used = {p["object"].lower() for p in prompts["build"] + prompts["heldout"]}
        for name in ("survival-dev-tasks", "survival-smoke-tasks", "continuity-dev-tasks", "continuity-smoke-tasks"):
            used |= {json.loads(x)["subject"].lower()
                     for x in (ROOT / "data" / f"{name}.jsonl").read_text().splitlines() if x.strip()}
        used |= {n for n, _ in ds.SCREEN_OBJECTS + ds.SCREEN_OBJECTS_B}
        names = [e[0] for e in ci.SET_C + ci.SET_D]
        self.assertEqual((len(ci.SET_C), len(ci.SET_D), len(set(names))), (24, 24, 48))
        self.assertFalse(set(names) & used)
        for e in ci.SET_C + ci.SET_D:
            levels = [lv for lv, _ in ci.categories(e)]
            self.assertEqual(levels, ["typical"] * 2 + ["peripheral"] * 2 + ["remote"] * 2 + ["foil"] * 2)
            self.assertEqual(len({c for _, c in ci.categories(e)}), 8, e[0])
            self.assertTrue(all(b in ci.BASES for _, b in e[4]), e[0])

    def test_probe_text_and_formulations(self):
        from survival import categorization_check as cc
        self.assertEqual(sorted(ci.FORMULATIONS), ["F1", "F2", "F3"])
        self.assertIn("No or Yes", ci.FORMULATIONS["F2"])
        u = cc.membership_user("vase", "a vessel", "containers", "F1")
        self.assertTrue(u.startswith("Object: vase: a vessel"))
        self.assertIn('category "containers"', u)
        p = cc.assoc_user("vase", "a vessel", ds.PREAMBLES["P2"])
        self.assertTrue(p.startswith(ds.PREAMBLES["P2"] + "\n\nObject: "))


@unittest.skipUnless(AVAILABLE, "PyTorch/Transformers required")
class ModelTests(unittest.TestCase):
    def setUp(self):
        import torch
        from transformers import Qwen2Config, Qwen2ForCausalLM
        self.torch = torch
        torch.manual_seed(3)
        self.model = Qwen2ForCausalLM(Qwen2Config(vocab_size=64, hidden_size=32, intermediate_size=64,
            num_hidden_layers=4, num_attention_heads=4, num_key_value_heads=2, max_position_embeddings=4096,
            attention_dropout=0.0, bos_token_id=1, eos_token_id=2, pad_token_id=0))
        for p in self.model.parameters():
            p.requires_grad_(False)
        self.model.eval()

        class Tokenizer:
            eos_token_id = 2; pad_token_id = 0; chat_template = "test"
            def __init__(self): self.dream_chat_kwargs = {"enable_thinking": False}
            def apply_chat_template(self, messages, **kw): return " ".join(m["content"] for m in messages)
            def __call__(self, text, return_tensors=None, add_special_tokens=False, return_offsets_mapping=False):
                ids = [3 + (b % 60) for b in text.encode("ascii", "replace")]
                out = {"input_ids": torch.tensor([ids]) if return_tensors else ids}
                out["attention_mask"] = torch.ones_like(out["input_ids"]) if return_tensors else [1] * len(ids)
                return out
            def decode(self, ids, skip_special_tokens=True): return "".join(chr(97 + int(x) % 26) for x in ids)
        self.tok = Tokenizer()

    def test_log_odds_during_and_after(self):
        from survival import categorization_check as cc
        v = ds.random_vectors(32)[0][2]
        msgs = [{"role": "user", "content": cc.membership_user("vase", "a vessel", "containers", "F2")}]
        base = cc.log_odds(self.model, self.tok, msgs)
        steered = cc.log_odds(self.model, self.tok, msgs, (v, -3, 0.4))
        self.assertTrue(0 < base["mass"] <= 1)
        self.assertNotAlmostEqual(base["log_odds"], steered["log_odds"], places=6)
        after = [{"role": "user", "content": cc.assoc_user("vase", "a vessel")},
                 {"role": "assistant", "content": "glass, flower"}, {"role": "user", "content": "Yes or No?"}]
        self.assertIsInstance(cc.log_odds(self.model, self.tok, after)["log_odds"], float)
        yes, no = cc.label_ids(self.tok)
        self.assertFalse(set(yes) & set(no))

    def test_release_schedule_glides_to_zero(self):
        from survival import categorization_check as cc
        from dream_core.schedules import dose
        self.assertEqual(dose(0, cc.RELEASE), 1.0)
        self.assertEqual(dose(cc.RELEASE["glide_tokens"], cc.RELEASE), 0.0)
        v = ds.random_vectors(32)[0][2]
        rec = cc.associations(self.model, self.tok, cc.assoc_user("vase", "a vessel"), (v, -3, 0.2))
        self.assertEqual(rec["dose_trace"][0], 0.2)
        self.assertTrue(all(b <= a for a, b in zip(rec["dose_trace"], rec["dose_trace"][1:])))
        hot = cc.associations(self.model, self.tok, cc.assoc_user("vase", "a vessel"), temperature=1.2, seed=1)
        self.assertNotIn("dose_trace", hot)

    def test_run_phases_end_to_end_resumable(self):
        from survival import categorization_check as cc
        vecs = {(c, -3): v for c, _, v in ds.random_vectors(32)}
        vecs[("D1", -3)] = ds.random_vectors(32)[0][2]
        with tempfile.TemporaryDirectory() as tmp:
            vp = Path(tmp) / "v.pt"; self.torch.save(vecs, vp)
            with mock.patch.object(cc, "SCREEN_OBJECTS", ds.SCREEN_OBJECTS[:2]), \
                 mock.patch.dict(cc.SETS, {"C": ci.SET_C[:1], "D": ci.SET_D[:1]}), \
                 mock.patch.object(cc, "TARGET", ("D1", -3, 0.2)):
                cal = cc.run(self.model, self.tok, Path(tmp) / "cal", vp, "calibration")
                n_cal = len((cal / "records.jsonl").read_text().splitlines())
                self.assertEqual(n_cal, 2 * (2 + len(ci.TEMPERATURE_GRID) * len(ci.TEMPERATURE_SEEDS)))
                with self.assertRaises(ValueError):
                    cc.run(self.model, self.tok, Path(tmp) / "t", vp, "test", temperature=1.0)
                out = cc.run(self.model, self.tok, Path(tmp) / "t", vp, "test", temperature=0.9)
                rows = [json.loads(x) for x in (out / "records.jsonl").read_text().splitlines()]
                arms12 = 12; seeds = len(ci.TEMPERATURE_SEEDS); forms = 3; cats = 8
                per_obj = (arms12 + seeds) * (1 + cats * forms) + arms12 * cats * forms
                self.assertEqual(len(rows), 2 * per_obj)
                self.assertFalse([r for r in rows if r["arm"] == "temp" and r.get("probe") == "during"])
                self.assertEqual({r["arm"] for r in rows}, {"baseline", "target", "P2", "temp",
                                                             *(f"R{i}" for i in range(9))})
                cc.run(self.model, self.tok, Path(tmp) / "t", vp, "test", temperature=0.9)
                self.assertEqual(len((out / "records.jsonl").read_text().splitlines()), len(rows))

if __name__ == "__main__":
    unittest.main()
