"""CPU-only CCONF-v1 sparse membership, integrity, exact integration and reports."""
from datetime import datetime
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from dream_core.ledger import release_source_hash  # noqa: E402
from tempo import bounded_mean as BM, clarconfirm as CC, factored as FA, holdout as HO  # noqa: E402
import cc_analyze as A  # noqa: E402
import cc_stage_check as SC  # noqa: E402


def dump(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=1)+"\n")


def jsonl(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True)+"\n" for row in rows))


def canonical_fixture(hub, panel):
    """Production-size schedule, canonical replies, fixture-only recipe declarations."""
    hub = Path(hub)
    dump(hub / "config/PANEL.json", CC.DEFAULT_CONFIG)
    dump(hub / "config/ANALYSIS-PLAN.json", A.DEFAULT_PLAN)
    dump(hub / "config/RULE.json", BM.rule_config())
    dump(hub / "config/RESOURCE-GUARD.json", A.cc_guard.POLICY)
    (hub / "design").mkdir()
    (hub / "design/FIXTURE.md").write_text("CPU-only canonical-response fixture; no model execution.\n")
    dump(hub / "phase0/VALIDATION.json", {"all_pass": True, "scope": "CPU fixture"})
    (hub / "run_cc.sh").write_text("# CPU fixture only\n")
    manifest = hub / "fixture-model-manifest.json"
    manifest.write_text('{}\n')
    jsonl(hub / "data/ALLOCATION.jsonl", panel["main"]["plan"]+panel["smoke"]["plan"])
    jsonl(hub / "data/ALLOWED-CALLS.jsonl", CC.allowed_manifest(panel))
    start = datetime.fromisoformat("2026-11-11T07:00:00-05:00")
    dump(hub / "config/DEADLINE.json", {"driver_start_epoch": start.timestamp(), "deadline_epoch": start.timestamp()+43200,
                                       "deadline_iso": "2026-11-11T19:00:00-05:00", "timezone": "America/New_York"})
    model = {"revision": A.PIN["revision"], "quantization": "nf4", "enable_thinking": False,
             "decoding": "greedy", "dtype": "bfloat16", "load": {"devices": ["cuda:0"], "quantization": {
                 "bnb_4bit_compute_dtype": "bfloat16", "bnb_4bit_use_double_quant": True}}}
    source_hash = release_source_hash(ROOT)
    for stage in ("main", "smoke"):
        part = panel[stage]
        calls = part["calls"]
        jsonl(hub / f"data/{stage}-calls.jsonl", calls)
        jsonl(hub / f"data/public/{stage}-targets.jsonl", part["public"])
        jsonl(hub / f"data/hidden/{stage}-cases.jsonl", part["hidden"])
        commitment = {"calls_sha256": A.sha(hub / f"data/{stage}-calls.jsonl")}
        dump(hub / f"data/COMMITMENT-{stage}.json", commitment)
        cfg = {"set": stage, "order": "as_committed", "max_input_tokens": 2048, "retry_limit": 0,
               "max_calls": len(calls), "max_seconds": 43200, "select": [c["call_id"] for c in calls],
               "model": {"path": "/fixture/"+A.PIN["revision"], "manifest": str(manifest), "dtype": "bfloat16",
                         "device": "cuda", "enable_thinking": False, "quantization": "nf4"}}
        dump(hub / f"config/stage-{stage}.json", cfg)
        lock = {"config_sha256": A.sha(hub / f"config/stage-{stage}.json"), "calls_sha256": commitment["calls_sha256"],
                "source_sha256": source_hash, "fake": False}
        dump(hub / f"stages/{stage}/LOCK.json", lock)
        dump(hub / f"stages/{stage}/config.json", cfg)
        dump(hub / f"stages/{stage}/start-1.json", {**lock, "planned": len(calls), "todo": len(calls),
                                                   "started": "2026-11-11T07:00:01-05:00"})
        dump(hub / f"stages/{stage}/END.json", {"finished": True, "stop_reason": None, "new_this_run": len(calls),
                                               "at": "2026-11-11T07:30:00", "elapsed_s": 100.0})
        hidden = {h["target"]: h for h in part["hidden"]}
        for call in calls:
            h = hidden[call["target"]]
            raw = FA.canonical_factored(HO.public(h["case"])[-1])
            raw["evidence"] = h["case"]["text"][-25:]
            rec = {"call_id": call["call_id"], "status": "ok", "complete": True, "attempts": 1,
                   "user_sha256": call["user_sha256"], "max_new_tokens": 256, "model": model,
                   "input_tokens": 1400, "output_tokens": 150, "raw": json.dumps(raw), "stop": "eos", "seconds": 13.,
                   "finished_at": "2026-11-11T07:00:20"}
            dump(hub / f"stages/{stage}/calls" / (call["call_id"].replace("|", "__")+".json"), rec)
    dump(hub/'runtime/GUARD-smoke.json', {'stage':'smoke','planned':36,'used_attempts_conservative':0,
                                        'elapsed_s':0.,'remaining_s':43200.,'ok':True,'problems':[]})
    dump(hub/'runtime/GUARD-main.json', {'stage':'main','planned':2304,'used_attempts_conservative':36,
                                       'elapsed_s':120.,'remaining_s':43080.,'ok':True,'problems':[],
                                       'smoke_mean_s':13.,'projected_total_s':120.+13.*2304*1.1+600})
    dump(hub/'runtime/SMOKE-CHECK.json', {'pass':True,'scheduled':36,'records':36,'semantic_accuracy_used':False})
    frozen = {"study": A.STUDY, "source_sha256": source_hash, "analysis_plan_sha256": A.KD.plan_sha256(A.DEFAULT_PLAN),
              "rule_sha256": A.sha(hub / 'config/RULE.json'),
              "driver_sha256": A.sha(hub / "run_cc.sh"), "model_manifest_path": str(manifest),
              "model_manifest_sha256": A.sha(manifest)}
    for section in ("design", "config", "data", "phase0"):
        frozen[section] = {str(path.relative_to(hub / section)): A.sha(path)
                           for path in sorted((hub / section).rglob('*')) if path.is_file() and path.name != "DEADLINE.json"}
    dump(hub / "config/FROZEN-PROTOCOL.json", frozen)


