"""V1.3.3: step sampling, extra steering arms, concept worlds and text targets (document 19)."""
import importlib.util
from copy import deepcopy
import json
from pathlib import Path
import unittest
from dream_core.config import load_config
from dream_core.modeling import render_chat
from dream_core.planning import trial_count
from dream.protocol import anchor_sampling, plan, step_sampling
from dream2.concept_worlds import EVAL_CATEGORIES, load_concept_worlds, validate_concept_worlds
from test_core import test_directory

ROOT = Path(__file__).resolve().parents[1]


def write_config(directory, cfg):
    path = Path(directory) / "cfg.json"
    path.write_text(json.dumps(cfg))
    return path


class StepSamplingTests(unittest.TestCase):
    def test_defaults_unchanged_without_presets(self):
        cfg = load_config(ROOT / "configs/dream-pilot.json")
        self.assertEqual(step_sampling(cfg, "anchor"), {"temperature": 0})
        self.assertEqual(step_sampling(cfg, "integration"),
                         {"temperature": cfg["generation"]["integration_temperature"], "top_p": cfg["generation"]["top_p"]})
        self.assertEqual(anchor_sampling(cfg), step_sampling(cfg, "anchor"))

    def test_broad_pilot_samples_anchor_and_integration(self):
        cfg = load_config(ROOT / "configs/dream-broad-pilot.json")
        for step in ("anchor", "integration"):
            self.assertEqual(step_sampling(cfg, step), {"temperature": 0.6, "top_p": 0.95, "top_k": 20})

    def test_integration_preset_rejects_unknown_keys(self):
        with test_directory() as d:
            cfg = json.loads((ROOT / "configs/dream-broad-pilot.json").read_text())
            cfg["generation"]["integration"]["min_p"] = 0.1
            with self.assertRaisesRegex(ValueError, "only temperature"):
                load_config(write_config(d, cfg))


class ExtraArmTests(unittest.TestCase):
    def test_decat_cell_and_counts(self):
        cfg = load_config(ROOT / "configs/dream-broad-pilot.json")
        cells = plan(cfg)
        decat = [c for c in cells if c.get("vector") == "decat"]
        self.assertEqual(len(decat), 1)
        self.assertEqual(decat[0]["lambda"], 0.2)
        self.assertEqual(decat[0]["temperature"], cfg["generation"]["temperature"])
        self.assertEqual(len(cells), 5)
        self.assertEqual(trial_count(cfg, 6), 90)
        self.assertTrue(Path(cfg["steering"]["extra_arms"][0]["vector_path"]).is_absolute())

    def test_concept_pilot_counts_one_coupled_decat_cell(self):
        cfg = load_config(ROOT / "configs/dream2-concepts-pilot.json")
        # frozen, plasticity_only, exploration_only, coupled, preexposure, coupled_decat
        self.assertEqual(trial_count(cfg, 6), 36)

    def test_bad_arms_rejected(self):
        base = json.loads((ROOT / "configs/dream-broad-pilot.json").read_text())
        for change, message in ((lambda a: a.update(name="divergent"), "new identifiers"),
                                (lambda a: a.update(**{"lambda": 0}), "lambda"),
                                (lambda a: a.pop("kind"), "kind"),
                                (lambda a: a.update(schedule=True), "takes name")):
            cfg = deepcopy(base)
            change(cfg["steering"]["extra_arms"][0])
            with test_directory() as d, self.assertRaisesRegex(ValueError, message):
                load_config(write_config(d, cfg))
        cfg = deepcopy(base)
        cfg["steering"]["extra_arms"].append(deepcopy(cfg["steering"]["extra_arms"][0]))
        with test_directory() as d, self.assertRaisesRegex(ValueError, "distinct"):
            load_config(write_config(d, cfg))

    def test_extra_arms_not_for_numeric_dream2(self):
        cfg = json.loads((ROOT / "configs/dream2-pilot.json").read_text())
        cfg["steering"]["extra_arms"] = json.loads((ROOT / "configs/dream-broad-pilot.json").read_text())["steering"]["extra_arms"]
        with test_directory() as d, self.assertRaisesRegex(ValueError, "extra_arms"):
            load_config(write_config(d, cfg))

    def test_concept_gate_must_stay_disabled(self):
        cfg = json.loads((ROOT / "configs/dream2-concepts-pilot.json").read_text())
        cfg["gate"]["enabled"] = True
        with test_directory() as d, self.assertRaisesRegex(ValueError, "blinded review"):
            load_config(write_config(d, cfg))


