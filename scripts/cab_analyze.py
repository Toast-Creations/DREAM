"""V1.17.0 scoring and analysis (no model).
Usage: cab_analyze.py --hub HUB --set SET --stage STAGE [--boot 10000] [--seed 20261106]
Per scored cell: adapter-v1 (text_channel.adapt, unchanged) with the cell's registry; source-aware exact meaning
(contract_validate.score_record, unchanged) and nul_evaluate.record_diag (kind, field, result, meta, prior); category
(state / event / correction; initial and observation are both "state"); correction-target correctness; contract
acceptance against the SAME canonical prefix in both conditions (evaluator only; never a model input).
Software gates: prompt isolation (FULL/LOCAL diff exactly the context block; NULL_PRIOR schema in both), model config,
distinct valid labels, byte-identical LOCAL control pairs and exact cache accounting, complete paired scoring, no
hidden labels in inputs. Primary: LOCAL - FULL exact meaning on the 120 arrivals; unit = group (n = 120); bootstrap
groups within the 8 precommitted strata, 10,000 resamples, seed 20261106 (descriptive)."""
import argparse
import collections
import json
import random
import statistics
from pathlib import Path

from _bootstrap import ROOT  # noqa: F401
from dream_core import localpaths as LP  # public release: local paths from environment
from tempo import assertions as A, ctxablate as CA, engine_fixtures as EF, nullprior as NP, text_channel as TC
from nul_evaluate import record_diag

DEPREC = Path(f"{LP.RUNS}/temporal-dependency-recovery-20261105-170340")


def load(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]


