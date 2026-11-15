"""Export blinded final answers and structural outcomes; no automatic creativity score.

Original records stay read-only. The output directory must be outside the run
directory and must not exist. Keep the private condition key away from raters.
"""
import argparse
import csv
import json
from pathlib import Path
import random
from _bootstrap import ROOT
from dream_core.ledger import atomic_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_directory"); parser.add_argument("output_directory")
    args = parser.parse_args()
    root = Path(args.run_directory).resolve(); out = Path(args.output_directory).resolve()
    if out.is_relative_to(root):
        raise ValueError("Write analysis outside the original trial directory")
    rows = [(p.name, json.loads(p.read_text())) for p in sorted(root.glob("trial-*.json"))]
    if not rows:
        raise ValueError("No completed concept records")
    out.mkdir(parents=True, exist_ok=False)
    random.Random(48371).shuffle(rows)
    key = {}; summary = {}
    with (out / "blinded-review.csv").open("x", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["review_id", "concept", "definition", "final_answer", "valid_distinct_count_0_to_5", "breadth_0_to_5", "useful_association_quality_0_to_10", "notes"])
        for i, (name, row) in enumerate(rows):
            review_id = f"C{i+1:04d}"
            writer.writerow([review_id, row["concept"], row["definition"], row["output"]["text"], "", "", "", ""])
            key[review_id] = {"trial":name, **{k:row[k] for k in ("task_id", "seed", "condition", "lambda", "reasoning_enabled")}}
            cell = f'{row["condition"]}/lambda={row["lambda"]}/reasoning={row["reasoning_enabled"]}'
            s = summary.setdefault(cell, {"responses":0, "completed_five_item_answers":0, "output_tokens":0, "length_stops":0})
            s["responses"] += 1; s["completed_five_item_answers"] += bool(row["completed_five_item_answer"])
            s["output_tokens"] += row["output"]["output_tokens"]
            s["length_stops"] += row["output"]["finish_reason"] == "length"
    atomic_json(out / "PRIVATE-condition-key.json", key)
    atomic_json(out / "structural-summary.json", {"status":"exploratory; semantic ratings pending", "cells":summary,
        "analysis_unit":"concept, with seeds and five items nested within concept",
        "primary_contrast":"reasoning on minus off, ordinary zero-steering only; relevance-gated association quality 0 to 10",
        "quality_claim":"No semantic or creativity result follows from schema validity."})
    print(out)


if __name__ == "__main__":
    main()
