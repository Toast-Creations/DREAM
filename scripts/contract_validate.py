"""Contract v1 / assertion engine v0.3 validation (no model calls).

Usage: contract_validate.py --out DIR [--runs $DREAM_RUNS]
Part A (fixtures): v0.3 fed canonical contract-v1 reports (assertions.from_v02 of the gold public records) must
  reproduce every committed gold value: current state, retrospective (P0), earlier-information (K0), action verdicts
  (A0 and the three plans), probe requirement verdicts, milestone-2 and prose-study checkpoints.
Part B (unstated prior): every event's "from" removed; views compared with Part A at NOW and at every record time.
Part C (DEVELOPMENT ANALYSIS, post hoc, labelled): the saved model extractions of milestone 2 and of the
  repair/prose study, mapped to contract v1 and replayed through v0.3; scored with the new assertion-coverage and
  temporal-denotation measures. Original exact-schema scores are unchanged and are not replaced.
Writes DIR/CONTRACT-VALIDATION.json and .md.
"""
import argparse
import collections
import json
from pathlib import Path

from _bootstrap import ROOT  # noqa: F401
from dream_core import localpaths as LP  # public release: local paths from environment
from tempo import assertions as A, engine as E, engine_fixtures as EF, score as S
from tempo.worlds import UNKNOWN

NOW = 12


def load(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]


def eng_for(world, domain, records, ctx, transform=None):
    a = A.AssertionEngine(EF.spec_from_world(world, domain, records), ctx)
    for r in records:
        rep = A.from_v02(EF.public_record(r))
        if transform:
            rep = transform(rep)
        a.ingest(rep)
    return a


def flat(view, fields):
    return {f: view["per_field"].get(f, "missing") for f in fields}


def act(world, domain):
    return ["take", world["x"]] if domain == "delivery" else ["install", world["g"], world["t"]]


def goal_ok(world, domain, s):
    if domain == "delivery":
        return s.get(f"{world['goal']['item']}.location") == world["goal"]["place"]
    p = s.get(f"{world['goal']['slot']}.part")
    return p not in (None, E.EMPTY) and world["parts"].get(p, {}).get("rating", -1) >= world["goal"]["min_rating"]


def plan_ok(a, world, domain, plan):
    b = a.branch(NOW)
    for s in b.states:
        cur = E.Branch([s], b.base_version)
        for step in plan:
            if a.check_action(cur, list(step))["verdict"] != "allowed":
                return False
            cur = a.predict_action(cur, list(step))
        if not goal_ok(world, domain, cur.states[0]):
            return False
    return True


def drop_from(rep):
    rep = json.loads(json.dumps(rep))
    if rep["type"] == "event":
        for x in rep["assertions"]:
            x.pop("from", None)
    return rep


