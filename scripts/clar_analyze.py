"""V1.23 development comparison; frozen HOLD-EVAL scoring, no model calls.

Usage: clar_analyze.py --hub HUB [--out-name dev]
Intervals are descriptive whole-stem percentile bootstrap references. There is no
qualification, significance, non-inferiority, or automatic next-stage decision.
"""
import argparse
import collections
import hashlib
import itertools
import json
import random
import statistics
from pathlib import Path

from _bootstrap import ROOT
from dream_core.ledger import release_source_hash
from tempo import factored as FA, kidconfdone as KD, kidconfscore as KS
from kconf_analyze import recipe_ok

ARMS = ("SUB_ORIG", "KEEP_ORIG", "SUB_CLAR", "KEEP_CLAR")
DIRECTIONS = ("yes_to_no", "no_to_yes")
HISTORIES = ("A", "B")
DEFAULT_PLAN = {"B": 10000, "seed": 2026111104, "interval": "descriptive_group_percentile95",
                "primary_family": "F2", "qualification": False}
DIAGNOSTICS = ("withdrawn_value_error", "state_correct_revision_withdrawn", "raw_revision_interval_ok",
               "raw_revision_value_correct", "revision_absent", "revision_multiple", "revision_wrong_field",
               "revision_wrong_target", "raw_extraction_invalid", "mixed_correction", "contradictory_correction",
               "simultaneous_value_conflict", "time_blind_conflict_without_simultaneous_conflict",
               "accepted_wrong_binding", "false_revision_raw", "false_revision_accepted", "truncated",
               "state_only_event_accepted", "arrival_event_present_raw", "arrival_rejected_extra_state")


