"""Pinned, read-only frozen dependencies (IGUARD-v0.1).

The guard and evaluator import the frozen V1.24.0 source tree read-only. What is actually checked, and when:

- activate() (default, every stage): hashes exactly the two decision dependencies in DECISION_PINS
  (src/tempo/refres.py, src/tempo/factored.py) before anything is imported from the frozen tree, and refuses to run
  unless bytecode writes are disabled. Other frozen modules (e.g. tempo.kidconfscore, tempo.holdeval, dream_core.*)
  are NOT individually hash-checked by activate() unless the optional expected_all map is passed (no stage does so).
- ig_plan (before any decision): recomputes dream_core.ledger.release_source_hash over each frozen source tree and
  requires it to equal that study's FROZEN-PROTOCOL.json source_sha256 (full source validation), and records every
  tempo/dream_core file hash in DEPENDENCIES.json.
- ig_decide records dependency_hashes() in each SEAL; ig_evaluate refuses a seal whose recorded hashes differ from the
  tree it is evaluating with. This comparison happens after import, so it detects drift between stages rather than
  preventing an import.
A hash mismatch at any of these points stops the stage; there is no fallback. Python bytecode writes must be disabled
(PYTHONDONTWRITEBYTECODE=1) so the frozen tree is never touched.
"""
import os as _os  # public release: local paths from environment
import sys as _sys
import hashlib
import os
import sys
from pathlib import Path

RULE = "IGUARD-v0.1"
PINNED_ROOT = Path((_os.path.expanduser(_os.environ.get("DREAM_HOME", "~/DREAM")) + "/Code/DREAM-project-1.24.0-clarified-keep-confirm-20261111"))

# Decision dependencies (the plan fixes these two hashes).
DECISION_PINS = {
    "src/tempo/refres.py": "6bd00c0880bdb9e48f78b6694641b6810ce1a948b2ae0995653246e701a90998",
    "src/tempo/factored.py": "bb03d16e988cbecd44d3d6e3137ef162ee625138d3e88081a321db22321b4a49",
}


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def tempo_files():
    """Every module of the frozen `tempo` package (recorded, not enumerated by import graph)."""
    return sorted(p for p in (PINNED_ROOT / "src" / "tempo").glob("*.py"))


def dependency_hashes():
    out = {str(p.relative_to(PINNED_ROOT)): sha256_file(p) for p in tempo_files()}
    for p in (PINNED_ROOT / "src" / "dream_core").glob("*.py") if (PINNED_ROOT / "src" / "dream_core").exists() else []:
        out[str(p.relative_to(PINNED_ROOT))] = sha256_file(p)
    return dict(sorted(out.items()))


def activate(expected_all=None):
    """Verify pins, then put the frozen src on sys.path. expected_all: optional full map (from the committed PLAN)."""
    if os.environ.get("PYTHONDONTWRITEBYTECODE") != "1" or not sys.dont_write_bytecode:
        raise SystemExit("refusing to import frozen source: set PYTHONDONTWRITEBYTECODE=1")
    for rel, want in DECISION_PINS.items():
        got = sha256_file(PINNED_ROOT / rel)
        if got != want:
            raise SystemExit(f"pinned dependency hash mismatch: {rel} {got} != {want}")
    if expected_all is not None:
        now = dependency_hashes()
        if now != expected_all:
            diff = sorted(set(now.items()) ^ set(expected_all.items()))
            raise SystemExit(f"frozen source differs from committed dependency manifest: {diff[:4]}")
    src = str(PINNED_ROOT / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
