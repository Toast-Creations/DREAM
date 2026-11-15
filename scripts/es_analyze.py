"""ESUB-v1 analyzer: integrity, unchanged V1.24 scoring, guarded replay and the pre-declared development screen.

Development screen, not a qualification gate. Every scheduled call is scored in its own denominator with the unchanged
V1.24 scorer (clar_analyze.score_one -> kidconfscore/HOLD-EVAL-v1 against the ORIGINAL target and prefix). Missing,
duplicate, extra, corrupt or non-usable records make the run INCOMPLETE and suppress the screen.

Guarded replay: IGUARD-v0.1's decision function (guard/decide.py, hash-pinned, loaded read-only) is applied to every
response from its public inputs only. final_accepted = accepted AND guard_pass; usable_exact = exact AND guard_pass.
"""
import collections
import hashlib
import importlib.util
import json
import math
import random
import statistics
import sys
from pathlib import Path

from _bootstrap import ROOT
from dream_core import localpaths as LP  # public release: local paths from environment
from dream_core.ledger import atomic_json, release_source_hash
from tempo import esubject as ES, kidconfscore as KS
import clar_analyze as CA
from kconf_analyze import recipe_ok

STUDY = ES.STUDY
ARMS = ES.ARMS
GUARD_DECIDE = ROOT / "tools/identity-guard-replay/guard/decide.py"
GUARD_DECIDE_SHA256 = "4213bc4eb8aef3c5f05f3056ac4b991ab150c2f756b41bfdce0c32aa8c6a77bf"
PLAN = {
    "study": STUDY, "candidate": "KEEP_SUBJ", "current": "KEEP_CLAR", "anchor": "SUB_ORIG",
    "unit": "independent stem; arrival d_g = mean of 2 history differences, correction d_g = mean of 4",
    "screen": {
        "wrong_bindings_not_more": "accepted wrong bindings KEEP_SUBJ <= KEEP_CLAR, all acts and F3 history-B arrivals",
        "arrival_exact_min_points": -3.0,
        "state_only_arrivals_max_excess": 3,
        "correction_exact_min": "-3/64",
        "new_failure_types": "outcome classes present in KEEP_SUBJ but absent in KEEP_CLAR (per act) -> manual review",
    },
    "bootstrap": {"B": 10000, "seed": 2026111134, "resample": "stems within family x reception",
                  "use": "descriptive 95% percentile interval only; never a gate"},
    "guard": {"decide_sha256": GUARD_DECIDE_SHA256, "role": "secondary descriptive replay"},
}
OUT = "analysis/dev"


def validate_plan(plan):
    if json.dumps(plan, sort_keys=True) != json.dumps(PLAN, sort_keys=True):
        raise ValueError("analysis plan differs from the declared ESUB-v1 plan")
    return plan


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_jsonl(path, problems, label):
    rows = []
    try:
        for i, line in enumerate(Path(path).read_text().splitlines(), 1):
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    problems.append(f"{label}: corrupt line {i}")
    except OSError as e:
        problems.append(f"{label}: unreadable {e}")
    return rows


def keyed(rows, key, problems, label):
    out = {}
    for r in rows:
        k = r.get(key)
        if k in out:
            problems.append(f"{label}: duplicate {k}")
        out[k] = r
    return out


def record_usable(rec, call):
    return (isinstance(rec, dict) and rec.get("status") == "ok" and rec.get("complete") is True
            and rec.get("attempts") == 1 and rec.get("user_sha256") == call.get("user_sha256") and recipe_ok(rec)
            and rec.get("stop") in ("eos", "length")
            and type(rec.get("seconds")) in (int, float) and math.isfinite(rec["seconds"]) and rec["seconds"] >= 0)


def load_records(hub, stage, problems):
    recs = {}
    d = Path(hub) / "stages" / stage / "calls"
    for p in sorted(d.glob("*.json")) if d.exists() else []:
        try:
            r = json.loads(p.read_text())
        except ValueError:
            problems.append(f"{stage}: corrupt record {p.name}")
            continue
        cid = r.get("call_id") if isinstance(r, dict) else None
        if not isinstance(cid, str) or p.name != cid.replace("|", "__") + ".json":
            problems.append(f"{stage}: record file/call_id mismatch {p.name}")
            continue
        if cid in recs:
            problems.append(f"{stage}: duplicate record {cid}")
        recs[cid] = r
    return recs


