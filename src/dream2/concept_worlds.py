"""V1.3.3 worded concept worlds for DREAM 2 learning (document 19).

Each world teaches one concept: an invented one (nothing to recall before
learning) or a real one (the test is new connections). Exposure mixes open-book
items, which show the taught material, with closed-book items, which do not, so
the adapter must hold the concept itself. Evaluation questions are open and
never contain the definition; answers go to a lenient blinded review.
"""
import json
from pathlib import Path

EVAL_CATEGORIES = ("recall", "property", "uses", "analogy", "combination", "edge_case")


def validate_concept_worlds(worlds):
    if not worlds or len({w.get("id") for w in worlds}) != len(worlds):
        raise ValueError("Concept worlds need unique IDs")
    for world in worlds:
        if world.get("split") not in ("development", "validation", "test"):
            raise ValueError("Invalid concept world split")
        if world.get("kind") not in ("invented", "real"):
            raise ValueError("Concept world kind must be invented or real")
        for key in ("id", "concept", "definition"):
            if type(world.get(key)) is not str or not world[key].strip():
                raise ValueError("Concept world needs an ID, concept and definition")
        terms = world.get("taught_terms")
        if type(terms) is not list or not terms or any(type(t) is not str or not t.strip() for t in terms):
            raise ValueError("Concept world needs taught terms for the overlap diagnostic")
        books = set()
        for item in world.get("train", []):
            if set(item) != {"question", "context", "target_text", "book"} or item["book"] not in ("open", "closed"):
                raise ValueError("Exposure items take question, context, target_text and book")
            if any(type(item[k]) is not str for k in ("question", "context", "target_text")) or not item["target_text"].strip():
                raise ValueError("Exposure text fields must be strings with a nonempty target")
            if (item["book"] == "closed") != (item["context"] == ""):
                raise ValueError("Closed-book items have no context; open-book items have one")
            books.add(item["book"])
        if books != {"open", "closed"}:
            raise ValueError("Exposure needs both open-book and closed-book items")
        if {i.get("category") for i in world.get("eval", [])} != set(EVAL_CATEGORIES):
            raise ValueError("Evaluation needs every category: " + ", ".join(EVAL_CATEGORIES))
        definition = world["definition"].casefold()
        for item in world["eval"] + [i for i in world["train"] if i["book"] == "closed"]:
            # The definition must never reach a closed-book or evaluation prompt.
            if type(item.get("question")) is not str or not item["question"].strip():
                raise ValueError("Questions must be nonempty strings")
            if definition in item["question"].casefold():
                raise ValueError(f"Definition text leaks into a closed-book or evaluation question in {world['id']}")
        for item in world["eval"]:
            if set(item) != {"category", "question"}:
                raise ValueError("Evaluation items take only category and question")
    return worlds


def load_concept_worlds(path, phase):
    worlds = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    validate_concept_worlds(worlds)
    selected = [w for w in worlds if w["split"] == phase]
    if not selected:
        raise ValueError("No concept worlds for the declared phase")
    return selected
