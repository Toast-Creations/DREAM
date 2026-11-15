"""Paired five-association study. Structural checks never claim semantic quality.

The primary reasoning comparison uses zero steering in both modes. Optional
steering/temperature arms are secondary. All modes share caps, prompts and
sampling. Actual token use is an outcome; equal caps are not equal computation.
"""
from contextlib import nullcontext
import json
from pathlib import Path
import random
import unicodedata

SYSTEM = ('Use the supplied concept definition. Return exactly one JSON object with only the key '
          '"associations", whose value is exactly five objects. Each object must contain only '
          '"item" and "connection", both nonempty strings. Give a specific example or application '
          'and explain its connection in one short sentence. No Markdown fences or extra final text.')


def load_concepts(path, phase):
    all_rows = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    if not all_rows or len({x["id"] for x in all_rows}) != len(all_rows):
        raise ValueError("Concept IDs must be nonempty and unique")
    for row in all_rows:
        if row.get("split") not in ("development", "validation", "test"):
            raise ValueError("Invalid concept split")
        if any(not isinstance(row.get(k), str) or not row[k].strip() for k in ("id", "concept", "definition")):
            raise ValueError("Concept requires an ID, name and definition")
    rows = [x for x in all_rows if x["split"] == phase]
    if not rows:
        raise ValueError("No concepts for declared phase")
    return rows


def prompt(row):
    return (f'Concept: {row["concept"]}.\nDefinition: {row["definition"]}\n'
            'Give five distinct examples or applications related to this concept. '
            'Use different contexts where they fit. Explain the specific relationship for each; '
            'avoid five synonyms or five minor variations of one example. Include at least two less obvious '
            'connections, while keeping all five accurate and meaningful.')


