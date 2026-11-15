"""Analyse the paired prose-robustness study (development; descriptive only).

Usage: repair_analyze.py --hub HUB --set SET --initial-stage S0 --retry-stage S1 [--boot 10000] [--seed 20261105]
Branches per history x surface, replayed with the same frozen pipeline (tempo.repair.run_branch):
  no-retry  : initial replies only; failures registered as unprocessed (completeness-aware state)
  one-retry : the same initial replies; stored retry replies (prompt sha verified) for rejected records
Reference S: the engine fed the gold public records.
Primary (pre-declared): exact completeness-aware supported state at the final checkpoint (a field touched by
unprocessed evidence counts as not exact). Secondary: all-checkpoint exactness, action-verdict accuracy, the
old-policy view (last accepted values, ignoring incompleteness) under its own label.
"""
import argparse
import collections
import json
import time
from pathlib import Path

from _bootstrap import ROOT  # noqa: F401
from tempo_analyze import bootstrap, domain_weighted, load, mean
from tempo import engine as E, engine_fixtures as EF, repair as RP, resolve
from tempo.worlds import UNKNOWN
from hist_analyze import compare_record
from repair_run import branch_inputs, initial_replies, inputs, safe

POLICIES = ("no_retry", "one_retry")


def asserted_values(records, f, now):
    vals = set()
    for r in records:
        if r["received_at"] > now:
            continue
        p = r["payload"]
        if r["kind"] == "initial" and f in p["assign"]:
            vals.add(p["assign"][f])
        elif p.get("field") == f:
            vals |= {p.get(x) for x in ("value", "from", "to") if p.get(x) is not None}
    return vals


def score_state(st, gold, asked, records, now):
    out = collections.Counter()
    out["exact"] = 1
    for f in asked:
        g, v = gold[f], st.get(f, "missing")
        if v == g:
            out["correct"] += 1
            continue
        out["exact"] = 0
        if v in ("missing",):
            out["missing"] += 1
        elif v == "incomplete":
            out["incomplete"] += 1
        elif v == UNKNOWN:
            out["false_unknown"] += 1
        elif g == UNKNOWN:
            out["false_certainty"] += 1
        else:
            out["wrong_definite"] += 1
            if v in asserted_values(records, f, now):
                out["outdated"] += 1
    out["n"] = len(asked)
    return dict(out)


