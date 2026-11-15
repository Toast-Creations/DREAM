"""EVT suite analyzer (V1.27.0): integrity, unchanged V1.24 scoring, guarded replay and each study's frozen reading.

Studies (key in config/PANEL.json):
  A  EVTC-v1  confirmation of the policy KEEP_EVT + IGUARD against KEEP_CLAR + IGUARD
  B  EVTR-v1  development screen of KEEP_EVTR (narrowed sentence) against KEEP_CLAR, with KEEP_EVT as comparator
  C  EVTB-v1  descriptive wrong-binding panel (history-B arrivals only); no gate
  D  EVTT-v1  (V1.29.0) development screen of KEEP_EVTT (combined sentence) against KEEP_EVT; KEEP_CLAR is a
              descriptive anchor. Studies A-C are analyzed exactly as in V1.27.0.

Every scheduled call is scored in its own denominator with the unchanged V1.24 scorer (clar_analyze.score_one ->
HOLD-EVAL-v1 against the ORIGINAL target and prefix). Missing, duplicate, extra, corrupt or non-usable records make
the run INCOMPLETE and suppress every reading. IGUARD-v0.1 guard/decide.py (hash-pinned, unchanged) is applied to
every response from public inputs only: final_accepted = accepted AND guard_pass; usable_exact = exact AND guard_pass.

Every non-exact response also gets a sub-pattern label (descriptive, from its normalized claims): e.g. spurious
revisions on an arrival, or a state dated at received_at instead of the event time. A sub-pattern that appears under
the candidate but not under the current arm triggers manual review in studies A and B.
"""
import collections
from datetime import datetime
import json
import math
import random
import statistics
import sys
from pathlib import Path

from _bootstrap import ROOT
from dream_core.ledger import atomic_json, release_source_hash
from tempo import evreport as ES, evsuite as S, factored as FA, kidconfscore as KS
import clar_analyze as CA
from ev_analyze import (GUARD_DECIDE_SHA256, cells, keyed, load_guard, load_jsonl, load_records, record_usable,
                        sha)

OUT = "analysis/dev"
CORR_MIN_POINTS = -100 * 3 / 64
POOLED_WB = {"status": "historically informed development-screen threshold, not a calibrated significance or "
                       "non-inferiority test",
             "rationale": "The +4 allowance is a historically informed development-screen threshold, not a calibrated "
                          "significance or non-inferiority test. The listed earlier KEEP-family arms contributed 17 "
                          "wrong bindings on 2,000 arrival targets. An illustrative independent, equal-rate Poisson "
                          "model with lambda 2.448 gives four as the smallest integer whose excess tail is at most "
                          "0.05, but that model does not account for this study's pairing, stem dependence, "
                          "historical heterogeneity, rate uncertainty or correction targets. The allowance would admit "
                          "EVT-v1's 4-versus-1 on this criterion alone; EVT-v1's frozen reading remains unchanged.",
             "earlier_arms": "accepted wrong bindings on arrival targets, as rescored by Codex in the EVT-v1 "
                             "verification: V1.22 KEEP 3/336; V1.23 KEEP_ORIG 0/32, KEEP_CLAR 0/32; V1.24 KEEP_CLAR "
                             "4/448; V1.25 KEEP_CLAR 4/288, KEEP_SUBJ 1/288; V1.26 KEEP_CLAR 1/288, KEEP_EVT 4/288",
             "k": 4}
INVARIANT_NOTE = ("These panels retain only targets on which the public identity resolver agrees with the "
                  "construction's gold identity. With the pinned scorer and guard, zero post-guard accepted wrong "
                  "bindings and zero exact answers blocked are expected structural invariants on retained targets. "
                  "The guarded replay checks this pipeline behavior; it does not independently test resolver "
                  "correctness, unsupported identities or guard safety.")
INVARIANT_RULE = ("any post-guard accepted wrong binding or exact answer blocked by the guard, in any arm, is a "
                  "pipeline-invariant violation: an infrastructure failure that blocks completion certification; the "
                  "study is INCOMPLETE / NOT_EVALUATED with diagnostic PIPELINE_INVARIANT_VIOLATION, and needs "
                  "investigation")
A_NOTE = ("The TRANSITION and correction screens permit point-estimate losses of up to 3 and 4.6875 percentage points "
          "respectively. Passing them is not evidence of no cost or statistical non-inferiority. Pre-guard "
          "wrong-binding increases remain adverse descriptive evidence even when the guarded policy passes.")
B_NOTE = ("Criterion transition_exact_not_below_keep_evt screens for no observed additional TRANSITION loss relative "
          "to KEEP_EVT. Equality can pass; it does not establish removal of KEEP_EVT's cost. The correction screen "
          "permits a point-estimate loss of up to 4.6875 percentage points. KEEP_EVTR is a composite of scope "
          "narrowing and a state-time instruction; this screen cannot attribute an effect to either clause.")
D_NOTE = ("Criteria 2-7 are point-estimate screens, not equivalence or non-inferiority tests; passing them is not "
          "evidence of no cost. The panel is weighted toward delayed F3 arrivals, so overall arrival exactness is not "
          "comparable in composition with runs A-C. KEEP_EVTT-KEEP_EVT isolates the appended time clause given "
          "KEEP_EVT's scope; it says nothing about the clause in other scopes. A reception-dated reply count under "
          "KEEP_EVT below 6 makes the target-error criterion uninformative (INSUFFICIENT_TARGET_ERRORS), unless "
          "another criterion already fails. KEEP_CLAR enters no criterion.")
RD_FLOOR = 6
STATE_ONLY_TOLERANCE = 2
WB_TOLERANCE_D = 4


def _boot(seed):
    return {"B": 10000, "seed": seed, "resample": "stems within family x reception"}


