"""Isolated CPU fixture for the actual ESUB supervisor/analyzer (adapted from cc_cpu_runner.py). Never study evidence.

Arguments: --hub --stage --config [--mode equal|better|worse|wrongbind|fail|slow|nonok|stop].
It emits the real runner artifact schema using canonical responses; no model imports/calls.
"""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from dream_core.ledger import release_source_hash  # noqa: E402
from tempo import factored as FA  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--hub", required=True)
ap.add_argument("--stage", required=True)
ap.add_argument("--config", required=True)
ap.add_argument("--mode", default="equal")
a = ap.parse_args()
hub, stage, cfgp = Path(a.hub), a.stage, Path(a.config)
cfg = json.loads(cfgp.read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
sd = hub / "stages" / stage
(sd / "calls").mkdir(parents=True, exist_ok=True)
calls = [json.loads(line) for line in (hub / f"data/{stage}-calls.jsonl").read_text().splitlines()]
public = {r["target"]: r for r in (json.loads(line) for line in (hub / f"data/public/{stage}-targets.jsonl").read_text().splitlines())}
hidden = {r["target"]: r for r in (json.loads(line) for line in (hub / f"data/hidden/{stage}-cases.jsonl").read_text().splitlines())}
lock = {"config_sha256": sha(cfgp), "calls_sha256": sha(hub / f"data/{stage}-calls.jsonl"),
        "source_sha256": release_source_hash(ROOT), "fake": False}
(sd / "LOCK.json").write_text(json.dumps(lock))
(sd / "config.json").write_text(cfgp.read_text())
(sd / "start-1.json").write_text(json.dumps({"started": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                                            "planned": len(calls), "todo": len(calls), **lock}))
identity = {"revision": "9216db5781bf21249d130ec9da846c4624c16137", "path": cfg["model"]["path"],
            "dtype": "bfloat16", "quantization": "nf4", "enable_thinking": False, "decoding": "greedy",
            "torch": "cpu-fixture", "transformers": "cpu-fixture",
            "load": {"protocol": "QLOAD-NF4-v1", "devices": ["cuda:0"], "quantization": {
                "bnb_4bit_compute_dtype": "bfloat16", "bnb_4bit_use_double_quant": True}}}
(sd / "LOAD.json").write_text(json.dumps(identity))
for i, call in enumerate(calls):
    if a.mode == "fail" and i >= len(calls)//2:
        raise SystemExit(21)
    case = hidden[call["call_id"].rsplit("|", 1)[0]]["case"]
    gold = case["records"][-1]
    reply = FA.canonical_factored(gold)
    tid, arm = call["call_id"].rsplit("|", 1)
    other = next(f for f in public[tid]["registry_order"] if f.endswith(".on_hand") and f != gold["payload"]["field"])
    arrival_f3b = gold["kind"] == "change" and call["family"].startswith("F3") and call["history"] == "B"
    def rebind():
        reply["events"] = [dict(e, field=other) for e in reply["events"]]
        reply["states"] = [dict(x, field=other) for x in reply["states"]]
    if stage == "main" and a.mode == "better" and arm == "KEEP_CLAR" and arrival_f3b:
        rebind()                     # current arm binds the wrong part; candidate stays exact
    if stage == "main" and a.mode == "worse" and arm == "KEEP_SUBJ" and gold["kind"] == "change":
        reply["events"] = []         # candidate arrivals become state-only
        reply["states"] = [{"field": gold["payload"]["field"], "at": gold["event_at"], "value": gold["payload"]["to"]}]
    if stage == "main" and a.mode == "wrongbind" and arm == "KEEP_SUBJ" and arrival_f3b and \
            call["call_id"] == min(c["call_id"] for c in calls if c["arm"] == "KEEP_SUBJ" and
                                   c["family"].startswith("F3") and c["history"] == "B" and c["act"] == "arrival"):
        rebind()                     # exactly one candidate wrong binding
    reply["evidence"] = case["text"][-25:]
    rec = {k: call[k] for k in ("call_id", "group_id", "domain", "pattern", "length", "arm", "qtype", "variant",
                                "n_records", "evidence_cutoff", "max_new_tokens", "user_sha256")}
    rec.update(model=identity, input_tokens=1400, output_tokens=120, raw=json.dumps(reply),
               status="infra_failed" if a.mode == "nonok" and i == 0 else "ok", stop="eos", attempts=1,
               complete=True, seconds=30.0 if a.mode == "slow" else 12.0,
               finished_at=time.strftime("%Y-%m-%dT%H:%M:%S"))
    (sd / "calls" / (call["call_id"].replace("|", "__") + ".json")).write_text(json.dumps(rec))
summary = {"finished": a.mode != "stop", "stop_reason": "fixture" if a.mode == "stop" else None,
           "new_this_run": len(calls), "elapsed_s": 1.0, "load_s": .1, "peak_gib": 0,
           "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
(sd / ("STOP.json" if a.mode == "stop" else "END.json")).write_text(json.dumps(summary))
