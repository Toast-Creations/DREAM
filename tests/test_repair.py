"""No-model tests for V1.8.2: engine v0.2 patch, frozen normaliser, one-retry policy, prose equivalence, pipeline."""
import collections
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from dream_core import localpaths as LP  # public release: local paths from environment
RUNS = Path(os.environ.get("DREAM_RUNS", f"{LP.RUNS}"))

from tempo import engine as E, engine_fixtures as EF, enumcheck, prose_study as P, repair as RP  # noqa: E402

PY = sys.executable
DELIV = {"domain": "delivery", "places": ["P", "Q", "R"], "roads": [["P", "Q", 1], ["Q", "R", 2]], "closed": [],
         "agent_at": "P", "crates": ["A", "B", "C"], "non_portable": []}


def rec(rid, kind, e, r, payload, status="verified"):
    return {"rid": rid, "kind": kind, "status": status, "event_at": e, "received_at": r, "payload": payload}


INIT = rec("r01", "initial", 0, 0, {"assign": {"A.location": "P", "B.location": "Q"}}, status="provisional")


def load(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]


def run(*args):
    r = subprocess.run([PY, "-B", *map(str, args)], cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        raise AssertionError(r.stdout + r.stderr)
    return r.stdout


class EngineV02(unittest.TestCase):
    @unittest.skipUnless((RUNS / "temporal-history-interpretation-20261105-100708").is_dir(), "saved run hub not present; set DREAM_RUNS to the run archive")
    def test_observed_keyerror_paths_are_typed_rejections(self):
        """Development replay of the two milestone-2 records that raised KeyError in v0.1."""
        hub = RUNS / "temporal-history-interpretation-20261105-100708"
        hs = {h["history_id"]: h for h in load(hub / "data" / "hist-histories.jsonl")}
        rows = load(hub / "analysis-hist" / "records.jsonl")
        seen = []
        for hid in ("hist-ass-stock-p2-15", "hist-ass-slot-p6-22"):
            h = hs[hid]
            eng = E.Engine(EF.spec_from_world(h["world"], h["domain"], h["records"]), hid)
            for r in sorted((x for x in rows if x["history_id"] == hid), key=lambda x: x["k"]):
                n = r["normalised"]
                head, ver = eng.log.head(), eng.log.version
                try:
                    eng.ingest_report(n)
                except E.RecordRejected as e:
                    self.assertEqual((eng.log.head(), eng.log.version), (head, ver))
                    if "KeyError" in (r["engine_reason"] or ""):
                        seen.append(e.code)  # v0.1 crashed here; v0.2 gives a typed rejection
        # stock-p2-15 r2: missing prior state; slot-p6-22 r6 (one-option unrecorded result) now fails the schema
        self.assertEqual(sorted(seen), ["missing_prior_state", "schema"])

    def test_event_after_failed_initial_then_valid_observation(self):
        eng = E.Engine(DELIV)
        with self.assertRaises(E.RecordRejected) as c:
            eng.ingest_report(rec("r02", "change", 3, 3, {"field": "C.location", "from": "R", "to": "Q"}))
        self.assertEqual(c.exception.code, "missing_prior_state")
        self.assertEqual(eng.log.version, 0)
        eng.ingest_report(rec("r03", "observation", 4, 4, {"field": "C.location", "value": "Q"}))
        self.assertEqual(eng.view("current", 5)["per_field"]["C.location"], "Q")

    def test_bad_types_are_typed_rejections(self):
        eng = E.Engine(DELIV)
        eng.ingest_report(dict(INIT, status="verified"))
        bad = [rec("r02", "observation", "4", 4, {"field": "A.location", "value": "P"}),
               rec("r02", "observation", None, 4, {"field": "A.location", "value": "P"}),
               rec("r02", "observation", 4, 4, {"field": 7, "value": "P"}),
               rec("r02", "observation", 4, 4, {"field": "A.location", "value": 3}),
               rec("r02", "uncertain_change", 4, 4, {"field": "A.location", "from": "P", "options": "Q"}),
               rec("r02", "initial", 4, 4, {"assign": []}),
               rec("r02", "correction", 0, 4, {"target": "r01", "field": "A.location", "value": "Q",
                                                "valid_from": 0, "valid_to": None}),
               rec("r02", "correction", None, 4, {"target": 1, "field": "A.location", "value": "Q",
                                                   "valid_from": 0, "valid_to": None}),
               dict(rec("r02", "observation", 4, 4, {"field": "A.location", "value": "P"}), rid=5)]
        for b in bad:
            with self.assertRaises(E.RecordRejected):
                eng.ingest_report(b)
        self.assertEqual(eng.log.version, 1)

    def test_internal_failure_is_not_a_rejection(self):
        eng = E.Engine(DELIV)
        with mock.patch.object(enumcheck, "supported", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                eng.ingest_report(INIT)
        self.assertEqual(eng.log.version, 0)
        with self.assertRaises(ValueError):
            E.RecordRejected("x", code="not-a-code")

    def test_unprocessed_correction_marks_incomplete_not_complete(self):
        eng = E.Engine(DELIV)
        eng.ingest_report(INIT)
        text = "r02 (came in at time 6): verified correction to r01: r01 was mistaken about where crate A was."
        eng.record_unprocessed("r02", 6, text, {"kind": "correction"}, "correction_event_at", "m")
        v = eng.view("current", 8)
        self.assertEqual(v["per_field"]["A.location"], "P")  # old-policy value still there
        self.assertEqual(v["complete_per_field"]["A.location"], "incomplete")
        self.assertEqual(v["complete_per_field"]["B.location"], "Q")
        b = eng.branch(8)
        chk = eng.check_action(b, ["take", "A"])
        self.assertEqual((chk["verdict"], chk["verdict_ignoring_pending"]), ("unresolved_pending", "allowed"))
        self.assertEqual(eng.check_action(b, ["take", "B"])["verdict"], "blocked")  # B at Q: known false, complete
        self.assertEqual(b.summary()["A.location"], "incomplete")
        self.assertEqual(eng.view("earlier", 0, cutoff=5)["incomplete_fields"], [])  # pending arrived at 6

    def test_unprocessed_without_identifiable_scope_is_context_wide(self):
        eng = E.Engine(DELIV)
        eng.ingest_report(INIT)
        eng.record_unprocessed("r02", 6, "something garbled", None, "parse", "no json")
        v = eng.view("current", 8)
        self.assertTrue(v["context_incomplete"])
        self.assertTrue(all(x == "incomplete" for x in v["complete_per_field"].values()))
        # a prerequisite known false on any value of the unknown fields still blocks? take A needs A at P: widened
        self.assertEqual(eng.check_action(eng.branch(8), ["go", "P", "R"])["verdict"], "blocked")  # no road: known

    def test_pending_survives_save_load_and_contexts_are_separate(self):
        eng = E.Engine(DELIV, "x")
        eng.ingest_report(INIT)
        eng.record_unprocessed("r02", 6, "crate B moved", None, "parse", "no json")
        other = E.Engine(DELIV, "y")
        other.ingest_report(INIT)
        self.assertEqual(other.view("current", 8)["incomplete_fields"], [])
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "l.jsonl")
            eng.save(p)
            back = E.Engine.load(p)
            self.assertEqual(back.view("current", 8), eng.view("current", 8))
            self.assertEqual(back.log.head(), eng.log.head())
        b = eng.branch(8)
        before = [dict(s) for s in b.states]
        eng.predict_action(b, ["take", "A"])
        self.assertEqual(b.states, before)

    @unittest.skipUnless((RUNS / "temporal-pilot-20261104-232811").is_dir(), "saved run hub not present; set DREAM_RUNS to the run archive")
    def test_old_run_hashes_preserved(self):
        for hub, sets in (("temporal-pilot-20261104-232811", ("main", "smoke")),
                          ("temporal-diagnostic-20261105-081325", ("diag", "diagsmoke")),
                          ("temporal-precondition-probe-20261105-085932", ("probe", "probesmoke")),
                          ("temporal-history-interpretation-20261105-100708", ("hist", "histsmoke"))):
            for s in sets:
                cm = json.loads((RUNS / hub / "data" / f"COMMITMENT-{s}.json").read_text())
                h = hashlib.sha256((RUNS / hub / "data" / f"{s}-calls.jsonl").read_bytes()).hexdigest()
                self.assertEqual(h, cm["calls_sha256"], (hub, s))


REG = {"A.location": ["P", "Q", "R", "carried by you"], "B.location": ["P", "Q", "R", "carried by you"]}


class Normaliser(unittest.TestCase):
    def test_equivalences_applied_and_logged(self):
        obj = {"rid": "r02", "kind": "correction", "status": "verified", "event_at": "0", "received_at": "6",
               "payload": {"target": "r01", "field": "A.location", "value": "crate q.", "valid_from": 0,
                           "valid_to": None}, "evidence": "x", "note": "extra"}
        r, log = RP.normalise(obj, REG)
        self.assertEqual((r["event_at"], r["received_at"], r["payload"]["value"]), (None, 6, "Q"))
        self.assertEqual(sorted(x["rule"] for x in log), ["N0", "N1", "N2", "N2", "N3"])
        self.assertNotIn("note", r)

    def test_counterexamples_left_alone(self):
        cases = [
            # correction event_at differs from valid_from: conflicting times, not redundant
            ({"kind": "correction", "event_at": 3, "payload": {"target": "r01", "field": "A.location", "value": "Q",
                                                                "valid_from": 0, "valid_to": None}}, "event_at", 3),
            # missing observation time is not inferred
            ({"kind": "observation", "event_at": None, "payload": {"field": "A.location", "value": "Q"}},
             "event_at", None),
            ({"kind": "observation", "event_at": "4.0", "payload": {"field": "A.location", "value": "Q"}},
             "event_at", "4.0"),
            ({"kind": "observation", "event_at": "about 4", "payload": {"field": "A.location", "value": "Q"}},
             "event_at", "about 4"),
        ]
        for obj, key, want in cases:
            o = dict({"rid": "r02", "status": "verified", "received_at": 6}, **obj)
            r, log = RP.normalise(o, REG)
            self.assertEqual(r[key], want)
        # kind, entity, target, values and options are never changed or invented
        o = {"rid": "r02", "kind": "uncertain_change", "status": "verified", "event_at": 3, "received_at": 3,
             "payload": {"field": "A.location", "from": "P", "options": ["Q"]}}
        r, log = RP.normalise(o, REG)
        self.assertEqual(r["payload"]["options"], ["Q"]); self.assertEqual(r["kind"], "uncertain_change")
        o = {"rid": "r02", "kind": "change", "status": "verified", "event_at": 3, "received_at": 3,
             "payload": {"field": "Z.location", "from": "P", "to": "Mars"}}
        r, log = RP.normalise(o, REG)
        self.assertEqual(r["payload"], o["payload"]); self.assertEqual(log, [])


class RetryPolicy(unittest.TestCase):
    def setUp(self):
        self.spec = DELIV
        self.texts = {1: "r01 text names crate A and crate B", 2: "r02 text about crate A"}
        self.prompts = {1: "PROMPT-1", 2: "PROMPT-2"}
        self.regs = {1: REG, 2: REG}

    def run_(self, init, retry):
        calls = []

        def fn(k, prompt):
            calls.append((k, prompt))
            return retry.get(k)
        rows, eng = RP.run_branch(self.spec, "t", self.texts, self.prompts, self.regs, init, retry_fn=fn,
                                  now_of=lambda k: {1: 0, 2: 6}[k])
        return rows, eng, calls

    def test_retry_only_on_rejection_once_and_no_gold_in_feedback(self):
        good1 = json.dumps(INIT)
        bad2 = json.dumps(rec("r02", "observation", None, 6, {"field": "A.location", "value": "P"}))
        fix2 = json.dumps(rec("r02", "observation", 6, 6, {"field": "A.location", "value": "P"}))
        rows, eng, calls = self.run_({1: good1, 2: bad2}, {2: fix2})
        self.assertEqual([k for k, _ in calls], [2])
        fp = calls[0][1]
        self.assertTrue(fp.startswith("PROMPT-2\n\nYour previous reply:\n" + bad2))
        self.assertIn(E.REJECT_CODES["time_type"], fp)
        self.assertNotIn(fix2, fp)
        self.assertTrue(rows[1]["final"]["accepted"])

    def test_schema_valid_semantic_error_is_not_caught(self):
        wrong = json.dumps(rec("r02", "observation", 6, 6, {"field": "B.location", "value": "Q"}))  # wrong crate
        rows, eng, calls = self.run_({1: json.dumps(INIT), 2: wrong}, {})
        self.assertEqual(calls, [])
        self.assertTrue(rows[1]["final"]["accepted"])

    def test_failed_retry_is_registered_and_not_backfilled(self):
        bad = "not json"
        rows, eng, calls = self.run_({1: json.dumps(INIT), 2: bad}, {2: "still not json"})
        self.assertEqual(len(calls), 1)
        self.assertFalse(rows[1]["final"]["accepted"])
        self.assertEqual([p["rid"] for p in eng.pending()], ["r02"])
        self.assertEqual(eng.view("current", 8)["complete_per_field"]["A.location"], "incomplete")
        self.assertEqual(eng.log.version, 2)  # one record + one pending entry; nothing invented


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.hub = Path(cls.tmp.name)
        for s in ("prose", "prosesmoke"):
            run("scripts/prose_generate.py", "--hub", cls.hub, "--set", s)
        d = cls.hub / "data"
        cls.hs = load(d / "prose-histories.jsonl")
        cls.calls = {c["call_id"]: c for c in load(d / "prose-calls.jsonl")}
        cls.gold = {g["call_id"]: g for g in load(d / "prose-gold.jsonl")}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()


class Prose(Base):
    def test_matrix(self):
        self.assertEqual(len(self.hs), 24)
        self.assertEqual(collections.Counter(c["surface"] for c in self.calls.values()), {"lines": 144, "prose": 144})
        self.assertEqual(len(load(self.hub / "data" / "prosesmoke-calls.jsonl")), 18)

    def test_every_prose_record_passes_and_counterexamples_fail(self):
        for h in self.hs:
            for r, t in zip(h["records"], h["texts"]["prose"]):
                P.check_equivalent(r, t)
        h = self.hs[0]
        r, t = h["records"][2], h["texts"]["prose"][2]
        for bad in (t.replace(f"time {r['event_at']}", "a while ago") if r["kind"] != "correction" else t,
                    t.replace(r["rid"], "a message")):
            if bad != t:
                with self.assertRaises(AssertionError):
                    P.check_equivalent(r, bad)
        prov = next((h, i) for h in self.hs for i, r in enumerate(h["records"]) if r["status"] == "provisional")
        hh, i = prov
        with self.assertRaises(AssertionError):
            P.check_equivalent(hh["records"][i], hh["texts"]["prose"][i].replace("provisional", "confirmed"))

    def test_same_instruction_both_surfaces(self):
        for h in self.hs:
            for k in range(1, 7):
                a = self.calls[f"{h['history_id']}|lines|r{k}"]["user"]
                b = self.calls[f"{h['history_id']}|prose|r{k}"]["user"]
                for i in range(k):
                    a = a.replace(h["texts"]["lines"][i], "<REC>")
                    b = b.replace(h["texts"]["prose"][i], "<REC>")
                self.assertEqual(a, b)
                for tok in ("_src", "ordinal", "gold", "true_state", "hidden"):
                    self.assertNotIn(tok, b)


def perfect(g):
    return json.dumps(dict(g["gold"], evidence=g["text"][-30:]))


class Pipeline(Base):
    def fake(self, initial, retries, tag):
        (self.hub / f"i-{tag}.json").write_text(json.dumps(initial))
        (self.hub / f"r-{tag}.json").write_text(json.dumps(retries))
        cfg = self.hub / "cfg.json"
        cfg.write_text(json.dumps({"set": "prose", "select": "all", "order_seed": 1, "max_seconds": 600,
                                   "max_calls": 999, "max_input_tokens": 8192, "retry_limit": 1, "max_retries": 288,
                                   "model": {}}))
        run("scripts/tempo_run.py", "--hub", self.hub, "--stage", f"init-{tag}", "--config", cfg, "--fake",
            self.hub / f"i-{tag}.json")
        run("scripts/repair_run.py", "--hub", self.hub, "--set", "prose", "--initial-stage", f"init-{tag}",
            "--stage", f"retry-{tag}", "--config", cfg, "--fake", self.hub / f"r-{tag}.json")
        run("scripts/repair_analyze.py", "--hub", self.hub, "--set", "prose", "--initial-stage", f"init-{tag}",
            "--retry-stage", f"retry-{tag}", "--boot", "200")
        res = json.loads((self.hub / "analysis-prose" / "ANALYSIS.json").read_text())
        recs = load(self.hub / "analysis-prose" / "records.jsonl")
        cps = load(self.hub / "analysis-prose" / "checkpoints.jsonl")
        return res, recs, cps

    def test_perfect_and_injected(self):
        init = {c: perfect(g) for c, g in self.gold.items()}
        res, _, _ = self.fake(init, {}, "perfect")
        for k, d in res["cells"].items():
            self.assertEqual(d["final_exact_count"], "24/24", k)
            self.assertEqual(d["verdict_correct"], "144/144", k)
        self.assertEqual(res["retry_calls"], 0)
        # injections on the prose surface
        by = collections.defaultdict(list)
        for c, g in self.gold.items():
            if c.split("|")[1] == "prose":
                by[g["gold"]["kind"]].append(c)
        inj, rep = dict(init), {}
        c1, c2, c3 = by["correction"][:3]
        g = json.loads(init[c1]); g["event_at"] = g["payload"]["valid_from"]; inj[c1] = json.dumps(g)  # N3 fixes
        g = json.loads(init[c2]); g["event_at"] = 99; inj[c2] = json.dumps(g)  # rejected -> retry -> fixed
        rep[c2 + "|retry"] = init[c2]
        g = json.loads(init[c3]); g["event_at"] = 99; inj[c3] = json.dumps(g)  # rejected -> retry fails
        rep[c3 + "|retry"] = "no json here"
        ob = by["observation"][0]
        g = json.loads(init[ob]); g["event_at"] = None; inj[ob] = json.dumps(g)  # rejected -> valid-looking wrong
        w = json.loads(init[ob]); w["event_at"] = w["event_at"]; rep[ob + "|retry"] = json.dumps(dict(w, rid=w["rid"]))
        wv = json.loads(init[ob]); wv["payload"]["value"] = [x for x in self.gold[ob]["registry"][wv["payload"]["field"]]
                                                              if x != wv["payload"]["value"]][0]
        rep[ob + "|retry"] = json.dumps(wv)
        res, recs, cps = self.fake(inj, rep, "inj")
        rr = {(r["call_id"], r["policy"]): r for r in recs}
        self.assertTrue(rr[(c1, "no_retry")]["initial_accepted"])
        self.assertIn("N3", [n["rule"] for n in rr[(c1, "no_retry")]["initial_norm"]])
        self.assertFalse(rr[(c2, "no_retry")]["final_accepted"])
        self.assertTrue(rr[(c2, "one_retry")]["final_accepted"] and rr[(c2, "one_retry")]["final_exact"])
        self.assertFalse(rr[(c3, "one_retry")]["final_accepted"])
        self.assertTrue(rr[(ob, "one_retry")]["final_accepted"])
        self.assertFalse(rr[(ob, "one_retry")]["final_exact"])  # a valid-looking wrong repair is still a failure
        cell = res["cells"]["prose:one_retry"]["records"]
        # cascade: the accepted wrong repair makes a later correct record inconsistent in that branch
        casc = [r for r in recs if r["policy"] == "one_retry" and r["history_id"] == ob.split("|")[0]
                and r["surface"] == "prose" and r["k"] > rr[(ob, "one_retry")]["k"] and r["initial_exact"]
                and r["initial_code"] == "inconsistent"]
        self.assertEqual(len(casc), 1)
        self.assertEqual(cell["retried"], 4)
        self.assertGreaterEqual(cell["retry_accepted_but_wrong"], 1)
        self.assertEqual(res["retry_calls"], 4)
        # the unprocessed correction leaves its field incomplete at the final checkpoint (not silently complete)
        hid = c3.split("|")[0]
        fin = next(c for c in cps if c["history_id"] == hid and c["surface"] == "prose" and c["policy"] == "one_retry"
                   and c["k"] == 6)
        self.assertIn("incomplete", fin["aware"].values())
        self.assertEqual(res["cells"]["lines:no_retry"]["final_exact_count"], "24/24")


if __name__ == "__main__":
    unittest.main()
