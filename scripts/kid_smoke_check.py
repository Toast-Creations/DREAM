"""V1.21.0 smoke check (structural only; no exactness is computed or printed, so prompts cannot be tuned on semantic
results). Usage: kid_smoke_check.py HUB STAGE. Pass iff every smoke record is status ok, stop eos, model identity
pinned, input <= 2048 tokens, and the reply parses and normalises under the frozen FACT-v1 compiler (compile_reply
returns claims, i.e. no parse/normalisation failure). Exit 0/1."""
import json
import sys
from pathlib import Path

from _bootstrap import ROOT  # noqa: F401
from tempo import factored as FA

hub, stage = Path(sys.argv[1]), sys.argv[2]
T = {t["target"]: t for t in map(json.loads, (hub / "data" / "inputs" / "ref-targets.jsonl").read_text().splitlines())}
bad, n = [], 0
for p in sorted((hub / "stages" / stage / "calls").glob("*.json")):
    r = json.loads(p.read_text()); n += 1
    m = r["model"]
    tid = r["call_id"].rsplit("|", 1)[0]
    ok = (r["status"] == "ok" and r["stop"] == "eos" and r["input_tokens"] <= 2048 and m["revision"].startswith("9216db57")
          and m["quantization"] == "nf4" and m["enable_thinking"] is False and m["load"]["devices"] == ["cuda:0"])
    claims = FA.compile_reply(r["raw"], T[tid]["registry"])[1]["claims"] if r["status"] == "ok" else None
    if not ok or claims is None:
        bad.append(r["call_id"])
print(json.dumps({"stage": stage, "records": n, "structural_failures": bad}))
sys.exit(0 if n and not bad else 1)
