#!/usr/bin/env python3
"""E1 lineage ratings (PREREGISTRATION_E1_E5.md, Section 6.2). Secondary, descriptive.

Rates every delivered FINAL member of every E1 chain that enters a pair (all four arms) with the frozen
scope-v5c lineage prompt and schema, the instrument whose lineage gate passed 8/8 (scope-v5c as a whole FAILED
qualification; see Section 6.2). One call per final member, as in scope-v5c: the payload is the chain's
original ledger, the earlier final members of the same chain, and the member being rated, in the scope-v5c
lineage_payload format (copied verbatim below). No arm, model or condition label is in the payload.

  run_e1_lineage.py --scope-v5c .../judging/scope-v5c --instrument .../judging/pairwise-v1 \
      --units qwen3-8b=DIR --units mistral-7b=DIR --out OUTDIR [--dry-run]

Before any call it verifies (1) the pinned SHA-256 of the scope-v5c lineage prompt and schema, (2) that both
still match scope-v5c's PACKAGE-SHA256SUMS and FREEZE-MANIFEST.txt, and (3) the E1 task, lock, hold-rule and
hash checks of run_e1_pairwise.build_pairs. It reads scope-v5c only; all output goes under --out.
Output: OUTDIR/lineage_rows.jsonl, one row per final slot ({model, unit_id, member, lineage_category, ...};
lineage_category is null for a missing member or a failed call), read by analyze_e1_pairwise.py --lineage.
"""
import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_e1_pairwise as drv  # noqa: E402

PINNED = {"package/prompts/lineage_system_prompt.txt": "0d8218ecf2ace42abcf3e0216ba9c6829c58dc55bf0897e1c537de24c0e64730",
          "package/schemas/lineage_schema.json": "2009d7a7875888c2aa2b71ee9597a57f52f4fdead670192a1e9868150e8afbf6"}
FREEZE_MANIFEST_SHA256 = "e0cd972de07827e99a906b2c944ce8f1bbcf3fb993d0d001e85ed1d23941aeea"
MODEL, EFFORT, TIMEOUT, MAX_ATTEMPTS, WORKERS = "claude-opus-5-5", "medium", 900, 2, 4   # as scope-v5c
_lock = threading.Lock()


def now():
    return datetime.now(timezone.utc).isoformat()


def verify_v5c(root):
    for rel, digest in PINNED.items():
        got = drv.sha(root / rel)
        if got != digest:
            raise SystemExit(f"scope-v5c {rel}: sha256 {got} != pinned {digest}")
    if drv.sha(root / "FREEZE-MANIFEST.txt") != FREEZE_MANIFEST_SHA256:
        raise SystemExit("scope-v5c FREEZE-MANIFEST.txt changed")
    sums = {rel: d for d, rel in (l.split(maxsplit=1) for l in (root / "PACKAGE-SHA256SUMS").read_text().splitlines())}
    for rel, digest in PINNED.items():
        key = next((k for k in sums if k.lstrip("./") == rel.removeprefix("package/")), None)
        if key is None or sums[key] != digest:
            raise SystemExit(f"scope-v5c PACKAGE-SHA256SUMS does not list {rel} with the pinned hash")
    return (root / "package/prompts/lineage_system_prompt.txt").read_text(encoding="utf-8"), \
        json.loads((root / "package/schemas/lineage_schema.json").read_text(encoding="utf-8"))


def lineage_payload(item):  # verbatim from scope-v5c run_scope_v5c.py
    prior_txt = "\n".join(item["prior_final_slots"]) if item["prior_final_slots"] else "None"
    return (f"<initial_ledger>\n{item['initial_ledger']}\n</initial_ledger>\n\n"
            f"<prior_final_slots>\n{prior_txt}\n</prior_final_slots>\n\n"
            f"<final_member>\n{item['final_member']}\n</final_member>")


def call(raw_dir, call_id, system, schema, payload):
    """scope-v5c transport: claude -p --json-schema, reply in structured_output, model must be reported."""
    import jsonschema
    final = raw_dir / f"{call_id}.json"
    if final.exists():
        rec = json.loads(final.read_text())
        if rec.get("valid"):
            return rec["result"]
    schema_txt = json.dumps(schema)
    rec = {}
    for attempt in range(1, MAX_ATTEMPTS + 1):
        cmd = ["claude", "-p", "--model", MODEL, "--effort", EFFORT, "--tools", "", "--safe-mode",
               "--strict-mcp-config", "--no-session-persistence", "--output-format", "json",
               "--system-prompt", system, "--json-schema", schema_txt]
        rec = {"call_id": call_id, "attempt": attempt, "started": now(), "payload": payload,
               "system_sha256": hashlib.sha256(system.encode()).hexdigest(), "model_requested": MODEL,
               "effort": EFFORT, "valid": False, "result": None}
        with tempfile.TemporaryDirectory() as work:
            try:
                proc = subprocess.run(cmd, input=payload, capture_output=True, text=True, cwd=work, timeout=TIMEOUT)
                rec.update(exit_code=proc.returncode, stdout=proc.stdout, stderr=proc.stderr[-4000:])
            except subprocess.TimeoutExpired:
                rec.update(exit_code=None, error="timeout")
        rec["finished"] = now()
        try:
            data = json.loads(rec.get("stdout") or "")
            rec["model_reported"] = sorted(data.get("modelUsage") or {})
            out = data.get("structured_output")
            if data.get("is_error"):
                rec["error"] = "is_error"
            elif rec["model_reported"] != [MODEL]:
                rec["error"] = f"model_reported={rec['model_reported']}"
            elif out is None:
                rec["error"] = "no structured_output"
            else:
                jsonschema.validate(out, schema)
                rec.update(valid=True, result=out)
        except (json.JSONDecodeError, TypeError) as e:
            rec["error"] = f"unparseable stdout: {e}"
        except jsonschema.ValidationError as e:
            rec["error"] = f"schema: {e.message}"
        (raw_dir / f"{call_id}.attempt{attempt}.json").write_text(json.dumps(rec, indent=1))
        if rec["valid"]:
            break
    final.write_text(json.dumps(rec, indent=1))
    return rec["result"]