def integrity(hub):
    """-> (info, bundle). info['complete'] False on any infrastructure problem."""
    hub = Path(hub)
    problems = []
    frozen = {}
    try:
        frozen = json.loads((hub / "config/FROZEN-PROTOCOL.json").read_text())
        if frozen.get("study") != STUDY or frozen.get("source_sha256") != release_source_hash(ROOT):
            problems.append("frozen study/source differs from the analyzing source")
        for section in ("design", "config", "data", "phase0"):
            for rel, digest in (frozen.get(section) or {}).items():
                if sha(hub / section / rel) != digest:
                    problems.append(f"frozen file changed: {section}/{rel}")
        validate_plan(frozen.get("analysis_plan"))
    except (OSError, ValueError) as e:
        problems.append(f"freeze unreadable/invalid: {e!r}")
    cfg = ES.validate_config(json.loads((hub / "config/PANEL.json").read_text()))
    bundle = {}
    for stage, n in (("smoke", 36), ("main", 1440)):
        allocation = ES.plan(cfg, smoke=(stage == "smoke"))
        expected_calls = ES.allowed_call_ids(allocation)
        expected_targets = {m["target"]: m for m in ES.expected_targets(allocation)}
        calls = keyed(load_jsonl(hub / f"data/{stage}-calls.jsonl", problems, f"{stage} calls"), "call_id",
                      problems, f"{stage} calls")
        pubs = keyed(load_jsonl(hub / f"data/public/{stage}-targets.jsonl", problems, f"{stage} public"), "target",
                     problems, f"{stage} public")
        hid = keyed(load_jsonl(hub / f"data/hidden/{stage}-cases.jsonl", problems, f"{stage} hidden"), "target",
                    problems, f"{stage} hidden")
        allowed = {r["call_id"] for r in load_jsonl(hub / "data/ALLOWED-CALLS.jsonl", problems, "allowed")
                   if r.get("set") == stage}
        if set(calls) != expected_calls or allowed != expected_calls or len(calls) != n:
            problems.append(f"{stage}: schedule membership differs from the declared allocation")
        if set(pubs) != set(expected_targets) or set(hid) != set(expected_targets):
            problems.append(f"{stage}: target membership differs from the declared allocation")
        recs = load_records(hub, stage, problems)
        if set(recs) != set(calls):
            problems.append(f"{stage}: records missing {len(set(calls) - set(recs))}, extra {len(set(recs) - set(calls))}")
        bad = sorted(c for c in calls if c in recs and not record_usable(recs[c], calls[c]))
        if bad:
            problems.append(f"{stage}: {len(bad)} records not usable (status/recipe/prompt/stop): {bad[:3]}")
        end = hub / "stages" / stage / "END.json"
        if not end.is_file() or json.loads(end.read_text()).get("finished") is not True or \
                (hub / "stages" / stage / "STOP.json").exists():
            problems.append(f"{stage}: stage did not finish")
        for att in (hub / "stages" / stage).glob("attempts.jsonl"):
            if att.read_text().strip():
                problems.append(f"{stage}: failed attempts recorded")
        bundle[stage] = {"calls": calls, "public": pubs, "hidden": hid, "records": recs, "allocation": allocation}
    info = {"complete": not problems, "problems": problems,
            "records": {s: len(b["records"]) for s, b in bundle.items()},
            "source_sha256": release_source_hash(ROOT), "frozen_source_sha256": frozen.get("source_sha256")}
    return info, bundle


def load_guard():
    if sha(GUARD_DECIDE) != GUARD_DECIDE_SHA256:
        raise ValueError("IGUARD decide.py differs from the pinned reviewed version")
    spec = importlib.util.spec_from_file_location("iguard_decide", GUARD_DECIDE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)   # imports tempo.refres / tempo.factored from this (byte-identical) tree
    return mod


def score(bundle):
    guard = load_guard()
    rows = []
    for cid in sorted(bundle["calls"]):
        call = bundle["calls"][cid]
        tid = cid.rsplit("|", 1)[0]
        pub, hid = bundle["public"][tid], bundle["hidden"][tid]
        rec = bundle["records"].get(cid)
        rec = dict(rec) if record_usable(rec, call) else None
        if rec is not None and not isinstance(rec.get("raw"), (str, type(None))):
            rec["raw"] = None
        s = CA.score_one(rec, hid, pub, call)
        s.update(bits="".join(map(str, pub["bits"])), block=pub["block"], outcome=KS.outcome(s))
        d = guard.decide(pub["prefix"], pub["target_text"], pub["registry"], pub["registry_order"],
                         rec["raw"] if rec else None)
        s.update(guard_disposition=d["disposition"], guard_mismatch=d["mismatch_kind"], guard_pass=d["guard_pass"],
                 guard_resolved=d["resolver"]["field"], guard_compiled_fields=d["compiled_fields"])
        s["final_accepted"] = bool(s.get("accepted")) and d["guard_pass"]
        s["usable_exact"] = bool(s["exact"]) and d["guard_pass"]
        s["post_wrong_binding"] = s["final_accepted"] and not s.get("bound_ok_accepted")
        s["exact_blocked"] = bool(s["exact"]) and not d["guard_pass"]
        rows.append(s)
    return rows


