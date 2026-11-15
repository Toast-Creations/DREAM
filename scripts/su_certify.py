"""EVT-suite fail-closed completion validator (Codex pre-freeze review F1, recheck R1-R4, R6). Host stdlib only.

One validator is used by the driver (stage integrity and final check), the stage checker, the analyzer and the
chain. It returns a list of problems; any problem makes the study INCOMPLETE and suppresses its reading. Problems
that come from the freeze carry the prefix FREEZE_PREFIX, so every caller can classify them as freeze faults.

Checks:
  - freeze: exact manifest schema; mandatory files present in design/config/data/phase0; every present file covered
    exactly (no selective maps); declared config contents (PANEL, ANALYSIS-PLAN, RESOURCE-GUARD, stage configs);
    actual source, driver, model-manifest (declared production path) and analysis-plan hashes; validation record;
  - terminal state: any driver failure/error/deadline/invalidation marker suppresses the reading permanently;
  - budget: DEADLINE.json present, 0 < deadline - start <= 8 h, start not before the freeze;
  - stages: exactly smoke and main; non-fake LOCK binding the committed config/calls/source; saved stage config
    identical to the frozen one; exactly one parseable start record binding the same hashes with planned == todo ==
    scheduled and a start time inside the budget; the full pinned LOAD recipe; END finished inside the budget and
    not before the start; no STOP; no logged failed attempts; attempts across all stages equal the declared total;
  - data: every call re-derived from public inputs with the declared builders (system text, user text, hashes,
    identity); allowed manifest exactly re-derived; target metadata equal to the canonical allocation;
  - records: transport schema (raw is a string, integer token counts within limits, finite timing, timestamps inside
    the budget and not before the stage start, model metadata identical to the stage LOAD record, identity
    consistent with the call);
  - terminal success: outside an active driver invocation, a COMPLETE study needs a valid success certificate whose
    whole schema checks out and which binds the freeze, the collected-record inventory and the analysis artifacts
    (ANALYSIS.json, scored.jsonl, REPORT.md), with a reading equal to the verified analysis.

These are local evidence-integrity checks, not an authenticated security boundary: someone able to rewrite both the
outputs and every commitment could defeat them.
"""
import hashlib
import json
import math
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from _bootstrap import ROOT
from dream_core.isotime import fromisoformat  # Python 3.10: accepts -0500 offsets
from dream_core.ledger import release_source_hash
from tempo import evsuite as S, kidconfgen as KG
from tempo.kidconfdone import plan_sha256
from ev_prepare import MODEL

NY = ZoneInfo("America/New_York")
STUDY_CEILING_S = 28800
FREEZE_PREFIX = "FREEZE: "
MANIFEST_PATH = MODEL["manifest"]   # production; CPU fixtures inject a test manifest explicitly
SECTIONS = ("design", "config", "data", "phase0")
UNFROZEN = ("DEADLINE.json", "FROZEN-PROTOCOL.json")
MANDATORY = {
    "design": {"PROTOCOL.md", "SUITE-PROTOCOL.md", "AUTHORIZATION.md"},
    "config": {"PANEL.json", "ANALYSIS-PLAN.json", "RESOURCE-GUARD.json", "COORDINATION.json", "stage-smoke.json",
               "stage-main.json"},
    "data": {"ALLOCATION.jsonl", "ALLOWED-CALLS.jsonl", "COMMITMENT.json", "COMMITMENT-main.json",
             "COMMITMENT-smoke.json", "main-calls.jsonl", "smoke-calls.jsonl", "public/main-targets.jsonl",
             "public/smoke-targets.jsonl", "hidden/main-cases.jsonl", "hidden/smoke-cases.jsonl",
             "main-construction-rejections.jsonl", "smoke-construction-rejections.jsonl"},
    "phase0": {"VALIDATION.json", "FULL-TESTS.json", "TOKENS.json", "HISTORICAL.json"},
}
TERMINAL_FAILURE_MARKERS = ("DRIVER-FAILURE.json", "runtime/DRIVER-ERROR.json", "runtime/DEADLINE-EXCEEDED.json",
                            "runtime/INVALIDATED.json")