def record_path(hub, call_id, stage="main"):
    return Path(hub) / f"stages/{stage}/calls" / (call_id.replace("|", "__")+".json")


class ProductionSizeFixtures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.panel = CC.generate()
        cls.base = Path(cls.temp.name) / "base"
        canonical_fixture(cls.base, cls.panel)
        cls.counter = 0

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def copy_hub(self):
        type(self).counter += 1
        hub = Path(self.temp.name) / f"case-{self.counter}"
        shutil.copytree(self.base, hub)
        # The fixture manifest is intentionally the original immutable fixture file.
        return hub

    def test_complete_ceiling_is_not_qualified_and_has_nonzero_uncertainty(self):
        result, rows, ledger = A.analyze(self.base)
        self.assertEqual(result["status"], "COMPLETE", result["infrastructure"]["problems"][:5])
        self.assertEqual(result["qualification"]["status"], "NOT_QUALIFIED")
        self.assertEqual(len(rows), 2304)
        primary = [r for r in ledger if r["kind"] == "primary"]
        self.assertEqual(collection_counts(primary), {"arrival": 224, "correction": 160})
        self.assertEqual(result["primary"]["arrival"]["evidence_exact"], "1")
        self.assertEqual(result["primary"]["arrival"]["equal_family_sensitivity"]["estimate_exact"], "0")
        self.assertFalse(result["primary"]["arrival"]["pass"])
        self.assertTrue(result["primary"]["correction"]["pass"])
        self.assertLess(result["primary"]["correction"]["lower_bound"]["upper"], 0)
        self.assertTrue(result["primary"]["correction"]["both_arms_observed_ceiling"])
        self.assertEqual(result["references"]["arrival|KEEP_CLAR_minus_SUB_CLAR"]["independent_stems"], 32)
        self.assertEqual(result["references"]["correction|KEEP_CLAR_minus_SUB_CLAR"]["independent_stems"], 16)
        self.assertEqual(result["infrastructure"]["attempts_recorded"], 2340)

    def test_qualified_semantics_and_all_reader_artifacts(self):
        hub = self.copy_hub()
        for call in self.panel["main"]["calls"]:
            if call["act"] == "arrival" and call["arm"] == "SUB_ORIG":
                path = record_path(hub, call["call_id"])
                rec = json.loads(path.read_text())
                content = json.loads(rec["raw"])
                content["events"] = []
                rec["raw"] = json.dumps(content)
                dump(path, rec)
        result = A.write_artifacts(hub)
        self.assertEqual(result["status"], "COMPLETE", result["infrastructure"]["problems"][:5])
        self.assertEqual(result["qualification"]["status"], "QUALIFIED")
        self.assertEqual(result["primary"]["arrival"]["estimate_exact"], "1")
        self.assertEqual(result["primary"]["arrival"]["paired"]["paired_counts"], {"rescue": 448})
        for filename in ("REPORT.md", "RUN-STATUS.md", "CLAIM-EVIDENCE-RESULTS.md", "READER-TAKEAWAY-RESULTS.md", "SEMANTIC-COVERAGE-RESULTS.md"):
            self.assertTrue((hub / filename).is_file())
        report = (hub / "REPORT.md").read_text()
        for required in ("Paired rescues / breaks", "Arrival", "Correction", "Matched references", "ceiling",
                         "equivalence", "America/New_York", "3/64", "Counts by family", "Counts by direction",
                         "equal-family sensitivity", "uncertainty is not estimated"):
            self.assertIn(required, report)

    def test_missing_sparse_reference_prevents_any_gates(self):
        hub = self.copy_hub()
        ref = next(c for c in self.panel["main"]["calls"] if c["arm"] == "SUB_CLAR")
        record_path(hub, ref["call_id"]).unlink()
        result, rows, ledger = A.analyze(hub)
        self.assertEqual(result["status"], "INCOMPLETE")
        self.assertEqual(result["qualification"]["status"], "NOT_EVALUATED")
        self.assertNotIn("primary", result)
        self.assertEqual(ledger, [])
        self.assertEqual(len(rows), 2304)
        self.assertEqual(sum(r["incomplete"] for r in rows), 1)

    def test_malformed_and_truncated_content_are_semantic_errors(self):
        hub = self.copy_hub()
        calls = [c for c in self.panel["main"]["calls"] if c["arm"] == "KEEP_CLAR" and c["act"] == "arrival"][:2]
        for index, call in enumerate(calls):
            path = record_path(hub, call["call_id"])
            rec = json.loads(path.read_text())
            if index == 0:
                rec["raw"] = 'not a JSON object'
            else:
                rec["stop"] = 'length'
            dump(path, rec)
        result, rows, _ = A.analyze(hub)
        self.assertEqual(result["status"], "COMPLETE", result["infrastructure"]["problems"][:5])
        for row in rows:
            if row["call_id"] in {c["call_id"] for c in calls}:
                self.assertFalse(row["incomplete"])
                self.assertFalse(row["exact"])

    def test_stage_integrity_negative_cases(self):
        main_call = self.panel["main"]["calls"][0]
        mutations = ("duplicate", "extra", "corrupt", "nonok", "partial", "prompt", "retry", "late", "stop", "end", "resume", "failed_attempt", "driver_error", "missing_guard", "bad_forecast", "missing_smoke_certificate", "unknown_stop", "invalid_time")
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                hub = self.copy_hub()
                path = record_path(hub, main_call["call_id"])
                rec = json.loads(path.read_text())
                if mutation == "duplicate":
                    shutil.copyfile(path, path.parent / "duplicate.json")
                elif mutation == "extra":
                    rec["call_id"] = 'unallowed|arrival|na|A|KEEP_CLAR'; dump(path.parent/'extra.json', rec)
                elif mutation == "corrupt":
                    path.write_text('{')
                elif mutation == "nonok":
                    rec["status"] = 'infra_failed'; dump(path, rec)
                elif mutation == "partial":
                    rec["complete"] = False; dump(path, rec)
                elif mutation == "prompt":
                    rec["user_sha256"] = 'changed'; dump(path, rec)
                elif mutation == "retry":
                    rec["attempts"] = 2; dump(path, rec)
                elif mutation == "late":
                    rec["finished_at"] = '2026-11-11T19:00:01'; dump(path, rec)
                elif mutation == "stop":
                    dump(hub/'stages/main/STOP.json', {"finished": False})
                elif mutation == "end":
                    (hub/'stages/main/END.json').unlink()
                elif mutation == "resume":
                    dump(hub/'stages/main/start-2.json', {"todo": 1})
                elif mutation == "failed_attempt":
                    jsonl(hub/'stages/main/attempts.jsonl', [{"call_id": main_call["call_id"], "attempt": 1}])
                elif mutation == "driver_error":
                    dump(hub/'runtime/DRIVER-ERROR.json', {"reason": 'synthetic final failure'})
                elif mutation == "missing_guard":
                    (hub/'runtime/GUARD-main.json').unlink()
                elif mutation == "bad_forecast":
                    path=hub/'runtime/GUARD-main.json';obj=json.loads(path.read_text());obj['projected_total_s']=40000;dump(path,obj)
                elif mutation == "missing_smoke_certificate":
                    (hub/'runtime/SMOKE-CHECK.json').unlink()
                elif mutation == "unknown_stop":
                    rec['stop']='unknown'; dump(path,rec)
                elif mutation == "invalid_time":
                    rec['seconds']=float('nan'); dump(path,rec)
                info = SC.check(hub)
                self.assertFalse(info["complete"])
                self.assertTrue(info["problems"])

    def test_frozen_bytes_rule_plan_and_namespace_hashes_are_required(self):
        mutations = ("source", "config", "data", "rule", "plan", "driver", "manifest", "deadline_timezone")
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                hub = self.copy_hub()
                if mutation == "source":
                    f = json.loads((hub/'config/FROZEN-PROTOCOL.json').read_text()); f['source_sha256']='changed'; dump(hub/'config/FROZEN-PROTOCOL.json',f)
                elif mutation == "config":
                    path=hub/'config/stage-main.json'; obj=json.loads(path.read_text()); obj['retry_limit']=1; dump(path,obj)
                elif mutation == "data":
                    path=hub/'data/main-calls.jsonl'; path.write_text(path.read_text()+'{}\n')
                elif mutation == "rule":
                    path=hub/'config/RULE.json'; obj=json.loads(path.read_text()); obj['arrival']['c'][0]='1/9'; dump(path,obj)
                elif mutation == "plan":
                    path=hub/'config/ANALYSIS-PLAN.json'; obj=json.loads(path.read_text()); obj['primary']['baseline']='SUB_CLAR'; dump(path,obj)
                elif mutation == "driver":
                    (hub/'run_cc.sh').write_text('# changed\n')
                elif mutation == "manifest":
                    # Point freeze at a mismatching file, without touching base fixture.
                    path=hub/'bad-manifest.json'; path.write_text('{"changed":true}')
                    f=json.loads((hub/'config/FROZEN-PROTOCOL.json').read_text());f['model_manifest_path']=str(path);dump(hub/'config/FROZEN-PROTOCOL.json',f)
                elif mutation == "deadline_timezone":
                    path=hub/'config/DEADLINE.json';obj=json.loads(path.read_text());obj['timezone']='UTC';dump(path,obj)
                self.assertFalse(SC.check(hub)["complete"])

    def test_membership_is_checked_beyond_its_hash_commitment(self):
        problems = []
        datasets = {stage: {"public_rows": self.panel[stage]["public"], "hidden_rows": self.panel[stage]["hidden"],
                            "call_rows": self.panel[stage]["calls"]} for stage in ('main','smoke')}
        # Remove an OPTIONAL-LOOKING reference that is actually required.
        datasets['main']['call_rows']=[c for c in datasets['main']['call_rows'] if not(c['arm']=='SUB_CLAR' and c['act']=='arrival')]
        A.validate_membership(CC.DEFAULT_CONFIG, self.panel['main']['plan']+self.panel['smoke']['plan'],
                              CC.allowed_manifest(self.panel), datasets, problems)
        self.assertTrue(any('sparse membership' in p for p in problems))

    def test_host_timezone_cannot_change_naive_epoch_interpretation(self):
        import time
        before = os.environ.get('TZ')
        try:
            os.environ['TZ']='UTC'; time.tzset()
            self.assertEqual(A.epoch('2026-11-11T07:00:00'), A.epoch('2026-11-11T07:00:00-05:00'))
            self.assertTrue(SC.check(self.base)['complete'])
        finally:
            if before is None: os.environ.pop('TZ',None)
            else: os.environ['TZ']=before
            time.tzset()