COUNTED = ("exact", "accepted", "rejected", "accepted_wrong_binding", "state_only_event_accepted",
           "withdrawn_value_error", "truncated", "empty_extraction", "mixed_correction", "incomplete",
           "final_accepted", "usable_exact", "post_wrong_binding", "exact_blocked")


def summarize(rs):
    rs = list(rs)
    out = {"n": len(rs), "stems": len({r["stem"] for r in rs}), **{k: sum(bool(r.get(k)) for r in rs) for k in COUNTED}}
    out["accepted_inexact"] = sum(bool(r.get("accepted")) and not r["exact"] for r in rs)
    out["revision_start_wrong"] = sum(r.get("rev_from_ok") is False for r in rs)
    out["guard"] = dict(collections.Counter(r["guard_disposition"] for r in rs))
    out["outcomes"] = dict(collections.Counter(r["outcome"] for r in rs))
    return out


def cells(rows, keys):
    g = collections.defaultdict(list)
    for r in rows:
        g["|".join(str(r[k]) for k in keys)].append(r)
    return {k: summarize(v) for k, v in sorted(g.items())}


def stem_differences(rows, act, pos, neg, metric="exact"):
    by = collections.defaultdict(dict)
    for r in rows:
        if r["act"] == act:
            by[r["stem"]].setdefault((r["direction"], r["history"]), {})[r["arm"]] = bool(r.get(metric))
    out = {}
    for stem, cellmap in by.items():
        diffs = [v[pos] - v[neg] for v in cellmap.values()]
        out[stem] = statistics.mean(diffs)
    return out


def bootstrap(diffs, strata, B, seed):
    rng = random.Random(seed)
    groups = collections.defaultdict(list)
    for stem, d in diffs.items():
        groups[strata[stem]].append(d)
    n = sum(len(v) for v in groups.values())
    means = []
    for _ in range(B):
        total = 0.0
        for v in groups.values():
            total += sum(v[rng.randrange(len(v))] for _ in v)
        means.append(total / n)
    means.sort()
    return [means[int(0.025 * B)], means[int(0.975 * B) - 1]]


def contrast(rows, act, pos, neg, strata, metric="exact"):
    d = stem_differences(rows, act, pos, neg, metric)
    by = collections.defaultdict(dict)
    for r in rows:
        if r["act"] == act:
            by[(r["stem"], r["direction"], r["history"])][r["arm"]] = bool(r.get(metric))
    rescues = sum(v[pos] and not v[neg] for v in by.values())
    breaks = sum(v[neg] and not v[pos] for v in by.values())
    lo, hi = bootstrap(d, strata, PLAN["bootstrap"]["B"], PLAN["bootstrap"]["seed"])
    return {"stems": len(d), "difference_points": 100 * statistics.mean(d.values()),
            "bootstrap95_points_descriptive": [100 * lo, 100 * hi], "rescues": rescues, "breaks": breaks,
            "stems_with_rescue": sum(1 for s in d if d[s] > 0), "stems_with_break": sum(1 for s in d if d[s] < 0)}


def screen(rows, by_arm_act, contrasts_):
    p = PLAN["screen"]
    wb = {a: sum(r["accepted_wrong_binding"] for r in rows if r["arm"] == a) for a in ARMS}
    f3b = {a: sum(r["accepted_wrong_binding"] for r in rows if r["arm"] == a and r["act"] == "arrival"
                  and r["family"] == "F3" and r["history"] == "B") for a in ARMS}
    so = {a: by_arm_act[f"{a}|arrival"]["state_only_event_accepted"] for a in ARMS}
    arr = contrasts_["arrival|KEEP_SUBJ-KEEP_CLAR"]["difference_points"]
    cor = contrasts_["correction|KEEP_SUBJ-KEEP_CLAR"]["difference_points"]
    crit = {
        "wrong_bindings_not_more": wb["KEEP_SUBJ"] <= wb["KEEP_CLAR"] and f3b["KEEP_SUBJ"] <= f3b["KEEP_CLAR"],
        "arrival_exact_not_lower_than_3_points": arr >= p["arrival_exact_min_points"],
        "state_only_not_more_than_plus_3": so["KEEP_SUBJ"] <= so["KEEP_CLAR"] + p["state_only_arrivals_max_excess"],
        "correction_exact_not_lower_than_3_64": cor >= -100 * 3 / 64,
    }
    new = {}
    for act in ("arrival", "correction"):
        cur = set(by_arm_act[f"KEEP_CLAR|{act}"]["outcomes"])
        cand = by_arm_act[f"KEEP_SUBJ|{act}"]["outcomes"]
        new[act] = {k: v for k, v in cand.items() if k not in cur}
    if not all(crit.values()):
        status = "DOES_NOT_WARRANT"
    elif any(new.values()):
        status = "REVIEW_NEW_FAILURE_TYPES"
    else:
        status = "WARRANTS_CONFIRMATION_DESIGN"
    return {"status": status, "criteria": crit, "accepted_wrong_bindings": wb, "f3_history_b_arrival_wrong_bindings": f3b,
            "state_only_arrivals": so, "arrival_difference_points": arr, "correction_difference_points": cor,
            "new_outcome_classes_in_candidate": new,
            "meaning": "development screen on fresh generated worlds; not qualification, not a rare-error or "
                       "transfer claim"}


