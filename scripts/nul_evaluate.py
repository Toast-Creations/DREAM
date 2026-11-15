"""Evaluate a V1.16.0 extraction stage on CPU (no model).
Usage: nul_evaluate.py --hub HUB --set SET --stage STAGE [--require-freeze]
Per world: two goal-blind text channels, one per interface (each from its own replies only), plus the perfect-
extraction channel. Per goal and environment: DEPENDENCY on structured / ORIGINAL / NULL_PRIOR (Q0, S2, selection and
post-query projection all from that channel), each with the independent reference given the same evidence; the
independent selector check; perfect parity; gold-poisoning invariance per interface; hidden-tape leakage (changing).
Per record and interface: the source-aware scorer (contract_validate.score_record, unchanged) plus kind, field
attribution, result, meta (time/status/rid) and prior-value use.
Writes HUB/stages/STAGE/eval/*.jsonl and EVAL-META.json. A missing or non-ok reply enters as None (unprocessed)."""
import argparse
import copy
import json
import time
from pathlib import Path

from _bootstrap import ROOT
from dream_core.ledger import release_source_hash
from tempo import assertions as A, freshness as F, nullprior as NP, textdep as TD, timing as TM
from contract_validate import atoms, score_record, source_states_from
from timing_run import full_domain

ROLES = ("A", "B")
CHANNELS = ("structured",) + NP.INTERFACES
PK = ("queried", "states_sha256", "plan", "candidates", "success", "utility_base", "outcome_kind", "status")


def load(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]


def record_diag(rep, gold, text):
    g1 = A.from_v02(gold)
    sc = score_record(rep, gold, text)
    gf = sorted({a["field"] for a in g1["assertions"]})
    out = dict(sc, kind_correct=sc["type_class_equal"], extracted_type=None if rep is None else rep["type"],
               gold_type=g1["type"], fields_gold=gf)
    if rep is None:
        return dict(out, fields_extracted=None, field_attribution_ok=False, result_ok=False, meta_ok=False, prior=None)
    ef = sorted({a["field"] for a in rep["assertions"]})
    noprior = lambda S: {x for x in S if x[0] != "event_from"}
    out.update(fields_extracted=ef, field_attribution_ok=ef == gf,
               result_ok=noprior(atoms(rep)) == noprior(atoms(g1)),
               meta_ok=rep["status"] == gold["status"] and rep["received_at"] == gold["received_at"] and rep["rid"] == gold["rid"])
    prior = None
    if gold["kind"] in ("change", "uncertain_change") and rep["type"] == "event":
        frm = rep["assertions"][0].get("from")
        gfrom = gold["payload"].get("from")
        stated = source_states_from(gold, text)
        prior = "null" if frm is None else "correct" if frm == gfrom else "incorrect"
        if stated and frm is None:
            prior = "dropped_explicit"
        out["prior_stated_in_source"] = stated
    out["prior"] = prior
    return out


def alt_tapes(hid, trs):
    return {"realized": hid["tape"], "none": [],
            "all": [{"transition": x["id"], "elapsed": 0.5 + i % 2} for i, x in enumerate(trs)],
            "all_late": [{"transition": x["id"], "elapsed": 1.5} for x in trs]}


