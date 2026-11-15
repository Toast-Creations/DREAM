"""Pre-collection validation for V1.18.0 (no model generation). Runs the input gates of fac_analyze.py (G1 matched
prompts, G2 model config + committed order, G3 labels / prefixes / canonical compile / canonical replay = reference /
accounting) on an empty stage; re-checks every rendering (check_equivalent); reports strata, lure and template
allocation and schedule balance; and tokenizes the canonical FACTORED and EXCLUSIVE replies with the pinned
tokenizer (no model weights) to check the 256-token cap fits.
Usage: fac_validate.py --hub HUB --set SET --stage-config CONFIG [--out DIR]"""
import argparse
import collections
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from _bootstrap import ROOT
from tempo import ctxablate as CA, factored as FA, prose, prose_study as PS


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
    fails, res = [], {}
    sys.path.insert(0, str(ROOT / "scripts"))
    from fac_analyze import world_of
    tm, st, lu = collections.Counter(), collections.Counter(), collections.Counter()
    for g in gold:
        if g["control"] or g["interface"] != "FACTORED":
            continue
        gr = groups[g["group"]]
        w = world_of(gr)
        for r in g["prefix"] + [g["gold"]]:
            try:
                PS.check_equivalent(r, prose.prose_line(w, r, gr["render_seed"]))
            except AssertionError as e:
                fails.append(f"{g['cell']}: {e}")
        if g["variant"] == "arrival":
            tm[CA.template_id(g["text"])] += 1
            st[str(tuple(g["stratum"]))] += 1
            lu[g["lure"]] += 1
    res["allocation"] = {"arrival_templates": dict(sorted(tm.items())), "strata": dict(st), "lure": dict(lu)}
    first = collections.Counter()
    seen = set()
    for c in calls:
        u = c["call_id"].rsplit("|", 1)[0]
        if u not in seen:
            seen.add(u); first[c["arm"]] += 1
    q = len(calls) // 4
    res["schedule"] = {"first_in_unit": dict(first), "per_quarter": [dict(collections.Counter(c["arm"] for c in calls[i * q:(i + 1) * q]))
                                                                     for i in range(4)]}
    from transformers import AutoTokenizer
    cfg = json.loads(Path(a.stage_config).read_text())
    tok = AutoTokenizer.from_pretrained(cfg["model"]["path"])
    lens = collections.defaultdict(list)
    for g in gold:
        if g["interface"] != "FACTORED":
            continue
        fo = dict(FA.canonical_factored(g["gold"]), evidence=g["text"])
        eo = dict(g["gold"], evidence=g["text"])
        lens["FACTORED"].append(len(tok(json.dumps(fo, indent=2))["input_ids"]))
        lens["EXCLUSIVE"].append(len(tok(json.dumps(eo, indent=2))["input_ids"]))
    res["canonical_reply_tokens"] = {k: {"max": max(v), "mean": round(sum(v) / len(v), 1)} for k, v in lens.items()}
    if max(lens["FACTORED"]) > 230:
        fails.append(f"canonical FACTORED reply up to {max(lens['FACTORED'])} tokens: too close to the 256 cap")
    tmp = Path(tempfile.mkdtemp())
    try:
        (tmp / "data").symlink_to(data)
        (tmp / "config").mkdir()
        shutil.copy(a.stage_config, tmp / "config" / "stage-validate.json")
        (tmp / "stages" / "validate" / "calls").mkdir(parents=True)
        subprocess.run([sys.executable, "-B", str(ROOT / "scripts" / "fac_analyze.py"), "--hub", str(tmp), "--set", a.set,
                        "--stage", "validate", "--boot", "10"], check=True, capture_output=True)
        an = json.loads((tmp / "analysis" / "validate" / "ANALYSIS.json").read_text())
    finally:
        shutil.rmtree(tmp)
    for k, g in an["gates"].items():
        if not k.startswith("G4") and not g["pass"]:
            fails.append(f"{k}: {g['examples']}")
    res["input_gates"] = {k: (g["pass"], g["failures"], g["checked"]) for k, g in an["gates"].items() if not k.startswith("G4")}
    res["failures"], res["pass"] = fails, not fails
    (out / "VALIDATION.json").write_text(json.dumps(res, indent=1) + "\n")
    (out / "VALIDATION.md").write_text(f"# V1.18.0 pre-collection validation ({a.set})\n\n**{'PASS' if not fails else 'FAIL'}**\n\n```\n"
                                       + json.dumps(res, indent=1)[:4000] + "\n```\n")
    print("PASS" if not fails else f"FAIL {fails[:5]}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
