"""Isolated CPU fixture for the actual EVT-suite supervisor/analyzer (adapted from ev_cpu_runner.py). Never study evidence.

Arguments: --hub --stage --config [--mode MODE]. Candidate arms are KEEP_EVT (study A) or KEEP_EVTR (B); in C both.
  equal               every reply canonical (exact)
  better              KEEP_CLAR omits the event on every RESULT-wording arrival; other arms exact
  wrongbind5          as better, plus 5 candidate wrong bindings on F3 history-B arrivals
  evtr_transition3    as better, plus KEEP_EVTR state-only on its first 3 TRANSITION arrivals
  stateatrecv         as better, plus candidate delayed arrivals give the state at received_at (first 2)
  corrections_event   as better, plus a spurious event on every candidate correction
  truncate            as better, plus one truncated unparseable candidate arrival
  Study D (V1.29.0; candidate KEEP_EVTT, comparator KEEP_EVT), all "as better" for KEEP_CLAR:
  d_warrants          KEEP_EVT reception-dated on its first 8 delayed RESULT arrivals, KEEP_EVTT on its first 2
  d_insufficient      KEEP_EVT reception-dated on 4, KEEP_EVTT on 0
  d_not_halved        KEEP_EVT reception-dated on 8, KEEP_EVTT on 5
  d_state_only        d_warrants, plus KEEP_EVTT state-only on its first 3 immediate RESULT arrivals
  d_wrongbind         d_warrants, plus 5 KEEP_EVTT wrong bindings on F3 history-B arrivals
  d_new_type          d_warrants, plus one KEEP_EVTT arrival with a spurious revision object
  fail | slow | nonok | stop | hang   infrastructure modes
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
            "load": {"protocol": "QLOAD-NF4-v1", "devices": ["cuda:0"], "attn_implementation": "sdpa", "quantization": {
                "load_in_4bit": True, "bnb_4bit_quant_type": "nf4", "bnb_4bit_use_double_quant": True,
                "bnb_4bit_compute_dtype": "bfloat16", "non_quantized_dtype": "bfloat16"}}}
(sd / "LOAD.json").write_text(json.dumps(identity))
panel = json.loads((hub / "config/PANEL.json").read_text())
cands = {"A": ["KEEP_EVT"], "B": ["KEEP_EVTR"], "C": ["KEEP_EVT", "KEEP_EVTR"], "D": ["KEEP_EVTT"]}[panel["key"]]


def first(arm, reception, wording_bit, n):
    return sorted(c["call_id"] for c in calls if c["arm"] == arm and c["act"] == "arrival"
                  and c["reception"] == reception and c["bits"][1] == wording_bit)[:n]


D_RD = {"d_warrants": (8, 2), "d_insufficient": (4, 0), "d_not_halved": (8, 5), "d_state_only": (8, 2),
        "d_wrongbind": (8, 2), "d_new_type": (8, 2)}
d_rd = set()
if stage == "main" and a.mode in D_RD:
    d_rd = set(first("KEEP_EVT", "delayed", 0, D_RD[a.mode][0]) + first("KEEP_EVTT", "delayed", 0, D_RD[a.mode][1]))
d_so = set(first("KEEP_EVTT", "immediate", 0, 3)) if stage == "main" and a.mode == "d_state_only" else set()
d_new = set(first("KEEP_EVTT", "delayed", 1, 1)) if stage == "main" and a.mode == "d_new_type" else set()
cand_f3b = sorted(c["call_id"] for c in calls if c["arm"] in cands and c["family"].startswith("F3")
                  and c["history"] == "B" and c["act"] == "arrival")
evtr_trans = sorted(c["call_id"] for c in calls if c["arm"] == "KEEP_EVTR" and c["act"] == "arrival"
                    and c["bits"][1] == 1)
cand_delayed = sorted(c["call_id"] for c in calls if c["arm"] in cands and c["act"] == "arrival"
                      and c["reception"] == "delayed")
BETTER = ("better", "wrongbind5", "evtr_transition3", "stateatrecv", "corrections_event", "truncate") + tuple(D_RD)
if a.mode == "hang":
    time.sleep(600)
for i, call in enumerate(calls):
    if a.mode == "fail" and i >= len(calls)//2:
        raise SystemExit(21)
    case = hidden[call["call_id"].rsplit("|", 1)[0]]["case"]
    gold = case["records"][-1]
    reply = FA.canonical_factored(gold)
    tid, arm = call["call_id"].rsplit("|", 1)
    cid = call["call_id"]
    other = next(f for f in public[tid]["registry_order"] if f.endswith(".on_hand") and f != gold["payload"]["field"])
    def rebind():
        reply["events"] = [dict(e, field=other) for e in reply["events"]]
        reply["states"] = [dict(x, field=other) for x in reply["states"]]
    def state_only():
        reply["events"] = []
        reply["states"] = [{"field": gold["payload"]["field"], "at": gold["event_at"], "value": gold["payload"]["to"]}]
    main_better = stage == "main" and a.mode in BETTER
    if main_better and arm == "KEEP_CLAR" and gold["kind"] == "change" and call["bits"][1] == 0:
        state_only()
    if stage == "main" and a.mode in ("wrongbind5", "d_wrongbind") and cid in cand_f3b[:5]:
        rebind()
    if stage == "main" and a.mode == "evtr_transition3" and cid in evtr_trans[:3]:
        state_only()
    if stage == "main" and a.mode == "stateatrecv" and cid in cand_delayed[:2]:
        reply["states"] = [{"field": gold["payload"]["field"], "at": case["recv"], "value": gold["payload"]["to"]}]
    if cid in d_rd:
        reply["states"] = [{"field": gold["payload"]["field"], "at": case["recv"], "value": gold["payload"]["to"]}]
    if cid in d_so:
        state_only()
    if cid in d_new:
        reply["revisions"] = [{"field": gold["payload"]["field"], "valid_from": gold["event_at"], "value": "no"}]
    if stage == "main" and a.mode == "corrections_event" and arm in cands and gold["kind"] == "correction":
        reply["events"] = [{"field": gold["payload"]["field"], "at": case["recv"], "from": None,
                            "to": gold["payload"]["value"]}]
    reply["evidence"] = case["text"][-25:]
    rec = {k: call[k] for k in ("call_id", "group_id", "domain", "pattern", "length", "arm", "qtype", "variant",
                                "n_records", "evidence_cutoff", "max_new_tokens", "user_sha256")}
    raw, stop, out_tok = json.dumps(reply), "eos", 120
    if stage == "main" and a.mode == "truncate" and cid == cand_f3b[-1]:
        raw, stop, out_tok = "```json\n" + json.dumps(reply)[:60], "length", 256
    rec.update(model=identity, input_tokens=1400, output_tokens=out_tok, raw=raw,
               status="infra_failed" if a.mode == "nonok" and i == 0 else "ok", stop=stop, attempts=1,
               complete=True, seconds=30.0 if a.mode == "slow" else 12.0,
               finished_at=time.strftime("%Y-%m-%dT%H:%M:%S"))
    (sd / "calls" / (call["call_id"].replace("|", "__") + ".json")).write_text(json.dumps(rec))
summary = {"finished": a.mode != "stop", "stop_reason": "fixture" if a.mode == "stop" else None,
           "new_this_run": len(calls), "elapsed_s": 1.0, "load_s": .1, "peak_gib": 0,
           "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
(sd / ("STOP.json" if a.mode == "stop" else "END.json")).write_text(json.dumps(summary))
