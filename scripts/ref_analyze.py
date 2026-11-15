"""V1.20.0 three-arm scoring and analysis (no model).
Usage: ref_analyze.py --hub HUB --set SET --stage-a STAGE --stage-b STAGE [--boot 10000] [--seed 20261106] [--out DIR]
Arms per target: BASE (stage-A BASE reply); RES-DET (stage-A DET reply if RES-DET resolved; pending if it refused;
BASE if bypass); RES-MODEL (stage-B MODEL reply, or the DET reply when the stage-B ledger records a byte-identical
prompt, or BASE if bypass; pending if the resolver was unresolved/invalid). Every output is scored with HOLD-EVAL-v1
(tempo.holdeval.score, unchanged) against the ORIGINAL target and prefix; pending = incorrect.
Gates: R1 canonical FACT-v1 replies exact, zero canonical compilation loss and canonical replay = independent
reference for every primary target; R2 RES-DET equals the hidden gold binding on every primary target, refuses every
refusal control with its declared reason, bypasses every explicit control (independent construction labels, not an
echo); R3 rewrite fidelity (only the detected span changes; the DET prompt differs from BASE only inside the target
line); R4 public-only recomputation of detection and RES-DET equals the stored values; R5 accounting.
Primary: RES-MODEL - BASE exact, 8 targets per group averaged, 48 groups, paired bootstrap within the 8 strata,
10,000 resamples, seed 20261106 (descriptive)."""
import argparse
import collections
import json
import random
import statistics
from pathlib import Path

from _bootstrap import ROOT  # noqa: F401
from tempo import factored as FA, holdeval as HE, holdout as HO, refgen as RG, refres as RR  # noqa: F401 (refgen registers pools)

ARMS = ("BASE", "RES_DET", "RES_MODEL")


def load(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]


def boot(gs, strat, stat, B, seed):
    by = collections.defaultdict(list)
    for g in gs:
        by[strat[g]].append(g)
    rng = random.Random(seed)
    est = sorted(stat([rng.choice(v) for v in by.values() for _ in v]) for _ in range(B))
    return [round(est[int(0.025 * B)], 4), round(est[int(0.975 * B) - 1], 4)]


