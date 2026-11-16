#!/usr/bin/env python3
"""Preregistered analysis for E1 (PREREGISTRATION_E1_E5.md, Sections 3-6). Pure Python, no model calls.

Input: pairwise-v1 pair records (JSONL, one line per pair, the format written by the frozen runner's
judge_pair): {pair_id, meta: {model, task_id, family, seed, baseline, steer_id, baseline_id}, orders:
{forward|reverse: {A, B, raw: {dim: A|B|TIE}, canonical: {dim: unit_id|TIE}}}, complete, consistency}.

  analyze_e1_pairwise.py --pairs PAIRS.jsonl [--lineage L.jsonl] [--audit AUDIT.jsonl]
                         (--e4-record E4.json | --exploratory) --out SUMMARY.json

--exploratory labels the output as non-confirmatory and skips the E4 gate (used only to test this script on
already-seen pilot data). Confirmatory use requires --e4-record: the completed E4 human-calibration record
(Section 9, item 3); without it the script refuses to report arm-level results.
"""
import argparse
import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path

DIMS = ("useful_originality", "novelty", "usefulness", "coherence")
PRIMARY = "useful_originality"
STEER = "targeted"
CONTRASTS = ("strong_prompt", "high_temperature", "random")      # C-A, C-B, C-D
CLAIM_CONTRASTS = ("strong_prompt", "high_temperature")           # the added-value claim needs both
SESOI = 0.25                                                      # net preference; win share (1 + 0.25) / 2 = 0.625
ALPHA = 0.05
FLIP_WARN = 0.15
BOOT_N, BOOT_SEED = 10000, 20261116
AUDIT_SHARE, AUDIT_SALT = 0.20, "e1-cross-family-audit-v1"
BT_RIDGE = 1e-3                                                    # tiny L2 penalty so separated data stay finite
LINEAGE_OK = {"faithful_development", "productive_reinterpretation"}


# ------------------------------------------------------------------ coding
def call_code(rec, order, dim):
    c = rec["orders"][order]["canonical"][dim]
    return 0 if c == "TIE" else (1 if c == rec["meta"]["steer_id"] else -1)


def pair_score(rec, dim):
    """Mean of the two order codes: -1, -0.5, 0, +0.5, +1. A hard flip (+1, -1) scores 0."""
    return Fraction(call_code(rec, "forward", dim) + call_code(rec, "reverse", dim), 2)


def task_scores(recs, dim):
    by_task = defaultdict(list)
    for r in recs:
        by_task[r["meta"]["task_id"]].append(pair_score(r, dim))
    return {t: sum(v, Fraction(0)) / len(v) for t, v in sorted(by_task.items())}


# ------------------------------------------------------------------ tests
def signflip_p(xs):
    """Exact two-sided sign-flip permutation p for the mean of xs (Fractions), by DP over integer units."""
    if not xs:
        return 1.0
    den = 1
    for x in xs:
        den = den * x.denominator // math.gcd(den, x.denominator)
    ints = [int(x * den) for x in xs]
    dist = Counter({0: 1})
    for v in ints:
        nxt = Counter()
        for s, c in dist.items():
            nxt[s + v] += c
            nxt[s - v] += c
        dist = nxt
    obs = abs(sum(ints))
    return sum(c for s, c in dist.items() if abs(s) >= obs) / 2 ** len(ints)


def sign_test(w, l):
    n = w + l
    if n == 0:
        return 1.0
    k = min(w, l)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def bootstrap_ci(xs, n=BOOT_N, seed=BOOT_SEED):
    if not xs:
        return None
    rng = random.Random(seed)
    fl = [float(x) for x in xs]
    m = sorted(sum(rng.choice(fl) for _ in fl) / len(fl) for _ in range(n))
    return [round(m[int(0.025 * n)], 4), round(m[int(0.975 * n) - 1], 4)]


def holm(ps):
    """ps: {key: p}. Returns Holm-adjusted {key: p}."""
    order = sorted(ps, key=ps.get)
    out, run = {}, 0.0
    for i, k in enumerate(order):
        run = max(run, min(1.0, (len(order) - i) * ps[k]))
        out[k] = run
    return out


