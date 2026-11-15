"""State engine v0.1 validation on saved development artifacts (no model calls).

Usage: engine_validate.py --out DIR [--runs $DREAM_RUNS]
Expected values come from the generators' independent implementations (resolver 1 vs 2, worlds.apply_own vs keycheck,
ectx.world vs keycheck plan solvers) as committed in the saved groups/worlds; the engine is a separate
implementation fed only public records and printed fixed facts. Saved model replies are audited: raw reply, engine
decision and engine successor are kept side by side, and the engine never takes a model boolean as authority.
Writes DIR/VALIDATION.json and DIR/VALIDATION.md.
"""
import argparse
import collections
import json
from pathlib import Path

from _bootstrap import ROOT  # noqa: F401
from dream_core import localpaths as LP  # public release: local paths from environment
from tempo import engine as E, engine_fixtures as F, score as S

NOW = 12


def load(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]


def summary_asked(view, asked):
    return {f: view["per_field"][f] for f in asked}


def action_of(world, domain):
    return ["take", world["x"]] if domain == "delivery" else ["install", world["g"], world["t"]]


def goal_ok(world, domain, s):
    if domain == "delivery":
        return s.get(f"{world['goal']['item']}.location") == world["goal"]["place"]
    p = s.get(f"{world['goal']['slot']}.part")
    return p not in (None, E.EMPTY) and world["parts"].get(p, {}).get("rating", -1) >= world["goal"]["min_rating"]


def plan_guaranteed(eng, world, domain, plan):
    b = eng.branch(NOW)
    for s in b.states:
        cur = E.Branch([s], b.base_version)
        for step in plan:
            st = ["put", step[1]] if step[0] == "put" else list(step)
            if eng.check_action(cur, st)["verdict"] != "allowed":
                return False
            cur = eng.predict_action(cur, st)
        if not goal_ok(world, domain, cur.states[0]):
            return False
    return True


def a0_compare(eng, world, domain, gold_a0, asked):
    b = eng.branch(NOW)
    act = action_of(world, domain)
    chk = eng.check_action(b, act)
    succ = eng.predict_action(b, act).summary()
    v_eng = {"allowed": True, "blocked": False, "unresolved": "unknown"}[chk["verdict"]]
    ok_app = v_eng == gold_a0["applicable"]
    ok_succ = all(succ[f] == gold_a0["predicted"][f] for f in asked)
    ok_obs = all(eng.view("current", NOW)["per_field"][f] == gold_a0["observed"][f] for f in asked)
    unchanged = eng.log.version == b.base_version
    return ok_app, ok_succ, ok_obs, unchanged, chk


def pilot(runs, out, dis):
    hub = runs / "temporal-pilot-20261104-232811"
    c = collections.Counter()
    for set_ in ("main", "smoke"):
        for g in load(hub / "data" / f"{set_}-groups.jsonl"):
            w, dom = g["world"], g["domain"]
            for L, var in g["variants"].items():
                for vk in ("a", "b", "i"):
                    recs = var[vk]["records"]
                    eng = F.engine_for(w, dom, recs, context=f"{g['group_id']}|{L}|{vk}")
                    gold = F.flat_now_state(var[vk]["now_state"])
                    got = eng.view("current", NOW)["per_field"]
                    c["current_state_variants"] += 1
                    if any(got[f] != gold[f] for f in gold):
                        dis.append(("current", g["group_id"], L, vk))
                    else:
                        c["current_state_agree"] += 1
                    for key, plan in w["plans"].items():
                        want = var[vk]["plan_status"][key]["guaranteed"]
                        c["plan_checks"] += 1
                        if plan_guaranteed(eng, w, dom, plan) != want:
                            dis.append(("plan", g["group_id"], L, vk, key))
                        else:
                            c["plan_agree"] += 1
                eng = F.engine_for(w, dom, var["a"]["records"], context=f"{g['group_id']}|{L}|a2")
                retro = summary_asked(eng.view("retrospective", g["p0_time"]), g["asked"])
                early = summary_asked(eng.view("earlier", g["p0_time"], cutoff=g["k0_cutoff"]), g["asked"])
                c["P0"] += 1; c["K0"] += 1
                c["P0_agree"] += retro == var["P0"]
                c["K0_agree"] += early == var["K0"]
                if retro != var["P0"]:
                    dis.append(("P0", g["group_id"], L))
                if early != var["K0"]:
                    dis.append(("K0", g["group_id"], L))
                ok = a0_compare(eng, w, dom, var["A0"], g["asked"])
                c["A0"] += 1
                c["A0_agree"] += all(ok[:4])
                if not all(ok[:4]):
                    dis.append(("A0", g["group_id"], L, ok[:4]))
    return dict(c)


