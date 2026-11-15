"""Assemble READINESS.json, REPORT.md, RUN-STATUS.md, CLAIM-EVIDENCE.md, READER-TAKEAWAY.md and SEMANTIC-COVERAGE.md
from the result files only. Usage: python -B scripts/ig_report.py --hub RESULTS_HUB

Status = <completion> / <readiness>.
  completion COMPLETE requires every TECHNICAL criterion (all stages succeeded, plan/frozen manifests verified, tests
  and controls passed, decision ledgers sealed and byte-identical on repeat, evaluator COMPLETE with per-row
  provenance verified on the full expected denominator, preservation unchanged, within the CPU cap). A missing or
  unreadable file fails its criterion; no criterion is satisfied vacuously by an empty list.
  readiness READY additionally requires every SUBSTANTIVE criterion (outcome checks). A completed replay whose
  substantive criteria fail is reported honestly as COMPLETE / NOT READY.
Exit code: 0 when the replay is technically COMPLETE (ready or not), 3 when INCOMPLETE. The report is always written.
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
from guard.studies import STUDIES as SPECS  # noqa: E402  (plain constants; imports no frozen code)

STUDIES = ("V1.24", "V1.22")
TECHNICAL = ("all_stages_succeeded", "within_cpu_cap", "frozen_manifests_verified", "tests_pass",
             "controls_pass", "decisions_sealed_and_deterministic", "coverage_complete",
             "provenance_verified_before_composition", "preservation_unchanged")
SUBSTANTIVE = ("supported_matching_controls_pass", "refusal_controls_abstain", "all_seven_known_bindings_blocked",
               "no_previously_exact_output_blocked", "acceptance_never_expands")


def load(p):
    p = Path(p)
    try:
        return json.loads(p.read_text()) if p.is_file() else None
    except (OSError, ValueError):
        return None


def cell(x):
    """One GFM table cell: escape every pipe as \\| (GFM honours this inside code spans too, displaying a bare |)
    and flatten newlines. Values here contain no backslashes, so no other escaping is needed."""
    return str(x).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def code(x):
    return f"`{cell(x)}`"


def row(*cells):
    return "| " + " | ".join(cells) + " |"


def _ok(f):
    try:
        return bool(f())
    except (KeyError, TypeError, AttributeError, IndexError):
        return False


def frac(a, b):
    return f"{a}/{b}"


def readiness(hub):
    hub = Path(hub)
    R = {s: load(hub / "results" / f"RESULTS-{s}.json") for s in STUDIES}
    C = load(hub / "controls" / "CONTROLS.json")
    P = load(hub / "PRESERVATION.json")
    T = load(hub / "tests" / "TESTS.json")
    M = load(hub / "INPUT-MANIFEST.json")
    RT = load(hub / "RUNTIME.json")
    DT = load(hub / "DETERMINISM.json")
    PL = load(hub / "PLAN.json")
    seals = {s: load(hub / "decisions" / f"SEAL-{s}.json") for s in STUDIES}
    rows = (C or {}).get("rows") or []
    exp = lambda d: [r for r in rows if (r.get("expected") or {}).get("disposition") == d]

    def full(r, s):
        return r["status"] == "COMPLETE" and not r["problems"] and r["totals"]["responses"] == SPECS[s]["calls"] \
            and r["seal"]["n_decisions"] == SPECS[s]["calls"]

    crit = {
        "all_stages_succeeded": _ok(lambda: RT["any_step_failed"] is False and not RT["failed_steps"]
                                    and RT["status"] == "STAGES_COMPLETE"),
        "within_cpu_cap": _ok(lambda: RT["within_cap"] is True and RT["cap_seconds"] <= 1800),
        "frozen_manifests_verified": _ok(lambda: set(M["studies"]) == set(STUDIES)
                                         and all(M["studies"][s]["frozen_manifest_check"]["ok"] is True
                                                 for s in STUDIES)),
        "tests_pass": _ok(lambda: T["ok"] is True and T["commit"] == PL["utility_commit"]),
        "controls_pass": _ok(lambda: C["status"] == "PASS" and C["failures"] == [] and C["n"] > 0
                             and C["n"] == len(rows) and all(r["ok"] is True for r in rows)),
        "decisions_sealed_and_deterministic": _ok(lambda: all(
            DT[s]["equal"] is True and DT[s]["first"] == DT[s]["repeat"] == seals[s]["decisions_sha256"]
            for s in STUDIES)),
        "coverage_complete": _ok(lambda: all(full(R[s], s) for s in STUDIES)),
        "provenance_verified_before_composition": _ok(lambda: all(
            R[s]["provenance"]["verified_before_composition"] is True
            and R[s]["provenance"]["rows_verified"] == SPECS[s]["calls"] for s in STUDIES)),
        "preservation_unchanged": _ok(lambda: P["unchanged"] is True and len(P["roots"]) == 4
                                      and all(v["unchanged"] and v["files"] > 0 for v in P["roots"].values())),
        "supported_matching_controls_pass": _ok(lambda: C["supported_matches_pass"] is True and len(exp("pass")) > 0
                                                and all(r["ok"] for r in exp("pass"))),
        "refusal_controls_abstain": _ok(lambda: C["refusals_abstain"] is True and C["no_refusal_passes"] is True
                                        and len(exp("abstain")) > 0),
        "all_seven_known_bindings_blocked": _ok(lambda: all(R[s]["known_fixtures_all_blocked"] is True
                                                            for s in STUDIES)
                                                and sum(len(R[s]["known_fixtures"]) for s in STUDIES) == 7
                                                and all(f["present"] and f["blocked"]
                                                        for s in STUDIES for f in R[s]["known_fixtures"])),
        "no_previously_exact_output_blocked": _ok(lambda: all(R[s]["totals"]["exact_blocked"] == 0
                                                              and R[s]["exact_blocked"] == [] for s in STUDIES)),
        "acceptance_never_expands": _ok(lambda: all(R[s]["totals"]["acceptance_expanded"] == 0
                                                    and R[s]["acceptance_expanded"] == [] for s in STUDIES)),
    }
    complete = all(crit[k] for k in TECHNICAL)
    ready = complete and all(crit[k] for k in SUBSTANTIVE)
    return {"criteria": crit, "technical_criteria": list(TECHNICAL), "substantive_criteria": list(SUBSTANTIVE),
            "technically_complete": complete,
            "failed_technical": [k for k in TECHNICAL if not crit[k]],
            "failed_substantive": [k for k in SUBSTANTIVE if not crit[k]],
            "failed_steps": (RT or {}).get("failed_steps") if RT else ["RUNTIME.json missing"],
            "ready_for_further_consideration": ready,
            "meaning": ("software acceptance on retrospective, already-inspected fixtures; not a statistical "
                        "qualification gate, an allowed harm margin, or evidence of general reliability")}, R, C, P, T, RT


def status_line(ready):
    return ("COMPLETE" if ready["technically_complete"] else "INCOMPLETE") + " / " + (
        "PROTOTYPE READY FOR FURTHER CONSIDERATION" if ready["ready_for_further_consideration"]
        else "PROTOTYPE NOT READY UNDER THE STATED CRITERIA")


def cell_table(r, conds):
    lines = ["| Condition / act | Responses (targets; stems) | Orig. accepted | Guard pass | Final accepted | "
             "Orig. exact → usable exact | Exact blocked | Newly rejected | Accepted wrong binding before → after | "
             "Accepted inexact before → after | Accepted state-only before → after |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for cond in conds:
        for act in ("arrival", "correction"):
            c = r["cells"].get(f"{cond}|{act}")
            if not c:
                continue
            lines.append(row(cell(f"{cond} {act}"),
                             cell(f"{c['responses']} ({c['targets']}; {c['independent_stems']})"),
                             *(cell(c[k]) for k in ("original_accepted", "guard_pass", "final_accepted")),
                             cell(f"{c['original_exact']} → {c['usable_exact']}"), cell(c["exact_blocked"]),
                             cell(c["newly_rejected"]),
                             cell(f"{c['original_wrong_binding']} → {c['post_wrong_binding']}"),
                             cell(f"{c['original_accepted_inexact']} → {c['post_accepted_inexact']}"),
                             cell(f"{c['state_only_event_accepted']} → {c['post_state_only']}")))
    return lines


def joint_table(r, conds):
    keys = sorted({k for c in r["cells"].values() for k in c["joint_original_accepted_x_disposition"]})
    lines = [row("Condition / act", *(cell(k) for k in keys)), "|---|" + "---:|" * len(keys)]
    for cond in conds:
        for act in ("arrival", "correction"):
            c = r["cells"].get(f"{cond}|{act}")
            if c:
                lines.append(row(cell(f"{cond} {act}"), *(cell(c["joint_original_accepted_x_disposition"].get(k, 0))
                                                          for k in keys)))
    return lines


def provenance_lines(hub):
    """Disclosure of earlier decision generation, read from this hub's INPUT-MANIFEST (never implied absent)."""
    M = load(hub / "INPUT-MANIFEST.json")
    PL = load(hub / "PLAN.json") or {}
    L = ["## Provenance and earlier decision generation", ""]
    if M and M.get("disclosure"):
        L += [f"INPUT-MANIFEST disclosure (verbatim): {M['disclosure']}", ""]
    else:
        L += ["**INPUT-MANIFEST.json missing or without a disclosure: earlier decision generation cannot be ruled out "
              "from this hub.**", ""]
    L += ["That decision-only scratch smoke preceded the original formal commit and replay; it is historical and is "
          "not part of this hub's outcomes. Earlier IGUARD-v0.1 hubs and commits (including any report-text-only "
          "regeneration) remain historical records and are not rewritten by this run. This hub's decisions were "
          f"generated and sealed at utility commit `{PL.get('utility_commit', 'unknown')}` before its evaluator ran.",
          ""]
    return L


