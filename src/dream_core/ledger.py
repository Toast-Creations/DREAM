"""Persist per-trial records and check cooperative run budgets.

Each run gets a new directory. Completed records survive a later Python error;
status.json records the final context-manager outcome. This is a local research
ledger, not a protected external controller, authenticated audit log, automatic
checkpoint system, or an OS-level enforcement of CPU/GPU time and disk use.
"""
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import time
import uuid


def file_hash(path):
    """Stream SHA-256 over exact file bytes without loading the whole file at once."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_hash(obj):
    """Hash a key-sorted JSON representation, rejecting NaN/Infinity as evidence."""
    return hashlib.sha256(json.dumps(obj, sort_keys=True, allow_nan=False).encode()).hexdigest()


def release_source_hash(root):
    """Hash source, tests, launch/build scripts and dependency declarations.

    V1.1.4 includes scripts so a changed runner invalidates prior ML evidence.
    Data/config/model identities are recorded separately per experiment. Hashes
    detect changes, not a malicious party able to rewrite both files and records.
    """
    root = Path(root)
    paths = [p for folder in ("src", "tests", "scripts") for p in sorted((root/folder).rglob("*.py"))]
    paths += [root/name for name in ("pyproject.toml", "requirements-ml.txt") if (root/name).exists()]
    rows = [{"path": p.relative_to(root).as_posix(), "sha256": file_hash(p)} for p in paths]
    return json_hash(rows)


def atomic_json(path, obj):
    """Replace one record through a same-directory temporary file, after flush.

    fsync improves durability of the file bytes; os.replace avoids exposing a
    half-written JSON file to readers. This is not an atomic transaction over
    multiple records or a guarantee against every storage/power failure. Existing
    status files are intentionally replaced; trial naming is owned by RunLedger.
    """
    path = Path(path)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(obj, stream, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class RunLedger:
    """Own unique output paths, elapsed-time checks, and completed-trial counters."""
    def __init__(self, root, config, max_seconds=1800, max_trials=100):
        """Create a new run and save configuration plus observed package versions.

        A timestamp plus random suffix separates runs; exist_ok=False rejects a
        collision. Package versions are provenance, not a reproducibility lock
        or evidence that an installed ML stack passed integration tests.
        """
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.path = Path(root) / (stamp + "-" + uuid.uuid4().hex[:12])
        self.path.mkdir(parents=True, exist_ok=False)
        self.started = time.monotonic()
        self.max_seconds = max_seconds
        self.max_trials = max_trials
        self.count = 0
        self.config_hash = json_hash(config)
        atomic_json(self.path / "config.json", config)
        versions = {}
        for name in ("torch", "transformers", "peft", "safetensors", "numpy", "accelerate"):
            try:
                versions[name] = importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:
                versions[name] = None
        atomic_json(self.path / "environment.json", {"python": platform.python_version(),
                    "platform": platform.platform(), "packages": versions})
        self.status("running")

    def check(self):
        """Raise after the elapsed cap when called; do not interrupt active work.

        monotonic() measures elapsed wall time without clock-adjustment jumps.
        Limits are cooperative: a long forward/backward or blocked I/O can run
        beyond the deadline before another check gets CPU control.
        """
        if time.monotonic() - self.started > self.max_seconds:
            raise TimeoutError("Preregistered wall-time budget exceeded")

    def record(self, obj):
        """Save one completed record before incrementing its in-memory counter.

        count tracks recorded trials, not every forward call or attempted step.
        Orchestrators also bound the full planned grid before starting execution.
        """
        self.check()
        if self.count >= self.max_trials:
            raise RuntimeError("Trial budget exceeded")
        atomic_json(self.path / f"trial-{self.count:06d}.json", obj)
        self.count += 1

    def status(self, state, error_type=None):
        """Save the latest lifecycle state; no automatic periodic heartbeat runs."""
        atomic_json(self.path / "status.json", {"state": state, "completed_trials": self.count,
                    "config_sha256": self.config_hash, "error_type": error_type,
                    "elapsed_seconds": time.monotonic() - self.started})

    def __enter__(self):
        return self

    def __exit__(self, kind, value, tb):
        """Record the Python exit path and propagate failures to the caller.

        A hard kill or power loss can leave the last status as 'running'; it must
        not be mistaken for completed work or silently restarted as a fresh run.
        """
        self.status("completed" if kind is None else "interrupted" if kind is KeyboardInterrupt else "failed",
                    None if kind is None else kind.__name__)
        return False
