"""Evaluator (runs only after the decision ledger is sealed). Joins sealed decisions with hidden gold and saved scores.

Usage: PYTHONDONTWRITEBYTECODE=1 python -B scripts/ig_evaluate.py --study V1.24 --decisions DIR --out DIR

1. Verify the seal and the provenance of every decision BEFORE any composition (verify_provenance): the sealed
   body hash, seal metadata (study, rule, status, file name, row count, disposition tally, dependency hashes,
   matching DECISION-STATUS), unique call IDs whose set equals the schedule, and, per row, all five recorded
   decision.input_sha256 hashes (prefix, target_text, registry, registry_order, raw) recomputed from the public
   target and saved record that this evaluator is about to join. Any discrepancy -> REFUSED: nothing is composed,
   no RESULTS/TRACE are written, EVALUATION-STATUS-<study>.json lists the problems and the exit code is 2.
   This is provenance validation only; it adds no subject rule.
2. Integrity: recompute the saved per-call scores with the unchanged pinned scorer (kidconfscore.score_record, i.e.
   HOLD-EVAL-v1 against the ORIGINAL target) and require agreement on every compared flag. This reuses the existing
   scorer outside the guard.
3. Compose: final_accepted = original_accepted AND guard_pass; usable_exact = original_exact AND guard_pass.
   Rejection never creates a rescue; raw fidelity and saved scores are unchanged.
4. Report full-denominator counts per condition x act, joint dispositions, individual lists of every newly
   rejected and every newly blocked exact response, known-fixture checks and descriptive breakdowns.
"""
import argparse
import collections
import hashlib
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
from guard import pins  # noqa: E402

pins.activate()
from guard import decide as D, studies as ST  # noqa: E402
from tempo import kidconfscore as KS  # noqa: E402

sys.path.insert(0, str(HERE / "scripts"))
import ig_decide  # noqa: E402  (source_hash only)

COMPARED = ("exact", "accepted", "bound_ok_accepted", "compiled", "state_only_event_accepted", "category",
            "contract_code", "pending_code", "incomplete")

# Known accepted wrong bindings (regression fixtures from analysis/historical-reference-audit/AUDIT.md). Used ONLY here,
# after sealing; they never enter the decision stage.
KNOWN = {
    "V1.24": ["c24-g0045|arrival|na|B|KEEP_CLAR", "c24-g0125|arrival|na|B|KEEP_CLAR",
              "c24-g0143|arrival|na|B|KEEP_CLAR", "c24-g0191|arrival|na|B|KEEP_CLAR"],
    "V1.22": ["c22-g0016|arrival|B|KEEP", "c22-g0095|arrival|B|KEEP", "c22-g0111|arrival|B|KEEP"],
}
KNOWN_CORRECTION_FAILURES = {"V1.24": ["c24-g0038|correction|yes_to_no|A|KEEP_CLAR",
                                       "c24-g0120|correction|yes_to_no|A|KEEP_CLAR"]}


def load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


def compose(original_accepted, original_exact, guard_pass):
    final = bool(original_accepted) and bool(guard_pass)
    return {"final_accepted": final, "usable_exact": bool(original_exact) and bool(guard_pass)}


def usable_record(study, rec, call):
    if not isinstance(rec, dict):
        return None
    ok = rec.get("status") == "ok" and rec.get("complete") is True and rec.get("user_sha256") == call["user_sha256"]
    if not ok:
        return None
    rec = dict(rec)
    if not isinstance(rec.get("raw"), (str, type(None))):
        rec["raw"] = None
    return rec


def meta_for(study, pub, hid, cid):
    parts = cid.split("|")
    if study == "V1.24":
        direction = pub["direction"]
    else:   # V1.22 targets carry no direction field; its corrections are all yes->no by design
        direction = "yes_to_no" if pub["act"] == "correction" else "na"
    return {"study": study, "call_id": cid, "target": ST.target_of(cid), "arm": parts[-1], "act": pub["act"],
            "family": pub["family"][:2], "history": pub["history"], "reception": pub["reception"],
            "direction": direction, "stem": pub.get("stem", pub["group"]),
            "component": "reference" if parts[-1] in ST.STUDIES[study]["reference"] else "primary"}


HASHED_INPUTS = ("prefix", "target_text", "registry", "registry_order", "raw")


