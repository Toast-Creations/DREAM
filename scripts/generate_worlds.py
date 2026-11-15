"""Generate separate development, validation, and final-test world files."""
import argparse
import json
from _bootstrap import ROOT
from dream2.worlds import generate_worlds, validate_worlds


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count-per-split", type=int, default=12)
    parser.add_argument("--seed", type=int, default=1101)
    parser.add_argument("--output", default=str(ROOT / "data" / "microworlds.jsonl"))
    args = parser.parse_args()
    worlds = []
    for offset, split in enumerate(("development", "validation", "test")):
        worlds += generate_worlds(args.count_per_split, args.seed+100000*offset, split)
    validate_worlds(worlds)
    from pathlib import Path
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Overwrite requires deliberate removal or a different output path.
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        for world in worlds:
            stream.write(json.dumps(world, separators=(",", ":")) + "\n")
    print(f"Wrote {len(worlds)} verified worlds to {path}")


if __name__ == "__main__":
    main()