def evidence(raw):
    from tempo import score as S
    if raw is None:
        return None
    o, e = S.parse_object(raw)
    return o.get("evidence") if e is None and isinstance(o, dict) else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", required=True)
    ap.add_argument("--set", required=True)
    ap.add_argument("--stage-a", required=True)
    ap.add_argument("--stage-b", required=True)
    ap.add_argument("--boot", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=20261106)
    ap.add_argument("--out")
    a = ap.parse_args()
    hub, data = Path(a.hub), Path(a.hub) / "data"
    T = {t["target"]: t for t in load(data / "public" / f"{a.set}-targets.jsonl")}
    H = {h["target"]: h for h in load(data / "hidden" / f"{a.set}-cases.jsonl")}
    callsA = {c["call_id"]: c for c in load(data / f"{a.set}A-calls.jsonl")}
    pb, pl = data / f"{a.set}B-calls.jsonl", data / f"{a.set}-stageB-ledger.jsonl"
    stageb_present = pb.exists() and pl.exists() and (data / f"COMMITMENT-{a.set}B.json").exists()
    callsB = {c["call_id"]: c for c in load(pb)} if pb.exists() else {}
    led = {r["target"]: r for r in load(pl)} if pl.exists() else {}
    recs = {}
    for st in (a.stage_a, a.stage_b):
        d = hub / "stages" / st / "calls"
        if d.exists():
            for p in d.glob("*.json"):
                r = json.loads(p.read_text())
                recs[r["call_id"]] = r
    worlds = {}

    def world(h):
        k = (h["world_seed"], h["pool"])
        if k not in worlds:
            worlds[k] = HO._world(*k)[0]
        return worlds[k]
    gates, fails = {}, []

    def gate(name, bad, total):
        gates[name] = {"pass": not bad, "failures": len(bad), "checked": total, "examples": [str(b) for b in bad[:8]]}
        if bad:
            fails.append(name)
    bad = []
    for tid, h in H.items():
        if h["component"] != "primary":
            continue
        case, w = h["case"], world(h)
        s, _, _ = HE.score(json.dumps(dict(FA.canonical_factored(HO.public(case)[-1]), evidence=case["text"][-25:])),
                           case, w, T[tid]["registry"])
        if not (s["exact"] and not s["compilation_loss"] and s["replay_ok"]):
            bad.append((tid, s["exact"], s["compilation_loss"], s["replay_ok"]))
    gate("R1 canonical replies exact, zero canonical compilation loss, canonical replay = independent reference (primary)",
         bad, sum(h["component"] == "primary" for h in H.values()))
    bad = []
    for tid, h in H.items():
        t = T[tid]
        if h["component"] == "primary":
            if t["detection"]["route"] != "resolve" or t.get("det", {}).get("field") != h["gold_field"]:
                bad.append(("det_vs_gold", tid))
        elif h["component"] == "control_refusal":
            if t["detection"]["route"] != "resolve" or t.get("det", {}).get("field") is not None or \
                    t["det"]["reason"] != h["expected_refusal"]:
                bad.append(("refusal", tid, t.get("det")))
        elif t["detection"]["route"] != "bypass":
            bad.append(("bypass", tid))
    gate("R2 RES-DET = hidden gold binding (primary); declared refusals; explicit bypass (independent construction labels)",
         bad, len(H))
    bad = []
    for tid, t in T.items():
        if t.get("det_prompt"):
            s, e = t["detection"]["span"]
            nt = t["target_text"][:s] + t["det_ledger"]["replacement"] + t["target_text"][e:]
            if t["det_prompt"] != t["base_prompt"].replace(t["target_text"], nt) or t["base_prompt"].count(t["target_text"]) != 1:
                bad.append(tid)
    gate("R3 rewrite fidelity: only the detected noun phrase changes; DET prompt = BASE prompt with only the target line rewritten",
         bad, sum(bool(t.get("det_prompt")) for t in T.values()))
    bad = []
    for tid, t in T.items():
        pi = RR.PublicInput.make(t["prefix"], t["target_text"], t["registry_order"])
        d = RR.detect(t["target_text"])
        if d != t["detection"]:
            bad.append(("detect", tid))
        elif d["route"] == "resolve" and RR.resolve_det(pi, d) != t["det"]:
            bad.append(("det", tid))
        elif d["route"] == "resolve" and RR.resolver_prompt(pi, d) != t["resolver_prompt"]:
            bad.append(("resolver_prompt", tid))
    gate("R4 public-only recomputation of detection, RES-DET and the resolver prompt equals the stored values (no hidden input)", bad, len(T))
    bad = [] if stageb_present else ["stage-B files missing"]
    import hashlib as _h
    for tid, t in T.items():
        L = led.get(tid)
        route = t["detection"]["route"]
        if L is None:
            bad.append(("no_ledger_row", tid)); continue
        if route == "bypass" and L.get("model") != "use_BASE":
            bad.append(("bypass_route", tid))
        elif route == "pending" and L.get("model") != "pending":
            bad.append(("pending_route", tid))
        elif route == "resolve":
            rc = recs.get(f"{tid}|RESOLVER")
            if rc is None or rc.get("status") != "ok":
                if L.get("model") != "incomplete":
                    bad.append(("resolver_infra_not_incomplete", tid))
                continue
            pr = RR.parse_resolver(rc["raw"], RR.PublicInput.make(t["prefix"], t["target_text"], t["registry_order"]))
            if rc.get("stop") == "length" and pr["status"] == "resolved":
                pr = {"status": "invalid"}
            if pr["status"] != "resolved":
                if L.get("model") != "pending":
                    bad.append(("resolver_pending_route", tid))
                continue
            nt, _ = RR.rewrite(t["target_text"], t["detection"], pr["field"])
            prompt = RR.rewrite_prompt(t["base_prompt"], t["target_text"], nt)
            if L.get("model") == "use_DET_cache":
                if prompt != t.get("det_prompt"):
                    bad.append(("cache_mismatch", tid))
            elif L.get("model") == "call":
                c = callsB.get(f"{tid}|MODEL")
                if c is None or c["user"] != prompt:
                    bad.append(("scheduled_prompt_mismatch", tid))
            else:
                bad.append(("resolved_without_route", tid))
    if set(callsB) != {f"{t}|MODEL" for t, L in led.items() if L.get("model") == "call"}:
        bad.append(("stageB_calls_vs_ledger",))
    gate("R5 stage-B ledger complete and consistent: a row per target, routes re-derived from public rules and stage-A "
         "records, scheduled prompts and cache matches exact", bad, len(T))
    sched = list(callsA) + list(callsB)
    inc = [(c, None if c not in recs else recs[c].get("status")) for c in sched if c not in recs or recs[c].get("status") != "ok"]
    inc += [("ledger_incomplete", t) for t, L in led.items() if L.get("model") == "incomplete"]
    gate("R6 completion: every scheduled stage-A/B call has a final record with status ok (missing, infra_failed or "
         "input_too_long = incomplete run, not a semantic error)", inc, len(sched))
    rows = {}
    for tid, h in H.items():
        t, case, w = T[tid], h["case"], world(h)
        reg = t["registry"]
        L = led.get(tid, {})
        outs = {}
        base = recs.get(f"{tid}|BASE")
        outs["BASE"] = ("call", base, t["base_prompt"])
        route = t["detection"]["route"]
        if route == "bypass":
            outs["RES_DET"] = outs["RES_MODEL"] = ("use_BASE", base, t["base_prompt"])
        elif route != "resolve":
            outs["RES_DET"] = outs["RES_MODEL"] = ("pending", None, None)
        else:
            outs["RES_DET"] = ("call", recs.get(f"{tid}|DET"), t["det_prompt"]) if t.get("det_prompt") else ("pending", None, None)
            m = L.get("model")
            if m == "call":
                outs["RES_MODEL"] = ("call", recs.get(f"{tid}|MODEL"), callsB[f"{tid}|MODEL"]["user"])
            elif m == "use_DET_cache":
                outs["RES_MODEL"] = ("use_DET_cache", recs.get(f"{tid}|DET"), t["det_prompt"])
            else:
                outs["RES_MODEL"] = ("pending", None, None)
        for arm, (src, r, prompt) in outs.items():
            if src == "pending":
                s = {"exact": False if h["component"] != "control_refusal" else None, "pending_pipeline": True,
                     "compiled": False, "accepted": False}
                raw = None
            elif h["component"] == "control_refusal":
                # structural-only: no unique source meaning exists; the scaffold serves only the evidence engine spec
                raw = r["raw"] if r and r.get("status") == "ok" else None
                rep, tr = FA.compile_reply(raw, reg)
                recs_c = [{k: x[k] for k in ("rid", "kind", "status", "event_at", "received_at", "payload")} for x in case["records"]]
                _, acc, ccode = HE.engine_for(w, recs_c[:-1], rep, recs_c[-1], "ctl")
                s = {"exact": None, "exact_NA": "no unique source meaning", "pending_pipeline": False,
                     "compiled": rep is not None, "accepted": acc, "contract_code": ccode, "pending_code": tr["code"],
                     "category": None if rep is None else rep["type"]}
            else:
                raw = r["raw"] if r and r.get("status") == "ok" else None
                s, rep, tr = HE.score(raw, case, w, reg, None if r is None else r.get("stop"))
                s = {k: v for k, v in s.items() if k not in ("replay", "replay_ref")} | {"replay_ok": s["replay_ok"]}
                s["pending_pipeline"] = False
                shown = prompt.split("New record to convert:\n")[1].split("\n")[0] if prompt else ""
                ev = evidence(raw)
                s["quote_valid_shown"] = isinstance(ev, str) and bool(ev) and ev in shown
                s["quote_contains_rewrite"] = RR.quote_contains_replacement(
                    ev, RR.ledger_for_arm(arm, src, t.get("det_ledger"), L.get("ledger")))
                s["wrong_field_competitor"] = bool(s.get("accepted")) and not s.get("bound_ok_accepted") and case.get("other") is not None \
                    and rep is not None and any(x.get("field") == f"{case['other']}.on_hand" for x in rep["assertions"])
                s["extra_states_on_correction"] = case["records"][-1]["kind"] == "correction" and bool(tr.get("reduced")) and \
                    bool(tr["reduced"]["states"]) and bool(tr["reduced"]["revisions"])
            rows[(tid, arm)] = dict(s, target=tid, arm=arm, source=src, component=h["component"], group=h["group"],
                                    family=h["family"], reception=h.get("reception"), act=h["act"], history=h["history"],
                                    stratum=T[tid].get("stratum"), raw=raw,
                                    output_tokens=None if not r else r.get("output_tokens"),
                                    seconds=None if not r else r.get("seconds"))
    res = {"set": a.set, "gates": gates, "software_gates_pass": not [f for f in fails if not f.startswith("R6")],
           "complete": "R6 completion: every scheduled stage-A/B call has a final record with status ok (missing, infra_failed or input_too_long = incomplete run, not a semantic error)" not in fails,
           "failed_gates": fails}
    prim = sorted({h["group"] for h in H.values() if h["component"] == "primary"})
    strat = {g: next(T[t]["stratum"] for t, h in H.items() if h["group"] == g) for g in prim}
    tg = collections.defaultdict(list)
    for tid, h in H.items():
        if h["component"] == "primary":
            tg[h["group"]].append(tid)
    gm = lambda arm, g, k="exact": statistics.mean(bool(rows[(t, arm)].get(k)) for t in tg[g])
    diff = lambda A, B: (lambda gs: statistics.mean(gm(A, g) - gm(B, g) for g in gs))
    res["primary"] = {"metric": "exact original-source meaning (HOLD-EVAL-v1), RES_MODEL - BASE", "n_groups": len(prim),
                      **{arm: round(statistics.mean(gm(arm, g) for g in prim), 4) for arm in ARMS},
                      "difference": round(diff("RES_MODEL", "BASE")(prim), 4),
                      "ci95": boot(prim, strat, diff("RES_MODEL", "BASE"), a.boot, a.seed)}
    pc = collections.Counter()
    for g in prim:
        for t in tg[g]:
            b, m = rows[(t, "BASE")]["exact"], rows[(t, "RES_MODEL")]["exact"]
            pc["both" if b and m else "RES_MODEL only" if m else "BASE only" if b else "neither"] += 1
    res["primary"]["paired_targets"] = dict(pc)
    res["diagnostic_RES_DET_minus_BASE"] = {"difference": round(diff("RES_DET", "BASE")(prim), 4),
                                            "ci95": boot(prim, strat, diff("RES_DET", "BASE"), a.boot, a.seed)}
    res["diagnostic_RES_MODEL_minus_RES_DET"] = {"difference": round(diff("RES_MODEL", "RES_DET")(prim), 4),
                                                 "ci95": boot(prim, strat, diff("RES_MODEL", "RES_DET"), a.boot, a.seed)}
    by = {}
    P = lambda arm: [rows[(t, arm)] for t in sorted(tid for tid, h in H.items() if h["component"] == "primary")]
    for key, vals in (("act", HO.ACTS), ("family", sorted({h["family"] for h in H.values() if h["component"] == "primary"})),
                      ("reception", HO.RECEPTION)):
        for v in vals:
            by[f"{key}={v}"] = {arm: f"{sum(r['exact'] for r in P(arm) if r[key] == v)}/{sum(r[key] == v for r in P(arm))}" for arm in ARMS}
    res["by"] = by
    res["both_histories_exact_by_act"] = {arm: {act: sum(all(rows[(t, arm)]["exact"] for t in tg[g] if rows[(t, arm)]["act"] == act)
                                                         for g in prim) for act in HO.ACTS} for arm in ARMS}
    diag = {}
    for arm in ARMS:
        rs = P(arm)
        acc = [r for r in rs if r.get("accepted")]
        wrongb = [r for r in acc if not r.get("bound_ok_accepted")]
        err = [r for r in rs if not r["exact"]]
        diag[arm] = {"n": len(rs), "exact": sum(r["exact"] for r in rs), "pipeline_pending": sum(r["pending_pipeline"] for r in rs),
                     "compiled": sum(bool(r.get("compiled")) for r in rs), "accepted": len(acc),
                     "accepted_wrong_binding": f"{len(wrongb)}/{len(rs)} targets; {len(wrongb)}/{len(acc)} accepted",
                     "accepted_wrong_binding_competitor": sum(r.get("wrong_field_competitor", False) for r in rs),
                     "accepted_but_inexact": sum(1 for r in acc if not r["exact"]),
                     "errors_accepted_fraction": f"{sum(1 for r in err if r.get('accepted'))}/{len(err)}",
                     "event_omitted": sum(1 for r in rs if r["act"] in ("arrival", "removal") and not r["pending_pipeline"] and not r.get("event_on_X")),
                     "state_only_event_accepted": sum(bool(r.get("state_only_event_accepted")) for r in rs),
                     "extra_states_on_correction": sum(bool(r.get("extra_states_on_correction")) for r in rs),
                     "false_revision_raw": sum(bool(r.get("false_revision_raw")) for r in rs),
                     "false_revision_accepted": sum(bool(r.get("false_revision_accepted")) for r in rs),
                     "compilation_loss": sum(bool(r.get("compilation_loss")) for r in rs),
                     "replay_ok": sum(bool(r.get("replay_ok")) for r in rs),
                     "quote_valid_shown": sum(bool(r.get("quote_valid_shown")) for r in rs),
                     "quote_contains_rewrite": sum(bool(r.get("quote_contains_rewrite")) for r in rs),
                     "truncated": sum(bool(r.get("truncated")) for r in rs)}
    res["diagnostics"] = diag
    rv = collections.Counter()
    joint = 0
    cites = collections.Counter()
    for tid, h in H.items():
        if h["component"] != "primary":
            continue
        L = led.get(tid, {})
        pr = L.get("resolver", {})
        st = pr.get("status")
        k = "correct" if st == "resolved" and pr["field"] == h["gold_field"] else "wrong" if st == "resolved" else st or "no_ledger"
        rv[k] += 1
        if st == "resolved":
            det_t = T[tid]["det"]["trace"]
            kd, ar = det_t["kind"], det_t["args"]
            if kd in ("one_hop", "slot_join"):
                req = {ar[0]}
            elif kd == "two_hop":
                req = {ar[0], det_t.get("link_ref")}
            elif kd == "historical":
                req = {det_t.get("decisive")}
            else:
                req = {ar[0], ar[1]}
            got = set(pr.get("records") or [])
            cites["covers_minimum_support" if req <= got else "misses_minimum_support"] += 1
            cites["extra_ids_total"] += len(got - req)
        joint += k == "correct" and rows[(tid, "RES_MODEL")]["exact"]
        if k == "wrong":
            rv["wrong_but_final_exact"] += rows[(tid, "RES_MODEL")]["exact"]
    res["resolver"] = {"primary": dict(rv), "joint_correct_resolution_and_exact": joint, "support_ids": dict(cites),
                       "support_ids_note": "independent minimum support per construction (one-hop rK; two-hop link and antecedent; slot-join rK; historical: the decisive occupancy record; measure: both checks); citation coverage is not proof of use",
                       "invalid_or_unresolved_reasons": dict(collections.Counter(led[t].get("reason") for t in led if led[t].get("model") == "pending" and H[t]["component"] == "primary"))}
    res["stageB_routes"] = dict(collections.Counter(r.get("model") for r in led.values()))
    ctl = {}
    for comp in ("control_refusal", "control_bare_correction", "control_explicit"):
        ts = [t for t, h in H.items() if h["component"] == comp]
        if not ts:
            continue
        c = {"n": len(ts)}
        if comp == "control_refusal":
            c["resolver"] = dict(collections.Counter((led.get(t, {}).get("resolver") or {}).get("status") for t in ts))
            c["resolver_guessed_field"] = sum((led.get(t, {}).get("resolver") or {}).get("status") == "resolved" for t in ts)
            c["RES_MODEL_extraction_accepted"] = sum(bool(rows[(t, "RES_MODEL")].get("accepted")) for t in ts)
            c["RES_DET_refused"] = sum(rows[(t, "RES_DET")]["pending_pipeline"] for t in ts)
            c["BASE_accepted"] = sum(bool(rows[(t, "BASE")].get("accepted")) for t in ts)
            c["by_type"] = {k: dict(collections.Counter((led.get(t, {}).get("resolver") or {}).get("status") for t in ts if H[t]["family"] == k))
                            for k in sorted({H[t]["family"] for t in ts})}
        else:
            c["bypass_all"] = all(T[t]["detection"]["route"] == "bypass" for t in ts)
            c["BASE_exact"] = sum(rows[(t, "BASE")]["exact"] for t in ts)
            c["arms_identical_source"] = all(rows[(t, "RES_MODEL")]["source"] == "use_BASE" for t in ts)
        ctl[comp] = c
    res["controls"] = ctl
    cost = collections.defaultdict(lambda: collections.Counter())
    for cid, r in recs.items():
        kind = cid.rsplit("|", 1)[1]
        cost[kind]["calls"] += 1
        cost[kind]["output_tokens"] += r.get("output_tokens") or 0
        cost[kind]["seconds"] += round(r.get("seconds") or 0, 1)
        cost[kind]["truncated"] += r.get("stop") == "length"
    res["cost"] = {k: dict(v) for k, v in cost.items()}
    res["calls"] = {"scheduled_A": len(callsA), "scheduled_B": len(callsB), "recorded": len(recs),
                    "cache_reuses_DET_for_MODEL": res["stageB_routes"].get("use_DET_cache", 0)}
    res["disagreements_BASE_vs_MODEL"] = [{"target": t, "BASE": rows[(t, "BASE")]["exact"], "RES_MODEL": rows[(t, "RES_MODEL")]["exact"],
                                           "MODEL_source": rows[(t, "RES_MODEL")]["source"]}
                                          for t in sorted(tid for tid, h in H.items() if h["component"] == "primary")
                                          if rows[(t, "BASE")]["exact"] != rows[(t, "RES_MODEL")]["exact"]]
    out = Path(a.out) if a.out else hub / "analysis" / a.set
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "scored.jsonl", "w") as fh:
        for r in rows.values():
            fh.write(json.dumps(r, default=str, sort_keys=True) + "\n")
    (out / "ANALYSIS.json").write_text(json.dumps(res, indent=1, default=str) + "\n")
    print(json.dumps({"software_gates_pass": res["software_gates_pass"], "failed": fails, "calls": res["calls"],
                      "primary": {k: res["primary"][k] for k in ("BASE", "RES_DET", "RES_MODEL", "difference", "ci95")}}))


if __name__ == "__main__":
    main()
