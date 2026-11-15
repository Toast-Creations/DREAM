"""Export V1.3.3 broad DREAM and DREAM 2 concept answers for a lenient blinded review.

Two reviewer files, shuffled with their own IDs, plus one private key:

* reviewer-dream.json: every final (integration) answer of the broad DREAM run,
  with its task. Steering arm, seed and temperature are hidden.
* reviewer-concepts.json: every DREAM 2 concept answer, the shared before-learning
  answers included, with the concept's taught material so the reviewer can judge
  whether it was used. Condition, reasoning mode and before/after are hidden;
  reasoning text is never shown, only the answer.

Rubric (document 19): uses_taught_idea 0-2, creative_connection 0-2, coherent 0-1.
Loose, metaphorical or strange use earns credit; strangeness is never penalized.
Commit the ratings hash before opening the key. Writes only to --out.
"""
import argparse
import json
from pathlib import Path
import random
import uuid
import _bootstrap  # noqa: F401  (adds src to sys.path)
from dream_core.ledger import atomic_json

RATING = {"uses_taught_idea_0to2": None, "creative_connection_0to2": None, "coherent_0to1": None, "notes": ""}


def dream_pool(root):
    pool, key = [], []
    for path in sorted(root.glob("trial-*.json")):
        trial = json.loads(path.read_text(encoding="utf-8"))
        if trial["status"] != "completed":
            # Looped steps have no final answer to rate; the key counts them per arm.
            key.append({"sample_id": None, "trial_file": path.name, "status": trial["status"], "stage": trial.get("stage"),
                        "condition": trial.get("condition"), "lambda": trial.get("lambda"), "vector": trial.get("vector"),
                        "seed": trial["seed"]})
            continue
        sample = uuid.uuid4().hex
        pool.append({"sample_id": sample, "task": trial["task_id"], "category": trial["category"],
                     "answer": trial["integrated"]["text"], "ratings": dict(RATING)})
        key.append({"sample_id": sample, "trial_file": path.name, "condition": trial["condition"],
                    "lambda": trial["lambda"], "vector": trial.get("vector"), "seed": trial["seed"],
                    "finish_reason": trial["integrated"].get("finish_reason")})
    return pool, key


def concept_pool(root, worlds):
    pool, key, seen_before = [], [], set()
    for path in sorted(root.glob("trial-*.json")):
        trial = json.loads(path.read_text(encoding="utf-8"))
        world = worlds[trial["world_id"]]
        stages = [("after", trial["after_eval"])]
        if (trial["world_id"], trial["seed"]) not in seen_before:
            # The before-learning baseline is shared by a world's conditions; rate it once.
            seen_before.add((trial["world_id"], trial["seed"]))
            stages.insert(0, ("before", trial["before_eval"]))
        for stage, rows in stages:
            for row in rows:
                sample = uuid.uuid4().hex
                pool.append({"sample_id": sample, "concept": world["concept"], "taught_definition": world["definition"],
                             "question": row["question"], "answer": row["text"], "ratings": dict(RATING)})
                key.append({"sample_id": sample, "trial_file": path.name, "world_id": trial["world_id"],
                            "kind": world["kind"], "stage": stage,
                            "condition": "before_learning" if stage == "before" else trial["condition"],
                            "lambda": trial["lambda"], "eta": trial["eta"], "vector": trial.get("vector"),
                            "category": row["category"], "reasoning_enabled": row["reasoning_enabled"],
                            "answered": row["answered"], "taught_term_overlap": row["taught_term_overlap"]})
    return pool, key


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dream", help="broad DREAM run directory (trial-*.json)")
    parser.add_argument("--concepts", help="DREAM 2 concept run directory (trial-*.json)")
    parser.add_argument("--worlds", help="concept-world data file used by that run")
    parser.add_argument("--out", required=True, help="new review directory (must not exist)")
    args = parser.parse_args()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    key = {}
    if args.dream:
        pool, key["dream"] = dream_pool(Path(args.dream).resolve())
        random.Random(1331).shuffle(pool)
        atomic_json(out / "reviewer-dream.json", pool)
    if args.concepts:
        lines = Path(args.worlds).read_text(encoding="utf-8").splitlines()
        worlds = {w["id"]: w for w in (json.loads(line) for line in lines if line.strip())}
        pool, key["concepts"] = concept_pool(Path(args.concepts).resolve(), worlds)
        random.Random(1332).shuffle(pool)
        atomic_json(out / "reviewer-concepts.json", pool)
    atomic_json(out / "private-condition-key.json", key)
    print(f"Exported {', '.join(f'{k}: {len(v)}' for k, v in key.items())}. Keep the key private.")


if __name__ == "__main__":
    main()