def parse_reply(raw, gold, condition):
    obj, err = S.parse_object(raw or "")
    if err is not None:
        return None
    rest = {k: obj.get(k) for k in ("applicable", "predicted_next_facts", "observed_world_facts")}
    r = S.score_action(json.dumps(rest), gold["allowed"], gold)
    if r["predicted"] is None:
        return None
    return {"applicable": r["applicable"], "predicted": {f: v["got"] for f, v in r["predicted"].items()},
            "valid": r["valid"]}


def audit_rows(rows, label, aud):
    """rows: (engine, world, domain, gold_a0, asked, row_kind, raw_reply, condition)."""
    for eng, w, dom, gold, asked, rk, raw, cond in rows:
        cur = eng.view("current", NOW)["per_field"]
        parsed = parse_reply(raw, gold, cond) if raw is not None else None
        a = E.audit_model_action(eng, NOW, action_of(w, dom), raw, parsed)
        key = (label, rk)
        aud[key]["rows"] += 1
        v = a["engine_check"]["verdict"]
        aud[key][f"engine_{v}"] += 1
        if v == "blocked":
            aud[key]["engine_blocked_successor_equals_current"] += all(a["engine_successor"][f] == cur[f]
                                                                         for f in asked)
        aud[key]["engine_matches_gold"] += (all(a["engine_successor"][f] == gold["predicted"][f] for f in asked)
                                            and {"allowed": True, "blocked": False, "unresolved": "unknown"}[v]
                                            == gold["applicable"])
        aud[key]["log_unchanged"] += a["log_version_unchanged"]
        if parsed is None:
            aud[key]["model_reply_unparsed"] += 1
            continue
        aud[key][f"model_said_{E.UNKNOWN if parsed['applicable'] == E.UNKNOWN else parsed['applicable']}"] += 1
        mp = parsed["predicted"]
        differs = any(mp.get(f) != a["engine_successor"][f] for f in asked)
        aud[key]["model_successor_differs_from_engine"] += differs
        if v == "blocked":
            eff = any(mp.get(f) is not None and mp.get(f) != cur[f] for f in gold["effect_fields"])
            aud[key]["model_described_effects_on_blocked"] += eff
            aud[key]["model_said_false_but_described_effects"] += eff and parsed["applicable"] is False


def probe_audit(runs, aud, dis, c):
    hub = runs / "temporal-precondition-probe-20261105-085932"
    calls = {x["call_id"]: x for x in load(hub / "data" / "probe-calls.jsonl")}
    gold = {x["call_id"]: x for x in load(hub / "data" / "probe-gold.jsonl")}
    worlds = {x["world_id"]: x for x in load(hub / "data" / "probe-worlds.jsonl")}
    raws = {}
    for p in (hub / "stages" / "main" / "calls").glob("*.json"):
        r = json.loads(p.read_text()); raws[r["call_id"]] = r["raw"]
    rows = []
    for wid, wr in worlds.items():
        for rk, row in wr["rows"].items():
            eng = F.engine_for(wr["world"], wr["domain"], row["records"], context=f"{wid}|{rk}")
            ok = a0_compare(eng, wr["world"], wr["domain"], row["a0"], wr["asked"])
            chk = ok[4]
            c["probe_rows"] += 1
            c["probe_rows_agree"] += all(ok[:4])
            pv = {k: chk["prerequisites"][k] for k in row["predicates"]}
            c["probe_predicates_agree"] += pv == row["predicates"]
            if not all(ok[:4]) or pv != row["predicates"]:
                dis.append(("probe", wid, rk, ok[:4], pv, row["predicates"]))
    for cid, call in calls.items():
        wr = worlds[call["group_id"]]
        row = wr["rows"][call["row"]]
        eng = F.engine_for(wr["world"], wr["domain"], row["records"], context=cid)
        rows.append((eng, wr["world"], wr["domain"], gold[cid], wr["asked"], call["row"], raws.get(cid),
                     call["condition"]))
        rows[-1] = rows[-1]
    by = collections.defaultdict(list)
    for r, cid in zip(rows, calls):
        by[f"probe {calls[cid]['condition']}:{calls[cid]['arm']}"].append(r)
    for label, rs in by.items():
        audit_rows(rs, label, aud)


