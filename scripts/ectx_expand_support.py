"""Build a 12-example support version of a development split; scored questions stay byte-identical.

Writes data/<out>.jsonl, data/COMMITMENT-<out>.json and data/<OUT>-REPORT.json. Refuses the sealed split.
"""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import secrets
import sys

from _bootstrap import ROOT
from ectx import generate, keycheck, render


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--hub", required=True)
    ap.add_argument("--source", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--support-seed", default=None, help="default: fresh random, recorded")
    a = ap.parse_args()
    if "sealed" in a.source:
        raise SystemExit("this tool never reads a sealed split")
    data = Path(a.hub) / "data"
    src_path = data / f"{a.source}.jsonl"
    commit = json.loads((data / f"COMMITMENT-{a.source}.json").read_text())
    if hashlib.sha256(src_path.read_bytes()).hexdigest() != commit[f"{a.source}_sha256"]:
        raise SystemExit("source split does not match its commitment")
    out_path = data / f"{a.out}.jsonl"
    if out_path.exists():
        raise SystemExit(f"{out_path} exists")
    seed = a.support_seed or secrets.token_hex(8)
    src = [json.loads(x) for x in src_path.read_text().splitlines()]
    eps, problems, cover = [], {}, {}
    for e in src:
        n = generate.with_harder_support(e, seed)
        assert json.dumps(n["queries"], sort_keys=True) == json.dumps(e["queries"], sort_keys=True)
        assert {k: v for k, v in n.items() if k not in ("support", "support_design")} == \
               {k: v for k, v in e.items() if k != "support"}
        p = keycheck.check_episode(n)
        scored = {q["flip"] for q in n["queries"] if q.get("flip")}
        kinds = collections.Counter(s.get("support_flip") or "ordinary" for s in n["support"])
        if len(n["support"]) != 12 or any(kinds[k] != 2 for k in scored) or kinds["correction"] != 2 or kinds["ordinary"] != 2:
            p.append(f"composition {dict(kinds)}")
        if any(len(s["acceptable"]) != 1 or s["answer"] != s["acceptable"][0] for s in n["support"]):
            p.append("support item without a unique verified answer")
        if p:
            problems[n["episode_id"]] = p
        cover[n["episode_id"]] = dict(sorted(kinds.items()))
        eps.append(n)
    out_path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in eps), encoding="utf-8")
    digest = hashlib.sha256(out_path.read_bytes()).hexdigest()
    (data / f"COMMITMENT-{a.out}.json").write_text(json.dumps({f"{a.out}_sha256": digest, "support_seed": seed,
                                                               "source": a.source, "source_sha256": commit[f"{a.source}_sha256"]}, indent=2) + "\n")
    chars = [len(render.user_prompt(e, q)) for e in eps for q in e["queries"]]
    report = {"out": a.out, "episodes": len(eps), "sha256": digest, "support_seed": seed, "key_problems": problems,
              "scored_questions_identical_to_source": True, "support_composition": cover,
              "prompt_chars_max": max(chars), "prompt_chars_mean": sum(chars) / len(chars)}
    (data / f"{a.out.upper()}-REPORT.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "support_composition"}, indent=2))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
