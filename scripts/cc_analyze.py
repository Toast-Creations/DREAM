"""CCONF-v1 fixed-time package comparison, integrity audit and result artifacts.

No model calls. Exactness is inherited unchanged. All required reference calls
are infrastructure requirements, but they never replace the primary comparator.
"""
import argparse
import collections
from datetime import datetime
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import statistics
from zoneinfo import ZoneInfo

from _bootstrap import ROOT
from dream_core.ledger import release_source_hash
from tempo import bounded_mean as BM, clarconfirm as CC, kidconfdone as KD
import clar_analyze as CA
import cc_guard
from kconf_analyze import PIN, recipe_ok

STUDY = "CCONF-v1"
NY = ZoneInfo("America/New_York")
BASELINE, CANDIDATE, REFERENCE = "SUB_ORIG", "KEEP_CLAR", "SUB_CLAR"
DEFAULT_PLAN = {
    "study": STUDY,
    "primary": {"baseline": BASELINE, "candidate": CANDIDATE, "arrival_stems": 224, "correction_stems": 160},
    "reference": {"arm": REFERENCE, "arrival_stems": 32, "correction_stems": 16},
    "expected": {"main_targets": 1088, "main_calls": 2304, "smoke_targets": 12, "smoke_calls": 36},
    "family_weights": {"F1": "1/4", "F2": "1/4", "F3": "1/2"},
    "reception_weights": {"immediate": "1/2", "delayed": "1/2"},
    "qualification": True, "rule_file": "RULE.json",
}


def strict_equal(actual, expected):
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return set(actual) == set(expected) and all(strict_equal(actual[k], v) for k, v in expected.items())
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(strict_equal(a, b) for a, b in zip(actual, expected))
    return actual == expected


def validate_plan(plan):
    if not strict_equal(plan, DEFAULT_PLAN):
        raise ValueError("ANALYSIS-PLAN must exactly equal the CCONF-v1 declared recipe")
    return plan


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path, problems, default=None):
    try:
        value = json.loads(Path(path).read_text())
        if not isinstance(value, dict):
            raise ValueError("expected a JSON object")
        return value
    except (OSError, ValueError, TypeError) as exc:
        problems.append(f"unreadable {Path(path).name}: {type(exc).__name__}")
        return default


def read_jsonl(path, problems):
    try:
        lines = Path(path).read_text().splitlines()
    except OSError:
        problems.append(f"missing {Path(path).name}")
        return []
    out = []
    for index, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError("not an object")
            out.append(value)
        except (ValueError, TypeError):
            problems.append(f"corrupt {Path(path).name} line {index}")
    return out


def index_unique(rows, key, problems, label):
    out = {}
    for row in rows:
        value = row.get(key)
        if not isinstance(value, str) or value in out:
            problems.append(f"{label}: missing/duplicate {key}: {value}")
            continue
        out[value] = row
    return out


def epoch(value):
    """The runner's naive timestamps explicitly mean New York, never host local TZ."""
    if not isinstance(value, str):
        raise ValueError("timestamp must be text")
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=NY)
    return dt.timestamp()


def load_records(hub, stage, problems):
    rows, n_files = [], 0
    for path in sorted((Path(hub) / "stages" / stage / "calls").glob("*.json")):
        n_files += 1
        row = read_json(path, problems)
        if not isinstance(row, dict):
            problems.append(f"{stage}: corrupt result {path.name}")
            continue
        rows.append(row)
    return index_unique(rows, "call_id", problems, stage+" results"), n_files


def audit_freeze(hub, problems):
    hub = Path(hub)
    frozen = read_json(hub / "config/FROZEN-PROTOCOL.json", problems, {})
    if not isinstance(frozen, dict):
        problems.append("invalid freeze object")
        return {}
    if frozen.get("study") != STUDY:
        problems.append("frozen study identifier differs from CCONF-v1")
    if frozen.get("source_sha256") != release_source_hash(ROOT):
        problems.append("current source differs from frozen source")
    rule_path = hub / "config/RULE.json"
    if not rule_path.is_file() or frozen.get("rule_sha256") != sha(rule_path):
        problems.append("frozen rule identity differs from actual RULE.json")
    for section in ("design", "config", "data", "phase0"):
        mapping = frozen.get(section)
        if not isinstance(mapping, dict) or not mapping:
            problems.append(f"missing frozen {section} file mapping")
            continue
        for rel, expected in mapping.items():
            path = hub / section / rel
            if not path.is_file() or sha(path) != expected:
                problems.append(f"frozen bytes differ: {section}/{rel}")
    for filename, field in (("run_cc.sh", "driver_sha256"),):
        path = hub / filename
        if not frozen.get(field) or not path.is_file() or sha(path) != frozen[field]:
            problems.append(f"frozen {filename} hash differs or is missing")
    manifest = frozen.get("model_manifest_path")
    if not isinstance(manifest, str) or not Path(manifest).is_file() or sha(manifest) != frozen.get("model_manifest_sha256"):
        problems.append("frozen model manifest hash differs or is missing")
    return frozen


