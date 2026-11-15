"""Study adapters and the public-only input loader for the decision stage.

The decision stage may open ONLY:
  <hub>/data/public/main-targets.jsonl   (then immediately reduced to PUBLIC_KEYS)
  <hub>/data/main-calls.jsonl            (call_id, user_sha256 only)
  <hub>/stages/main/calls/*.json         (call_id, status, complete, attempts, user_sha256, raw only)
Anything under data/hidden or analysis/ is refused by path, and the loaders keep no other keys.
"""
import os as _os  # public release: local paths from environment
import sys as _sys
import collections
import hashlib
import json
from pathlib import Path

RUNS = Path((_os.path.expanduser(_os.environ.get("DREAM_HOME", "~/DREAM")) + "/Runs"))

STUDIES = {
    "V1.24": {"hub": RUNS / "temporal-clarified-keep-confirm-20261111-063336", "calls": 2304, "targets": 1088,
              "arrival_targets": 448, "correction_targets": 640,
              "conditions": {"KEEP_CLAR": 1088, "SUB_ORIG": 1088, "SUB_CLAR": 128},
              "primary": ["KEEP_CLAR", "SUB_ORIG"], "reference": ["SUB_CLAR"]},
    "V1.22": {"hub": RUNS / "temporal-keepid-confirm-20261110-150658", "calls": 2240, "targets": 1120,
              "arrival_targets": 336, "correction_targets": 784,
              "conditions": {"KEEP": 1120, "SUB": 1120},
              "primary": ["KEEP", "SUB"], "reference": []},
}

# Exact declared membership, pinned. Digest = sha256 of the sorted IDs joined by "\n". The call digests come from each
# study's frozen config/stage-main.json "select" list (that file's hash is in the study's FROZEN-PROTOCOL.json and is
# re-verified by ig_plan, which also re-derives these digests from it). Equal totals with a substituted condition,
# target or call therefore cannot pass.
STUDIES["V1.24"].update(
    calls_sha256="55b2fc0f01ee60f8855fd69324716844311aa2c1e613829ada895cac5dfa1e2b",
    targets_sha256="3a34e02d55eea0208cdf7bd40e4eb398c0aa5a1e8a85d41e8690dc4ee17b12b1")
STUDIES["V1.22"].update(
    calls_sha256="280383da4363dfc0eceab8e89efb444aa4e04af5a388aab3cc3477107ab9d194",
    targets_sha256="16bcd7ca10503cfdbc5b84d814604cfcd9218b12bca976b9365a81851a01df63")


def id_digest(ids):
    return hashlib.sha256("\n".join(sorted(ids)).encode()).hexdigest()


def membership_problems(target_ids, call_ids, expected):
    """Declared-membership checks beyond totals: allowed conditions, per-condition and per-act counts, every target
    scheduled, and exact pinned call/target ID digests."""
    out = []
    arms = collections.Counter(arm_of(c) for c in call_ids)
    for arm in sorted(set(arms) - set(expected["conditions"])):
        out.append(f"undeclared condition {arm}: {arms[arm]} scheduled calls")
    for arm, n in sorted(expected["conditions"].items()):
        if arms.get(arm, 0) != n:
            out.append(f"condition {arm}: {arms.get(arm, 0)} scheduled calls != declared {n}")
    acts = collections.Counter(t.split("|")[1] if t.count("|") >= 1 else None for t in target_ids)
    for act in ("arrival", "correction"):
        if acts.get(act, 0) != expected[f"{act}_targets"]:
            out.append(f"{act} targets {acts.get(act, 0)} != declared {expected[f'{act}_targets']}")
    unscheduled = set(target_ids) - {target_of(c) for c in call_ids}
    if unscheduled:
        out.append(f"{len(unscheduled)} public targets have no scheduled call")
    if id_digest(call_ids) != expected["calls_sha256"]:
        out.append("scheduled call IDs differ from the pinned declared membership")
    if id_digest(target_ids) != expected["targets_sha256"]:
        out.append("public target IDs differ from the pinned declared membership")
    return out