def parse_associations(text):
    def unique(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj:
                raise ValueError("Duplicate JSON key")
            obj[key] = value
        return obj
    try:
        obj = json.loads(text, object_pairs_hook=unique)
        if type(obj) is not dict or set(obj) != {"associations"}:
            raise ValueError("Expected one associations object")
        items = obj["associations"]
        if type(items) is not list or len(items) != 5:
            raise ValueError("Exactly five associations required")
        for item in items:
            if type(item) is not dict or set(item) != {"item", "connection"}:
                raise ValueError("Each association needs only item and connection")
            if any(type(v) is not str or not v.strip() for v in item.values()):
                raise ValueError("Association fields must be nonempty strings")
        names = [unicodedata.normalize("NFKC", x["item"]).strip().casefold() for x in items]
        if len(set(names)) != 5:
            raise ValueError("Duplicate association labels")
        return {"valid": True, "associations": items, "format_error": None,
                "semantic_quality": "pending blinded review"}
    except (ValueError, TypeError) as exc:
        return {"valid": False, "associations": [], "format_error": str(exc),
                "semantic_quality": "pending blinded review"}


def conditions(cfg):
    cells = []
    for lam in cfg["steering"]["lambda_values"]:
        for mode in cfg["association"]["reasoning_modes"]:
            cells.append({"condition": "ordinary" if lam == 0 else "steered", "lambda": lam,
                          "reasoning_enabled": mode, "temperature": cfg["generation"]["temperature"],
                          "vector_kind": "none" if lam == 0 else "semantic"})
    if cfg["association"]["include_temperature_control"]:
        for mode in cfg["association"]["reasoning_modes"]:
            cells.append({"condition": "temperature", "lambda": 0.0,
                          "reasoning_enabled": mode, "temperature": cfg["generation"]["high_temperature"],
                          "vector_kind": "none"})
    if cfg["association"].get("include_random_direction_control", False):
        for mode in cfg["association"]["reasoning_modes"]:
            cells.append({"condition": "random_direction", "lambda": cfg["association"]["random_direction_strength"],
                          "reasoning_enabled": mode, "temperature": cfg["generation"]["temperature"],
                          "vector_kind": "random"})
    return cells


def run(model, tokenizer, cfg):
    from dream_core.ledger import RunLedger, atomic_json, file_hash
    from dream_core.modeling import generate
    from dream_core.planning import trial_count
    from dream_core.steering import MaskedSteerer, assert_no_dream_hooks, load_vector
    rows = load_concepts(cfg["data_path"], cfg["phase"])
    if len(rows) > cfg["limits"]["max_worlds"] or trial_count(cfg, len(rows)) > cfg["limits"]["max_trials"]:
        raise ValueError("Concept plan exceeds budget")
    if any(p.requires_grad for p in model.parameters()):
        raise ValueError("Concept comparison requires a frozen model")
    vectors = {}
    if any(x > 0 for x in cfg["steering"]["lambda_values"]):
        vectors["semantic"] = load_vector(cfg["steering"]["vector_path"], model,
                             file_hash(cfg["model"]["manifest"]), cfg["steering"]["layer_index"])
    if cfg["association"].get("include_random_direction_control", False):
        vectors["random"] = load_vector(cfg["steering"]["random_vector_path"], model,
                             file_hash(cfg["model"]["manifest"]), cfg["steering"]["layer_index"])
    previous = getattr(tokenizer, "dream_chat_kwargs", None)
    with RunLedger(cfg["output_dir"], cfg, cfg["limits"]["max_seconds"], cfg["limits"]["max_trials"]) as ledger:
        atomic_json(ledger.path / "input_hashes.json", {"concepts": file_hash(cfg["data_path"]),
                    "model": file_hash(cfg["model"]["manifest"]),
                    "vector": file_hash(cfg["steering"]["vector_path"]) if "semantic" in vectors else None,
                    "random_vector": file_hash(cfg["steering"]["random_vector_path"]) if "random" in vectors else None})
        queue = [(row, seed, cell) for row in rows for seed in cfg["seeds"] for cell in conditions(cfg)]
        # Fixed random interleaving prevents reasoning mode from being a stage
        # or time-of-session confound. Every response has a fresh context/cache.
        random.Random(20261030).shuffle(queue)
        try:
            for row, seed, cell in queue:
                ledger.check()
                tokenizer.dream_chat_kwargs = {"enable_thinking": cell["reasoning_enabled"]}
                assert_no_dream_hooks(model)
                ctx = (MaskedSteerer(model, cfg["steering"]["layer_index"], vectors[cell["vector_kind"]], cell["lambda"],
                       generation=True, schedule=False, max_new_tokens=cfg["limits"]["max_new_tokens"])
                       if cell["lambda"] > 0 else nullcontext())
                with ctx as steerer:
                    output = generate(model, tokenizer, prompt(row), system=SYSTEM, seed=seed,
                        temperature=cell["temperature"], top_p=cfg["generation"]["top_p"], top_k=cfg["generation"]["top_k"],
                        max_input_tokens=cfg["limits"]["max_input_tokens"], max_new_tokens=cfg["limits"]["max_new_tokens"])
                assert_no_dream_hooks(model)
                parsed = parse_associations(output["text"])
                usable = parsed["valid"] and output.get("finish_reason") == "eos" and not output.get("thinking_truncated", False)
                ledger.record({"status": "completed", "task_id": row["id"], "concept": row["concept"],
                               "definition": row["definition"], "seed": seed, **cell, "output": output,
                               "structure": parsed, "completed_five_item_answer": usable,
                               "steering_trace": steerer.trace if steerer is not None else [],
                               "ratings": None})
                if not usable and cfg["association"]["halt_on_invalid"]:
                    raise RuntimeError("Incomplete or invalid concept answer preserved; qualification requires review")
        finally:
            if previous is None:
                del tokenizer.dream_chat_kwargs
            else:
                tokenizer.dream_chat_kwargs = previous
            assert_no_dream_hooks(model)
    return ledger.path