def boot(groups, strat, stat, B, seed):
    by = collections.defaultdict(list)
    for g in groups:
        by[strat[g]].append(g)
    rng = random.Random(seed)
    est = []
    for _ in range(B):
        s = [rng.choice(v) for v in by.values() for _ in v]
        x = stat(s)
        if x is not None:
            est.append(x)
    est.sort()
    n = len(est)
    return [round(est[int(0.025 * n)], 4), round(est[min(n - 1, int(0.975 * n))], 4)] if n else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", required=True)
    ap.add_argument("--set", required=True)
    ap.add_argument("--stage", required=True)
    ap.add_argument("--boot", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=20261106)
    a = ap.parse_args()
    hub = Path(a.hub)
    data = hub / "data"
    commit = json.loads((data / f"COMMITMENT-{a.set}.json").read_text())
    calls = {c["call_id"]: c for c in load(data / f"{a.set}-calls.jsonl")}
    targets = load(data / "public" / f"{a.set}-targets.jsonl")
    gold = {g["cell"]: g for g in load(data / "hidden" / f"{a.set}-gold.jsonl")}
    groups = {g["group"]: g for g in load(data / "hidden" / f"{a.set}-groups.jsonl")}
    recs = {}
    for p in (hub / "stages" / a.stage / "calls").glob("*.json"):
        r = json.loads(p.read_text())
        recs[r["call_id"]] = r
    gates, fails = {}, []

    def gate(name, bad, total):
        gates[name] = {"pass": not bad, "failures": len(bad), "checked": total, "examples": [str(b) for b in bad[:10]]}
        if bad:
            fails.append(name)
    bad = []
    for cid, c in calls.items():
        if c["arm"] == "FULL":
            loc = calls[cid.replace("|FULL_A", "|LOCAL").replace("|FULL_B", "|LOCAL").replace("|FULL", "|LOCAL")]
            try:
                CA.check_diff(c["user"], loc["user"])
            except AssertionError:
                bad.append(("diff", cid))
        if NP.NULL_PAYLOAD_LINE not in c["user"] or NP.CLARIFICATION not in c["user"] or c["max_new_tokens"] != 256:
            bad.append(("schema", cid))
        if any(x in c["user"] for x in ("|arrival|", "|removal|", "|correction|", "|observation|", "FULL_A", "LOCAL")):
            bad.append(("label_in_input", cid))
    gate("G1 prompt isolation (FULL/LOCAL differ only in the context block), NULL_PRIOR schema and 256-token cap in both, "
         "no labels in inputs", bad, len(calls))
    cfg = json.loads((hub / "config" / f"stage-{a.stage}.json").read_text())
    old = json.loads((DEPREC / "config" / "stage-main.json").read_text())
    gate("G2 model configuration equals the frozen 1.11.0-1.16.0 configuration; committed order",
         [] if cfg["model"] == old["model"] and cfg["retry_limit"] == old["retry_limit"] and cfg.get("order") == "as_committed"
         else ["config"], 1)
    bad = []
    by_group = collections.defaultdict(dict)
    for g in gold.values():
        if not g["control"]:
            by_group[g["group"]][g["variant"]] = g
    for gid, vs in by_group.items():
        if set(vs) != set(CA.VARIANTS):
            bad.append(("variants", gid))
            continue
        ar, ob, rm, co = (vs[v]["gold"] for v in CA.VARIANTS)
        P = ar["payload"]["field"]
        if not (ar["kind"] == "change" and ar["payload"]["to"] == "yes" and ob["kind"] == "observation" and
                rm["kind"] == "change" and rm["payload"]["to"] == "no" and co["kind"] == "correction" and
                all((x["payload"]["field"] == P) for x in (ob, rm, co))):
            bad.append(("labels", gid))
        pre = {v: {r["payload"].get("field"): r for r in vs[v]["prefix"]} for v in CA.VARIANTS}
        if pre["arrival"][P]["payload"]["value"] != "no" or pre["removal"][P]["payload"]["value"] != "yes" or \
                pre["correction"][P]["status"] != "provisional" or co["payload"]["target"] != pre["correction"][P]["rid"]:
            bad.append(("prefix_compatibility", gid))
    ctl = collections.defaultdict(list)
    for c in calls.values():
        if c["variant"] == "control":
            ctl[c["group_id"]].append(c)
    for cg, cs in ctl.items():
        if len(cs) != 3 or sum(c["arm"] == "LOCAL" for c in cs) != 1:
            bad.append(("control_calls", cg))
        ga, gb = gold[f"{cg}|ctl|FULL|A"]["gold"], gold[f"{cg}|ctl|FULL|B"]["gold"]
        if ga["payload"]["field"] == gb["payload"]["field"]:
            bad.append(("control_fields_not_distinct", cg))
    n_unique = len(calls)
    exp_cells = 8 * commit["groups"] + 4 * commit["control_groups"]
    if n_unique != commit["calls"] or len(targets) != exp_cells or commit["calls"] != 8 * commit["groups"] + 3 * commit["control_groups"]:
        bad.append(("cache_accounting", n_unique, len(targets)))
    gate("G3 valid distinct source labels and compatible prefixes; control pairs distinct in FULL, one cached LOCAL; "
         "exact cell/call accounting", bad, len(by_group) + len(ctl))
    # score
    rows = []
    for t in targets:
        g = gold[t["cell"]]
        rc = recs.get(t["call_id"])
        raw = rc["raw"] if rc and rc.get("status") == "ok" else None
        rep, log = TC.adapt(raw, t["registry"])
        gr = groups[t["group"]]
        w, _ = CA._world(gr["world_seed"], gr["pool"])
        full_recs = g["prefix"] + [g["gold"]]
        eng = A.AssertionEngine(EF.spec_from_world(vars(w), "assembly", full_recs), t["cell"])
        for r in g["prefix"]:
            eng.ingest(A.from_v02(EF.public_record(r)))
        accepted, code = False, None
        if rep is not None:
            try:
                eng.ingest(rep)
                accepted = True
            except A.ContractRejected as e:
                code = e.code
        else:
            code = "parse" if log["parse_error"] else "unmapped"
        d = record_diag(rep, g["gold"], g["text"])
        cat = None if rep is None else rep["type"]
        ct_ok = None
        if g["gold"]["kind"] == "correction":
            ct_ok = rep is not None and rep["type"] == "correction" and \
                rep["assertions"][0].get("target") == g["gold"]["payload"]["target"]
        rows.append(dict(d, cell=t["cell"], call_id=t["call_id"], group=t["group"], variant=t["variant"],
                         condition=t["condition"], alternative=t.get("alternative"), control=t["control"],
                         stratum=g.get("stratum"), raw=raw, report=rep, adapter_log=log, accepted=accepted, code=code,
                         category=cat, gold_category=A.from_v02(g["gold"])["type"], correction_target_ok=ct_ok,
                         call_status=None if rc is None else rc.get("status"),
                         output_tokens=None if rc is None else rc.get("output_tokens"),
                         seconds=None if rc is None else rc.get("seconds"), stop=None if rc is None else rc.get("stop")))
    gate("G4 complete paired scoring (every committed call has a stored reply record; every cell scored)",
         [c for c in calls if c not in recs] + ([] if len(rows) == exp_cells else ["cells"]), len(calls))
    res = {"set": a.set, "stage": a.stage, "gates": gates, "software_gates_pass": not fails, "failed_gates": fails,
           "calls": {"unique_committed": commit["calls"], "collected": len(recs),
                     "ok": sum(r.get("status") == "ok" for r in recs.values()), "scored_cells": len(rows),
                     "cached_local_control_replies": commit["control_groups"]}}
    R = {(r["group"], r["variant"], r["condition"]): r for r in rows if not r["control"]}
    G = sorted({r["group"] for r in rows if not r["control"]})
    strat = {g: tuple(R[(g, "arrival", "FULL")]["stratum"]) for g in G}

    def acc(gs, v, cond, key="denotation_equal"):
        return sum(bool(R[(g, v, cond)][key]) for g in gs), len(gs)

    def diff(gs, v="arrival", key="denotation_equal"):
        a1, n = acc(gs, v, "LOCAL", key)
        a0, _ = acc(gs, v, "FULL", key)
        return (a1 - a0) / n if n else None
    pair = collections.Counter()
    for g in G:
        f, l = R[(g, "arrival", "FULL")]["denotation_equal"], R[(g, "arrival", "LOCAL")]["denotation_equal"]
        pair["both correct" if f and l else "LOCAL only" if l else "FULL only" if f else "neither"] += 1
    res["primary"] = {"metric": "arrival exact meaning, LOCAL - FULL", "n_groups": len(G),
                      "FULL": acc(G, "arrival", "FULL"), "LOCAL": acc(G, "arrival", "LOCAL"),
                      "difference": None if not G else round(diff(G), 4), "ci95": boot(G, strat, diff, a.boot, a.seed),
                      "paired": dict(pair)}
    sec = {}
    for v in CA.VARIANTS:
        x = {}
        for cond in CA.CONDITIONS:
            rs = [R[(g, v, cond)] for g in G]
            x[cond] = {"exact": sum(r["denotation_equal"] for r in rs), "kind": sum(bool(r["kind_correct"]) for r in rs),
                       "field": sum(bool(r["field_attribution_ok"]) for r in rs), "result": sum(bool(r["result_ok"]) for r in rs),
                       "meta": sum(bool(r["meta_ok"]) for r in rs), "accepted": sum(r["accepted"] for r in rs),
                       "mapped": sum(r["report"] is not None for r in rs),
                       "category": dict(collections.Counter(str(r["category"]) for r in rs)),
                       "prior": dict(collections.Counter(r["prior"] for r in rs if r.get("prior"))),
                       "codes": dict(collections.Counter(str(r["code"]) for r in rs)),
                       "correction_target_ok": sum(bool(r["correction_target_ok"]) for r in rs) if v == "correction" else None,
                       "wrong_field_mapped": [r["cell"] for r in rs if r["report"] is not None and not r["field_attribution_ok"]]}
        pc = collections.Counter()
        for g in G:
            f, l = R[(g, v, "FULL")]["denotation_equal"], R[(g, v, "LOCAL")]["denotation_equal"]
            pc["both" if f and l else "LOCAL only" if l else "FULL only" if f else "neither"] += 1
        x["paired"] = dict(pc)
        x["difference_exact"] = round(diff(G, v), 4) if G else None
        x["difference_ci95"] = boot(G, strat, lambda gs, v=v: diff(gs, v), a.boot, a.seed)
        x["difference_kind"] = round(diff(G, v, "kind_correct"), 4) if G else None
        x["difference_kind_ci95"] = boot(G, strat, lambda gs, v=v: diff(gs, v, "kind_correct"), a.boot, a.seed)
        sec[v] = x
    res["by_variant"] = sec
    res["by_stratum_arrival"] = {str(s): {c: acc([g for g in G if strat[g] == s], "arrival", c) for c in CA.CONDITIONS}
                                 for s in sorted(set(strat.values()))}
    disc = [{"group": g, "variant": v, "FULL": R[(g, v, "FULL")]["denotation_equal"], "LOCAL": R[(g, v, "LOCAL")]["denotation_equal"],
             "FULL_category": R[(g, v, "FULL")]["category"], "LOCAL_category": R[(g, v, "LOCAL")]["category"],
             "FULL_raw": (R[(g, v, "FULL")]["raw"] or "")[:300], "LOCAL_raw": (R[(g, v, "LOCAL")]["raw"] or "")[:300]}
            for g in G for v in CA.VARIANTS if R[(g, v, "FULL")]["denotation_equal"] != R[(g, v, "LOCAL")]["denotation_equal"]]
    res["discordant"] = disc
    C = {(r["group"], r["condition"], r["alternative"]): r for r in rows if r["control"]}
    CG = sorted({r["group"] for r in rows if r["control"]})
    res["controls"] = {"groups": len(CG),
                       "FULL_both_alternatives_exact": sum(C[(c, "FULL", "A")]["denotation_equal"] and C[(c, "FULL", "B")]["denotation_equal"] for c in CG),
                       "FULL_both_alternatives_field": sum(bool(C[(c, "FULL", "A")]["field_attribution_ok"]) and bool(C[(c, "FULL", "B")]["field_attribution_ok"]) for c in CG),
                       "FULL_exact_by_alternative": {x: sum(C[(c, "FULL", x)]["denotation_equal"] for c in CG) for x in "AB"},
                       "LOCAL_shared_reply_matches": {x: sum(C[(c, "LOCAL", x)]["denotation_equal"] for c in CG) for x in "AB"},
                       "LOCAL_shared_reply_field_matches": {x: sum(bool(C[(c, "LOCAL", x)]["field_attribution_ok"]) for c in CG) for x in "AB"},
                       "LOCAL_matches_both": sum(C[(c, "LOCAL", "A")]["denotation_equal"] and C[(c, "LOCAL", "B")]["denotation_equal"] for c in CG),
                       "per_group": {c: {"FULL_A": C[(c, "FULL", "A")]["denotation_equal"], "FULL_B": C[(c, "FULL", "B")]["denotation_equal"],
                                         "LOCAL_vs_A": C[(c, "LOCAL", "A")]["denotation_equal"], "LOCAL_vs_B": C[(c, "LOCAL", "B")]["denotation_equal"],
                                         "LOCAL_fields": C[(c, "LOCAL", "A")]["fields_extracted"], "LOCAL_category": C[(c, "LOCAL", "A")]["category"]}
                                     for c in CG}}
    res["runtime"] = {"output_tokens": sum((r.get("output_tokens") or 0) for r in recs.values()),
                      "generation_s": round(sum((r.get("seconds") or 0) for r in recs.values()), 1),
                      "truncated": sum(r.get("stop") == "length" for r in recs.values())}
    out = hub / "analysis" / a.stage
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "scored.jsonl", "w") as fh:
        for r in rows:
            fh.write(json.dumps(r, default=str, sort_keys=True) + "\n")
    (out / "ANALYSIS.json").write_text(json.dumps(res, indent=1, default=str) + "\n")
    print(json.dumps({"software_gates_pass": res["software_gates_pass"], "failed": fails, "calls": res["calls"],
                      "primary": {k: res["primary"][k] for k in ("FULL", "LOCAL", "difference", "ci95", "paired")}}))


if __name__ == "__main__":
    main()