FROZEN_KEYS = {"study", "suite", "key", "status", "frozen_at", "source_dir", "source_sha256", "analysis_plan_sha256",
               "analysis_plan", "driver_sha256", "model_manifest_path", "model_manifest_sha256", *SECTIONS}
SUCCESS_KEYS = {"finished", "at", "study", "key", "reading", "frozen_protocol_sha256", "inventory_sha256",
                "analysis_sha256", "scored_sha256", "report_sha256", "certifies"}
PINNED_REVISION = "9216db5781bf21249d130ec9da846c4624c16137"
ANALYSIS_FILES = {"analysis_sha256": "analysis/dev/ANALYSIS.json", "scored_sha256": "analysis/dev/scored.jsonl",
                  "report_sha256": "REPORT.md"}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def text_sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def epoch(stamp):
    """Parse an ISO time; naive stamps (the worker's) are America/New_York local time."""
    t = fromisoformat(stamp)
    if t.tzinfo is None:
        t = t.replace(tzinfo=NY)
    return t.timestamp()


def _jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def is_freeze_fault(problems):
    return any(p.startswith(FREEZE_PREFIX) for p in problems)


def inventory(hub):
    """Hash over every collected file (stages/), sorted by relative path."""
    hub = Path(hub)
    rows = sorted((str(p.relative_to(hub)), sha(p)) for p in (hub / "stages").rglob("*") if p.is_file())
    return text_sha(json.dumps(rows))


def _section_files(hub, name):
    d = Path(hub) / name
    return {str(p.relative_to(d)) for p in d.rglob("*") if p.is_file() and p.name not in UNFROZEN}


def check_freeze(hub, problems):
    """-> (frozen dict or {}, config or None). Every problem added here is a freeze fault."""
    from su_analyze import PLANS
    from su_guard import policy
    from su_prepare import validate_stage_configs
    hub = Path(hub)
    found = []
    try:
        cfg = S.validate_config(json.loads((hub / "config/PANEL.json").read_text()))
    except (OSError, ValueError, TypeError) as e:
        problems.append(FREEZE_PREFIX + f"PANEL invalid: {e!r}"[:300])
        return {}, None
    try:
        frozen = json.loads((hub / "config/FROZEN-PROTOCOL.json").read_text())
    except (OSError, ValueError) as e:
        problems.append(FREEZE_PREFIX + f"freeze unreadable: {e!r}"[:300])
        return {}, cfg
    if not isinstance(frozen, dict) or set(frozen) != FROZEN_KEYS:
        problems.append(FREEZE_PREFIX + "freeze manifest schema differs from the declared schema")
        return {}, cfg
    key = cfg["key"]
    try:
        if frozen["study"] != cfg["study"] or frozen["key"] != key or frozen["suite"] != S.SUITE:
            found.append("freeze names a different study")
        if frozen["source_sha256"] != release_source_hash(ROOT):
            found.append("source differs from freeze")
        if json.dumps(frozen["analysis_plan"], sort_keys=True) != json.dumps(PLANS[key], sort_keys=True) or \
                frozen["analysis_plan_sha256"] != plan_sha256(PLANS[key]):
            found.append("analysis plan differs from the declared plan")
        if json.loads((hub / "config/ANALYSIS-PLAN.json").read_text()) != PLANS[key]:
            found.append("config/ANALYSIS-PLAN.json differs from the declared plan")
        if json.loads((hub / "config/RESOURCE-GUARD.json").read_text()) != policy(key):
            found.append("config/RESOURCE-GUARD.json differs from the declared policy")
        validate_stage_configs(hub)
        if sha(hub / "run_su.sh") != frozen["driver_sha256"]:
            found.append("driver differs from freeze")
        if frozen["model_manifest_path"] != str(Path(MANIFEST_PATH).resolve()) or \
                sha(frozen["model_manifest_path"]) != frozen["model_manifest_sha256"]:
            found.append("model manifest path/hash differs from the declared manifest")
        validation = json.loads((hub / "phase0/VALIDATION.json").read_text())
        if validation.get("all_pass") is not True or validation.get("source_sha256") != frozen["source_sha256"]:
            found.append("phase0 validation did not pass on the frozen source")
        from su_phase0 import validate as validate_phase0   # V1.29.0, Codex pre-freeze F1/F2 (study D only)
        found.extend("phase0: " + p for p in validate_phase0(hub, cfg, frozen["source_sha256"]))
        epoch(frozen["frozen_at"])
    except Exception as e:  # any failure validating frozen inputs is a freeze fault (O3)
        found.append(f"freeze inputs unreadable or invalid: {e!r}"[:300])
    for name in SECTIONS:
        mapping = frozen.get(name)
        if not isinstance(mapping, dict) or not mapping:
            found.append(f"frozen {name} map missing or empty")
            continue
        present = _section_files(hub, name)
        if not MANDATORY[name] <= present:
            found.append(f"mandatory {name} files missing: {sorted(MANDATORY[name] - present)[:4]}")
        if set(mapping) != present:
            found.append(f"frozen {name} map does not cover exactly the present files "
                         f"(unlisted {sorted(present - set(mapping))[:3]}, missing {sorted(set(mapping) - present)[:3]})")
        for rel, digest in mapping.items():
            p = hub / name / rel
            if not p.is_file() or sha(p) != digest:
                found.append(f"frozen file changed or missing: {name}/{rel}")
    problems.extend(FREEZE_PREFIX + p for p in found)
    return frozen, cfg


