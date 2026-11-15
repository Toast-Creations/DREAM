"""V1.3.0/1.3.1 explore ladder: release glide, rung doses, strict final parser and runner wiring."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from dream.decategorization import (EXPLORE_ROLES, EXPLORE_SYSTEM, load_objects, conditions, explore_prompt, hypotheses_as_ideas, ladder_rungs,
                                    needed_vectors, parse_hypotheses, run)
from dream_core.config import load_config
from dream_core.planning import trial_count
from dream_core.schedules import dose, end_token, validate_spec
from test_core import test_directory
from test_decategorization import keepers_text, write_cfg

ROOT = Path(__file__).resolve().parents[1]


def hypotheses(n=5, status="partly_known"):
    return [{"source_idea": f"Odd {i}", "kernel": "k", "real_world_link": "fish hearts", "hypothesis": f"H{i}",
             "test": "t", "would_prove_wrong": "w", "status": status} for i in range(n)]


def explore_cfg(directory, mutate):
    def both(c):
        explore = json.loads((ROOT / "configs/decat-explore-pilot.json").read_text())
        explore["steering"].update({k: c["steering"][k] for k in ("vector_path", "random_vector_path")})
        c.update(explore | {"data_path": c["data_path"], "output_dir": c["output_dir"]})
        mutate(c)
    return write_cfg(directory, both)


class ReleaseScheduleTests(unittest.TestCase):
    def test_release_glides_from_start_to_floor_then_holds(self):
        spec = validate_spec({"shape": "release", "glide_tokens": 600, "end_fraction": 0.05 / 0.10})
        values = [dose(s, spec) for s in range(800)]
        self.assertEqual(values[0], 1.0)
        self.assertTrue(all(a >= b for a, b in zip(values, values[1:])))
        self.assertAlmostEqual(values[300], 0.75)
        self.assertTrue(all(v == 0.5 for v in values[600:]))
        self.assertEqual(end_token(spec), 600)
        self.assertEqual(dose(700, validate_spec({"shape": "release", "glide_tokens": 10, "end_fraction": 0})), 0)

    def test_bad_release_specs_rejected(self):
        for spec in ({"shape": "release", "glide_tokens": 0, "end_fraction": 0.5},
                     {"shape": "release", "glide_tokens": 10, "end_fraction": 1.5},
                     {"shape": "release", "glide_tokens": 10}):
            with self.assertRaises(ValueError):
                validate_spec(spec)


class LadderConfigTests(unittest.TestCase):
    def test_shipped_configs(self):
        for name, objects, trials in (("decat-explore-smoke", 2, 14), ("decat-explore-pilot", 12, 120)):
            cfg = load_config(ROOT / f"configs/{name}.json")
            self.assertEqual(trial_count(cfg, objects), trials)
        cfg = load_config(ROOT / "configs/decat-explore-pilot.json")
        cells = {c["condition"]: c for c in conditions(cfg)}
        for name in ("trip_ladder_40", "trip_ladder_50", "trip_ladder_60", "trip_flat"):
            self.assertEqual(cells[name]["lambda"], cells["trip"]["lambda"])
            self.assertEqual(cells[name]["schedule_spec"], cells["trip"]["schedule_spec"])
        self.assertEqual(cells["baseline_flat"]["lambda"], 0)
        self.assertIn("decategorization", needed_vectors(cfg))

    def test_rungs_by_mode(self):
        cfg = load_config(ROOT / "configs/decat-explore-smoke.json")
        for name, start in (("40", 0.40), ("50", 0.50), ("60", 0.60)):
            ladder = ladder_rungs(cfg, ("ladder", name))
            self.assertEqual([r[0] for r in ladder], ["unpack", "stretch", "connect", "distill", "ground"])
            self.assertEqual((ladder[0][1], ladder[-1][2]), (start, 0.05))
            self.assertTrue(all(a[2] == b[1] and a[1] > a[2] for a, b in zip(ladder, ladder[1:])))
        zero = ladder_rungs(cfg, ("ladder_zero", "40"))
        self.assertEqual(zero[-1], ("ground", 0.12, 0.0))
        self.assertEqual(zero[:-1], ladder_rungs(cfg, ("ladder", "40"))[:-1])
        self.assertTrue(all(r[1:] == (0.0, 0.0) for r in ladder_rungs(cfg, ("flat", None))))

    def test_explore_prompts_carry_no_object_ideas(self):
        # 1.3.0 leak: an example idea in the system prompt became a model idea.
        objects = load_objects(ROOT / "data/objects-development.jsonl", "development")
        text = (EXPLORE_SYSTEM + " ".join(EXPLORE_ROLES.values())).casefold()
        names = {row["object"].casefold() for row in objects} | {"heart", "aortic", "valve", "bone", "web"}
        self.assertEqual({n for n in names if n in text}, set())

    def test_ladder_bounds(self):
        def levels(c):
            return c["ladder"]["levels"]
        bad = [lambda c: levels(c)["40"].__setitem__(2, 0.35),               # rising
               lambda c: levels(c)["60"].__setitem__(0, 0.65),               # above cap
               lambda c: levels(c)["50"].pop(),                              # wrong length
               lambda c: levels(c).pop("60"),                                # arm uses a missing ladder
               lambda c: c["ladder"]["roles"].reverse(),                     # ground not last
               lambda c: c["ladder"]["roles"].__setitem__(2, "hallucinate"),
               lambda c: c["steering"].update(max_abs_strength=0.7),
               lambda c: c["decategorization"]["conditions"].remove("trip_flat") or
                         c["decategorization"]["conditions"].remove("baseline_flat"),
               lambda c: c["decategorization"]["conditions"].remove("baseline"),
               lambda c: c.pop("ladder")]
        with test_directory() as directory:
            load_config(explore_cfg(directory, lambda c: None))
            for mutate in bad:
                with self.assertRaises((ValueError, KeyError)):
                    load_config(explore_cfg(directory, mutate))


class HypothesisParserTests(unittest.TestCase):
    def test_strict(self):
        parsed = parse_hypotheses(json.dumps({"hypotheses": hypotheses()}))
        self.assertTrue(parsed["valid"])
        for text in (json.dumps({"hypotheses": hypotheses(4)}), json.dumps({"hypotheses": hypotheses(status="maybe")}),
                     json.dumps({"hypotheses": hypotheses(), "extra": 1}),
                     json.dumps({"hypotheses": hypotheses()[:4] + [dict(hypotheses()[4], source_idea=" odd 0")]}), "Here: " + json.dumps({"hypotheses": hypotheses()})):
            self.assertFalse(parse_hypotheses(text)["valid"])

    def test_shared_idea_shape_for_blinding(self):
        self.assertEqual(set(hypotheses_as_ideas(hypotheses())[0]), {"idea", "reasoning", "would_prove_wrong"})

    def test_prompt_encodes_material_and_role(self):
        text = explore_prompt({"object": "heart", "description": "pump"}, "connect", 'say "hi"\nnow', False)
        self.assertIn(json.dumps('say "hi"\nnow'), text)
        self.assertIn(EXPLORE_ROLES["connect"], text)
        self.assertIn("previous step", text)


class LadderRunnerTests(unittest.TestCase):
    def test_runner_chains_passes_with_gliding_doses(self):
        with test_directory() as directory:
            root = Path(directory)
            manifest = root / "manifest.json"; manifest.write_text("{}")
            cfg = load_config(ROOT / "configs/decat-explore-smoke.json")
            cfg.update(output_dir=str(root / "runs"))
            cfg["model"]["manifest"] = str(manifest)
            for key in ("vector_path", "random_vector_path"):
                (root / key).write_text("{}"); cfg["steering"][key] = str(root / key)
            hooks = {"active": None}; calls = []

            class Steerer:
                def __init__(self, model, layer, vector, strength, **kwargs):
                    self.spec = kwargs["schedule_spec"]; self.strength = strength
                    self.trace = [strength]; self.comedown_complete = True if self.spec else None
                def __enter__(self):
                    hooks["active"] = (self.strength, self.spec); return self
                def __exit__(self, *exc):
                    hooks["active"] = None; return False

            def no_hooks(model):
                if hooks["active"]:
                    raise RuntimeError("hook active")

            def generate(model, tok, text, **kwargs):
                calls.append({"text": text, "system": kwargs["system"], "hook": hooks["active"], "seed": kwargs["seed"]})
                if "developing strange ideas" not in kwargs["system"]:
                    body = keepers_text()
                elif EXPLORE_ROLES["ground"] in text:
                    body = json.dumps({"hypotheses": hypotheses()})
                else:
                    body = f"pass output {len(calls)}"
                return {"text": body, "finish_reason": "eos", "input_tokens": 10, "output_tokens": 50}

            steering = SimpleNamespace(MaskedSteerer=Steerer, assert_no_dream_hooks=no_hooks,
                                       load_vector=lambda *a, **k: k.get("kind"))
            with patch.dict(sys.modules, {"dream_core.steering": steering}), patch("dream_core.modeling.generate", generate):
                path = run(SimpleNamespace(parameters=lambda: iter(())), SimpleNamespace(), cfg)
            trials = {(t["object"], t["condition"]): t for t in
                      (json.loads(p.read_text()) for p in sorted(path.glob("trial-*.json")))}
            self.assertEqual(len(trials), 14)
            explore_calls = [c for c in calls if "developing strange ideas" in c["system"]]
            self.assertEqual(len(explore_calls), 2 * 5 * 5)
            for (obj, cond), t in trials.items():
                if cond in ("baseline", "trip"):
                    self.assertNotIn("explore_passes", t); continue
                passes = t["explore_passes"]
                self.assertEqual([p["role"] for p in passes], ["unpack", "stretch", "connect", "distill", "ground"])
                self.assertTrue(t["explore_structure"]["valid"] and t["completed_five_idea_answer"])
                self.assertEqual(t["final_ideas"][0]["idea"], "H0")
                ends = [p["end"] for p in passes]
                if cond.endswith("flat"):
                    self.assertTrue(all(p["start"] == 0 and p["steering_trace"] == [] for p in passes))
                else:
                    starts = {"trip_ladder_40": 0.40, "trip_ladder_50": 0.50, "trip_ladder_60": 0.60}[cond]
                    self.assertEqual((passes[0]["start"], ends[-1]), (starts, 0.05))
            # Each pass reads the previous pass's text, and the first reads stage 1.
            heart = [c for c in explore_calls if "heart" in c["text"]][:5]
            self.assertIn(json.dumps(keepers_text()), heart[0]["text"])
            self.assertTrue(all('previous step, encoded as JSON:\n"pass output ' in c["text"] for c in heart[1:]))
            steered = [c["hook"] for c in explore_calls if c["hook"]]
            self.assertTrue(all(spec["shape"] == "release" for _, spec in steered))
            self.assertIn((0.60, {"shape": "release", "glide_tokens": 600, "end_fraction": 0.49 / 0.60}), steered)


if __name__ == "__main__":
    unittest.main()
