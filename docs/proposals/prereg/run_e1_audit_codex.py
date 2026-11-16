#!/usr/bin/env python3
"""E1 cross-family audit (PREREGISTRATION_E1_E5.md, Section 9.1, item 2). Report-only diagnostic.

Re-judges a deterministic stratified 20% of the E1 confirmatory pairs with a second judge family (Codex CLI,
OpenAI family), in both orders, with the FROZEN pairwise-v1 system prompt, schema and payload renderer.

  run_e1_audit_codex.py --instrument .../judging/pairwise-v1 --units qwen3-8b=DIR --units mistral-7b=DIR \
      --out OUTDIR [--codex-bin codex] [--model gpt-6.1-sol] [--dry-run]

Pairs are built by run_e1_pairwise.build_pairs (same tasks, lock, hold-rule and hash checks); the sample is
analyze_e1_pairwise.audit_selection: per model x baseline x family, 5 of 8 tasks by hash rank and one seed per
task by hash rank, i.e. 90 of 432 pairs (20.8%), 180 calls. Output records use the frozen judge_pair format, so
analyze_e1_pairwise.py --audit reads them directly.

Transport: `codex exec --output-schema <frozen schema>` inside a bubblewrap jail (read-only root, empty home
except ~/.codex, a scratch working directory, read-only sandbox, ephemeral session, user config and rules
ignored, plugins/apps/browser/computer use disabled). Codex has no separate system-prompt channel, so the
frozen system prompt and the frozen payload are sent as one message, separated by a blank line; this is the
only transport difference from the Claude judge and is recorded in every raw call. A reply counts only if it
parses as JSON, validates against the frozen schema and the event stream shows no tool use.
"""
import argparse
import hashlib
import json
import shutil
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
import analyze_e1_pairwise as an  # noqa: E402
import run_e1_pairwise as drv  # noqa: E402

DEFAULT_MODEL, EFFORT, TIMEOUT, MAX_ATTEMPTS, WORKERS = "gpt-6.1-sol", "medium", 900, 3, 2
TOOL_TYPES = ("command_execution", "file_change", "mcp_tool_call", "web_search", "todo_list")
_lock = threading.Lock()


def now():
    return datetime.now(timezone.utc).isoformat()


def codex_call(a, schema_path, prompt):
    home = Path.home()
    work = Path(tempfile.mkdtemp(prefix="e1-audit-"))
    try:
        shutil.copy2(schema_path, work / "schema.json")
        jail = ["bwrap", "--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc", "--tmpfs", "/tmp",
                "--tmpfs", str(home), "--bind", str(home / ".codex"), str(home / ".codex"),
                "--bind", str(work), str(home / "w"), "--chdir", str(home / "w"), "--die-with-parent"]
        cmd = jail + [a.codex_bin, "exec", "--skip-git-repo-check", "--ephemeral", "--ignore-user-config",
                      "--ignore-rules", "--sandbox", "read-only", "-m", a.model,
                      "-c", f'model_reasoning_effort="{EFFORT}"',
                      "--disable", "plugins", "--disable", "apps", "--disable", "browser_use",
                      "--disable", "computer_use", "--json", "-C", str(home / "w"),
                      "--output-schema", str(home / "w/schema.json"), "-o", str(home / "w/last.txt"), "-"]
        proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=TIMEOUT)
        last = work / "last.txt"
        return {"cmd": cmd, "exit_code": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr[-4000:],
                "final_text": last.read_text() if last.exists() else ""}
    finally:
        shutil.rmtree(work, ignore_errors=True)


def judged(a, raw_dir, call_id, system, schema, schema_path, payload):
    final = raw_dir / f"{call_id}.json"
    if final.exists():
        rec = json.loads(final.read_text())
        if rec.get("valid"):
            return rec["result"]
    prompt = system + "\n\n" + payload
    rec = {}
    for attempt in range(1, MAX_ATTEMPTS + 1):
        rec = {"call_id": call_id, "attempt": attempt, "started": now(), "family": "codex", "model_requested": a.model,
               "effort": EFFORT, "transport_note": "system prompt and payload sent as one message (no system channel)",
               "system_sha256": hashlib.sha256(system.encode()).hexdigest(),
               "payload_sha256": hashlib.sha256(payload.encode()).hexdigest(), "valid": False, "result": None}
        try:
            info = codex_call(a, schema_path, prompt)
            rec.update(exit_code=info["exit_code"], stdout=info["stdout"], stderr=info["stderr"])
            events = [json.loads(x) for x in info["stdout"].splitlines() if x.strip().startswith("{")]
            tools = sum(1 for e in events if e.get("type") in ("item.started", "item.completed")
                        and (e.get("item") or {}).get("type") in TOOL_TYPES)
            rec["tool_events"] = tools
            out = json.loads(info["final_text"])
            import jsonschema
            jsonschema.validate(out, schema)
            if info["exit_code"] != 0:
                rec["error"] = f"exit {info['exit_code']}"
            elif tools:
                rec["error"] = "tool use"
            else:
                rec.update(valid=True, result=out)
        except subprocess.TimeoutExpired:
            rec["error"] = "timeout"
        except Exception as e:  # noqa: BLE001 - any parse/validation failure is recorded and retried
            rec["error"] = f"{type(e).__name__}: {e}"[:500]
        rec["finished"] = now()
        (raw_dir / f"{call_id}.attempt{attempt}.json").write_text(json.dumps(rec, indent=1))
        if rec["valid"]:
            break
    final.write_text(json.dumps(rec, indent=1))
    return rec["result"]