def validate_membership(config, allocation, allowed_rows, datasets, problems):
    """Canonical, declarative sparse membership; never infer arms from responses."""
    canonical = {stage: CC.plan(config, smoke=(stage == "smoke")) for stage in ("main", "smoke")}
    if allocation != canonical["main"] + canonical["smoke"]:
        problems.append("ALLOCATION differs from canonical PANEL plan")
    allowed = index_unique(allowed_rows, "call_id", problems, "allowed manifest")
    all_expected = CC.allowed_call_ids(canonical["main"]) | CC.allowed_call_ids(canonical["smoke"])
    if set(allowed) != all_expected:
        problems.append("allowed-call manifest differs from canonical sparse membership")
    for stage in ("main", "smoke"):
        bundle = datasets[stage]
        expected = {p["target"]: p for p in CC.expected_targets(canonical[stage])}
        expected_calls = CC.allowed_call_ids(canonical[stage])
        pubs = index_unique(bundle["public_rows"], "target", problems, stage+" public")
        hidden = index_unique(bundle["hidden_rows"], "target", problems, stage+" hidden")
        calls = index_unique(bundle["call_rows"], "call_id", problems, stage+" calls")
        bundle.update(public=pubs, hidden=hidden, calls=calls, expected=expected, expected_calls=expected_calls)
        for label, mapping in (("public", pubs), ("hidden", hidden)):
            if set(mapping) != set(expected):
                problems.append(f"{stage}: {label} targets differ from canonical target membership")
            for target in set(mapping) & set(expected):
                if any(not strict_equal(mapping[target].get(key), value) for key, value in expected[target].items()):
                    problems.append(f"{stage}: {label} metadata differs: {target}")
        if set(calls) != expected_calls:
            problems.append(f"{stage}: schedule differs from canonical sparse membership")
        for cid, call in calls.items():
            target, _, arm = cid.rpartition("|")
            meta = expected.get(target)
            if meta is None or arm not in CC.allowed_arms(meta, meta["act"]):
                problems.append(f"{stage}: unallowed call role: {cid}")
                continue
            keys = ("set", "target", "stem", "act", "direction", "history")
            if call.get("arm") != arm or any(call.get(key) != meta[key] for key in keys):
                problems.append(f"{stage}: call metadata differs: {cid}")
            for text_key in ("system", "user"):
                text = call.get(text_key)
                expected_hash = hashlib.sha256(text.encode()).hexdigest() if isinstance(text, str) else None
                if expected_hash is None or call.get(text_key+"_sha256") != expected_hash:
                    problems.append(f"{stage}: actual {text_key} hash differs: {cid}")
            ledger = allowed.get(cid, {})
            for key in ("set", "call_id", "target", "stem", "act", "direction", "history", "arm",
                        "system_sha256", "user_sha256", "max_new_tokens"):
                if ledger.get(key) != call.get(key):
                    problems.append(f"{stage}: allowed-call hash/metadata differs: {cid}")
                    break
            if call.get("max_new_tokens") != 256:
                problems.append(f"{stage}: output cap differs: {cid}")
    return canonical


def record_usable(rec, call):
    return (isinstance(rec, dict) and rec.get("status") == "ok" and rec.get("complete") is True
            and rec.get("attempts") == 1 and rec.get("user_sha256") == call.get("user_sha256") and recipe_ok(rec)
            and rec.get("stop") in ("eos", "length")
            and type(rec.get("seconds")) in (int, float) and math.isfinite(rec["seconds"]) and rec["seconds"] >= 0)