def load(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_plan(plan):
    if plan != DEFAULT_PLAN:
        raise ValueError("analysis plan differs from the fixed V1.23 development recipe")


def records(hub, stage):
    out, duplicates, problems = {}, [], []
    for path in sorted((Path(hub) / "stages" / stage / "calls").glob("*.json")):
        try:
            rec = json.loads(path.read_text())
            cid = rec["call_id"]
            if cid in out:
                duplicates.append(cid)
            out[cid] = rec
        except (OSError, ValueError, KeyError, TypeError) as exc:
            problems.append(f"{stage}: unreadable record {path.name}: {type(exc).__name__}")
    return out, duplicates, problems


def check_records(calls, recs, duplicates=()):
    """Pure completeness check, including actual schedule text and result hashes."""
    problems = []
    ids = [c["call_id"] for c in calls]
    callmap = {c["call_id"]: c for c in calls}
    if len(ids) != len(set(ids)):
        problems.append("duplicate scheduled call IDs")
    if duplicates:
        problems.append(f"duplicate result records: {len(duplicates)}")
    if set(ids) != set(recs):
        problems.append(f"records != schedule: {len(set(ids)-set(recs))} missing, {len(set(recs)-set(ids))} extra")
    for cid, call in callmap.items():
        expected = hashlib.sha256(call["user"].encode()).hexdigest()
        if call.get("user_sha256") != expected:
            problems.append(f"schedule prompt hash mismatch: {cid}")
        rec = recs.get(cid)
        if rec is None:
            continue
        if rec.get("status") != "ok":
            problems.append(f"non-ok record: {cid}")
        if rec.get("complete") is not True:
            problems.append(f"incomplete result record: {cid}")
        if rec.get("user_sha256") != expected:
            problems.append(f"result prompt hash mismatch: {cid}")
        if not recipe_ok(rec):
            problems.append(f"result recipe mismatch: {cid}")
    return problems


def check_crossing(pubs, calls):
    """Every included stem has both correction directions/histories, all four cells."""
    problems, target_map = [], {p["target"]: p for p in pubs}
    if len(target_map) != len(pubs):
        problems.append("duplicate public targets")
    cells = collections.Counter()
    by_stem = collections.defaultdict(set)
    for p in pubs:
        stem = p.get("stem", p["group"])
        by_stem[stem].add((p["act"], p["direction"], p["history"]))
    for stem, units in by_stem.items():
        want = {("correction", d, h) for d in DIRECTIONS for h in HISTORIES}
        if any(a == "arrival" for a, _, _ in units):
            want |= {("arrival", "na", h) for h in HISTORIES}
        if units != want:
            problems.append(f"incomplete target crossing: {stem}")
    for call in calls:
        target, arm = call["call_id"].rsplit("|", 1)
        if target not in target_map or arm not in ARMS:
            problems.append(f"unknown target/arm: {call['call_id']}")
        cells[(target, arm)] += 1
    if cells != collections.Counter({(target, arm): 1 for target in target_map for arm in ARMS}):
        problems.append("calls != declared target x four-arm crossing")
    return problems


def freeze_problems(hub, frozen, plan):
    """Check current source AND actual frozen bytes, rather than only LOCK claims."""
    problems = []
    if frozen.get("source_sha256") != release_source_hash(ROOT):
        problems.append("current source differs from frozen source")
    if frozen.get("analysis_plan_sha256") != KD.plan_sha256(plan):
        problems.append("analysis-plan hash differs from freeze")
    for section in ("design", "config", "data", "phase0"):
        mapping = frozen.get(section)
        if not isinstance(mapping, dict) or not mapping:
            problems.append(f"missing frozen {section} file hashes")
            continue
        for rel, expected in mapping.items():
            path = Path(hub) / section / rel
            if not path.is_file() or sha(path) != expected:
                problems.append(f"frozen file mismatch: {section}/{rel}")
    driver = Path(hub) / "run_clar.sh"
    if frozen.get("driver_sha256") is not None and (not driver.is_file() or sha(driver) != frozen["driver_sha256"]):
        problems.append("driver hash differs from freeze")
    manifest = frozen.get("model_manifest_path")
    if manifest is not None and (not Path(manifest).is_file() or sha(manifest) != frozen.get("model_manifest_sha256")):
        problems.append("model manifest hash differs from freeze")
    return problems


def simultaneous_conflict(claims):
    """Explicit temporal overlap only; states/events are points, revisions [a,b).

    This diagnostic does not infer persistence or replace the frozen compiler.
    In particular a revision ending at b and a state at b do not overlap.
    """
    atoms = []
    for category in FA.LISTS:
        for x in (claims or {}).get(category, []):
            if category == "revisions":
                if x["valid_to"] is not None and x["valid_to"] <= x["valid_from"]:
                    continue
                atoms.append((x["field"], x["value"], x["valid_from"], x["valid_to"], False))
            elif category == "states" or "to" in x:
                atoms.append((x["field"], x.get("value", x.get("to")), x["at"], x["at"], True))
    for a, b in itertools.combinations(atoms, 2):
        if a[0] != b[0] or a[1] == b[1]:
            continue
        if a[4] and b[4]:
            overlap = a[2] == b[2]
        elif a[4] or b[4]:
            point, interval = (a, b) if a[4] else (b, a)
            overlap = interval[2] <= point[2] and (interval[3] is None or point[2] < interval[3])
        else:
            lo = max(a[2], b[2])
            ends = [x[3] for x in (a, b) if x[3] is not None]
            overlap = not ends or lo < min(ends)
        if overlap:
            return True
    return False


def revision_diagnostics(claims, case):
    """Raw-normalized means before R1-R3. Every scheduled correction is denominator."""
    gold = case["records"][-1]
    out = {key: False for key in ("withdrawn_value_error", "state_correct_revision_withdrawn",
                                 "raw_revision_interval_ok", "raw_revision_value_correct", "revision_absent",
                                 "revision_multiple", "revision_wrong_field", "revision_wrong_target")}
    out["raw_extraction_invalid"] = claims is None
    out["simultaneous_value_conflict"] = simultaneous_conflict(claims)
    if gold["kind"] != "correction":
        return out
    p = gold["payload"]
    if claims is None:
        out["revision_category"] = "invalid_extraction"
        return out
    revisions = claims["revisions"]
    if not revisions:
        out["revision_absent"], out["revision_category"] = True, "absent"
        return out
    if len(revisions) != 1:
        out["revision_multiple"], out["revision_category"] = True, "multiple"
        return out
    rev = revisions[0]
    out["revision_wrong_field"] = rev["field"] != p["field"]
    out["revision_wrong_target"] = rev["target"] != p["target"]
    if out["revision_wrong_field"] or out["revision_wrong_target"]:
        out["revision_category"] = "wrong_field_and_target" if all(out[k] for k in ("revision_wrong_field", "revision_wrong_target")) \
            else "wrong_field" if out["revision_wrong_field"] else "wrong_target"
        return out
    old_record = next(r for r in case["records"][:-1] if r["rid"] == p["target"])
    old = old_record["payload"].get("value", old_record["payload"].get("assign", {}).get(p["field"]))
    out.update(revision_category="single_matching", withdrawn_value=old, corrected_value=p["value"],
               withdrawn_value_error=rev["value"] == old,
               raw_revision_value_correct=rev["value"] == p["value"],
               raw_revision_interval_ok=(rev["valid_from"] == p["valid_from"] and rev["valid_to"] == p.get("valid_to")))
    out["state_correct_revision_withdrawn"] = out["withdrawn_value_error"] and any(
        s["field"] == p["field"] and s["value"] == p["value"] and s["at"] == p["valid_from"]
        for s in claims["states"])
    return out


def score_one(rec, hidden, pub, call):
    usable = rec is not None and rec.get("status") == "ok" and rec.get("complete") is True \
        and rec.get("user_sha256") == call["user_sha256"] \
        and recipe_ok(rec)
    valid_rec = rec if usable else None
    # Unchanged scorer: canonical target/prefix, including original interval semantics.
    s = KS.score_record(valid_rec, hidden, pub)
    _, trace = FA.compile_reply(valid_rec["raw"] if usable else None, pub["registry"])
    s.update(revision_diagnostics(trace.get("claims"), hidden["case"]))
    s["time_blind_conflict_without_simultaneous_conflict"] = bool(s.get("contradictory_correction")) \
        and not s["simultaneous_value_conflict"]
    s["accepted_wrong_binding"] = bool(s.get("accepted")) and not s.get("bound_ok_accepted")
    s.update(call_id=call["call_id"], target=pub["target"], arm=call["call_id"].rsplit("|", 1)[1],
             stem=pub.get("stem", pub["group"]), group=pub["group"], family=pub["family"][:2],
             act=pub["act"], direction=pub["direction"], history=pub["history"], reception=pub["reception"])
    return s


def describe(rows):
    """Scheduled denominators remain explicit; missing calls never masquerade as successes."""
    rows = list(rows)
    return {"scheduled": len(rows), "ok_usable": sum(not r["incomplete"] for r in rows),
            "incomplete": sum(bool(r["incomplete"]) for r in rows),
            "exact": sum(bool(r["exact"]) for r in rows),
            **{key: sum(bool(r.get(key)) for r in rows) for key in DIAGNOSTICS},
            "revision_categories": dict(collections.Counter(r.get("revision_category", "not_correction") for r in rows)),
            "rejection_codes": dict(collections.Counter(str(r.get("contract_code") or r.get("pending_code"))
                                                        for r in rows if r.get("rejected"))),
            "seconds_mean": statistics.mean([r["seconds"] for r in rows if r.get("seconds") is not None])
            if any(r.get("seconds") is not None for r in rows) else None}


def contrasts(rows, B=10000, seed=2026111104, intervals=True):
    """Cell means average directions/history within stem, then stems equally.

    Resampling is shared by all contrasts: whole stems within family x reception,
    carrying all directions, histories, arms and outcomes together. No historical
    1:1:2 family mixture is imposed on this F2-enriched development panel.
    """
    rows = list(rows)
    specs = {}
    metrics = ("exact", "withdrawn_value_error")
    for metric in metrics:
        for arm in ("KEEP", "SUB"):
            specs[f"correction|{metric}|F2|{arm}_clar_minus_orig"] = (
                "correction", metric, {"family": "F2"}, {arm+"_CLAR": 1, arm+"_ORIG": -1})
        specs[f"correction|{metric}|F2|interaction"] = ("correction", metric, {"family": "F2"},
                {"KEEP_CLAR": 1, "KEEP_ORIG": -1, "SUB_CLAR": -1, "SUB_ORIG": 1})
    for family in sorted({r["family"] for r in rows}):
        for act in ("correction", "arrival"):
            for wording in ("ORIG", "CLAR"):
                specs[f"{act}|exact|{family}|KEEP_minus_SUB_{wording}"] = (act, "exact", {"family": family},
                                                                            {"KEEP_"+wording: 1, "SUB_"+wording: -1})
            for arm in ("KEEP", "SUB"):
                specs[f"{act}|exact|{family}|{arm}_clar_minus_orig"] = (act, "exact", {"family": family},
                                                                        {arm+"_CLAR": 1, arm+"_ORIG": -1})
                if act == "correction":
                    for dimension, vals in (("direction", DIRECTIONS), ("reception", ("immediate", "delayed"))):
                        for value in vals:
                            specs[f"{act}|exact|{family}|{arm}_clar_minus_orig|{dimension}={value}"] = (
                                act, "exact", {"family": family, dimension: value},
                                {arm+"_CLAR": 1, arm+"_ORIG": -1})
    by_stem, stem_strata = collections.defaultdict(list), {}
    for r in rows:
        by_stem[r["stem"]].append(r)
        stem_strata[r["stem"]] = (r["family"], r["reception"])
    stratum_stems = collections.defaultdict(list)
    for stem in sorted(by_stem):
        stratum_stems[stem_strata[stem]].append(stem)
    stem_values, result = {}, {}
    for name, (act, metric, filters, coefficients) in specs.items():
        values, paired, n_targets = {}, collections.Counter(), 0
        for stem, rs in by_stem.items():
            selected = [r for r in rs if r["act"] == act and all(r.get(k) == v for k, v in filters.items())]
            if not selected:
                continue
            by_arm = {arm: [r for r in selected if r["arm"] == arm] for arm in coefficients}
            lengths = {len(v) for v in by_arm.values()}
            if len(lengths) != 1 or not all(by_arm.values()):
                raise ValueError(f"unpaired contrast: {name}/{stem}")
            if any(r["incomplete"] for rs2 in by_arm.values() for r in rs2):
                raise ValueError(f"incomplete contrast: {name}/{stem}")
            values[stem] = sum(coef * statistics.mean(bool(r.get(metric)) for r in by_arm[arm])
                               for arm, coef in coefficients.items())
            n_targets += next(iter(lengths))
            if len(coefficients) == 2 and sorted(coefficients.values()) == [-1, 1]:
                pos = next(a for a, v in coefficients.items() if v == 1)
                neg = next(a for a, v in coefficients.items() if v == -1)
                mp = {(r["direction"], r["history"]): bool(r.get(metric)) for r in by_arm[pos]}
                mn = {(r["direction"], r["history"]): bool(r.get(metric)) for r in by_arm[neg]}
                if mp.keys() != mn.keys():
                    raise ValueError(f"mismatched pairing: {name}/{stem}")
                paired.update("both" if mp[k] and mn[k] else "positive_only" if mp[k] else "negative_only"
                              if mn[k] else "neither" for k in mp)
        if values:
            stem_values[name] = values
            result[name] = {"estimate": statistics.mean(values.values()), "independent_stems": len(values),
                            "targets_per_arm": n_targets, "paired_counts": dict(paired),
                            "metric": metric, "coefficients": coefficients,
                            "interval_label": "descriptive whole-stem percentile 95% reference"}
    if intervals:
        rng = random.Random(seed)
        draws = {name: [] for name in result}
        arrival_strata = {k: [g for g in v if any(r["act"] == "arrival" for r in by_stem[g])]
                          for k, v in stratum_stems.items()}
        for _ in range(B):
            sampled = [rng.choice(stems) for _, stems in sorted(stratum_stems.items()) for _ in stems]
            arrival_sampled = [rng.choice(stems) for _, stems in sorted(arrival_strata.items()) if stems for _ in stems]
            for name, values in stem_values.items():
                # Each act uses its fixed, frozen panel. For arrivals, sample
                # only nested selected stems, preserving its stratum counts.
                selected_sample = arrival_sampled if specs[name][0] == "arrival" else sampled
                kept = [values[stem] for stem in selected_sample if stem in values]
                draws[name].append(statistics.mean(kept))
        for name, values in draws.items():
            ordered = sorted(values)
            result[name]["reference_95_interval"] = [ordered[int(.025 * B)], ordered[int(.975 * B)-1]]
    return result


def analyze(hub, plan):
    validate_plan(plan)
    hub = Path(hub)
    public = load(hub / "data/public/main-targets.jsonl")
    hidden = load(hub / "data/hidden/main-cases.jsonl")
    pubs = {p["target"]: p for p in public}
    hid = {h["target"]: h for h in hidden}
    calls = load(hub / "data/main-calls.jsonl")
    recs, dup, problems = records(hub, "main")
    problems += check_records(calls, recs, dup) + check_crossing(public, calls)
    if len(hid) != len(hidden) or set(hid) != set(pubs):
        problems.append("hidden targets duplicated or differ from public targets")
    try:
        frozen = json.loads((hub / "config/FROZEN-PROTOCOL.json").read_text())
        problems += freeze_problems(hub, frozen, plan)
        done = KD.completion(hub, frozen["source_sha256"])
        problems += done["problems"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        done = {"complete": False, "error": type(exc).__name__}
        problems.append(f"freeze or runner completion unreadable: {type(exc).__name__}")
    for stage, count in (("main", 640), ("smoke", 48)):
        stage_calls = load(hub / "data" / f"{stage}-calls.jsonl")
        stage_pub = load(hub / "data/public" / f"{stage}-targets.jsonl")
        sr, sd, sp = records(hub, stage)
        problems += sp + check_records(stage_calls, sr, sd) + check_crossing(stage_pub, stage_calls)
        if len(stage_calls) != count:
            problems.append(f"{stage}: expected {count} scheduled calls")
        commit = json.loads((hub / "data" / f"COMMITMENT-{stage}.json").read_text())
        if commit.get("calls_sha256") != sha(hub / "data" / f"{stage}-calls.jsonl"):
            problems.append(f"{stage}: actual call-file hash differs from commitment")
    rows = []
    for call in calls:
        target = call["call_id"].rsplit("|", 1)[0]
        if target not in hid or target not in pubs:
            problems.append(f"cannot score undeclared target: {target}")
            continue
        rows.append(score_one(recs.get(call["call_id"]), hid[target], pubs[target], call))
    complete = not problems
    stage_timings = {}
    for stage in ("smoke", "main"):
        end_path = hub / "stages" / stage / "END.json"
        if end_path.is_file():
            end = json.loads(end_path.read_text())
            stage_timings[stage] = {k: end.get(k) for k in ("at", "elapsed_s", "load_s", "finished")}
    res = {"study": "CLAR-v1", "status": "COMPLETE" if complete else "INCOMPLETE", "comparison": "prespecified development",
           "qualification": None, "qualification_applicable": False, "plan": plan,
           "infrastructure": {"complete": complete, "problems": sorted(set(problems)), "completion": done,
                              "scheduled_main": len(calls), "record_files_main": len(recs), "duplicate_results": dup,
                              "stage_timings": stage_timings},
           "descriptives": {}}
    for keys in (("act", "arm"), ("family", "act", "arm"), ("reception", "act", "arm"),
                 ("family", "direction", "act", "arm"),
                 ("family", "reception", "direction", "act", "arm")):
        grouped = collections.defaultdict(list)
        for row in rows:
            grouped["|".join(row[key] for key in keys)].append(row)
        res["descriptives"]["_".join(keys)] = {key: describe(v) for key, v in sorted(grouped.items())}
    if complete:
        res["contrasts"] = contrasts(rows, plan["B"], plan["seed"])
    else:
        res["inference_suppressed"] = "Incomplete collection/integrity: counts and scheduled denominators only; no contrasts or intervals."
    return res, rows


def render_report(res):
    lines = ["# Revision-value clarification development comparison", "", f"**Status: {res['status']}.**",
             "This is a prespecified development comparison; no qualification or formal harm/preservation test is defined.", ""]
    done = res["infrastructure"]["completion"]
    lines += ["## Integrity", "",
              f"Attempts: {done.get('attempts_used', 'unknown')} / {done.get('attempt_ceiling', 'unknown')} ceiling; "
              "planned 688 calls (640 main and 48 structural smoke).",
              f"Frozen source/config/data checks and runner completion: {'passed' if res['infrastructure']['complete'] else 'incomplete; see problems below'}."]
    for stage, timing in res["infrastructure"].get("stage_timings", {}).items():
        elapsed = timing.get("elapsed_s")
        lines.append(f"{stage.capitalize()} stage: {elapsed/3600:.2f} hours; END at {timing.get('at')}." if elapsed is not None
                     else f"{stage.capitalize()} END at {timing.get('at')}.")
    lines.append("")
    if res["status"] == "COMPLETE":
        lines += ["## F2 prespecified contrasts", "", "| Outcome / contrast | Estimate (points) | Descriptive 95% reference interval |",
                  "|---|---:|---:|"]
        for metric in ("exact", "withdrawn_value_error"):
            for contrast in ("KEEP_clar_minus_orig", "SUB_clar_minus_orig", "interaction"):
                c = res["contrasts"][f"correction|{metric}|F2|{contrast}"]
                lo, hi = c["reference_95_interval"]
                lines.append(f"| {metric}: {contrast} | {100*c['estimate']:+.2f} | [{100*lo:+.2f}, {100*hi:+.2f}] |")
        lines += ["", "A positive exactness contrast favors clarification; a negative withdrawn-value-error contrast favors clarification.",
                  "The interaction is the KEEP clarification effect minus the SUB clarification effect.",
                  "These estimates describe the assigned prompt manipulation on these authored families; error patterns do not establish an internal reasoning mechanism."]
        lines += ["", "## Arrival guards", "", "| Family / contrast | Estimate (points) | Descriptive 95% reference interval |",
                  "|---|---:|---:|"]
        for family in ("F2", "F1", "F3"):
            for contrast in ("KEEP_clar_minus_orig", "SUB_clar_minus_orig", "KEEP_minus_SUB_CLAR"):
                c = res["contrasts"].get(f"arrival|exact|{family}|{contrast}")
                if c is None:
                    continue
                lo, hi = c["reference_95_interval"]
                lines.append(f"| {family}: {contrast} | {100*c['estimate']:+.2f} | [{100*lo:+.2f}, {100*hi:+.2f}] |")
        lines += ["", "These small arrival panels can reveal regressions; intervals crossing zero do not establish preservation."]
    else:
        lines += [res["inference_suppressed"], ""] + ["- "+p for p in res["infrastructure"]["problems"]]
    lines += ["", "## Counts", "", "| Act / arm | Exact / scheduled | Usable | Withdrawn-value errors | Mixed correction |",
              "|---|---:|---:|---:|---:|"]
    for key, v in res["descriptives"]["act_arm"].items():
        lines.append(f"| {key} | {v['exact']}/{v['scheduled']} | {v['ok_usable']} | {v['withdrawn_value_error']} | {v['mixed_correction']} |")
    lines += ["", "## F2 corrections by direction", "", "| Direction / arm | Exact / scheduled | Withdrawn-value errors / scheduled |",
              "|---|---:|---:|"]
    for direction in DIRECTIONS:
        for arm in ARMS:
            v = res["descriptives"]["family_direction_act_arm"].get(f"F2|{direction}|correction|{arm}")
            if v:
                lines.append(f"| {direction}: {arm} | {v['exact']}/{v['scheduled']} | {v['withdrawn_value_error']}/{v['scheduled']} |")
    lines += ["", "## Sentinel exact counts", "", "| Family / act | SUB original | KEEP original | SUB clarified | KEEP clarified |",
              "|---|---:|---:|---:|---:|"]
    for family in ("F1", "F3"):
        for act in ("correction", "arrival"):
            cells = [res["descriptives"]["family_act_arm"].get(f"{family}|{act}|{arm}") for arm in ARMS]
            values = [f"{v['exact']}/{v['scheduled']}" if v else "missing" for v in cells]
            lines.append(f"| {family}: {act} | "+" | ".join(values)+" |")
    lines += ["", "## Reading limits", "", "- F2 is the primary family; F1/F3 are low-precision sentinels. No historical family weights are imposed.",
              "- Both correction directions and paired histories remain together when resampling whole independent stems within family/reception.",
              "- The nested arrival subset is resampled separately within its fixed family/reception allocation; arrival effects are guards, not preservation tests.",
              "- The withdrawn-value diagnostic requires exactly one raw-normalized revision matching the expected field and target. Missing, multiple, invalid, and wrong-target/field revisions remain in the scheduled denominator and are counted separately.",
              "- The historical contradictory-correction flag ignores times. The separate simultaneous-conflict diagnostic checks explicit points against half-open revision intervals without inferring persistence.",
              "- Compiler, exactness scorer, model, and decoding are unchanged. No conclusion about unseen families, broader transfer, general safety, or absence of harm follows.",
              "", "Full cells, paired counts, diagnostics, costs and reference intervals: `analysis/dev/ANALYSIS.json`; individual scores: `analysis/dev/scored.jsonl`.",
              "No next stage is authorized by this report.", ""]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", required=True)
    ap.add_argument("--out-name", default="dev")
    args = ap.parse_args()
    hub = Path(args.hub)
    plan = json.loads((hub / "config/ANALYSIS-PLAN.json").read_text())
    res, rows = analyze(hub, plan)
    out = hub / "analysis" / args.out_name
    out.mkdir(parents=True, exist_ok=True)
    (out / "scored.jsonl").write_text("".join(json.dumps(row, sort_keys=True, default=str)+"\n" for row in rows))
    (out / "ANALYSIS.json").write_text(json.dumps(res, indent=2, sort_keys=True)+"\n")
    (hub / "REPORT.md").write_text(render_report(res))
    (hub / "RUN-STATUS.md").write_text(f"# Run status\n\n**{res['status']}: prespecified development comparison.**\n\n"
                                      "No qualification decision. See `REPORT.md`. No next stage started.\n")
    print(json.dumps({"status": res["status"], "qualification_applicable": False,
                      "problems": res["infrastructure"]["problems"]}))
    if res["status"] != "COMPLETE":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