class ConceptWorldTests(unittest.TestCase):
    def setUp(self):
        self.worlds = load_concept_worlds(ROOT / "data/concept-worlds-development.jsonl", "development")

    def test_shipped_worlds(self):
        self.assertEqual(len(self.worlds), 6)
        self.assertEqual(sorted(w["kind"] for w in self.worlds), ["invented"] * 3 + ["real"] * 3)
        for world in self.worlds:
            self.assertEqual({i["category"] for i in world["eval"]}, set(EVAL_CATEGORIES))
            closed = [i for i in world["train"] if i["book"] == "closed"]
            self.assertTrue(closed and all(i["context"] == "" for i in closed))
            for item in closed + world["eval"]:
                self.assertNotIn(world["definition"].casefold(), item["question"].casefold())

    def test_definition_leak_rejected(self):
        worlds = deepcopy(self.worlds)
        worlds[0]["eval"][0]["question"] += " " + worlds[0]["definition"]
        with self.assertRaisesRegex(ValueError, "leaks"):
            validate_concept_worlds(worlds)

    def test_closed_book_must_have_no_context(self):
        worlds = deepcopy(self.worlds)
        next(i for i in worlds[0]["train"] if i["book"] == "closed")["context"] = "hint"
        with self.assertRaisesRegex(ValueError, "Closed-book"):
            validate_concept_worlds(worlds)

    def test_both_books_required(self):
        worlds = deepcopy(self.worlds)
        worlds[0]["train"] = [i for i in worlds[0]["train"] if i["book"] == "open"]
        with self.assertRaisesRegex(ValueError, "both open-book and closed-book"):
            validate_concept_worlds(worlds)

    def test_smoke_world_is_a_shipped_world(self):
        smoke = load_concept_worlds(ROOT / "data/concept-worlds-smoke.jsonl", "development")
        self.assertEqual(smoke, self.worlds[:1])


class RenderOverrideTests(unittest.TestCase):
    class Tokenizer:
        chat_template = "test"
        def apply_chat_template(self, messages, **kwargs):
            return json.dumps(kwargs.get("enable_thinking"))

    def test_override_applies_only_to_hybrid_tokenizers(self):
        tok = self.Tokenizer()
        self.assertEqual(render_chat(tok, "q", enable_thinking=False), "null")
        tok.dream_chat_kwargs = {"enable_thinking": True}
        self.assertEqual(render_chat(tok, "q"), "true")
        self.assertEqual(render_chat(tok, "q", enable_thinking=False), "false")
        self.assertEqual(tok.dream_chat_kwargs, {"enable_thinking": True})

    def test_broad_tasks_keep_negative_control(self):
        rows = [json.loads(l) for l in (ROOT / "data/tasks-broad.jsonl").read_text().splitlines() if l.strip()]
        self.assertEqual(len(rows), 6)
        self.assertIn("negative_control", {r["category"] for r in rows})
        self.assertEqual(len({r["id"] for r in rows}), 6)


class ReviewExportTests(unittest.TestCase):
    def test_concept_pool_hides_condition_and_rates_baseline_once(self):
        import importlib.util, sys
        sys.path.insert(0, str(ROOT / "scripts"))
        spec = importlib.util.spec_from_file_location("export_concept_review", ROOT / "scripts/export_concept_review.py")
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        world = load_concept_worlds(ROOT / "data/concept-worlds-smoke.jsonl", "development")[0]
        row = {"category": "uses", "question": "q", "text": "an answer", "reasoning_enabled": True,
               "answered": True, "taught_term_overlap": 0.5, "thinking": "hidden reasoning"}
        with test_directory() as d:
            for i, condition in enumerate(("frozen", "coupled_decat")):
                (Path(d) / f"trial-{i:06d}.json").write_text(json.dumps({"world_id": world["id"], "seed": 11,
                    "condition": condition, "lambda": 0.2, "eta": 1.0, "vector": "decat",
                    "before_eval": [row], "after_eval": [row]}))
            pool, key = module.concept_pool(Path(d), {world["id"]: world})
        self.assertEqual(len(pool), 3)
        self.assertEqual([k["stage"] for k in key].count("before"), 1)
        for item in pool:
            self.assertEqual(set(item), {"sample_id", "concept", "taught_definition", "question", "answer", "ratings"})
            self.assertNotIn("hidden reasoning", json.dumps(item))


