"""V1.22.0 KEEP+ID confirmation analysis (no model).
Usage: kconf_analyze.py --hub HUB [--plan HUB/config/ANALYSIS-PLAN.json] [--out-name confirm]

ANALYSIS-PLAN.json (frozen before output; schema checked by tempo.kidconfdone.validate_plan, no fallback):
  {"arrival": {"rule": [fam, alpha], "threshold": "0"}, "correction": {"rule": [fam, alpha], "threshold": "-3/64"},
   "reference": ["P", 0.025], "B": 10000, "seed": int}

1. Infrastructure qualification (separate from semantics), all required:
   - tempo.kidconfdone.completion: runner LOCK (non-fake, committed config/calls, frozen source), END finished, no
     STOP, records = schedule for smoke and main, all ok, no logged failed attempts, attempts <= ceiling, every record
     and END no later than the deadline;
   - current source = the frozen source (config/FROZEN-PROTOCOL.json; absent -> not a confirmation run);
   - kidconf.check_complete on the declared (group, act) membership; prompt hashes and pinned recipe per record.
   If any fails: status INCOMPLETE, descriptive tables of the present records only, no A/C gates.
2. Scoring: kidconfscore.score_record per scheduled call against the ORIGINAL target (HOLD-EVAL-v1).
3. Gates (complete runs only), unrounded: A = arrival KEEP-SUB lower bound > 0; C = correction KEEP-SUB lower
   bound > -3/64; qualification requires both. Descriptive 95% intervals reported separately.
4. Declared secondaries per arm x act, family x act and reception x act tables, paired counts, cost."""
import argparse
import collections
import json
import statistics
from fractions import Fraction
from pathlib import Path

from _bootstrap import ROOT
from dream_core.ledger import release_source_hash
from tempo import kidconf as KC, kidconfdone as KD, kidconfscore as KS

PIN = {"revision": "9216db5781bf21249d130ec9da846c4624c16137", "quantization": "nf4", "enable_thinking": False,
       "decoding": "greedy", "dtype": "bfloat16"}


def load(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]


def records(hub, stage):
    out, dup = {}, []
    d = Path(hub) / "stages" / stage / "calls"
    for p in sorted(d.glob("*.json")) if d.exists() else []:
        r = json.loads(p.read_text())
        if r["call_id"] in out:
            dup.append(r["call_id"])
        out[r["call_id"]] = r
    return out, dup


def recipe_ok(r):
    m = r.get("model") or {}
    try:
        return (all(m.get(k) == v for k, v in PIN.items()) and m["load"]["devices"] == ["cuda:0"]
                and m["load"]["quantization"]["bnb_4bit_compute_dtype"] == "bfloat16"
                and m["load"]["quantization"]["bnb_4bit_use_double_quant"] is True
                and r.get("max_new_tokens") == 256 and r.get("attempts", 1) == 1)
    except (KeyError, TypeError):
        return False