def audit_stage(hub, stage, bundle, frozen, deadline, problems):
    hub = Path(hub)
    sd = hub / "stages" / stage
    cfg_path = hub / "config" / f"stage-{stage}.json"
    cfg = read_json(cfg_path, problems, {})
    calls = bundle["calls"]
    commitment = read_json(hub / "data" / f"COMMITMENT-{stage}.json", problems, {})
    call_path = hub / "data" / f"{stage}-calls.jsonl"
    actual_call_hash = sha(call_path) if call_path.is_file() else None
    if commitment.get("calls_sha256") != actual_call_hash or actual_call_hash is None:
        problems.append(f"{stage}: actual calls bytes differ from commitment")
    lock = read_json(sd / "LOCK.json", problems, {})
    expected_lock = {"config_sha256": sha(cfg_path) if cfg_path.is_file() else None,
                     "calls_sha256": actual_call_hash, "source_sha256": frozen.get("source_sha256"), "fake": False}
    if lock != expected_lock:
        problems.append(f"{stage}: LOCK hash mismatch or fake runner")
    required_config = {"set": stage, "order": "as_committed", "max_input_tokens": 2048, "retry_limit": 0,
                       "max_calls": len(bundle["expected_calls"]), "max_seconds": 43200}
    if any(not strict_equal(cfg.get(k), v) for k, v in required_config.items()):
        problems.append(f"{stage}: config recipe differs")
    if cfg.get("select") != [c.get("call_id") for c in bundle["call_rows"]]:
        problems.append(f"{stage}: config selection/order differs from schedule")
    model = cfg.get("model", {})
    for key, value in (("dtype", "bfloat16"), ("device", "cuda"), ("enable_thinking", False), ("quantization", "nf4")):
        if not strict_equal(model.get(key), value):
            problems.append(f"{stage}: configured model recipe differs: {key}")
    if not str(model.get("path", "")).endswith(PIN["revision"]):
        problems.append(f"{stage}: configured model revision differs")
    if not (sd / "config.json").is_file() or sha(sd / "config.json") != expected_lock["config_sha256"]:
        problems.append(f"{stage}: runner config copy missing or differs")
    start_files = sorted(sd.glob("start-*.json"))
    if len(start_files) != 1:
        problems.append(f"{stage}: expected exactly one start record (no automatic resume)")
    for path in start_files:
        start = read_json(path, problems, {})
        if (start.get("planned") != len(bundle["expected_calls"]) or start.get("todo") != len(bundle["expected_calls"])
                or any(start.get(k) != v for k, v in expected_lock.items())):
            problems.append(f"{stage}: start record shows resume, wrong membership, or hash mismatch")
        try:
            start_at = epoch(start.get("started"))
            if not deadline["driver_start_epoch"] <= start_at <= deadline["deadline_epoch"]:
                raise ValueError("start outside deadline")
        except (ValueError, TypeError, KeyError):
            problems.append(f"{stage}: start timestamp missing/invalid/outside deadline")
    end = read_json(sd / "END.json", problems, {})
    if end.get("finished") is not True or end.get("stop_reason") is not None or end.get("new_this_run") != len(bundle["expected_calls"]):
        problems.append(f"{stage}: END missing/incomplete or indicates resumed/stopped stage")
    if (sd / "STOP.json").exists():
        problems.append(f"{stage}: STOP present")
    try:
        if not deadline["driver_start_epoch"] <= epoch(end.get("at")) <= deadline["deadline_epoch"]:
            raise ValueError("late END")
    except (ValueError, TypeError, KeyError):
        problems.append(f"{stage}: END timestamp missing/invalid/outside deadline")
    recs, n_files = load_records(hub, stage, problems)
    bundle["records"] = recs
    if set(recs) != bundle["expected_calls"]:
        problems.append(f"{stage}: records differ from required calls ({len(bundle['expected_calls']-set(recs))} missing, "
                        f"{len(set(recs)-bundle['expected_calls'])} extra)")
    for cid, rec in recs.items():
        call = calls.get(cid)
        if call is None or not record_usable(rec, call):
            problems.append(f"{stage}: result status/complete/prompt/attempt/recipe mismatch: {cid}")
        try:
            if not deadline["driver_start_epoch"] <= epoch(rec.get("finished_at")) <= deadline["deadline_epoch"]:
                raise ValueError("late result")
        except (ValueError, TypeError, KeyError):
            problems.append(f"{stage}: undated/invalid/late result: {cid}")
        for key, cap in (("input_tokens", 2048), ("output_tokens", 256)):
            if type(rec.get(key)) is not int or not 0 <= rec[key] <= cap:
                problems.append(f"{stage}: invalid {key}: {cid}")
    failed = read_jsonl(sd / "attempts.jsonl", problems) if (sd / "attempts.jsonl").exists() else []
    if failed:
        problems.append(f"{stage}: failed attempts logged; retry limit is zero")
    return {"scheduled": len(bundle["expected_calls"]), "records": len(recs), "record_files": n_files,
            "failed_attempt_entries": len(failed), "end": end}