# ------------------------------------------------------------------ Bradley-Terry with a position term
def bt_order_adjusted(recs, dim=PRIMARY):
    """Call-level games. P(x beats y | x shown as A) = sigmoid(th_x - th_y + gamma). Ties = half win each.
    th_targeted fixed at 0. Newton-Raphson with a small ridge. Returns {arm: theta, 'position_A': gamma}."""
    arms = sorted({r["meta"]["baseline"] for r in recs})
    idx = {a: i for i, a in enumerate(arms)}           # free parameters: one per baseline, then gamma
    k = len(arms) + 1
    games = []                                          # (baseline index, steer_shown_as_A, steer_score)
    for r in recs:
        for o in ("forward", "reverse"):
            if r["orders"][o]["A"] == r["meta"]["steer_id"]:
                a_is_steer = True
            else:
                a_is_steer = False
            s = {1: 1.0, 0: 0.5, -1: 0.0}[call_code(r, o, dim)]
            games.append((idx[r["meta"]["baseline"]], a_is_steer, s))
    th = [0.0] * k
    for _ in range(100):
        g = [-BT_RIDGE * t for t in th]
        H = [[-BT_RIDGE if i == j else 0.0 for j in range(k)] for i in range(k)]
        for b, a_is_steer, s in games:
            # linear predictor for "steer wins": (0 - th_b) + gamma * (+1 if steer is A else -1)
            sgn = 1.0 if a_is_steer else -1.0
            eta = -th[b] + sgn * th[-1]
            p = 1 / (1 + math.exp(-eta))
            x = {b: -1.0, k - 1: sgn}
            for i, xi in x.items():
                g[i] += (s - p) * xi
                for j, xj in x.items():
                    H[i][j] -= p * (1 - p) * xi * xj
        step = solve([[-h for h in row] for row in H], g)
        th = [t + d for t, d in zip(th, step)]
        if max(abs(d) for d in step) < 1e-10:
            break
    out = {STEER: 0.0}
    out.update({a: round(th[i], 4) for a, i in idx.items()})
    out["position_A"] = round(th[-1], 4)
    return out


def solve(A, b):
    n = len(b)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(M[r][c]))
        M[c], M[p] = M[p], M[c]
        for r in range(n):
            if r != c and M[c][c]:
                f = M[r][c] / M[c][c]
                M[r] = [x - f * y for x, y in zip(M[r], M[c])]
    return [M[i][n] / M[i][i] for i in range(n)]


# ------------------------------------------------------------------ summaries
def contrast_summary(recs, dim):
    ts = task_scores(recs, dim)
    xs = list(ts.values())
    ps = [pair_score(r, dim) for r in recs]
    w, t, l = sum(x > 0 for x in xs), sum(x == 0 for x in xs), sum(x < 0 for x in xs)
    mean = float(sum(xs, Fraction(0)) / len(xs)) if xs else float("nan")
    ci = bootstrap_ci(xs)
    return {"tasks": len(xs), "pairs": len(recs),
            "task_W_T_L": [w, t, l], "net_preference": round(mean, 4),
            "tie_adjusted_win_share": round((mean + 1) / 2, 4), "ci95_bootstrap_tasks": ci,
            "p_signflip": round(signflip_p(xs), 6), "p_sign_test": round(sign_test(w, l), 6),
            "pair_W_T_L": [sum(x > 0 for x in ps), sum(x == 0 for x in ps), sum(x < 0 for x in ps)],
            "pair_net_preference": round(float(sum(ps, Fraction(0)) / len(ps)), 4) if ps else None,
            "precision_vs_sesoi": precision(ci),
            "task_scores": {k: round(float(v), 4) for k, v in ts.items()}}


def precision(ci):
    if not ci:
        return None
    lo, hi = ci
    return {"excludes_zero": lo > 0 or hi < 0, "includes_sesoi": lo <= SESOI <= hi,
            "rules_out_sesoi": hi < SESOI, "lower_bound_at_or_above_sesoi": lo >= SESOI}


