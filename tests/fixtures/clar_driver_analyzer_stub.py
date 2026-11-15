"""CPU fixture: exercise driver success propagation without semantic analysis."""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from tempo import kidconfdone as KD  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--hub", required=True)
a = ap.parse_args()
hub = Path(a.hub)
if os.environ.get("CLAR_STUB_ANALYZER_FAIL"):
    sys.exit(3)
source = json.loads((hub / "config/FROZEN-PROTOCOL.json").read_text())["source_sha256"]
done = KD.completion(hub, source)
status = "COMPLETE" if done["complete"] and not os.environ.get("CLAR_STUB_INCOMPLETE") else "INCOMPLETE"
out = hub / "analysis/dev"
out.mkdir(parents=True, exist_ok=True)
(out / "ANALYSIS.json").write_text(json.dumps({"study": "CLAR-v1", "status": status,
                                              "infrastructure": {"problems": done["problems"]}}))