def audit_runtime_certificates(hub, datasets, deadline, problems):
    certificates = {}
    for stage, planned, used in (("smoke", 36, 0), ("main", 2304, 36)):
        cert = read_json(Path(hub) / f"runtime/GUARD-{stage}.json", problems, {})
        certificates[stage] = cert
        if (cert.get("ok") is not True or cert.get("problems") != [] or cert.get("stage") != stage
                or cert.get("planned") != planned or cert.get("used_attempts_conservative") != used):
            problems.append(f"{stage}: runtime guard certificate missing/failed/mismatched")
        try:
            elapsed, remaining = cert["elapsed_s"], cert["remaining_s"]
            if (not math.isfinite(elapsed) or not math.isfinite(remaining) or elapsed < 0
                    or remaining <= cc_guard.POLICY["analysis_reserve_s"] + cc_guard.POLICY["kill_grace_s"]
                    or not math.isclose(elapsed + remaining, 43200, rel_tol=0, abs_tol=.001)):
                raise ValueError("invalid runtime guard clock")
        except (ValueError, TypeError, KeyError):
            problems.append(f"{stage}: runtime guard elapsed/remaining clock invalid")
    smoke = read_json(Path(hub) / "runtime/SMOKE-CHECK.json", problems, {})
    if not strict_equal(smoke, {"pass": True, "scheduled": 36, "records": 36, "semantic_accuracy_used": False}):
        problems.append("structural smoke certificate missing/failed/mismatched")
    times = []
    for cid, rec in datasets["smoke"].get("records", {}).items():
        try:
            seconds = rec["seconds"]
            if not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or seconds <= 0:
                raise ValueError("invalid smoke timing")
            times.append(seconds)
            target = cid.rsplit("|", 1)[0]
            pub = datasets["smoke"]["public"][target]
            raw = rec.get("raw")
            claims = CA.FA.compile_reply(raw if isinstance(raw, str) else None, pub["registry"])[1]["claims"]
            if rec.get("stop") != "eos" or claims is None:
                problems.append(f"smoke: structural normalization or completion failed: {cid}")
        except (KeyError, TypeError, ValueError):
            problems.append(f"smoke: runtime structural/timing evidence unavailable: {cid}")
    main_guard = certificates["main"]
    try:
        if len(times) != 36:
            raise ValueError("36 smoke timings required")
        smoke_mean = statistics.mean(times)
        projected = main_guard["elapsed_s"] + smoke_mean * 2304 * cc_guard.POLICY["feasibility_slowdown"] \
            + cc_guard.POLICY["main_overhead_s"]
        if (not math.isclose(main_guard["smoke_mean_s"], smoke_mean, rel_tol=1e-12, abs_tol=1e-8)
                or not math.isclose(main_guard["projected_total_s"], projected, rel_tol=1e-12, abs_tol=1e-8)
                or projected > cc_guard.POLICY["planning_limit_s"]):
            raise ValueError("measured forecast differs or exceeds reserve")
    except (KeyError, ValueError, TypeError):
        problems.append("main: measured feasibility certificate missing/inconsistent/exceeds 10.2h reserve")
    return {"guards": certificates, "structural_smoke": smoke}


def integrity(hub):
    """Read-only production audit. Early missing stage files produce INCOMPLETE."""
    hub = Path(hub)
    problems = []
    if (hub / "runtime/DRIVER-ERROR.json").exists():
        problems.append("driver terminal failure record present")
    frozen = audit_freeze(hub, problems)
    plan = read_json(hub / "config/ANALYSIS-PLAN.json", problems, {})
    rule = read_json(hub / "config/RULE.json", problems, {})
    config = read_json(hub / "config/PANEL.json", problems, {})
    try:
        validate_plan(plan)
        BM.validate_rule_config(rule)
        CC.validate_config(config)
    except (ValueError, TypeError, KeyError) as exc:
        problems.append(f"invalid canonical configuration: {exc}")
    if frozen.get("analysis_plan_sha256") != KD.plan_sha256(plan):
        problems.append("analysis plan canonical hash differs from freeze")
    allocation = read_jsonl(hub / "data/ALLOCATION.jsonl", problems)
    allowed = read_jsonl(hub / "data/ALLOWED-CALLS.jsonl", problems)
    datasets = {stage: {
        "public_rows": read_jsonl(hub / "data/public" / f"{stage}-targets.jsonl", problems),
        "hidden_rows": read_jsonl(hub / "data/hidden" / f"{stage}-cases.jsonl", problems),
        "call_rows": read_jsonl(hub / "data" / f"{stage}-calls.jsonl", problems),
    } for stage in ("main", "smoke")}
    try:
        canonical = validate_membership(config, allocation, allowed, datasets, problems)
    except (ValueError, TypeError, KeyError) as exc:
        problems.append(f"membership cannot be validated: {exc}")
        canonical = {"main": [], "smoke": []}
        for bundle in datasets.values():
            for key, source, field in (("public", "public_rows", "target"), ("hidden", "hidden_rows", "target"),
                                       ("calls", "call_rows", "call_id")):
                bundle.setdefault(key, index_unique(bundle[source], field, problems, key))
            bundle.setdefault("expected", {})
            bundle.setdefault("expected_calls", set())
    guard = read_json(hub / "config/RESOURCE-GUARD.json", problems, {})
    deadline = read_json(hub / "config/DEADLINE.json", problems, {})
    if not strict_equal(guard, cc_guard.POLICY):
        problems.append("resource policy differs from the fixed CCONF attempt/time/reserve policy")
    try:
        if (deadline.get("timezone") != "America/New_York"
                or type(deadline["driver_start_epoch"]) not in (int, float)
                or type(deadline["deadline_epoch"]) not in (int, float)
                or deadline["deadline_epoch"] - deadline["driver_start_epoch"] != 43200
                or epoch(deadline["deadline_iso"]) != deadline["deadline_epoch"]
                or datetime.fromisoformat(deadline["deadline_iso"]).tzinfo is None):
            raise ValueError("invalid deadline")
    except (ValueError, TypeError, KeyError):
        problems.append("deadline epoch/ISO/timezone policy missing or inconsistent")
    stages = {}
    for stage, bundle in datasets.items():
        try:
            stages[stage] = audit_stage(hub, stage, bundle, frozen, deadline, problems)
        except (ValueError, TypeError, KeyError, OSError) as exc:
            problems.append(f"{stage}: stage audit cannot complete: {type(exc).__name__}: {exc}")
            bundle.setdefault("records", load_records(hub, stage, problems)[0])
            stages[stage] = {"scheduled": len(bundle["expected_calls"]), "records": len(bundle["records"])}
    certificates = audit_runtime_certificates(hub, datasets, deadline, problems)
    recorded = sum(stage.get("record_files", stage.get("records", 0)) for stage in stages.values())
    failed = sum(stage.get("failed_attempt_entries", 0) for stage in stages.values())
    if recorded + failed > 2340:
        problems.append("recorded attempt accounting exceeds ceiling")
    if not problems and recorded != 2340:
        problems.append("complete run must contain all 2340 no-retry attempts")
    info = {"complete": not problems, "status": "COMPLETE" if not problems else "INCOMPLETE",
            "problems": sorted(set(problems)), "stages": stages, "attempts_recorded": recorded,
            "failed_attempt_entries": failed, "attempt_ceiling": 2340,
            "interrupted_attempt_accounting_uncertain": bool(problems),
            "deadline": deadline, "source_sha256": frozen.get("source_sha256"),
            "analysis_plan_sha256": KD.plan_sha256(plan), "runtime_certificates": certificates}
    return info, datasets, canonical, plan


