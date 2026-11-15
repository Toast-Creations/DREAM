"""Run the public-only control fixtures through the guard and compare with the separately written expected labels.

Usage: PYTHONDONTWRITEBYTECODE=1 python -B scripts/ig_controls.py --out DIR
Controls are reported separately and never enter study outcome totals.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
from guard import pins  # noqa: E402

pins.activate()
from guard import decide as D  # noqa: E402

FIX = HERE / "fixtures"


def actual_labels(d):
    return {"disposition": d["disposition"], "mismatch_kind": d["mismatch_kind"],
            "resolver_status": d["resolver"]["status"], "resolver_reason": d["resolver"]["reason"],
            "resolved_field": d["resolver"]["field"], "compile_code": d["compile"]["code"]}


def run():
    inputs = [json.loads(x) for x in (FIX / "controls-inputs.jsonl").read_text().splitlines() if x]
    expected = json.loads((FIX / "controls-expected.json").read_text())
    rows, failures = [], []
    for c in inputs:
        d = D.decide(c["prefix"], c["target_text"], c["registry"], c["registry_order"], c["raw"])
        got = actual_labels(d)
        exp = expected.get(c["name"])
        if exp is None:
            failures.append({"name": c["name"], "problem": "no expected label"})
            continue
        bad = {k: {"expected": v, "got": got.get(k)} for k, v in exp.items() if k in got and got[k] != v}
        if bad:
            failures.append({"name": c["name"], "mismatch": bad})
        rows.append({"name": c["name"], "expected": exp, "got": got, "ok": not bad})
    missing = sorted(set(expected) - {"_note"} - {c["name"] for c in inputs})
    if missing:
        failures.append({"problem": "expected labels without inputs", "names": missing})
    refusal = [r for r in rows if r["expected"].get("disposition") == "abstain"]
    match = [r for r in rows if r["expected"].get("disposition") == "pass"]
    return {"rule": D.RULE, "status": "PASS" if not failures else "FAIL", "n": len(rows), "failures": failures,
            "supported_matches_pass": all(r["ok"] for r in match),
            "refusals_abstain": all(r["ok"] and r["got"]["disposition"] == "abstain" for r in refusal),
            "no_refusal_passes": not any(r["got"]["disposition"] == "pass" for r in refusal),
            "inputs_sha256": hashlib.sha256((FIX / "controls-inputs.jsonl").read_bytes()).hexdigest(),
            "expected_sha256": hashlib.sha256((FIX / "controls-expected.json").read_bytes()).hexdigest(),
            "note": "Identity-only limits: a matching subject with a wrong time or value passes; it is not caught.",
            "rows": rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    r = run()
    Path(a.out).mkdir(parents=True, exist_ok=True)
    (Path(a.out) / "CONTROLS.json").write_text(json.dumps(r, indent=1, sort_keys=True) + "\n")
    print(json.dumps({k: r[k] for k in ("status", "n", "supported_matches_pass", "refusals_abstain")}))
    for f in r["failures"]:
        print("  FAIL", json.dumps(f))
    if r["status"] != "PASS":
        sys.exit(2)


if __name__ == "__main__":
    main()