def part_a_b(runs, c, dis, unstated):
    pilot = runs / "temporal-pilot-20261104-232811"
    for set_ in ("main", "smoke"):
        for g in load(pilot / "data" / f"{set_}-groups.jsonl"):
            w, dom = g["world"], g["domain"]
            for L, var in g["variants"].items():
                for vk in ("a", "b", "i"):
                    recs = var[vk]["records"]
                    a = eng_for(w, dom, recs, f"{g['group_id']}|{L}|{vk}")
                    gold = EF.flat_now_state(var[vk]["now_state"])
                    c["current"] += 1
                    got = flat(a.view("current", NOW), gold)
                    if got == gold:
                        c["current_agree"] += 1
                    else:
                        dis.append(("current", g["group_id"], L, vk, got, gold))
                    for key, plan in w["plans"].items():
                        c["plans"] += 1
                        if plan_ok(a, w, dom, plan) == var[vk]["plan_status"][key]["guaranteed"]:
                            c["plans_agree"] += 1
                        else:
                            dis.append(("plan", g["group_id"], L, vk, key))
                    # Part B
                    b = eng_for(w, dom, recs, "nofrom", transform=drop_from)
                    times = sorted({r["event_at"] for r in recs if r["event_at"] is not None} | {NOW})
                    for t in times:
                        unstated["views"] += 1
                        va, vb = a.view("retrospective", t), b.view("retrospective", t)
                        if va["per_field"] != vb["per_field"]:
                            unstated["differ"] += 1
                            diff = [f for f in va["per_field"] if va["per_field"][f] != vb["per_field"].get(f)]
                            unstated["examples"].append((g["group_id"], L, vk, t, {f: (va["per_field"][f],
                                                                                         vb["per_field"].get(f)) for f in diff}))
                a = eng_for(w, dom, var["a"]["records"], "a2")
                for q, view in (("P0", a.view("retrospective", g["p0_time"])),
                                ("K0", a.view("earlier", g["p0_time"], cutoff=g["k0_cutoff"]))):
                    c[q] += 1
                    got = flat(view, g["asked"])
                    if got == var[q]:
                        c[q + "_agree"] += 1
                    else:
                        dis.append((q, g["group_id"], L, got, var[q]))
                chk = a.check_action(a.branch(NOW), act(w, dom))
                v = {"allowed": True, "blocked": False, "unresolved": "unknown"}[chk["verdict"]]
                succ = a.predict_action(a.branch(NOW), act(w, dom)).summary()
                c["A0"] += 1
                if v == var["A0"]["applicable"] and all(succ[f] == var["A0"]["predicted"][f] for f in g["asked"]):
                    c["A0_agree"] += 1
                else:
                    dis.append(("A0", g["group_id"], L))
    probe = runs / "temporal-precondition-probe-20261105-085932"
    for wr in load(probe / "data" / "probe-worlds.jsonl"):
        for rk, row in wr["rows"].items():
            a = eng_for(wr["world"], wr["domain"], row["records"], rk)
            chk = a.check_action(a.branch(NOW), act(wr["world"], wr["domain"]))
            v = {"allowed": True, "blocked": False, "unresolved": "unknown"}[chk["verdict"]]
            pv = {k: chk["prerequisites"][k] for k in row["predicates"]}
            c["probe"] += 1
            if v == row["a0"]["applicable"] and pv == row["predicates"]:
                c["probe_agree"] += 1
            else:
                dis.append(("probe", wr["world_id"], rk, v, pv))
    for hub, set_ in (("temporal-history-interpretation-20261105-100708", "hist"),
                      ("temporal-repair-prose-20261105-111843", "prose")):
        for h in load(runs / hub / "data" / f"{set_}-histories.jsonl"):
            for cp in h["checkpoints"]:
                a = eng_for(h["world"], h["domain"], h["records"][:cp["k"]], h["history_id"])
                c[f"{set_}_checkpoints"] += 1
                got = flat(a.view("current", cp["now"]), h["asked"])
                ok = got == {f: cp["gold_state"][f] for f in h["asked"]}
                for t in cp["tests"]:
                    vv = a.check_action(a.branch(cp["now"]), t["action"])["verdict"]
                    ok = ok and vv == t["gold_verdict"]
                c[f"{set_}_checkpoints_agree"] += ok
                if not ok:
                    dis.append((set_, h["history_id"], cp["k"], got))


# ---------------------------------------------------------------- Part C (development analysis)

def source_states_from(gold, text):
    """Does the source text itself state the prior value of this event? (public text only)"""
    p = gold["payload"]
    if gold["kind"] not in ("change", "uncertain_change"):
        return False
    frm = p.get("from")
    if frm is None:
        return False
    if p["field"].endswith(".location"):
        return frm in text
    if p["field"].endswith(".on_hand"):
        return False  # "delivered" / "took" imply but do not state the prior stock value
    return frm != E.EMPTY and frm in text  # slot: "removed part X" / "replaced part X" state it


def atoms(rep, gold_v02=None, text=None, require_from=None):
    out = set()
    if rep is None:
        return out
    for a in rep["assertions"]:
        if rep["type"] == "state":
            out.add(("state", a["field"], a["at"], tuple(sorted(a["options"])) if "options" in a else a["value"]))
        elif rep["type"] == "event":
            to = tuple(sorted(a["to_options"])) if "to_options" in a else a["to"]
            out.add(("event", a["field"], a["at"], to))
            if a.get("from") is not None:
                out.add(("event_from", a["field"], a["at"], a["from"]))
        else:
            out.add(("correction", a["field"], a["target"], a["value"], a["valid_from"]))
    return out


