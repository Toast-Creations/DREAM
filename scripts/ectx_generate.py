"""Gate 1 (no model): generate development and sealed episodes, cross-check every key, commit hashes.

The sealed file is written once and never read by any development-stage code path.
"""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import sys

from _bootstrap import ROOT
from ectx import generate, keycheck, render


def write_jsonl(path, rows):
    path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows), encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def nonce_words(ep):
    """First token of every entity name (the invented word); suffix nouns like 'Dock' are shared by design."""
    out = {ep["world_name"].split()[0]}
    def walk(x):
        if isinstance(x, dict):
            for k, v in x.items():
                out.add(k.split()[0]); walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
        elif isinstance(x, str) and x[:1].isupper():
            out.add(x.split()[0])
    walk(ep["static"])
    return out - {"places", "roads", "items", "portable", "slots", "parts", "adapters", "prices", "type", "rating",
                  "from", "to", "sources", "resource", "cost", "permit", "permits", "recipes", "inputs"}


def summary(eps):
    counts = collections.Counter()
    positions = collections.Counter()
    for e in eps:
        for q in e["queries"]:
            counts[(e["family"], q["kind"], q.get("flip") or "-")] += 1
            if q["kind"] == "pair":
                ids = [c["id"] for c in q["candidates"]]
                positions[(q["side"], ids.index(q["acceptable"][0]))] += 1
    return {"queries": {"|".join(k): v for k, v in sorted(counts.items())},
            "correct_position_by_side": {f"{s}@{p}": v for (s, p), v in sorted(positions.items())}}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--hub", required=True)
    ap.add_argument("--dev-per-family", type=int, default=8)
    ap.add_argument("--sealed-per-family", type=int, default=40)
    ap.add_argument("--seed", required=True, help="base seed string, recorded")
    a = ap.parse_args()
    data = Path(a.hub) / "data"
    data.mkdir(parents=True, exist_ok=False)
    report = {"seed": a.seed, "splits": {}}
    dev_names, sealed_names = set(), set()
    for split, n in (("dev", a.dev_per_family), ("sealed", a.sealed_per_family)):
        eps = generate.generate_split(split, n, a.seed)
        problems = {e["episode_id"]: keycheck.check_episode(e) for e in eps}
        bad = {k: v for k, v in problems.items() if v}
        words = set()
        for e in eps:
            words |= nonce_words(e)
        (dev_names if split == "dev" else sealed_names).update(words)
        sha = write_jsonl(data / f"{split}.jsonl", eps)
        tokens = [len(render.user_prompt(e, e["queries"][0])) // 4 for e in eps]
        report["splits"][split] = {"episodes": len(eps), "file_sha256": sha, "key_problems": bad,
                                   "approx_prompt_tokens_max": max(tokens), "approx_prompt_tokens_mean": sum(tokens) / len(tokens)}
        if split == "dev":
            report["splits"][split]["summary"] = summary(eps)
        else:
            report["splits"][split]["summary"] = {"note": "sealed composition counts only",
                                                  "queries": summary(eps)["queries"]}
    shared = sorted(dev_names & sealed_names)
    report["nonce_labels_shared_between_splits"] = shared
    report["passed"] = all(not s["key_problems"] for s in report["splits"].values()) and not shared
    (data / "COMMITMENT.json").write_text(json.dumps({
        "dev_sha256": report["splits"]["dev"]["file_sha256"],
        "sealed_sha256": report["splits"]["sealed"]["file_sha256"],
        "note": "sealed.jsonl must hash to this value when the frozen sealed stage opens it"}, indent=2) + "\n")
    (data / "GATE1-REPORT.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "splits"}, indent=2))
    for split, s in report["splits"].items():
        print(split, s["episodes"], "episodes; key problems:", len(s["key_problems"]), "; sha", s["file_sha256"][:12])
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