PLANS = {
    "A": {"study": "EVTC-v1", "role": "confirmation on one fresh panel", "candidate": "KEEP_EVT", "current": "KEEP_CLAR",
          "policy": "prompt arm + IGUARD-v0.1 (usable_exact = exact AND guard pass)",
          "primary_outcome": "paired usable-exact arrival difference KEEP_EVT-KEEP_CLAR",
          "unit": "independent stem; arrival d_g = mean of 2 history differences, correction d_g = mean of 4",
          "criteria": {
              "usable_exact_arrival_gain": "difference > 0 points AND bootstrap 95% lower bound > 0 points",
              "transition_usable_exact_not_lower_than_3_points": "TRANSITION-wording usable-exact difference >= -3",
              "post_guard_wrong_bindings_not_more": "post-guard accepted wrong bindings KEEP_EVT <= KEEP_CLAR",
              "exact_blocked_at_most_1_per_arm": "exact answers blocked by the guard <= 1 in each arm",
              "correction_usable_exact_not_lower_than_3_64": "correction usable-exact difference >= -3/64",
          },
          "review_rule": "outcome classes or non-exact sub-patterns present under KEEP_EVT but absent under "
                         "KEEP_CLAR (per act) -> REVIEW_NEW_FAILURE_TYPES when all criteria pass",
          "statuses": ["CONFIRMS_ON_THIS_PANEL", "DOES_NOT_CONFIRM", "REVIEW_NEW_FAILURE_TYPES"],
          "bootstrap": {**_boot(2026111254), "use": "95% percentile interval; its lower bound is a declared gate for "
                                                    "the primary criterion only; all other intervals descriptive"},
          "descriptive": ["raw exact contrasts", "state-only arrivals", "pre-guard wrong bindings", "sub-patterns",
                          "revision/event objects", "truncation", "output tokens"],
          "interpretation": A_NOTE, "invariants": {"note": INVARIANT_NOTE, "rule": INVARIANT_RULE},
          "guard": {"decide_sha256": GUARD_DECIDE_SHA256}},
    "B": {"study": "EVTR-v1", "role": "development screen", "candidate": "KEEP_EVTR", "current": "KEEP_CLAR",
          "comparator": "KEEP_EVT",
          "primary_outcome": "accepted state-only arrivals; TRANSITION-wording exactness against KEEP_EVT",
          "unit": "independent stem; arrival d_g = mean of 2 history differences, correction d_g = mean of 4",
          "criteria": {
              "state_only_halved_with_baseline_at_least_10": "KEEP_EVTR <= floor(KEEP_CLAR / 2) and KEEP_CLAR >= 10",
              "arrival_exact_not_lower": "arrival exact KEEP_EVTR-KEEP_CLAR >= 0 points",
              "transition_exact_not_lower_than_3_points": "TRANSITION exact KEEP_EVTR-KEEP_CLAR >= -3 points",
              "transition_exact_not_below_keep_evt": "TRANSITION exact KEEP_EVTR-KEEP_EVT >= 0 points",
              "wrong_bindings_within_pooled_tolerance": "accepted wrong bindings KEEP_EVTR <= KEEP_CLAR + 4",
              "correction_exact_not_lower_than_3_64": "correction exact KEEP_EVTR-KEEP_CLAR >= -3/64",
          },
          "wrong_binding_tolerance": POOLED_WB,
          "review_rule": "outcome classes or non-exact sub-patterns present under KEEP_EVTR but absent under "
                         "KEEP_CLAR (per act) -> REVIEW_NEW_FAILURE_TYPES when all criteria pass",
          "statuses": ["WARRANTS_CONFIRMATION_DESIGN", "DOES_NOT_WARRANT", "REVIEW_NEW_FAILURE_TYPES"],
          "bootstrap": {**_boot(2026111264), "use": "descriptive 95% percentile interval only; never a gate"},
          "descriptive": ["KEEP_EVT-KEEP_CLAR replication of EVT-v1", "guarded replay", "sub-patterns",
                          "revision/event objects", "truncation", "output tokens"],
          "interpretation": B_NOTE, "invariants": {"note": INVARIANT_NOTE, "rule": INVARIANT_RULE},
          "guard": {"decide_sha256": GUARD_DECIDE_SHA256}},
    "C": {"study": "EVTB-v1", "role": "descriptive wrong-binding panel; no gate",
          "arms": ["KEEP_CLAR", "KEEP_EVT", "KEEP_EVTR"],
          "primary_outcome": "accepted wrong bindings per arm, before and after IGUARD-v0.1, with exact "
                             "Clopper-Pearson 95% intervals; exact answers blocked by the guard",
          "unit": "independent stem; one history-B arrival target per stem per arm",
          "pairwise": "discordant wrong-binding stems with an exact two-sided sign test, pre-declared, descriptive",
          "subgroups": "per arm x wording and per arm x family: wrong-binding rates before and after the guard with "
                       "nominal descriptive exact binomial (Clopper-Pearson) 95% intervals and explicit denominators; "
                       "no simultaneous coverage or equivalence claim",
          "statuses": ["DESCRIPTIVE_COMPLETE"],
          "bootstrap": {**_boot(2026111274), "use": "descriptive 95% percentile interval only; never a gate"},
          "invariants": {"note": INVARIANT_NOTE, "rule": INVARIANT_RULE},
          "guard": {"decide_sha256": GUARD_DECIDE_SHA256}},
    "D": {"study": "EVTT-v1", "role": "development screen", "candidate": "KEEP_EVTT", "current": "KEEP_EVT",
          "anchor": "KEEP_CLAR (descriptive only; enters no criterion)",
          "primary_outcome": "arrival replies with sub-pattern RECEPTION_DATED (event at the stated time, resulting "
                             "state dated at received_at), KEEP_EVTT against KEEP_EVT",
          "unit": "independent stem; arrival d_g = mean of 2 history differences, correction d_g = mean of 4",
          "metric": "raw exact (scorer) for every criterion; the guarded replay is reported beside it",
          "criteria": {
              "reception_dated_halved_with_keep_evt_at_least_6":
                  "RECEPTION_DATED arrivals KEEP_EVTT <= floor(KEEP_EVT / 2) and KEEP_EVT >= 6",
              "arrival_exact_not_lower": "arrival exact KEEP_EVTT-KEEP_EVT >= 0 points",
              "state_only_within_2": "accepted state-only arrivals KEEP_EVTT <= KEEP_EVT + 2",
              "immediate_result_exact_not_lower_than_3_points":
                  "immediate-reception RESULT-wording arrival exact KEEP_EVTT-KEEP_EVT >= -3 points",
              "transition_exact_not_lower_than_3_points": "TRANSITION-wording arrival exact KEEP_EVTT-KEEP_EVT >= -3 "
                                                          "points",
              "wrong_bindings_within_4": "pre-guard accepted wrong bindings KEEP_EVTT <= KEEP_EVT + 4",
              "correction_exact_not_lower_than_3_64": "correction exact KEEP_EVTT-KEEP_EVT >= -3/64",
          },
          "precedence": ["any of criteria 2-7 fails -> DOES_NOT_WARRANT",
                         "else KEEP_EVT RECEPTION_DATED < 6 -> INSUFFICIENT_TARGET_ERRORS",
                         "else KEEP_EVTT > floor(KEEP_EVT / 2) -> DOES_NOT_WARRANT",
                         "else outcome classes or non-exact sub-patterns present under KEEP_EVTT but absent under "
                         "KEEP_EVT (per act) -> REVIEW_NEW_FAILURE_TYPES",
                         "else WARRANTS_CONFIRMATION_DESIGN (justifies a confirmation design, not adoption)",
                         "a pipeline-invariant violation overrides all of these (INCOMPLETE)"],
          "statuses": ["WARRANTS_CONFIRMATION_DESIGN", "DOES_NOT_WARRANT", "INSUFFICIENT_TARGET_ERRORS",
                       "REVIEW_NEW_FAILURE_TYPES"],
          "bootstrap": {**_boot(2026111494), "use": "descriptive 95% percentile interval only; never a gate"},
          "descriptive": ["arm x wording x reception table (declared)", "RECEPTION_DATED by arm x history and by "
                          "arm x family", "stems with any RECEPTION_DATED reply, discordant between arms, with an "
                          "exact two-sided sign test (descriptive)", "KEEP_EVT-KEEP_CLAR and KEEP_EVTT-KEEP_CLAR "
                          "contrasts", "delayed-RESULT contrasts", "paired bootstrap intervals", "sub-patterns",
                          "every pre- and post-guard wrong binding", "truncation", "output tokens"],
          "interpretation": D_NOTE, "invariants": {"note": INVARIANT_NOTE, "rule": INVARIANT_RULE},
          "guard": {"decide_sha256": GUARD_DECIDE_SHA256}},
}
PAIRS = {"A": [("KEEP_EVT", "KEEP_CLAR")],
         "B": [("KEEP_EVTR", "KEEP_CLAR"), ("KEEP_EVT", "KEEP_CLAR"), ("KEEP_EVTR", "KEEP_EVT")],
         "C": [("KEEP_EVT", "KEEP_CLAR"), ("KEEP_EVTR", "KEEP_CLAR"), ("KEEP_EVTR", "KEEP_EVT")],
         "D": [("KEEP_EVTT", "KEEP_EVT"), ("KEEP_EVT", "KEEP_CLAR"), ("KEEP_EVTT", "KEEP_CLAR")]}


