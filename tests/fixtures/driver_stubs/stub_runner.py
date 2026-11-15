"""CPU stub of scripts/hold_run.py for driver tests (no model). Writes the runner's artifact schema: LOCK.json
(non-fake, committed hashes, current source), one record per scheduled call with a canonical reply and the pinned
recipe identity, then END.json. KCONF_STUB_FAIL=<stage> makes that stage write half its records and exit 3."""
import hashlib
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
from dream_core.ledger import release_source_hash  # noqa: E402
from tempo import factored as FA, holdout as HO  # noqa: E402

a = sys.argv
hub, stage, cfgp = Path(a[a.index("--hub") + 1]), a[a.index("--stage") + 1], Path(a[a.index("--config") + 1])
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
sd = hub / "stages" / stage
(sd / "calls").mkdir(parents=True, exist_ok=True)
commit = json.loads((hub / "data" / f"COMMITMENT-{stage}.json").read_text())
(sd / "LOCK.json").write_text(json.dumps({"config_sha256": sha(cfgp), "calls_sha256": commit["calls_sha256"],
                                          "source_sha256": release_source_hash(ROOT), "fake": False}))
hid = {json.loads(l)["target"]: json.loads(l) for l in (hub / "data" / "hidden" / f"{stage}-cases.jsonl").read_text().splitlines() if l.strip()}
calls = [json.loads(l) for l in (hub / "data" / f"{stage}-calls.jsonl").read_text().splitlines() if l.strip()]
model = {"revision": "9216db5781bf21249d130ec9da846c4624c16137", "quantization": "nf4", "enable_thinking": False,
         "decoding": "greedy", "dtype": "bfloat16", "load": {"devices": ["cuda:0"], "quantization": {
             "bnb_4bit_compute_dtype": "bfloat16", "bnb_4bit_use_double_quant": True}}}
fail = os.environ.get("KCONF_STUB_FAIL") == stage
for i, c in enumerate(calls):
    if fail and i >= len(calls) // 2:
        print("stub failure", file=sys.stderr)
        sys.exit(3)
    h = hid[c["call_id"].rsplit("|", 1)[0]]
    raw = json.dumps(dict(FA.canonical_factored(HO.public(h["case"])[-1]), evidence=h["case"]["text"][-25:]))
    r = {"call_id": c["call_id"], "status": "ok", "stop": "eos", "raw": raw, "user_sha256": c["user_sha256"],
         "model": model, "max_new_tokens": 256, "attempts": 1, "complete": True, "input_tokens": 1400,
         "output_tokens": 140, "seconds": 12.0, "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    (sd / "calls" / (c["call_id"].replace("|", "__") + ".json")).write_text(json.dumps(r))
(sd / "END.json").write_text(json.dumps({"finished": True, "at": time.strftime("%Y-%m-%dT%H:%M:%S")}))
