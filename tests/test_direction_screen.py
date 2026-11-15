"""V1.5.1 direction screen: held-out objects, spans, deterministic random null, generated-token pooling."""
import importlib.util
import json
from pathlib import Path
import unittest

from survival import direction_screen as ds

ROOT = Path(__file__).resolve().parents[1]
AVAILABLE = all(importlib.util.find_spec(n) is not None for n in ("torch", "transformers", "safetensors"))


class StaticTests(unittest.TestCase):
    def test_objects_are_held_out(self):
        prompts = json.loads((ROOT / "data/decategorization_prompts.json").read_text())
        used = {p["object"] for p in prompts["build"] + prompts["heldout"]}
        for name in ("survival-dev-tasks", "survival-smoke-tasks", "continuity-dev-tasks", "continuity-smoke-tasks"):
            used |= {json.loads(x)["subject"] for x in (ROOT / "data" / f"{name}.jsonl").read_text().splitlines() if x.strip()}
        names = [n for n, _ in ds.SCREEN_OBJECTS]
        self.assertEqual(len(names), 24)
        self.assertEqual(len(set(names)), 24)
        self.assertFalse(set(names) & used)

    def test_object_set_b_is_held_out_and_disjoint(self):
        prompts = json.loads((ROOT / "data/decategorization_prompts.json").read_text())
        used = {p["object"] for p in prompts["build"] + prompts["heldout"]} | {n for n, _ in ds.SCREEN_OBJECTS}
        for name in ("survival-dev-tasks", "survival-smoke-tasks", "continuity-dev-tasks", "continuity-smoke-tasks"):
            used |= {json.loads(x)["subject"] for x in (ROOT / "data" / f"{name}.jsonl").read_text().splitlines() if x.strip()}
        names = [n for n, _ in ds.SCREEN_OBJECTS_B]
        self.assertEqual(len(set(names)), 24)
        self.assertFalse(set(names) & used)

    def test_saved_vectors_artifact_has_d1_d2_and_randoms(self):
        import importlib.util as u
        if u.find_spec("torch") is None:
            self.skipTest("torch required")
        import torch
        vecs = torch.load(ROOT / "artifacts/screen-vectors-1.5.1.pt", weights_only=False)
        for layer in ds.LAYERS:
            for code in ("D1", "D2") + tuple(f"R{i}" for i in range(9)):
                self.assertAlmostEqual(float(vecs[(code, layer)].norm()), 1.0, places=4)

    def test_probe_span_is_the_object_line(self):
        for kind in ("categories", "description"):
            user, (a, b) = ds.probe_user(kind, "abacus", "a frame of rods")
            self.assertEqual(user[a:b], "abacus: a frame of rods")

    def test_contrast_pairs(self):
        build = json.loads((ROOT / "data/decategorization_prompts.json").read_text())["build"]
        self.assertEqual(len(ds.d1_pairs(build)), len(build))
        objects = {p["object"] for p in build}
        self.assertEqual(len(ds.d2_pairs(build)), len(objects))


    def test_preambles_v153(self):
        self.assertEqual(sorted(ds.PREAMBLES), [f"N{i}" for i in range(9)] + ["P0", "P1", "P2"])
        for code, text in ds.PREAMBLES.items():
            low = text.lower()
            if code.startswith("P"):
                self.assertFalse([w for w in ds.STYLE_WORDS if w in low], code)
            self.assertTrue(18 <= len(text.split()) <= 36, code)

    def test_preamble_span_and_baseline_unchanged(self):
        base, (a, b) = ds.probe_user("description", "abacus", "a frame of rods")
        self.assertTrue(base.startswith("Object: "))
        user, (c, d) = ds.probe_user("description", "abacus", "a frame of rods", ds.PREAMBLES["P0"])
        self.assertTrue(user.startswith(ds.PREAMBLES["P0"] + "\n\nObject: "))
        self.assertEqual(user[c:d], "abacus: a frame of rods")
        self.assertTrue(user.endswith(base))


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
                if return_offsets_mapping:
                    out["offset_mapping"] = [(i, i + 1) for i in range(len(ids))]
                return out
            def decode(self, ids, skip_special_tokens=True): return "".join(chr(97 + int(x) % 26) for x in ids)
        self.tok = Tokenizer()

    def test_random_null_is_deterministic_unit(self):
        a, b = ds.random_vectors(32), ds.random_vectors(32)
        self.assertEqual(len(a), 9)
        for (ca, sa, va), (cb, sb, vb) in zip(a, b):
            self.assertEqual((ca, sa), (cb, sb))
            self.assertTrue(self.torch.equal(va, vb))
            self.assertAlmostEqual(float(va.norm()), 1.0, places=5)

    def test_generated_pool_and_contrast(self):
        text, pooled = ds.generated_pool(self.model, self.tok, "describe a thing", (-3, -2), max_new_tokens=8)
        self.assertTrue(text)
        self.assertEqual(set(pooled), {-3, -2})
        self.assertEqual(tuple(pooled[-3].shape), (32,))
        log = []
        vecs = ds.contrast_generated(self.model, self.tok, [("loose please", "strict please")], (-2,), log)
        self.assertAlmostEqual(float(vecs[-2].norm()), 1.0, places=5)
        self.assertEqual(len(log), 2)

    def test_probe_steers_prefill_only(self):
        v = ds.random_vectors(32)[0][2]
        rec = ds.run_probe(self.model, self.tok, {}, "categories", "abacus", "a frame of rods", v, -3, 0.2)
        self.assertEqual(rec["prefill_positions"], len("abacus: a frame of rods"))
        base = ds.run_probe(self.model, self.tok, {}, "categories", "abacus", "a frame of rods")
        self.assertNotIn("prefill_positions", base)

    def test_generate_mode_steers_every_forward(self):
        v = ds.random_vectors(32)[0][2]
        rec = ds.run_probe(self.model, self.tok, {}, "categories", "abacus", "a frame of rods", v, -3, 0.4,
                           mode="generate")
        self.assertGreaterEqual(rec["steered_forwards"], 1)
        self.assertLessEqual(rec["steered_forwards"], rec["output_tokens"] + 1)
        self.assertNotIn("prefill_positions", rec)
        base = ds.run_probe(self.model, self.tok, {}, "categories", "abacus", "a frame of rods")
        self.assertIsInstance(base["text"], str)

    def test_prompt_mode_is_unsteered(self):
        v = ds.random_vectors(32)[0][2]
        with self.assertRaises(ValueError):
            ds.run_probe(self.model, self.tok, {}, "categories", "abacus", "a frame", v, -3, 0.2, mode="prompt")
        with self.assertRaises(ValueError):
            ds.run_probe(self.model, self.tok, {}, "categories", "abacus", "a frame", mode="unknown")

    def test_run_prompt_writes_all_codes(self):
        import tempfile
        from unittest import mock
        small = (("abacus", "a frame of rods"), ("hammock", "a hung bed"))
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(ds.OBJECT_SETS, {"A": small}):
            ds.run(self.model, self.tok, {}, tmp, [], candidates=("P1",), objects="A", mode="prompt")
            rows = [json.loads(x) for x in (Path(tmp) / "screen.jsonl").read_text().splitlines()]
            codes = {r["direction"] for r in rows}
            self.assertEqual(codes, {"baseline", "P1", *(f"N{i}" for i in range(9))})
            self.assertEqual(len(rows), 11 * 2 * 2)
            self.assertTrue(all(r["mode"] == "prompt" and r["layer"] is None for r in rows))
            ds.run(self.model, self.tok, {}, tmp, [], candidates=("P1",), objects="A", mode="prompt")
            self.assertEqual(len((Path(tmp) / "screen.jsonl").read_text().splitlines()), 44)
        with self.assertRaises(ValueError):
            ds.run(self.model, self.tok, {}, tempfile.mkdtemp(), [], candidates=("N1",), mode="prompt")


if __name__ == "__main__":
    unittest.main()