def validate_plan(plan, key):
    if json.dumps(plan, sort_keys=True) != json.dumps(PLANS[key], sort_keys=True):
        raise ValueError(f"analysis plan differs from the declared {PLANS[key]['study']} plan")
    return plan


def panel_config(hub):
    return S.validate_config(json.loads((Path(hub) / "config/PANEL.json").read_text()))


def integrity(hub, during_driver=False):
    """-> (info, bundle, config). info['complete'] False on any infrastructure problem."""
    from su_certify import certify
    hub = Path(hub)
    cfg = panel_config(hub)
    problems = certify(hub, during_driver=during_driver)
    frozen = {}
    try:
        frozen = json.loads((hub / "config/FROZEN-PROTOCOL.json").read_text())
    except (OSError, ValueError):
        pass
    bundle = {}
    if problems:
        info = {"complete": False, "problems": problems, "source_sha256": release_source_hash(ROOT),
                "frozen_source_sha256": frozen.get("source_sha256")}
        return info, bundle, cfg
    for stage, n in (("smoke", cfg["smoke_calls"]), ("main", cfg["main_calls"])):
        allocation = S.plan(cfg, smoke=(stage == "smoke"))
        expected_calls = S.allowed_call_ids(allocation, cfg)
        expected_targets = {m["target"]: m for m in S.expected_targets(allocation, cfg)}
        calls = keyed(load_jsonl(hub / f"data/{stage}-calls.jsonl", problems, f"{stage} calls"), "call_id",
                      problems, f"{stage} calls")
        pubs = keyed(load_jsonl(hub / f"data/public/{stage}-targets.jsonl", problems, f"{stage} public"), "target",
                     problems, f"{stage} public")
        hid = keyed(load_jsonl(hub / f"data/hidden/{stage}-cases.jsonl", problems, f"{stage} hidden"), "target",
                    problems, f"{stage} hidden")
        allowed = {r["call_id"] for r in load_jsonl(hub / "data/ALLOWED-CALLS.jsonl", problems, "allowed")
                   if r.get("set") == stage}
        if set(calls) != expected_calls or allowed != expected_calls or len(calls) != n:
            problems.append(f"{stage}: schedule membership differs from the declared allocation")
        if set(pubs) != set(expected_targets) or set(hid) != set(expected_targets):
            problems.append(f"{stage}: target membership differs from the declared allocation")
        recs = load_records(hub, stage, problems)
        if set(recs) != set(calls):
            problems.append(f"{stage}: records missing {len(set(calls) - set(recs))}, extra {len(set(recs) - set(calls))}")
        bad = sorted(c for c in calls if c in recs and not record_usable(recs[c], calls[c]))
        if bad:
            problems.append(f"{stage}: {len(bad)} records not usable (status/recipe/prompt/stop): {bad[:3]}")
        end = hub / "stages" / stage / "END.json"
        if not end.is_file() or json.loads(end.read_text()).get("finished") is not True or \
                (hub / "stages" / stage / "STOP.json").exists():
            problems.append(f"{stage}: stage did not finish")
        for att in (hub / "stages" / stage).glob("attempts.jsonl"):
            if att.read_text().strip():
                problems.append(f"{stage}: failed attempts recorded")
        bundle[stage] = {"calls": calls, "public": pubs, "hidden": hid, "records": recs}
    info = {"complete": not problems, "problems": problems,
            "records": {s: len(b["records"]) for s, b in bundle.items()},
            "source_sha256": release_source_hash(ROOT), "frozen_source_sha256": frozen.get("source_sha256")}
    return info, bundle, cfg


RECEPTION_DATED = "arrival with correct event and result state dated at the true receipt time"