def check_terminal(hub, problems):
    for rel in TERMINAL_FAILURE_MARKERS:
        if (Path(hub) / rel).exists():
            problems.append(f"terminal failure or invalidation recorded: {rel}")


def check_budget(hub, frozen, problems):
    """-> (start, deadline) epochs or (None, None)."""
    try:
        d = json.loads((Path(hub) / "config/DEADLINE.json").read_text())
        start, deadline = d["driver_start_epoch"], d["deadline_epoch"]
        if not all(type(x) in (int, float) and math.isfinite(x) for x in (start, deadline)):
            raise ValueError("non-numeric budget")
    except (OSError, ValueError, KeyError, TypeError) as e:
        problems.append(f"deadline missing or invalid: {e!r}"[:200])
        return None, None
    if not 0 < deadline - start <= STUDY_CEILING_S:
        problems.append("deadline is not within 8 hours after the driver start")
    try:
        if start < epoch(frozen["frozen_at"]) - 1:
            problems.append("driver started before the freeze")
    except (KeyError, TypeError, ValueError):
        problems.append("freeze time unreadable")
    return start, deadline


def _load_ok(load):
    q = load["load"]["quantization"]
    return (load.get("revision") == PINNED_REVISION and load.get("path") == MODEL["path"]
            and load.get("dtype") == "bfloat16" and load.get("quantization") == "nf4"
            and load.get("enable_thinking") is False and load.get("decoding") == "greedy"
            and load["load"].get("protocol") == "QLOAD-NF4-v1" and load["load"].get("devices") == ["cuda:0"]
            and load["load"].get("attn_implementation") == "sdpa"
            and q == {"load_in_4bit": True, "bnb_4bit_quant_type": "nf4", "bnb_4bit_use_double_quant": True,
                      "bnb_4bit_compute_dtype": "bfloat16", "non_quantized_dtype": "bfloat16"})


