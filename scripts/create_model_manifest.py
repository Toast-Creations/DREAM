"""Record local model bytes after independently verifying source and revision."""
import argparse
import json
from pathlib import Path
import re
from _bootstrap import ROOT
from dream_core.ledger import file_hash


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--revision", required=True, help="Actual 40-character source commit; not a fabricated tag")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[a-fA-F0-9]{40}", args.revision):
        parser.error("Revision must be the actual immutable model commit")
    root = Path(args.model_dir).resolve()
    if not root.is_dir():
        parser.error("Local model directory does not exist")
    files = [{"path":p.relative_to(root).as_posix(), "sha256":file_hash(p)} for p in sorted(root.rglob("*"))
             if p.is_file() and p.suffix in (".safetensors", ".json", ".txt", ".model", ".jinja")
             and p.resolve() != Path(args.output).resolve()]
    with Path(args.output).open("x", encoding="utf-8") as stream:
        json.dump({"model_id":args.model_id, "revision":args.revision, "files":files,
                   "provenance_note":"Hashes record local content; operator must verify upstream authenticity."}, stream, indent=2)
    print("Recorded local hashes. This does not authenticate their source.")


if __name__ == "__main__":
    main()