def to_v1(rec):
    """Extracted v0.2-style record -> contract v1 (None if it cannot be mapped)."""
    if not isinstance(rec, dict) or rec.get("kind") not in E.KINDS or not isinstance(rec.get("payload"), dict):
        return None
    try:
        r = dict(rec)
        if r["kind"] == "uncertain_change":
            r["payload"] = dict(r["payload"])
            r["payload"].setdefault("from", None)
            if "options" not in r["payload"]:
                return None
        return A.from_v02({k: r.get(k) for k in ("rid", "kind", "status", "event_at", "received_at", "payload")})
    except (KeyError, TypeError, AttributeError):
        return None


def score_record(ext_v1, gold_rec, text):
    g1 = A.from_v02(gold_rec)
    gat = atoms(g1)
    if not source_states_from(gold_rec, text):
        gat = {x for x in gat if x[0] != "event_from"}
    eat = atoms(ext_v1)
    if ext_v1 is not None and not source_states_from(gold_rec, text):
        extra_from = {x for x in eat if x[0] == "event_from"}
        wrong_from = {x for x in extra_from if x not in atoms(g1)}
        eat = (eat - extra_from) | wrong_from
    cov = len(gat & eat) / len(gat) if gat else 1.0
    meta_ok = ext_v1 is not None and ext_v1["status"] == gold_rec["status"] and \
        ext_v1["received_at"] == gold_rec["received_at"] and ext_v1["rid"] == gold_rec["rid"]
    return {"coverage": cov, "denotation_equal": meta_ok and eat == gat, "type_class_equal":
            ext_v1 is not None and ext_v1["type"] == g1["type"], "spurious": len(eat - gat)}


def replay(h, recs_by_k, ks, ctx):
    a = A.AssertionEngine(EF.spec_from_world(h["world"], h["domain"], h["records"]), ctx)
    rows, snaps = [], {}
    cps = {cp["k"]: cp for cp in h["checkpoints"]}
    for k in ks:
        rep = recs_by_k.get(k)
        acc, code = False, None
        if rep is None:
            code = "unmapped"
        else:
            try:
                a.ingest(dict(rep, source="extractor:qwen3-8b"))
                acc = True
            except A.ContractRejected as e:
                code = e.code
        if not acc:
            a.record_unprocessed(f"r{k:02d}", h["records"][k - 1]["received_at"], h["texts"][k - 1] if "texts" in h
                                 else "", None, code, None)
        rows.append({"k": k, "accepted": acc, "code": code})
        if k in cps:
            cp = cps[k]
            v = a.view("current", cp["now"])
            st = {f: v["complete_per_field"].get(f, "missing") for f in h["asked"]}
            tests = [a.check_action(a.branch(cp["now"]), t["action"])["verdict"] == t["gold_verdict"] for t in cp["tests"]]
            snaps[k] = {"exact": st == {f: cp["gold_state"][f] for f in h["asked"]}, "tests": tests,
                        "conflicts": v["conflict_fields"], "suspended": sorted({s for d in v["detail"].values()
                                                                                 for s in d["suspended"]})}
    return rows, snaps