def judge_pair(a, mod, pair, raw_dir, ckpt, system, schema, schema_path):
    """Same record format and consistency coding as the frozen judge_pair, with the Codex transport."""
    out = {"pair_id": pair["pair_id"], "meta": pair["meta"], "c1": pair["c1"], "c2": pair["c2"], "orders": {},
           "judge_family": "codex", "judge_model": a.model}
    texts = {pair["c1"]: pair["text1"], pair["c2"]: pair["text2"]}
    for order, (x, y) in (("forward", (pair["c1"], pair["c2"])), ("reverse", (pair["c2"], pair["c1"]))):
        res = judged(a, raw_dir, f"{pair['pair_id']}.{order}", system, schema, schema_path,
                     mod.render(pair["task"], texts[x], texts[y]))
        out["orders"][order] = None if res is None else {
            "A": x, "B": y, "raw": {d: res[d] for d in mod.DIMS},
            "canonical": {d: mod.canon(res[d], x, y) for d in mod.DIMS}, "rationale": res["rationale"]}
    f, r = out["orders"]["forward"], out["orders"]["reverse"]
    out["complete"] = bool(f and r)
    if out["complete"]:
        out["consistency"] = {d: {"consistent": f["canonical"][d] == r["canonical"][d],
                                  "hard_flip": f["canonical"][d] != r["canonical"][d]
                                  and "TIE" not in (f["canonical"][d], r["canonical"][d]),
                                  "position_A_won_both": f["raw"][d] == "A" and r["raw"][d] == "A",
                                  "position_B_won_both": f["raw"][d] == "B" and r["raw"][d] == "B"}
                              for d in mod.DIMS}
    with _lock, open(ckpt, "a") as fh:
        fh.write(json.dumps(out, ensure_ascii=False) + "\n")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--instrument", required=True, type=Path)
    ap.add_argument("--tasks", default=HERE / "tasks_e1_24.json", type=Path)
    ap.add_argument("--lock", default=HERE / "steering_lock.json", type=Path)
    ap.add_argument("--units", action="append", required=True)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--codex-bin", default="codex")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    inst, out = a.instrument.resolve(), a.out.resolve()
    if out == inst or inst in out.parents:
        raise SystemExit("--out must be outside the frozen instrument directory")
    drv.check_registered(a.tasks, "tasks_e1_24.json")
    drv.check_registered(a.lock, "steering_lock.json")
    drv.check_registered(HERE / "analyze_e1_pairwise.py", "analyze_e1_pairwise.py")
    mod = drv.load_frozen(inst)
    tasks, lock = json.loads(a.tasks.read_text()), json.loads(a.lock.read_text())
    units = dict(x.split("=", 1) for x in a.units)
    pairs, missing, problems, hold = drv.build_pairs(mod, units, tasks, lock)
    sel = set(an.audit_selection(pairs))
    todo_all = [p for p in pairs if p["pair_id"] in sel]
    print(f"planned pairs {len(pairs)}; audit sample {len(todo_all)} ({2 * len(todo_all)} calls); "
          f"lock/task problems {len(problems)}; hold-rule gaps {len(hold)}")
    if a.dry_run:
        return
    if problems or hold:
        raise SystemExit("REFUSED: lock/task problems or incomplete generation (prospective hold rule)")

    system, schema_path = mod.PROMPT.read_text(), mod.SCHEMA
    schema = json.loads(schema_path.read_text())
    out.mkdir(parents=True, exist_ok=True)
    raw_dir, ckpt = out / "raw-audit", out / "audit_pairs.jsonl"
    raw_dir.mkdir(exist_ok=True)
    (out / "AUDIT-MANIFEST.json").write_text(json.dumps({
        "audit_script_sha256": drv.sha(__file__), "registered_sha256": drv.REGISTERED, "codex_model": a.model,
        "effort": EFFORT, "selection": sorted(sel)}, indent=1) + "\n")
    done = set()
    if ckpt.exists():
        done = {json.loads(l)["pair_id"] for l in ckpt.read_text().splitlines()
                if l.strip() and json.loads(l).get("complete")}
    todo = [p for p in todo_all if p["pair_id"] not in done]
    print(f"{len(done)} complete, {len(todo)} to judge")
    with ThreadPoolExecutor(WORKERS) as ex:
        for rec in ex.map(lambda p: judge_pair(a, mod, p, raw_dir, ckpt, system, schema, schema_path), todo):
            print(rec["pair_id"], "ok" if rec["complete"] else "INCOMPLETE", flush=True)


if __name__ == "__main__":
    main()