def order_diagnostics(recs, dim=PRIMARY):
    n = len(recs)
    flips = sum(r["consistency"][dim]["hard_flip"] for r in recs)
    cons = sum(r["consistency"][dim]["consistent"] for r in recs)
    pos = Counter(r["orders"][o]["raw"][dim] for r in recs for o in ("forward", "reverse"))
    calls = 2 * n
    return {"pairs": n, "hard_flips": flips, "hard_flip_rate": round(flips / n, 4) if n else None,
            "order_consistent": cons, "order_consistency_rate": round(cons / n, 4) if n else None,
            "position_counts": dict(pos), "second_position_win_rate": round(pos["B"] / calls, 4) if calls else None,
            "stability_warning": (flips / n > FLIP_WARN) if n else None}


def audit_selection(pair_ids):
    ranked = sorted(pair_ids, key=lambda p: hashlib.sha256(f"{AUDIT_SALT}|{p}".encode()).hexdigest())
    return ranked[:math.ceil(AUDIT_SHARE * len(ranked))]


def audit_summary(primary, audit):
    sel = audit_selection([r["pair_id"] for r in primary])
    a = {r["pair_id"]: r for r in audit if r.get("complete")}
    p = {r["pair_id"]: r for r in primary}
    done = [k for k in sel if k in a]
    sgn = lambda x: (x > 0) - (x < 0)
    agree = sum(sgn(pair_score(p[k], PRIMARY)) == sgn(pair_score(a[k], PRIMARY)) for k in done)
    exact = sum(pair_score(p[k], PRIMARY) == pair_score(a[k], PRIMARY) for k in done)
    net = lambda rs: round(float(sum((pair_score(r, PRIMARY) for r in rs), Fraction(0)) / len(rs)), 4) if rs else None
    return {"selected": len(sel), "audited_complete": len(done), "missing": sorted(set(sel) - set(done)),
            "uo_sign_agreement": [agree, len(done)], "uo_exact_pair_score_agreement": [exact, len(done)],
            "net_preference_primary_judge_on_subset": net([p[k] for k in done]),
            "net_preference_audit_judge_on_subset": net([a[k] for k in done]),
            "role": "disclosed diagnostic; does not change the primary result (Section 4)"}


def lineage_summary(recs, lineage):
    """lineage rows: {model, unit_id, member, lineage_category}. Report by arm and for steering's UO pair wins."""
    lab = defaultdict(list)
    for row in lineage:
        lab[(row["model"], row["unit_id"])].append(row["lineage_category"])
    share = lambda labels: sum(x in LINEAGE_OK for x in labels) / len(labels) if labels else None
    by_arm = defaultdict(Counter)
    for (model, unit), labels in lab.items():
        arm = unit.rsplit("__", 1)[-1]
        by_arm[f"{model}|{arm}"].update(labels)
    out = {"by_arm": {k: dict(v, linked_share=round(sum(v[x] for x in LINEAGE_OK) / sum(v.values()), 4))
                      for k, v in sorted(by_arm.items())}, "steer_uo_wins": {}}
    for model in sorted({r["meta"]["model"] for r in recs}):
        for base in CONTRASTS:
            wins = [r for r in recs if r["meta"]["model"] == model and r["meta"]["baseline"] == base
                    and pair_score(r, PRIMARY) > 0]
            shares = [s for r in wins if (s := share(lab.get((model, r["meta"]["steer_id"]), []))) is not None]
            out["steer_uo_wins"][f"{model}|{base}"] = {
                "wins": len(wins), "with_lineage": len(shares),
                "mean_linked_share_of_steer_final": round(sum(shares) / len(shares), 4) if shares else None}
    return out


