"""V1.18.0 scoring, temporal replay and analysis (no model).
Usage: fac_analyze.py --hub HUB --set SET --stage STAGE [--boot 10000] [--seed 20261106]
EXCLUSIVE replies: adapter-v1 (text_channel.adapt, unchanged). FACTORED replies: factored.compile_reply. Both become
canonical v1 reports, scored by the same unchanged source-aware scorer (contract_validate.score_record; the
compiler's R2/R3 make an event plus its matching result state equal to the event alone; a state alone is not an
event; a revision is not an event). Acceptance: the unchanged engine contract over the SAME canonical prefix.
Temporal replay (canonical prefix + the interface's accepted target, else the target as pending evidence), three
queries on the target field P: Q1 value at the historical anchor with all evidence (cutoff 12); Q2 value now (12);
Q3 value at the anchor known before the target's reception (cutoff t-1). Independent reference = hand rules over the
canonical source meaning (arrival no/yes/no; observation yes/yes/yes; removal yes/no/yes; correction no/no/yes);
the canonical replay must equal it (software gate); interface replay accuracy is an outcome.
Primary: FACTORED - EXCLUSIVE in the group's mean exact meaning over the four classes; n = 120 groups; bootstrap
groups within the 8 strata, 10,000 resamples, seed 20261106 (descriptive)."""
import argparse
import collections
import json
import random
import statistics
from pathlib import Path

from _bootstrap import ROOT  # noqa: F401
from dream_core import localpaths as LP  # public release: local paths from environment
from tempo import assertions as A, ctxablate as CA, engine_fixtures as EF, factored as FA, text_channel as TC, worlds
from contract_validate import score_record

DEPREC = Path(f"{LP.RUNS}/temporal-dependency-recovery-20261105-170340")
REF = {"arrival": ("no", "yes", "no"), "observation": ("yes", "yes", "yes"), "removal": ("yes", "no", "yes"),
       "correction": ("no", "no", "yes")}
NOW = 12


def load(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]


def boot(groups, strat, stat, B, seed):
    by = collections.defaultdict(list)
    for g in groups:
        by[strat[g]].append(g)
    rng = random.Random(seed)
    est = sorted(x for x in (stat([rng.choice(v) for v in by.values() for _ in v]) for _ in range(B)) if x is not None)
    n = len(est)
    return [round(est[int(0.025 * n)], 4), round(est[min(n - 1, int(0.975 * n))], 4)] if n else None


def world_of(gr):
    rng = random.Random(gr["world_seed"])
    return worlds.make_world("assembly", rng, __import__("tempo.freshgen", fromlist=["Names"]).Names(gr["pool"], rng), "stock")


def engine_with(w, prefix, rep, text, rid, recv, ctx, gold=None):
    """Evaluator engine: the same canonical prefix for both interfaces (spec from prefix + canonical target)."""
    eng = A.AssertionEngine(EF.spec_from_world(vars(w), "assembly", prefix + ([gold] if gold else [])), ctx)
    for r in prefix:
        eng.ingest(A.from_v02(EF.public_record(r)))
    accepted, code = False, None
    if rep is not None:
        try:
            eng.ingest(rep)
            accepted = True
        except A.ContractRejected as e:
            code = e.code
    if not accepted:
        eng.record_unprocessed(rid, recv, text, rep, code or "unprocessed", None)
    return eng, accepted, code


def replay(eng, P, anchor, t_recv):
    val = lambda v: v["per_field"].get(P)
    return (val(eng.view("earlier", anchor, cutoff=NOW)), val(eng.view("current", NOW)),
            val(eng.view("earlier", anchor, cutoff=t_recv - 1)))


