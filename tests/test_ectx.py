"""V1.6.0 explicit-context study: task engine, independent key check, leakage, prompts, runtime."""
import collections
import contextlib
import copy
import importlib.util
import json
from pathlib import Path
import random
import unittest

from ectx import generate, keycheck, render, runtime, world
from dream_core import localpaths as LP  # public release: local paths from environment

ROOT = Path(__file__).resolve().parents[1]
QWEN3 = Path(f"{LP.MODELS}/Qwen3-8B/b968826d9c46dd6066d109eabc6255188de91218")
ML = all(importlib.util.find_spec(n) is not None for n in ("torch", "transformers", "peft", "safetensors"))


def delivery_static():
    return {"places": ["North", "Mid", "South"],
            "roads": [["Mid", "North", 1], ["Mid", "South", 1], ["North", "South", 5]],
            "items": {"pod": {"portable": True}, "sign": {"portable": False}, "box": {"portable": True}}}


class EngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dev = generate.generate_split("dev", 2, "unit-test")
        cls.sealed = generate.generate_split("sealed", 2, "unit-test")

    def test_two_solvers_agree_and_design_properties_hold(self):
        for ep in self.dev + self.sealed:
            self.assertEqual(keycheck.check_episode(ep), [], ep["episode_id"])

    def test_hand_worked_delivery_case(self):
        st = delivery_static()
        q = {"state": {"agent": "North", "item_at": {"pod": "North", "sign": "Mid", "box": "South"}, "closed": []},
             "goal": {"item": "pod", "place": "South"}, "correction": None,
             "candidates": [
                 {"id": "A1", "plan": [["take", "pod"], ["go", "North", "Mid"], ["go", "Mid", "South"], ["put", "pod"]]},  # cost 4
                 {"id": "B2", "plan": [["take", "pod"], ["go", "North", "South"], ["put", "pod"]]},  # cost 7
                 {"id": "C3", "plan": [["go", "North", "Mid"], ["go", "Mid", "South"]]},  # goal not met
                 {"id": "D4", "plan": [["take", "sign"]]}]}  # sign fixed: invalid
        for judge in (world.judge, keycheck.judge):
            best, ok, detail = judge("delivery", st, q)
            self.assertEqual((best, ok), (4, ["A1"]))
            self.assertEqual(detail["B2"], (True, 7))
            self.assertFalse(detail["D4"][0])
        closed = copy.deepcopy(q); closed["state"]["closed"] = [["Mid", "South"]]
        for judge in (world.judge, keycheck.judge):
            self.assertEqual(judge("delivery", st, closed)[:2], (7, ["B2"]))
        done = copy.deepcopy(q); done["state"]["item_at"]["pod"] = "South"
        done["candidates"].append({"id": "E5", "plan": []})
        for judge in (world.judge, keycheck.judge):
            self.assertEqual(judge("delivery", st, done)[:2], (0, ["E5"]))
        held = copy.deepcopy(q); held["state"]["item_at"]["box"] = "held"
        for judge in (world.judge, keycheck.judge):  # hands full: taking pod first is not allowed
            self.assertFalse(judge("delivery", st, held)[2]["A1"][0])

    def test_multiple_acceptable_answers_all_accepted(self):
        st = delivery_static()
        st["roads"][2][2] = 2  # direct road now ties the two-step route
        q = {"state": {"agent": "North", "item_at": {"pod": "North", "sign": "Mid", "box": "South"}, "closed": []},
             "goal": {"item": "pod", "place": "South"}, "correction": None,
             "candidates": [{"id": "A1", "plan": [["take", "pod"], ["go", "North", "Mid"], ["go", "Mid", "South"], ["put", "pod"]]},
                            {"id": "B2", "plan": [["take", "pod"], ["go", "North", "South"], ["put", "pod"]]}]}
        for judge in (world.judge, keycheck.judge):
            self.assertEqual(judge("delivery", st, q)[1], ["A1", "B2"])

    def test_correction_overrides_without_mutating_packet(self):
        st = delivery_static()
        before = json.dumps(st)
        corr = {"path": ["roads", 2, 2], "value": 1, "text": "x"}
        self.assertEqual(world.apply_correction(st, corr)["roads"][2][2], 1)
        self.assertEqual(json.dumps(st), before)

    def test_assembly_adapter_semantics(self):
        st = {"slots": {"S": "J1"}, "parts": {"p": {"type": "J2", "rating": 4}},
              "adapters": {"ad": {"from": "J2", "to": "J1"}}, "prices": {}}
        q = {"state": {"slot_part": {"S": None}, "slot_adapter": {"S": None}, "on_hand": ["ad", "p"]},
             "goal": {"slot": "S", "min_rating": 3}, "correction": None,
             "candidates": [{"id": "A1", "plan": [["install", "p", "S"]]},
                            {"id": "B2", "plan": [["fit", "ad", "S"], ["install", "p", "S"]]}]}
        for judge in (world.judge, keycheck.judge):
            best, ok, detail = judge("assembly", st, q)
            self.assertEqual((best, ok), (3, ["B2"]))
            self.assertFalse(detail["A1"][0])

    def test_workshop_inputs_consumed_and_permits(self):
        st = {"sources": {"Shop": {"resource": "r1", "cost": 1, "permit": None},
                          "Far": {"resource": "r2", "cost": 2, "permit": "P"}},
              "permits": {"P": 3}, "recipes": {"X": {"inputs": ["r1", "r2"], "permit": None}}}
        q = {"state": {"have": [], "permits": [], "out_of_stock": []}, "goal": {"item": "X"}, "correction": None,
             "candidates": [{"id": "A1", "plan": [["get", "r1", "Shop"], ["get", "r2", "Far"], ["make", "X"]]},
                            {"id": "B2", "plan": [["get", "r1", "Shop"], ["obtain", "P"], ["get", "r2", "Far"], ["make", "X"]]}]}
        for judge in (world.judge, keycheck.judge):
            best, ok, detail = judge("workshop", st, q)
            self.assertEqual((best, ok), (7, ["B2"]))
            self.assertFalse(detail["A1"][0])

    def test_pairs_share_options_and_have_disjoint_keys(self):
        for ep in self.dev + self.sealed:
            pairs = {}
            for q in ep["queries"]:
                if q["kind"] == "pair":
                    pairs.setdefault(q["pair_id"], []).append(q)
            self.assertEqual(len(pairs), 4)
            for a, b in pairs.values():
                self.assertEqual(a["candidates"], b["candidates"])
                self.assertFalse(set(a["acceptable"]) & set(b["acceptable"]))

    def test_split_templates_and_labels_are_disjoint(self):
        for fam, f in generate.FLIPS.items():
            self.assertFalse(set(f["dev"]) & set(f["sealed"]))
        self.assertFalse(set(generate.CONSONANTS["dev"]) & set(generate.CONSONANTS["sealed"]))
        for ep in self.dev:
            self.assertTrue(all(q.get("flip") in (None, *generate.FLIPS[ep["family"]]["dev"]) for q in ep["queries"]))

    def test_generation_is_deterministic(self):
        again = generate.generate_split("dev", 2, "unit-test")
        self.assertEqual(json.dumps(again, sort_keys=True), json.dumps(self.dev, sort_keys=True))

    def test_no_evaluation_query_reaches_adapter_training(self):
        for ep in self.dev:
            examples = runtime.training_examples(ep, 2, 5)
            self.assertEqual({e["source_qid"] for e in examples}, {s["qid"] for s in ep["support"]})
            for e in examples:
                for q in ep["queries"]:
                    self.assertNotIn(render.query_block(ep["family"], q), e["prompt"])
                # leave-one-out: the trained example's answer line is not in its own context
                self.assertNotIn(render.query_block(ep["family"], next(s for s in ep["support"] if s["qid"] == e["source_qid"]),
                                                    answer=next(s for s in ep["support"] if s["qid"] == e["source_qid"])["answer"]),
                                 e["prompt"])

    def test_augmentation_keeps_the_answer_plan(self):
        ep = self.dev[0]
        rng = random.Random(1)
        for s in ep["support"]:
            v = runtime.augment(s, rng)
            plan = lambda q: next(c["plan"] for c in q["candidates"] if c["id"] == q["answer"])
            self.assertEqual(plan(v), plan(s))
            self.assertEqual(sorted(json.dumps(c["plan"]) for c in v["candidates"]),
                             sorted(json.dumps(c["plan"]) for c in s["candidates"]))

    def test_rendered_text_contains_every_fact(self):
        for ep in self.dev:
            text = render.packet(ep)
            for line in render.static_lines(ep["family"], ep["static"]):
                self.assertIn(line, text)
            for q in ep["queries"]:
                block = render.query_block(ep["family"], q)
                self.assertIn(render.goal_line(ep["family"], q["goal"]), block)
                for c in q["candidates"]:
                    self.assertIn(f"[{c['id']}]", block)
                if q["correction"]:
                    self.assertIn(q["correction"]["text"], block)

    def test_wx_mapping_is_a_same_family_derangement_and_rejects_singletons(self):
        import importlib.util as iu
        spec = iu.spec_from_file_location("ectx_run", ROOT / "scripts" / "ectx_run.py")
        mod = iu.module_from_spec(spec); spec.loader.exec_module(mod)
        eps = {e["episode_id"]: e for e in self.dev}
        ids = list(eps)
        pair = mod.partners(ids, eps)
        self.assertTrue(all(pair[i] != i and eps[pair[i]]["family"] == eps[i]["family"] for i in ids))
        self.assertEqual(sorted(pair.values()), sorted(ids))
        one_each = [next(i for i in ids if eps[i]["family"] == f) for f in ("delivery", "assembly", "workshop")]
        with self.assertRaises(SystemExit):
            mod.partners(one_each, eps)

    def test_cross_world_donor_mapping_validation(self):
        import importlib.util as iu
        spec = iu.spec_from_file_location("ectx_run", ROOT / "scripts" / "ectx_run.py")
        mod = iu.module_from_spec(spec); spec.loader.exec_module(mod)
        eps = {e["episode_id"]: e for e in generate.generate_split("dev", 4, "unit-test")}
        F = lambda f, i: f"dev-{f}-{i:03d}"
        good = {F("delivery", 0): F("assembly", 0), F("delivery", 1): F("workshop", 1), F("delivery", 2): F("assembly", 2), F("delivery", 3): F("workshop", 3),
                F("assembly", 0): F("workshop", 0), F("assembly", 1): F("delivery", 1), F("assembly", 2): F("workshop", 2), F("assembly", 3): F("delivery", 3),
                F("workshop", 0): F("delivery", 0), F("workshop", 1): F("assembly", 1), F("workshop", 2): F("delivery", 2), F("workshop", 3): F("assembly", 3)}
        ids = sorted(good)
        self.assertEqual(mod.validate_cross(good, ids, eps), good)
        same = dict(good); same[F("delivery", 0)], same[F("delivery", 1)] = F("delivery", 1), F("delivery", 0)
        with self.assertRaises(SystemExit):
            mod.validate_cross(same, ids, eps)
        reuse = dict(good); reuse[F("delivery", 1)] = F("assembly", 0)
        with self.assertRaises(SystemExit):
            mod.validate_cross(reuse, ids, eps)
        one_world = dict(good); one_world[F("delivery", 1)], one_world[F("delivery", 2)] = F("assembly", 2), F("workshop", 1)
        one_world[F("delivery", 3)] = F("workshop", 3)
        mod.validate_cross(one_world, ids, eps)  # still both worlds
        only_a = {**good, F("delivery", 1): F("assembly", 1), F("assembly", 1): F("workshop", 1), F("workshop", 1): F("delivery", 1)}
        only_a[F("delivery", 3)] = F("assembly", 3); only_a[F("assembly", 3)] = F("workshop", 3); only_a[F("workshop", 3)] = F("delivery", 3)
        with self.assertRaises(SystemExit):
            mod.validate_cross(only_a, ids, eps)

    def test_dev_all_covers_every_flip_type_and_keys_check(self):
        eps = generate.generate_split("dev_all", 1, "unit-test")
        for ep in eps:
            self.assertEqual(keycheck.check_episode(ep), [])
            flips = sorted({q["flip"] for q in ep["queries"] if q.get("flip")})
            self.assertEqual(flips, sorted(generate.flip_kinds(ep["family"], "all")))
            self.assertTrue(ep["episode_id"].startswith("devall-"))
            self.assertTrue(all("support_flip" in s for s in ep["support"]))

    def test_rules_only_training_context_keeps_rules_and_facts_but_no_examples(self):
        ep = self.dev[0]
        loo = runtime.training_examples(ep, 0, 1, "loo")
        ro = runtime.training_examples(ep, 0, 1, "rules_only")
        self.assertEqual([e["target"] for e in loo], [e["target"] for e in ro])
        for e in ro:
            self.assertNotIn("Solved examples", e["prompt"])
            self.assertNotIn("Answer:", e["prompt"])
            for r in render.RULES[ep["family"]]:
                self.assertIn(r, e["prompt"])
            for line in render.static_lines(ep["family"], ep["static"]):
                self.assertIn(line, e["prompt"])
            for q in ep["queries"]:
                self.assertNotIn(render.query_block(ep["family"], q), e["prompt"])
        for e in loo:
            self.assertIn("Solved examples", e["prompt"])
        # evaluation prompts are unchanged: full packet with every solved example
        self.assertEqual(render.user_prompt(ep, ep["queries"][0]).count("Answer: "), len(ep["support"]))
        with self.assertRaises(ValueError):
            runtime.training_examples(ep, 0, 1, "other")

    def test_harder_support_keeps_scored_questions_and_covers_every_flip(self):
        from ectx.keycheck import situation
        for ep in generate.generate_split("dev_all", 1, "unit-test"):
            new = generate.with_harder_support(ep, "unit-support")
            self.assertEqual(new["queries"], ep["queries"])
            self.assertEqual(keycheck.check_episode(new), [])
            self.assertEqual(len(new["support"]), 12)
            kinds = [s.get("support_flip") for s in new["support"]]
            for k in {q["flip"] for q in ep["queries"] if q.get("flip")}:
                self.assertEqual(kinds.count(k), 2)
            self.assertEqual(kinds.count("correction"), 2)
            self.assertEqual(kinds.count(None), 2)
            sigs = [situation(x) for x in new["support"]]
            self.assertEqual(len(set(sigs)), 12)
            self.assertFalse(set(sigs) & {situation(q) for q in ep["queries"]})
            for x in new["support"]:
                self.assertEqual(x["acceptable"], [x["answer"]])
                if x["correction"]:
                    self.assertEqual(x["correction"]["scope"], "example")
            # the pair sides share options and have different answers
            pairs = {}
            for x in new["support"]:
                if x.get("support_pair"):
                    pairs.setdefault(x["support_pair"], []).append(x)
            for a, b in pairs.values():
                self.assertEqual(a["candidates"], b["candidates"]); self.assertNotEqual(a["answer"], b["answer"])
            # scoped correction wording in the packet; scored correction wording unchanged
            text = render.packet(new)
            self.assertIn("applies to this example only", text)
            scored = next(q for q in new["queries"] if q["kind"] == "correction")
            self.assertIn("Correction (this replaces the packet's fixed fact): ", render.query_block(ep["family"], scored))
            self.assertEqual(generate.with_harder_support(ep, "unit-support"), new)  # deterministic

    def test_each_source_once_schedule_covers_every_support_example(self):
        ep = generate.with_harder_support(generate.generate_split("dev_all", 1, "unit-test")[0], "unit-support")
        ex = runtime.training_examples(ep, 1, 7)
        self.assertEqual(len(ex), 24)
        order = runtime.training_schedule(ex, {"steps": 12, "schedule": "each_source_once"}, random.Random(1))
        self.assertEqual(sorted(e["source_qid"] for e in order), sorted(s["qid"] for s in ep["support"]))
        order = runtime.training_schedule(ex, {"steps": 24, "schedule": "each_source_once"}, random.Random(1))
        self.assertEqual(collections.Counter(e["source_qid"] for e in order), collections.Counter({s["qid"]: 2 for s in ep["support"]}))
        with self.assertRaises(ValueError):
            runtime.training_schedule(ex, {"steps": 10, "schedule": "each_source_once"}, random.Random(1))
        old = runtime.training_schedule(ex[:12], {"steps": 12}, random.Random(1))  # default unchanged: one shuffled pass
        self.assertEqual(sorted(map(id, old)), sorted(map(id, ex[:12])))

    def test_parse_choice_is_strict(self):
        ids = ["K3", "A6"]
        self.assertEqual(runtime.parse_choice('{"choice": "K3"}', ids), "K3")
        self.assertEqual(runtime.parse_choice('Answer: {"choice":"A6"}.', ids), "A6")
        for bad in ('{"choice": "Z9"}', 'K3', '{"choice": "K3"} {"choice": "A6"}', '{"choice": 3}', '{choice: K3}', ''):
            self.assertIsNone(runtime.parse_choice(bad, ids), bad)


