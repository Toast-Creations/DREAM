"""V1.3.3 clean, open evaluation of a learned concept, with reasoning off and on.

No definition, hook or training cache reaches these prompts. Every learned
state answers the same questions with the same seeds, so conditions stay
paired. Automatic checks are structural; quality comes from a lenient blinded
review (document 19), never from matching wording to preferred answers.
"""
from dream_core.modeling import generate
from dream_core.steering import assert_no_dream_hooks
from .training import CONCEPT_SYSTEM


def concept_prompt(world, question):
    # Same shape as a closed-book exposure prompt, so only the adapter differs.
    return f"Concept world {world['id']}: {world['concept']}.\nQuestion: {question}"


def term_overlap(text, terms):
    """Share of taught terms that appear in an answer. A diagnostic, never a score."""
    folded = text.casefold()
    return sum(t.casefold() in folded for t in terms) / len(terms)


def evaluate_concepts(model, tokenizer, world, cfg, seed, check=lambda: None):
    assert_no_dream_hooks(model)
    previous = getattr(tokenizer, "dream_chat_kwargs", None)
    rows = []
    try:
        for index, item in enumerate(world["eval"]):
            for mode in cfg["evaluation"]["reasoning_modes"]:
                check()
                if previous is not None:
                    tokenizer.dream_chat_kwargs = {**previous, "enable_thinking": mode}
                sampling = cfg["evaluation"]["sampling"]["thinking" if mode else "direct"]
                output = generate(model, tokenizer, concept_prompt(world, item["question"]), system=CONCEPT_SYSTEM,
                    seed=seed * 1000 + index * 10 + int(mode), temperature=sampling["temperature"],
                    top_p=sampling["top_p"], top_k=sampling.get("top_k"),
                    max_input_tokens=cfg["limits"]["max_input_tokens"], max_new_tokens=cfg["limits"]["max_new_tokens"],
                    loop_guard=cfg["limits"].get("loop_guard"))
                answered = bool(output["text"].strip()) and output.get("finish_reason") == "eos" \
                    and not output.get("thinking_truncated", False)
                rows.append({"category": item["category"], "question": item["question"], "reasoning_enabled": mode,
                             **output, "answered": answered,
                             "taught_term_overlap": term_overlap(output["text"], world["taught_terms"]),
                             "rating": "pending blinded review"})
    finally:
        if previous is not None:
            tokenizer.dream_chat_kwargs = previous
        assert_no_dream_hooks(model)
    return rows


def concept_metrics(before, after):
    """Per reasoning mode: answered share and mean taught-term overlap, before and after."""
    out = {}
    for mode in sorted({r["reasoning_enabled"] for r in after}):
        b = [r for r in before if r["reasoning_enabled"] == mode]
        a = [r for r in after if r["reasoning_enabled"] == mode]
        key = "thinking" if mode else "direct"
        out[key] = {"answered_after": sum(r["answered"] for r in a) / len(a),
                    "overlap_before": sum(r["taught_term_overlap"] for r in b) / len(b) if b else None,
                    "overlap_after": sum(r["taught_term_overlap"] for r in a) / len(a),
                    "truncated_after": sum(r.get("finish_reason") == "length" for r in a),
                    "looped_after": sum(r.get("finish_reason") == "loop" for r in a)}
    return out