def subpattern(s, raw, pub, hid):
    """Descriptive label for a non-exact response (None when exact). Frozen definitions and precedence:
    1. unparsed (claims cannot be normalized);
    2. arrival with spurious revisions (any revision on an arrival target);
    3. RECEPTION_DATED, the narrow reviewed pattern: true receipt later than the true event; reply metadata
       (rid, status, received_at) equal to the original; exactly one event, with the gold field, time and result;
       exactly one state, with the gold field and result, dated at the true receipt time; no revisions;
    4. correction with spurious events (any event on a correction target);
    5. otherwise the scorer's outcome label.
    The hidden canonical case is used only here, in analysis; never in prompts or the guard."""
    if s["exact"]:
        return None
    claims = FA.compile_reply(raw, pub["registry"])[1]["claims"] if isinstance(raw, str) else None
    if claims is None:
        return "unparsed" + (" (truncated)" if s.get("truncated") else "")
    if s["act"] == "arrival":
        if claims["revisions"]:
            return "arrival with spurious revisions"
        case = hid["case"]
        gold = case["records"][-1]
        field, to, event_at, recv = gold["payload"]["field"], gold["payload"].get("to"), gold["event_at"], case["recv"]
        meta_ok = (claims.get("rid") == gold.get("rid") and claims.get("status") == gold.get("status")
                   and claims.get("received_at") == recv)
        events, states = claims["events"], claims["states"]
        if recv > event_at and meta_ok and len(events) == 1 and len(states) == 1 \
                and events[0]["field"] == field and events[0]["at"] == event_at and events[0].get("to") == to \
                and states[0] == {"field": field, "at": recv, "value": to}:
            return RECEPTION_DATED
    elif claims["events"]:
        return "correction with spurious events"
    return s["outcome"]


def score(bundle):
    guard = load_guard()
    rows = []
    for cid in sorted(bundle["calls"]):
        call = bundle["calls"][cid]
        tid = cid.rsplit("|", 1)[0]
        pub, hid = bundle["public"][tid], bundle["hidden"][tid]
        rec = bundle["records"].get(cid)
        rec = dict(rec) if record_usable(rec, call) else None
        if rec is not None and not isinstance(rec.get("raw"), (str, type(None))):
            rec["raw"] = None
        s = CA.score_one(rec, hid, pub, call)
        s.update(bits="".join(map(str, pub["bits"])), block=pub["block"], outcome=KS.outcome(s),
                 wording=ES.wording(pub["bits"]))
        raw = rec["raw"] if rec else None
        d = guard.decide(pub["prefix"], pub["target_text"], pub["registry"], pub["registry_order"], raw)
        s.update(guard_disposition=d["disposition"], guard_mismatch=d["mismatch_kind"], guard_pass=d["guard_pass"],
                 guard_resolved=d["resolver"]["field"], guard_compiled_fields=d["compiled_fields"])
        s["final_accepted"] = bool(s.get("accepted")) and d["guard_pass"]
        s["usable_exact"] = bool(s["exact"]) and d["guard_pass"]
        s["post_wrong_binding"] = s["final_accepted"] and not s.get("bound_ok_accepted")
        s["exact_blocked"] = bool(s["exact"]) and not d["guard_pass"]
        s["subpattern"] = subpattern(s, raw, pub, hid)
        rows.append(s)
    return rows


def summarize_rows(rows, keys):
    out = cells(rows, keys)
    groups = collections.defaultdict(list)
    for r in rows:
        groups["|".join(str(r[k]) for k in keys)].append(r)
    for k, rs in groups.items():
        out[k]["subpatterns"] = dict(collections.Counter(r["subpattern"] for r in rs if r["subpattern"]))
    return out


def bootstrap(diffs, strata, B, seed):
    rng = random.Random(seed)
    groups = collections.defaultdict(list)
    for stem, d in sorted(diffs.items()):
        groups[strata[stem]].append(d)
    n = sum(len(v) for v in groups.values())
    means = []
    for _ in range(B):
        total = 0.0
        for g in sorted(groups):
            v = groups[g]
            total += sum(v[rng.randrange(len(v))] for _ in v)
        means.append(total / n)
    means.sort()
    return [means[int(0.025 * B)], means[int(0.975 * B) - 1]]


def contrast(rows, act, pos, neg, boot, metric="exact", wording=None, reception=None):
    by = collections.defaultdict(dict)
    strata = {}
    for r in rows:
        if r["act"] == act and (wording is None or r["wording"] == wording) and r["arm"] in (pos, neg) \
                and (reception is None or r["reception"] == reception):
            by[(r["stem"], r["direction"], r["history"])][r["arm"]] = bool(r.get(metric))
            strata[r["stem"]] = f"{r['family']}|{r['reception']}"
    stems = collections.defaultdict(list)
    for (stem, _d, _h), v in by.items():
        stems[stem].append(v[pos] - v[neg])
    d = {stem: statistics.mean(v) for stem, v in stems.items()}
    lo, hi = bootstrap(d, strata, boot["B"], boot["seed"])
    return {"stems": len(d), "difference_points": 100 * statistics.mean(d.values()),
            "bootstrap95_points": [100 * lo, 100 * hi],
            "rescues": sum(v[pos] and not v[neg] for v in by.values()),
            "breaks": sum(v[neg] and not v[pos] for v in by.values()),
            "stems_with_net_gain": sum(1 for x in d.values() if x > 0),
            "stems_with_net_loss": sum(1 for x in d.values() if x < 0)}


def contrasts(rows, key):
    boot = PLANS[key]["bootstrap"]
    acts = ("arrival",) if key == "C" else ("arrival", "correction")
    out = {}
    for pos, neg in PAIRS[key]:
        for metric in ("exact", "usable_exact"):
            tag = "" if metric == "exact" else "usable_exact|"
            for act in acts:
                out[f"{act}|{tag}{pos}-{neg}"] = contrast(rows, act, pos, neg, boot, metric)
            for w in ("RESULT", "TRANSITION"):
                out[f"arrival|{w}|{tag}{pos}-{neg}"] = contrast(rows, "arrival", pos, neg, boot, metric, w)
            if key == "D":   # declared slices (V1.29.0); A-C contrasts are unchanged
                for w in ("RESULT", "TRANSITION"):
                    for rec in ("immediate", "delayed"):
                        out[f"arrival|{w}|{rec}|{tag}{pos}-{neg}"] = contrast(rows, "arrival", pos, neg, boot,
                                                                             metric, w, rec)
    return out


def reception_dated(rows, arm):
    return sum(1 for r in rows if r["arm"] == arm and r["act"] == "arrival" and r["subpattern"] == RECEPTION_DATED)


