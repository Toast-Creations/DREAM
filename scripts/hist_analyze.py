"""Milestone 2 analysis: run systems S (structured), X (per-record extraction) and R (full-history readout) through
state engine v0.1 and score them (development; descriptive only).

Usage: hist_analyze.py --hub HUB --set hist|histsmoke --stage STAGE [--boot 10000] [--seed 20261105]
Writes HUB/analysis-<set>/{records.jsonl, checkpoints.jsonl, ANALYSIS.json, TABLES.md}.

X normaliser (fixed, part of system X): JSON parse (one optional code fence); values matched to the field's allowed
list case-insensitively with surrounding spaces, a trailing full stop and an entity word ("crate ", "part ", ...)
ignored (score.match_value); field names, kinds, statuses, rids and integer times must match exactly. The
normalised record goes to the engine unchanged; a rejection is kept as an extraction failure and the system carries
on without that record. Nothing is replaced by gold.
R: readout parsed by score.score_facts; "unknown" -> every allowed value; an invalid reply -> every field unknown.
"""
import argparse
import collections
import itertools
import json
from pathlib import Path

from _bootstrap import ROOT  # noqa: F401
from tempo_analyze import bootstrap, domain_weighted, load, mean
from tempo import engine as E, engine_fixtures as EF, history as Hm, score as S
from tempo.worlds import UNKNOWN

SOURCE = "extractor:qwen3-8b"
VERD = ("allowed", "blocked", "unresolved")


def records_of(stage):
    out = {}
    if stage.exists():
        for p in (stage / "calls").glob("*.json"):
            r = json.loads(p.read_text()); out[r["call_id"]] = r
    return out


def normalise(obj, registry):
    """Model JSON -> engine record dict (or None if not a dict). Unknown fields/values pass through unchanged so the
    engine rejects them."""
    if not isinstance(obj, dict):
        return None
    rec = {k: obj.get(k) for k in ("rid", "kind", "status", "event_at", "received_at")}
    rec["payload"] = obj.get("payload")
    rec["source"] = SOURCE
    if isinstance(obj.get("evidence"), str):
        rec["evidence"] = obj["evidence"]
    p = rec["payload"]

    def nv(f, v):
        m = S.match_value(v, registry[f]) if f in registry else None
        return m if m is not None else v
    if isinstance(p, dict):
        p = dict(p)
        if isinstance(p.get("assign"), dict):
            p["assign"] = {f: nv(f, v) for f, v in p["assign"].items()}
        f = p.get("field")
        if isinstance(f, str):
            for key in ("value", "from", "to"):
                if key in p:
                    p[key] = nv(f, p[key])
            if isinstance(p.get("options"), list):
                p["options"] = [nv(f, x) for x in p["options"]]
        rec["payload"] = p
    return rec


def compare_record(got, gold, text):
    """Field-level comparison of a normalised extraction with the gold public record."""
    if got is None:
        return {"parsed": False, "exact": False, "errors": ["unparsed"]}
    gp, mp = gold["payload"], got.get("payload") if isinstance(got.get("payload"), dict) else {}
    c = {"parsed": True, "rid": got.get("rid") == gold["rid"], "kind": got.get("kind") == gold["kind"],
         "status": got.get("status") == gold["status"], "event_at": got.get("event_at") == gold["event_at"],
         "received_at": got.get("received_at") == gold["received_at"]}
    if gold["kind"] == "initial":
        ga, ma = gp["assign"], mp.get("assign") if isinstance(mp.get("assign"), dict) else {}
        c["field"] = set(ma) == set(ga)
        c["value"] = c["field"] and all(ma[f] == ga[f] for f in ga)
    else:
        c["field"] = mp.get("field") == gp["field"]
        vk = {"observation": ["value"], "change": ["from", "to"], "uncertain_change": ["from", "options"],
              "correction": ["value"]}[gold["kind"]]
        c["value"] = all((sorted(mp.get(k) or []) == sorted(gp[k])) if k == "options" else mp.get(k) == gp[k]
                         for k in vk)
    if gold["kind"] == "correction":
        c["target"] = mp.get("target") == gp["target"]
        c["valid_from"] = mp.get("valid_from") == gp["valid_from"]
    c["payload_keys"] = set(mp) == set(gp)
    c["exact"] = all(v for k, v in c.items() if k != "parsed")
    ev = got.get("evidence")
    c["evidence_linked"] = isinstance(ev, str) and len(ev.strip()) > 0 and ev.strip() in text
    c["errors"] = [k for k in ("kind", "field", "value", "event_at", "received_at", "status", "target", "valid_from",
                               "rid", "payload_keys") if k in c and not c[k]]
    return c


