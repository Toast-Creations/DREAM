"""Evaluate a completed (or partial) V1.15.0 extraction stage on CPU (no model).
Usage: ftx_evaluate.py --hub HUB --set SET --stage STAGE [--require-freeze]
Per world: one goal-blind text channel from the stored replies (shared by every text clone), plus the perfect-
extraction channel (canonical public records through the same ingestion path; no-model protection). Per goal,
environment, channel (structured / text) and selector (BASE / DEPENDENCY): Q0 from that channel, S2 and selection
from that channel, one DEFER-clock trajectory from that channel's log, and the independent reference given the same
evidence. Also: the independent selector check, perfect-channel parity, gold-poisoning invariance and hidden-tape
leakage (four alternative tapes) for every distinct field list.
Writes HUB/stages/STAGE/eval/{channels,selections,selcheck,trajectories,reference,parity,poison,leakage,
feasibility,extraction}.jsonl and EVAL-META.json. A missing or non-ok call reply enters as None (unprocessed)."""
import argparse
import copy
import json
import time
from pathlib import Path

from _bootstrap import ROOT
from dream_core.ledger import release_source_hash
from tempo import freshness as F, ftxgen as XG, textdep as TD, timing as TM
from contract_validate import score_record
from timing_run import full_domain

ROLES = ("A", "B")
PKEYS = ("queried", "states_sha256", "plan", "candidates", "success", "utility_base", "outcome_kind", "status")