def scored_rows(bundle):
    rows = []
    # Use declared target metadata rather than whatever calls/results survive.
    for target, meta in sorted(bundle["expected"].items()):
        for arm in CC.allowed_arms(meta, meta["act"]):
            cid = target+"|"+arm
            call, pub, hid = bundle["calls"].get(cid), bundle["public"].get(target), bundle["hidden"].get(target)
            if call is None or pub is None or hid is None:
                row = {**meta, "call_id": cid, "arm": arm, "family": meta["family"][:2],
                       "exact": False, "incomplete": True, "seconds": None}
            else:
                rec = bundle["records"].get(cid)
                rec = dict(rec) if record_usable(rec, call) else None
                if rec is not None and not isinstance(rec.get("raw"), (str, type(None))):
                    rec["raw"] = None   # malformed semantic content stays in the denominator
                row = CA.score_one(rec, hid, pub, call)
                row.update({key: meta[key] for key in ("primary_arrival", "primary_correction",
                                                       "reference_arrival", "reference_correction", "block")})
            rows.append(row)
    return rows


def paired_summary(rows, positive, negative, metric="exact"):
    mapping = {(r["target"], r["arm"]): r for r in rows}
    targets = sorted({r["target"] for r in rows if r["arm"] == positive})
    counts, rescue_stems, break_stems, values = collections.Counter(), set(), set(), []
    for target in targets:
        a, b = mapping.get((target, positive)), mapping.get((target, negative))
        if a is None or b is None or a["incomplete"] or b["incomplete"]:
            raise ValueError("paired comparison has incomplete/missing cells")
        av, bv = bool(a.get(metric)), bool(b.get(metric))
        counts["both" if av and bv else "rescue" if av else "break" if bv else "neither"] += 1
        if av and not bv:
            rescue_stems.add(a["stem"])
        if bv and not av:
            break_stems.add(a["stem"])
        values.append(int(av)-int(bv))
    return {"targets_per_arm": len(targets), "paired_counts": dict(counts),
            "rescue_stems": len(rescue_stems), "break_stems": len(break_stems),
            "estimate_exact": str(Fraction(sum(values), len(values))) if values else None,
            "estimate": statistics.mean(values) if values else None}


def aggregate_stems(rows, allocation, act, positive=CANDIDATE, negative=BASELINE, reference=False):
    mapping = {(r["target"], r["arm"]): r for r in rows}
    ledger = []
    for meta in allocation:
        if not meta[("reference_" if reference else "primary_")+act]:
            continue
        cells = [(direction, history) for direction in (("na",) if act == "arrival" else CC.DIRECTIONS)
                 for history in CC.HISTORIES]
        differences, targets = [], []
        for direction, history in cells:
            target = f"{meta['stem']}|{act}|{direction}|{history}"
            a, b = mapping.get((target, positive)), mapping.get((target, negative))
            if a is None or b is None or a["incomplete"] or b["incomplete"]:
                raise ValueError(f"missing paired stem cells: {target}")
            targets.append(target)
            differences.append(int(bool(a["exact"]))-int(bool(b["exact"])))
        difference = Fraction(sum(differences), len(cells))
        ledger.append({"kind": "reference" if reference else "primary", "stem": meta["stem"], "act": act,
                       "family": meta["family"][:2], "reception": meta["reception"],
                       "positive": positive, "negative": negative, "targets": targets,
                       "target_differences": differences, "difference_exact": str(difference),
                       "difference": float(difference)})
    return ledger


