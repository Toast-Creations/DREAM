"""V1.4.0 idea survival: prompts, extraction, config bounds, plan, and real-generate runner wiring."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from dream_core.config import load_config
from dream_core.planning import trial_count
from dream_core.schedules import dose
from survival.extract import extract
from survival.prompts import render
from survival.runner import plan_units
from test_core import test_directory
from dream_core import localpaths as LP  # public release: local paths from environment

ROOT = Path(__file__).resolve().parents[1]
AVAILABLE = all(importlib.util.find_spec(n) is not None for n in ("torch", "transformers", "safetensors"))


def write_cfg(directory, name="survival-pilot", mutate=lambda c: None):
    cfg = json.loads((ROOT / "configs" / f"{name}.json").read_text())
    cfg["data_path"] = str(ROOT / "data/survival-dev-tasks.jsonl")
    cfg["output_dir"] = str(Path(directory) / "out")
    mutate(cfg)
    path = Path(directory) / "cfg.json"
    path.write_text(json.dumps(cfg))
    return path


class PromptTests(unittest.TestCase):
    def test_templates_are_verbatim_and_fields_exact(self):
        design = Path(f"{LP.HOME}/notes/idea-survival-design/prompt-templates.md")
        if design.exists():
            text = design.read_text()
            for stage in ("ideation", "development", "final"):
                system, user = render(stage, **{k: "{" + k + "}" for k in
                                                {"ideation": ["task_prompt"], "development": ["task_prompt", "original_ledger"],
                                                 "final": ["task_prompt", "original_ledger", "development_text"]}[stage]})
                self.assertIn(system, text)
                for paragraph in user.split("\n\n"):
                    self.assertIn(paragraph, text)
        with self.assertRaises(KeyError):
            render("development", task_prompt="t")

    def test_braces_in_ledger_are_not_resubstituted(self):
        _, user = render("final", task_prompt="T", original_ledger="I1 {development_text} {x}", development_text="D")
        self.assertIn("I1 {development_text} {x}", user)
        self.assertEqual(user.count("Development text: D"), 1)


class ExtractionTests(unittest.TestCase):
    def test_initial_ledger_offsets_are_verbatim(self):
        text = "Intro.\n**I1.** Clip as hinge.\nWhy.\nI2: Clip stand.\n### I3 - Clip weight\nI4. Tuner\nI5 Brush rest\n"
        rows = extract(text, "initial")
        self.assertEqual([r["label"] for r in rows], ["I1", "I2", "I3", "I4", "I5"])
        for r in rows:
            self.assertEqual(text[r["source_start_offset"]:r["source_end_offset"]], r["verbatim_excerpt"])
        self.assertTrue(rows[0]["verbatim_excerpt"].endswith("Why."))

    def test_missing_slots_stay_missing_and_partial_is_flagged(self):
        rows = extract("I1 one\nI2 two\nI3 thr", "initial", finish_reason="length")
        self.assertEqual([r["extraction_status"] for r in rows], ["complete", "complete", "partial", "missing", "missing"])
        self.assertFalse(rows[3]["delivered"])

    def test_numbered_fallback_unstructured_and_empty(self):
        self.assertEqual(extract("1. a\n2. b", "initial")[0]["extraction_method"], "numbered_list")
        un = extract("Just prose with no list.", "initial")
        self.assertEqual(un[0]["extraction_status"], "unstructured")
        self.assertEqual(sum(r["delivered"] for r in un), 1)
        self.assertEqual(sum(r["delivered"] for r in extract("", "initial")), 0)

    def test_nested_lists_do_not_split_ideas(self):
        rows = extract("1. Idea one (I1)\n   1. step\n   2. step\n2. Idea two (I2, I3; merger)\n", "final")
        self.assertEqual(sum(r["delivered"] for r in rows), 2)
        self.assertEqual(rows[1]["source_seed_ids"], ["I2", "I3"])

    def test_new_idea_note_is_split_and_unsourced(self):
        rows = extract("1. From I1: kept.\n2. From I4.\nNew idea: a sourceless thought.", "final")
        notes = [r for r in rows if r["stage"] == "final_new_idea"]
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["source_seed_ids"], [])
        self.assertNotIn("sourceless", rows[1]["verbatim_excerpt"])
        self.assertEqual(len([r for r in rows if r["stage"] == "final"]), 5)

    # V1.4.2 final-stage rules R1-R4 (replicas of the formats seen in ten Mistral pilot finals).
    def _verbatim(self, text, rows):
        for r in rows:
            if r["delivered"]:
                self.assertEqual(text[r["source_start_offset"]:r["source_end_offset"]], r["verbatim_excerpt"])

    def test_r1_digit_space_paren_headers_and_r3_numbered_new_idea(self):
        text = ("1 (Faithful Development from I1)\nA clip.\n\n2 (Faithful Development from I2)\nA hook.\n\n"
                "3 (Reinterpretation from I3)\nA stand.\n\n4 (Faithful Development from I4)\nA tray.\n\n"
                "5 (New Idea)\nA lamp.")
        rows = extract(text, "final")
        finals = [r for r in rows if r["stage"] == "final"]
        self.assertEqual([r["delivered"] for r in finals], [True, True, True, True, False])
        self.assertEqual(finals[2]["source_seed_ids"], ["I3"])
        notes = [r for r in rows if r["stage"] == "final_new_idea"]
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["source_seed_ids"], [])
        self.assertIn("A lamp", notes[0]["verbatim_excerpt"])
        self._verbatim(text, rows)

    def test_r3_header_citing_a_source_stays_sourced(self):
        rows = extract("1. Kept (I1)\n2. Labyrinth Map (New Idea - Merger of I1 and I2)\nBody.\n"
                       "3. **Water Wall (New idea derived from I3)**\nBody.\n4. (New Idea) Lone thought\n", "final")
        finals = [r for r in rows if r["stage"] == "final" and r["delivered"]]
        self.assertEqual(len(finals), 3)
        self.assertEqual(finals[1]["source_seed_ids"], ["I1", "I2"])
        self.assertEqual(len([r for r in rows if r["stage"] == "final_new_idea"]), 1)

    def test_r1_bold_after_digit(self):
        rows = extract("1 **Clip** from I1.\n2 **Hook** from I2.\n", "final")
        self.assertEqual(sum(r["delivered"] for r in rows if r["stage"] == "final"), 2)

    def test_r2_i_label_headers_and_r4_excess(self):
        text = "".join(f"I{n}. **Item {n}** (Faithful Development, Original Idea I{n})\nBody {n}.\n" for n in range(1, 6))
        text += "I6. **Extra** (New Idea)\nNote body.\n"
        rows = extract(text, "final")
        finals = [r for r in rows if r["stage"] == "final"]
        self.assertTrue(all(r["delivered"] for r in finals))
        self.assertEqual(finals[0]["label"], "I1")
        self.assertEqual(finals[4]["source_seed_ids"], ["I5"])
        self.assertEqual(rows[0]["extraction_method"], "i_label_headers")
        self.assertEqual(len([r for r in rows if r["stage"] == "final_new_idea"]), 1)
        self._verbatim(text, rows)
        more = "".join(f"{n}. Kept idea {n} from I1.\n" for n in range(1, 8))
        rows = extract(more, "final")
        self.assertEqual(len([r for r in rows if r["stage"] == "final_excess"]), 2)
        self.assertNotIn("idea 6", [r for r in rows if r["stage"] == "final"][4]["verbatim_excerpt"])

    def test_v2_rules_leave_initial_stage_and_prose_unchanged(self):
        self.assertEqual(extract("I1 one\nI2 two", "initial")[0]["label"], "I1")
        prose = extract("I think the best plan keeps I1 and I2 together.", "final")
        self.assertEqual(prose[0]["extraction_status"], "unstructured")
        nested = extract("1. Idea (I1)\n   2 (sub-step)\n2. Other (I2)\n", "final")
        self.assertEqual(sum(r["delivered"] for r in nested if r["stage"] == "final"), 2)

    def test_partial_flag_marks_last_written_member(self):
        rows = extract("1 (from I1)\nA.\n2 (New idea)\nB cut", "final", finish_reason="length")
        self.assertEqual([r for r in rows if r["stage"] == "final_new_idea"][0]["extraction_status"], "partial")
        self.assertEqual(rows[0]["extraction_status"], "complete")


class ConfigAndPlanTests(unittest.TestCase):
    def test_pilot_plan_is_72_balanced_units(self):
        with test_directory() as d:
            cfg = load_config(write_cfg(d))
            self.assertEqual(trial_count(cfg, 6), 72)
            units = plan_units(cfg, [{"id": f"t{i}"} for i in range(6)])
        self.assertEqual(len(units), 72)
        blocks = {}
        for u in units:
            blocks.setdefault((u["task_id"], u["seed"]), []).append(u["arm"])
        self.assertTrue(all(sorted(a) == sorted(cfg["survival"]["arms"]) for a in blocks.values()))
        self.assertGreater(len({tuple(a) for a in blocks.values()}), 1)  # order really varies by block
        rand = [u for u in units if u["arm"] == "random"]
        self.assertTrue(all(u["random_vector_index"] == (3 * u["task_index"] + u["seed_index"]) % 9 for u in rand))
        counts = [sum(u["random_vector_index"] == i for u in rand) for i in range(9)]
        self.assertEqual(counts, [2] * 9)

    def test_plan_is_deterministic(self):
        with test_directory() as d:
            cfg = load_config(write_cfg(d))
            rows = [{"id": f"t{i}"} for i in range(6)]
            self.assertEqual(plan_units(cfg, rows), plan_units(copy.deepcopy(cfg), rows))

    def test_rejections(self):
        bad = [lambda c: c["model"].update(enable_thinking=True),
               lambda c: c["survival"].update(arms=["strong_prompt", "nope"]),
               lambda c: c["survival"].update(arms=["targeted", "targeted"]),
               lambda c: c["steering"]["schedule"].update(shape="constant"),
               lambda c: c["steering"].pop("random_set_dir"),
               lambda c: c["limits"]["stage_input_tokens"].pop("final"),
               lambda c: c["steering"].update(peak_strength=0.5),
               lambda c: c["survival"].update(workflow="other"),
               lambda c: c["limits"].update(external_retries=2)]
        for mutate in bad:
            with test_directory() as d, self.assertRaises((ValueError, KeyError)):
                load_config(write_cfg(d, mutate=mutate))

    def test_token_clock_dose(self):
        with test_directory() as d:
            spec = load_config(write_cfg(d))["steering"]["schedule"]
        self.assertEqual(dose(0, spec), 0.0)
        self.assertAlmostEqual(dose(25, spec), 0.5)
        self.assertEqual(dose(50, spec), 1.0)
        self.assertEqual(dose(149, spec), 1.0)
        self.assertAlmostEqual(dose(250, spec), 0.5)
        self.assertEqual(dose(350, spec), 0.0)
        self.assertEqual(dose(3000, spec), 0.0)
        # Planned exposure: the +0.20 curve sums to 45 over its 350 steps (test plan), i.e. 225 per unit peak.
        self.assertAlmostEqual(sum(dose(t, spec) for t in range(400)), 225.0, places=6)


@unittest.skipUnless(AVAILABLE, "PyTorch/Transformers required")
class RunnerIntegrationTests(unittest.TestCase):
    def setUp(self):
        import torch
        from transformers import Qwen2Config, Qwen2ForCausalLM
        self.torch = torch
        torch.manual_seed(5)
        self.model = Qwen2ForCausalLM(Qwen2Config(vocab_size=64, hidden_size=32, intermediate_size=64,
            num_hidden_layers=2, num_attention_heads=4, num_key_value_heads=2, max_position_embeddings=1024,
            attention_dropout=0.0, bos_token_id=1, eos_token_id=2, pad_token_id=0))
        for p in self.model.parameters():
            p.requires_grad_(False)
        self.model.eval()

        class Tokenizer:
            eos_token_id = 2; pad_token_id = 0; chat_template = "test"
            def __init__(self): self.dream_chat_kwargs = {"enable_thinking": False}
            def apply_chat_template(self, messages, **kw): return " ".join(m["content"] for m in messages)
            def __call__(self, text, return_tensors=None, add_special_tokens=False):
                ids = torch.tensor([[3 + (b % 60) for b in text.encode()][-24:]])
                return {"input_ids": ids, "attention_mask": torch.ones_like(ids)}
            def decode(self, ids, skip_special_tokens=True): return " ".join(str(int(x)) for x in ids)
        self.tok = Tokenizer()

    def make(self, d, mutate=lambda c: None):
        import torch
        from dream_core.ledger import atomic_json, file_hash
        d = Path(d)
        manifest = d / "manifest.json"; manifest.write_text('{"model_id":"tiny"}')
        (d / "rs").mkdir()
        def vec(seed):
            v = torch.randn(32, generator=torch.Generator().manual_seed(seed)); return (v / v.norm()).tolist()
        atomic_json(d / "target.json", {"model_manifest_sha256": file_hash(manifest), "layer": 1,
                                        "kind": "decategorization", "vector": vec(1)})
        for i in range(9):
            atomic_json(d / "rs" / f"random-direction-{i:02d}.json", {"model_manifest_sha256": file_hash(manifest),
                        "layer": 1, "kind": "random", "vector": vec(100 + i)})
        rows = [{"id": "t1", "split": "development", "prompt": "Uses for a clip."},
                {"id": "t2", "split": "development", "prompt": "A map that changes."}]
        (d / "tasks.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
        def m(c):
            c["model"].update(path=str(d), manifest=str(manifest))
            c["data_path"] = str(d / "tasks.jsonl"); c["seeds"] = [11]
            c["steering"].update(layer_index=-1, vector_path=str(d / "target.json"), random_set_dir=str(d / "rs"),
                                 schedule={"shape": "smooth", "onset_tokens": 2, "plateau_tokens": 2, "comedown_tokens": 2})
            c["limits"].update(max_new_tokens=64, max_trials=8, max_worlds=2)
            c["limits"].pop("loop_guard")
            mutate(c)
        return load_config(write_cfg(d, mutate=m))

    def test_chains_hooks_zero_dose_and_resume(self):
        from survival.runner import run
        with test_directory() as d:
            cfg = self.make(d)
            out = run(self.model, self.tok, cfg)
            units = {p.stem: json.loads(p.read_text()) for p in (out / "units").glob("*.json")}
            self.assertEqual(len(units), 8)
            for u in units.values():
                self.assertEqual([c["stage"] for c in u["calls"]], ["ideation", "development", "final"])
                for c in u["calls"][1:]:
                    self.assertIsNone(c["steering"])           # development is never steered
                    self.assertNotIn("steering_trace", c)
                    self.assertEqual(c["temperature"], 0.6)
                first = u["calls"][0]
                if u["arm"] in ("targeted", "random"):
                    self.assertEqual(len(first["steering_trace"]), first["output"]["output_tokens"])
                    self.assertEqual(len(first["norm_trace"]), len(first["steering_trace"]))
                    self.assertEqual(first["steering_trace"][0], 0.0)
                self.assertEqual(first["temperature"], 1.3 if u["arm"] == "high_temperature" else 0.6)
                # Development/final prompts depend only on the ledger: identical seeds across arms.
                self.assertEqual(u["calls"][1]["seed"], 100011)
                self.assertIn(u["original_ledger"], u["calls"][1]["user"])
            self.assertEqual(units["t1__s11__random"]["random_vector_index"], 0)
            self.assertEqual(units["t2__s11__random"]["random_vector_index"], 3)
            # Resume: a deleted unit is regenerated identically; nothing else is rerun.
            victim = out / "units/t1__s11__strong_prompt.json"
            before = json.loads(victim.read_text()); victim.unlink()
            stamp = (out / "units/t2__s11__targeted.json").stat().st_mtime_ns
            run(self.model, self.tok, cfg)
            after = json.loads(victim.read_text())
            self.assertEqual(before["calls"][0]["output"]["raw_text"], after["calls"][0]["output"]["raw_text"])
            self.assertEqual(stamp, (out / "units/t2__s11__targeted.json").stat().st_mtime_ns)
            # A changed config cannot resume into the same directory.
            changed = copy.deepcopy(cfg); changed["generation"]["temperature"] = 0.7
            with self.assertRaises(RuntimeError):
                run(self.model, self.tok, changed)
            self.assertEqual(self.tok.dream_chat_kwargs, {"enable_thinking": False})

    def test_zero_dose_targeted_equals_strong_prompt(self):
        from survival.runner import run
        with test_directory() as d:
            cfg = self.make(d, lambda c: c["steering"].update(peak_strength=0.0))
            out = run(self.model, self.tok, cfg)
            a = json.loads((out / "units/t1__s11__strong_prompt.json").read_text())
            c = json.loads((out / "units/t1__s11__targeted.json").read_text())
            for i in range(3):
                self.assertEqual(a["calls"][i]["output"]["raw_text"], c["calls"][i]["output"]["raw_text"])
            self.assertTrue(all(x == 0.0 for x in c["calls"][0]["steering_trace"]))

    def test_retry_rule(self):
        from dream_core import modeling
        from survival.runner import _call
        with test_directory() as d:
            cfg = self.make(d)
            real = modeling.generate
            calls = {"n": 0}
            def flaky(*a, **k):
                calls["n"] += 1
                if calls["n"] == 1:
                    raise RuntimeError("CUDA hiccup")
                return real(*a, **k)
            with patch.object(modeling, "generate", flaky):
                rec = _call(self.model, self.tok, cfg, "ideation", "s", "u", 1, 0.6, "ideation")
            self.assertEqual(rec["status"], "completed"); self.assertEqual(len(rec["attempts"]), 2)
            with patch.object(modeling, "generate", side_effect=RuntimeError("down")):
                rec = _call(self.model, self.tok, cfg, "ideation", "s", "u", 1, 0.6, "ideation")
            self.assertEqual(rec["status"], "external_failure"); self.assertEqual(len(rec["attempts"]), 2)
            with patch.object(modeling, "generate", side_effect=ValueError("Prompt exceeds token budget")):
                rec = _call(self.model, self.tok, cfg, "ideation", "s", "u", 1, 0.6, "ideation")
            self.assertEqual(rec["status"], "input_budget_exceeded"); self.assertEqual(len(rec["attempts"]), 1)
            # V1.4.1: any other ValueError is a fault, never a recorded budget outcome.
            with patch.object(modeling, "generate", side_effect=ValueError("model_kwargs not used: token_type_ids")):
                with self.assertRaises(ValueError):
                    _call(self.model, self.tok, cfg, "ideation", "s", "u", 1, 0.6, "ideation")

    def test_generate_ignores_token_type_ids(self):
        from dream_core.modeling import generate
        torch = self.torch
        base = self.tok
        class WithTypes(type(base)):
            def __call__(self, text, return_tensors=None, add_special_tokens=False):
                out = super().__call__(text, return_tensors, add_special_tokens)
                out["token_type_ids"] = torch.zeros_like(out["input_ids"]); return out
        a = generate(self.model, base, "pump", max_new_tokens=6, temperature=0.6, top_p=0.95, top_k=20, seed=3)
        b = generate(self.model, WithTypes(), "pump", max_new_tokens=6, temperature=0.6, top_p=0.95, top_k=20, seed=3)
        self.assertEqual(a["raw_text"], b["raw_text"])

    def test_devqual_branches_share_finalizer_and_budget(self):
        from survival.runner import run
        with test_directory() as d:
            src = Path(d) / "src.jsonl"
            src.write_text(json.dumps({"id": "kidney__baseline", "split": "development", "prompt": "Explore kidney.",
                                       "original_ledger": "I1 filter {odd braces}"}) + "\n")
            cfg = self.make(d, lambda c: (c.update(survival={"mode": "devqual", "branches": ["develop", "review"],
                                                              "order_seed": 1}, data_path=str(src))))
            out = run(self.model, self.tok, cfg)
            dev = json.loads((out / "units/kidney__baseline__develop.json").read_text())
            rev = json.loads((out / "units/kidney__baseline__review.json").read_text())
            self.assertEqual([c["stage"] for c in dev["calls"]], ["development", "final"])
            self.assertEqual([c["stage"] for c in rev["calls"]], ["review", "final"])
            self.assertEqual(dev["calls"][1]["system"], rev["calls"][1]["system"])
            self.assertEqual(dev["calls"][0]["max_new_tokens"], rev["calls"][0]["max_new_tokens"])
            self.assertIn("I1 filter {odd braces}", rev["calls"][0]["user"])


if __name__ == "__main__":
    unittest.main()