def _keyed(rows, key, label, problems):
    out = {}
    for r in rows:
        k = r.get(key) if isinstance(r, dict) else None
        if k in out:
            problems.append(f"{label}: duplicate {key} {k}")
        out[k] = r
    return out


def verify_provenance(study, ddir, pubs, calls, recs, use_expected=True):
    """-> (seal, decisions {call_id: row}, problems). Empty problems is required before any join/composition."""
    ddir = Path(ddir)
    problems = []
    seal_path = ddir / f"SEAL-{study}.json"
    try:
        seal = json.loads(seal_path.read_text())
    except (OSError, ValueError) as e:
        return None, {}, [f"seal unreadable {seal_path}: {e}"]
    want_file = f"DECISIONS-{study}.jsonl"
    meta = {"study": study, "rule": D.RULE, "status": "SEALED", "decisions_file": want_file}
    for k, v in meta.items():
        if seal.get(k) != v:
            problems.append(f"seal {k} is {seal.get(k)!r}, expected {v!r}")
    if problems:
        return seal, {}, problems
    body = (ddir / want_file).read_bytes()
    sha = hashlib.sha256(body).hexdigest()
    if sha != seal.get("decisions_sha256"):
        return seal, {}, ["sealed decision hash mismatch"]
    try:
        st = json.loads((ddir / f"DECISION-STATUS-{study}.json").read_text())
        if st.get("status") != "SEALED" or st.get("decisions_sha256") != sha or st.get("study") != study:
            problems.append(f"decision status {st.get('status')} / {st.get('decisions_sha256')} does not match seal")
    except (OSError, ValueError) as e:
        problems.append(f"decision status unreadable: {e}")
    if seal.get("utility_source_sha256") != ig_decide.source_hash():
        problems.append("seal utility_source_sha256 differs from the evaluating utility source")
    if seal.get("dependency_sha256") != pins.dependency_hashes():
        problems.append("seal dependency_sha256 differs from the current frozen dependency tree")
    rows = []
    for i, line in enumerate(body.decode("utf-8").split("\n"), 1):
        if line:
            try:
                rows.append(json.loads(line))
            except ValueError:
                problems.append(f"decision line {i} corrupt")
    decisions = _keyed(rows, "call_id", "decisions", problems)
    if seal.get("n_decisions") != len(rows):
        problems.append(f"seal n_decisions {seal.get('n_decisions')} != ledger rows {len(rows)}")
    tally = dict(collections.Counter((r.get("decision") or {}).get("disposition") for r in rows))
    if seal.get("dispositions") != tally:
        problems.append(f"seal dispositions {seal.get('dispositions')} != ledger {tally}")
    if use_expected and len(rows) != ST.STUDIES[study]["calls"]:
        problems.append(f"ledger rows {len(rows)} != expected {ST.STUDIES[study]['calls']}")
    if use_expected and seal.get("membership_checked") is not True:
        problems.append("seal was produced without the declared-membership checks")
    if set(decisions) != set(calls):
        problems.append(f"decision membership differs from schedule: missing {len(set(calls) - set(decisions))}, "
                        f"extra {len(set(decisions) - set(calls))}")
    for cid in sorted(set(decisions) & set(calls)):
        row = decisions[cid]
        d = row.get("decision") or {}
        tid = ST.target_of(cid)
        if row.get("target") != tid or d.get("rule") != D.RULE:
            problems.append(f"{cid}: decision target/rule inconsistent")
            continue
        pub, rec = pubs.get(tid), recs.get(cid)
        if pub is None or not isinstance(rec, dict):
            problems.append(f"{cid}: public target or saved record missing at evaluation")
            continue
        raw = rec.get("raw") if isinstance(rec.get("raw"), str) else None
        if row.get("raw_is_str") is not isinstance(rec.get("raw"), str):
            problems.append(f"{cid}: raw_is_str differs from the saved record")
        try:
            now = D.input_hashes(pub["prefix"], pub["target_text"], pub["registry"], pub["registry_order"], raw)
        except (KeyError, TypeError) as e:
            problems.append(f"{cid}: public inputs unusable for provenance hashing ({e})")
            continue
        sealed = d.get("input_sha256") or {}
        bad = [k for k in HASHED_INPUTS if sealed.get(k) != now[k]]
        if bad or set(sealed) != set(HASHED_INPUTS):
            problems.append(f"{cid}: decision input hash mismatch on {bad or sorted(sealed)}")
    return seal, decisions, problems


