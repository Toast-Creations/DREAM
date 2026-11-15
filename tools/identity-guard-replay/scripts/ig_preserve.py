"""Before/after hash snapshot of existing evidence (both study hubs and both frozen source trees).

Usage: python -B scripts/ig_preserve.py snapshot OUT.json
       python -B scripts/ig_preserve.py compare BEFORE.json AFTER.json PRESERVATION.json
"""
import os as _os  # public release: local paths from environment
import sys as _sys
import hashlib
import json
import sys
from pathlib import Path

ROOTS = [
    (_os.path.expanduser(_os.environ.get("DREAM_HOME", "~/DREAM")) + "/Runs/temporal-clarified-keep-confirm-20261111-063336"),
    (_os.path.expanduser(_os.environ.get("DREAM_HOME", "~/DREAM")) + "/Runs/temporal-keepid-confirm-20261110-150658"),
    (_os.path.expanduser(_os.environ.get("DREAM_HOME", "~/DREAM")) + "/Code/DREAM-project-1.24.0-clarified-keep-confirm-20261111"),
    (_os.path.expanduser(_os.environ.get("DREAM_HOME", "~/DREAM")) + "/Code/DREAM-project-1.22.0-keepid-confirm-20261110"),
]


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def snapshot():
    out = {}
    for root in ROOTS:
        r = Path(root)
        out[root] = {str(p.relative_to(r)): sha(p) for p in sorted(r.rglob("*")) if p.is_file() and not p.is_symlink()}
    return out


def compare(before, after):
    res = {"roots": {}, "unchanged": True}
    for root in ROOTS:
        b, a = before.get(root, {}), after.get(root, {})
        changed = sorted(k for k in set(a) & set(b) if a[k] != b[k])
        added, removed = sorted(set(a) - set(b)), sorted(set(b) - set(a))
        ok = not (changed or added or removed)
        res["roots"][root] = {"files": len(b), "unchanged": ok, "changed": changed, "added": added,
                              "removed": removed,
                              "tree_sha256": hashlib.sha256(json.dumps(b, sort_keys=True).encode()).hexdigest()}
        res["unchanged"] = res["unchanged"] and ok
    return res


if __name__ == "__main__":
    if sys.argv[1] == "snapshot":
        Path(sys.argv[2]).write_text(json.dumps(snapshot(), indent=0, sort_keys=True) + "\n")
        print("snapshot", sys.argv[2])
    else:
        r = compare(json.loads(Path(sys.argv[2]).read_text()), json.loads(Path(sys.argv[3]).read_text()))
        Path(sys.argv[4]).write_text(json.dumps(r, indent=1, sort_keys=True) + "\n")
        print(json.dumps({"unchanged": r["unchanged"],
                          **{k: v["unchanged"] for k, v in r["roots"].items()}}))
        sys.exit(0 if r["unchanged"] else 2)
