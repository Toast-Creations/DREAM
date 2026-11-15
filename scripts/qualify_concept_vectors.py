"""Qualification helper, invoked through the observed vector-building entrypoint.

Held-out prompt-contrast alignment tests extraction consistency, not creativity
or downstream usefulness. The full study measures those outcomes separately.
V1.2.0 generalizes the check to named poles and direction kinds. For the
decategorization direction it also reports the cosine with the V1.1
divergent direction, so a renamed "be creative" vector is visible.
"""
import json
from pathlib import Path
from _bootstrap import ROOT
from dream_core.ledger import atomic_json, file_hash


def acceptance(split_cosine, cosines):
    """Fixed rule: split halves agree and at least 3/4 of held-out pairs align."""
    positives = sum(x > 0 for x in cosines)
    return split_cosine > 0 and positives * 4 >= len(cosines) * 3, positives


def qualify(model, tokenizer, cfg, pairs, pairs_path, *, heldout, poles=("divergent", "convergent"), kind="semantic"):
    import torch
    from dream_core.steering import build_vector, resolve_layer, validate_vector
    layer = cfg["steering"]["layer_index"]
    cap = cfg["limits"]["max_input_tokens"]
    build = lambda rows, p=poles: build_vector(model, tokenizer, rows, layer, cap, poles=p)
    vector = build(pairs)
    # Interleaved halves keep every template family represented in both.
    first, second = build(pairs[0::2]), build(pairs[1::2])
    cosines = [float(torch.dot(vector, build([p]))) for p in heldout]
    random_generator = torch.Generator(device="cpu").manual_seed(20261030)
    random = torch.randn(model.config.hidden_size, generator=random_generator)
    random = validate_vector(random / random.norm(), model.config.hidden_size)
    comparison = {}
    if kind != "semantic":
        divergent_pairs = json.loads((ROOT / "data/steering_prompts.json").read_text(encoding="utf-8"))
        divergent = build(divergent_pairs, ("divergent", "convergent"))
        comparison = {"divergent_cosine": float(torch.dot(vector, divergent)),
                      "divergent_contrast_sha256": file_hash(ROOT / "data/steering_prompts.json")}
    paths = [Path(cfg["steering"]["vector_path"]), Path(cfg["steering"]["random_vector_path"])]
    report_path = paths[0].parent / f"vector-qualification-{kind}.json"
    if any(p.exists() for p in paths + [report_path]):
        raise FileExistsError("Preserve existing vector artifacts")
    metadata = {"version":"1.2.0", "model_manifest_sha256":file_hash(cfg["model"]["manifest"]),
                "contrast_sha256":file_hash(pairs_path), "layer":resolve_layer(model, layer),
                "pooling":"last prompt token", "normalization":"unit L2", "enable_thinking":False,
                "poles":list(poles)}
    for path, values, label in zip(paths, [vector, random], [kind, "random"]):
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_json(path, {**metadata, "vector":values.tolist(), "kind":label})
    split_cosine = float(torch.dot(first, second))
    passed, positives = acceptance(split_cosine, cosines)
    atomic_json(report_path, {"passed":passed, "kind":kind, "training_pairs":len(pairs), "heldout_pairs":len(heldout),
        "split_half_cosine":split_cosine, "heldout_pair_cosines":cosines, "positive_heldout_pairs":positives,
        "random_direction_cosine":float(torch.dot(vector, random)), "random_seed":20261030,
        "direction_norm":float(vector.norm()), "random_norm":float(random.norm()), **comparison,
        "fixed_acceptance":"split-half cosine > 0 and at least three quarters of held-out pair cosines > 0",
        "interpretation":"Prompt-contrast consistency only; downstream exploration-specific benefit is unproven."})
    if not passed:
        raise RuntimeError("Vector consistency qualification failed; artifacts preserved, full queue halted")
    print(f"{kind} and random vectors qualified; downstream quality is still an experimental outcome.")