def _refuse(study, out, problems, t0):
    status = {"study": study, "status": "REFUSED", "problems": problems, "composed": False,
              "seconds": round(time.time() - t0, 2)}
    (out / f"EVALUATION-STATUS-{study}.json").write_text(json.dumps(status, indent=1) + "\n")
    return status


def evaluate(study, ddir, out, hub=None, use_expected=True):
    """hub/use_expected: tests only (isolated subset hubs). Production uses the fixed study hub and counts."""
    t0 = time.time()
    spec = ST.STUDIES[study]
    hub = Path(hub or spec["hub"])
    ddir, out = Path(ddir), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    for name in (f"RESULTS-{study}.json", f"TRACE-{study}.jsonl", f"EVALUATION-STATUS-{study}.json"):
        if (out / name).exists():
            return {"study": study, "status": "REFUSED", "problems": [f"refusing to overwrite {out / name}"]}
    problems = []
    inp = []
    pubs = _keyed(load_jsonl(hub / "data" / "public" / "main-targets.jsonl"), "target", "public targets", inp)
    calls = _keyed(load_jsonl(hub / "data" / "main-calls.jsonl"), "call_id", "schedule", inp)
    recs = {}
    for p in sorted((hub / "stages" / "main" / "calls").glob("*.json")):
        try:
            r = json.loads(p.read_text())
        except ValueError:
            inp.append(f"corrupt record file {p.name}")
            continue
        if r.get("call_id") in recs:
            inp.append(f"records: duplicate call_id {r.get('call_id')}")
        recs[r.get("call_id")] = r
    seal, decisions, prov = verify_provenance(study, ddir, pubs, calls, recs, use_expected)
    if inp or prov:
        return _refuse(study, out, inp + prov, t0)

    hid = {h["target"]: h for h in load_jsonl(hub / "data" / "hidden" / "main-cases.jsonl")}
    saved = {s["call_id"]: s for s in load_jsonl(hub / "analysis" / "confirm" / "scored.jsonl")}
    for label, keys in (("saved scores", set(saved)), ("records", set(recs))):
        if keys != set(calls):
            problems.append(f"{label} membership differs from schedule: missing {len(set(calls) - keys)}, "
                            f"extra {len(keys - set(calls))}")
    missing_hidden = sorted({ST.target_of(c) for c in calls} - set(hid))
    if missing_hidden:
        return _refuse(study, out, [f"hidden gold missing for {len(missing_hidden)} targets"], t0)
    rows = []
    rescore_mismatch = []
    for cid in sorted(calls):
        tid = ST.target_of(cid)
        pub, h, dec, sv = pubs[tid], hid[tid], decisions.get(cid), saved.get(cid)
        rec = usable_record(study, recs.get(cid), calls[cid])
        s = KS.score_record(rec, h, pub)
        s["accepted_wrong_binding"] = bool(s.get("accepted")) and not s.get("bound_ok_accepted")
        diffs = [k for k in COMPARED if sv is None or s.get(k) != sv.get(k)]
        if diffs:
            rescore_mismatch.append({"call_id": cid, "flags": diffs})
        d = dec["decision"]
        gold = h["case"]["field"]
        m = meta_for(study, pub, h, cid)
        c = compose(s["accepted"], s["exact"], d["guard_pass"])
        row = {**m,
               "gold_field": gold, "resolved_field": d["resolver"]["field"], "resolver_status": d["resolver"]["status"],
               "resolver_reason": d["resolver"]["reason"], "resolver_kind": (d["resolver"]["detection"] or {}).get("kind"),
               "resolver_matches_gold": d["resolver"]["field"] == gold,
               "saved_identity_field": (pub.get("identity") or {}).get("field"),
               "compile_code": d["compile"]["code"], "compiled_type": d["compile"]["type"],
               "compiled_fields": d["compiled_fields"], "raw_fields": d["raw_fields"],
               "disposition": d["disposition"], "mismatch_kind": d["mismatch_kind"], "guard_pass": d["guard_pass"],
               "original_accepted": bool(s["accepted"]), "original_exact": bool(s["exact"]),
               "original_compiled": bool(s["compiled"]), "bound_ok_accepted": bool(s["bound_ok_accepted"]),
               "state_only_event_accepted": bool(s["state_only_event_accepted"]),
               "original_contract_code": s.get("contract_code"), "original_pending_code": s.get("pending_code"),
               "category": s.get("category"), **c}
        row["original_wrong_binding"] = row["original_accepted"] and not row["bound_ok_accepted"]
        row["post_wrong_binding"] = row["final_accepted"] and not row["bound_ok_accepted"]
        row["original_accepted_inexact"] = row["original_accepted"] and not row["original_exact"]
        row["post_accepted_inexact"] = row["final_accepted"] and not row["original_exact"]
        row["post_state_only"] = row["state_only_event_accepted"] and row["guard_pass"]
        row["newly_rejected"] = row["original_accepted"] and not row["guard_pass"]
        row["exact_blocked"] = row["original_exact"] and not row["guard_pass"]
        row["mismatch_on_already_rejected"] = (not row["original_accepted"]) and d["disposition"] == "identity_mismatch"
        row["acceptance_expanded"] = row["final_accepted"] and not row["original_accepted"]
        rows.append(row)
    if rescore_mismatch:
        problems.append(f"{len(rescore_mismatch)} saved-score rows disagree with the pinned scorer")
    if use_expected and len(rows) != spec["calls"]:
        problems.append(f"rows {len(rows)} != expected {spec['calls']}")

    counted = ("original_accepted", "guard_pass", "final_accepted", "original_exact", "usable_exact",
               "original_wrong_binding", "post_wrong_binding", "original_accepted_inexact", "post_accepted_inexact",
               "state_only_event_accepted", "post_state_only", "newly_rejected", "exact_blocked",
               "mismatch_on_already_rejected", "acceptance_expanded", "resolver_matches_gold")

    def summarize(rs):
        rs = list(rs)
        out_ = {"responses": len(rs), "targets": len({r["target"] for r in rs}),
                "independent_stems": len({r["stem"] for r in rs}),
                **{k: sum(bool(r[k]) for r in rs) for k in counted},
                "resolver_status": dict(collections.Counter(r["resolver_status"] for r in rs)),
                "dispositions": dict(collections.Counter(r["disposition"] for r in rs)),
                "joint_original_accepted_x_disposition": dict(collections.Counter(
                    f"{'accepted' if r['original_accepted'] else 'rejected'}|{r['disposition']}" for r in rs))}
        out_["blocked_exact_over_original_exact"] = [out_["exact_blocked"], out_["original_exact"]]
        out_["newly_rejected_over_original_accepted"] = [out_["newly_rejected"], out_["original_accepted"]]
        out_["accepted_inexact_over_scheduled_before_after"] = [out_["original_accepted_inexact"],
                                                                out_["post_accepted_inexact"], len(rs)]
        out_["secondary_inexact_among_accepted_before_after"] = [
            [out_["original_accepted_inexact"], out_["original_accepted"]],
            [out_["post_accepted_inexact"], out_["final_accepted"]]]
        return out_

    by = collections.defaultdict(list)
    for r in rows:
        by[(r["arm"], r["act"])].append(r)
    cells = {f"{a}|{b}": summarize(v) for (a, b), v in sorted(by.items())}
    breakdowns = {}
    for dim in ("family", "history", "reception", "direction"):
        g = collections.defaultdict(list)
        for r in rows:
            g[(r["arm"], r["act"], r[dim])].append(r)
        breakdowns[dim] = {f"{a}|{b}|{c}": {k: v for k, v in summarize(rs).items()
                                            if k in ("responses", "targets", "independent_stems", "original_exact",
                                                     "usable_exact", "original_accepted", "final_accepted",
                                                     "original_wrong_binding", "post_wrong_binding", "exact_blocked",
                                                     "newly_rejected")}
                           for (a, b, c), rs in sorted(g.items())}

    keyed = {r["call_id"]: r for r in rows}
    trim = lambda r: {k: r[k] for k in ("call_id", "family", "history", "reception", "direction", "disposition",
                                        "mismatch_kind", "resolved_field", "gold_field", "compiled_fields",
                                        "original_accepted", "original_exact", "final_accepted", "usable_exact",
                                        "original_contract_code", "original_pending_code", "compile_code", "category")}
    fixtures = []
    for cid in KNOWN.get(study, []):
        r = keyed.get(cid)
        if r is None:
            fixtures.append({"call_id": cid, "present": False})
            continue
        tparts = cid.split("|")
        partners = {}
        other_hist = "A" if tparts[-2] == "B" else "B"
        for arm in spec["primary"]:
            for hist in (tparts[-2], other_hist):
                pid = "|".join(tparts[:-2] + [hist, arm])
                if pid != cid and pid in keyed:
                    partners[pid] = trim(keyed[pid])
        fixtures.append({"present": True, **trim(r), "was_accepted_wrong_binding": r["original_wrong_binding"],
                         "blocked": r["original_wrong_binding"] and not r["final_accepted"], "partners": partners})
    known_ok = all(f.get("present") and f["was_accepted_wrong_binding"] and f["blocked"] for f in fixtures)
    other_wrong = sorted(r["call_id"] for r in rows if r["original_wrong_binding"] and r["call_id"] not in KNOWN.get(study, []))

    state_only = []
    if study == "V1.24":
        state_only = [trim(r) for r in rows if r["arm"] == "KEEP_CLAR" and r["act"] == "arrival"
                      and not r["original_exact"] and r["category"] == "state"]
    corr_fail = [trim(keyed[c]) for c in KNOWN_CORRECTION_FAILURES.get(study, []) if c in keyed]

    result = {
        "study": study, "rule": seal["rule"], "status": "COMPLETE" if not problems else "INCOMPLETE",
        "problems": problems, "seal": {k: seal[k] for k in ("decisions_sha256", "n_decisions", "utility_source_sha256")},
        "provenance": {"verified_before_composition": True, "rows_verified": len(decisions),
                       "hashed_inputs": list(HASHED_INPUTS), "mismatches": 0},
        "integrity": {"rescored_with": "tempo.kidconfscore.score_record (pinned, unchanged)",
                      "compared_flags": list(COMPARED), "mismatches": rescore_mismatch[:50],
                      "n_mismatches": len(rescore_mismatch)},
        "totals": summarize(rows),
        "cells": cells, "breakdowns_descriptive": breakdowns,
        "known_fixtures": fixtures, "known_fixtures_all_blocked": known_ok,
        "other_original_wrong_bindings": other_wrong,
        "newly_rejected": [trim(r) for r in rows if r["newly_rejected"]],
        "identity_mismatches": [trim(r) for r in rows if r["disposition"] == "identity_mismatch"],
        "exact_blocked": [trim(r) for r in rows if r["exact_blocked"]],
        "abstentions": [trim(r) for r in rows if r["disposition"] == "abstain"],
        "acceptance_expanded": [r["call_id"] for r in rows if r["acceptance_expanded"]],
        "resolver_disagrees_with_gold": [trim(r) for r in rows if not r["resolver_matches_gold"]],
        "resolver_disagrees_with_saved_identity": [r["call_id"] for r in rows
                                                   if r["resolved_field"] != r["saved_identity_field"]],
        "state_only_arrival_dispositions": state_only,
        "known_correction_failure_dispositions": corr_fail,
        "seconds": round(time.time() - t0, 2),
    }
    (out / f"RESULTS-{study}.json").write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    with open(out / f"TRACE-{study}.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, sort_keys=True) + "\n")
    (out / f"EVALUATION-STATUS-{study}.json").write_text(json.dumps(
        {"study": study, "status": result["status"], "problems": problems, "composed": True,
         "provenance_rows_verified": len(decisions)}, indent=1) + "\n")
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--study", required=True, choices=sorted(ST.STUDIES))
    ap.add_argument("--decisions", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    r = evaluate(a.study, a.decisions, a.out)
    if r["status"] == "REFUSED":
        print(json.dumps({"study": a.study, "status": "REFUSED", "problems": r["problems"][:10]}))
        sys.exit(2)
    t = r["totals"]
    print(json.dumps({"study": a.study, "status": r["status"], "problems": r["problems"][:5],
                      "known_fixtures_all_blocked": r["known_fixtures_all_blocked"],
                      "exact_blocked": t["exact_blocked"], "newly_rejected": t["newly_rejected"],
                      "post_wrong_binding": t["post_wrong_binding"], "seconds": r["seconds"]}))
    if r["status"] != "COMPLETE":
        sys.exit(2)


if __name__ == "__main__":
    main()