def claims_of(iface, rep, tr):
    """(events, states, revisions) lists of fields, from the factored claims or the exclusive report."""
    if iface == "FACTORED":
        c = (tr or {}).get("claims")
        if not c:
            return None
        return ([e["field"] for e in c["events"]], [s["field"] for s in c["states"]], [r["field"] for r in c["revisions"]])
    if rep is None:
        return None
    fs = [a["field"] for a in rep["assertions"]]
    return (fs if rep["type"] == "event" else [], fs if rep["type"] == "state" else [], fs if rep["type"] == "correction" else [])


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
        if c["arm"] == "EXCLUSIVE":
            f = calls[cid.replace("|EXCLUSIVE", "|FACTORED")]
            try:
                if FA.factored_prompt(c["user"]) != f["user"]:
                    bad.append(("prompt_pair", cid))
            except AssertionError:
                bad.append(("prompt_blocks", cid))
        if c["max_new_tokens"] != 256 or any(x in c["user"] for x in ("|arrival|", "|removal|", "|correction|", "|observation|", "EXCLUSIVE", "FACTORED")):
            bad.append(("cap_or_label", cid))
    gate("G1 matched inputs: FACTORED = EXCLUSIVE with exactly the two declared blocks replaced; shared FULL context; "
         "256-token cap; no labels in inputs", bad, len(calls))
    cfg = json.loads((hub / "config" / f"stage-{a.stage}.json").read_text())
    old = json.loads((DEPREC / "config" / "stage-main.json").read_text())
    gate("G2 model configuration equals the frozen configuration; committed order",
         [] if cfg["model"] == old["model"] and cfg["retry_limit"] == old["retry_limit"] and cfg.get("order") == "as_committed" else ["config"], 1)
    bad = []
    by_group = collections.defaultdict(dict)
    for g in gold.values():
        if not g["control"] and g["interface"] == "FACTORED":
            by_group[g["group"]][g["variant"]] = g
    for gid, vs in by_group.items():
        if set(vs) != set(CA.VARIANTS):
            bad.append(("variants", gid)); continue
        P = vs["arrival"]["P"]
        kinds = tuple(vs[v]["gold"]["kind"] for v in CA.VARIANTS)
        if kinds != ("change", "observation", "change", "correction") or any(vs[v]["gold"]["payload"]["field"] != P for v in CA.VARIANTS):
            bad.append(("labels", gid))
        pre = {v: {r["payload"].get("field"): r for r in vs[v]["prefix"]} for v in CA.VARIANTS}
        if pre["arrival"][P]["payload"]["value"] != "no" or pre["removal"][P]["payload"]["value"] != "yes" or \
                pre["correction"][P]["status"] != "provisional" or vs["correction"]["gold"]["payload"]["target"] != pre["correction"][P]["rid"]:
            bad.append(("prefix", gid))
    # canonical compile + replay = reference (software)
    nrep = 0
    for g in gold.values():
        if g["control"] or g["interface"] != "FACTORED":
            continue
        gr = groups[g["group"]]
        w = world_of(gr)
        reg = next(t["registry"] for t in targets if t["cell"] == g["cell"])
        rep, tr = FA.compile_reply(json.dumps(FA.canonical_factored(g["gold"])), reg)
        if rep is None or not score_record(rep, g["gold"], g["text"])["denotation_equal"]:
            bad.append(("canonical_compile", g["cell"]))
        eng, acc, _ = engine_with(w, g["prefix"], A.from_v02(EF.public_record(g["gold"])), g["text"], g["gold"]["rid"],
                                  g["gold"]["received_at"], "ref", g["gold"])
        nrep += 1
        if not acc or replay(eng, g["P"], g["anchor"], g["gold"]["received_at"]) != REF[g["variant"]]:
            bad.append(("canonical_replay", g["cell"], replay(eng, g["P"], g["anchor"], g["gold"]["received_at"])))
    ctl_ok = all(len([c for c in calls if c.startswith(f"{cg}|ctl|")]) == 4 for cg in {x["group"] for x in gold.values() if x["control"]})
    if len(calls) != commit["calls"] or not ctl_ok:
        bad.append(("accounting",))
    gate("G3 valid canonical labels and prefixes; canonical replies compile exactly; canonical replay equals the "
         "independent temporal reference; exact accounting", bad, len(by_group) + nrep)
    rows = []
    for t in targets:
        g = gold[t["cell"]]
        rc = recs.get(t["call_id"])
        raw = rc["raw"] if rc and rc.get("status") == "ok" else None
        if t["interface"] == "EXCLUSIVE":
            rep, log = TC.adapt(raw, t["registry"])
            tr = {"adapter_log": log}
            code = None if rep is not None else ("parse" if log["parse_error"] else "unmapped")
        else:
            rep, tr = FA.compile_reply(raw, t["registry"])
            code = tr["code"]
        gr = groups[t["group"]]
        w = world_of(gr)
        eng, accepted, ccode = engine_with(w, g["prefix"], rep, g["text"], g["gold"]["rid"], g["gold"]["received_at"], t["cell"], g["gold"])
        sc = score_record(rep, g["gold"], g["text"])
        P = g.get("P") or g["gold"]["payload"]["field"]
        cl = claims_of(t["interface"], rep, tr)
        row = {"cell": t["cell"], "group": t["group"], "variant": t["variant"], "interface": t["interface"],
               "alternative": t.get("alternative"), "control": t["control"], "raw": raw, "report": rep, "trace": tr,
               "exact": sc["denotation_equal"], "coverage": sc["coverage"], "spurious": sc["spurious"],
               "category": None if rep is None else rep["type"], "pending_code": code, "accepted": accepted,
               "contract_code": ccode, "fields": None if rep is None else sorted({x["field"] for x in rep["assertions"]}),
               "field_ok": rep is not None and sorted({x["field"] for x in rep["assertions"]}) == [g["gold"]["payload"]["field"]],
               "claims": cl, "stop": None if rc is None else rc.get("stop"),
               "output_tokens": None if rc is None else rc.get("output_tokens"), "seconds": None if rc is None else rc.get("seconds"),
               "call_status": None if rc is None else rc.get("status")}
        if cl is not None:
            ev, st, rv = cl
            row.update(has_event_on_P=P in ev, has_state_on_P=P in st, has_revision=bool(rv),
                       other_field_claimed=any(f != P for f in ev + st + rv))
        if not t["control"]:
            row["replay"] = replay(eng, P, g["anchor"], g["gold"]["received_at"])
            row["replay_ok"] = row["replay"] == REF[t["variant"]]
            row["replay_q"] = [x == y for x, y in zip(row["replay"], REF[t["variant"]])]
            res_val = {"arrival": "yes", "observation": "yes", "removal": "no", "correction": "no"}[t["variant"]]
            row["result_value_ok"] = rep is not None and any(x.get("value", x.get("to")) == res_val for x in rep["assertions"]
                                                            if x.get("field") == P)
        rows.append(row)
    gate("G4 complete accounting: every committed call has a stored reply record; every cell scored",
         [c for c in calls if c not in recs] + ([] if len(rows) == len(targets) else ["cells"]), len(calls))
    res = {"set": a.set, "stage": a.stage, "gates": gates, "software_gates_pass": not fails, "failed_gates": fails,
           "calls": {"committed": commit["calls"], "collected": len(recs), "ok": sum(r.get("status") == "ok" for r in recs.values())}}
    R = {(r["group"], r["variant"], r["interface"]): r for r in rows if not r["control"]}
    G = sorted({r["group"] for r in rows if not r["control"]})
    strat = {g: tuple(groups[g]["stratum"]) for g in G}
    macro = lambda gs, i: sum(statistics.mean(R[(g, v, i)]["exact"] for v in CA.VARIANTS) for g in gs) / len(gs)
    d = lambda gs: macro(gs, "FACTORED") - macro(gs, "EXCLUSIVE")
    res["primary"] = {"metric": "macro exact meaning over 4 classes, FACTORED - EXCLUSIVE", "n_groups": len(G),
                      "EXCLUSIVE": round(macro(G, "EXCLUSIVE"), 4), "FACTORED": round(macro(G, "FACTORED"), 4),
                      "difference": round(d(G), 4), "ci95": boot(G, strat, d, a.boot, a.seed)}
    pv = {}
    for v in CA.VARIANTS:
        x = {}
        for i in FA.INTERFACES:
            rs = [R[(g, v, i)] for g in G]
            x[i] = {"exact": sum(r["exact"] for r in rs), "field_ok": sum(r["field_ok"] for r in rs),
                    "result_value_ok": sum(r["result_value_ok"] for r in rs),
                    "result_value_ok_but_not_exact": sum(r["result_value_ok"] and not r["exact"] for r in rs),
                    "accepted": sum(r["accepted"] for r in rs), "category": dict(collections.Counter(str(r["category"]) for r in rs)),
                    "pending": dict(collections.Counter(str(r["pending_code"]) for r in rs if r["report"] is None)),
                    "contract_rejections": dict(collections.Counter(str(r["contract_code"]) for r in rs if r["report"] is not None and not r["accepted"])),
                    "event_on_P": sum(bool(r.get("has_event_on_P")) for r in rs),
                    "state_on_P": sum(bool(r.get("has_state_on_P")) for r in rs),
                    "revision_claimed": sum(bool(r.get("has_revision")) for r in rs),
                    "other_field_claimed": sum(bool(r.get("other_field_claimed")) for r in rs),
                    "accepted_as_correction": sum(r["accepted"] and r["category"] == "correction" for r in rs),
                    "replay_all_ok": sum(r["replay_ok"] for r in rs),
                    "replay_q_ok": [sum(r["replay_q"][q] for r in rs) for q in range(3)],
                    "truncated": sum(r["stop"] == "length" for r in rs)}
        pc = collections.Counter()
        for g in G:
            e, f = R[(g, v, "EXCLUSIVE")]["exact"], R[(g, v, "FACTORED")]["exact"]
            pc["both" if e and f else "FACTORED only" if f else "EXCLUSIVE only" if e else "neither"] += 1
        x["paired"] = dict(pc)
        dv = lambda gs, v=v: sum(R[(g, v, "FACTORED")]["exact"] - R[(g, v, "EXCLUSIVE")]["exact"] for g in gs) / len(gs)
        x["difference"] = round(dv(G), 4)
        x["ci95"] = boot(G, strat, dv, a.boot, a.seed)
        pv[v] = x
    res["by_class"] = pv
    red = collections.Counter(rr["rule"] for r in rows if r["interface"] == "FACTORED" and r["trace"] and r["trace"].get("reduce")
                              for rr in r["trace"]["reduce"])
    res["factored_redundancy_rules"] = dict(red)
    res["by_stratum_macro"] = {str(s): {i: round(macro([g for g in G if strat[g] == s], i), 3) for i in FA.INTERFACES}
                               for s in sorted(set(strat.values()))}
    res["discordant"] = [{"group": g, "variant": v, "EXCLUSIVE": R[(g, v, "EXCLUSIVE")]["exact"], "FACTORED": R[(g, v, "FACTORED")]["exact"],
                          "EXCLUSIVE_raw": (R[(g, v, "EXCLUSIVE")]["raw"] or "")[:300], "FACTORED_raw": (R[(g, v, "FACTORED")]["raw"] or "")[:400],
                          "FACTORED_code": R[(g, v, "FACTORED")]["pending_code"]}
                         for g in G for v in CA.VARIANTS if R[(g, v, "EXCLUSIVE")]["exact"] != R[(g, v, "FACTORED")]["exact"]]
    C = {(r["group"], r["alternative"], r["interface"]): r for r in rows if r["control"]}
    CG = sorted({r["group"] for r in rows if r["control"]})
    res["controls"] = {i: {"both_alternatives_exact": sum(C[(c, "A", i)]["exact"] and C[(c, "B", i)]["exact"] for c in CG),
                           "exact_by_alternative": {x: sum(C[(c, x, i)]["exact"] for c in CG) for x in "AB"},
                           "both_alternatives_field": sum(C[(c, "A", i)]["field_ok"] and C[(c, "B", i)]["field_ok"] for c in CG),
                           "categories": dict(collections.Counter(str(C[(c, x, i)]["category"] or C[(c, x, i)]["pending_code"]) for c in CG for x in "AB"))}
                       for i in FA.INTERFACES}
    res["controls"]["n_groups"] = len(CG)
    tok = collections.defaultdict(list)
    for r in rows:
        if r["output_tokens"] is not None and not (r["control"] and False):
            tok[r["interface"]].append((r["output_tokens"], r["seconds"] or 0))
    res["runtime"] = {i: {"calls": len(v), "output_tokens": sum(x for x, _ in v), "mean_tokens": round(statistics.mean(x for x, _ in v), 1) if v else None,
                          "generation_s": round(sum(y for _, y in v), 1)} for i, v in tok.items()}
    out = hub / "analysis" / a.stage
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "scored.jsonl", "w") as fh:
        for r in rows:
            fh.write(json.dumps(r, default=str, sort_keys=True) + "\n")
    (out / "ANALYSIS.json").write_text(json.dumps(res, indent=1, default=str) + "\n")
    print(json.dumps({"software_gates_pass": res["software_gates_pass"], "failed": fails, "calls": res["calls"], "primary": res["primary"]}))


if __name__ == "__main__":
    main()