def reception_dated_descriptives(rows, arm_names):
    """Study D declared descriptives: RECEPTION_DATED by arm x history / family; discordant stems + sign test."""
    by_cell = collections.Counter()
    stems = collections.defaultdict(lambda: collections.defaultdict(bool))
    for r in rows:
        if r["act"] == "arrival":
            stems[r["stem"]][r["arm"]] |= r["subpattern"] == RECEPTION_DATED
            if r["subpattern"] == RECEPTION_DATED:
                by_cell[f"{r['arm']}|history {r['history']}"] += 1
                by_cell[f"{r['arm']}|{r['family']}"] += 1
    pair = {}
    for pos, neg in PAIRS["D"]:
        only_pos = sum(v[pos] and not v[neg] for v in stems.values())
        only_neg = sum(v[neg] and not v[pos] for v in stems.values())
        pair[f"{pos}-{neg}"] = {"only_" + pos: only_pos, "only_" + neg: only_neg,
                                "both": sum(v[pos] and v[neg] for v in stems.values()),
                                "sign_test_two_sided_p": sign_test(only_pos, only_neg)}
    return {"counts": {a: reception_dated(rows, a) for a in arm_names}, "by_cell": dict(sorted(by_cell.items())),
            "stems_discordant": pair,
            "note": "stem-level: a stem counts for an arm when any of its arrival targets is RECEPTION_DATED"}


def clopper_pearson(k, n, alpha=0.05):
    def cdf(x, p):
        return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(x + 1))

    def solve(f):
        lo, hi = 0.0, 1.0
        for _ in range(100):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if f(mid) else (lo, mid)
        return (lo + hi) / 2
    lower = 0.0 if k == 0 else solve(lambda p: 1 - cdf(k - 1, p) < alpha / 2)
    upper = 1.0 if k == n else solve(lambda p: cdf(k, p) > alpha / 2)
    return [lower, upper]