def evaluate(hub, set_name, stage):
    data = hub / "data"
    pubs = load(data / "public" / f"{set_name}-worlds.jsonl")
    txt = {t["world_id"]: t for t in load(data / "public" / f"{set_name}-text.jsonl")}
    hids = {h["world_id"]: h for h in load(data / "hidden" / f"{set_name}-hidden.jsonl")}
    gold = {g["call_id"]: g for g in load(data / "hidden" / f"{set_name}-gold.jsonl")}
    recs = {}
    for p in (hub / "stages" / stage / "calls").glob("*.json"):
        r = json.loads(p.read_text())
        recs[r["call_id"]] = r
    rows = {r[0]: (d, r) for d, r, _ in NP.specs(set_name, 0, smoke=set_name.endswith("smoke"))}
    out = {k: [] for k in ("channels", "selcheck", "selections", "trajectories", "reference", "parity", "poison",
                           "leakage", "feasibility", "extraction")}
    for pub in pubs:
        wid, domain = pub["world_id"], pub["domain"]
        hid, tx = hids[wid], txt[wid]
        bids = tx["call_ids"]
        chans = {}
        for iface in NP.INTERFACES:
            cids = [f"{b}|{iface}" for b in bids]
            raws = [recs[c]["raw"] if c in recs and recs[c].get("status") == "ok" else None for c in cids]
            ch = TD.build_channel(f"{wid}|{iface}", pub["spec"], raws, tx["registries"], tx["texts"], tx["received"])
            chans[iface] = ch
            out["channels"].append({"world": wid, "interface": iface, "rows": ch["rows"], "sequence": ch["sequence"],
                                    "n_reports": len(bids), "missing_replies": [c for c, r in zip(cids, raws) if r is None]})
            for b, c, row in zip(bids, cids, ch["rows"]):
                rc = recs.get(c) or {}
                out["extraction"].append(dict(record_diag(row["report"], gold[b]["gold"], gold[b]["text"]),
                                              call_id=c, base_id=b, world=wid, family=NP.family(wid), domain=domain,
                                              interface=iface, k=row["k"], kind_class=gold[b]["kind_class"],
                                              gold_kind=gold[b]["gold"]["kind"], accepted=row["accepted"], code=row["code"],
                                              parsed=row["raw"] is not None and row["adapter_log"]["parse_error"] is None,
                                              mapped=row["report"] is not None, call_status=rc.get("status"),
                                              output_tokens=rc.get("output_tokens"), seconds=rc.get("seconds"),
                                              stop=rc.get("stop")))
        perf = TD.build_channel(wid, pub["spec"], TD.perfect_raws([gold[b]["gold"] for b in bids]), tx["registries"],
                                tx["texts"], tx["received"])
        if not all(r["accepted"] for r in perf["rows"]):
            raise AssertionError(f"{wid}: perfect extraction not accepted")
        w = NP.build(rows[wid][1], domain, hid["seed"], set_name)[0]
        for role in ROLES:
            ep_s, gc, env_ep = NP.goal_copy(pub, hid, role)
            ep_t = TD.text_copy(ep_s)
            poisoned = copy.deepcopy(ep_s)
            for r in poisoned["reports"]:
                r["assertions"] = []
            for env in TM.ENVS:
                key = {"world": wid, "family": NP.family(wid), "domain": domain, "role": role, "env": env}
                envo = TM.environment(env_ep, env, pub["transitions"], hid["tape"], TM.schedule_clock("DEFER"))
                out["feasibility"].append(dict(key, optimum_at_action=full_domain(w, domain, gc["goal"], envo.state_at(16)[0])))
                runs = {}
                for chn, ep, ch in [("structured", ep_s, None)] + [(i, ep_t, chans[i]) for i in NP.INTERFACES] + \
                        [("perfect", ep_t, perf)] + [(f"poisoned_{i}", poisoned, chans[i]) for i in NP.INTERFACES]:
                    q0 = F.p2_request(ep, gc, ch)["fields"]
                    sel = TD.selection_for(ep, gc, q0, env, ch)
                    tagc = chn.replace("poisoned_", "") if chn != "perfect" else "perfect"
                    t = TD.run(ep, gc, sel["fields"]["DEPENDENCY"], env, env_ep, hid["tape"], ch, f"|{tagc}|DEPENDENCY")
                    runs[chn] = (q0, sel, t)
                    if chn not in CHANNELS:
                        continue
                    ref = TD.selection_reference(ep, gc, q0, env, ch)
                    sk = lambda S: sorted(json.dumps(sorted(x.items())) for x in S)
                    ok = {"s2": sk(sel["s2_states"]) == sk(ref["s2_states"]), "R": sel["R"] == ref["R"], "D": sel["D"] == ref["D"],
                          "DEPENDENCY": sel["fields"]["DEPENDENCY"] == ref["DEPENDENCY"]}
                    out["selcheck"].append(dict(key, channel=chn, ok=ok, all_ok=all(ok.values())))
                    out["selections"].append(dict(key, channel=chn, **sel))
                    rf = TD.reference(ep, gc, t, env, ch)
                    out["reference"].append(dict(key, channel=chn, states=rf["states"], classes=rf["classes"], choice=rf["choice"]))
                    out["trajectories"].append(dict(t, **key, channel=chn, selector="DEPENDENCY", Q0=q0,
                                                    fields=sel["fields"]["DEPENDENCY"], e=sel["e"], R=sel["R"], D=sel["D"],
                                                    relevant=gc["relevant"], label=hid["labels"][role]))
                    if env == "changing":
                        lrow = dict(key, channel=chn, by_list={"DEPENDENCY": {}})
                        for tn, tp in alt_tapes(hid, pub["transitions"]).items():
                            o = TD.run(ep, gc, sel["fields"]["DEPENDENCY"], env, env_ep, tp, ch, f"|leak|{chn}|{tn}")
                            lrow["by_list"]["DEPENDENCY"][tn] = {"readings": [(r["field"], r["value"]) for r in o["readings"]],
                                                                 "states_sha256": o["states_sha256"], "plan": o["plan"],
                                                                 "queried": o["queried"]}
                        out["leakage"].append(lrow)
                (qs, ss, ts), (qp, sp, tp_) = runs["structured"], runs["perfect"]
                out["parity"].append(dict(key, q0=qs == qp, fields=ss["fields"] == sp["fields"],
                                          s2=sorted(map(str, ss["s2_states"])) == sorted(map(str, sp["s2_states"])),
                                          trajectory=all(ts[k] == tp_[k] for k in PK)))
                for i in NP.INTERFACES:
                    (qa, sa, ta), (qb, sb, tb) = runs[i], runs[f"poisoned_{i}"]
                    out["poison"].append(dict(key, interface=i, ok=qa == qb and sa["fields"] == sb["fields"] and
                                              all(ta[k] == tb[k] for k in PK + ("receipts_sha256",))))
    return out, recs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", required=True)
    ap.add_argument("--set", required=True)
    ap.add_argument("--stage", required=True)
    ap.add_argument("--require-freeze", action="store_true")
    a = ap.parse_args()
    hub = Path(a.hub)
    src = release_source_hash(ROOT)
    if a.require_freeze:
        fz = json.loads((hub / "config" / "FROZEN-PROTOCOL.json").read_text())
        if fz["source_sha256"] != src:
            raise SystemExit(f"source {src} differs from the frozen {fz['source_sha256']}")
    od = hub / "stages" / a.stage / "eval"
    if (od / "trajectories.jsonl").exists():
        raise SystemExit(f"{od} already evaluated")
    od.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    out, recs = evaluate(hub, a.set, a.stage)
    tr = out["trajectories"]
    meta = {"set": a.set, "stage": a.stage, "source_sha256": src, "decision_trajectories": len(tr),
            "by_channel": {c: sum(t["channel"] == c for t in tr) for c in CHANNELS},
            "verification_runs": {"perfect_and_poisoned": 3 * len(out["parity"]),
                                  "leakage": sum(len(v) for r in out["leakage"] for v in r["by_list"].values())},
            "call_records": len(recs), "call_status": {s: sum(r.get("status") == s for r in recs.values())
                                                       for s in sorted({r.get("status") for r in recs.values()})},
            "model_calls_in_this_step": 0, "cpu_wall_s": time.perf_counter() - t0,
            "max_support": max(t["max_set"] for t in tr), "limit_exceeded": sum(t["status"] == "limit_exceeded" for t in tr)}
    for name, rows in out.items():
        with open(od / f"{name}.jsonl", "w") as fh:
            for r in rows:
                fh.write(json.dumps(r, default=str, sort_keys=True) + "\n")
    (od / "EVAL-META.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(json.dumps(meta))


if __name__ == "__main__":
    main()
