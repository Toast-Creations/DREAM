"""V1.19.0 scoring and analysis (no model).
Usage: hold_analyze.py --hub HUB --set SET --stage-small STAGE --stage-large STAGE [--boot 10000] [--seed 20261106]
Scores every target for each model with tempo.holdeval (HOLD-EVAL-v1). Gates: canonical replies score exact and
canonical replay equals the independent reference for every case; prompts identical across models; complete
accounting. Primary (component "primary" only): LARGE - SMALL exact meaning, averaged over the 8 targets (4 acts x 2
histories) within each group, then over the 64 groups; paired group bootstrap within the 8 strata, 10,000 resamples,
seed 20261106 (descriptive; n = 64 groups, conditional on the four authored families)."""
import argparse
import collections
import json
import random
import statistics
from pathlib import Path

from _bootstrap import ROOT  # noqa: F401
from tempo import factored as FA, holdeval as HE, holdout as HO

MODELS = ("SMALL", "LARGE")


def load(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]


def boot(gs, strat, stat, B, seed):
    by = collections.defaultdict(list)
    for g in gs:
        by[strat[g]].append(g)
    rng = random.Random(seed)
    est = sorted(stat([rng.choice(v) for v in by.values() for _ in v]) for _ in range(B))
    return [round(est[int(0.025 * B)], 4), round(est[int(0.975 * B) - 1], 4)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", required=True)
    ap.add_argument("--set", required=True)
    ap.add_argument("--stage-small", required=True)
    ap.add_argument("--stage-large", required=True)
    ap.add_argument("--boot", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=20261106)
    ap.add_argument("--out")
    a = ap.parse_args()
    hub = Path(a.hub)
    data = hub / "data"
    targets = {t["target"]: t for t in load(data / "public" / f"{a.set}-targets.jsonl")}
    cases = {c["target"]: c for c in load(data / "hidden" / f"{a.set}-cases.jsonl")}
    calls = {m: {c["call_id"]: c for c in load(data / f"{a.set}{m}-calls.jsonl")} for m in MODELS}
    stage = {"SMALL": a.stage_small, "LARGE": a.stage_large}
    recs = {}
    for m in MODELS:
        recs[m] = {}
        d = hub / "stages" / stage[m] / "calls"
        if d.exists():
            for p in d.glob("*.json"):
                r = json.loads(p.read_text())
                recs[m][r["call_id"]] = r
    worlds = {}

    def world(c):
        k = (c["world_seed"], c["pool"])
        if k not in worlds:
            worlds[k] = HO._world(c["world_seed"], c["pool"])[0]
        return worlds[k]
    gates, fails = {}, []

    def gate(name, bad, total):
        gates[name] = {"pass": not bad, "failures": len(bad), "checked": total, "examples": [str(b) for b in bad[:8]]}
        if bad:
            fails.append(name)
    bad, canon_loss = [], 0
    for tid, c in cases.items():
        case, w = c["case"], world(c)
        gold = HO.public(case)[-1]
        s, _, _ = HE.score(json.dumps(dict(FA.canonical_factored(gold), evidence=case["text"][-30:])), case, w,
                           targets[tid]["registry"])
        if not s["exact"] or not s["replay_ok"]:
            bad.append((tid, s["exact"], s["replay"], s["replay_ref"]))
        if s["compilation_loss"] != bool(case["finite"]):
            bad.append((tid, "compilation_loss flag", s["compilation_loss"], case["finite"]))
        canon_loss += s["compilation_loss"]
    gate("H1 canonical replies score exact; canonical engine replay equals the independent temporal reference", bad, len(cases))
    bad = [tid for tid in targets if calls["SMALL"][f"{tid}|SMALL"]["user"] != calls["LARGE"][f"{tid}|LARGE"]["user"]]
    bad += [m for m in MODELS if len({c["user"] for c in calls[m].values()}) != len(calls[m])]
    gate("H2 byte-identical prompts across models; unique prompts within each model", bad, len(targets))
    miss = {m: [c for c in calls[m] if c not in recs[m]] for m in MODELS}
    gate("H3 complete accounting (every scheduled call has one stored record)", [x for m in MODELS for x in miss[m]],
         sum(len(calls[m]) for m in MODELS))
    rows = {}
    for tid, c in cases.items():
        case, w = c["case"], world(c)
        for m in MODELS:
            r = recs[m].get(f"{tid}|{m}")
            raw = r["raw"] if r and r.get("status") == "ok" else None
            s, rep, tr = HE.score(raw, case, w, targets[tid]["registry"], None if r is None else r.get("stop"))
            rows[(tid, m)] = dict(s, target=tid, model=m, group=c["group"], component=c["component"], family=c["family"],
                                  reception=c["reception"], stratum=c["stratum"], act=c["act"], history=c["history"],
                                  bits=c["bits"], raw=raw, trace=tr, call_status=None if r is None else r.get("status"),
                                  output_tokens=None if r is None else r.get("output_tokens"),
                                  input_tokens=None if r is None else r.get("input_tokens"),
                                  seconds=None if r is None else r.get("seconds"))
    res = {"set": a.set, "canonical_compilation_loss_targets": canon_loss, "gates": gates, "software_gates_pass": not fails, "failed_gates": fails,
           "completion": {m: {"scheduled": len(calls[m]), "records": len(recs[m]),
                              "ok": sum(r.get("status") == "ok" for r in recs[m].values())} for m in MODELS}}
    T = {}
    for (tid, m), r in rows.items():
        T.setdefault(m, {})[tid] = r

    def gmean(m, g, key="exact", comp=None):
        xs = [r[key] for tid, r in T[m].items() if r["group"] == g]
        return sum(bool(x) for x in xs) / len(xs)
    for comp in ("primary", "calibration", "smoke"):
        G = sorted({r["group"] for r in T["SMALL"].values() if r["component"] == comp})
        if not G:
            continue
        strat = {g: next(r["stratum"] for r in T["SMALL"].values() if r["group"] == g) for g in G}
        d = lambda gs, k="exact": statistics.mean(gmean("LARGE", g, k) - gmean("SMALL", g, k) for g in gs)
        pair = collections.Counter()
        for tid, r in T["SMALL"].items():
            if r["component"] != comp:
                continue
            s_, l_ = r["exact"], T["LARGE"][tid]["exact"]
            pair["both" if s_ and l_ else "LARGE only" if l_ else "SMALL only" if s_ else "neither"] += 1
        block = {"n_groups": len(G), "SMALL": round(statistics.mean(gmean("SMALL", g) for g in G), 4),
                 "LARGE": round(statistics.mean(gmean("LARGE", g) for g in G), 4), "difference": round(d(G), 4),
                 "ci95": boot(G, strat, d, a.boot, a.seed) if comp == "primary" else None, "paired_targets": dict(pair),
                 "metric": "exact_extraction (reduced claims incl. valid_to); see end_to_end below"}
        block["end_to_end"] = {"SMALL": round(statistics.mean(gmean("SMALL", g, "exact_end_to_end") for g in G), 4),
                               "LARGE": round(statistics.mean(gmean("LARGE", g, "exact_end_to_end") for g in G), 4),
                               "difference": round(d(G, "exact_end_to_end"), 4),
                               "ci95": boot(G, strat, lambda gs: d(gs, "exact_end_to_end"), a.boot, a.seed) if comp == "primary" else None,
                               "note": "finite corrections cannot be exact end to end under contract v1 (amendment 01, proposed)"}
        nonfinite = lambda m, g: [r for r in T[m].values() if r["group"] == g and not (r["act"] == "correction" and r["bits"][2])]
        dn = lambda gs: statistics.mean(statistics.mean(r["exact"] for r in nonfinite("LARGE", g)) -
                                        statistics.mean(r["exact"] for r in nonfinite("SMALL", g)) for g in gs)
        block["excluding_finite_corrections"] = {"difference": round(dn(G), 4),
                                                 "ci95": boot(G, strat, dn, a.boot, a.seed) if comp == "primary" else None,
                                                 "note": "option (a)-style scope, reported only as a sensitivity view until amendment 01 is settled"}
        per = {}
        for key, vals in (("act", HO.ACTS), ("family", sorted({r["family"] for r in T["SMALL"].values() if r["component"] == comp})),
                          ("reception", HO.RECEPTION)):
            for v in vals:
                rs = {m: [r for r in T[m].values() if r["component"] == comp and r[key] == v] for m in MODELS}
                per[f"{key}={v}"] = {m: f"{sum(r['exact'] for r in rs[m])}/{len(rs[m])}" for m in MODELS}
        block["by"] = per
        both = {}
        for m in MODELS:
            ok = collections.Counter()
            for g in G:
                for act in HO.ACTS:
                    rs = [r for r in T[m].values() if r["group"] == g and r["act"] == act]
                    ok[act] += all(r["exact"] for r in rs)
            both[m] = dict(ok)
        block["both_histories_exact_by_act"] = both
        diag = {}
        for m in MODELS:
            rs = [r for r in T[m].values() if r["component"] == comp]
            cnt = lambda k: sum(bool(r.get(k)) for r in rs)
            ev = [r for r in rs if r["act"] in ("arrival", "removal")]
            cr = [r for r in rs if r["act"] == "correction"]
            diag[m] = {"exact": cnt("exact"), "exact_end_to_end": cnt("exact_end_to_end"), "compilation_loss": cnt("compilation_loss"), "n": len(rs), "compiled": cnt("compiled"), "accepted": cnt("accepted"),
                       "pending": dict(collections.Counter(str(r["pending_code"]) for r in rs if not r["compiled"])),
                       "contract_rejections": dict(collections.Counter(str(r["contract_code"]) for r in rs if r["compiled"] and not r["accepted"])),
                       "bound_ok_raw": cnt("bound_ok_raw"), "bound_ok_accepted": cnt("bound_ok_accepted"),
                       "other_field_raw": cnt("other_field_raw"), "slot_field_claimed": cnt("slot_field_claimed"),
                       "false_revision_raw": cnt("false_revision_raw"),
                       "false_revision_mixed_or_rejected": sum(r["false_revision_raw"] and not r["false_revision_accepted"] for r in rs),
                       "false_revision_compiled": cnt("false_revision_compiled"), "false_revision_accepted": cnt("false_revision_accepted"),
                       "event_omitted": sum(not r.get("event_on_X") for r in ev), "state_only_event_accepted": cnt("state_only_event_accepted"),
                       "endpoint_ok_not_exact": sum(r["endpoint_ok"] and not r["exact"] for r in rs),
                       "rev_target_ok": sum(bool(r.get("rev_target_ok")) for r in cr), "rev_from_ok": sum(bool(r.get("rev_from_ok")) for r in cr),
                       "rev_to_ok": sum(bool(r.get("rev_to_ok")) for r in cr),
                       "rev_to_ok_finite": sum(bool(r.get("rev_to_ok")) for r in cr if r["bits"][2]),
                       "prior_ok": sum(bool(r.get("prior_ok")) for r in ev), "prior_stated_n": sum(r["bits"][1] for r in ev),
                       "prior_ok_when_stated": sum(bool(r.get("prior_ok")) for r in ev if r["bits"][1]),
                       "event_time_ok": sum(bool(r.get("event_time_ok")) for r in ev), "reception_ok": cnt("reception_ok"),
                       "quote_valid": cnt("quote_valid"), "replay_ok": cnt("replay_ok"),
                       "truncated": cnt("truncated"), "output_tokens": sum(r["output_tokens"] or 0 for r in rs),
                       "generation_s": round(sum(r["seconds"] or 0 for r in rs), 1),
                       "max_input_tokens": max([r["input_tokens"] or 0 for r in rs] or [0])}
        block["diagnostics"] = diag
        block["disagreements"] = [{"target": tid, "SMALL": r["exact"], "LARGE": T["LARGE"][tid]["exact"],
                                   "SMALL_raw": (r["raw"] or "")[:300], "LARGE_raw": (T["LARGE"][tid]["raw"] or "")[:300]}
                                  for tid, r in T["SMALL"].items() if r["component"] == comp and r["exact"] != T["LARGE"][tid]["exact"]]
        res[comp] = block
    if "calibration" in res and "primary" in res:
        res["holdout_minus_calibration"] = {m: round(res["primary"][m] - res["calibration"][m], 4) for m in MODELS}
    for m in MODELS:
        p = hub / "stages" / stage[m] / "LOAD.json"
        e = hub / "stages" / stage[m] / "END.json"
        res.setdefault("runtime", {})[m] = {"load": json.loads(p.read_text()).get("load") if p.exists() else None,
                                            "end": json.loads(e.read_text()) if e.exists() else None}
    out = Path(a.out) if a.out else hub / "analysis" / a.set
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "scored.jsonl", "w") as fh:
        for r in rows.values():
            fh.write(json.dumps(r, default=str, sort_keys=True) + "\n")
    (out / "ANALYSIS.json").write_text(json.dumps(res, indent=1, default=str) + "\n")
    print(json.dumps({"software_gates_pass": res["software_gates_pass"], "failed": fails, "completion": res["completion"],
                      **({"primary": {k: res["primary"][k] for k in ("SMALL", "LARGE", "difference", "ci95")}} if "primary" in res else {})}))


if __name__ == "__main__":
    main()
