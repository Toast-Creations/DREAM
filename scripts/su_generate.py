"""Commit an EVT-suite study allocation, allowed membership and fresh panel; no model calls.

Usage: su_generate.py --hub HUB --config PANEL.json [--historical FILE ...]
All configuration is explicit. The allocation manifest is written before any worlds are generated.
Any existing data artifact blocks generation; prior studies and partially generated attempts are preserved.
"""
import argparse
import hashlib
import json
from pathlib import Path

from _bootstrap import ROOT
from dream_core.ledger import release_source_hash
from tempo import clarify as CL, evsuite as CC


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
    ap.add_argument("--config", required=True)
    ap.add_argument("--historical", nargs="*", default=[])
    args = ap.parse_args()
    cfg = CC.validate_config(json.loads(Path(args.config).read_text()))
    hub = Path(args.hub)
    data = hub / "data"
    if data.exists() and any(data.rglob("*")):
        raise SystemExit("data directory is not empty; refusing to overwrite")
    historical_prompts, historical_seeds = [], []
    for name in args.historical:
        for line in Path(name).read_text().splitlines():
            if line.strip():
                row = json.loads(line)
                if "base_prompt" in row:
                    historical_prompts.append(row["base_prompt"])
                if "world_seed" in row:
                    historical_seeds.append(row["world_seed"])
    allocation = {part: CC.plan(cfg, smoke=(part == "smoke")) for part in ("main", "smoke")}
    write(data / "ALLOCATION.jsonl", allocation["main"] + allocation["smoke"])
    panel = CC.generate(cfg, historical_prompts, historical_seeds, allocation)
    files = {"ALLOCATION.jsonl": sha(data / "ALLOCATION.jsonl")}
    write(data / "ALLOWED-CALLS.jsonl", CC.allowed_manifest(panel))
    files["ALLOWED-CALLS.jsonl"] = sha(data / "ALLOWED-CALLS.jsonl")
    for part, result in panel.items():
        for name, rows in ((f"public/{part}-targets.jsonl", result["public"]),
                           (f"hidden/{part}-cases.jsonl", result["hidden"]),
                           (f"{part}-calls.jsonl", result["calls"]),
                           (f"{part}-construction-rejections.jsonl", result["rejected"])):
            write(data / name, rows)
            files[name] = sha(data / name)
        commitment = {"set": part, "calls": len(result["calls"]), "calls_sha256": files[f"{part}-calls.jsonl"]}
        with (data / f"COMMITMENT-{part}.json").open("x") as fh:
            fh.write(json.dumps(commitment, indent=2) + "\n")
    record = {"study": cfg["study"], "suite": CC.SUITE, "key": cfg["key"], "source_sha256": release_source_hash(ROOT), "config": cfg,
              "config_sha256": sha(args.config), "clarification": CL.CLARIFICATION, "event_sentence": CC.EVENT_SENTENCE, "evtr_sentence": CC.EVTR_SENTENCE,
              "allocation": allocation, "calls": {part: len(result["calls"]) for part, result in panel.items()},
              "targets": {part: len(result["public"]) for part, result in panel.items()},
              "rejected_attempts": {part: len(result["rejected"]) for part, result in panel.items()},
              "historical_checked": {"files": args.historical, "prompts": len(historical_prompts),
                                     "world_seeds": len(historical_seeds)}, "files_sha256": files}
    with (data / "COMMITMENT.json").open("x") as fh:
        fh.write(json.dumps(record, indent=2) + "\n")
    print(json.dumps({key: record[key] for key in ("study", "calls", "targets", "rejected_attempts")}))


if __name__ == "__main__":
    main()
