"""CPU-only allocation, sparse membership, semantics and commitments for CCONF-v1."""
import collections
import copy
import hashlib
import itertools
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tempo import clarify as CL, clarconfirm as CC, factored as FA, holdeval as HE, holdout as HO
from tempo.worlds import YES, NO


class ConfirmGenerator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.panel = CC.generate()

    def test_closed_explicit_config(self):
        cfg = copy.deepcopy(CC.DEFAULT_CONFIG)
        self.assertEqual(CC.validate_config(cfg), cfg)
        bads = [dict(cfg, unknown=True), {k: v for k, v in cfg.items() if k != "schedule_seed"},
                dict(cfg, primary_arrival_stems=320), dict(cfg, primary_correction_stems=225),
                dict(cfg, family_ratio=[True, 1, 2]), dict(cfg, b2=False), dict(cfg, max_attempts=True),
                dict(cfg, pool=cfg["smoke_pool"]), dict(cfg, id_prefix="unsafe__namespace"),
                dict(cfg, base_seed=cfg["smoke_base_seed"])]
        for bad in bads:
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    CC.validate_config(bad)

    def test_exact_allocation_nesting_and_bits(self):
        rows = self.panel["main"]["plan"]
        self.assertEqual(len(rows), 224)
        expected = {"primary_arrival": (224, {"F1_two_hop": 56, "F2_slot_join": 56, "F3_historical_occupant": 112}),
                    "primary_correction": (160, {"F1_two_hop": 40, "F2_slot_join": 40, "F3_historical_occupant": 80}),
                    "reference_arrival": (32, {"F1_two_hop": 8, "F2_slot_join": 8, "F3_historical_occupant": 16}),
                    "reference_correction": (16, {"F1_two_hop": 4, "F2_slot_join": 4, "F3_historical_occupant": 8})}
        cells = {(0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 0)}
        for flag, (count, families) in expected.items():
            selected = [row for row in rows if row[flag]]
            self.assertEqual(len(selected), count)
            self.assertEqual(collections.Counter(row["family"] for row in selected), families)
            for fam, family_n in families.items():
                for rec in HO.RECEPTION:
                    sub = [row for row in selected if row["family"] == fam and row["reception"] == rec]
                    self.assertEqual(len(sub), family_n // 2)
                    bitcounts = collections.Counter(tuple(row["bits"]) for row in sub)
                    if flag != "reference_correction" or fam == "F3_historical_occupant":
                        self.assertEqual(set(bitcounts), cells)
                        self.assertEqual(len(set(bitcounts.values())), 1)
                globalbits = collections.Counter(tuple(row["bits"]) for row in selected if row["family"] == fam)
                self.assertEqual(set(globalbits), cells)
                self.assertEqual(len(set(globalbits.values())), 1)
        for row in rows:
            self.assertEqual(row["primary_correction"], row["block"] < 20)
            self.assertEqual(row["reference_arrival"], row["block"] < 4)
            self.assertEqual(row["reference_correction"], row["block"] < 2)
        mutated = copy.deepcopy(rows)
        mutated[0]["reference_correction"] = False
        with self.assertRaises(ValueError):
            CC.validate_allocation(mutated)
        mutated = copy.deepcopy(rows)
        mutated[0]["primary_arrival"] = 1
        with self.assertRaises(ValueError):
            CC.validate_allocation(mutated)
        with self.assertRaises(ValueError):
            CC.generate(allocation={})

    def test_exact_targets_sparse_arms_and_encoded_ids(self):
        for part, ntargets, ncalls in (("main", 1088, 2304), ("smoke", 12, 36)):
            data = self.panel[part]
            self.assertEqual(len(data["public"]), ntargets)
            self.assertEqual(len(data["hidden"]), ntargets)
            self.assertEqual(len(data["calls"]), ncalls)
            ids = {call["call_id"] for call in data["calls"]}
            self.assertEqual(ids, CC.allowed_call_ids(data["plan"]))
            self.assertEqual(len({cid.replace("|", "__") for cid in ids}), ncalls)
            bytarget = collections.defaultdict(set)
            public = {p["target"]: p for p in data["public"]}
            for call in data["calls"]:
                bytarget[call["target"]].add(call["arm"])
                self.assertEqual(hashlib.sha256(call["user"].encode()).hexdigest(), call["user_sha256"])
                self.assertEqual(hashlib.sha256(call["system"].encode()).hexdigest(), call["system_sha256"])
            for tid, arms in bytarget.items():
                self.assertEqual(arms, set(CC.allowed_arms(public[tid], public[tid]["act"])))
        main = self.panel["main"]["calls"]
        self.assertEqual(collections.Counter(c["arm"] for c in main),
                         {"SUB_ORIG": 1088, "KEEP_CLAR": 1088, "SUB_CLAR": 128})
        self.assertEqual(collections.Counter(c["act"] for c in main), {"arrival": 960, "correction": 1344})
        self.assertEqual(collections.Counter(c["direction"] for c in main),
                         {"na": 960, "yes_to_no": 672, "no_to_yes": 672})
        self.assertFalse(any(c["arm"] == "KEEP_ORIG" for c in main))

    def test_prompt_parity_and_hidden_label_poisoning(self):
        for part in self.panel.values():
            prompts = {p["target"]: p for p in part["public"]}
            for pub in part["public"]:
                inherited, led = CL.prompts_from_public(pub)
                self.assertEqual(inherited["SUB_CLAR"].replace("\n" + CL.CLARIFICATION, ""), inherited["SUB_ORIG"])
                self.assertEqual(inherited["KEEP_CLAR"].replace("\n" + CL.CLARIFICATION, ""), inherited["KEEP_ORIG"])
                poisoned = copy.deepcopy(pub)
                poisoned.update(gold_field="poison.on_hand", case={"records": []}, identity={"field": "poison"})
                self.assertEqual(CL.prompts_from_public(poisoned), (inherited, led))
            for call in part["calls"]:
                self.assertEqual(call["user"], CL.prompts_from_public(prompts[call["target"]])[0][call["arm"]])

    def test_originals_reversals_and_history_contrast(self):
        for part in self.panel.values():
            bytarget = {h["target"]: h for h in part["hidden"]}
            for row in part["plan"]:
                first = next(h for h in part["hidden"] if h["stem"] == row["stem"])
                original = HO.build_group(row["stem"], first["world_seed"], row["family"], row["reception"],
                                          row["bits"], first["pool"])
                for act in ("arrival", "correction"):
                    if not row[f"primary_{act}"]:
                        continue
                    for direction in (("na",) if act == "arrival" else CC.DIRECTIONS):
                        a = bytarget[f"{row['stem']}|{act}|{direction}|A"]
                        b = bytarget[f"{row['stem']}|{act}|{direction}|B"]
                        self.assertEqual(a["case"]["text"], b["case"]["text"])
                        self.assertNotEqual(a["gold_field"], b["gold_field"])
                        for h in (a, b):
                            base = original["cases"][(act, h["history"])]
                            case = h["case"]
                            if direction != "no_to_yes":
                                self.assertEqual(case, base)
                            else:
                                # Independent record-level reversal expectation, not a call back into CL.
                                expected_records = copy.deepcopy(base["records"])
                                for rec in expected_records[:-1]:
                                    p = rec["payload"]
                                    if rec["kind"] == "observation" and p.get("field") == base["field"]:
                                        p["value"] = NO if p["value"] == YES else YES
                                expected_records[-1]["payload"]["value"] = YES
                                self.assertEqual(case["records"], expected_records)
                                self.assertEqual(case["desc"], base["desc"])
                                self.assertEqual(case["text"], base["text"].replace("it was not on hand.", "it was on hand."))
                                gold = case["records"][-1]
                                withdrawn = next(r for r in case["records"] if r["rid"] == gold["payload"]["target"])
                                self.assertEqual(withdrawn["payload"]["value"], NO)
                                self.assertIsNone(gold["payload"]["valid_to"])
                # Rebuilt public text agrees with changed canonical records, including F1 custom xrec.
                for h in (h for h in part["hidden"] if h["stem"] == row["stem"]):
                    w = original["world"]
                    pub = next(p for p in part["public"] if p["target"] == h["target"])
                    self.assertEqual(HO.prompt(w, h["case"], h["render_seed"]), pub["base_prompt"])
                    if row["family"] == "F1_two_hop":
                        for rec in h["case"]["records"][:-1]:
                            if rec["kind"] == "observation" and rec["payload"].get("field") == h["gold_field"] and \
                                    rec["rid"] in h["case"]["custom"]:
                                line = next(e["raw_text"] for e in pub["prefix"] if e["record_id"] == rec["rid"])
                                suffix = " is on hand." if rec["payload"]["value"] == YES else " is not on hand."
                                self.assertTrue(line.endswith(suffix), h["target"])

    def test_canonical_exact_no_loss_replay_and_mutation_rejection(self):
        for part in self.panel.values():
            for h in part["hidden"]:
                w = HO._world(h["world_seed"], h["pool"])[0]
                case = h["case"]
                reg = HO.registry(w, case)
                canonical = FA.canonical_factored(case["records"][-1])
                score, _, _ = HE.score(json.dumps(canonical), case, w, reg, "eos")
                self.assertTrue(score["exact"], h["target"])
                self.assertFalse(score["compilation_loss"], h["target"])
                self.assertTrue(score["replay_ok"], h["target"])
                bads = []
                if h["act"] == "correction":
                    for key, value in (("value", NO if canonical["revisions"][0]["value"] == YES else YES),
                                       ("field", h["case"]["other"] + ".on_hand"),
                                       ("target", "r99"), ("valid_from", canonical["revisions"][0]["valid_from"] + 1),
                                       ("valid_to", 99)):
                        bad = copy.deepcopy(canonical)
                        bad["revisions"][0][key] = value
                        bads.append(bad)
                else:
                    bad = copy.deepcopy(canonical)
                    bad["events"][0]["to"] = NO
                    bads.append(bad)
                    state_only = copy.deepcopy(canonical)
                    event = state_only["events"].pop()
                    state_only["states"] = [{"field": event["field"], "at": event["at"], "value": event["to"]}]
                    bads.append(state_only)
                for bad in bads:
                    mutated, _, _ = HE.score(json.dumps(bad), case, w, reg, "eos")
                    self.assertFalse(mutated["exact"], h["target"])

    def test_stem_act_schedule_units_shared_cell_order(self):
        for part in self.panel.values():
            calls = part["calls"]
            seen = set()
            for _, unit in itertools.groupby(calls, key=lambda c: (c["stem"], c["act"])):
                unit = list(unit)
                unitkey = (unit[0]["stem"], unit[0]["act"])
                self.assertNotIn(unitkey, seen)
                seen.add(unitkey)
                perarm = collections.defaultdict(list)
                for call in unit:
                    perarm[call["arm"]].append((call["direction"], call["history"]))
                orders = list(perarm.values())
                self.assertTrue(all(order == orders[0] for order in orders))
                self.assertEqual(len(orders[0]), 2 if unitkey[1] == "arrival" else 4)
                self.assertEqual(len(set(orders[0])), len(orders[0]))
        self.assertEqual(CC.generate(), self.panel)

    def test_historical_collisions_fail(self):
        p = self.panel["main"]["public"][0]["base_prompt"]
        seed = self.panel["main"]["hidden"][0]["world_seed"]
        with self.assertRaisesRegex(AssertionError, "BASE prompt"):
            CC.generate(historical_prompts=[p])
        with self.assertRaisesRegex(AssertionError, "world seed"):
            CC.generate(historical_seeds=[seed])

    def test_cli_commitments_regeneration_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            cfg = folder / "PANEL.json"
            cfg.write_text(json.dumps(CC.DEFAULT_CONFIG, sort_keys=True))
            hubs = [folder / "first", folder / "second"]
            for hub in hubs:
                proc = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/cc_generate.py"),
                                       "--hub", str(hub), "--config", str(cfg)], capture_output=True, text=True)
                self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
                commitment = json.loads((hub / "data/COMMITMENT.json").read_text())
                self.assertEqual(commitment["calls"], {"main": 2304, "smoke": 36})
                self.assertEqual(commitment["targets"], {"main": 1088, "smoke": 12})
                for relative, expected in commitment["files_sha256"].items():
                    self.assertEqual(hashlib.sha256((hub / "data" / relative).read_bytes()).hexdigest(), expected)
                for part in ("main", "smoke"):
                    stage = json.loads((hub / f"data/COMMITMENT-{part}.json").read_text())
                    self.assertEqual(stage["calls_sha256"], commitment["files_sha256"][part + "-calls.jsonl"])
            for file in (hubs[0] / "data").rglob("*"):
                if file.is_file():
                    self.assertEqual(file.read_bytes(), (hubs[1] / "data" / file.relative_to(hubs[0] / "data")).read_bytes())
            unchanged = (hubs[0] / "data/COMMITMENT.json").read_bytes()
            proc = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/cc_generate.py"), "--hub", str(hubs[0]),
                                   "--config", str(cfg)], capture_output=True, text=True)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("refusing to overwrite", proc.stdout + proc.stderr)
            self.assertEqual((hubs[0] / "data/COMMITMENT.json").read_bytes(), unchanged)


if __name__ == "__main__":
    unittest.main()