class LoopGuardTests(unittest.TestCase):
    GUARD = {"window_tokens": 64, "ngram": 4, "repeat_share": 0.8, "check_every": 8}

    def test_repeated_tail_detected_and_varied_text_not(self):
        from dream_core.modeling import loop_detected, loop_share
        import random
        self.assertIsNone(loop_share(list(range(10)), self.GUARD))
        rng = random.Random(5)
        varied = [rng.randrange(1000) for _ in range(300)]
        self.assertFalse(loop_detected(varied, self.GUARD))
        looping = varied[:100] + list(range(500, 510)) * 20
        self.assertTrue(loop_detected(looping, self.GUARD))

    def test_shipped_guard_matches_calibration(self):
        for name in ("dream-broad-pilot", "dream2-concepts-pilot"):
            guard = load_config(ROOT / f"configs/{name}.json")["limits"]["loop_guard"]
            self.assertEqual({k: guard[k] for k in self.GUARD},
                             {"window_tokens": 1200, "ngram": 16, "repeat_share": 0.8, "check_every": 16})

    def test_guard_validation(self):
        base = json.loads((ROOT / "configs/dream-broad-pilot.json").read_text())
        for change, message in ((lambda g: g.update(repeat_share=0.3), "repeat share"),
                                (lambda g: g.update(window_tokens=9000), "loop window"),
                                (lambda g: g.update(min_tokens=3), "takes window_tokens")):
            cfg = deepcopy(base); change(cfg["limits"]["loop_guard"])
            with test_directory() as d, self.assertRaisesRegex(ValueError, message):
                load_config(write_config(d, cfg))
        cfg = json.loads((ROOT / "configs/dream2-pilot.json").read_text())
        cfg["limits"]["loop_guard"] = dict(self.GUARD)
        with test_directory() as d, self.assertRaisesRegex(ValueError, "loop_guard"):
            load_config(write_config(d, cfg))

    @unittest.skipUnless(importlib.util.find_spec("torch") is not None, "torch required")
    def test_dream_records_looped_steps_and_continues(self):
        # Option A: a looped anchor skips its task/seed, a looped exploration skips one cell;
        # both are recorded and the run carries on to completed trials.
        from contextlib import contextmanager
        from unittest.mock import patch
        import dream.experiment as experiment
        cfg = load_config(ROOT / "configs/dream-broad-smoke.json")
        calls = []

        def fake_generate(model, tokenizer, text, *, system=None, **kwargs):
            calls.append(system)
            self.assertEqual(kwargs["loop_guard"], cfg["limits"]["loop_guard"])
            looped_anchor = system == experiment.ANCHOR_SYSTEM and "ladder" in text
            looped_explore = system == experiment.EXPLORE_SYSTEM and len([c for c in calls if c == system]) == 1
            finish = "loop" if looped_anchor or looped_explore else "eos"
            return {"text": "" if finish == "loop" else "ok", "thinking": "x", "finish_reason": finish,
                    "input_tokens": 3, "output_tokens": 5}

        class Steerer:
            trace = []
            def __init__(self, *a, **k): pass
            def __enter__(self): return self
            def __exit__(self, *a): return False

        with test_directory() as d:
            cfg["output_dir"] = d
            with patch.object(experiment, "generate", fake_generate), \
                 patch.object(experiment, "load_vector", lambda *a, **k: None), \
                 patch.object(experiment, "MaskedSteerer", Steerer), \
                 patch.object(experiment, "assert_no_dream_hooks", lambda m: None), \
                 patch.object(experiment, "file_hash", lambda p: "h"):
                path = experiment.run(None, None, cfg)
            records = [json.loads(p.read_text()) for p in sorted(Path(path).glob("trial-*.json"))]
        statuses = [(r["status"], r.get("stage")) for r in records]
        self.assertEqual(statuses[0], ("looped", "anchor"))
        self.assertEqual(statuses.count(("looped", "exploration")), 1)
        self.assertEqual(statuses.count(("completed", None)), 4)


if __name__ == "__main__":
    unittest.main()