def score_state(state, gold, asked):
    out = {"exact": True, "correct": 0, "false_unknown": 0, "false_certainty": 0, "wrong_definite": 0, "missing": 0}
    for f in asked:
        g, v = gold[f], state.get(f, "missing")
        if v == g:
            out["correct"] += 1
            continue
        out["exact"] = False
        if v in ("missing", None, "invalid"):
            out["missing"] += 1
        elif v == UNKNOWN:
            out["false_unknown"] += 1
        elif g == UNKNOWN:
            out["false_certainty"] += 1
        else:
            out["wrong_definite"] += 1
    out["n"] = len(asked)
    return out


def checks(eng, branch, tests):
    head = eng.log.head()
    out = []
    for t in tests:
        v = eng.check_action(branch, t["action"])["verdict"]
        out.append({"action": t["action"], "verdict": v, "gold_verdict": t["gold_verdict"],
                    "true_legal": t["true_legal"], "correct": v == t["gold_verdict"],
                    "wrongly_allowed": v == "allowed" and not t["true_legal"],
                    "wrongly_blocked": v == "blocked" and t["true_legal"]})
    return out, eng.log.head() == head


def run_engine_system(h, recs_in, label, rec_rows):
    """recs_in: list of k -> record dict or None (per arriving record). Returns checkpoint rows."""
    spec = EF.spec_from_world(h["world"], h["domain"], h["records"])
    eng = E.Engine(spec, context=f"{h['history_id']}|{label}")
    cps = {cp["k"]: cp for cp in h["checkpoints"]}
    rows = []
    for k, r in enumerate(recs_in, 1):
        acc, reason = False, None
        if r is None:
            reason = "no record (unparsed or missing)"
        else:
            try:
                eng.ingest_report(r)
                acc = True
            except (E.RecordRejected, E.EngineError, KeyError, TypeError, ValueError, AttributeError) as e:
                reason = f"{type(e).__name__}: {e}"[:300]
        if rec_rows is not None:
            rec_rows[k - 1].update(engine_accepted=acc, engine_reason=reason)
        if k in cps:
            cp = cps[k]
            view = eng.view("current", cp["now"])
            st = {f: view["per_field"].get(f, "missing") for f in h["asked"]}
            tests, unchanged = checks(eng, eng.branch(cp["now"]), cp["tests"])
            rows.append({"history_id": h["history_id"], "domain": h["domain"], "pattern": h["pattern"],
                         "system": label, "k": k, "state": st,
                         "score": score_state(st, cp["gold_state"], h["asked"]), "tests": tests,
                         "log_unchanged_by_tests": unchanged, "records_in_log": eng.log.version})
    return rows