class FakePeft:
    def __init__(self):
        self.active = "null"

    @contextlib.contextmanager
    def disable_adapter(self):
        prev, self.active = self.active, "DISABLED"
        yield
        self.active = prev


class ConditionPromptTests(unittest.TestCase):
    def test_conditions_receive_byte_identical_prompts(self):
        ep = generate.generate_split("dev", 2, "unit-test")[0]
        rt = runtime.Runtime.__new__(runtime.Runtime)
        rt.peft = FakePeft()
        seen = []
        rt.load_adapter = lambda name, state: setattr(rt.peft, "active", name)
        rt.drop_adapter = lambda name: setattr(rt.peft, "active", "null")
        rt.generate = lambda user, max_new_tokens=24: (seen.append((rt.peft.active, user)) or ('{"choice": "Q1"}', 10, 3))
        rows = rt.evaluate_conditions(ep, ["W", "W+A", "W+X", "W+Y"],
                                      {"W+A": ({}, "own"), "W+X": ({}, "other-ep"), "W+Y": ({}, "cross-ep")})
        by = {}
        for active, user in seen:
            by.setdefault(active, []).append(user)
        self.assertEqual(sorted(by), ["DISABLED", "ectxcross", "ectxother", "ectxown"])
        for slot in ("ectxown", "ectxother", "ectxcross"):
            self.assertEqual(by["DISABLED"], by[slot])
        self.assertEqual(len(rows), 4 * (len(ep["queries"]) + len(runtime.UNRELATED)))
        self.assertEqual({r["adapter_from"] for r in rows if r["condition"] == "W+Y"}, {"cross-ep"})


