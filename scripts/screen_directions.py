"""Run the V1.5.1 direction screen (see src/survival/direction_screen.py). Inference only.

Usage (inside the hub sandbox): python scripts/screen_directions.py --config /inputs/configs/<stage>.json --out DIR
"""
import argparse
import json
from pathlib import Path

from _bootstrap import ROOT
from dream_core.config import load_config
from dream_core.modeling import load_local_model


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-seconds", type=int, default=21600)
    ap.add_argument("--strengths", default="0.1,0.2")
    ap.add_argument("--candidates", default="D0,D1,D2")
    ap.add_argument("--layers", default="-12,-8,-4")
    ap.add_argument("--objects", choices=("A", "B"), default="A")
    ap.add_argument("--catcheck-phase", choices=("calibration", "test"))
    ap.add_argument("--temperature", type=float)
    ap.add_argument("--mode", choices=("perceive", "generate", "prompt", "catcheck"), default="perceive")
    ap.add_argument("--vectors-from", help="Project-relative path of saved screen vectors (e.g. artifacts/...pt)")
    a = ap.parse_args()
    cfg = load_config(a.config)
    from survival.direction_screen import run
    build = json.loads((ROOT / "data/decategorization_prompts.json").read_text(encoding="utf-8"))["build"]
    model, tokenizer, _ = load_local_model(cfg["model"])
    if any(p.requires_grad for p in model.parameters()):
        raise ValueError("The screen requires a frozen model")
    previous = getattr(tokenizer, "dream_chat_kwargs", None)
    if previous is not None:
        tokenizer.dream_chat_kwargs = {**previous, "enable_thinking": False}
    if a.mode == "catcheck":
        # V1.5.5 Stage A v2; --vectors-from and --catcheck-phase are required (--temperature for the test phase).
        from survival.categorization_check import run as run_catcheck
        out = run_catcheck(model, tokenizer, a.out, ROOT / a.vectors_from, a.catcheck_phase,
                           a.temperature, a.max_seconds)
        print(f"Categorization check complete: {out}")
        return
    out = run(model, tokenizer, cfg, a.out, build, cfg["steering"].get("vector_path"), a.max_seconds,
              strengths=tuple(float(x) for x in a.strengths.split(",")), candidates=tuple(a.candidates.split(",")),
              objects=a.objects, vectors_from=(ROOT / a.vectors_from) if a.vectors_from else None,
              layers=tuple(int(x) for x in a.layers.split(",")), mode=a.mode)
    print(f"Screen complete: {out}")


if __name__ == "__main__":
    main()
