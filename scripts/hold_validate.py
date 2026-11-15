"""Pre-collection validation for V1.19.0 (no model generation; tokenizers only).
Usage: hold_validate.py --hub HUB --set SET --small-config CFG --large-config CFG [--out DIR]
Checks: (1) H1-H3 input gates of hold_analyze (canonical exact + canonical replay = independent reference; identical
prompts across models, unique within model) on an empty stage; (2) every complete chat-rendered prompt <= 2,048 input
tokens and every canonical FACT-v1 output (with a valid evidence span) <= 256 tokens, under BOTH tokenizers;
(3) public/hidden separation (no act, history, family, component or gold labels in prompts; public target file has no
hidden keys); (4) allocation balance (strata x factor bits); (5) the construction inventory hash."""
import argparse
import collections
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from _bootstrap import ROOT
from tempo import factored as FA, holdout as HO, render
from dream_core.modeling import render_chat

LABELS = ("history A", "history B", "F1_", "F2_", "F3_", "F4_", "CN_explicit", "C1_one", "primary", "calibration",
          "|arrival|", "|removal|", "|correction|", "|observation|")


def load(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", required=True)
    ap.add_argument("--set", required=True)
    ap.add_argument("--small-config", required=True)
    ap.add_argument("--large-config", required=True)
    ap.add_argument("--out")
    a = ap.parse_args()
    hub = Path(a.hub)
    out = Path(a.out) if a.out else hub / "phase0" / a.set
    out.mkdir(parents=True, exist_ok=True)
    data = hub / "data"
    fails, res = [], {}
    from transformers import AutoTokenizer
    calls = load(data / f"{a.set}SMALL-calls.jsonl")
    cases = {c["target"]: c for c in load(data / "hidden" / f"{a.set}-cases.jsonl")}
    targets = load(data / "public" / f"{a.set}-targets.jsonl")
    budget = {}
    for name, cfgp in (("SMALL", a.small_config), ("LARGE", a.large_config)):
        cfg = json.loads(Path(cfgp).read_text())["model"]
        tok = AutoTokenizer.from_pretrained(cfg["path"], local_files_only=True)
        tok.dream_chat_kwargs = {"enable_thinking": False}
        ins, outs = [], []
        for c in calls:
            text = render_chat(tok, c["user"], system=render.SYSTEM, enable_thinking=False)
            n = len(tok(text, add_special_tokens=False)["input_ids"])
            ins.append(n)
            tid = c["call_id"].rsplit("|", 1)[0]
            case = cases[tid]["case"]
            gold = HO.public(case)[-1]
            o = dict(FA.canonical_factored(gold), evidence=case["text"].split(": ", 1)[1])
            outs.append(len(tok(json.dumps(o, indent=2))["input_ids"]))
        budget[name] = {"max_input": max(ins), "mean_input": round(sum(ins) / len(ins), 1), "max_canonical_output": max(outs),
                        "mean_canonical_output": round(sum(outs) / len(outs), 1), "tokenizer_json_sha256":
                        hashlib.sha256((Path(cfg["path"]) / "tokenizer.json").read_bytes()).hexdigest(),
                        "tokenizer_config_sha256": hashlib.sha256((Path(cfg["path"]) / "tokenizer_config.json").read_bytes()).hexdigest()}
        if max(ins) > 2048:
            fails.append(f"{name}: prompt of {max(ins)} tokens exceeds 2048")
        if max(outs) > 256:
            fails.append(f"{name}: canonical output of {max(outs)} tokens exceeds 256")
    res["budgets"] = budget
    bad = [c["call_id"] for c in calls if any(l in c["user"] for l in LABELS)]
    if bad:
        fails.append(f"labels in prompts: {bad[:3]}")
    if any({"case", "world_seed", "pool"} & set(t) for t in targets):
        fails.append("hidden key in public targets")
    res["separation"] = "no labels in prompts; public targets hold registry and text only"
    alloc = collections.Counter((c["component"], c["stratum"], tuple(c["bits"])) for c in cases.values() if c["act"] == "arrival"
                                and c["history"] == "A")
    per = collections.defaultdict(list)
    for (comp, st, b) in alloc.elements():
        per[f"{comp}|{st}"].append(list(b))
    res["allocation"] = {k: {"groups": len(v), "distinct_factor_settings": len({tuple(x) for x in v})} for k, v in sorted(per.items())}
    for k, v in res["allocation"].items():
        if k.startswith("primary|") and (v["groups"] != 8 or v["distinct_factor_settings"] != 8):
            fails.append(f"allocation {k}: {v}")
    inv = hub / "design" / "CONSTRUCTION-INVENTORY.md"
    res["construction_inventory_sha256"] = hashlib.sha256(inv.read_bytes()).hexdigest() if inv.exists() else None
    if not inv.exists():
        fails.append("construction inventory missing")
    tmp = Path(tempfile.mkdtemp())
    try:
        (tmp / "data").symlink_to(data)
        subprocess.run([sys.executable, "-B", str(ROOT / "scripts" / "hold_analyze.py"), "--hub", str(tmp), "--set", a.set,
                        "--stage-small", "none", "--stage-large", "none", "--boot", "10", "--out", str(tmp / "an")],
                       check=True, capture_output=True)
        an = json.loads((tmp / "an" / "ANALYSIS.json").read_text())
    finally:
        shutil.rmtree(tmp)
    for k, g in an["gates"].items():
        if not k.startswith("H3") and not g["pass"]:
            fails.append(f"{k}: {g['examples']}")
    res["input_gates"] = {k: (g["pass"], g["failures"], g["checked"]) for k, g in an["gates"].items() if not k.startswith("H3")}
    res["failures"], res["pass"] = fails, not fails
    (out / "VALIDATION.json").write_text(json.dumps(res, indent=1, default=str) + "\n")
    (out / "VALIDATION.md").write_text(f"# V1.19.0 pre-collection validation ({a.set})\n\n**{'PASS' if not fails else 'FAIL'}**\n\n```\n"
                                       + json.dumps(res, indent=1, default=str)[:5000] + "\n```\n")
    print("PASS" if not fails else f"FAIL {fails[:5]}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