def study_section(s, r):
    conds = {"V1.24": ["KEEP_CLAR", "SUB_ORIG", "SUB_CLAR"], "V1.22": ["KEEP", "SUB"]}[s]
    t = r["totals"]
    L = [f"## {s} ({'primary retrospective census' if s == 'V1.24' else 'separate historical check'})", "",
         f"Evaluator status {r['status']}; {t['responses']} responses, {t['targets']} targets, "
         f"{t['independent_stems']} stems. Resolver: {t['resolver_status']}; resolved field equals source gold on "
         f"{t['resolver_matches_gold']}/{t['responses']} responses. Saved scores re-derived with the pinned "
         f"scorer: {r['integrity']['n_mismatches']} disagreements. Per-row input provenance verified before "
         f"composition: {(r.get('provenance') or {}).get('rows_verified', 'NOT RECORDED')} rows. Sealed decisions "
         f"`{r['seal']['decisions_sha256'][:16]}…`.", ""]
    if r["problems"]:
        L += ["Evaluator problems: " + "; ".join(map(str, r["problems"][:20])), ""]
    if s == "V1.24":
        L += ["SUB_CLAR rows are the scheduled matched references and keep their own denominators.", ""]
    L += cell_table(r, conds) + [""]
    L += ["Joint original acceptance × guard disposition (a mismatch on an already rejected response is not a "
          "new rejection):", ""] + joint_table(r, conds) + [""]
    L += ["Known accepted wrong bindings (regression fixtures, not independent validation):", "",
          row("Call", "Disposition", "Resolved field", "Compiled fields", "Final accepted", "Partners (usable exact)"),
          "|---|---|---|---|---|---|"]
    for f in r["known_fixtures"]:
        parts = "; ".join(f"{p.split('|', 2)[-1]}: {'exact' if v['usable_exact'] else v['disposition']}"
                          for p, v in f.get("partners", {}).items())
        L.append(row(code(f["call_id"]), cell(f.get("disposition", "ABSENT")), code(f.get("resolved_field")),
                     code(f.get("compiled_fields")), cell(f.get("final_accepted")), cell(parts)))
    L += [""]
    extra = [m for m in r["identity_mismatches"] if m["call_id"] not in {f["call_id"] for f in r["known_fixtures"]}]
    if extra:
        L += ["Other identity mismatches (all listed):", "",
              row("Call", "Originally accepted", "Original code", "Compiled fields", "Resolved field"),
              "|---|---|---|---|---|"]
        L += [row(code(m["call_id"]), cell(m["original_accepted"]),
                  cell(m["original_contract_code"] or m["original_pending_code"]), code(m["compiled_fields"]),
                  code(m["resolved_field"])) for m in extra]
        L += [""]
    if r["exact_blocked"]:
        L += ["**Previously exact responses blocked (all listed):**", ""] + \
             [f"- `{m['call_id']}`: {m['disposition']} ({m['compiled_fields']} vs {m['resolved_field']})"
              for m in r["exact_blocked"]] + [""]
    else:
        L += ["No previously exact response was blocked in this study.", ""]
    if r["other_original_wrong_bindings"]:
        L += [f"Accepted wrong bindings outside the known list: {r['other_original_wrong_bindings']}", ""]
    if s == "V1.24":
        so = r["state_only_arrival_dispositions"]
        disp = {}
        for x in so:
            k = f"{x['disposition']}, final_accepted={x['final_accepted']}"
            disp[k] = disp.get(k, 0) + 1
        L += [f"KEEP_CLAR inexact state-only arrivals: {len(so)}; guard dispositions {disp}. The subject matches, "
              "so these remain accepted-but-inexact; a subject check does not address the missing event.", ""]
        L += ["Known KEEP_CLAR correction failures:", ""] + \
             [f"- `{x['call_id']}`: originally accepted={x['original_accepted']} "
              f"(code {x['original_contract_code'] or x['original_pending_code']}); guard {x['disposition']}; "
              f"final accepted={x['final_accepted']}; remains inexact." for x in r["known_correction_failure_dispositions"]] + [""]
    return L


