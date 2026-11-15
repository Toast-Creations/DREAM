"""V1.5.0 continuity: prefill-span steering, one continuous context, section views, config bounds."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

from dream_core.config import load_config
from survival.prompts import CONTINUITY_USER, render_continuity
from survival.runner import plan_units, load_rows, section_views
from test_core import test_directory

ROOT = Path(__file__).resolve().parents[1]
AVAILABLE = all(importlib.util.find_spec(n) is not None for n in ("torch", "transformers", "safetensors"))


def write_cfg(directory, name="continuity-pilot", mutate=lambda c: None):
    cfg = json.loads((ROOT / "configs" / f"{name}.json").read_text())
    cfg["data_path"] = str(ROOT / "data/continuity-dev-tasks.jsonl")
    cfg["output_dir"] = str(Path(directory) / "out")
    mutate(cfg)
    path = Path(directory) / "cfg.json"
    path.write_text(json.dumps(cfg))
    return path


class PromptAndSectionTests(unittest.TestCase):
    def test_span_locates_task_text_exactly(self):
        system, user, (a, b) = render_continuity("Uses for a {clip}.")
        self.assertEqual(user[a:b], "Uses for a {clip}.")
        self.assertTrue(user.startswith("Task: "))
        self.assertEqual(user.count("Uses for a {clip}."), 1)
        _, probe, (c, d) = render_continuity("A map.", probe=True)
        self.assertEqual(probe[c:d], "A map.")

    def test_sections_are_verbatim_slices_in_order(self):
        text = "IDEAS\nI1. a\n\nTHINKING\nt\n**DEVELOPMENT**\nd\n## FINAL:\n1. x (I1)"
        views = section_views(text, "length")
        self.assertEqual(list(views), ["IDEAS", "THINKING", "DEVELOPMENT", "FINAL"])
        for v in views.values():
            a, b = v["char_span"]
            self.assertEqual(text[a:b].strip("\n"), v["text"])
        self.assertEqual(views["FINAL"]["finish_reason"], "length")
        self.assertEqual(views["IDEAS"]["finish_reason"], "eos")

    def test_missing_or_inline_headers_are_not_invented(self):
        self.assertEqual(section_views("I1. no headers", "eos"), {})
        views = section_views("IDEAS: I1 inline\nTHINKING\nt", "eos")
        self.assertEqual(list(views), ["THINKING"])   # an inline header is not a header line

    def test_task_line_is_the_only_templated_field(self):
        self.assertEqual(CONTINUITY_USER.count("{"), 1)


class ConfigTests(unittest.TestCase):
    def test_pilot_plan_is_90_balanced_units_with_shared_random_index(self):
        with test_directory() as d:
            cfg = load_config(write_cfg(d))
        units = plan_units(cfg, load_rows(cfg["data_path"], "development"))
        self.assertEqual(len(units), 90)
        by_block = {}
        for u in units:
            by_block.setdefault((u["task_id"], u["seed"]), []).append(u)
        for block in by_block.values():
            self.assertEqual(sorted(u["arm"] for u in block), sorted(cfg["survival"]["arms"]))
            idx = {u.get("random_vector_index") for u in block if u["arm"].endswith("random")}
            self.assertEqual(len(idx), 1)   # both random arms in a block use the same direction

    def test_rejections(self):
        bad = [
            lambda c: c.update(version="1.4.0"),
            lambda c: c["survival"].update(arms=["baseline", "targeted"]),
            lambda c: c["steering"]["perceive"]["schedule"].update(end_fraction=0.1),
            lambda c: c["steering"]["perceive"].update(prefill_strength=0.5),
            lambda c: c["steering"]["generate"].update(schedule={"shape": "constant"}),
            lambda c: c["limits"].update(stage_input_tokens={"ideation": 10}),
            lambda c: c["survival"].update(category_probe="yes"),
        ]
        for mutate in bad:
            with test_directory() as d:
                with self.assertRaises((ValueError, KeyError)):
                    load_config(write_cfg(d, mutate=mutate))

    def test_survival_14_configs_still_load(self):
        for name in ("survival-pilot", "survival-smoke", "survival-devqual"):
            cfg = json.loads((ROOT / "configs" / f"{name}.json").read_text())
            self.assertEqual(cfg["version"], "1.4.0")


@unittest.skipUnless(AVAILABLE, "PyTorch/Transformers required")
class SteeringIntegrationTests(unittest.TestCase):
    def setUp(self):
        import torch
        from transformers import Qwen2Config, Qwen2ForCausalLM
        self.torch = torch
        torch.manual_seed(7)
        self.model = Qwen2ForCausalLM(Qwen2Config(vocab_size=64, hidden_size=32, intermediate_size=64,
            num_hidden_layers=2, num_attention_heads=4, num_key_value_heads=2, max_position_embeddings=4096,
            attention_dropout=0.0, bos_token_id=1, eos_token_id=2, pad_token_id=0))
        for p in self.model.parameters():
            p.requires_grad_(False)
        self.model.eval()

        class Tokenizer:
            """Byte-level tokenizer with offsets, no truncation."""
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
            def decode(self, ids, skip_special_tokens=True): return " ".join(str(int(x)) for x in ids)
        self.tok = Tokenizer()

    def vec(self, seed):
        v = self.torch.randn(32, generator=self.torch.Generator().manual_seed(seed))
        return (v / v.norm()).tolist()

    def logits_after(self, prefill_strength, positions, layer=0):
        """Next-token logits for a short prompt, with the prompt span steered at prefill and decode dose 0.

        Layer 0 of 2: its output feeds the next block's keys/values, which is what the cache carries. Steering
        the final block cannot reach any cache (DREAM uses block -8, leaving later blocks to carry it).
        """
        from dream_core.steering import MaskedSteerer
        ids = self.torch.tensor([[5, 9, 11, 13, 17, 19, 23, 29]])
        with MaskedSteerer(self.model, layer, self.vec(1), 0.0, generation=True, prefill_positions=positions,
                           prefill_strength=prefill_strength, prompt_tokens=8) as s:
            out = self.model(input_ids=ids, use_cache=True)
            nxt = self.model(input_ids=self.torch.tensor([[31]]), past_key_values=out.past_key_values, use_cache=True)
        return out.logits[0, -1], nxt.logits[0, -1], s

    def test_zero_prefill_equals_unsteered_and_trace_recorded(self):
        base_last, base_next = self.model(input_ids=self.torch.tensor([[5, 9, 11, 13, 17, 19, 23, 29]])).logits[0, -1], None
        last, _, s = self.logits_after(0.0, [1, 2, 3])
        self.assertTrue(self.torch.equal(last, base_last))
        self.assertEqual(s.trace, [0.0, 0.0])
        self.assertEqual(s.prefill_trace, {"positions": [1, 2, 3], "strength": 0.0})

    def test_steered_encoding_persists_in_cache_after_dose_returns_to_zero(self):
        _, unsteered_next, _ = self.logits_after(0.0, [1, 2, 3])
        _, steered_next, s = self.logits_after(0.3, [1, 2, 3])
        # The decode step itself is unsteered (trace 0) yet differs, because it attends to steered keys/values.
        self.assertEqual(s.trace, [0.3, 0.0])
        self.assertFalse(self.torch.allclose(unsteered_next, steered_next))

    def test_only_span_positions_are_perturbed(self):
        from dream_core.steering import MaskedSteerer, blocks
        seen = {}
        ids = self.torch.tensor([[5, 9, 11, 13, 17, 19, 23, 29]])
        handle = blocks(self.model)[1].register_forward_hook(lambda m, i, o: seen.setdefault("h", o[0] if isinstance(o, tuple) else o))
        try:
            self.model(input_ids=ids)
        finally:
            handle.remove()
        clean = seen.pop("h").clone()
        captured = {}
        with MaskedSteerer(self.model, -1, self.vec(1), 0.0, generation=True, prefill_positions=[2, 4],
                           prefill_strength=0.5, prompt_tokens=8):
            handle = blocks(self.model)[1].register_forward_hook(lambda m, i, o: captured.setdefault("h", o[0] if isinstance(o, tuple) else o))
            try:
                self.model(input_ids=ids)
            finally:
                handle.remove()
        changed = [(captured["h"][0, t] - clean[0, t]).abs().max().item() > 1e-6 for t in range(8)]
        self.assertEqual(changed, [False, False, True, False, True, False, False, False])

    def test_prefill_shape_mismatch_and_bad_positions_refused(self):
        from dream_core.steering import MaskedSteerer
        with self.assertRaises(ValueError):
            MaskedSteerer(self.model, -1, self.vec(1), 0.0, generation=True, prefill_positions=[9],
                          prefill_strength=0.2, prompt_tokens=8)
        with self.assertRaises(ValueError):
            MaskedSteerer(self.model, -1, self.vec(1), 0.0, mask=[[True]], prefill_positions=[1],
                          prefill_strength=0.2, prompt_tokens=8)
        with self.assertRaises(RuntimeError):
            with MaskedSteerer(self.model, -1, self.vec(1), 0.0, generation=True, prefill_positions=[1],
                               prefill_strength=0.2, prompt_tokens=9):
                self.model(input_ids=self.torch.tensor([[5, 9, 11, 13, 17, 19, 23, 29]]))

    def test_default_policy_unchanged(self):
        """prefill_positions=None reproduces the 1.4.x final-position policy exactly."""
        from dream_core.steering import MaskedSteerer
        spec = {"shape": "smooth", "onset_tokens": 2, "plateau_tokens": 2, "comedown_tokens": 2}
        ids = self.torch.tensor([[5, 9, 11, 13]])
        outs = []
        for kw in ({}, {"prefill_positions": None}):
            with MaskedSteerer(self.model, -1, self.vec(1), 0.3, generation=True, schedule_spec=spec, **kw) as s:
                outs.append((self.model(input_ids=ids).logits.clone(), list(s.trace)))
        self.assertTrue(self.torch.equal(outs[0][0], outs[1][0]))
        self.assertEqual(outs[0][1], outs[1][1])

    def make(self, d, mutate=lambda c: None):
        from dream_core.ledger import atomic_json, file_hash
        d = Path(d)
        manifest = d / "manifest.json"; manifest.write_text('{"model_id":"tiny"}')
        (d / "rs").mkdir()
        atomic_json(d / "target.json", {"model_manifest_sha256": file_hash(manifest), "layer": 1,
                                        "kind": "decategorization", "vector": self.vec(1)})
        for i in range(9):
            atomic_json(d / "rs" / f"random-direction-{i:02d}.json", {"model_manifest_sha256": file_hash(manifest),
                        "layer": 1, "kind": "random", "vector": self.vec(100 + i)})
        rows = [{"id": "t1", "split": "development", "prompt": "Uses for a clip."}]
        (d / "tasks.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")

        def m(c):
            c["model"].update(path=str(d), manifest=str(manifest))
            c["data_path"] = str(d / "tasks.jsonl"); c["seeds"] = [11]
            c["steering"].update(layer_index=-1, vector_path=str(d / "target.json"), random_set_dir=str(d / "rs"))
            c["steering"]["perceive"]["schedule"]["glide_tokens"] = 4
            c["steering"]["generate"]["schedule"] = {"shape": "smooth", "onset_tokens": 2, "plateau_tokens": 2,
                                                     "comedown_tokens": 2}
            c["limits"].update(max_new_tokens=64, max_trials=5, max_worlds=1)
            c["limits"].pop("loop_guard")
            mutate(c)
        return load_config(write_cfg(d, mutate=m))

    def test_runner_end_to_end(self):
        from survival.runner import run
        with test_directory() as d:
            cfg = self.make(d)
            out = run(self.model, self.tok, cfg)
            units = {p.stem: json.loads(p.read_text()) for p in (out / "units").glob("*.json")}
            self.assertEqual(len(units), 5)
            for name, u in units.items():
                call = u["continuous_call"]
                self.assertEqual([c["stage"] for c in u["calls"]], ["ideation", "thinking", "development", "final"])
                # Random tokens from a tiny model produce no section headers: views stay missing, never invented.
                self.assertTrue(all(c["status"] == "missing_section" for c in u["calls"]))
                self.assertEqual(u["status"], "missing_sections")
                if u["arm"] == "baseline":
                    self.assertIsNone(call["steering"])
                elif u["arm"].startswith("perceive"):
                    self.assertEqual(call["steering_trace"][0], 0.2)
                    self.assertEqual(call["steering_trace"][-1], 0.0)
                    pos = call["prefill_trace"]["positions"]
                    self.assertEqual(call["steering"]["prefill_covered_text"], "Uses for a clip.")
                    self.assertEqual(len(pos), len("Uses for a clip."))
                else:
                    self.assertEqual(call["steering_trace"][0], 0.0)
                    self.assertNotIn("prefill_trace", call)
                if u["arm"] in ("baseline", "perceive_targeted", "perceive_random"):
                    probe = u["category_probe"]
                    self.assertEqual(probe["status"], "completed")
                    if u["arm"] != "baseline":
                        self.assertEqual(probe["prefill_trace"]["strength"], 0.2)
                else:
                    self.assertNotIn("category_probe", u)
            self.assertEqual(units["t1__s11__perceive_random"]["random_vector_index"],
                             units["t1__s11__generate_random"]["random_vector_index"])


if __name__ == "__main__":
    unittest.main()