def check_stages(hub, cfg, start, deadline, problems):
    """-> {stage: (LOAD dict, stage start epoch)} for the record checks."""
    from su_guard import policy
    from tempo import refguard
    hub = Path(hub)
    source = release_source_hash(ROOT)
    present = {p.name for p in (hub / "stages").iterdir()} if (hub / "stages").is_dir() else set()
    if present != {"smoke", "main"}:
        problems.append(f"stages present {sorted(present)} differ from exactly smoke and main")
    out = {}
    for stage in ("smoke", "main"):
        sd = hub / "stages" / stage
        try:
            n = len(_jsonl(hub / f"data/{stage}-calls.jsonl"))
            commit = json.loads((hub / f"data/COMMITMENT-{stage}.json").read_text())
            want = {"config_sha256": sha(hub / f"config/stage-{stage}.json"), "calls_sha256": commit["calls_sha256"],
                    "source_sha256": source, "fake": False}
            lock = json.loads((sd / "LOCK.json").read_text())
            if lock != want or commit["calls_sha256"] != sha(hub / f"data/{stage}-calls.jsonl") or commit["calls"] != n:
                problems.append(f"{stage}: LOCK does not bind the committed config/calls/source or is fake")
            if (sd / "config.json").read_bytes() != (hub / f"config/stage-{stage}.json").read_bytes():
                problems.append(f"{stage}: saved stage config differs from the frozen config")
            starts = sorted(sd.glob("start-*.json"))
            if len(starts) != 1:
                raise ValueError(f"{len(starts)} start records (exactly one required)")
            st = json.loads(starts[0].read_text())
            st_epoch = epoch(st["started"])
            if {k: st.get(k) for k in want} != want or st.get("planned") != n or st.get("todo") != n:
                problems.append(f"{stage}: start record does not bind the committed hashes and counts")
            load = json.loads((sd / "LOAD.json").read_text())
            if not _load_ok(load):
                problems.append(f"{stage}: load recipe differs from QLOAD-NF4-v1 greedy bf16 on the pinned model")
            end = json.loads((sd / "END.json").read_text())
            if end.get("finished") is not True:
                problems.append(f"{stage}: END not finished")
            end_epoch = epoch(end["at"])
            if start is None or not (start - 1 <= st_epoch <= end_epoch <= deadline):
                problems.append(f"{stage}: start/END times outside the driver budget or out of order")
            out[stage] = (load, st_epoch, end_epoch)
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
            problems.append(f"{stage}: stage provenance missing or invalid: {e!r}"[:300])
        if (sd / "STOP.json").exists():
            problems.append(f"{stage}: STOP present")
        att = sd / "attempts.jsonl"
        if att.exists() and att.read_text().strip():
            problems.append(f"{stage}: logged failed attempts")
    if "smoke" in out and "main" in out and not out["smoke"][2] <= out["main"][1] + 1:
        problems.append("main stage started before the smoke stage ended")
    total = policy(cfg["key"])["total_attempts"]
    used = refguard.used_attempts(hub)
    if used != total:
        problems.append(f"attempts across all stages {used} differ from the declared {total}")
    return out


def check_data_and_records(hub, cfg, start, deadline, stage_info, problems):
    hub = Path(hub)
    allowed = _jsonl(hub / "data/ALLOWED-CALLS.jsonl")
    derived = []
    for stage in ("main", "smoke"):
        allocation = S.plan(cfg, smoke=(stage == "smoke"))
        targets = {m["target"]: m for m in S.expected_targets(allocation, cfg)}
        calls = _jsonl(hub / f"data/{stage}-calls.jsonl")
        public = {r["target"]: r for r in _jsonl(hub / f"data/public/{stage}-targets.jsonl")}
        if set(public) != set(targets) or json.loads((hub / "data/ALLOCATION.jsonl").read_text().splitlines()[0]) \
                != S.plan(cfg)[0]:
            problems.append(f"{stage}: public targets or allocation differ from the canonical allocation")
            continue
        for t, meta in targets.items():
            if any(public[t].get(k) != v for k, v in meta.items()):
                problems.append(f"{stage}: target metadata differs from the allocation: {t}")
                break
        prompts = {}
        bad = []
        for c in calls:
            tid = c.get("target")
            if tid not in public:
                bad.append(c.get("call_id"))
                continue
            if tid not in prompts:
                prompts[tid] = S.prompts_from_public(public[tid], cfg)[0]
            arm = c.get("arm")
            if arm not in prompts[tid]:
                bad.append(c.get("call_id"))
                continue
            want = KG.call(f"{tid}|{arm}", arm, public[tid]["history"], prompts[tid][arm], 256)
            if any(c.get(k) != v for k, v in want.items()) or c.get("system_sha256") != text_sha(want["system"]):
                bad.append(c.get("call_id"))
        if bad:
            problems.append(f"{stage}: {len(bad)} calls not re-derivable from public inputs: {bad[:3]}")
        derived.extend({k: c.get(k) for k in ("set", "call_id", "target", "stem", "act", "direction", "history",
                                               "arm", "system_sha256", "user_sha256", "max_new_tokens")}
                       for c in calls)
        if stage in stage_info:
            _records(hub, stage, {c["call_id"]: c for c in calls}, stage_info[stage], deadline, problems)
    if allowed != derived:
        problems.append("ALLOWED-CALLS differs from the manifest re-derived from the committed calls")