@unittest.skipUnless(ML and (QWEN3 / "tokenizer.json").exists(), "needs torch/peft and the local Qwen3 tokenizer")
class RuntimeIntegrationTests(unittest.TestCase):
    def test_train_save_load_reset_on_tiny_model(self):
        import torch
        from transformers import AutoTokenizer, Qwen3Config, Qwen3ForCausalLM
        tok = AutoTokenizer.from_pretrained(str(QWEN3), local_files_only=True)
        tok.dream_chat_kwargs = {"enable_thinking": False}
        torch.manual_seed(0)
        model = Qwen3ForCausalLM(Qwen3Config(vocab_size=len(tok), hidden_size=32, intermediate_size=64, num_hidden_layers=2,
                                             num_attention_heads=4, num_key_value_heads=2, head_dim=8,
                                             max_position_embeddings=8192, tie_word_embeddings=False))
        model.eval()
        for p in model.parameters():
            p.requires_grad_(False)
        lora = {"rank": 4, "alpha": 8, "targets": ["q_proj", "v_proj"]}
        ep = generate.generate_split("dev", 2, "unit-test")[0]
        rt = runtime.Runtime.from_model(model, tok, lora, "S1", task_probe=render.user_prompt(ep, ep["queries"][0]))
        self.assertEqual(sorted(rt.removal_detail()), ["reference/disabled", "reference/null", "task/disabled", "task/null"])
        self.assertTrue(rt.render("hi").endswith("<think>\n\n</think>\n\n"))
        self.assertEqual(rt.removal_check(), 0.0)
        full = rt.full_hash()
        state, rec, trained_logits = rt.train_adapter(ep, "ectxtrain", 3, {"steps": 4, "lr": 1e-2, "n_aug": 1})
        self.assertTrue(state)
        self.assertFalse([k for k in state if ".null." in k])
        with self.assertRaises(RuntimeError):  # a substring-colliding name is refused, not silently mixed
            rt.train_adapter(ep, "l", 3, {"steps": 1, "lr": 1e-2, "n_aug": 0})
        if "l" in rt.peft.peft_config:
            rt.peft.set_adapter("null"); rt.peft.delete_adapter("l")
        self.assertLess(rec["loss_last"], rec["loss_first"] + 5)
        self.assertEqual(rt.fingerprint(), rt.base_fingerprint)
        self.assertEqual(rt.full_hash(), full)
        self.assertEqual(rt.removal_check(), 0.0)
        self.assertNotIn("ectxtrain", rt.peft.peft_config)
        self.assertEqual(set(rec["support_before"]), {"loo", "rules_only"})
        self.assertEqual(len(rec["steps_log"]), 4)
        self.assertTrue(all(s["grad_norm"] > 0 for s in rec["steps_log"]))
        self.assertGreater(rec["delta_norm_total"], 0.0)
        _, rec_ro, _ = rt.train_adapter(ep, "ectxtrain", 3, {"steps": 2, "lr": 1e-2, "n_aug": 0, "context": "rules_only"})
        self.assertEqual(rec_ro["context"], "rules_only")
        ids, n_target, pos = rt.encode("q", json.dumps({"choice": "K7"}), "K7")
        self.assertEqual(tok.decode(ids[0, -n_target:][pos]).strip(), "K7")
        # repeat with the same seed: identical adapter (fresh init and optimizer per episode)
        state2, _, _ = rt.train_adapter(ep, "ectxtrain", 3, {"steps": 4, "lr": 1e-2, "n_aug": 1})
        self.assertTrue(all(torch.equal(state[k], state2[k]) for k in state))
        # loaded adapter changes outputs; dropping it restores the base exactly
        rt.load_adapter("ectxown", state)
        self.assertTrue(torch.equal(rt.adapter_probe("ectxown"), trained_logits))  # save/load functional identity
        with torch.no_grad():
            ids = tok(rt.render("x"), return_tensors="pt").input_ids
            with_adapter = rt.peft(input_ids=ids).logits[0, -1]
        rt.drop_adapter("ectxown")
        self.assertEqual(rt.removal_check(), 0.0)
        self.assertNotIn("ectxown", rt.peft.peft_config)
        with torch.no_grad():
            with rt.peft.disable_adapter():
                base = rt.peft(input_ids=ids).logits[0, -1]
        self.assertGreater(float((with_adapter - base).abs().max()), 0.0)
        rows = rt.evaluate_episode(ep, state, state2, "x")
        self.assertEqual({r["condition"] for r in rows}, {"W", "W+A", "W+X"})
        self.assertEqual(rt.fingerprint(), rt.base_fingerprint)


if __name__ == "__main__":
    unittest.main()
