"""Pre-collection validation for V1.17.0 (no model). Runs the input gates of cab_analyze.py (G1 prompt isolation /
schema / no labels, G2 model config + committed order, G3 labels / prefix compatibility / control identity / cache
accounting) on the committed inputs, plus: every rendering re-checked with prose_study.check_equivalent, arrival
template allocation, strata counts, and the balance of the committed schedule (each condition first in half the units;
per-quarter counts). Usage: cab_validate.py --hub HUB --set SET --stage-config CONFIG [--out DIR]"""
import argparse
import collections
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from _bootstrap import ROOT
from tempo import ctxablate as CA, prose, prose_study as PS


def load(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", required=True)
    ap.add_argument("--set", required=True)
    ap.add_argument("--stage-config", required=True)
    ap.add_argument("--out")
    a = ap.parse_args()
    hub = Path(a.hub)
    out = Path(a.out) if a.out else hub / "phase0"
    out.mkdir(parents=True, exist_ok=True)
    data = hub / "data"
    calls = load(data / f"{a.set}-calls.jsonl")
    gold = load(data / "hidden" / f"{a.set}-gold.jsonl")
    groups = {g["group"]: g for g in load(data / "hidden" / f"{a.set}-groups.jsonl")}
    failures, res = [], {}
    # rendering and template allocation
    tmpl, strata = collections.Counter(), collections.Counter()
    for g in gold:
        if g["control"]:
            continue
        gr = groups[g["group"]]
        w, _ = CA._world(gr["world_seed"], gr["pool"])
        for r in g["prefix"] + [g["gold"]]:
            try:
                PS.check_equivalent(r, prose.prose_line(w, r, gr["render_seed"]))
            except AssertionError as e:
                failures.append(f"{g['cell']}: {e}")
        if prose.prose_line(w, g["gold"], gr["render_seed"]) != g["text"]:
            failures.append(f"{g['cell']}: text differs")
        if g["variant"] == "arrival" and g["condition"] == "FULL":
            tmpl[CA.template_id(g["text"])] += 1
            strata[tuple(g["stratum"])] += 1
    res["arrival_templates"] = dict(sorted(tmpl.items()))
    res["strata"] = {str(k): v for k, v in sorted(strata.items())}
    # schedule balance
    first = collections.Counter()
    seen = set()
    for c in calls:
        u = c["call_id"].rsplit("|", 1)[0]
        if u not in seen:
            seen.add(u)
            first[c["arm"] if c["variant"] != "control" else ("LOCAL" if c["arm"] == "LOCAL" else "FULL")] += 1
    q = len(calls) // 4
    res["schedule"] = {"first_in_unit": dict(first),
                       "per_quarter": [dict(collections.Counter(c["arm"] for c in calls[i * q:(i + 1) * q if i < 3 else None]))
                                       for i in range(4)]}
    # input gates via the analysis code on an empty stage (G4 is expected to fail there and is ignored)
    tmp = Path(tempfile.mkdtemp())
    try:
        (tmp / "data").symlink_to(data)
        (tmp / "config").mkdir()
        shutil.copy(a.stage_config, tmp / "config" / "stage-validate.json")
        (tmp / "stages" / "validate" / "calls").mkdir(parents=True)
        subprocess.run([sys.executable, "-B", str(ROOT / "scripts" / "cab_analyze.py"), "--hub", str(tmp), "--set", a.set,
                        "--stage", "validate", "--boot", "10"], check=True, capture_output=True)
        an = json.loads((tmp / "analysis" / "validate" / "ANALYSIS.json").read_text())
    finally:
        shutil.rmtree(tmp)
    for k, g in an["gates"].items():
        if not k.startswith("G4") and not g["pass"]:
            failures.append(f"{k}: {g['examples']}")
    res["input_gates"] = {k: (g["pass"], g["failures"], g["checked"]) for k, g in an["gates"].items() if not k.startswith("G4")}
    res["failures"], res["pass"] = failures, not failures
    (out / "VALIDATION.json").write_text(json.dumps(res, indent=1) + "\n")
    (out / "VALIDATION.md").write_text(f"# V1.17.0 pre-collection validation ({a.set})\n\n**{'PASS' if not failures else 'FAIL'}**\n\n```\n"
                                       + json.dumps(res, indent=1)[:4000] + "\n```\n")
    print("PASS" if not failures else f"FAIL {failures[:5]}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