def load(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]


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
    rows = {r[0]: (d, r) for d, r, _ in XG.specs(set_name, 0, smoke=set_name.endswith("smoke"))}
    out = {k: [] for k in ("channels", "selections", "selcheck", "trajectories", "reference", "parity", "poison",
                           "leakage", "feasibility", "extraction")}
    for pub in pubs:
        wid, domain = pub["world_id"], pub["domain"]
        hid, tx = hids[wid], txt[wid]
        cids = tx["call_ids"]
        raws = [recs[c]["raw"] if c in recs and recs[c].get("status") == "ok" else None for c in cids]
        ch_text = TD.build_channel(wid, pub["spec"], raws, tx["registries"], tx["texts"], tx["received"])
        ch_perf = TD.build_channel(wid, pub["spec"], TD.perfect_raws([gold[c]["gold"] for c in cids]),
                                   tx["registries"], tx["texts"], tx["received"])
        if not all(r["accepted"] for r in ch_perf["rows"]):
            raise AssertionError(f"{wid}: perfect extraction not accepted")
        out["channels"].append({"world": wid, "domain": domain, "n_reports": len(cids), "rows": ch_text["rows"],
                                "sequence": ch_text["sequence"],
                                "missing_replies": [c for c, r in zip(cids, raws) if r is None]})
        for c, row in zip(cids, ch_text["rows"]):
            sc = score_record(row["report"], gold[c]["gold"], gold[c]["text"])
            rec = recs.get(c) or {}
            out["extraction"].append({"call_id": c, "world": wid, "domain": domain, "k": row["k"],
                                      "gold_kind": gold[c]["gold"]["kind"], "gold_status": gold[c]["gold"]["status"],
                                      "accepted": row["accepted"], "code": row["code"], "adapter_log": row["adapter_log"],
                                      "parsed": row["adapter_log"]["parse_error"] is None and row["raw"] is not None,
                                      "mapped": row["report"] is not None, **sc,
                                      "status_wrong": bool(row["report"]) and row["report"]["status"] != gold[c]["gold"]["status"],
                                      "call_status": rec.get("status"), "output_tokens": rec.get("output_tokens"),
                                      "input_tokens": rec.get("input_tokens"), "seconds": rec.get("seconds"),
                                      "stop": rec.get("stop")})
        w = XG.build(rows[wid][1], domain, hid["seed"], set_name)[0]
        for role in ROLES:
            ep_s, gc, env_ep = XG.goal_copy(pub, hid, role)
            ep_t = TD.text_copy(ep_s)
            poisoned = copy.deepcopy(ep_s)
            for r in poisoned["reports"]:
                r["assertions"] = []
            for env in TM.ENVS:
                key = {"world": wid, "domain": domain, "role": role, "env": env}
                sc_ = TM.schedule_clock("DEFER")
                envo = TM.environment(env_ep, env, pub["transitions"], hid["tape"], sc_)
                out["feasibility"].append(dict(key, optimum_at_origin=full_domain(w, domain, gc["goal"], envo.state_at(TM.ORIGIN)[0]),
                                               optimum_at_action=full_domain(w, domain, gc["goal"], envo.state_at(16)[0])))
                per = {}
                for chn, ep, ch in (("structured", ep_s, None), ("text", ep_t, ch_text), ("perfect", ep_t, ch_perf),
                                    ("text_poisoned", poisoned, ch_text)):
                    q0 = F.p2_request(ep, gc, ch)["fields"]
                    sel = TD.selection_for(ep, gc, q0, env, ch)
                    trajs = {}
                    for s in TD.SELECTORS:
                        tag = f"|{chn if chn in ('structured', 'text') else chn}|{s}"
                        trajs[s] = TD.run(ep, gc, sel["fields"][s], env, env_ep, hid["tape"], ch,
                                          f"|{'text' if chn != 'structured' else 'structured'}|{s}")
                    per[chn] = (q0, sel, trajs)
                    if chn not in ("structured", "text"):
                        continue
                    ref = TD.selection_reference(ep, gc, q0, env, ch)
                    sk = lambda S: sorted(json.dumps(sorted(x.items())) for x in S)
                    ok = {"s2": sk(sel["s2_states"]) == sk(ref["s2_states"]), "R": sel["R"] == ref["R"],
                          "D": sel["D"] == ref["D"], "DEPENDENCY": sel["fields"]["DEPENDENCY"] == ref["DEPENDENCY"]}
                    out["selcheck"].append(dict(key, channel=chn, ok=ok, all_ok=all(ok.values())))
                    out["selections"].append(dict(key, channel=chn, **{k: v for k, v in sel.items()}))
                    for s, t in trajs.items():
                        rf = TD.reference(ep, gc, t, env, ch)
                        out["reference"].append(dict(key, channel=chn, selector=s, states=rf["states"],
                                                     classes=rf["classes"], choice=rf["choice"]))
                        out["trajectories"].append(dict(t, **key, channel=chn, selector=s, Q0=q0, fields=sel["fields"][s],
                                                        added_fields=[f for f in sel["fields"][s] if f not in q0],
                                                        e=sel["e"], R=sel["R"], D=sel["D"], relevant=gc["relevant"],
                                                        label=hid["labels"][role]))
                    if env == "changing":
                        lrow = dict(key, channel=chn, by_list={})
                        for s in TD.SELECTORS:
                            lrow["by_list"][s] = {}
                            for tn, tp in alt_tapes(hid, pub["transitions"]).items():
                                o = TD.run(ep, gc, sel["fields"][s], env, env_ep, tp, ch, f"|leak|{chn}|{s}|{tn}")
                                lrow["by_list"][s][tn] = {"readings": [(r["field"], r["value"]) for r in o["readings"]],
                                                          "states_sha256": o["states_sha256"], "plan": o["plan"],
                                                          "queried": o["queried"]}
                        out["leakage"].append(lrow)
                q_s, s_s, t_s = per["structured"]
                q_p, s_p, t_p = per["perfect"]
                out["parity"].append(dict(key, q0=q_s == q_p, fields=s_s["fields"] == s_p["fields"],
                                          s2=sorted(map(str, s_s["s2_states"])) == sorted(map(str, s_p["s2_states"])),
                                          trajectories={s: {k: t_s[s][k] == t_p[s][k] for k in PKEYS} for s in TD.SELECTORS}))
                q_t, s_t, t_t = per["text"]
                q_x, s_x, t_x = per["text_poisoned"]
                out["poison"].append(dict(key, q0=q_t == q_x, fields=s_t["fields"] == s_x["fields"],
                                          trajectories={s: all(t_t[s][k] == t_x[s][k] for k in PKEYS + ("receipts_sha256",))
                                                        for s in TD.SELECTORS}))
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
    t0, c0 = time.perf_counter(), time.process_time()
    out, recs = evaluate(hub, a.set, a.stage)
    tr = out["trajectories"]
    meta = {"set": a.set, "stage": a.stage, "source_sha256": src, "rule": TD.RULE,
            "decision_trajectories": len(tr), "by_channel": {c: sum(t["channel"] == c for t in tr) for c in TD.CHANNELS},
            "verification_runs": {"perfect_and_poisoned": 4 * len(out["parity"]),
                                  "leakage": sum(len(v) for r in out["leakage"] for v in r["by_list"].values())},
            "call_records": len(recs), "call_status": {s: sum(r.get("status") == s for r in recs.values())
                                                       for s in sorted({r.get("status") for r in recs.values()})},
            "model_calls_in_this_step": 0, "cpu_wall_s": time.perf_counter() - t0, "cpu_s": time.process_time() - c0,
            "max_support": max(t["max_set"] for t in tr), "limit_exceeded": sum(t["status"] == "limit_exceeded" for t in tr),
            "started": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    for name, rows in out.items():
        with open(od / f"{name}.jsonl", "w") as fh:
            for r in rows:
                fh.write(json.dumps(r, default=str, sort_keys=True) + "\n")
    (od / "EVAL-META.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(json.dumps(meta))


if __name__ == "__main__":
    main()