PUBLIC_KEYS = ("target", "prefix", "target_text", "registry", "registry_order")
RECORD_KEYS = ("call_id", "status", "complete", "attempts", "user_sha256", "raw")
FORBIDDEN_PARTS = ("hidden", "analysis")


class Incomplete(Exception):
    pass


def _guard_path(path):
    parts = Path(path).parts
    if any(p in FORBIDDEN_PARTS for p in parts[-4:]):
        raise PermissionError(f"decision stage may not open {path}")
    return path


def _read_jsonl(path, problems, label):
    rows = []
    try:
        with open(_guard_path(path), encoding="utf-8") as f:
            for i, line in enumerate(f, 1):
                if not line.strip():
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    problems.append(f"{label}: corrupt line {i}")
    except FileNotFoundError:
        problems.append(f"{label}: missing file {path}")
    return rows


def target_of(call_id):
    return call_id.rsplit("|", 1)[0]


def arm_of(call_id):
    return call_id.rsplit("|", 1)[1]


def load_public_inputs(hub, expected):
    """-> (targets {target: public-only row}, calls [(call_id, record-or-None)], problems). Never shrinks totals."""
    hub = Path(hub)
    problems = []
    pubs = {}
    for row in _read_jsonl(hub / "data" / "public" / "main-targets.jsonl", problems, "public targets"):
        tid = row.get("target")
        if tid in pubs:
            problems.append(f"duplicate target {tid}")
            continue
        missing = [k for k in PUBLIC_KEYS if k not in row]
        if missing:
            problems.append(f"target {tid}: missing public keys {missing}")
            continue
        pubs[tid] = {k: row[k] for k in PUBLIC_KEYS}
    schedule = {}
    for row in _read_jsonl(hub / "data" / "main-calls.jsonl", problems, "call schedule"):
        cid = row.get("call_id")
        if cid in schedule:
            problems.append(f"duplicate scheduled call {cid}")
            continue
        schedule[cid] = row.get("user_sha256")
    for cid in schedule:
        if target_of(cid) not in pubs:
            problems.append(f"scheduled call {cid} has no public target")
    recs, files = {}, 0
    calls_dir = hub / "stages" / "main" / "calls"
    for p in sorted(_guard_path(calls_dir).glob("*.json")) if calls_dir.exists() else []:
        files += 1
        try:
            r = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            problems.append(f"corrupt record file {p.name}")
            continue
        if not isinstance(r, dict) or not isinstance(r.get("call_id"), str):
            problems.append(f"corrupt record file {p.name}")
            continue
        cid = r["call_id"]
        if p.name != cid.replace("|", "__") + ".json":
            problems.append(f"record file name does not match call_id: {p.name}")
        if cid in recs:
            problems.append(f"duplicate record {cid}")
            continue
        recs[cid] = {k: r.get(k) for k in RECORD_KEYS}
    if not calls_dir.exists():
        problems.append(f"missing record directory {calls_dir}")
    for cid in sorted(set(recs) - set(schedule)):
        problems.append(f"extra record not in schedule {cid}")
    calls = []
    for cid in sorted(schedule):
        r = recs.get(cid)
        if r is None:
            problems.append(f"missing record {cid}")
        else:
            if r["status"] != "ok" or r["complete"] is not True or r["attempts"] != 1:
                problems.append(f"non-ok record {cid}: status={r['status']} complete={r['complete']} "
                                f"attempts={r['attempts']}")
            if r["user_sha256"] != schedule[cid]:
                problems.append(f"prompt hash mismatch {cid}")
        calls.append((cid, r))
    counts = {"scheduled_calls": len(schedule), "record_files": files, "records": len(recs), "targets": len(pubs)}
    if expected is not None:
        if len(schedule) != expected["calls"]:
            problems.append(f"scheduled calls {len(schedule)} != expected {expected['calls']}")
        if len(pubs) != expected["targets"]:
            problems.append(f"targets {len(pubs)} != expected {expected['targets']}")
        if files != expected["calls"]:
            problems.append(f"record files {files} != expected {expected['calls']}")
        problems.extend(membership_problems(list(pubs), list(schedule), expected))
    return pubs, calls, problems, counts
