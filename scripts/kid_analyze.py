"""V1.21.0 KEEP+ID development analysis (no model).
Usage: kid_analyze.py --hub HUB --src-hub HUB_1_20 [--stages smoke main] [--boot 10000] [--seed 20261110]
Arms on the 192 primary arrival/correction targets of the 1.20 panel:
  BASE  1.20 main-A BASE reply (cached; reference comparison, no identity annotation)
  SUB   1.20 main-A DET reply (cached; RES-DET rewrite = verified identity substituted into the sentence)
  KEEP  new KEEP+ID reply (original sentence + one identity annotation line)
Every reply is scored with HOLD-EVAL-v1 (tempo.holdeval.score, unchanged) against the ORIGINAL target and prefix.
A KEEP call without an ok record is incomplete and counted as an error in every table that includes it, with the
number reported (no imputation).
Masks: MAIN = F1/F2/F3 (32 groups, 128 targets); F4 = 16 groups, 64 targets (separate; not pooled with MAIN).
Focal: MAIN arrival exactness KEEP - SUB. Group = construction group; its two histories (A/B) stay together. Group
statistic = mean over the group's targets in the mask; difference of group means averaged over groups; 95% interval
from a stratified (family x reception) group bootstrap, 10,000 resamples, seed 20261110. Development, descriptive.
Declared secondary counts (all arms): accepted wrong binding, accepted state-only arrival, mixed correction (reduced
claims carry both states and revisions on a correction target), value contradiction (internal: two claims on the
same field with different values; gold: a claim on the gold field whose value differs from the gold value),
rejection (not accepted; compile pending code or contract code), event omitted (arrival without an event on X),
truncation, tokens and seconds."""
import argparse
import collections
import json
import random
import statistics
from pathlib import Path

from _bootstrap import ROOT  # noqa: F401
from tempo import factored as FA, holdeval as HE, holdout as HO, refgen as RG  # noqa: F401

ARMS = ("BASE", "SUB", "KEEP")
PROBES = [  # the 19 correct-resolution regression probes (1.20 BREAKDOWN.md, corrected classification)
    ("g002|arrival|A", "state_only"), ("g002|arrival|B", "state_only"), ("g003|arrival|A", "state_only"),
    ("g003|arrival|B", "state_only"), ("g009|arrival|A", "state_only"), ("g010|arrival|A", "state_only"),
    ("g010|arrival|B", "state_only"), ("g011|arrival|A", "state_only"), ("g011|arrival|B", "state_only"),
    ("g012|arrival|B", "rejected_mixed_acts"), ("g036|arrival|B", "state_only"), ("g041|arrival|A", "state_only"),
    ("g041|arrival|B", "state_only"), ("g042|arrival|A", "state_only"), ("g042|arrival|B", "state_only"),
    ("g005|correction|A", "mixed_no_state_yes_revision"), ("g018|correction|A", "mixed_no_state_yes_revision"),
    ("g030|correction|A", "mixed_no_state_yes_revision"), ("g044|correction|A", "mixed_no_state_yes_revision")]


def load(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]


def boot(gs, strat, stat, B, seed):
    by = collections.defaultdict(list)
    for g in gs:
        by[strat[g]].append(g)
    rng = random.Random(seed)
    est = sorted(stat([rng.choice(v) for v in by.values() for _ in v]) for _ in range(B))
    return [round(est[int(0.025 * B)], 4), round(est[int(0.975 * B) - 1], 4)]


def val(x):
    return x.get("value", x.get("to"))