def load_jsonl(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", required=True)
    ap.add_argument("--lineage")
    ap.add_argument("--audit")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--e4-record", help="completed E4 human-calibration record (JSON); required for confirmatory use")
    g.add_argument("--exploratory", action="store_true")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    status = "EXPLORATORY (not confirmatory)" if a.exploratory else "confirmatory"
    e4 = None
    if a.e4_record:
        e4 = json.loads(Path(a.e4_record).read_text())
        if not e4.get("completed"):
            raise SystemExit("E4 human-calibration record is not marked completed; arm-level results stay sealed")

    raw = load_jsonl(a.pairs)
    latest = {r["pair_id"]: r for r in raw}                          # last line per pair wins (resume-safe)
    recs = [r for r in latest.values() if r.get("complete")]
    incomplete = sorted(k for k, r in latest.items() if not r.get("complete"))
    models = sorted({r["meta"]["model"] for r in recs})

    out = {"analysis": "E1 preregistered pairwise analysis", "status": status,
           "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
           "pairs_sha256": hashlib.sha256(Path(a.pairs).read_bytes()).hexdigest(),
           "e4_record_sha256": hashlib.sha256(Path(a.e4_record).read_bytes()).hexdigest() if a.e4_record else None,
           "constants": {"SESOI_net": SESOI, "SESOI_win_share": (1 + SESOI) / 2, "alpha": ALPHA,
                         "flip_warning": FLIP_WARN, "bootstrap": [BOOT_N, BOOT_SEED], "bt_ridge": BT_RIDGE},
           "pairs_complete": len(recs), "pairs_incomplete_excluded": incomplete,
           "primary": {}, "decision": {}, "secondary": {}, "bradley_terry": {}, "order_diagnostics": {}}

    sel = lambda m, b: [r for r in recs if r["meta"]["model"] == m and r["meta"]["baseline"] == b]
    for m in models:
        for b in CONTRASTS:
            rs = sel(m, b)
            if rs:
                out["primary"][f"{m}|{b}"] = contrast_summary(rs, PRIMARY)
                out["order_diagnostics"][f"{m}|{b}"] = order_diagnostics(rs)
                sec = {d: contrast_summary(rs, d) for d in DIMS[1:]}
                adj = holm({d: sec[d]["p_signflip"] for d in sec})
                for d in sec:
                    sec[d]["p_signflip_holm_dims"] = round(adj[d], 6)
                    sec[d].pop("task_scores")
                out["secondary"][f"{m}|{b}"] = sec
        mrecs = [r for r in recs if r["meta"]["model"] == m]
        out["bradley_terry"][m] = bt_order_adjusted(mrecs)
        out["order_diagnostics"][f"{m}|all"] = order_diagnostics(mrecs)
    out["bradley_terry"]["pooled"] = bt_order_adjusted(recs)
    out["order_diagnostics"]["all"] = order_diagnostics(recs)

    # decision rule: per contrast, Holm across models; per model, both claim contrasts positive and adjusted p < alpha
    adj = {b: holm({m: out["primary"][f"{m}|{b}"]["p_signflip"] for m in models if f"{m}|{b}" in out["primary"]})
           for b in CONTRASTS}
    for m in models:
        rows = {}
        for b in CONTRASTS:
            k = f"{m}|{b}"
            if k in out["primary"]:
                out["primary"][k]["p_signflip_holm_models"] = round(adj[b][m], 6)
                rows[b] = (out["primary"][k]["net_preference"] > 0) and adj[b][m] < ALPHA
        claim = all(rows.get(b, False) for b in CLAIM_CONTRASTS)
        out["decision"][m] = {"added_value_claim_supported": claim if not a.exploratory else None,
                              "per_contrast_positive_and_significant": rows,
                              "direction_specificity_C_minus_D": rows.get("random"),
                              "stability_warning_any": any(v["stability_warning"] for k, v in out["order_diagnostics"].items()
                                                           if k.startswith(m + "|"))}
    if a.audit:
        out["cross_family_audit"] = audit_summary(recs, load_jsonl(a.audit))
    if a.lineage:
        out["lineage"] = lineage_summary(recs, load_jsonl(a.lineage))
    Path(a.out).write_text(json.dumps(out, indent=1) + "\n")

    print(f"status: {status}; pairs complete {len(recs)}, incomplete {len(incomplete)}")
    for k, v in out["primary"].items():
        od = out["order_diagnostics"][k]
        warn = "  STABILITY WARNING" if od["stability_warning"] else ""
        print(f"{k:<32} tasks {v['tasks']:>2} W/T/L {v['task_W_T_L']} net {v['net_preference']:+.3f} "
              f"{v['ci95_bootstrap_tasks']} p_perm {v['p_signflip']:.4f} (Holm {v['p_signflip_holm_models']:.4f}) "
              f"p_sign {v['p_sign_test']:.4f} | pair W/T/L {v['pair_W_T_L']} flips {od['hard_flips']}/{od['pairs']}{warn}")
    print("BT (order-adjusted):", json.dumps(out["bradley_terry"]))
    print("decision:", json.dumps(out["decision"]))


if __name__ == "__main__":
    main()