def part_c(runs):
    out = {}
    # milestone 2 (lines, one pass)
    hub = runs / "temporal-history-interpretation-20261105-100708"
    hs = {h["history_id"]: h for h in load(hub / "data" / "hist-histories.jsonl")}
    gold = {g["call_id"]: g for g in load(hub / "data" / "hist-gold.jsonl")}
    recs = load(hub / "analysis-hist" / "records.jsonl")
    cells = {"milestone2:lines": [(hs[r["history_id"]], r["k"], r["normalised"], gold[r["call_id"]]) for r in recs]}
    hub2 = runs / "temporal-repair-prose-20261105-111843"
    hs2 = {h["history_id"]: h for h in load(hub2 / "data" / "prose-histories.jsonl")}
    gold2 = {g["call_id"]: g for g in load(hub2 / "data" / "prose-gold.jsonl")}
    recs2 = load(hub2 / "analysis-prose" / "records.jsonl")
    for surface in ("lines", "prose"):
        for pol in ("no_retry", "one_retry"):
            sel = [r for r in recs2 if r["surface"] == surface and r["policy"] == pol]
            key = "final" if pol == "one_retry" else "initial"
            cells[f"prose-study:{surface}:{pol}"] = []
            for r in sel:
                rec = None
                raw = r["retry_raw"] if (pol == "one_retry" and r["retried"]) else r["initial_raw"]
                if raw is not None:
                    obj, err = S.parse_object(raw)
                    if err is None:
                        from tempo import repair as RP
                        rec, _ = RP.normalise(obj, gold2[r["call_id"]]["registry"])
                h = dict(hs2[r["history_id"]]); h["texts"] = h["texts"][surface]
                cells[f"prose-study:{surface}:{pol}"].append((h, r["k"], rec, gold2[r["call_id"]]))
    for name, items in cells.items():
        by = collections.defaultdict(dict)
        rs = collections.Counter()
        cov = []
        for h, k, rec, g in items:
            v1 = to_v1(rec)
            by[h["history_id"]][k] = (h, v1)
            sc = score_record(v1, g["gold"], g["text"])
            cov.append(sc["coverage"])
            rs["records"] += 1
            rs["denotation_equal"] += sc["denotation_equal"]
            rs["type_class_equal"] += sc["type_class_equal"]
            rs["full_coverage"] += sc["coverage"] == 1.0
            rs["spurious_assertions"] += sc["spurious"]
            rs["unmapped"] += v1 is None
        fin = 0
        tests = []
        conf = 0
        susp = 0
        for hid, d in by.items():
            h = d[min(d)][0]
            rows, snaps = replay(h, {k: v for k, (_, v) in d.items()}, sorted(d), f"{name}|{hid}")
            rs["structurally_rejected"] += sum(1 for r in rows if not r["accepted"] and r["code"] != "unmapped")
            if 6 in snaps:
                fin += snaps[6]["exact"]
            for s in snaps.values():
                tests += s["tests"]
                conf += len(s["conflicts"])
                susp += len(s["suspended"])
        rs["mean_coverage"] = round(sum(cov) / len(cov), 4)
        out[name] = {**dict(rs), "final_state_exact_v03": f"{fin}/{len(by)}",
                     "verdicts_correct_v03": f"{sum(tests)}/{len(tests)}", "conflict_field_checkpoints": conf,
                     "suspended_provisional_checkpoints": susp}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--runs", default=f"{LP.RUNS}")
    a = ap.parse_args()
    runs, out = Path(a.runs), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    c, dis = collections.Counter(), []
    unstated = {"views": 0, "differ": 0, "examples": []}
    part_a_b(runs, c, dis, unstated)
    pc = part_c(runs)
    res = {"part_A_fixtures": dict(c), "disagreements": dis[:30], "n_disagreements": len(dis),
           "part_B_unstated_prior": {"views": unstated["views"], "differ": unstated["differ"],
                                     "examples": unstated["examples"][:15]},
           "part_C_development_replay": pc}
    (out / "CONTRACT-VALIDATION.json").write_text(json.dumps(res, indent=1, default=str) + "\n")
    L = ["# Contract v1 / engine v0.3 validation (generated)", "", f"Part A disagreements: {len(dis)}", "",
         "| Check | agree / total |", "|---|---|"]
    for k in ("current", "plans", "P0", "K0", "A0", "probe", "hist_checkpoints", "prose_checkpoints"):
        L.append(f"| {k} | {c[k + '_agree']} / {c[k]} |")
    L += ["", f"Part B (every event's 'from' removed): {unstated['differ']} of {unstated['views']} retrospective views differ.",
          "", "## Part C — DEVELOPMENT ANALYSIS (post hoc replay of saved extractions; original scores unchanged)", "",
          "| Cell | records | denotation equal | type class equal | full coverage | mean coverage | spurious | unmapped | structurally rejected | final state exact (v0.3) | verdicts (v0.3) | conflict fields | suspended provisional |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for k, v in pc.items():
        L.append(f"| {k} | {v['records']} | {v['denotation_equal']} | {v['type_class_equal']} | {v['full_coverage']} | "
                 f"{v['mean_coverage']} | {v['spurious_assertions']} | {v['unmapped']} | {v.get('structurally_rejected', 0)} | "
                 f"{v['final_state_exact_v03']} | {v['verdicts_correct_v03']} | {v['conflict_field_checkpoints']} | "
                 f"{v['suspended_provisional_checkpoints']} |")
    (out / "CONTRACT-VALIDATION.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))
    if unstated["examples"]:
        print("B examples:", unstated["examples"][:5])
    if dis:
        print("A disagreements:", dis[:5])


if __name__ == "__main__":
    main()