def snapshot(h, cp, eng):
    v = eng.view("current", cp["now"])
    aware = {f: v["complete_per_field"].get(f, "missing") for f in h["asked"]}
    old = {f: v["per_field"].get(f, "missing") for f in h["asked"]}
    head = eng.log.head()
    b = eng.branch(cp["now"])
    tests = []
    for t in cp["tests"]:
        vv = eng.check_action(b, t["action"])["verdict"]
        tests.append({"action": t["action"], "verdict": vv, "gold_verdict": t["gold_verdict"],
                      "true_legal": t["true_legal"], "correct": vv == t["gold_verdict"],
                      "wrongly_allowed": vv == "allowed" and not t["true_legal"],
                      "wrongly_blocked": vv == "blocked" and t["true_legal"]})
    return {"k": cp["k"], "aware": aware, "old": old, "pending": v["pending"],
            "score": score_state(aware, cp["gold_state"], h["asked"], h["records"], cp["now"]),
            "score_old": score_state(old, cp["gold_state"], h["asked"], h["records"], cp["now"]),
            "tests": tests, "log_unchanged_by_tests": eng.log.head() == head,
            "focal_gold_unknown": cp["gold_state"][h["focal_field"]] == UNKNOWN,
            "focal_unknown_kept": cp["gold_state"][h["focal_field"]] == UNKNOWN and aware[h["focal_field"]] == UNKNOWN}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", required=True)
    ap.add_argument("--set", required=True)
    ap.add_argument("--initial-stage", required=True)
    ap.add_argument("--retry-stage", required=True)
    ap.add_argument("--boot", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=20261105)
    a = ap.parse_args()
    hub = Path(a.hub)
    hs, calls, gold = inputs(hub, a.set)
    init = initial_replies(hub, a.initial_stage, calls)
    irec = {cid: json.loads((hub / "stages" / a.initial_stage / "calls" / f"{safe(cid)}.json").read_text())
            for cid in calls}
    rdir = hub / "stages" / a.retry_stage / "calls"
    rrec = {json.loads(p.read_text())["call_id"]: json.loads(p.read_text()) for p in rdir.glob("*.json")} \
        if rdir.exists() else {}
    rec_rows, cp_rows = [], []
    t_engine = 0.0
    for h in hs:
        cps = {cp["k"]: cp for cp in h["checkpoints"]}
        # reference S
        eng = E.Engine(EF.spec_from_world(h["world"], h["domain"], h["records"]), f"{h['history_id']}|S")
        for k, r in enumerate(h["public_records"], 1):
            eng.ingest_report(dict(r, source="env"))
            if k in cps:
                cp_rows.append(dict(snapshot(h, cps[k], eng), history_id=h["history_id"], domain=h["domain"],
                                    pattern=h["pattern"], surface="structured", policy="reference"))
        for surface in ("lines", "prose"):
            kw, ks = branch_inputs(h, calls, gold, surface, init)
            if not ks:
                continue
            for pol in POLICIES:
                missing_retry = []

                def retry_fn(k, prompt, surface=surface):
                    cid = f"{h['history_id']}|{surface}|r{k}|retry"
                    r = rrec.get(cid)
                    if r is None:
                        missing_retry.append(k)
                        return None
                    import hashlib
                    if r["user_sha256"] != hashlib.sha256(prompt.encode()).hexdigest():
                        raise SystemExit(f"retry {cid} was made from a different prompt")
                    return r["raw"] if r["status"] == "ok" else None
                snaps = []
                t0 = time.perf_counter()
                rows, _ = RP.run_branch(context=f"{h['history_id']}|{surface}|{pol}",
                                        retry_fn=retry_fn if pol == "one_retry" else None,
                                        on_checkpoint=lambda k, e: snaps.append(snapshot(h, cps[k], e)), **kw)
                t_engine += time.perf_counter() - t0
                for s in snaps:
                    cp_rows.append(dict(s, history_id=h["history_id"], domain=h["domain"], pattern=h["pattern"],
                                        surface=surface, policy=pol))
                for r in rows:
                    cid = f"{h['history_id']}|{surface}|r{r['k']}"
                    g = gold[cid]
                    ci = compare_record(r["initial"]["record"], g["gold"], g["text"])
                    cf = compare_record(r["final"]["record"], g["gold"], g["text"])
                    row = {"call_id": cid, "history_id": h["history_id"], "domain": h["domain"],
                           "pattern": h["pattern"], "surface": surface, "policy": pol, "k": r["k"],
                           "gold_kind": g["gold"]["kind"], "initial_exact": ci["exact"],
                           "initial_errors": ci["errors"], "initial_accepted": r["initial"]["accepted"],
                           "initial_code": r["initial"]["code"], "initial_norm": r["initial"]["norm"],
                           "retried": r["retried"], "final_exact": cf["exact"], "final_errors": cf["errors"],
                           "final_accepted": r["final"]["accepted"], "final_code": r["final"]["code"],
                           "retry_missing": r["k"] in missing_retry,
                           "initial_raw": init[cid], "retry_raw": r.get("retry", {}).get("raw"),
                           "retry_norm": r.get("retry", {}).get("norm"),
                           "retry_changed_keys": sorted(_diff(r["initial"]["record"], r.get("retry", {}).get("record")))
                           if r["retried"] else None}
                    rec_rows.append(row)
    out = hub / f"analysis-{a.set}"
    out.mkdir(exist_ok=True)
    for name, rows in (("records", rec_rows), ("checkpoints", cp_rows)):
        with open(out / f"{name}.jsonl", "w") as fh:
            for r in rows:
                fh.write(json.dumps(r, default=str) + "\n")
    gdom = {h["history_id"]: h["domain"] for h in hs}
    B, sd = a.boot, a.seed

    def est(gv):
        gv = {g: v for g, v in gv.items() if v is not None}
        m = domain_weighted(gv, gdom)
        return {"mean": None if m is None else round(m, 4), "ci95": bootstrap(gv, gdom, B, sd), "histories": len(gv)}

    res = {"set": a.set, "initial_calls": len(calls),
           "initial_status": dict(collections.Counter(r["status"] for r in irec.values())),
           "initial_truncated": sum(1 for r in irec.values() if r.get("stop") == "length"),
           "retry_calls": len(rrec), "retry_status": dict(collections.Counter(r["status"] for r in rrec.values())),
           "retry_truncated": sum(1 for r in rrec.values() if r.get("stop") == "length"),
           "cost": {s: {"initial_output_tokens": sum(irec[c].get("output_tokens") or 0 for c in calls if calls[c]["surface"] == s),
                        "initial_seconds": round(sum(irec[c].get("seconds") or 0 for c in calls if calls[c]["surface"] == s), 1),
                        "retry_calls": sum(1 for r in rrec.values() if r["surface"] == s),
                        "retry_output_tokens": sum(r.get("output_tokens") or 0 for r in rrec.values() if r["surface"] == s),
                        "retry_seconds": round(sum(r.get("seconds") or 0 for r in rrec.values() if r["surface"] == s), 1)}
                    for s in ("lines", "prose")},
           "engine_replay_seconds_total": round(t_engine, 3), "cells": {}, "contrasts": {}}
    gvals = {}
    for surface in ("structured", "lines", "prose"):
        for pol in (("reference",) if surface == "structured" else POLICIES):
            cr = [r for r in cp_rows if r["surface"] == surface and r["policy"] == pol]
            if not cr:
                continue
            rr = [r for r in rec_rows if r["surface"] == surface and r["policy"] == pol]
            tests = [t for r in cr for t in r["tests"]]
            fin = {r["history_id"]: float(r["score"]["exact"]) for r in cr if r["k"] == 6}
            allcp = collections.defaultdict(list)
            ver = collections.defaultdict(list)
            for r in cr:
                allcp[r["history_id"]].append(float(r["score"]["exact"]))
                ver[r["history_id"]] += [float(t["correct"]) for t in r["tests"]]
            sc = lambda key: sum(r["score"].get(key, 0) for r in cr)
            d = {"PRIMARY_final_exact": est(fin), "final_exact_count": f"{int(sum(fin.values()))}/{len(fin)}",
                 "all_checkpoint_exact": est({g: mean(v) for g, v in allcp.items()}),
                 "all_checkpoint_exact_count": f"{sum(r['score']['exact'] for r in cr)}/{len(cr)}",
                 "old_policy_final_exact_count": f"{sum(r['score_old']['exact'] for r in cr if r['k'] == 6)}/{len(fin)}",
                 "fields": f"{sc('correct')}/{sc('n')}",
                 **{k: sc(k) for k in ("incomplete", "missing", "false_unknown", "false_certainty", "wrong_definite",
                                       "outdated")},
                 "verdict_accuracy": est({g: mean(v) for g, v in ver.items()}),
                 "verdict_correct": f"{sum(t['correct'] for t in tests)}/{len(tests)}",
                 "verdicts": dict(collections.Counter(t["verdict"] for t in tests)),
                 "wrongly_allowed_vs_truth": sum(t["wrongly_allowed"] for t in tests),
                 "wrongly_blocked_vs_truth": sum(t["wrongly_blocked"] for t in tests),
                 "genuine_unknown_kept": f"{sum(r['focal_unknown_kept'] for r in cr)}/{sum(r['focal_gold_unknown'] for r in cr)}",
                 "log_unchanged_by_tests": f"{sum(r['log_unchanged_by_tests'] for r in cr)}/{len(cr)}",
                 "pending_at_final": sum(len(r["pending"]) for r in cr if r["k"] == 6)}
            if rr:
                d["records"] = {
                    "n": len(rr), "initial_exact": sum(r["initial_exact"] for r in rr),
                    "initial_accepted": sum(r["initial_accepted"] for r in rr),
                    "initial_exact_but_rejected": sum(1 for r in rr if r["initial_exact"] and not r["initial_accepted"]),
                    "retried": sum(r["retried"] for r in rr),
                    "retry_accepted": sum(1 for r in rr if r["retried"] and r["final_accepted"]),
                    "retry_exact": sum(1 for r in rr if r["retried"] and r["final_exact"]),
                    "retry_accepted_but_wrong": sum(1 for r in rr if r["retried"] and r["final_accepted"] and not r["final_exact"]),
                    "final_exact": sum(r["final_exact"] for r in rr), "final_accepted": sum(r["final_accepted"] for r in rr),
                    "final_accepted_but_wrong": sum(1 for r in rr if r["final_accepted"] and not r["final_exact"]),
                    "final_exact_but_rejected": sum(1 for r in rr if r["final_exact"] and not r["final_accepted"]),
                    "unprocessed": sum(1 for r in rr if not r["final_accepted"]),
                    "retry_missing": sum(r["retry_missing"] for r in rr),
                    "initial_reject_codes": dict(collections.Counter(r["initial_code"] for r in rr if not r["initial_accepted"])),
                    "initial_error_classes": dict(collections.Counter(e for r in rr for e in r["initial_errors"])),
                    "final_error_classes": dict(collections.Counter(e for r in rr for e in r["final_errors"])),
                    "normalisation_rules": dict(collections.Counter(n["rule"] for r in rr for n in r["initial_norm"] or [])),
                    "exact_by_kind": {kd: f"{sum(1 for r in rr if r['gold_kind'] == kd and r['final_exact'])}/{sum(1 for r in rr if r['gold_kind'] == kd)}" for kd in E.KINDS}}
            res["cells"][f"{surface}:{pol}"] = d
            gvals[(surface, pol)] = ({g: v for g, v in fin.items()}, {g: mean(v) for g, v in ver.items()})
    for nm, x, y in [("lines: one_retry - no_retry", ("lines", "one_retry"), ("lines", "no_retry")),
                     ("prose: one_retry - no_retry", ("prose", "one_retry"), ("prose", "no_retry")),
                     ("no_retry: prose - lines", ("prose", "no_retry"), ("lines", "no_retry")),
                     ("one_retry: prose - lines", ("prose", "one_retry"), ("lines", "one_retry"))]:
        if x in gvals and y in gvals:
            c = {}
            for i, key in enumerate(("final_exact", "verdict_accuracy")):
                X, Y = gvals[x][i], gvals[y][i]
                dd = {g: X[g] - Y[g] for g in X if g in Y}
                e = est(dd)
                e.update(better=sum(v > 0 for v in dd.values()), equal=sum(v == 0 for v in dd.values()),
                         worse=sum(v < 0 for v in dd.values()))
                c[key] = e
            res["contrasts"][nm] = c
    (out / "ANALYSIS.json").write_text(json.dumps(res, indent=1, default=str) + "\n")
    (out / "TABLES.md").write_text(tables(res))
    print(tables(res))