def analyze(hub, plan):
    KD.validate_plan(plan)          # schema first: an invalid recipe stops analysis outright (no fallback)
    hub = Path(hub)
    data = hub / "data"
    pubs = {p["target"]: p for p in load(data / "public" / "main-targets.jsonl")}
    hid = {h["target"]: h for h in load(data / "hidden" / "main-cases.jsonl")}
    calls = load(data / "main-calls.jsonl")
    callmap = {c["call_id"]: c for c in calls}
    recs, dup = records(hub, "main")
    declared = {(p["group"], p["act"]): p["stratum"] for p in pubs.values()}
    infra = {"scheduled": len(calls), "records": len(recs), "duplicates": dup, "problems": []}
    fz = hub / "config" / "FROZEN-PROTOCOL.json"
    src_now = release_source_hash(ROOT)
    frozen_src = json.loads(fz.read_text())["source_sha256"] if fz.exists() else None
    done = KD.completion(hub, frozen_src or src_now)
    infra["completion"] = done
    if not done["complete"]:
        infra["problems"].extend(done["problems"])
    if frozen_src is None:
        infra["problems"].append("no FROZEN-PROTOCOL.json: not a frozen confirmation run")
    elif frozen_src != src_now:
        infra["problems"].append("current source differs from the frozen source")
    frozen_plan = json.loads(fz.read_text()).get("analysis_plan_sha256") if fz.exists() else None
    confirmatory = frozen_plan is not None and KD.plan_sha256(plan) == frozen_plan
    infra["analysis_plan_sha256"] = KD.plan_sha256(plan)
    infra["frozen_analysis_plan_sha256"] = frozen_plan
    try:
        if dup:
            raise KC.Incomplete(f"duplicate records {dup[:3]}")
        KC.check_complete(declared, set(callmap), recs)
        bad = [c for c, r in recs.items() if r["user_sha256"] != callmap[c]["user_sha256"] or not recipe_ok(r)]
        if bad:
            raise KC.Incomplete(f"{len(bad)} records with a prompt or recipe mismatch")
    except KC.Incomplete as e:
        infra["problems"].append(str(e))
    complete = not infra["problems"]
    infra["complete"] = complete
    rows, exact = {}, {}
    for cid, c in callmap.items():
        tid, arm = cid.rsplit("|", 1)
        r = recs.get(cid)
        if r is not None and r["user_sha256"] != c["user_sha256"]:
            r = None
        s = KS.score_record(r, hid[tid], pubs[tid])
        p = pubs[tid]
        s.update(call_id=cid, target=tid, arm=arm, group=p["group"], family=p["family"][:2], act=p["act"],
                 history=p["history"], reception=p["reception"], stratum=p["stratum"])
        rows[cid] = s
        if not s["incomplete"]:
            exact[(p["group"], p["act"], p["history"], arm)] = bool(s["exact"])
    res = {"status": "COMPLETE" if complete else "INCOMPLETE", "infrastructure": infra, "plan": plan}
    if complete:
        P = KD.validate_plan(plan)
        gates = {}
        for act in ("arrival", "correction"):
            tab, k = KC.pair_table(declared, exact, (act,))
            g = KC.decide(tab, P[act]["threshold"], P[act]["rule"], P["B"], P["seed"], k=k)
            ref = KC.decide(tab, P[act]["threshold"], P["reference"], P["B"], P["seed"], k=k)
            g["reference_95_interval_not_the_gate"] = ref["percentile95"]
            pc, ph = KC.paired_counts(declared, exact, (act,))
            g.update(paired_targets=pc, paired_history_units=ph)
            gates[act] = g
        if confirmatory:
            res["gates"] = gates
            res["qualification"] = KC.qualification(gates["arrival"], gates["correction"])
        else:   # a plan other than the frozen one: exploratory output only, never a confirmatory qualification
            res["status"] = "EXPLORATORY"
            res["exploratory_gates_not_confirmatory"] = gates
            res["exploratory_reason"] = "analysis plan differs from the frozen ANALYSIS-PLAN commitment"
    # descriptives (present records; denominators always shown)
    desc = {}
    for act in KC.ACTS:
        for arm in KC.ARMS:
            rs = [r for r in rows.values() if r["act"] == act and r["arm"] == arm]
            key = f"{act}|{arm}"
            desc[key] = {"n": len(rs), "incomplete": sum(r["incomplete"] for r in rs),
                         "exact": sum(bool(r["exact"]) for r in rs),
                         "accepted_wrong_binding": sum(bool(r.get("accepted")) and not r.get("bound_ok_accepted") for r in rs),
                         "accepted_inexact": sum(bool(r.get("accepted")) and not r["exact"] for r in rs),
                         "state_only_accepted": sum(bool(r.get("state_only_event_accepted")) for r in rs),
                         "event_present_raw": sum(bool(r.get("arrival_event_present_raw")) for r in rs),
                         "rejected_event_plus_extra_state": sum(bool(r.get("arrival_rejected_extra_state")) for r in rs),
                         "event_omitted": sum(bool(r.get("event_omitted")) for r in rs),
                         "mixed_correction": sum(bool(r.get("mixed_correction")) for r in rs),
                         "contradictory_correction": sum(bool(r.get("contradictory_correction")) for r in rs),
                         "empty_extraction": sum(bool(r.get("empty_extraction")) for r in rs),
                         "rejected": sum(bool(r.get("rejected")) for r in rs),
                         "rejection_codes": dict(collections.Counter(str(r.get("contract_code") or r.get("pending_code"))
                                                                     for r in rs if r.get("rejected"))),
                         "truncated": sum(bool(r.get("truncated")) for r in rs),
                         "outcomes": dict(collections.Counter(KS.outcome(r) for r in rs)),
                         "seconds_mean": round(statistics.mean(r["seconds"] for r in rs if r["seconds"] is not None), 3)
                         if any(r["seconds"] is not None for r in rs) else None}
    res["descriptives"] = desc
    for dim in ("family", "reception"):
        res[f"by_{dim}_act"] = {f"{v}|{act}": {arm: f"{sum(bool(r['exact']) for r in rows.values() if r[dim] == v and r['act'] == act and r['arm'] == arm)}/"
                                                     f"{sum(1 for r in rows.values() if r[dim] == v and r['act'] == act and r['arm'] == arm)}"
                                               for arm in KC.ARMS}
                                for v in sorted({r[dim] for r in rows.values()}) for act in KC.ACTS}
    return res, rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", required=True)
    ap.add_argument("--plan")
    ap.add_argument("--out-name", default="confirm")
    a = ap.parse_args()
    plan = json.loads(Path(a.plan or Path(a.hub) / "config" / "ANALYSIS-PLAN.json").read_text())
    res, rows = analyze(a.hub, plan)
    out = Path(a.hub) / "analysis" / a.out_name
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "scored.jsonl", "w") as fh:
        for r in rows.values():
            fh.write(json.dumps(r, sort_keys=True, default=str) + "\n")
    (out / "ANALYSIS.json").write_text(json.dumps(res, indent=1, default=str) + "\n")
    print(json.dumps({"status": res["status"], "qualification": res.get("qualification")}))


if __name__ == "__main__":
    main()