def _n(f, default="n/a"):
    try:
        return f()
    except (KeyError, TypeError, AttributeError, IndexError):
        return default


def write(hub):
    hub = Path(hub)
    ready, R, C, P, T, RT = readiness(hub)
    (hub / "READINESS.json").write_text(json.dumps(ready, indent=1) + "\n")
    r24, r22 = R["V1.24"], R["V1.22"]
    status = status_line(ready)
    L = [f"# Identity-guard replay on saved outputs (IGUARD-v0.1)", "",
         f"**Status: {status}.** CPU replay of saved responses only; no model call, prompt variant, live policy "
         "change, baseline adoption or qualification. Codex independent verification: **pending**.", ""]
    if not ready["technically_complete"]:
        L += ["**This replay is technically INCOMPLETE; no outcome below may be read as a readiness result.** "
              f"Failed technical criteria: {', '.join(ready['failed_technical'])}. "
              f"Failed or skipped stages: {ready['failed_steps']}.", ""]
        for s in STUDIES:
            es = load(hub / "results" / f"EVALUATION-STATUS-{s}.json")
            ds = load(hub / "decisions" / f"DECISION-STATUS-{s}.json")
            L += [f"- {s}: decision stage {(ds or {}).get('status', 'NOT RUN / MISSING')}; evaluator "
                  f"{(es or {}).get('status', 'NOT RUN / MISSING')}"
                  + (f" ({'; '.join(map(str, ((ds or {}).get('problems') or []) + ((es or {}).get('problems') or [])))[:600]})"
                     if ((ds or {}).get("problems") or (es or {}).get("problems")) else "")]
        L += [""]
    L += ["## What was checked", "",
          "A rejection-only wrapper re-derives the stock subject from the original public target and prefix with the "
          "unchanged REFRES-v1 deterministic resolver, compiles each saved reply with the unchanged FACT-v1 compiler, "
          "and passes a reply only when its compiled assertion fields are exactly the resolved field. Unresolved or "
          "unsupported references abstain. Final acceptance = original acceptance AND guard pass. In this hub, "
          "decisions were generated from public inputs only and sealed before the evaluator joined hidden gold and "
          "saved scores; the evaluator re-verified every row's five input hashes before composing.", ""]
    L += provenance_lines(hub)
    L += ["## Readiness criteria", "", row("Criterion", "Kind", "Result"), "|---|---|---|"]
    L += [row(cell(k), "technical" if k in TECHNICAL else "substantive", "pass" if v else "**FAIL**")
          for k, v in ready["criteria"].items()]
    L += ["", f"These criteria are {ready['meaning']}.", ""]
    for s in STUDIES:
        r = R[s]
        if not r:
            L += [f"## {s}: no results (evaluator not run, refused or failed)", ""]
            continue
        try:
            L += study_section(s, r)
        except (KeyError, TypeError, AttributeError, IndexError) as e:
            L += [f"## {s}: results file unreadable ({type(e).__name__}: {e})", ""]
    L += ["## Controls (separate from study totals)", "",
          _n(lambda: f"{C['n']} public-only fixtures; status {C['status']}; supported matches pass: "
                     f"{C['supported_matches_pass']}; refusals abstain: {C['refusals_abstain']}. {C['note']}",
             "Controls missing or unreadable."), "",
          "## Evidence preservation", "",
          _n(lambda: f"Before/after hashes of both study hubs and both frozen source trees: "
                     f"{'unchanged' if P['unchanged'] else 'CHANGED'} "
                     f"({', '.join(str(v['files']) for v in P['roots'].values())} files).",
             "Preservation missing or unreadable."), "",
          "## Interpretation boundaries", "",
          "- Both panels were constructed to keep cases where the public resolver matched gold, so preserving exact "
          "responses here is largely expected; this is not an independent validation of the resolver.",
          "- Both panels were already inspected. Zero remaining accepted wrong bindings is a property of these "
          "selected cases under this guard's scope, not an estimated error rate or evidence of general safety.",
          "- Blocked wrong answers stay wrong: rejection gives no exactness credit and rescues nothing.",
          "- A matching subject with a wrong time or value passes this check (see controls).",
          f"- Abstentions in study data: V1.24 {_n(lambda: len(r24['abstentions']))}, "
          f"V1.22 {_n(lambda: len(r22['abstentions']))}. "
          "Refusal/abstain behavior is therefore exercised only by the separate controls, not by these panels.",
          "- The V1.24 COMPLETE / QUALIFIED and V1.22 results are unchanged historical evidence; the wrapper "
          "inherits no qualification. V1.24 and V1.22 counts are not pooled.", "",
          "Artifacts: `PLAN.json`, `DEPENDENCIES.json`, `INPUT-MANIFEST.json`, `decisions/` (sealed ledgers), "
          "`DETERMINISM.json`, `results/` (RESULTS + per-call TRACE + EVALUATION-STATUS), `controls/CONTROLS.json`, "
          "`tests/`, `PRESERVATION.json`, `READINESS.json`, `RUNTIME.json`, `TERMINAL.json`."]
    (hub / "REPORT.md").write_text("\n".join(L) + "\n")
    (hub / "RUN-STATUS.md").write_text(f"# Run status\n\n**{status}.**\n\nCodex review: pending. No next stage started.\n")

    def wb(r):
        return _n(lambda: (sum(c["original_wrong_binding"] for c in r["cells"].values()),
                           sum(c["post_wrong_binding"] for c in r["cells"].values())), ("n/a", "n/a"))

    def eb(r):
        return _n(lambda: (r["totals"]["exact_blocked"], r["totals"]["original_exact"]), ("n/a", "n/a"))
    inc = "" if ready["technically_complete"] else " (REPLAY INCOMPLETE: not evidence)"
    claims = ["# Claim / evidence", "", f"Run status: {status}.", "",
              "| Claim | Evidence | Scope |", "|---|---|---|",
              f"| The guard blocks the seven known accepted wrong bindings{inc} | known_fixtures in results/RESULTS-*.json: "
              f"V1.24 {wb(r24)[0]}→{wb(r24)[1]}, V1.22 {wb(r22)[0]}→{wb(r22)[1]} accepted wrong bindings | Known "
              "regression fixtures on inspected panels; not independent validation |",
              f"| Collateral loss of exact responses{inc} | exact_blocked V1.24 {eb(r24)[0]}/{eb(r24)[1]}, "
              f"V1.22 {eb(r22)[0]}/{eb(r22)[1]} | Panels built for resolver-gold agreement |",
              f"| Acceptance never expands{inc} | criterion acceptance_never_expands: "
              f"{ready['criteria']['acceptance_never_expands']} | By construction and checked |",
              "| Decisions use public inputs only | tests/TESTS.json (poisoning, no-hidden run, loader keys); per-row "
              "input-hash provenance in the evaluator | Code-level isolation for this utility |",
              f"| Refusal behavior | controls/CONTROLS.json refusals abstain: {_n(lambda: C['refusals_abstain'])} | "
              f"{_n(lambda: C['n'])} hand-built fixtures |",
              "| Not established | resolver reliability on new inputs; removal of state-only omissions or wrong "
              "times/values; any qualification or safety of the wrapper | — |"]
    (hub / "CLAIM-EVIDENCE.md").write_text("\n".join(claims) + "\n")
    if ready["technically_complete"]:
        take = ["# Reader takeaway", "",
                f"On the saved V1.24 and V1.22 panels, requiring the compiled subject to equal the public-resolved "
                f"subject turned the accepted wrong bindings into rejections (V1.24 {wb(r24)[0]}→{wb(r24)[1]}, V1.22 "
                f"{wb(r22)[0]}→{wb(r22)[1]}) and blocked {eb(r24)[0]} of {eb(r24)[1]} and {eb(r22)[0]} of {eb(r22)[1]} "
                "previously exact responses. The rejected answers remain wrong; no extraction was rescued, and the "
                "state-only arrival errors are untouched. This holds for these already-inspected, resolver-correct "
                "panels only; it does not show the resolver or the wrapper is reliable in general, and it confers no "
                f"qualification. Status: {status}. Codex verification is pending."]
    else:
        take = ["# Reader takeaway", "", f"**{status}.** This replay did not complete technically "
                f"({', '.join(ready['failed_technical'])}); it supports no outcome claim. Codex verification is pending."]
    (hub / "READER-TAKEAWAY.md").write_text("\n".join(take) + "\n")
    sem = ["# Source-to-acceptance semantic coverage", "",
           "| Stage | Measured here | Unchanged / not addressed |", "|---|---|---|",
           "| Source target and prefix | Original public text for every condition (SUB uses the original, not its "
           "rewritten prompt) | — |",
           "| Reference resolution | REFRES-v1 deterministic route, reason and field per response; agreement with "
           "gold reported in the evaluator only | Resolver reliability outside these panels |",
           "| Raw reply | Hashed, never modified; raw fields logged as diagnostics | Raw fidelity and saved scores |",
           "| FACT-v1 compile | Unchanged compile; rejection codes preserved | Compiler semantics |",
           "| Identity check | Compiled field set vs resolved field: pass / mismatch (different or extra field) / "
           "abstain | Value, time, act and interval correctness |",
           "| Engine acceptance | Joined from the pinned scorer after sealing; final = original AND guard | Engine "
           "rules |",
           "| Exactness | usable_exact = original_exact AND guard_pass | No rescue; wrong answers stay wrong |"]
    (hub / "SEMANTIC-COVERAGE.md").write_text("\n".join(sem) + "\n")
    print(status)
    return ready


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", required=True)
    rd = write(ap.parse_args().hub)
    sys.exit(0 if rd["technically_complete"] else 3)