def outcome(r):
    """Short descriptive label of one scored row (for probe tables)."""
    if r.get("incomplete"):
        return "incomplete (no ok record)"
    if r["exact"]:
        return "exact"
    if not r.get("accepted"):
        code = r.get('contract_code') or r.get('pending_code')
        if r.get("mixed_correction"):
            return f"rejected mixed state/revision ({code})" + (" with value conflict" if r.get("value_conflict_internal") else "")
        if r.get("event_on_X") and r.get("raw_states"):
            return f"rejected event + extra state ({code})"
        return f"rejected ({code})"
    if not r.get("bound_ok_accepted"):
        return "accepted wrong binding" + (" (state-only)" if r.get("state_only_event_accepted") else "")
    if r.get("state_only_event_accepted"):
        return "accepted state-only"
    if r.get("mixed_correction"):
        return "mixed state/revision"
    return "accepted other inexact"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", required=True)
    ap.add_argument("--src-hub", required=True)
    ap.add_argument("--stages", nargs="+", default=["smoke", "main"])
    ap.add_argument("--boot", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=20261110)
    a = ap.parse_args()
    hub, src = Path(a.hub), Path(a.src_hub)
    data = hub / "data"
    T = {t["target"]: t for t in load(data / "inputs" / "ref-targets.jsonl")}
    H = {h["target"]: h for h in load(data / "inputs" / "ref-cases.jsonl")}
    led = {r["target"]: r for r in load(data / "kid-ledger.jsonl")}
    cmap = {r["target"]: r for r in load(data / "CACHE-MAP.jsonl")}
    calls = load(data / "kid-calls.jsonl")
    recs = {}
    for st in a.stages:
        d = hub / "stages" / st / "calls"
        for p in sorted(d.glob("*.json")) if d.exists() else []:
            r = json.loads(p.read_text())
            if r["call_id"] in recs:
                raise SystemExit(f"duplicate record {r['call_id']}")
            recs[r["call_id"]] = dict(r, _stage=st)
    attempts_logged = sum(len(load(hub / "stages" / st / "attempts.jsonl")) for st in a.stages
                          if (hub / "stages" / st / "attempts.jsonl").exists())
    callmap = {c["call_id"]: c for c in calls}
    worlds = {}

    def world(h):
        k = (h["world_seed"], h["pool"])
        if k not in worlds:
            worlds[k] = HO._world(*k)[0]
        return worlds[k]
    rows = {}
    for tid in led:
        h, t = H[tid], T[tid]
        case, w, reg = h["case"], world(h), t["registry"]
        gold = case["records"][-1]
        gv = gold["payload"].get("to", gold["payload"].get("value"))
        for arm in ARMS:
            if arm == "KEEP":
                r = recs.get(f"{tid}|KEEP")
                if r is not None and r["user_sha256"] != callmap[f"{tid}|KEEP"]["user_sha256"]:
                    raise SystemExit(f"{tid}: KEEP record does not match its scheduled prompt")
                src_rec = "new"
            else:
                m = cmap[tid][arm]
                r = json.loads((src / m["record"]).read_text())
                if r["user_sha256"] != m["user_sha256"]:
                    raise SystemExit(f"{tid}: cached {arm} record changed")
                src_rec = "cache_1.20:" + m["call_id"]
            ok = r is not None and r.get("status") == "ok"
            raw = r["raw"] if ok else None
            s, rep, tr = HE.score(raw, case, w, reg, None if r is None else r.get("stop"))
            s = {k: v for k, v in s.items() if k not in ("replay", "replay_ref")}
            claims, red = tr.get("claims"), tr.get("reduced")
            byf = collections.defaultdict(set)
            for k in FA.LISTS:
                for x in (claims or {}).get(k, []):
                    if val(x) is not None:
                        byf[x.get("field")].add(val(x))
            s.update(incomplete=not ok, source=src_rec,
                     mixed_correction=gold["kind"] == "correction" and bool(red) and bool(red["states"]) and bool(red["revisions"]),
                     value_conflict_internal=any(len(v) > 1 for v in byf.values()),
                     value_contradicts_gold=any(v != gv for v in byf.get(case["field"], set())),
                     rejected=not s.get("accepted"),
                     event_omitted=gold["kind"] == "change" and not s.get("event_on_X"),
                     raw=raw, input_tokens=None if r is None else r.get("input_tokens"),
                     output_tokens=None if r is None else r.get("output_tokens"),
                     seconds=None if r is None else r.get("seconds"), stage=None if r is None else r.get("_stage"),
                     claims_summary=None if not claims else {k: [(x.get("field"), x.get("at"), x.get("from"), val(x)) if k == "events"
                                                                  else (x.get("field"), x.get("at") or x.get("valid_from"), val(x))
                                                                  for x in claims[k]] for k in FA.LISTS})
            rows[(tid, arm)] = dict(s, target=tid, arm=arm, group=h["group"], family=h["family"][:2], act=h["act"],
                                    history=h["history"], reception=h["reception"], stratum=T[tid]["stratum"])
    res = {"note": "Development screen on inspected 1.20 data; not confirmation. KEEP+ID vs SUB compares representation "
                   "packages (wording, length and annotation presentation differ).",
           "records": {"KEEP_scheduled": len(calls), "KEEP_ok": sum(1 for c in calls if recs.get(c["call_id"], {}).get("status") == "ok"),
                       "KEEP_records": len(recs), "KEEP_not_ok": sorted(c["call_id"] for c in calls if recs.get(c["call_id"], {}).get("status") != "ok"),
                       "attempts_logged": attempts_logged,
                       "by_stage": dict(collections.Counter(r["_stage"] for r in recs.values()))}}
    masks = {"MAIN": lambda r: r["family"] in ("F1", "F2", "F3"), "F4": lambda r: r["family"] == "F4"}
    sel = lambda arm, m, act=None: [r for (t, ar), r in sorted(rows.items()) if ar == arm and masks[m](r) and (act is None or r["act"] == act)]
    for m in masks:
        out = {}
        groups = sorted({r["group"] for r in sel("KEEP", m)})
        strat = {g: next(r["stratum"] for r in sel("KEEP", m) if r["group"] == g) for g in groups}
        for act in ("arrival", "correction", None):
            key = act or "both_acts"
            gm = lambda arm, g: statistics.mean(bool(r["exact"]) for r in sel(arm, m, act) if r["group"] == g)
            blk = {"n_targets": len(sel("KEEP", m, act)), "n_groups": len(groups),
                   "exact": {arm: sum(r["exact"] for r in sel(arm, m, act)) for arm in ARMS}}
            for A_, B_ in (("KEEP", "SUB"), ("KEEP", "BASE"), ("SUB", "BASE")):
                st = lambda gs, A_=A_, B_=B_: statistics.mean(gm(A_, g) - gm(B_, g) for g in gs)
                pc = collections.Counter()
                for ra, rb in zip(sel(A_, m, act), sel(B_, m, act)):
                    assert ra["target"] == rb["target"]
                    pc["both" if ra["exact"] and rb["exact"] else f"{A_} only" if ra["exact"] else f"{B_} only" if rb["exact"] else "neither"] += 1
                pair = collections.Counter()
                for g in groups:
                    for ac in ([act] if act else ["arrival", "correction"]):
                        ea = all(r["exact"] for r in sel(A_, m, ac) if r["group"] == g)
                        eb = all(r["exact"] for r in sel(B_, m, ac) if r["group"] == g)
                        pair["both" if ea and eb else f"{A_} only" if ea else f"{B_} only" if eb else "neither"] += 1
                blk[f"{A_}-{B_}"] = {"difference": round(st(groups), 4), "ci95": boot(groups, strat, st, a.boot, a.seed),
                                     "paired_targets": dict(pc), "paired_history_units_both_exact": dict(pair)}
            blk["both_histories_exact"] = {arm: sum(all(r["exact"] for r in sel(arm, m, ac) if r["group"] == g)
                                                    for g in groups for ac in ([act] if act else ["arrival", "correction"])) for arm in ARMS}
            out[key] = blk
        diag = {}
        for arm in ARMS:
            rs = sel(arm, m)
            diag[arm] = {"n": len(rs), "exact": sum(r["exact"] for r in rs), "incomplete": sum(r["incomplete"] for r in rs),
                         "accepted": sum(bool(r.get("accepted")) for r in rs),
                         "accepted_wrong_binding": sum(bool(r.get("accepted")) and not r.get("bound_ok_accepted") for r in rs),
                         "accepted_but_inexact": sum(bool(r.get("accepted")) and not r["exact"] for r in rs),
                         "arrival_state_only_accepted": sum(bool(r.get("state_only_event_accepted")) for r in rs),
                         "arrival_event_omitted": sum(r["event_omitted"] for r in rs),
                         "correction_mixed": sum(r["mixed_correction"] for r in rs),
                         "value_conflict_internal": sum(r["value_conflict_internal"] for r in rs),
                         "value_contradicts_gold": sum(r["value_contradicts_gold"] for r in rs),
                         "rejected": sum(r["rejected"] for r in rs),
                         "rejection_codes": dict(collections.Counter(str(r.get("contract_code") or r.get("pending_code")) for r in rs if r["rejected"])),
                         "false_revision_accepted": sum(bool(r.get("false_revision_accepted")) for r in rs),
                         "truncated": sum(bool(r.get("truncated")) for r in rs),
                         "replay_ok": sum(bool(r.get("replay_ok")) for r in rs),
                         "outcomes_by_act": {ac: dict(collections.Counter(outcome(r) for r in rs if r["act"] == ac)) for ac in ("arrival", "correction")}}
        out["diagnostics"] = diag
        out["by_family_act"] = {f"{fam}|{ac}": {arm: f"{sum(r['exact'] for r in sel(arm, m, ac) if r['family'] == fam)}/"
                                                     f"{sum(1 for r in sel(arm, m, ac) if r['family'] == fam)}" for arm in ARMS}
                                for fam in sorted({r['family'] for r in sel('KEEP', m)}) for ac in ("arrival", "correction")}
        out["by_reception_act"] = {f"{rc}|{ac}": {arm: f"{sum(r['exact'] for r in sel(arm, m, ac) if r['reception'] == rc)}/"
                                                       f"{sum(1 for r in sel(arm, m, ac) if r['reception'] == rc)}" for arm in ARMS}
                                   for rc in ("immediate", "delayed") for ac in ("arrival", "correction")}
        res[m] = out
    pr = []
    for tid, expected in PROBES:
        sub = rows[(tid, "SUB")]
        got = ("state_only" if sub.get("state_only_event_accepted") and sub.get("bound_ok_accepted") else
               "rejected_mixed_acts" if sub["rejected"] and sub.get("pending_code") == "mixed_acts" and sub.get("event_on_X") else
               "mixed_no_state_yes_revision" if sub["mixed_correction"] and sub["value_conflict_internal"] else "other")
        pr.append({"target": tid, "family": rows[(tid, "SUB")]["family"], "reception": rows[(tid, "SUB")]["reception"],
                   "phrase": led[tid]["phrase"], "identity": led[tid]["field"],
                   "expected_SUB_class": expected, "SUB_class_recomputed": got, "SUB_class_matches": got == expected,
                   **{arm: outcome(rows[(tid, arm)]) for arm in ARMS},
                   **{f"{arm}_claims": rows[(tid, arm)]["claims_summary"] for arm in ARMS}})
    res["probes"] = {"rows": pr, "KEEP_exact": sum(p["KEEP"] == "exact" for p in pr), "BASE_exact": sum(p["BASE"] == "exact" for p in pr),
                     "SUB_exact": sum(p["SUB"] == "exact" for p in pr), "SUB_class_all_match": all(p["SUB_class_matches"] for p in pr),
                     "KEEP_by_class": {c: dict(collections.Counter(p["KEEP"] for p in pr if p["expected_SUB_class"] == c))
                                       for c in ("state_only", "rejected_mixed_acts", "mixed_no_state_yes_revision")}}
    cost = {}
    for arm in ARMS:
        rs = [r for (t, ar), r in rows.items() if ar == arm and not r["incomplete"]]
        cost[arm] = {"n": len(rs), "input_tokens_mean": round(statistics.mean(r["input_tokens"] for r in rs), 1) if rs else None,
                     "output_tokens_mean": round(statistics.mean(r["output_tokens"] for r in rs), 1) if rs else None,
                     "seconds_mean": round(statistics.mean(r["seconds"] for r in rs), 3) if rs else None,
                     "seconds_total": round(sum(r["seconds"] for r in rs), 1)}
    res["cost"] = cost
    out = hub / "analysis" / "kid"
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "scored.jsonl", "w") as fh:
        for r in rows.values():
            fh.write(json.dumps(r, sort_keys=True, default=str) + "\n")
    (out / "ANALYSIS.json").write_text(json.dumps(res, indent=1, default=str) + "\n")
    print(json.dumps({"records": res["records"], "MAIN_arrival": res["MAIN"]["arrival"]["exact"],
                      "MAIN_arrival_KEEP-SUB": res["MAIN"]["arrival"]["KEEP-SUB"]}))


if __name__ == "__main__":
    main()
