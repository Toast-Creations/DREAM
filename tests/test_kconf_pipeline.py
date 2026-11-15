"""No-model pipeline fixtures for V1.22.0: a small TEST-SEED panel in a temp dir (never a confirmation panel), with
synthetic stage artifacts in the runner's own schema (LOCK.json, END.json / STOP.json, attempts.jsonl, per-call
records) plus DEADLINE / RESOURCE-GUARD / FROZEN-PROTOCOL. Checks: the analyzer's infrastructure gate (completion,
resources, freeze, records = schedule, recipe), per-component frozen rules, scoring of both acts and gate arithmetic."""
import copy
import hashlib
import json
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from dream_core.ledger import release_source_hash  # noqa: E402
from tempo import factored as FA, holdout as HO, keepid as KI, kidconfdone as KD, refres as RR  # noqa: E402
import kconf_analyze as KA  # noqa: E402
import kconf_generate as KGEN  # noqa: E402

CFG = {"base_seed": 999001, "pool": "kctest", "smoke_base_seed": 999002, "smoke_pool": "kctests",
       "consonants": "bcdfhjk", "id_prefix": "t22-g", "smoke_prefix": "t22-s", "n_correction_groups": 16,
       "n_arrival_groups": 8, "smoke_groups": 4, "schedule_seed": 999003}
MODEL = {"revision": KA.PIN["revision"], "quantization": "nf4", "enable_thinking": False, "decoding": "greedy",
         "dtype": "bfloat16", "load": {"devices": ["cuda:0"], "quantization": {"bnb_4bit_compute_dtype": "bfloat16",
                                                                             "bnb_4bit_use_double_quant": True}}}
PLAN = {"arrival": {"rule": ["P", 0.025], "threshold": "0"}, "correction": {"rule": ["P", 0.01], "threshold": "-3/64"},
        "reference": ["P", 0.025], "B": 1000, "seed": 5}
SRC = release_source_hash(ROOT)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def canonical(h):
    return dict(FA.canonical_factored(HO.public(h["case"])[-1]), evidence=h["case"]["text"][-25:])


def stamp(epoch):
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(epoch))


class Pipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.td = tempfile.TemporaryDirectory()
        cls.base = Path(cls.td.name) / "base"
        out = KGEN.generate(dict(CFG))
        cls.out = out
        data = cls.base / "data"
        for part, (groups, pubs, hid, calls, rej) in out.items():
            KGEN.write(data / f"public/{part}-targets.jsonl", pubs)
            KGEN.write(data / f"hidden/{part}-cases.jsonl", hid)
            KGEN.write(data / f"{part}-calls.jsonl", calls)
            (data / f"COMMITMENT-{part}.json").write_text(json.dumps(
                {"set": part, "calls": len(calls), "calls_sha256": sha(data / f"{part}-calls.jsonl")}))
        cfgd = cls.base / "config"
        cfgd.mkdir()
        for part in ("smoke", "main"):
            (cfgd / f"stage-{part}.json").write_text(json.dumps({"set": part, "select": [c["call_id"] for c in out[part][3]]}))
        (cfgd / "RESOURCE-GUARD.json").write_text(json.dumps({"total_attempts": 128, "ceiling_s": 43200,
                                                              "feasibility_slowdown": 1.1, "main_overhead_s": 600,
                                                              "retry_limit": 0}))
        (cfgd / "FROZEN-PROTOCOL.json").write_text(json.dumps({"source_sha256": SRC,
                                                               "analysis_plan_sha256": KD.plan_sha256(PLAN)}))
        cls.hid = {h["target"]: h for part in out.values() for h in part[2]}
        cls.n = 0

    @classmethod
    def tearDownClass(cls):
        cls.td.cleanup()

    def hub(self, reply_for=None, deadline_offset=3600, skip=(), bad_recipe=(), end=True, finished=True,
            stop=False, attempts=0, fake=False, late_record=False, late_end=False, extra=False, duplicate=False):
        """Fresh copy of the base hub with synthetic stage artifacts."""
        Pipeline.n += 1
        hub = Path(self.td.name) / f"h{Pipeline.n}"
        shutil.copytree(self.base, hub)
        now = time.time()
        dl = int(now + deadline_offset)
        (hub / "config" / "DEADLINE.json").write_text(json.dumps({"driver_start_epoch": int(now) - 60, "deadline_epoch": dl}))
        reply_for = reply_for or (lambda tid, arm: canonical(self.hid[tid]))
        for st in ("smoke", "main"):
            sd = hub / "stages" / st
            (sd / "calls").mkdir(parents=True)
            (sd / "LOCK.json").write_text(json.dumps({"config_sha256": sha(hub / "config" / f"stage-{st}.json"),
                                                      "calls_sha256": json.loads((hub / "data" / f"COMMITMENT-{st}.json").read_text())["calls_sha256"],
                                                      "source_sha256": SRC, "fake": fake}))
            for c in self.out[st][3]:
                if c["call_id"] in skip:
                    continue
                tid, arm = c["call_id"].rsplit("|", 1)
                m = copy.deepcopy(MODEL)
                if c["call_id"] in bad_recipe:
                    m["quantization"] = "bf16"
                r = {"call_id": c["call_id"], "status": "ok", "stop": "eos", "raw": json.dumps(reply_for(tid, arm)),
                     "user_sha256": c["user_sha256"], "model": m, "max_new_tokens": 256, "attempts": 1,
                     "complete": True, "input_tokens": 1400, "output_tokens": 140, "seconds": 12.0,
                     "finished_at": stamp(dl + 5 if late_record and st == "main" else now)}
                (sd / "calls" / (c["call_id"].replace("|", "__") + ".json")).write_text(json.dumps(r))
            if st == "main" and duplicate:
                c = self.out[st][3][0]
                src = sd / "calls" / (c["call_id"].replace("|", "__") + ".json")
                (sd / "calls" / "dup-copy.json").write_text(src.read_text())
            if st == "main" and extra:
                (sd / "calls" / "extra.json").write_text(json.dumps({"call_id": "t22-g9999|arrival|A|SUB", "status": "ok"}))
            if end:
                (sd / "END.json").write_text(json.dumps({"finished": finished,
                                                         "at": stamp(dl + 5 if late_end and st == "main" else now)}))
            if stop and st == "main":
                (sd / "STOP.json").write_text(json.dumps({"finished": False, "stop_reason": "max_seconds"}))
            if attempts and st == "main":
                (sd / "attempts.jsonl").write_text("".join(json.dumps({"call_id": "x", "attempt": i + 1}) + "\n"
                                                           for i in range(attempts)))
        return hub

    def assertIncomplete(self, hub, needle):
        res, _ = KA.analyze(hub, PLAN)
        self.assertEqual(res["status"], "INCOMPLETE")
        self.assertNotIn("gates", res)
        self.assertNotIn("qualification", res)
        self.assertTrue(any(needle in p for p in res["infrastructure"]["problems"]), res["infrastructure"]["problems"])
        return res

    # ---------------------------------------------------------------- construction
    def test_structure(self):
        groups, pubs, hid, calls, rej = self.out["main"]
        self.assertEqual(len(calls), 4 * 16 + 4 * 8)
        self.assertEqual(len(self.out["smoke"][3]), 32)
        self.assertFalse({p["group"] for p in pubs} & {p["group"] for p in self.out["smoke"][1]})
        self.assertFalse({h["world_seed"] for h in hid} & {h["world_seed"] for h in self.out["smoke"][2]})
        for p in pubs:
            sub = next(c for c in calls if c["call_id"] == p["target"] + "|SUB")["user"]
            keep = next(c for c in calls if c["call_id"] == p["target"] + "|KEEP")["user"]
            led = p["identity"]
            self.assertEqual(KI.strip_annotation(keep, led["keep_ledger"]["annotation"]), p["base_prompt"])
            self.assertEqual(sub, RR.rewrite_prompt(p["base_prompt"], p["target_text"],
                                                    RR.rewrite(p["target_text"], led["detection"], led["field"])[0]))
            self.assertEqual(led["field"], self.hid[p["target"]]["gold_field"])

    def test_disjointness_assertions(self):
        pubs = self.out["main"][1]
        for kw in ({"historical_prompts": [pubs[0]["base_prompt"]]},
                   {"historical_seeds": [self.out["main"][2][0]["world_seed"]]}):
            with self.assertRaises(SystemExit):
                KGEN.generate(dict(CFG), **kw)
        for bad in ({"id_prefix": "g0"}, {"smoke_pool": CFG["pool"]}):
            with self.assertRaises(SystemExit):
                KGEN.generate(dict(CFG, **bad))

    # ---------------------------------------------------------------- legitimate completion
    def test_valid_completed_run(self):
        res, rows = KA.analyze(self.hub(), PLAN)
        self.assertEqual(res["status"], "COMPLETE", res["infrastructure"]["problems"])
        self.assertTrue(all(r["exact"] for r in rows.values()))
        self.assertEqual(res["gates"]["arrival"]["estimate_exact"], "0")
        self.assertFalse(res["gates"]["arrival"]["pass"])
        self.assertEqual(res["gates"]["arrival"]["rule"], ["P", 0.025])
        self.assertEqual(res["gates"]["correction"]["rule"], ["P", 0.01])      # per-component rules applied
        self.assertIn("reference_95_interval_not_the_gate", res["gates"]["correction"])
        self.assertFalse(res["qualification"]["qualifies"])

    def test_keep_wins_arrivals_loses_corrections(self):
        def reply(tid, arm):
            h = self.hid[tid]
            can = canonical(h)
            if arm == "SUB" and h["act"] == "arrival":
                st = {"field": h["gold_field"], "at": h["case"]["records"][-1]["event_at"], "value": "yes"}
                return dict(can, events=[], states=[st])
            if arm == "KEEP" and h["act"] == "correction" and h["group"].endswith("1"):
                return dict(can, events=[], states=[], revisions=[])
            return can
        res, _ = KA.analyze(self.hub(reply), PLAN)
        self.assertEqual(res["status"], "COMPLETE")
        d = res["descriptives"]
        self.assertEqual((d["arrival|SUB"]["exact"], d["arrival|KEEP"]["exact"]), (0, 16))
        self.assertEqual(d["arrival|SUB"]["state_only_accepted"], 16)
        self.assertEqual(d["correction|KEEP"]["empty_extraction"], 32 - d["correction|KEEP"]["exact"])
        self.assertTrue(res["gates"]["arrival"]["pass"])
        self.assertFalse(res["gates"]["correction"]["pass"])
        self.assertFalse(res["qualification"]["qualifies"])

    # ---------------------------------------------------------------- incomplete / failed runs
    def test_all_records_but_no_end(self):
        self.assertIncomplete(self.hub(end=False), "no END.json")

    def test_unfinished_end(self):
        self.assertIncomplete(self.hub(finished=False), "not finished")

    def test_stop_present(self):
        self.assertIncomplete(self.hub(stop=True), "STOP.json")

    def test_end_after_deadline(self):
        self.assertIncomplete(self.hub(late_end=True), "END after the deadline")

    def test_record_after_deadline(self):
        self.assertIncomplete(self.hub(late_record=True), "after the deadline")

    def test_over_attempt_budget(self):
        res = self.assertIncomplete(self.hub(attempts=3), "attempt budget exceeded")
        self.assertTrue(any("logged failed attempts" in p for p in res["infrastructure"]["problems"]))

    def test_fake_lock(self):
        self.assertIncomplete(self.hub(fake=True), "LOCK")

    def test_missing_record(self):
        self.assertIncomplete(self.hub(skip={self.out["main"][3][3]["call_id"]}), "missing")

    def test_extra_and_duplicate_records(self):
        self.assertIncomplete(self.hub(extra=True), "extra")
        self.assertIncomplete(self.hub(duplicate=True), "duplicate")

    def test_recipe_mismatch(self):
        self.assertIncomplete(self.hub(bad_recipe={self.out["main"][3][0]["call_id"]}), "recipe")

    def test_unfrozen_or_changed_source(self):
        h = self.hub()
        (h / "config" / "FROZEN-PROTOCOL.json").unlink()
        self.assertIncomplete(h, "FROZEN-PROTOCOL")
        h = self.hub()
        (h / "config" / "FROZEN-PROTOCOL.json").write_text(json.dumps({"source_sha256": "0" * 64}))
        self.assertIncomplete(h, "source")

    def test_changed_plan_is_exploratory_only(self):
        alt = dict(PLAN, correction={"rule": ["P", 0.0125], "threshold": "-3/64"})
        res, _ = KA.analyze(self.hub(), alt)
        self.assertEqual(res["status"], "EXPLORATORY")
        self.assertNotIn("qualification", res)
        self.assertNotIn("gates", res)
        self.assertIn("exploratory_gates_not_confirmatory", res)
        h = self.hub()                                # frozen plan hash absent -> exploratory too
        (h / "config" / "FROZEN-PROTOCOL.json").write_text(json.dumps({"source_sha256": SRC}))
        res, _ = KA.analyze(h, PLAN)
        self.assertEqual(res["status"], "EXPLORATORY")
        self.assertNotIn("qualification", res)

    # ---------------------------------------------------------------- recipe schema
    def test_plan_schema(self):
        KD.validate_plan(PLAN)
        bad = [dict(PLAN, rule=["P", 0.025]),                                            # legacy common rule key
               {k: v for k, v in PLAN.items() if k != "correction"},
               dict(PLAN, correction={"rule": ["P", 0.01], "threshold": "-1/16"}),         # widened margin
               dict(PLAN, arrival={"rule": ["Z", 0.025], "threshold": "0"}),
               dict(PLAN, reference=["P", 0.01]),
               dict(PLAN, B=100)]
        for p in bad:
            with self.assertRaises((ValueError, KeyError, TypeError)):
                KD.validate_plan(p)
            with self.assertRaises((ValueError, KeyError, TypeError)):
                KA.analyze(self.base, p)


if __name__ == "__main__":
    unittest.main()
