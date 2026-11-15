"""Episode-level outcomes and paired differences with a family-stratified episode bootstrap.

Primary: complete-pair correctness (both sides of a fact-flip pair correct), W+A minus W.
Invalid or unparseable selections count as incorrect. Unrelated probes are reported separately.
"""
import argparse
import collections
import json
from pathlib import Path
import random
import statistics
import sys

from _bootstrap import ROOT

CONDS = ("W", "W+A", "W+X", "W+Y")
CONTRASTS = (("W+A", "W"), ("W+A", "W+X"), ("W+X", "W"), ("W+X", "W+Y"), ("W+Y", "W"))


def episode_metrics(ep, rows):
    by = {(r["qid"], r["condition"]): r for r in rows if r["qid"] != "_reset"}
    conds = sorted({c for _, c in by})
    out = {}
    for c in conds:
        q = {x["qid"]: x for x in ep["queries"]}
        ok = lambda qid: bool(by[(qid, c)]["correct"])
        pairs = collections.defaultdict(list)
        for x in ep["queries"]:
            if x["kind"] == "pair":
                pairs[x["pair_id"]].append(x["qid"])
        m = {
            "complete_pair": statistics.mean(all(ok(i) for i in v) for v in pairs.values()),
            "marginal": statistics.mean(ok(i) for i in q),
            "side_A": statistics.mean(ok(x["qid"]) for x in ep["queries"] if x.get("side") == "A"),
            "side_B": statistics.mean(ok(x["qid"]) for x in ep["queries"] if x.get("side") == "B"),
            "irrelevant": statistics.mean(ok(x["qid"]) for x in ep["queries"] if x["kind"] == "irrelevant"),
            "irrelevant_consistent": statistics.mean(ok(x["qid"]) == ok(x["base_qid"]) for x in ep["queries"] if x["kind"] == "irrelevant"),
            "correction": statistics.mean(ok(x["qid"]) for x in ep["queries"] if x["kind"] == "correction"),
            "stale_choice": statistics.mean(bool(by[(x["qid"], c)]["stale"]) for x in ep["queries"] if x["kind"] == "correction"),
            "invalid": statistics.mean(not by[(i, c)]["valid_format"] for i in q),
            "unrelated": statistics.mean(r["correct"] for (qid, cc), r in by.items() if cc == c and qid.startswith("unrelated")),
        }
        for flip in sorted({x.get("flip") for x in ep["queries"] if x.get("flip")}):
            ids = [v for v in pairs.values() if q[v[0]]["flip"] == flip]
            m[f"complete_pair[{flip}]"] = statistics.mean(all(ok(i) for i in v) for v in ids)
        out[c] = m
    return out


def bootstrap(diffs_by_family, n=10000, seed=0):
    rng = random.Random(seed)
    fams = [f for f in sorted(diffs_by_family) if diffs_by_family[f]]
    stats = []
    for _ in range(n):
        vals = []
        for f in fams:
            d = diffs_by_family[f]
            vals.append(statistics.mean(rng.choice(d) for _ in d))
        stats.append(statistics.mean(vals))  # equal family weights
    stats.sort()
    return stats[int(0.025 * n)], stats[int(0.975 * n) - 1]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--hub", required=True)
    ap.add_argument("--stage", required=True)
    a = ap.parse_args()
    hub = Path(a.hub); out = hub / "stages" / a.stage
    cfg = json.loads((out / "config.json").read_text())
    episodes = {e["episode_id"]: e for e in map(json.loads, (hub / "data" / f"{cfg['split']}.jsonl").read_text().splitlines())}
    per_ep, resets = {}, []
    for eid in cfg["episodes"]:
        path = out / "eval" / f"{eid}.jsonl"
        if not path.exists():
            continue
        rows = [json.loads(x) for x in path.read_text().splitlines()]
        resets += [r for r in rows if r["qid"] == "_reset"]
        per_ep[eid] = episode_metrics(episodes[eid], rows)
    conds = [c for c in CONDS if all(c in m for m in per_ep.values())] if per_ep else []
    metrics = sorted({k for m in per_ep.values() for c in m for k in m[c]})
    fam_of = {eid: episodes[eid]["family"] for eid in per_ep}
    report = {"stage": a.stage, "episodes_complete": len(per_ep), "episodes_planned": len(cfg["episodes"]),
              "equal_family_weights": True, "means": {}, "family_means": {}, "contrasts": {},
              "reset": {"all_fingerprints_unchanged": all(r["fingerprint_unchanged"] for r in resets),
                        "max_removal_logit_diff": max((r["removal_maxdiff"] for r in resets), default=None)}}
    for c in conds:
        report["means"][c] = {}
        for k in metrics:
            vals = {f: [per_ep[e][c][k] for e in per_ep if fam_of[e] == f and k in per_ep[e][c]] for f in set(fam_of.values())}
            fam_means = {f: statistics.mean(v) for f, v in vals.items() if v}
            report["family_means"].setdefault(c, {})[k] = fam_means
            report["means"][c][k] = statistics.mean(fam_means.values()) if fam_means else None
    for hi, lo in CONTRASTS:
        if hi not in conds or lo not in conds:
            continue
        name = f"{hi} - {lo}"
        report["contrasts"][name] = {}
        for k in ("complete_pair", "marginal", "side_A", "side_B", "irrelevant", "correction", "stale_choice", "unrelated", "invalid"):
            d = collections.defaultdict(list)
            for e in per_ep:
                d[fam_of[e]].append(per_ep[e][hi][k] - per_ep[e][lo][k])
            point = statistics.mean(statistics.mean(v) for v in d.values())
            lo_ci, hi_ci = bootstrap(d)
            flat = [x for v in d.values() for x in v]
            report["contrasts"][name][k] = {"diff": point, "ci95": [lo_ci, hi_ci],
                                            "episodes_better": sum(x > 0 for x in flat), "episodes_worse": sum(x < 0 for x in flat),
                                            "episode_sd": statistics.pstdev(flat)}
    train = [json.loads(p.read_text()) for p in sorted((out / "train").glob("*.json"))]
    if train:
        report["cost"] = {k: statistics.mean(t[k] for t in train) for k in
                          ("seconds", "train_tokens", "approx_train_flops", "peak_gib", "adapter_params", "loss_first", "loss_last")}
        report["cost"]["adapters_trained"] = len(train)
    (out / "ANALYSIS.json").write_text(json.dumps({"report": report, "per_episode": per_ep}, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    sys.exit(main())