def analyze(hub):
    info, bundle = integrity(hub)
    result = {"study": STUDY, "plan": PLAN, "infrastructure": info}
    if not info["complete"]:
        result.update(status="INCOMPLETE", screen={"status": "NOT_EVALUATED"},
                      inference_suppressed="Incomplete collection: no screen result or intervals.")
        return result, []
    rows = score(bundle["main"])
    strata = {r["stem"]: f"{r['family']}|{r['reception']}" for r in rows}
    by_arm_act = cells(rows, ("arm", "act"))
    cons = {}
    for act in ("arrival", "correction"):
        for pos, neg in (("KEEP_SUBJ", "KEEP_CLAR"), ("KEEP_SUBJ", "SUB_ORIG"), ("KEEP_CLAR", "SUB_ORIG")):
            cons[f"{act}|{pos}-{neg}"] = contrast(rows, act, pos, neg, strata)
        cons[f"{act}|usable_exact|KEEP_SUBJ-KEEP_CLAR"] = contrast(rows, act, "KEEP_SUBJ", "KEEP_CLAR", strata,
                                                                   "usable_exact")
    result.update(
        status="COMPLETE", screen=screen(rows, by_arm_act, cons), by_arm_act=by_arm_act, contrasts=cons,
        breakdowns_descriptive={"|".join(k): cells(rows, ("arm", "act") + k) for k in
                                (("family",), ("family", "history"), ("reception",), ("bits",), ("direction",))},
        wrong_bindings=[{k: r.get(k) for k in ("call_id", "family", "history", "reception", "bits", "guard_disposition",
                                                "guard_compiled_fields", "guard_resolved")}
                        for r in rows if r["accepted_wrong_binding"]],
        exact_blocked_by_guard=[r["call_id"] for r in rows if r["exact_blocked"]],
        cost={a: {"seconds_mean": statistics.mean(r["seconds"] for r in rows if r["arm"] == a),
                  "input_tokens_max": max(r["input_tokens"] for r in rows if r["arm"] == a),
                  "output_tokens_mean": statistics.mean(r["output_tokens"] for r in rows if r["arm"] == a)}
              for a in ARMS})
    return result, rows


def fmt_cell(c):
    return f"{c['exact']}/{c['n']}"


