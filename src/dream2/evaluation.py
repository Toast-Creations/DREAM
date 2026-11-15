"""Clean, typed, context-free probes with separate evaluation categories."""
from dream_core.modeling import generate
from dream_core.scoring import accuracy, score
from dream_core.contracts import REQUIRED_CATEGORIES
from dream_core.steering import assert_no_dream_hooks
from .training import SYSTEM


def evaluate_world(model, tokenizer, world, cfg, check=lambda: None):
    assert_no_dream_hooks(model)
    rows = []
    for item in world["eval"]:
        check()
        question = (f"World {world['id']}. Recall only what you learned in its adapter.\n"
                    f"Question: {item['question']}\nAnswer type: {item['answer_type']}.")
        output = generate(model, tokenizer, question, system=SYSTEM,
            max_input_tokens=cfg["limits"]["max_input_tokens"], max_new_tokens=cfg["limits"]["max_new_tokens"])
        rows.append({"category": item["category"], "question": item["question"],
            "reference": item["answer"], "answer_type": item["answer_type"], **output,
            **score(output["text"], item["answer"], item["answer_type"])})
    assert_no_dream_hooks(model)
    return rows


def gate_metrics(before, after):
    counts = {c:sum(r["category"] == c for r in after) for c in REQUIRED_CATEGORIES}
    composition_before, composition_after = accuracy(before, "composition"), accuracy(after, "composition")
    anchor_before, anchor_after = accuracy(before, "anchor"), accuracy(after, "anchor")
    error_rows = [r for r in after if r["category"] in ("contradiction", "scope")]
    return {"counts": counts,
        "composition_gain": None if None in (composition_before, composition_after) else composition_after-composition_before,
        "anchor_regression": None if None in (anchor_before, anchor_after) else anchor_before-anchor_after,
        "error_rate": None if not error_rows else sum(not r["correct"] for r in error_rows)/len(error_rows),
        "accuracy": {c:accuracy(after, c) for c in REQUIRED_CATEGORIES},
        "invalid_format_rate": sum(not r["valid"] for r in after)/len(after) if after else None}