def sign_test(a, b):
    n = a + b
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(min(a, b) + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def new_classes(by_arm_act, cand, cur, acts):
    out = {}
    for act in acts:
        for field in ("outcomes", "subpatterns"):
            current = set(by_arm_act[f"{cur}|{act}"][field])
            new = {k: v for k, v in by_arm_act[f"{cand}|{act}"][field].items() if k not in current}
            if new:
                out[f"{act}|{field}"] = new
    return out


def reading(key, rows, by_arm_act, cons):
    plan = PLANS[key]
    arm_names = S.SPECS[key]["arms"]
    wb = {a: sum(r["accepted_wrong_binding"] for r in rows if r["arm"] == a) for a in arm_names}
    post = {a: sum(r["post_wrong_binding"] for r in rows if r["arm"] == a) for a in arm_names}
    blocked = {a: sum(r["exact_blocked"] for r in rows if r["arm"] == a) for a in arm_names}
    so = {a: by_arm_act[f"{a}|arrival"]["state_only_event_accepted"] for a in arm_names}
    violation = any(post.values()) or any(blocked.values())
    base = {"pipeline_invariant_violation": violation, "accepted_wrong_bindings": wb, "post_guard_wrong_bindings": post, "exact_blocked": blocked,
            "state_only_arrivals": so,
            "meaning": "one fresh panel of generated worlds (assembly domain), one model, fixed decoding; "
                       "not qualification, not a rare-error, transfer or safety claim"}
    if key == "A":
        p = cons["arrival|usable_exact|KEEP_EVT-KEEP_CLAR"]
        crit = {
            "usable_exact_arrival_gain": p["difference_points"] > 0 and p["bootstrap95_points"][0] > 0,
            "transition_usable_exact_not_lower_than_3_points":
                cons["arrival|TRANSITION|usable_exact|KEEP_EVT-KEEP_CLAR"]["difference_points"] >= -3.0,
            "post_guard_wrong_bindings_not_more": post["KEEP_EVT"] <= post["KEEP_CLAR"],
            "exact_blocked_at_most_1_per_arm": all(v <= 1 for v in blocked.values()),
            "correction_usable_exact_not_lower_than_3_64":
                cons["correction|usable_exact|KEEP_EVT-KEEP_CLAR"]["difference_points"] >= CORR_MIN_POINTS,
        }
        new = new_classes(by_arm_act, "KEEP_EVT", "KEEP_CLAR", ("arrival", "correction"))
        status = "DOES_NOT_CONFIRM" if not all(crit.values()) else \
            "REVIEW_NEW_FAILURE_TYPES" if new else "CONFIRMS_ON_THIS_PANEL"
        return {"status": status, "criteria": crit, "new_in_candidate": new, **base}
    if key == "D":
        rd = {a: reception_dated(rows, a) for a in arm_names}
        crit = {
            "reception_dated_halved_with_keep_evt_at_least_6":
                rd["KEEP_EVT"] >= RD_FLOOR and rd["KEEP_EVTT"] <= rd["KEEP_EVT"] // 2,
            "arrival_exact_not_lower": cons["arrival|KEEP_EVTT-KEEP_EVT"]["difference_points"] >= 0,
            "state_only_within_2": so["KEEP_EVTT"] <= so["KEEP_EVT"] + STATE_ONLY_TOLERANCE,
            "immediate_result_exact_not_lower_than_3_points":
                cons["arrival|RESULT|immediate|KEEP_EVTT-KEEP_EVT"]["difference_points"] >= -3.0,
            "transition_exact_not_lower_than_3_points":
                cons["arrival|TRANSITION|KEEP_EVTT-KEEP_EVT"]["difference_points"] >= -3.0,
            "wrong_bindings_within_4": wb["KEEP_EVTT"] <= wb["KEEP_EVT"] + WB_TOLERANCE_D,
            "correction_exact_not_lower_than_3_64":
                cons["correction|KEEP_EVTT-KEEP_EVT"]["difference_points"] >= CORR_MIN_POINTS,
        }
        new = new_classes(by_arm_act, "KEEP_EVTT", "KEEP_EVT", ("arrival", "correction"))
        floor_met = rd["KEEP_EVT"] >= RD_FLOOR
        others = [v for k, v in crit.items() if k != "reception_dated_halved_with_keep_evt_at_least_6"]
        if not all(others):
            status = "DOES_NOT_WARRANT"
        elif not floor_met:
            status = "INSUFFICIENT_TARGET_ERRORS"
        elif not crit["reception_dated_halved_with_keep_evt_at_least_6"]:
            status = "DOES_NOT_WARRANT"
        else:
            status = "REVIEW_NEW_FAILURE_TYPES" if new else "WARRANTS_CONFIRMATION_DESIGN"
        return {"status": status, "criteria": crit, "new_in_candidate": new, "reception_dated": rd,
                "target_error_floor_met": floor_met, **base}
    if key == "B":
        crit = {
            "state_only_halved_with_baseline_at_least_10":
                so["KEEP_CLAR"] >= 10 and so["KEEP_EVTR"] <= so["KEEP_CLAR"] // 2,
            "arrival_exact_not_lower": cons["arrival|KEEP_EVTR-KEEP_CLAR"]["difference_points"] >= 0,
            "transition_exact_not_lower_than_3_points":
                cons["arrival|TRANSITION|KEEP_EVTR-KEEP_CLAR"]["difference_points"] >= -3.0,
            "transition_exact_not_below_keep_evt":
                cons["arrival|TRANSITION|KEEP_EVTR-KEEP_EVT"]["difference_points"] >= 0,
            "wrong_bindings_within_pooled_tolerance": wb["KEEP_EVTR"] <= wb["KEEP_CLAR"] + POOLED_WB["k"],
            "correction_exact_not_lower_than_3_64":
                cons["correction|KEEP_EVTR-KEEP_CLAR"]["difference_points"] >= CORR_MIN_POINTS,
        }
        new = new_classes(by_arm_act, "KEEP_EVTR", "KEEP_CLAR", ("arrival", "correction"))
        status = "DOES_NOT_WARRANT" if not all(crit.values()) else \
            "REVIEW_NEW_FAILURE_TYPES" if new else "WARRANTS_CONFIRMATION_DESIGN"
        return {"status": status, "criteria": crit, "new_in_candidate": new, **base}
    n = {a: by_arm_act[f"{a}|arrival"]["n"] for a in arm_names}
    rates = {a: {"wrong_bindings": wb[a], "n": n[a], "rate": wb[a] / n[a], "cp95": clopper_pearson(wb[a], n[a]),
                 "post_guard": post[a], "post_guard_cp95": clopper_pearson(post[a], n[a]),
                 "exact_blocked": blocked[a]} for a in arm_names}
    by = collections.defaultdict(dict)
    for r in rows:
        by[r["stem"]][r["arm"]] = bool(r["accepted_wrong_binding"])
    pair = {}
    for pos, neg in PAIRS["C"]:
        only_pos = sum(v[pos] and not v[neg] for v in by.values())
        only_neg = sum(v[neg] and not v[pos] for v in by.values())
        pair[f"{pos}-{neg}"] = {"only_" + pos: only_pos, "only_" + neg: only_neg,
                                "both": sum(v[pos] and v[neg] for v in by.values()),
                                "sign_test_two_sided_p": sign_test(only_pos, only_neg)}
    subgroups = {}
    for dim in ("wording", "family"):
        g = collections.defaultdict(list)
        for r in rows:
            g[f"{r['arm']}|{r[dim]}"].append(r)
        subgroups[dim] = {}
        for k, rs in sorted(g.items()):
            pre = sum(r["accepted_wrong_binding"] for r in rs)
            pst = sum(r["post_wrong_binding"] for r in rs)
            subgroups[dim][k] = {"n": len(rs), "wrong_bindings": pre, "cp95": clopper_pearson(pre, len(rs)),
                                 "post_guard": pst, "post_guard_cp95": clopper_pearson(pst, len(rs)),
                                 "exact": sum(r["exact"] for r in rs), "exact_blocked": sum(r["exact_blocked"] for r in rs)}
    return {"status": "DESCRIPTIVE_COMPLETE",
            "wrong_binding_rates": rates, "wrong_binding_rates_by_subgroup": subgroups,
            "pairwise_discordance": pair, **base}


def analyze(hub, during_driver=False):
    from su_certify import inventory
    before = inventory(hub)
    info, bundle, cfg = integrity(hub, during_driver)
    key = cfg["key"]
    result = {"study": cfg["study"], "key": key, "plan": PLANS[key], "infrastructure": info}
    if not info["complete"]:
        result.update(status="INCOMPLETE", reading={"status": "NOT_EVALUATED"},
                      inference_suppressed="Incomplete collection: no reading or intervals.")
        return result, []
    rows = score(bundle["main"])
    if inventory(hub) != before:
        info.update(complete=False, problems=["collected records changed during analysis"])
        result.update(status="INCOMPLETE", reading={"status": "NOT_EVALUATED"},
                      inference_suppressed="Evidence changed during analysis: no reading.")
        return result, []
    violators = [r["call_id"] for r in rows if r["post_wrong_binding"] or r["exact_blocked"]]
    if violators:
        info.update(complete=False, problems=[f"pipeline invariant violated by {len(violators)} responses"])
        result.update(status="INCOMPLETE", reading={"status": "NOT_EVALUATED",
                      "diagnostic": "PIPELINE_INVARIANT_VIOLATION", "violating_calls": violators[:50],
                      "rule": INVARIANT_RULE},
                      inference_suppressed="Pipeline invariant violated: investigate before any reading.")
        return result, []
    result["evidence_inventory_sha256"] = before
    arm_names = S.SPECS[key]["arms"]
    by_arm_act = summarize_rows(rows, ("arm", "act"))
    cons = contrasts(rows, key)
    result.update(
        status="COMPLETE", reading=reading(key, rows, by_arm_act, cons), by_arm_act=by_arm_act, contrasts=cons,
        breakdowns_descriptive={"|".join(k): summarize_rows(rows, ("arm", "act") + k) for k in
                                (("wording",), ("family",), ("family", "history"), ("reception",), ("bits",),
                                 ("direction",), ("family", "wording"), ("history", "wording"))},
        wrong_bindings=[{k: r.get(k) for k in ("call_id", "family", "history", "reception", "bits", "wording",
                                                "guard_disposition", "guard_compiled_fields", "guard_resolved")}
                        for r in rows if r["accepted_wrong_binding"]],
        non_exact=[{k: r.get(k) for k in ("call_id", "wording", "reception", "outcome", "subpattern",
                                           "guard_disposition", "output_tokens", "stop")}
                   for r in rows if not r["exact"]],
        exact_blocked_by_guard=[r["call_id"] for r in rows if r["exact_blocked"]],
        truncated=[r["call_id"] for r in rows if r.get("truncated")],
        **({"reception_dated_descriptive": reception_dated_descriptives(rows, arm_names),
            "wording_x_reception": summarize_rows([r for r in rows if r["act"] == "arrival"],
                                                  ("arm", "wording", "reception"))} if key == "D" else {}),
        cost={a: {"seconds_mean": statistics.mean(r["seconds"] for r in rows if r["arm"] == a),
                  "input_tokens_max": max(r["input_tokens"] for r in rows if r["arm"] == a),
                  "output_tokens_mean": statistics.mean(r["output_tokens"] for r in rows if r["arm"] == a),
                  "output_tokens_max": max(r["output_tokens"] for r in rows if r["arm"] == a)}
              for a in arm_names})
    return result, rows


def esc(x):
    return str(x).replace("|", "\\|")


def render(result):
    if result["status"] != "COMPLETE":
        lines = [f"# {result.get('study') or 'EVT-suite study'}: incomplete", "",
                 "**Status: INCOMPLETE.** No reading or intervals.", ""]
        if result.get("reading", {}).get("diagnostic"):
            lines += [f"Diagnostic: **{result['reading']['diagnostic']}** - {result['reading']['rule']}", ""]
        lines += ["Problems:", ""] + [f"- {esc(p)}" for p in result["infrastructure"]["problems"][:40]]
        return "\n".join(lines) + "\n"
    title = {"A": "EVTC-v1 confirmation: KEEP_EVT + IGUARD vs KEEP_CLAR + IGUARD",
             "B": "EVTR-v1 development screen: narrowed event sentence (KEEP_EVTR)",
             "C": "EVTB-v1 descriptive wrong-binding panel (history-B arrivals)",
             "D": "EVTT-v1 development screen: combined event + state-time sentence (KEEP_EVTT)"}[result["key"]]
    L = [f"# {title}", ""]
    if result["status"] != "COMPLETE":
        L += ["**Status: INCOMPLETE.** No reading or intervals.", "", "Problems:", ""] + \
             [f"- {esc(p)}" for p in result["infrastructure"]["problems"][:40]]
        return "\n".join(L) + "\n"
    key, rd = result["key"], result["reading"]
    arm_names = S.SPECS[key]["arms"]
    acts = ("arrival",) if key == "C" else ("arrival", "correction")
    L += [f"**Status: COMPLETE. Reading: {rd['status']}.** {result['plan']['role']}.", "",
          "Qwen3-32B NF4, greedy, thinking off. Fresh generated worlds (assembly domain). RESULT and TRANSITION "
          "arrival wordings balanced in every family x reception stratum.", "", "## Side by side", "",
          "| Arm / act | Exact | Usable exact (guard) | State-only | Wrong binding (before → after guard) | "
          "Exact blocked | Rejected | Truncated | With revision objects | With event objects |",
          "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for a in arm_names:
        for act in acts:
            c = result["by_arm_act"][f"{a}|{act}"]
            L.append(f"| {a} {act} | {c['exact']}/{c['n']} | {c['usable_exact']}/{c['n']} | "
                     f"{c['state_only_event_accepted']} | {c['accepted_wrong_binding']} → {c['post_wrong_binding']} | "
                     f"{c['exact_blocked']} | {c['rejected']} | {c['truncated']} | "
                     f"{c['responses_with_revision_objects']} | {c['responses_with_event_objects']} |")
    L += ["", "Object-presence counts come from normalized parsed raw claims, including compiler-rejected replies; "
          "replies that fail parsing/normalization are excluded from them.", "",
          "## Arrivals by wording", "", "| Arm | Wording | Exact | Usable exact | State-only | Wrong binding | Rejected |",
          "|---|---|---:|---:|---:|---:|---:|"]
    bw = result["breakdowns_descriptive"]["wording"]
    for a in arm_names:
        for w in ("RESULT", "TRANSITION"):
            c = bw.get(f"{a}|arrival|{w}")
            if c:
                L.append(f"| {a} | {w} | {c['exact']}/{c['n']} | {c['usable_exact']}/{c['n']} | "
                         f"{c['state_only_event_accepted']} | {c['accepted_wrong_binding']} | {c['rejected']} |")
    if key == "D":
        L += ["", "## Arrivals by wording x reception (declared)", "",
              "| Arm | Wording | Reception | Exact | State-only | Reception-dated | Wrong binding | Rejected |",
              "|---|---|---|---:|---:|---:|---:|---:|"]
        for a in arm_names:
            for w in ("RESULT", "TRANSITION"):
                for rec in ("immediate", "delayed"):
                    c = result["wording_x_reception"].get(f"{a}|{w}|{rec}")
                    if c:
                        L.append(f"| {a} | {w} | {rec} | {c['exact']}/{c['n']} | {c['state_only_event_accepted']} | "
                                 f"{c['subpatterns'].get(RECEPTION_DATED, 0)} | {c['accepted_wrong_binding']} | "
                                 f"{c['rejected']} |")
        d = result["reception_dated_descriptive"]
        L += ["", f"Reception-dated replies (all arrivals): {esc(d['counts'])}. By cell: {esc(d['by_cell'] or 'none')}.",
              "", "Stems with any reception-dated reply, discordant between arms (descriptive):", ""]
        L += [f"- {k}: {esc(v)}" for k, v in d["stems_discordant"].items()]
    L += ["", "## Paired stem differences", "",
          "| Contrast | Stems | Difference (points) | Bootstrap 95% (points) | Target rescues / breaks |",
          "|---|---:|---:|---:|---:|"]
    for k, c in result["contrasts"].items():
        lo, hi = c["bootstrap95_points"]
        L.append(f"| {esc(k)} | {c['stems']} | {c['difference_points']:+.2f} | [{lo:+.2f}, {hi:+.2f}] | "
                 f"{c['rescues']} / {c['breaks']} |")
    L += ["", f"Bootstrap use: {result['plan']['bootstrap']['use']}.", "", "## Reading (frozen before output)", ""]
    if "criteria" in rd:
        L += ["| Criterion | Rule | Result |", "|---|---|---|"]
        L += [f"| {k} | {esc(result['plan']['criteria'][k])} | {'pass' if v else '**fail**'} |"
              for k, v in rd["criteria"].items()]
        L += ["", f"New outcome classes or sub-patterns under the candidate: {esc(rd['new_in_candidate'] or 'none')}."]
        if key == "D":
            L += ["", f"Target-error floor (KEEP_EVT reception-dated >= {RD_FLOOR}): "
                  f"{'met' if rd['target_error_floor_met'] else '**not met**'} ({esc(rd['reception_dated'])}). "
                  "Precedence: " + esc("; ".join(result["plan"]["precedence"])) + "."]
    else:
        L += ["| Arm | Wrong bindings | Rate | Clopper-Pearson 95% | After guard | Exact blocked |",
              "|---|---:|---:|---:|---:|---:|"]
        for a, v in rd["wrong_binding_rates"].items():
            L.append(f"| {a} | {v['wrong_bindings']}/{v['n']} | {100 * v['rate']:.2f}% | "
                     f"[{100 * v['cp95'][0]:.2f}%, {100 * v['cp95'][1]:.2f}%] | {v['post_guard']} | {v['exact_blocked']} |")
        L += ["", "Pairwise discordant wrong-binding stems (pre-declared, descriptive):", ""]
        L += [f"- {k}: {esc(v)}" for k, v in rd["pairwise_discordance"].items()]
    if "wrong_binding_rates_by_subgroup" in rd:
        L += ["", "Wrong-binding rates by subgroup (nominal descriptive 95% intervals; no simultaneous coverage):", "",
              "| Subgroup | n | Wrong bindings [95%] | After guard [95%] |", "|---|---:|---:|---:|"]
        for dim, groups in rd["wrong_binding_rates_by_subgroup"].items():
            for k, v in groups.items():
                L.append(f"| {esc(k)} | {v['n']} | {v['wrong_bindings']} [{100 * v['cp95'][0]:.2f}%, "
                         f"{100 * v['cp95'][1]:.2f}%] | {v['post_guard']} [{100 * v['post_guard_cp95'][0]:.2f}%, "
                         f"{100 * v['post_guard_cp95'][1]:.2f}%] |")
    if result["plan"].get("interpretation"):
        L += ["", f"**Interpretation fixed before output:** {result['plan']['interpretation']}"]
    L += ["", f"**Guard invariants:** {INVARIANT_NOTE} Violation in this run: "
          f"{'YES - investigate before certification' if rd['pipeline_invariant_violation'] else 'none'}."]
    L += ["", f"State-only arrivals: {rd['state_only_arrivals']}. Accepted wrong bindings: "
          f"{rd['accepted_wrong_bindings']}; after guard: {rd['post_guard_wrong_bindings']}; exact blocked: "
          f"{rd['exact_blocked']}.", "", "## Non-exact sub-patterns (descriptive)", "",
          "| Arm / act | Sub-patterns |", "|---|---|"]
    for a in arm_names:
        for act in acts:
            L.append(f"| {a} {act} | {esc(result['by_arm_act'][f'{a}|{act}']['subpatterns'] or 'none')} |")
    L += ["", "Accepted wrong bindings (all listed):", ""]
    L += [f"- `{w['call_id']}` {w['wording']} bits {w['bits']} {w['reception']}: guard {w['guard_disposition']} "
          f"({w['guard_compiled_fields']} vs {w['guard_resolved']})" for w in result["wrong_bindings"]] or ["- none"]
    L += ["", f"Truncated replies: {result['truncated'] or 'none'}. Exact answers blocked by the guard: "
          f"{result['exact_blocked_by_guard'] or 'none'}.", "", "## Cost", ""]
    L += [f"- {a}: mean {c['seconds_mean']:.1f} s/call, max input {c['input_tokens_max']} tokens, mean output "
          f"{c['output_tokens_mean']:.0f} tokens (max {c['output_tokens_max']})" for a, c in result["cost"].items()]
    L += ["", "## Scope", "",
          "- One fresh panel of generated worlds of the declared families (assembly domain only), one model, fixed "
          "decoding.",
          "- Passing a threshold on a point estimate is not equivalence or non-inferiority.",
          "- Rejected answers remain wrong; the guard turns detected identity mismatches into rejections. It does "
          "not address event omission.",
          "- No qualification, transfer, rare-error elimination or safety claim. The protocol stops after reporting.",
          "", "Full data: `analysis/dev/ANALYSIS.json`, per-call `analysis/dev/scored.jsonl`."]
    return "\n".join(L) + "\n"


def _had_complete_authority(hub):
    if (Path(hub) / "DRIVER-SUCCESS.json").exists():
        return True
    try:
        old = json.loads((Path(hub) / OUT / "ANALYSIS.json").read_text())
        return isinstance(old, dict) and old.get("status") == "COMPLETE"
    except (OSError, ValueError):
        return False


def _incomplete(problem, base=None):
    base = base or {}
    return {"study": base.get("study"), "key": base.get("key"), "status": "INCOMPLETE",
            "reading": {"status": "NOT_EVALUATED"}, "plan": base.get("plan", {}),
            "infrastructure": {"complete": False, "problems": [problem[:500]]},
            "inference_suppressed": "Damaged evidence or artifact failure: no reading."}


def write_artifacts(hub, during_driver=False):
    hub = Path(hub)
    try:
        result, rows = analyze(hub, during_driver)
    except Exception as e:  # damaged PANEL/freeze/END/record/terminal structures: fail closed (recheck R3)
        result, rows = _incomplete(f"analysis failed: {e!r}"), []
    try:  # render before committing anything; a rendering failure is an infrastructure failure (C2)
        report = render(result)
    except Exception as e:
        result, rows = _incomplete(f"report rendering failed: {e!r}", result), []
        report = render(result)
    out = hub / OUT
    out.mkdir(parents=True, exist_ok=True)
    if result["status"] != "COMPLETE":
        if _had_complete_authority(hub):
            atomic_json(hub / "runtime/INVALIDATED.json", {"at": datetime.now().isoformat(timespec="seconds"),
                        "problems": result["infrastructure"]["problems"][:20]})
        stale = [p for p in (out / "scored.jsonl", hub / "DRIVER-SUCCESS.json") if p.exists()]
        if stale:
            archive = hub / "analysis/invalidated" / datetime.now().strftime("%Y%m%dT%H%M%S%f")
            archive.mkdir(parents=True, exist_ok=True)
            for path in stale:
                path.rename(archive / path.name)
    if rows:
        with open(out / "scored.jsonl", "w") as f:
            for r in rows:
                f.write(json.dumps(r, sort_keys=True, default=str) + "\n")
    atomic_json(out / "ANALYSIS.json", result)
    (hub / "REPORT.md").write_text(report)
    status = result["status"] + ("" if result["status"] != "COMPLETE" else " / " + result["reading"]["status"])
    (hub / "RUN-STATUS.md").write_text(f"# Run status\n\n**{status}.**\n\nSee `REPORT.md`. No next stage started.\n")
    # Handoff commitment (C1): the exact artifacts this call produced, returned to the driver (not saved in them).
    from su_certify import sha as _sha
    commitment = {"status": result["status"], "reading": result.get("reading", {}).get("status"),
                  "evidence_inventory_sha256": result.get("evidence_inventory_sha256"),
                  "analysis_sha256": _sha(out / "ANALYSIS.json"), "report_sha256": _sha(hub / "REPORT.md"),
                  "scored_sha256": _sha(out / "scored.jsonl") if rows else None}
    return dict(result, artifact_commitment=commitment)


if __name__ == "__main__":
    r = write_artifacts(sys.argv[1])
    print(json.dumps({"status": r["status"], "reading": r.get("reading", {}).get("status")}))