def jobs_for(model, u):
    """One job per final slot. Missing members become rows with no call."""
    finals = sorted((e for e in u["extraction"] if e["stage"] == "final"), key=lambda e: e["slot"])
    prior, jobs = [], []
    for e in finals:
        base = {"model": model, "unit_id": u["unit_id"], "member": e["slot"], "label": e["label"]}
        if not (e.get("delivered") and e.get("extraction_status") == "complete"):
            jobs.append({**base, "status": "missing", "payload": None}); continue
        payload = lineage_payload({"initial_ledger": u["original_ledger"], "prior_final_slots": list(prior),
                                   "final_member": e["verbatim_excerpt"]})
        jobs.append({**base, "status": "to_rate", "payload": payload})
        prior.append(e["verbatim_excerpt"])
    return jobs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scope-v5c", required=True, type=Path)
    ap.add_argument("--instrument", required=True, type=Path, help="pairwise-v1 dir (for the shared E1 checks)")
    ap.add_argument("--tasks", default=HERE / "tasks_e1_24.json", type=Path)
    ap.add_argument("--lock", default=HERE / "steering_lock.json", type=Path)
    ap.add_argument("--units", action="append", required=True)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    v5c, out = a.scope_v5c.resolve(), a.out.resolve()
    if out == v5c or v5c in out.parents or out == a.instrument.resolve() or a.instrument.resolve() in out.parents:
        raise SystemExit("--out must be outside the frozen scope-v5c and pairwise-v1 directories")
    system, schema = verify_v5c(v5c)
    drv.check_registered(a.tasks, "tasks_e1_24.json")
    drv.check_registered(a.lock, "steering_lock.json")
    mod = drv.load_frozen(a.instrument.resolve())
    tasks, lock = json.loads(a.tasks.read_text()), json.loads(a.lock.read_text())
    units = dict(x.split("=", 1) for x in a.units)
    pairs, _, problems, hold = drv.build_pairs(mod, units, tasks, lock)
    in_pairs = {(p["meta"]["model"], uid) for p in pairs for uid in (p["meta"]["steer_id"], p["meta"]["baseline_id"])}
    jobs = []
    for model, d in units.items():
        for f in sorted(Path(d).glob("*.json")):
            u = json.loads(f.read_text())
            if (model, u["unit_id"]) in in_pairs:
                jobs += jobs_for(model, u)
    n_calls = sum(j["status"] == "to_rate" for j in jobs)
    print(f"units in pairs {len(in_pairs)}; final slots {len(jobs)}; calls {n_calls}; "
          f"lock/task problems {len(problems)}; hold-rule gaps {len(hold)}")
    if a.dry_run:
        return
    if problems or hold:
        raise SystemExit("REFUSED: lock/task problems or incomplete generation (prospective hold rule)")

    out.mkdir(parents=True, exist_ok=True)
    raw_dir, rows_path = out / "raw-lineage", out / "lineage_rows.jsonl"
    raw_dir.mkdir(exist_ok=True)
    (out / "LINEAGE-MANIFEST.json").write_text(json.dumps({
        "lineage_script_sha256": drv.sha(__file__), "pinned_v5c": PINNED, "registered_sha256": drv.REGISTERED,
        "model": MODEL, "effort": EFFORT, "calls_planned": n_calls}, indent=1) + "\n")

    def run(j):
        cid = f"{j['model']}.{j['unit_id']}.F{j['member']}"
        res = call(raw_dir, cid, system, schema, j["payload"]) if j["payload"] else None
        row = {k: j[k] for k in ("model", "unit_id", "member", "label")}
        row.update(call_id=cid if j["payload"] else None, status=j["status"] if res or not j["payload"] else "failed",
                   lineage_category=res["lineage_category"] if res else None,
                   survives_lineage_gate=res["survives_lineage_gate"] if res else None)
        if res:
            row["status"] = "rated"
        return row

    with ThreadPoolExecutor(WORKERS) as ex:
        rows = list(ex.map(run, jobs))
    with _lock:
        rows_path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    print(f"rows {len(rows)}: rated {sum(r['status'] == 'rated' for r in rows)}, "
          f"missing {sum(r['status'] == 'missing' for r in rows)}, failed {sum(r['status'] == 'failed' for r in rows)}")


if __name__ == "__main__":
    main()