def descriptive(rows):
    out = CA.describe(rows)
    for key in ("accepted", "compiled", "exact_extraction", "compilation_loss", "exact_end_to_end", "replay_ok",
                "rev_target_ok", "rev_from_ok", "rev_to_ok", "quote_valid", "empty_extraction", "rejected"):
        out[key] = sum(bool(r.get(key)) for r in rows)
    out["independent_stems"] = len({r["stem"] for r in rows})
    out["seconds_sum"] = sum(r.get("seconds") or 0 for r in rows)
    return out


def analyze(hub):
    info, datasets, canonical, plan = integrity(hub)
    rows = scored_rows(datasets["main"])
    result = {"study": STUDY, "status": info["status"], "integrity": {"status": info["status"]},
              "infrastructure": info, "analysis_plan": plan, "qualification": {"status": "NOT_EVALUATED"},
              "descriptives": {}, "claim_scope": "clarified KEEP package versus original SUB baseline on the declared generator/recipe"}
    for keys in (("act", "arm"), ("family", "act", "arm"), ("reception", "act", "arm"),
                 ("direction", "act", "arm"), ("family", "reception", "direction", "act", "arm")):
        groups = collections.defaultdict(list)
        for row in rows:
            groups["|".join(row[key] for key in keys)].append(row)
        result["descriptives"]["_".join(keys)] = {key: descriptive(group) for key, group in sorted(groups.items())}
    ledger = []
    if info["complete"]:
        primaries, references = {}, {}
        for act in ("arrival", "correction"):
            stem_rows = aggregate_stems(rows, canonical["main"], act)
            expected_n = DEFAULT_PLAN["primary"][act+"_stems"]
            if len(stem_rows) != expected_n:
                raise ValueError("primary independent-stem count differs")
            expected_counts = {("F1", "immediate"): expected_n//8, ("F1", "delayed"): expected_n//8,
                               ("F2", "immediate"): expected_n//8, ("F2", "delayed"): expected_n//8,
                               ("F3", "immediate"): expected_n//4, ("F3", "delayed"): expected_n//4}
            if collections.Counter((r["family"], r["reception"]) for r in stem_rows) != expected_counts:
                raise ValueError("primary allocation is not proportional to the declared weights")
            gate = BM.evaluate([Fraction(r["difference_exact"]) for r in stem_rows], act)
            act_rows = [r for r in rows if r["act"] == act and r["arm"] in (BASELINE, CANDIDATE)]
            gate["paired"] = paired_summary(act_rows, CANDIDATE, BASELINE)
            gate["all_differences_zero"] = all(Fraction(r["difference_exact"]) == 0 for r in stem_rows)
            gate["both_arms_observed_ceiling"] = all(r["exact"] for r in act_rows)
            family_estimates = {family: sum((Fraction(r["difference_exact"]) for r in stem_rows if r["family"] == family), Fraction())
                                / sum(r["family"] == family for r in stem_rows) for family in ("F1", "F2", "F3")}
            sensitivity = sum(family_estimates.values(), Fraction())/3
            gate["equal_family_sensitivity"] = {"estimate_exact": str(sensitivity), "estimate": float(sensitivity),
                                                "family_estimates_exact": {f: str(v) for f, v in family_estimates.items()},
                                                "role": "descriptive prespecified sensitivity; never replaces frozen 1:1:2 gate"}
            primaries[act] = gate
            ledger.extend(stem_rows)
            for positive, negative in ((CANDIDATE, REFERENCE), (REFERENCE, BASELINE)):
                ref_ledger = aggregate_stems(rows, canonical["main"], act, positive, negative, reference=True)
                ref_stems = {r["stem"] for r in ref_ledger}
                selected = [r for r in rows if r["act"] == act and r["stem"] in ref_stems
                            and r["arm"] in (positive, negative)]
                key = f"{act}|{positive}_minus_{negative}"
                references[key] = {"independent_stems": len(ref_stems), **paired_summary(selected, positive, negative),
                                   "inferential_role": "descriptive matched subset; no qualification or fallback",
                                   "uncertainty": "not estimated; sparse matched subset cannot establish preservation, equivalence or no effect",
                                   "all_differences_zero": all(Fraction(r["difference_exact"]) == 0 for r in ref_ledger)}
                ledger.extend(ref_ledger)
        result["primary"] = primaries
        result["references"] = references
        result["qualification"] = {"status": "QUALIFIED" if all(v["pass"] for v in primaries.values()) else "NOT_QUALIFIED",
                                   "requires_both_components": True, "correction_tolerance_exact": "3/64",
                                   "decision_from_exact_evidence": True}
    else:
        result["inference_suppressed"] = "Incomplete infrastructure: no bounds, gates or qualification; scheduled counts only."
    return result, rows, ledger


def count_text(value):
    return f"{value['exact']}/{value['scheduled']} (usable {value['ok_usable']})" if value else "unavailable"


def render_report(result):
    infrastructure = result["infrastructure"]
    qualified = result["qualification"]["status"]
    lines = ["# Clarified KEEP package confirmation", "", f"**Integrity: {result['status']}. Qualification: {qualified}.**", "",
             f"Recorded calls: {infrastructure['attempts_recorded']}/2340; failed-attempt entries: {infrastructure['failed_attempt_entries']}.",
             "The primary comparison is KEEP_CLAR minus SUB_ORIG. SUB_CLAR is a descriptive reference and cannot rescue a failed primary gate.", ""]
    for stage, info in infrastructure["stages"].items():
        end = info.get("end", {})
        elapsed = end.get("elapsed_s")
        lines.append(f"{stage.capitalize()}: {info.get('records', 0)}/{info.get('scheduled', 0)} records; "
                     + (f"{elapsed/3600:.2f} hours; " if isinstance(elapsed, (int, float)) else "")
                     + f"END {end.get('at', 'missing')}.")
    lines += ["", f"Hard deadline: {infrastructure['deadline'].get('deadline_iso', 'unavailable')} (epoch clock authority; America/New_York).", ""]
    if result["status"] == "COMPLETE":
        lines += ["## Primary results", "", "| Component | Independent stems | KEEP − SUB (points) | One-sided 97.5% lower bound (points, approximate) | Exact T > 40? | Paired rescues / breaks |",
                  "|---|---:|---:|---:|---:|---:|"]
        pair_notes = []
        for act, gate in result["primary"].items():
            bound, pair = gate["lower_bound"], gate["paired"]
            pc = pair["paired_counts"]
            lines.append(f"| {act} | {gate['n']} | {100*gate['estimate']:+.2f} | {100*bound['lower']:+.4f} | "
                         f"{'pass' if gate['pass'] else 'fail'} | {pc.get('rescue', 0)} / {pc.get('break', 0)} |")
            pair_notes.append(f"{act.capitalize()} rescues involve {pair['rescue_stems']} independent stems; breaks involve {pair['break_stems']}.")
        lines += [""] + pair_notes
        lines += ["", "Arrival requires T(0)>40. Correction requires T(−3/64)>40. Equality fails. Exact rational evidence and direct decisions are stored in `analysis/confirm/ANALYSIS.json`; rounded bounds never decide qualification.",
                  "Qualification is conditional on the 3/64 correction tolerance. It does not establish no correction harm.",
                  "Both outcomes are shown together: arrival gains do not compensate for a failed correction gate.",
                  "The displayed lower bound is the conservative inverted endpoint. Its exact enclosing numerical bracket is retained in JSON as a calculation certificate, not a population interval."]
        for act, gate in result["primary"].items():
            bound = gate["lower_bound"]
            lines.append(f"{act.capitalize()} boundary flags: all stem differences zero={gate['all_differences_zero']}; "
                         f"both arms at observed ceiling={gate['both_arms_observed_ceiling']}; "
                         f"empty pass set={bound['empty_pass_set']}; numerical censoring={bound['censored']}.")
            lines.append(f"{act.capitalize()} equal-family sensitivity: {100*gate['equal_family_sensitivity']['estimate']:+.2f} points "
                         "(descriptive only; the frozen 1:1:2 gate is unchanged).")
        lines += ["Observed equal or perfect outputs do not establish equivalence; the bound retains uncertainty about rare future losses.",
                  "", "## Matched references (descriptive only)", "", "| Contrast | Independent stems | Targets/arm | Difference (points) | Rescues / breaks |",
                  "|---|---:|---:|---:|---:|"]
        for key, value in result["references"].items():
            pc = value["paired_counts"]
            lines.append(f"| {key} | {value['independent_stems']} | {value['targets_per_arm']} | {100*value['estimate']:+.2f} | {pc.get('rescue', 0)} / {pc.get('break', 0)} |")
        lines += ["", "References use their paired 32-arrival/16-correction stem subsets; they are not whole-panel comparisons, representation-only tests, or fallback qualification claims.",
                  "Reference uncertainty is not estimated here. These sparse matched subsets cannot establish preservation, equivalence, or no effect."]
    else:
        lines += [result["inference_suppressed"], ""] + ["- "+p for p in infrastructure["problems"]]
        lines += ["", "Interrupted calls without a result cannot be verified or counted as completed attempts; attempt accounting may be incomplete."]
    lines += ["", "## Side-by-side exactness", "", "| Act / arm | Exact / scheduled (usable) | Withdrawn-value errors | State-only arrivals | Accepted wrong bindings | Truncated |",
              "|---|---:|---:|---:|---:|---:|"]
    for key, value in result["descriptives"].get("act_arm", {}).items():
        lines.append(f"| {key} | {count_text(value)} | {value['withdrawn_value_error']} | {value['state_only_event_accepted']} | {value['accepted_wrong_binding']} | {value['truncated']} |")
    for dimension in ("family", "reception", "direction"):
        lines += ["", f"## Counts by {dimension}", "", "| Cell / act / arm | Exact / scheduled (usable) |",
                  "|---|---:|"]
        for key, value in result["descriptives"].get(dimension+"_act_arm", {}).items():
            lines.append(f"| {key} | {count_text(value)} |")
    lines += ["", "## Scope and evidence", "",
              "- Family allocation is the frozen 1:1:2 mixture with equal reception. Both histories/directions stay inside independent stems.",
              "- This tests the clarified KEEP package against original SUB on fresh generated worlds of the declared authored families, one model and fixed decoding. It does not identify original model intent or show uniform family benefit, unseen-family transfer, safe execution, or general deployment safety.",
              "- Exact extraction, preservation into the compiled contract, and restricted replay remain separate measurements. Open correction intervals only are in scope.",
              "- Wrong/malformed/truncated model content is semantically incorrect in its scheduled denominator. Infrastructure failures suppress all confidence statements and qualification.",
              "- The inherited contradictory-correction flag ignores times; simultaneous conflict checks explicit half-open interval overlap separately.",
              "", "Full diagnostic cells, cost and exact evidence: `analysis/confirm/ANALYSIS.json`. Per-call scores: `analysis/confirm/scored.jsonl`. Independent-stem audit trail: `analysis/confirm/stem-differences.jsonl`.",
              "The protocol stops after reporting. No next study, baseline replacement or publication is started.", ""]
    return "\n".join(lines)


def write_artifacts(hub):
    hub = Path(hub)
    result, rows, ledger = analyze(hub)
    out = hub / "analysis/confirm"
    out.mkdir(parents=True, exist_ok=True)
    for filename, values in (("scored.jsonl", rows), ("stem-differences.jsonl", ledger)):
        (out / filename).write_text("".join(json.dumps(value, sort_keys=True, default=str)+"\n" for value in values))
    (out / "ANALYSIS.json").write_text(json.dumps(result, sort_keys=True, indent=2)+"\n")
    (hub / "REPORT.md").write_text(render_report(result))
    status = result["qualification"]["status"]
    (hub / "RUN-STATUS.md").write_text(f"# Run status\n\n**{result['status']} / {status}.**\n\n"
                                      "See `REPORT.md`. No next stage started.\n")
    takeaway = (f"Integrity: {result['status']}. Qualification: {status}.\n\n"
                "Primary claim: clarified KEEP package versus original SUB under the declared generator and correction tolerance. "
                "Matched SUB_CLAR references do not replace the primary result. No equivalence, original-intent, uniform-benefit or transfer claim.\n")
    if result["status"] == "COMPLETE":
        for act, gate in result["primary"].items():
            bound = gate["lower_bound"]
            pair = gate["paired"]["paired_counts"]
            takeaway += (f"\n{act.capitalize()}: {100*gate['estimate']:+.2f} points across {gate['n']} independent stems; "
                         f"one-sided 97.5% lower bound approximately {100*bound['lower']:+.4f} points; "
                         f"exact gate {'passes' if gate['pass'] else 'fails'}. "
                         f"Paired rescues/breaks: {pair.get('rescue', 0)}/{pair.get('break', 0)}.\n")
        takeaway += "\nQualification remains conditional on the 3/64 correction tolerance; equal or perfect observed outcomes do not establish equivalence or no future harm.\n"
    else:
        takeaway += "\nAll bounds/gates are suppressed because infrastructure is incomplete. See `REPORT.md` for the recorded failure reasons and scheduled denominators.\n"
    (hub / "READER-TAKEAWAY-RESULTS.md").write_text("# Reader takeaway\n\n"+takeaway)
    (hub / "CLAIM-EVIDENCE-RESULTS.md").write_text("# Claim/evidence results\n\n"+takeaway+
        "\nEvidence: exact gate values and counts in `analysis/confirm/ANALYSIS.json`, raw-source scoring in `scored.jsonl`, "
        "and the independently grouped `stem-differences.jsonl`. Incomplete infrastructure leaves all gate claims unevaluated.\n")
    coverage = {key: {k: value[k] for k in ("scheduled", "ok_usable", "exact_extraction", "compilation_loss", "exact_end_to_end", "replay_ok")}
                for key, value in result["descriptives"].get("act_arm", {}).items()}
    (hub / "SEMANTIC-COVERAGE-RESULTS.md").write_text("# Semantic coverage results\n\n"+takeaway+
        "\nOpen-interval source extraction, compiled preservation and restricted replay counts follow. These are distinct measurements, not broad execution-safety evidence.\n\n```json\n"+
        json.dumps(coverage, indent=2, sort_keys=True)+"\n```\n")
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", required=True)
    args = ap.parse_args()
    result = write_artifacts(args.hub)
    print(json.dumps({"study": STUDY, "status": result["status"], "qualification": result["qualification"],
                      "problems": result["infrastructure"]["problems"]}))
    if result["status"] != "COMPLETE":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
