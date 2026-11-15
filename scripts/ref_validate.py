"""Pre-collection validation for V1.20.0 (tokenizer only; no generation).
Usage: ref_validate.py --hub HUB --set SET --config CFG [--out DIR]
Checks: (1) input gates R1-R4 of ref_analyze (canonical exact + zero canonical compilation loss + replay; RES-DET =
hidden gold / declared refusals / bypass; rewrite fidelity; public-only recomputation) on an empty stage;
(2) budgets under the Qwen3-32B tokenizer: every BASE, DET and resolver prompt <= 2,048 input tokens (chat-rendered),
every canonical FACT-v1 reply <= 256 and every canonical resolver reply <= 128 output tokens; (3) poisoning: the hidden
case file is replaced by scrambled labels and detection/RES-DET recomputed from the public file only must not change;
(4) census of prefix records the public parser does not recognize; (5) mutation coverage of the HOLD-EVAL scorer on the
primary targets (every scored constraint changed -> the exact check fails); (6) unique original prompts; the
allocation (48 groups, 16/16/8/8, strata 8/8/4/4 per reception) and control counts; open intervals only."""
import argparse
import collections
import copy
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from _bootstrap import ROOT
from tempo import factored as FA, holdeval as HE, holdout as HO, refgen as RG, refres as RR, render  # noqa: F401
from dream_core.modeling import render_chat
from hold_coverage import mutations