def collection_counts(ledger):
    return {act: sum(r['act']==act for r in ledger) for act in ('arrival','correction')}


class AggregationFixtures(unittest.TestCase):
    def test_half_quarter_differences_pair_histories_and_directions_first(self):
        allocation = CC.plan()[:1]
        rows = []
        for meta in CC.expected_targets(allocation):
            for arm in CC.PRIMARY_ARMS:
                exact = arm == A.CANDIDATE and meta['history']=='A' and (meta['act']=='arrival' or meta['direction']=='yes_to_no')
                rows.append({**meta, 'family':meta['family'][:2], 'arm':arm, 'exact':exact, 'incomplete':False})
        a=A.aggregate_stems(rows,allocation,'arrival'); c=A.aggregate_stems(rows,allocation,'correction')
        self.assertEqual(a[0]['difference_exact'],'1/2')
        self.assertEqual(c[0]['difference_exact'],'1/4')
        self.assertEqual(len(c[0]['target_differences']),4)
        with self.assertRaises(ValueError):
            A.aggregate_stems(rows[:-1],allocation,'correction')

    def test_explicit_arrival_only_stem_is_supported(self):
        allocation=CC.plan()[160:161]
        self.assertTrue(allocation[0]['primary_arrival'])
        self.assertFalse(allocation[0]['primary_correction'])
        rows=[{**meta,'family':meta['family'][:2],'arm':arm,'exact':True,'incomplete':False}
              for meta in CC.expected_targets(allocation) for arm in CC.PRIMARY_ARMS]
        self.assertEqual(len(A.aggregate_stems(rows,allocation,'arrival')),1)
        self.assertEqual(A.aggregate_stems(rows,allocation,'correction'),[])

    def test_schema_rejects_floats_bool_counts_and_fallbacks(self):
        import copy
        A.validate_plan(A.DEFAULT_PLAN)
        for bad in (224.0, True, 223):
            plan=copy.deepcopy(A.DEFAULT_PLAN);plan['primary']['arrival_stems']=bad
            with self.assertRaises(ValueError): A.validate_plan(plan)

    def test_early_missing_stage_writes_terminal_incomplete_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            result=A.write_artifacts(tmp)
            self.assertEqual(result['status'],'INCOMPLETE')
            self.assertEqual(result['qualification']['status'],'NOT_EVALUATED')
            self.assertNotIn('primary',result)
            self.assertIn('INCOMPLETE', (Path(tmp)/'RUN-STATUS.md').read_text())
            self.assertIn('no bounds', (Path(tmp)/'REPORT.md').read_text())


if __name__ == '__main__':
    unittest.main()