def diag_audit(runs, aud, dis, c):
    import diag_generate as DG
    from tempo import diag as D
    pilot = runs / "temporal-pilot-20261104-232811"
    hub = runs / "temporal-diagnostic-20261105-081325"
    calls = {x["call_id"]: x for x in load(hub / "data" / "diag-calls.jsonl") if x["block"] == "D"}
    gold = {x["call_id"]: x for x in load(hub / "data" / "diag-gold.jsonl")}
    raws = {}
    for p in (hub / "stages" / "diag1" / "calls").glob("*D__C*.json"):
        r = json.loads(p.read_text()); raws[r["call_id"]] = r["raw"]
    built = {g["group_id"]: (w, g) for w, g in DG.rebuild(pilot / "data", "main")[1]}
    stored = {g["group_id"]: g for g in load(pilot / "data" / "main-groups.jsonl")}
    by = collections.defaultdict(list)
    for cid, call in calls.items():
        w, g = built[call["group_id"]]
        if call["variant"] == "uncertain":
            recs = g["variants"]["short"]["a"]["records"]
        else:
            recs = D.d_variants(w, g)[call["variant"]]["records"]
        wd = stored[call["group_id"]]["world"]
        eng = F.engine_for(wd, call["domain"], recs, context=cid)
        ok = a0_compare(eng, wd, call["domain"], gold[cid], g["asked"])
        c["diag_D_rows"] += 1
        c["diag_D_agree"] += all(ok[:4])
        if not all(ok[:4]):
            dis.append(("diagD", cid, ok[:4]))
        by[f"diag D:{call['arm']}"].append((eng, wd, call["domain"], gold[cid], g["asked"], call["variant"],
                                             raws.get(cid), "direct"))
    for label, rs in by.items():
        audit_rows(rs, label, aud)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--runs", default=f"{LP.RUNS}")
    a = ap.parse_args()
    runs, out = Path(a.runs), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    dis = []
    c = collections.Counter(pilot(runs, out, dis))
    aud = collections.defaultdict(collections.Counter)
    probe_audit(runs, aud, dis, c)
    diag_audit(runs, aud, dis, c)
    res = {"engine_version": E.ENGINE_VERSION, "fixture_agreement": dict(c), "disagreements": dis[:50],
           "n_disagreements": len(dis),
           "audit": {f"{k[0]} | {k[1]}": dict(v) for k, v in sorted(aud.items())}}
    (out / "VALIDATION.json").write_text(json.dumps(res, indent=1, default=str) + "\n")
    L = ["# Engine v0.1 fixture validation (generated)", "", f"Disagreements: {len(dis)}", "",
         "| Check | agree / total |", "|---|---|"]
    for k, tot in (("current_state", "current_state_variants"), ("plan", "plan_checks"), ("P0", "P0"),
                   ("K0", "K0"), ("A0", "A0"), ("probe_rows", "probe_rows"), ("probe_predicates", "probe_rows"),
                   ("diag_D", "diag_D_rows")):
        L.append(f"| {k} | {c[k + '_agree']} / {c[tot]} |")
    L += ["", "## Saved model replies audited against the engine", "",
          "| Source | row | rows | engine verdicts | model applicability | model successor ≠ engine | blocked: model described effects (of which model said false) | engine blocked successor = current | log unchanged |",
          "|---|---|---|---|---|---|---|---|---|"]
    for k, v in sorted(aud.items()):
        ev = {x[7:]: v[x] for x in v if x.startswith("engine_") and x[7:] in ("allowed", "blocked", "unresolved")}
        ms = {x[11:]: v[x] for x in v if x.startswith("model_said_") and "described" not in x}
        L.append(f"| {k[0]} | {k[1]} | {v['rows']} | {ev} | {ms} | {v['model_successor_differs_from_engine']} | "
                 f"{v['model_described_effects_on_blocked']} ({v['model_said_false_but_described_effects']}) | "
                 f"{v['engine_blocked_successor_equals_current']}/{ev.get('blocked', 0)} | {v['log_unchanged']}/{v['rows']} |")
    (out / "VALIDATION.md").write_text("\n".join(L) + "\n")
    print("\n".join(L[:14]))


if __name__ == "__main__":
    main()