def render(result):
    L = [f"# ESUB-v1 explicit-subject development comparison", ""]
    if result["status"] != "COMPLETE":
        L += [f"**Status: INCOMPLETE.** No screen result or intervals.", "",
              "Problems:", ""] + [f"- {p}" for p in result["infrastructure"]["problems"][:40]]
        return "\n".join(L) + "\n"
    s = result["screen"]
    L += [f"**Status: COMPLETE. Development screen: {s['status']}.** Not a qualification gate.", "",
          "Arms: SUB_ORIG (anchor), KEEP_CLAR (current), KEEP_SUBJ (KEEP_CLAR + one explicit-subject sentence). "
          "Qwen3-32B NF4, greedy, thinking off. Fresh generated worlds; F1:F2:F3 = 1:1:4.", "",
          "## Side by side", "",
          "| Arm / act | Exact | Accepted wrong binding | Accepted state-only | Accepted inexact | Rejected | "
          "Withdrawn value | Wrong revision start | Truncated |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for a in ARMS:
        for act in ("arrival", "correction"):
            c = result["by_arm_act"][f"{a}|{act}"]
            L.append(f"| {a} {act} | {fmt_cell(c)} | {c['accepted_wrong_binding']} | {c['state_only_event_accepted']} | "
                     f"{c['accepted_inexact']} | {c['rejected']} | {c['withdrawn_value_error']} | "
                     f"{c['revision_start_wrong']} | {c['truncated']} |")
    L += ["", "## Paired stem differences (descriptive bootstrap intervals, not gates)", "",
          "| Contrast | Stems | Difference (points) | Bootstrap 95% (points) | Rescues / breaks |", "|---|---:|---:|---:|---:|"]
    for k, c in result["contrasts"].items():
        lo, hi = c["bootstrap95_points_descriptive"]
        L.append(f"| {k} | {c['stems']} | {c['difference_points']:+.2f} | [{lo:+.2f}, {hi:+.2f}] | "
                 f"{c['rescues']} / {c['breaks']} |")
    L += ["", "## Reading guide (frozen before output)", "", "| Criterion | Result |", "|---|---|"]
    L += [f"| {k} | {'pass' if v else '**fail**'} |" for k, v in s["criteria"].items()]
    L += ["", f"Accepted wrong bindings (all acts): {s['accepted_wrong_bindings']}; F3 history-B arrivals: "
          f"{s['f3_history_b_arrival_wrong_bindings']}. State-only arrivals: {s['state_only_arrivals']}.",
          f"New outcome classes in KEEP_SUBJ (absent in KEEP_CLAR): {s['new_outcome_classes_in_candidate']}.", "",
          "## F3 history B arrivals", "", "| Arm | Exact | Wrong binding | State-only |", "|---|---:|---:|---:|"]
    fh = result["breakdowns_descriptive"].get("family|history")
    for a in ARMS:
        c = (fh or {}).get(f"{a}|arrival|F3|B")
        if c:
            L.append(f"| {a} | {fmt_cell(c)} | {c['accepted_wrong_binding']} | {c['state_only_event_accepted']} |")
    L += ["", "## Guarded replay (IGUARD-v0.1 decision function, unchanged)", "",
          "| Arm / act | Exact → usable exact | Wrong binding before → after | Exact blocked | Guard dispositions |",
          "|---|---:|---:|---:|---|"]
    for a in ARMS:
        for act in ("arrival", "correction"):
            c = result["by_arm_act"][f"{a}|{act}"]
            L.append(f"| {a} {act} | {c['exact']} → {c['usable_exact']} | {c['accepted_wrong_binding']} → "
                     f"{c['post_wrong_binding']} | {c['exact_blocked']} | {c['guard']} |")
    L += ["", "Accepted wrong bindings (all listed):", ""]
    L += [f"- `{w['call_id']}` bits {w['bits']} {w['reception']}: guard {w['guard_disposition']} "
          f"({w['guard_compiled_fields']} vs {w['guard_resolved']})" for w in result["wrong_bindings"]] or ["- none"]
    L += ["", "## Cost", ""] + [f"- {a}: mean {c['seconds_mean']:.1f} s/call, max input {c['input_tokens_max']} tokens, "
                                  f"mean output {c['output_tokens_mean']:.0f} tokens" for a, c in result["cost"].items()]
    L += ["", "## Scope", "",
          "- Development screen on fresh generated worlds of the declared families, one model and fixed decoding.",
          "- About 3–4 KEEP_CLAR F3 history-B wrong bindings were expected from earlier panels; a small difference in "
          "this count cannot distinguish a real change from chance. Regressions are what this panel can expose.",
          "- Rejected answers remain wrong. The guard and the prompt address different things; neither targets "
          "state-only arrivals.", "- No qualification, transfer, rare-error elimination or safety claim. "
          "The protocol stops after reporting.",
          "", "Full data: `analysis/dev/ANALYSIS.json`, per-call `analysis/dev/scored.jsonl`."]
    return "\n".join(L) + "\n"


def write_artifacts(hub):
    hub = Path(hub)
    result, rows = analyze(hub)
    out = hub / OUT
    out.mkdir(parents=True, exist_ok=True)
    if rows:
        with open(out / "scored.jsonl", "w") as f:
            for r in rows:
                f.write(json.dumps(r, sort_keys=True, default=str) + "\n")
    atomic_json(out / "ANALYSIS.json", result)
    (hub / "REPORT.md").write_text(render(result))
    status = result["status"] + ("" if result["status"] != "COMPLETE" else " / " + result["screen"]["status"])
    (hub / "RUN-STATUS.md").write_text(f"# Run status\n\n**{status}.**\n\nSee `REPORT.md`. No next stage started.\n")
    return result


if __name__ == "__main__":
    r = write_artifacts(sys.argv[1])
    print(json.dumps({"status": r["status"], "screen": r.get("screen", {}).get("status")}))
