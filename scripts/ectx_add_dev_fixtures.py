"""Add development-only fixtures covering every scored flip type, and record support-example coverage.

David, 2026-11-04: broaden development coverage before efficacy tuning while preserving the committed
sealed set. Writes data/dev_all.jsonl with its own commitment (COMMITMENT-dev_all.json). Never reads,
hashes, or regenerates the sealed split. Support coverage for the committed dev split is obtained by
regenerating it from its seed and proving byte identity (minus the coverage field) with its commitment.
"""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import sys

from _bootstrap import ROOT
from ectx import generate, keycheck


def jsonl_bytes(rows):
    return "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows).encode()


def coverage(eps):
    out = {}
    for e in eps:
        c = collections.Counter(s["support_flip"] or "unflipped" for s in e["support"])
        out[e["episode_id"]] = dict(sorted(c.items()))
    by_family = collections.defaultdict(collections.Counter)
    missing = collections.defaultdict(int)
    for e in eps:
        by_family[e["family"]].update(out[e["episode_id"]])
        pair_flips = {q["flip"] for q in e["queries"] if q.get("flip")}
        missing[e["family"]] += len(pair_flips - set(out[e["episode_id"]]))
    return {"per_episode": out, "totals_by_family": {f: dict(sorted(c.items())) for f, c in by_family.items()},
            "evaluated_flip_types_without_a_support_example_of_that_type": dict(missing)}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--hub", required=True)
    ap.add_argument("--per-family", type=int, default=8)
    a = ap.parse_args()
    data = Path(a.hub) / "data"
    gate1 = json.loads((data / "GATE1-REPORT.json").read_text())
    seed = gate1["seed"]
    commit = json.loads((data / "COMMITMENT.json").read_text())
    dev = generate.generate_split("dev", gate1["splits"]["dev"]["episodes"] // 3, seed)
    stripped = json.loads(json.dumps(dev))
    for e in stripped:
        for s in e["support"]:
            s.pop("support_flip")
    if hashlib.sha256(jsonl_bytes(stripped)).hexdigest() != commit["dev_sha256"]:
        raise SystemExit("regenerated dev split does not reproduce its commitment")
    target = data / "dev_all.jsonl"
    if target.exists():
        raise SystemExit("dev_all.jsonl already exists")
    eps = generate.generate_split("dev_all", a.per_family, seed)
    problems = {e["episode_id"]: keycheck.check_episode(e) for e in eps}
    bad = {k: v for k, v in problems.items() if v}
    target.write_bytes(jsonl_bytes(eps))
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    (data / "COMMITMENT-dev_all.json").write_text(json.dumps({"dev_all_sha256": digest, "seed": seed}, indent=2) + "\n")
    flips = collections.Counter((e["family"], q["flip"]) for e in eps for q in e["queries"] if q.get("side") == "A")
    report = {"dev_all": {"episodes": len(eps), "file_sha256": digest, "key_problems": bad,
                          "pairs_by_flip": {f"{f}|{k}": v for (f, k), v in sorted(flips.items())},
                          "support_coverage": coverage(eps)},
              "dev": {"reproduced_commitment": True, "support_coverage": coverage(dev)},
              "sealed": "not read; its support coverage is recorded when the frozen sealed stage opens it"}
    (data / "DEV-FIXTURES-REPORT.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"dev_all": {k: v for k, v in report["dev_all"].items() if k != "support_coverage"},
                      "dev_all_support_totals": report["dev_all"]["support_coverage"]["totals_by_family"],
                      "dev_all_missing": report["dev_all"]["support_coverage"]["evaluated_flip_types_without_a_support_example_of_that_type"],
                      "dev_support_totals": report["dev"]["support_coverage"]["totals_by_family"],
                      "dev_missing": report["dev"]["support_coverage"]["evaluated_flip_types_without_a_support_example_of_that_type"]}, indent=1))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
