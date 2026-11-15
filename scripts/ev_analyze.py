"""EVT-v1 analyzer (adapted from es_analyze.py): integrity, unchanged V1.24 scoring, guarded replay and the pre-declared development screen.

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
from tempo import evreport as ES, kidconfscore as KS
import clar_analyze as CA
from kconf_analyze import recipe_ok

STUDY = ES.STUDY
ARMS = ES.ARMS
GUARD_DECIDE = ROOT / "tools/identity-guard-replay/guard/decide.py"
GUARD_DECIDE_SHA256 = "4213bc4eb8aef3c5f05f3056ac4b991ab150c2f756b41bfdce0c32aa8c6a77bf"
PLAN = {
    "study": STUDY, "candidate": "KEEP_EVT", "current": "KEEP_CLAR",
    "primary_outcome": "accepted state-only arrivals (event omitted, state accepted)",
    "unit": "independent stem; arrival d_g = mean of 2 history differences, correction d_g = mean of 4",
    "wording": "arrival wording from public bit b1: 0 = RESULT ('so it is now on hand'), 1 = TRANSITION",
    "screen": {
        "state_only_halved": "accepted state-only arrivals: KEEP_EVT <= floor(KEEP_CLAR / 2), and KEEP_CLAR >= 10",
        "arrival_exact_min_points": 0.0,
        "transition_wording_arrival_exact_min_points": -3.0,
        "wrong_bindings_max_excess": 2,
        "correction_exact_min": "-3/64",
        "new_failure_types": "outcome classes present in KEEP_EVT but absent in KEEP_CLAR (per act) -> manual review",
    },
    "descriptive_only": ["revision objects on arrivals", "event objects on corrections", "truncation",
                         "output tokens", "RESULT-wording contrast", "guarded replay"],
    "bootstrap": {"B": 10000, "seed": 2026111244, "resample": "stems within family x reception",
                  "use": "descriptive 95% percentile interval only; never a gate"},
    "guard": {"decide_sha256": GUARD_DECIDE_SHA256, "role": "secondary descriptive replay"},
}
OUT = "analysis/dev"


def validate_plan(plan):
    if json.dumps(plan, sort_keys=True) != json.dumps(PLAN, sort_keys=True):
        raise ValueError("analysis plan differs from the declared EVT-v1 plan")
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
    for stage, n in (("smoke", 24), ("main", 960)):
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
        s.update(bits="".join(map(str, pub["bits"])), block=pub["block"], outcome=KS.outcome(s),
                 wording=ES.wording(pub["bits"]))
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
    out["responses_with_revision_objects"] = sum((r.get("raw_revisions") or 0) > 0 for r in rs)
    out["responses_with_event_objects"] = sum((r.get("raw_events") or 0) > 0 for r in rs)
    out["output_tokens_max"] = max((r.get("output_tokens") or 0) for r in rs) if rs else 0
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
    cand, cur = "KEEP_EVT", "KEEP_CLAR"
    wb = {a: sum(r["accepted_wrong_binding"] for r in rows if r["arm"] == a) for a in ARMS}
    so = {a: by_arm_act[f"{a}|arrival"]["state_only_event_accepted"] for a in ARMS}
    arr = contrasts_["arrival|KEEP_EVT-KEEP_CLAR"]["difference_points"]
    trans = contrasts_["arrival|TRANSITION|KEEP_EVT-KEEP_CLAR"]["difference_points"]
    cor = contrasts_["correction|KEEP_EVT-KEEP_CLAR"]["difference_points"]
    crit = {
        "state_only_halved_with_baseline_at_least_10": so[cur] >= 10 and so[cand] <= so[cur] // 2,
        "arrival_exact_not_lower": arr >= p["arrival_exact_min_points"],
        "transition_wording_arrival_exact_not_lower_than_3_points":
            trans >= p["transition_wording_arrival_exact_min_points"],
        "wrong_bindings_not_more_than_plus_2": wb[cand] <= wb[cur] + p["wrong_bindings_max_excess"],
        "correction_exact_not_lower_than_3_64": cor >= -100 * 3 / 64,
    }
    new = {}
    for act in ("arrival", "correction"):
        current = set(by_arm_act[f"{cur}|{act}"]["outcomes"])
        new[act] = {k: v for k, v in by_arm_act[f"{cand}|{act}"]["outcomes"].items() if k not in current}
    if not all(crit.values()):
        status = "DOES_NOT_WARRANT"
    elif any(new.values()):
        status = "REVIEW_NEW_FAILURE_TYPES"
    else:
        status = "WARRANTS_CONFIRMATION_DESIGN"
    return {"status": status, "criteria": crit, "accepted_wrong_bindings": wb, "state_only_arrivals": so,
            "arrival_difference_points": arr, "transition_arrival_difference_points": trans,
            "correction_difference_points": cor, "new_outcome_classes_in_candidate": new,
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
        cons[f"{act}|KEEP_EVT-KEEP_CLAR"] = contrast(rows, act, "KEEP_EVT", "KEEP_CLAR", strata)
        cons[f"{act}|usable_exact|KEEP_EVT-KEEP_CLAR"] = contrast(rows, act, "KEEP_EVT", "KEEP_CLAR", strata,
                                                                  "usable_exact")
    for w in ("RESULT", "TRANSITION"):
        sub = [r for r in rows if r["act"] != "arrival" or r["wording"] == w]
        cons[f"arrival|{w}|KEEP_EVT-KEEP_CLAR"] = contrast(sub, "arrival", "KEEP_EVT", "KEEP_CLAR",
                                                           {r["stem"]: strata[r["stem"]] for r in sub
                                                            if r["act"] == "arrival"})
    result.update(
        status="COMPLETE", screen=screen(rows, by_arm_act, cons), by_arm_act=by_arm_act, contrasts=cons,
        breakdowns_descriptive={"|".join(k): cells(rows, ("arm", "act") + k) for k in
                                (("wording",), ("family",), ("family", "history"), ("reception",), ("bits",),
                                 ("direction",), ("family", "wording"))},
        wrong_bindings=[{k: r.get(k) for k in ("call_id", "family", "history", "reception", "bits", "guard_disposition",
                                                "guard_compiled_fields", "guard_resolved")}
                        for r in rows if r["accepted_wrong_binding"]],
        exact_blocked_by_guard=[r["call_id"] for r in rows if r["exact_blocked"]],
        truncated=[r["call_id"] for r in rows if r.get("truncated")],
        cost={a: {"seconds_mean": statistics.mean(r["seconds"] for r in rows if r["arm"] == a),
                  "input_tokens_max": max(r["input_tokens"] for r in rows if r["arm"] == a),
                  "output_tokens_mean": statistics.mean(r["output_tokens"] for r in rows if r["arm"] == a)}
              for a in ARMS})
    return result, rows


def fmt_cell(c):
    return f"{c['exact']}/{c['n']}"


def render(result):
    L = ["# EVT-v1 event-reporting development comparison", ""]
    if result["status"] != "COMPLETE":
        L += ["**Status: INCOMPLETE.** No screen result or intervals.", "",
              "Problems:", ""] + [f"- {p}" for p in result["infrastructure"]["problems"][:40]]
        return "\n".join(L) + "\n"
    s = result["screen"]
    L += [f"**Status: COMPLETE. Development screen: {s['status']}.** Not a qualification gate.", "",
          "Arms: KEEP_CLAR (current), KEEP_EVT (KEEP_CLAR + one event-reporting sentence). Qwen3-32B NF4, greedy, "
          "thinking off. Fresh generated worlds; F1:F2:F3 = 1:1:4; RESULT and TRANSITION arrival wordings balanced.",
          "", "## Side by side", "",
          "| Arm / act | Exact | Accepted state-only | Accepted wrong binding | Accepted inexact | Rejected | "
          "Withdrawn value | Truncated | With revision objects | With event objects |",
          "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for a in ARMS:
        for act in ("arrival", "correction"):
            c = result["by_arm_act"][f"{a}|{act}"]
            L.append(f"| {a} {act} | {fmt_cell(c)} | {c['state_only_event_accepted']} | {c['accepted_wrong_binding']} | "
                     f"{c['accepted_inexact']} | {c['rejected']} | {c['withdrawn_value_error']} | {c['truncated']} | "
                     f"{c['responses_with_revision_objects']} | {c['responses_with_event_objects']} |")
    L += ["", "Revision objects on arrivals and event objects on corrections are spurious for these targets; "
          "counts are from compiled replies (unparseable replies are not counted there).", "",
          "## Arrivals by wording", "", "| Arm | Wording | Exact | Accepted state-only | Rejected |", "|---|---|---:|---:|---:|"]
    bw = result["breakdowns_descriptive"]["wording"]
    for a in ARMS:
        for w in ("RESULT", "TRANSITION"):
            c = bw.get(f"{a}|arrival|{w}")
            if c:
                L.append(f"| {a} | {w} | {fmt_cell(c)} | {c['state_only_event_accepted']} | {c['rejected']} |")
    L += ["", "## Paired stem differences (descriptive bootstrap intervals, not gates)", "",
          "| Contrast | Stems | Difference (points) | Bootstrap 95% (points) | Target rescues / breaks |",
          "|---|---:|---:|---:|---:|"]
    for k, c in result["contrasts"].items():
        lo, hi = c["bootstrap95_points_descriptive"]
        label = k.replace("|", ": ", 1).replace("|", " ")
        L.append(f"| {label} | {c['stems']} | {c['difference_points']:+.2f} | [{lo:+.2f}, {hi:+.2f}] | "
                 f"{c['rescues']} / {c['breaks']} |")
    L += ["", "## Reading guide (frozen before output)", "", "| Criterion | Result |", "|---|---|"]
    L += [f"| {k} | {'pass' if v else '**fail**'} |" for k, v in s["criteria"].items()]
    L += ["", f"State-only arrivals: {s['state_only_arrivals']}. Accepted wrong bindings (all acts): "
          f"{s['accepted_wrong_bindings']}.",
          f"New outcome classes in KEEP_EVT (absent in KEEP_CLAR): {s['new_outcome_classes_in_candidate']}.", "",
          "## Guarded replay (IGUARD-v0.1 decision function, unchanged)", "",
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
    L += ["", f"Truncated replies: {result['truncated'] or 'none'}.", "",
          "## Cost", ""] + [f"- {a}: mean {c['seconds_mean']:.1f} s/call, max input {c['input_tokens_max']} tokens, "
                            f"mean output {c['output_tokens_mean']:.0f} tokens" for a, c in result["cost"].items()]
    L += ["", "## Scope", "",
          "- Development screen on fresh generated worlds of the declared families (assembly domain only), one model "
          "and fixed decoding. The sentence's examples name actions from this world's rules.",
          "- Passing a threshold on a point estimate is not equivalence or non-inferiority; intervals are descriptive.",
          "- Rejected answers remain wrong. The guard addresses identity, not event omission.",
          "- No qualification, transfer, rare-error elimination or safety claim. The protocol stops after reporting.",
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