def run_readout(h, cp, raw, gold_row):
    asked = h["asked"]
    r = S.score_facts(raw or "", gold_row["allowed"], gold_row["gold"])
    st = {}
    for f in asked:
        got = (r["fields"] or {}).get(f, {}).get("got") if r["valid"] else None
        st[f] = got if got is not None else (UNKNOWN if r["valid"] else "invalid")
    spec = EF.spec_from_world(h["world"], h["domain"], h["records"])
    eng = E.Engine(spec, context=f"{h['history_id']}|R|cp{cp['k']}")
    allowed = gold_row["allowed"]
    choices = [[st[f]] if st[f] not in (UNKNOWN, "invalid") else [x for x in allowed[f] if x != UNKNOWN] for f in asked]
    states = [dict(zip(asked, c)) for c in itertools.product(*choices)]
    if h["domain"] == "delivery":
        states = [dict(s, **{"agent.at": spec["agent_at"]}) for s in states]
    tests, unchanged = checks(eng, E.Branch(states, 0), cp["tests"])
    return {"history_id": h["history_id"], "domain": h["domain"], "pattern": h["pattern"], "system": "R",
            "k": cp["k"], "state": st, "reply_valid": r["valid"], "score": score_state(st, cp["gold_state"], asked),
            "tests": tests, "log_unchanged_by_tests": unchanged}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", required=True)
    ap.add_argument("--set", required=True)
    ap.add_argument("--stage", required=True)
    ap.add_argument("--boot", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=20261105)
    a = ap.parse_args()
    hub = Path(a.hub)
    hs = load(hub / "data" / f"{a.set}-histories.jsonl")
    calls = {c["call_id"]: c for c in load(hub / "data" / f"{a.set}-calls.jsonl")}
    gold = {g["call_id"]: g for g in load(hub / "data" / f"{a.set}-gold.jsonl")}
    recs = records_of(hub / "stages" / a.stage)
    rec_rows, cp_rows = [], []
    for h in hs:
        hid = h["history_id"]
        cp_rows += run_engine_system(h, [dict(r, source="env") for r in h["public_records"]], "S", None)
        xs = [f"{hid}|X|r{k}" for k in range(1, Hm.N_RECORDS + 1)]
        if all(x in calls for x in xs):
            rows, ins = [], []
            for k, cid in enumerate(xs, 1):
                rr = recs.get(cid)
                raw = rr["raw"] if rr and rr["status"] == "ok" else None
                obj, err = S.parse_object(raw) if raw is not None else (None, "missing")
                norm = normalise(obj, gold[cid]["registry"]) if err is None else None
                cmpr = compare_record(norm, gold[cid]["gold"], gold[cid]["text"])
                rows.append({"call_id": cid, "history_id": hid, "domain": h["domain"], "pattern": h["pattern"],
                             "k": k, "gold_kind": gold[cid]["gold"]["kind"], "status": rr["status"] if rr else "missing",
                             "parse_error": err, "raw": raw, "normalised": norm, **cmpr,
                             "output_tokens": rr.get("output_tokens") if rr else None,
                             "seconds": rr.get("seconds") if rr else None, "stop": rr.get("stop") if rr else None})
                ins.append(norm)
            cp_rows += run_engine_system(h, ins, "X", rows)
            rec_rows += rows
        for cp in h["checkpoints"]:
            cid = f"{hid}|R|cp{cp['k']}"
            if cid in calls:
                rr = recs.get(cid)
                row = run_readout(h, cp, rr["raw"] if rr and rr["status"] == "ok" else None, gold[cid])
                row.update(status=rr["status"] if rr else "missing", output_tokens=rr.get("output_tokens") if rr else None,
                           seconds=rr.get("seconds") if rr else None, stop=rr.get("stop") if rr else None)
                cp_rows.append(row)
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

    res = {"set": a.set, "stage": a.stage, "calls": len(calls),
           "call_status": dict(collections.Counter((recs.get(c) or {}).get("status", "missing") for c in calls)),
           "truncated": sum(1 for r in recs.values() if r.get("stop") == "length"),
           "input_tokens_max": max([r["input_tokens"] for r in recs.values()] or [0]),
           "output_tokens": {s: sum((recs.get(c) or {}).get("output_tokens") or 0 for c in calls
                                    if calls[c]["system_name"] == s) for s in ("X", "R")},
           "seconds": {s: round(sum((recs.get(c) or {}).get("seconds") or 0 for c in calls
                                    if calls[c]["system_name"] == s), 1) for s in ("X", "R")}}
    # X records
    if rec_rows:
        keys = ("parsed", "kind", "field", "value", "event_at", "received_at", "status", "rid", "exact",
                "evidence_linked", "engine_accepted")
        res["X_records"] = {"n": len(rec_rows), **{k: sum(1 for r in rec_rows if r.get(k)) for k in keys},
                            "corrections": f"{sum(1 for r in rec_rows if r['gold_kind'] == 'correction' and r.get('target') and r.get('valid_from'))}/{sum(1 for r in rec_rows if r['gold_kind'] == 'correction')} target+valid_from",
                            "exact_by_kind": {kd: f"{sum(1 for r in rec_rows if r['gold_kind'] == kd and r['exact'])}/{sum(1 for r in rec_rows if r['gold_kind'] == kd)}"
                                              for kd in E.KINDS},
                            "error_classes": dict(collections.Counter(e for r in rec_rows for e in r["errors"])),
                            "accepted_but_wrong": sum(1 for r in rec_rows if r.get("engine_accepted") and not r["exact"]),
                            "rejected": dict(collections.Counter((r.get("engine_reason") or "")[:60] for r in rec_rows
                                                                 if not r.get("engine_accepted")))}
    # checkpoints per system
    systems = {}
    for s in ("S", "X", "R"):
        rows = [r for r in cp_rows if r["system"] == s]
        if not rows:
            continue
        tests = [t for r in rows for t in r["tests"]]
        d = {"checkpoints": len(rows),
             "state_exact": sum(r["score"]["exact"] for r in rows),
             "state_exact_by_k": {k: f"{sum(r['score']['exact'] for r in rows if r['k'] == k)}/{sum(1 for r in rows if r['k'] == k)}" for k in Hm.CHECKPOINTS},
             "fields": f"{sum(r['score']['correct'] for r in rows)}/{sum(r['score']['n'] for r in rows)}",
             **{k: sum(r["score"][k] for r in rows) for k in ("false_unknown", "false_certainty", "wrong_definite", "missing")},
             "state_exact_by_pattern": {p: f"{sum(r['score']['exact'] for r in rows if r['pattern'] == p)}/{sum(1 for r in rows if r['pattern'] == p)}" for p in range(1, 7)},
             "tests": len(tests), "verdict_correct": sum(t["correct"] for t in tests),
             "verdicts": dict(collections.Counter(t["verdict"] for t in tests)),
             "confusion": dict(collections.Counter(f"{t['gold_verdict']}->{t['verdict']}" for t in tests)),
             "wrongly_allowed_vs_truth": sum(t["wrongly_allowed"] for t in tests),
             "wrongly_blocked_vs_truth": sum(t["wrongly_blocked"] for t in tests),
             "log_unchanged_by_tests": f"{sum(r['log_unchanged_by_tests'] for r in rows)}/{len(rows)}"}
        if s == "R":
            d["invalid_replies"] = sum(1 for r in rows if not r["reply_valid"])
        fin = {r["history_id"]: float(r["score"]["exact"]) for r in rows if r["k"] == 6}
        ver = collections.defaultdict(list)
        for r in rows:
            ver[r["history_id"]] += [float(t["correct"]) for t in r["tests"]]
        d["PRIMARY_final_state_exact"] = est(fin)
        d["PRIMARY_verdict_accuracy"] = est({g: mean(v) for g, v in ver.items()})
        d["_fin"], d["_ver"] = fin, {g: mean(v) for g, v in ver.items()}
        systems[s] = d
    con = {}
    for x, y in (("X", "S"), ("R", "S"), ("X", "R")):
        if x in systems and y in systems:
            c = {}
            for key in ("_fin", "_ver"):
                X, Y = systems[x][key], systems[y][key]
                dd = {g: X[g] - Y[g] for g in X if g in Y}
                e = est(dd)
                e.update(better=sum(v > 0 for v in dd.values()), equal=sum(v == 0 for v in dd.values()),
                         worse=sum(v < 0 for v in dd.values()))
                c["final_state_exact" if key == "_fin" else "verdict_accuracy"] = e
            con[f"{x}-{y}"] = c
    for d in systems.values():
        d.pop("_fin"); d.pop("_ver")
    res["systems"], res["contrasts"] = systems, con
    (out / "ANALYSIS.json").write_text(json.dumps(res, indent=1, default=str) + "\n")
    (out / "TABLES.md").write_text(tables(res))
    print(tables(res))


