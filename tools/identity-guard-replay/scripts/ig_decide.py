"""Decision stage (public inputs only). Writes DECISIONS.jsonl + SEAL.json for one study.

Usage: PYTHONDONTWRITEBYTECODE=1 python -B scripts/ig_decide.py --study V1.24 --out DIR [--hub HUB]

The CLI always enforces the expected totals and declared membership (guard/studies.py). Skipping them is possible only
through run(..., use_expected=False) in isolated fixture tests; it is refused for the real study hub, and the seal
records membership_checked so the production evaluator refuses an unchecked seal.

It opens only the public target file, the call schedule and the saved call records (see guard/studies.py).
It never opens hidden cases, scored analyses, saved identity ledgers or failure lists. Any missing, duplicate,
extra, corrupt, non-ok or prompt-mismatched input -> INCOMPLETE: no SEAL is written and the exit code is 2.

Existing output for the same study (DECISIONS-, SEAL- or DECISION-STATUS-<study>) is never overwritten: the run is
REFUSED (exit 3) and the historic files are left byte-for-byte untouched. Files are created exclusively, so a
concurrent writer also causes a refusal instead of an overwrite.
"""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
from guard import pins  # noqa: E402

pins.activate()
from guard import decide as D, studies as ST  # noqa: E402


def source_hash():
    files = sorted(p for p in HERE.rglob("*.py") if "__pycache__" not in p.parts)
    h = hashlib.sha256()
    for p in files:
        h.update(str(p.relative_to(HERE)).encode() + b"\0" + p.read_bytes() + b"\0")
    return h.hexdigest()


def output_names(study):
    return (f"DECISIONS-{study}.jsonl", f"SEAL-{study}.json", f"DECISION-STATUS-{study}.json")


def _create(path, data):
    """Exclusive create: never replaces an existing ledger, seal or status file."""
    with open(path, "xb") as f:
        f.write(data if isinstance(data, bytes) else data.encode("utf-8"))


def run(study, hub, out, use_expected=True):
    t0 = time.time()
    spec = ST.STUDIES[study]
    hub = Path(hub or spec["hub"])
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    if not use_expected and hub.resolve() == Path(spec["hub"]).resolve():
        # Unchecked membership is for isolated fixture hubs only; a real study hub always gets the full checks.
        return {"study": study, "hub": str(hub), "rule": D.RULE, "status": "REFUSED",
                "problems": ["membership checks may only be skipped for isolated fixture hubs, not the study hub"]}
    existing = [n for n in output_names(study) if (out / n).exists() or (out / n).is_symlink()]
    if existing:
        return {"study": study, "hub": str(hub), "rule": D.RULE, "status": "REFUSED",
                "problems": [f"refusing to overwrite existing decision output {out / n}" for n in existing]}
    pubs, calls, problems, counts = ST.load_public_inputs(hub, spec if use_expected else None)
    status = {"study": study, "hub": str(hub), "rule": D.RULE, "counts": counts, "problems": problems}
    if problems:
        status["status"] = "INCOMPLETE"
        _create(out / f"DECISION-STATUS-{study}.json", json.dumps(status, indent=1) + "\n")
        return status
    lines = []
    for cid, rec in calls:
        pub = pubs[ST.target_of(cid)]
        raw = rec["raw"] if isinstance(rec["raw"], str) else None   # malformed content stays in the denominator
        d = D.decide(pub["prefix"], pub["target_text"], pub["registry"], pub["registry_order"], raw)
        lines.append(json.dumps({"call_id": cid, "target": pub["target"], "raw_is_str": isinstance(rec["raw"], str),
                                 "decision": d}, sort_keys=True, ensure_ascii=False))
    body = ("\n".join(lines) + "\n").encode("utf-8")
    dec = out / f"DECISIONS-{study}.jsonl"
    _create(dec, body)
    seal = {"study": study, "rule": D.RULE, "status": "SEALED", "decisions_file": dec.name,
            "decisions_sha256": hashlib.sha256(body).hexdigest(), "n_decisions": len(lines), "counts": counts,
            "dispositions": {}, "utility_source_sha256": source_hash(),
            "membership_checked": bool(use_expected),
            "dependency_sha256": pins.dependency_hashes(),
            "inputs_opened": ["data/public/main-targets.jsonl", "data/main-calls.jsonl", "stages/main/calls/*.json"],
            "seconds": round(time.time() - t0, 2)}
    for line in lines:
        k = json.loads(line)["decision"]["disposition"]
        seal["dispositions"][k] = seal["dispositions"].get(k, 0) + 1
    _create(out / f"SEAL-{study}.json", json.dumps(seal, indent=1, sort_keys=True) + "\n")
    status.update(status="SEALED", decisions_sha256=seal["decisions_sha256"], n_decisions=len(lines))
    _create(out / f"DECISION-STATUS-{study}.json", json.dumps(status, indent=1) + "\n")
    return status


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--study", required=True, choices=sorted(ST.STUDIES))
    ap.add_argument("--hub")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    st = run(a.study, a.hub, a.out)   # the CLI always enforces expected totals and declared membership
    print(json.dumps({k: st.get(k) for k in ("study", "status", "n_decisions", "decisions_sha256")}))
    if st["status"] != "SEALED":
        for p in st["problems"][:20]:
            print("  problem:", p)
        sys.exit(3 if st["status"] == "REFUSED" else 2)


if __name__ == "__main__":
    main()
