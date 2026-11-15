"""Regressions for the scientific comparison, parser and qualification boundary."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from dream.concepts import conditions, parse_associations, run
from dream_core.config import load_config
from dream_core.ledger import release_source_hash
from dream_core.modeling import split_thinking
from dream_core.planning import trial_count
from dream2.worlds import generate_worlds, validate_worlds
from test_core import test_directory

ROOT = Path(__file__).resolve().parents[1]


def answer():
    return {"associations": [{"item": f"Example {i}", "connection": "A specific relationship."} for i in range(5)]}


class ConceptTests(unittest.TestCase):
    def test_exact_five_and_no_substring_or_extra_key_credit(self):
        self.assertTrue(parse_associations(json.dumps(answer()))["valid"])
        for n in (0, 4, 6):
            obj = answer(); obj["associations"] = (obj["associations"] * 2)[:n]
            self.assertFalse(parse_associations(json.dumps(obj))["valid"])
        self.assertFalse(parse_associations('Commentary ' + json.dumps(answer()))["valid"])
        obj = answer(); obj["explanation"] = "extra"
        self.assertFalse(parse_associations(json.dumps(obj))["valid"])

    def test_duplicate_and_empty_associations_fail(self):
        for replacement in ("Example 0", "EXAMPLE 0", "Ｅｘａｍｐｌｅ ０"):
            obj = answer(); obj["associations"][1]["item"] = replacement
            self.assertFalse(parse_associations(json.dumps(obj))["valid"])
        obj = answer(); obj["associations"][1]["connection"] = " "
        self.assertFalse(parse_associations(json.dumps(obj))["valid"])
        self.assertFalse(parse_associations('{"associations":[],"associations":[]}')["valid"])

    def test_modes_are_paired_and_secondary_conditions_are_separate(self):
        cfg = load_config(ROOT / "configs/concepts-pilot.json")
        cells = conditions(cfg)
        self.assertEqual(len(cells), 2)
        self.assertEqual({c["reasoning_enabled"] for c in cells}, {True, False})
        self.assertEqual({c["lambda"] for c in cells}, {0})
        self.assertEqual(len({c["temperature"] for c in cells}), 1)
        cfg["steering"]["lambda_values"] = [0, .05]
        cfg["association"]["include_temperature_control"] = True
        self.assertEqual(trial_count(cfg, 6), len(conditions(cfg)) * 6 * len(cfg["seeds"]))

    def test_direct_json_requires_eos_and_preserves_format_deviation(self):
        text = json.dumps(answer())
        self.assertTrue(split_thinking(text, True)["thinking_truncated"])
        recovered = split_thinking(text, True, ended_with_eos=True)
        self.assertEqual(recovered["text"], text)
        self.assertEqual(recovered["format_deviation"], "direct_json_without_thinking_block")
        for text in ("I should think", '<think>{"answer":43}', '{"answer":1,"answer":2}'):
            self.assertTrue(split_thinking(text, True, ended_with_eos=True)["thinking_truncated"])

    def test_numeric_probes_are_unique_and_defeat_copy_and_sign_flip(self):
        for world in validate_worlds(generate_worlds(100, 1101)):
            probes = [x for x in world["eval"] if x["category"] == "composition"]
            self.assertEqual(len({x["question"] for x in probes}), 4)
            for x in probes:
                self.assertNotIn(x["answer"], (x["oracle"]["start"], -x["oracle"]["start"]))
        world = generate_worlds(1)[0]; world["eval"].append(deepcopy(world["eval"][6]))
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            validate_worlds([world])

    def test_plan_only_rejects_world_cap_before_model_loading(self):
        cfg = json.loads((ROOT / "configs/concepts-pilot.json").read_text())
        cfg["limits"]["max_worlds"] = 1
        cfg["data_path"] = str(ROOT / "data/concepts-development.jsonl")
        with test_directory() as directory:
            path = Path(directory) / "bad-plan.json"; path.write_text(json.dumps(cfg))
            result = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/run_experiment.py"),
                                     "--config", str(path), "--plan-only"], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("world/task budget", result.stderr)

    def test_source_evidence_covers_launchers(self):
        with test_directory() as directory:
            root = Path(directory)
            for name in ("src", "tests", "scripts"):
                (root / name).mkdir()
            path = root / "scripts/launcher.py"; path.write_text("x=1")
            before = release_source_hash(root); path.write_text("x=2")
            self.assertNotEqual(before, release_source_hash(root))

    def test_runner_pairs_prompts_and_preserves_invalid_output_before_stopping(self):
        with test_directory() as directory:
            root = Path(directory); data = root / "concepts.jsonl"
            data.write_text(json.dumps({"id":"dev-one", "split":"development", "concept":"feedback", "definition":"Output affects later input."}) + "\n")
            manifest = root / "manifest.json"; manifest.write_text("{}")
            cfg = load_config(ROOT / "configs/concepts-smoke.json")
            cfg.update(data_path=str(data), output_dir=str(root / "good"))
            cfg["model"]["manifest"] = str(manifest)
            tok = SimpleNamespace(); calls = []
            def generate(*args, **kwargs):
                calls.append((args[2], dict(tok.dream_chat_kwargs), kwargs))
                return {"text":json.dumps(answer()), "finish_reason":"eos", "input_tokens":20, "output_tokens":100}
            steering = SimpleNamespace(MaskedSteerer=None, assert_no_dream_hooks=lambda m:None, load_vector=None)
            with patch.dict(sys.modules, {"dream_core.steering": steering}), patch("dream_core.modeling.generate", generate):
                path = run(SimpleNamespace(parameters=lambda: iter(())), tok, cfg)
            self.assertEqual(len(list(path.glob("trial-*.json"))), 2)
            self.assertEqual(calls[0][0], calls[1][0])
            self.assertEqual(calls[0][2], calls[1][2])
            self.assertNotEqual(calls[0][1], calls[1][1])
            self.assertFalse(hasattr(tok, "dream_chat_kwargs"))
            cfg["output_dir"] = str(root / "bad")
            bad = {"text":"", "thinking":"unfinished", "finish_reason":"length", "input_tokens":20, "output_tokens":4096}
            with patch.dict(sys.modules, {"dream_core.steering": steering}), patch("dream_core.modeling.generate", return_value=bad):
                with self.assertRaisesRegex(RuntimeError, "preserved"):
                    run(SimpleNamespace(parameters=lambda: iter(())), tok, cfg)
            path = next((root / "bad").iterdir())
            self.assertEqual(len(list(path.glob("trial-*.json"))), 1)
            self.assertFalse(json.loads((path / "trial-000000.json").read_text())["completed_five_item_answer"])


if __name__ == "__main__":
    unittest.main()
