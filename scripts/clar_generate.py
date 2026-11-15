"""Commit the V1.23 clarification-development panel. No model calls.

Usage: clar_generate.py --hub HUB [--config PANEL.json] [--historical FILE ...]
Historical public and hidden JSONL files provide BASE prompts and world seeds for disjointness checks.
Refuses any existing panel commitment; does not overwrite prior studies.
"""
import argparse
import hashlib
import json
from pathlib import Path

from _bootstrap import ROOT
from dream_core.ledger import release_source_hash
from tempo import clarify as CL


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True, default=str) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", required=True)
    ap.add_argument("--config")
    ap.add_argument("--historical", nargs="*", default=[])
    args = ap.parse_args()
    hub = Path(args.hub)
    data = hub / "data"
    if data.exists() and any(data.rglob("*")):
        raise SystemExit("data directory is not empty; refusing to overwrite")
    cfg = {**CL.DEFAULT_CONFIG, **(json.loads(Path(args.config).read_text()) if args.config else {})}
    historical_prompts, historical_seeds = [], []
    for name in args.historical:
        for line in Path(name).read_text().splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if "base_prompt" in row:
                historical_prompts.append(row["base_prompt"])
            if "world_seed" in row:
                historical_seeds.append(row["world_seed"])
    panel = CL.generate(cfg, historical_prompts, historical_seeds)
    files = {}
    for part, result in panel.items():
        for name, rows in ((f"public/{part}-targets.jsonl", result["public"]),
                           (f"hidden/{part}-cases.jsonl", result["hidden"]),
                           (f"{part}-calls.jsonl", result["calls"]),
                           (f"{part}-construction-rejections.jsonl", result["rejected"])):
            write(data / name, rows)
            files[name] = sha(data / name)
        commitment = {"set": part, "calls": len(result["calls"]), "calls_sha256": files[f"{part}-calls.jsonl"]}
        (data / f"COMMITMENT-{part}.json").write_text(json.dumps(commitment, indent=2) + "\n")
    record = {"rule": CL.RULE, "source_sha256": release_source_hash(ROOT), "config": cfg,
              "clarification": CL.CLARIFICATION,
              "allocation": {part: result["plan"] for part, result in panel.items()},
              "calls": {part: len(result["calls"]) for part, result in panel.items()},
              "targets": {part: len(result["public"]) for part, result in panel.items()},
              "rejected_attempts": {part: len(result["rejected"]) for part, result in panel.items()},
              "historical_checked": {"files": args.historical, "prompts": len(historical_prompts),
                                     "world_seeds": len(historical_seeds)}, "files_sha256": files}
    (data / "COMMITMENT.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({k: record[k] for k in ("calls", "targets", "rejected_attempts")}))


if __name__ == "__main__":
    main()
