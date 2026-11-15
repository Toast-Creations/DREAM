"""Build the frozen set of norm-matched random directions for the idea-survival random arm (V1.4.0).

Protocol: Gaussian unit vectors from seeds 271828-271836 (nine by default), each bound to
the model manifest hash and resolved layer like any steering artifact (kind "random").
"Norm-matched" holds by construction: the hook scales every unit direction by the same
relative strength times ||h||, exactly as for the targeted direction.
No model weights are loaded; hidden size and depth come from the model's config.json.

Usage: python scripts/build_random_set.py --config CFG --out DIR [--first-seed 271828]
"""
import argparse
import json
from pathlib import Path
from _bootstrap import ROOT
from dream_core.config import load_config
from dream_core.ledger import atomic_json, file_hash


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--first-seed", type=int, default=271828)
    args = parser.parse_args()
    import torch
    cfg = load_config(args.config)
    model_cfg = json.loads((Path(cfg["model"]["path"]) / "config.json").read_text())
    hidden, depth = model_cfg["hidden_size"], model_cfg["num_hidden_layers"]
    layer = cfg["steering"]["layer_index"]
    resolved = layer if layer >= 0 else depth + layer
    if not 0 <= resolved < depth:
        raise ValueError("Layer outside model")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for i in range(cfg["steering"]["random_count"]):
        seed = args.first_seed + i
        path = out / f"random-direction-{i:02d}.json"
        if path.exists():
            raise FileExistsError("Preserve existing random directions")
        g = torch.Generator(device="cpu").manual_seed(seed)
        v = torch.randn(hidden, generator=g, dtype=torch.float32)
        v = v / v.norm()
        atomic_json(path, {"version": "1.4.0", "model_manifest_sha256": file_hash(cfg["model"]["manifest"]),
                           "layer": resolved, "kind": "random", "seed": seed, "distribution": "standard Gaussian, unit L2",
                           "normalization": "unit L2", "vector": v.tolist()})
        rows.append({"index": i, "seed": seed, "path": path.name, "sha256": file_hash(path)})
    atomic_json(out / "random-set-manifest.json", {"first_seed": args.first_seed, "count": len(rows),
                "hidden_size": hidden, "layer": resolved, "directions": rows})
    print(f"Wrote {len(rows)} random directions to {out}")


if __name__ == "__main__":
    main()