def f(e):
    if not e or e.get("mean") is None:
        return "—"
    ci = e.get("ci95")
    return f"{e['mean']:.3f}" + (f" [{ci[0]:.2f}, {ci[1]:.2f}]" if ci else "")


def tables(res):
    L = ["# Milestone 2 tables (generated)", "", f"Calls {res['calls']}; status {res['call_status']}; truncated "
         f"{res['truncated']}; max input {res['input_tokens_max']}; output tokens {res['output_tokens']}; seconds {res['seconds']}.", ""]
    if "X_records" in res:
        x = res["X_records"]
        L += ["## X typed records", "", "| measure | count |", "|---|---|"] + \
             [f"| {k} | {v} |" for k, v in x.items()]
    L += ["", "## Systems", "", "| System | final state exact | verdict accuracy | state exact (all checkpoints) | by checkpoint | fields | false unknown | false certainty | wrong definite | missing | wrongly allowed vs truth | wrongly blocked vs truth | log unchanged |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for s, d in res["systems"].items():
        L.append(f"| {s} | {f(d['PRIMARY_final_state_exact'])} | {f(d['PRIMARY_verdict_accuracy'])} ({d['verdict_correct']}/{d['tests']}) | "
                 f"{d['state_exact']}/{d['checkpoints']} | {d['state_exact_by_k']} | {d['fields']} | {d['false_unknown']} | "
                 f"{d['false_certainty']} | {d['wrong_definite']} | {d['missing']} | {d['wrongly_allowed_vs_truth']} | "
                 f"{d['wrongly_blocked_vs_truth']} | {d['log_unchanged_by_tests']} |")
    L += ["", "| System | state exact by pattern | verdict confusion (gold->system) |", "|---|---|---|"]
    for s, d in res["systems"].items():
        L.append(f"| {s} | {d['state_exact_by_pattern']} | {d['confusion']} |")
    L += ["", "## Paired contrasts (per history; better / equal / worse)", "",
          "| Contrast | final state exact | verdict accuracy |", "|---|---|---|"]
    for k, c in res["contrasts"].items():
        a, b = c["final_state_exact"], c["verdict_accuracy"]
        L.append(f"| {k} | {f(a)} ({a['better']}/{a['equal']}/{a['worse']}) | {f(b)} ({b['better']}/{b['equal']}/{b['worse']}) |")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