def _diff(a, b):
    if not isinstance(a, dict) or not isinstance(b, dict):
        return {"whole_record"}
    out = {k for k in set(a) | set(b) if k not in ("payload", "evidence") and a.get(k) != b.get(k)}
    pa, pb = a.get("payload") or {}, b.get("payload") or {}
    if isinstance(pa, dict) and isinstance(pb, dict):
        out |= {f"payload.{k}" for k in set(pa) | set(pb) if pa.get(k) != pb.get(k)}
    return out


def f(e):
    if not e or e.get("mean") is None:
        return "—"
    ci = e.get("ci95")
    return f"{e['mean']:.3f}" + (f" [{ci[0]:.2f}, {ci[1]:.2f}]" if ci else "")


def tables(res):
    L = ["# Prose-robustness study tables (generated)", "",
         f"Initial calls {res['initial_calls']} {res['initial_status']} (truncated {res['initial_truncated']}); retry "
         f"calls {res['retry_calls']} {res['retry_status']} (truncated {res['retry_truncated']}); cost {res['cost']}; "
         f"engine replay {res['engine_replay_seconds_total']} s.", "",
         "## States and verdicts", "",
         "| Cell | final exact (aware) | all checkpoints | old-policy final | fields | incomplete | false unknown | wrong definite (outdated) | verdicts | verdict mix | wrongly allowed / blocked vs truth | genuine unknown kept | pending at final | log unchanged |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for k, d in res["cells"].items():
        L.append(f"| {k} | {d['final_exact_count']}; {f(d['PRIMARY_final_exact'])} | {d['all_checkpoint_exact_count']} | "
                 f"{d['old_policy_final_exact_count']} | {d['fields']} | {d['incomplete']} | {d['false_unknown']} | "
                 f"{d['wrong_definite']} ({d['outdated']}) | {d['verdict_correct']}; {f(d['verdict_accuracy'])} | "
                 f"{d['verdicts']} | {d['wrongly_allowed_vs_truth']} / {d['wrongly_blocked_vs_truth']} | "
                 f"{d['genuine_unknown_kept']} | {d['pending_at_final']} | {d['log_unchanged_by_tests']} |")
    L += ["", "## Records", ""]
    for k, d in res["cells"].items():
        if "records" in d:
            L.append(f"- **{k}**: {d['records']}")
    L += ["", "## Paired contrasts (per history; better / equal / worse)", "",
          "| Contrast | final exact | verdict accuracy |", "|---|---|---|"]
    for k, c in res["contrasts"].items():
        a, b = c["final_exact"], c["verdict_accuracy"]
        L.append(f"| {k} | {f(a)} ({a['better']}/{a['equal']}/{a['worse']}) | {f(b)} ({b['better']}/{b['equal']}/{b['worse']}) |")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
