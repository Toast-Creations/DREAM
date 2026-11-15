"""Build a JSON steering artifact bound to exact model content and layer.

``--direction divergent`` (default) is the V1.1 divergent-minus-convergent
contrast. ``--direction decategorization`` (V1.2.0) uses the build split of
data/decategorization_prompts.json. ``--qualify-full`` runs the held-out
consistency check and writes the qualified artifacts plus a report.
"""
import argparse
import json
from pathlib import Path
from _bootstrap import ROOT
from dream_core.config import load_config
from dream_core.ledger import atomic_json, file_hash, json_hash
from dream_core.modeling import load_local_model

DIRECTIONS = {
    "divergent": {"pairs": "data/steering_prompts.json", "heldout": "data/steering-validation-prompts.json",
                  "poles": ("divergent", "convergent"), "kind": "semantic"},
    "decategorization": {"pairs": "data/decategorization_prompts.json", "heldout": None,
                         "poles": ("decategorized", "categorical"), "kind": "decategorization"},
}


def load_pairs(direction):
    """Return (build pairs, held-out pairs, contrast file path) for a direction."""
    spec = DIRECTIONS[direction]
    path = ROOT / spec["pairs"]
    data = json.loads(path.read_text(encoding="utf-8"))
    if spec["heldout"] is None:
        # Held-out pairs live in the same file, with a different wording family.
        return data["build"], data["heldout"], path
    heldout_path = ROOT / spec["heldout"]
    return data, json.loads(heldout_path.read_text(encoding="utf-8")), path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--direction", choices=sorted(DIRECTIONS), default="divergent")
    parser.add_argument("--qualify-full", action="store_true")
    args = parser.parse_args()
    cfg = load_config(args.config)
    from dream_core.steering import build_vector, resolve_layer
    spec = DIRECTIONS[args.direction]
    pairs, heldout, pairs_path = load_pairs(args.direction)
    model, tokenizer, identity = load_local_model(cfg["model"])
    if args.qualify_full:
        from qualify_concept_vectors import qualify
        qualify(model, tokenizer, cfg, pairs, pairs_path, heldout=heldout, poles=spec["poles"], kind=spec["kind"])
        return
    vector = build_vector(model, tokenizer, pairs, cfg["steering"]["layer_index"], cfg["limits"]["max_input_tokens"],
                          poles=spec["poles"])
    output = Path(cfg["steering"]["vector_path"])
    if output.exists():
        raise FileExistsError("Choose a new vector artifact path rather than overwrite provenance")
    output.parent.mkdir(parents=True, exist_ok=True)
    atomic_json(output, {"version":"1.2.0", "model_manifest_sha256":file_hash(cfg["model"]["manifest"]),
        "contrast_sha256":file_hash(pairs_path), "layer":resolve_layer(model, cfg["steering"]["layer_index"]),
        "vector":vector.tolist(), "pooling":"last prompt token", "normalization":"unit L2",
        "kind":spec["kind"], "poles":list(spec["poles"])})
    print(f"Saved vector to {output}")


if __name__ == "__main__":
    main()
