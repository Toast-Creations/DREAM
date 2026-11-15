"""Validate release source, document links, JSON, and content manifest offline."""
import argparse
import ast
import json
from pathlib import Path
import re
import sys
from _bootstrap import ROOT
from dream_core.ledger import file_hash


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-manifest",action="store_true")
    args=parser.parse_args(); errors=[]; py_count=0; links=0
    for path in ROOT.rglob("*.py"):
        if "dist" in path.parts or "__pycache__" in path.parts: continue
        try: ast.parse(path.read_text(encoding="utf-8")); py_count+=1
        except (SyntaxError,UnicodeDecodeError) as exc: errors.append(str(path)+": "+str(exc))
    for path in ROOT.rglob("*.json"):
        if "dist" in path.parts: continue
        try: json.loads(path.read_text(encoding="utf-8"))
        except ValueError as exc: errors.append(str(path)+": "+str(exc))
    for path in ROOT.rglob("*.md"):
        if "dist" in path.parts: continue
        for target in re.findall(r"\]\(([^)]+)\)",path.read_text(encoding="utf-8")):
            if target.startswith(("https://","http://","#")): continue
            links+=1
            if not (path.parent/target.split("#")[0]).exists(): errors.append("Broken link: "+str(path)+" -> "+target)
    if args.verify_manifest:
        manifest=json.loads((ROOT/"MANIFEST.json").read_text(encoding="utf-8"))
        for row in manifest["files"]:
            path=ROOT/row["path"]
            if not path.is_file() or file_hash(path)!=row["sha256"]: errors.append("Manifest mismatch: "+row["path"])
    report={"python_sources_parsed":py_count,"local_document_links_checked":links,"errors":errors}
    print(json.dumps(report,indent=2))
    return 1 if errors else 0


if __name__=="__main__":sys.exit(main())
