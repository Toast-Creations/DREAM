"""Export V1.2.0 decategorization outputs for blinded review, with a private key.

Three reviewer files, each shuffled with its own IDs so they cannot be joined
without the key:

* reviewer-ideas.json: every final idea (five per completed answer), identical
  fields in every arm. This is the primary rating pool.
* reviewer-notebooks.json: raw stage-1 exploration text, for judging whether
  "nonsense" carried a kernel. Rated separately from final ideas.
* reviewer-parked.json: ideas a sober pass PARKED. Only sober arms produce
  these, so this file reveals arm type and is opened only after primary
  ratings are committed (hash recorded) as in the V1.1.4 procedure.

Answers without valid ideas are counted in the key, not hidden: format failure
rates per arm are reported alongside ratings.
"""
import argparse
import json
from pathlib import Path
import random
import uuid
import _bootstrap  # noqa: F401  (adds src to sys.path)
from dream_core.ledger import atomic_json

RATING = {"novelty_1to5": None, "plausibility_1to5": None, "worth_exploring": None,
          "nonsense_with_kernel": None, "notes": ""}


def build(trials):
    ideas, notebooks, parked, key = [], [], [], []
    for name, trial in trials:
        entry = {"trial_file": name, "condition": trial["condition"], "lambda": trial["lambda"],
                 "seed": trial["seed"], "object": trial["object"],
                 "completed_five_idea_answer": trial["completed_five_idea_answer"],
                 "comedown_complete": trial.get("comedown_complete"), "idea_ids": [], "notebook_id": None,
                 "parked_ids": []}
        for idea in trial.get("final_ideas") or []:
            sample = uuid.uuid4().hex
            ideas.append({"sample_id": sample, "object": trial["object"], "description": trial["description"],
                          **{k: idea[k] for k in ("idea", "reasoning", "would_prove_wrong")}, "ratings": dict(RATING)})
            entry["idea_ids"].append(sample)
        sample = uuid.uuid4().hex
        notebooks.append({"sample_id": sample, "object": trial["object"], "text": trial["stage1"]["text"],
                          "ratings": {"has_kernel": None, "coherence_1to5": None, "notes": ""}})
        entry["notebook_id"] = sample
        for item in (trial.get("sober_structure") or {}).get("parked", []):
            sample = uuid.uuid4().hex
            parked.append({"sample_id": sample, "object": trial["object"], **item, "ratings": dict(RATING)})
            entry["parked_ids"].append(sample)
        key.append(entry)
    for i, pool in enumerate((ideas, notebooks, parked)):
        random.Random(1201 + i).shuffle(pool)
    return ideas, notebooks, parked, key


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("run_directory")
    args = parser.parse_args(); root = Path(args.run_directory).resolve()
    trials = [(p.name, json.loads(p.read_text(encoding="utf-8"))) for p in sorted(root.glob("trial-*.json"))]
    trials = [(n, t) for n, t in trials if "stage1" in t]
    if not trials:
        raise ValueError("No V1.2.0 decategorization trials found")
    ideas, notebooks, parked, key = build(trials)
    out = root / "blinded-review"
    out.mkdir(exist_ok=False)
    for name, items in (("reviewer-ideas.json", ideas), ("reviewer-notebooks.json", notebooks),
                        ("reviewer-parked.json", parked), ("private-condition-key.json", key)):
        atomic_json(out / name, items)
    print(f"Exported {len(ideas)} ideas, {len(notebooks)} notebooks, {len(parked)} parked ideas. Keep the key private.")


if __name__ == "__main__":
    main()