def _records(hub, stage, calls, info, deadline, problems):
    load, st_epoch, end_epoch = info
    bad = []
    for p in sorted((Path(hub) / "stages" / stage / "calls").glob("*.json")):
        try:
            r = json.loads(p.read_text())
            c = calls[r["call_id"]]
            ok = (isinstance(r.get("raw"), str)
                  and type(r.get("input_tokens")) is int and 0 < r["input_tokens"] <= 2048
                  and type(r.get("output_tokens")) is int and 0 <= r["output_tokens"] <= c["max_new_tokens"]
                  and type(r.get("seconds")) in (int, float) and math.isfinite(r["seconds"]) and r["seconds"] >= 0
                  and r.get("user_sha256") == c["user_sha256"] and r.get("arm") == c["arm"]
                  and r.get("max_new_tokens") == c["max_new_tokens"]
                  and p.name == r["call_id"].replace("|", "__") + ".json"
                  and r.get("model") == load
                  and r.get("status") == "ok" and r.get("complete") is True and r.get("attempts") == 1
                  and r.get("stop") in ("eos", "length")
                  and st_epoch - 1 <= epoch(r["finished_at"]) <= min(end_epoch + 1, deadline))
            if not ok:
                bad.append(p.name)
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            bad.append(p.name)
    if bad:
        problems.append(f"{stage}: {len(bad)} records fail the transport/budget schema: {bad[:3]}")


def check_success(hub, cfg, start, deadline, problems):
    """Outside an active driver: a COMPLETE study needs a valid, fully bound success certificate."""
    from su_analyze import PLANS
    hub = Path(hub)
    path = hub / "DRIVER-SUCCESS.json"
    if not path.exists():
        problems.append("no terminal success certificate")
        return
    try:
        s = json.loads(path.read_text())
        if not isinstance(s, dict) or set(s) != SUCCESS_KEYS:
            problems.append("success certificate schema differs from the declared schema")
            return
        if s["finished"] is not True or s["study"] != cfg["study"] or s["key"] != cfg["key"] or \
                s["reading"] not in PLANS[cfg["key"]]["statuses"]:
            problems.append("success certificate fields are not a valid completion of this study")
        main_end = epoch(json.loads((hub / "stages/main/END.json").read_text())["at"])
        if start is None or not main_end - 1 <= epoch(s["at"]) <= deadline:
            problems.append("success certificate time outside the driver budget or before the final END")
        if s["frozen_protocol_sha256"] != sha(hub / "config/FROZEN-PROTOCOL.json"):
            problems.append("success certificate does not bind the current freeze")
        if s["inventory_sha256"] != inventory(hub):
            problems.append("collected records differ from the inventory the success certificate binds")
        for field, rel in ANALYSIS_FILES.items():
            if not (hub / rel).is_file() or s[field] != sha(hub / rel):
                problems.append(f"success certificate does not bind the current {rel}")
        analysis = json.loads((hub / "analysis/dev/ANALYSIS.json").read_text())
        if analysis.get("status") != "COMPLETE" or analysis.get("reading", {}).get("status") != s["reading"] or \
                analysis.get("evidence_inventory_sha256") != s["inventory_sha256"]:
            problems.append("success certificate reading/inventory disagrees with the saved analysis")
    except (OSError, ValueError, KeyError, TypeError) as e:
        problems.append(f"success certificate or analysis unreadable: {e!r}"[:200])


def certify(hub, *, during_driver=False):
    """-> list of problems (empty when the study's evidence is complete and consistent)."""
    problems = []
    try:
        frozen, cfg = check_freeze(hub, problems)
        check_terminal(hub, problems)
        if cfg is None or not frozen:
            return problems
        start, deadline = check_budget(hub, frozen, problems)
        info = check_stages(hub, cfg, start, deadline, problems)
        check_data_and_records(hub, cfg, start, deadline, info, problems)
        if not during_driver:
            check_success(hub, cfg, start, deadline, problems)
    except Exception as e:  # fail closed on anything unexpected
        problems.append(f"evidence unreadable or invalid: {e!r}"[:300])
    return problems