def load(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", required=True)
    ap.add_argument("--set", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--out")
    a = ap.parse_args()
    hub, data = Path(a.hub), Path(a.hub) / "data"
    out = Path(a.out) if a.out else hub / "phase0" / a.set
    out.mkdir(parents=True, exist_ok=True)
    T = load(data / "public" / f"{a.set}-targets.jsonl")
    H = {h["target"]: h for h in load(data / "hidden" / f"{a.set}-cases.jsonl")}
    fails, res = [], {}
    from transformers import AutoTokenizer
    cfg = json.loads(Path(a.config).read_text())["model"]
    tok = AutoTokenizer.from_pretrained(cfg["path"], local_files_only=True)
    tok.dream_chat_kwargs = {"enable_thinking": False}
    n_in = lambda u: len(tok(render_chat(tok, u, system=render.SYSTEM, enable_thinking=False), add_special_tokens=False)["input_ids"])
    n_out = lambda s: len(tok(s)["input_ids"])
    ins, fouts, routs = [], [], []
    for t in T:
        h = H[t["target"]]
        for k in ("base_prompt", "det_prompt", "resolver_prompt"):
            if t.get(k):
                ins.append(n_in(t[k]))
        gold = HO.public(h["case"])[-1]
        fouts.append(n_out(json.dumps(dict(FA.canonical_factored(gold), evidence=t["target_text"].split(": ", 1)[1]), indent=2)))
        if t.get("resolver_prompt"):
            f = h.get("gold_field") or None
            ids = [e["record_id"] for e in t["prefix"]]
            routs.append(n_out(json.dumps({"field": f, "records": ids}, indent=2)))
    res["budgets"] = {"max_input": max(ins), "max_fact_output": max(fouts), "max_resolver_output": max(routs or [0])}
    if max(ins) > 2048 or max(fouts) > 256 or max(routs or [0]) > 128:
        fails.append(f"budget exceeded {res['budgets']}")
    # poisoning: recompute from public only while the hidden file is scrambled
    tmp = Path(tempfile.mkdtemp())
    try:
        (tmp / "data" / "public").mkdir(parents=True)
        (tmp / "data" / "hidden").mkdir(parents=True)
        shutil.copy(data / "public" / f"{a.set}-targets.jsonl", tmp / "data" / "public")
        scr = []
        for h in H.values():
            x = copy.deepcopy(h)
            x["gold_field"] = "Poison.on_hand"
            x["case"]["field"] = "Poison.on_hand"
            x["case"]["selected"] = "Poison"
            scr.append(x)
        (tmp / "data" / "hidden" / f"{a.set}-cases.jsonl").write_text("\n".join(json.dumps(x, default=str) for x in scr) + "\n")
        diff = 0
        for t in load(tmp / "data" / "public" / f"{a.set}-targets.jsonl"):
            pi = RR.PublicInput.make(t["prefix"], t["target_text"], t["registry_order"])
            d = RR.detect(t["target_text"])
            if d != t["detection"] or (d["route"] == "resolve" and (RR.resolve_det(pi, d) != t["det"] or
                                                                    RR.resolver_prompt(pi, d) != t["resolver_prompt"])):
                diff += 1
        res["poisoning"] = f"{diff} public decisions changed with the hidden file scrambled"
        if diff:
            fails.append("poisoning changed public decisions")
    finally:
        shutil.rmtree(tmp)
    unrec = collections.Counter()
    for t in T:
        for e in t["prefix"]:
            r = RR.parse_record(e["record_id"], e["raw_text"])
            unrec[(t["component"], r["kind"])] += 1
    res["prefix_record_kinds"] = {f"{k[0]}|{k[1]}": v for k, v in sorted(unrec.items())}
    if any(k[1] == "unrecognized" and k[0] == "primary" for k in unrec):
        fails.append("unrecognized prefix records in primary targets")
    cov = collections.Counter()
    worlds = {}
    for tid, h in H.items():
        if h["component"] != "primary":
            continue
        k = (h["world_seed"], h["pool"])
        worlds.setdefault(k, HO._world(*k)[0])
        w, case = worlds[k], h["case"]
        reg = next(t["registry"] for t in T if t["target"] == tid)
        base = dict(FA.canonical_factored(HO.public(case)[-1]), evidence=case["text"][-25:])
        for name, mut in mutations(base, case, w).items():
            o = copy.deepcopy(base)
            mut(o)
            s = HE.score(json.dumps(o), case, w, reg)[0]
            cov[name] += 1
            if s["exact"]:
                fails.append(f"{tid} mutation {name} not detected")
    res["mutation_classes"] = dict(cov)
    prim = [t for t in T if t["component"] == "primary"]
    groups = {t["group"]: (t["family"], t["reception"]) for t in prim}
    res["allocation"] = {"groups": len(groups), "by_family": dict(collections.Counter(f for f, _ in groups.values())),
                         "by_stratum": dict(collections.Counter(f"{f}|{r}" for f, r in groups.values())),
                         "targets": len(prim), "controls": dict(collections.Counter(t["component"] for t in T if t["component"] != "primary")),
                         "finite_corrections": sum(bool(H[t["target"]]["case"]["finite"]) for t in prim)}
    if res["allocation"]["finite_corrections"]:
        fails.append("finite correction intervals present")
    if len({t["base_prompt"] for t in prim}) != len(prim):
        fails.append("duplicate original prompts")
    tmp = Path(tempfile.mkdtemp())
    try:
        (tmp / "data").symlink_to(data)
        subprocess.run([sys.executable, "-B", str(ROOT / "scripts" / "ref_analyze.py"), "--hub", str(tmp), "--set", a.set,
                        "--stage-a", "none", "--stage-b", "none", "--boot", "10", "--out", str(tmp / "an")], check=True,
                       capture_output=True)
        an = json.loads((tmp / "an" / "ANALYSIS.json").read_text())
    finally:
        shutil.rmtree(tmp)
    for k, g in an["gates"].items():
        if k[:2] in ("R1", "R2", "R3", "R4") and not g["pass"]:
            fails.append(f"{k}: {g['examples']}")
    res["input_gates"] = {k[:2]: (g["pass"], g["failures"], g["checked"]) for k, g in an["gates"].items() if k[:2] in ("R1", "R2", "R3", "R4")}
    res["failures"], res["pass"] = fails[:50], not fails
    (out / "VALIDATION.json").write_text(json.dumps(res, indent=1, default=str) + "\n")
    (out / "VALIDATION.md").write_text(f"# V1.20.0 pre-collection validation ({a.set})\n\n**{'PASS' if not fails else 'FAIL'}**\n\n```\n"
                                       + json.dumps(res, indent=1, default=str)[:5000] + "\n```\n")
    print("PASS" if not fails else f"FAIL {fails[:4]}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
