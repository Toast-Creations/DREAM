"""Multi-seed development analysis (V1.6.3; V1.6.4: per-flip means use only episodes that contain that flip type). Episodes are the independent units; seeds are training repeats.

Each seed is one or more stages over the same episodes (e.g. the original seed = s12-loo for W/W+A/W+X plus
s12-loo-cross for W+Y). Rows are merged per seed; W must be identical wherever it was evaluated twice.
Per episode, each metric is averaged over seeds first; uncertainty is a world-stratified bootstrap over the
12 episodes (equal world weights). Primary: complete-pair W+A - W. Mechanism diagnostics: W+A - W+X (own vs
same-world wrong) and W+X - W+Y (same-world wrong vs different-world wrong).
Usage: ectx_seed_analysis.py --hub HUB --seed NAME=stage[,stage] ... --out FILE
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
CONTRASTS = (("W+A", "W"), ("W+A", "W+X"), ("W+X", "W+Y"), ("W+X", "W"), ("W+Y", "W"))
METRICS = ("complete_pair", "marginal", "correction", "stale", "side_A", "side_B", "irrelevant")


def metrics(ep, R, cond):
    ok = lambda q: bool(R[(q["qid"], cond)]["correct"])
    pairs = collections.defaultdict(list)
    for q in ep["queries"]:
        if q["kind"] == "pair":
            pairs[q["pair_id"]].append(q)
    m = {"complete_pair": statistics.mean(all(ok(q) for q in v) for v in pairs.values()),
         "marginal": statistics.mean(ok(q) for q in ep["queries"]),
         "correction": statistics.mean(ok(q) for q in ep["queries"] if q["kind"] == "correction"),
         "stale": statistics.mean(bool(R[(q["qid"], cond)]["stale"]) for q in ep["queries"] if q["kind"] == "correction"),
         "side_A": statistics.mean(ok(q) for q in ep["queries"] if q.get("side") == "A"),
         "side_B": statistics.mean(ok(q) for q in ep["queries"] if q.get("side") == "B"),
         "irrelevant": statistics.mean(ok(q) for q in ep["queries"] if q["kind"] == "irrelevant")}
    for v in pairs.values():
        m.setdefault("flip:" + v[0]["flip"], []).append(all(ok(q) for q in v))
    m.update({k: statistics.mean(v) for k, v in m.items() if k.startswith("flip:")})
    return m


def world_mean(values, world):
    by = collections.defaultdict(list)
    for e, v in values.items():
        by[world[e]].append(v)
    wm = {w: statistics.mean(v) for w, v in by.items()}
    return statistics.mean(wm.values()), wm, by


def bootstrap(by, n=10000, seed=0):
    rng = random.Random(seed)
    stats = sorted(statistics.mean(statistics.mean(rng.choice(v) for _ in v) for v in by.values()) for _ in range(n))
    return [stats[int(0.025 * n)], stats[int(0.975 * n) - 1]]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--hub", required=True)
    ap.add_argument("--seed", action="append", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    hub = Path(a.hub)
    seeds, split, ids = {}, None, None
    for spec in a.seed:
        name, stages = spec.split("=")
        R, W_seen = {}, {}
        for st in stages.split(","):
            cfg = json.loads((hub / "stages" / st / "config.json").read_text())
            if split not in (None, cfg["split"]) or ids not in (None, cfg["episodes"]):
                raise SystemExit("all stages must share split and episodes")
            split, ids = cfg["split"], cfg["episodes"]
            for p in (hub / "stages" / st / "eval").glob("*.jsonl"):
                for r in map(json.loads, p.read_text().splitlines()):
                    if r["qid"] == "_reset":
                        continue
                    key = (r["qid"], r["condition"])
                    if r["condition"] == "W" and key in W_seen and W_seen[key] != r["choice"]:
                        raise SystemExit(f"W not deterministic across stages for {key}")
                    if r["condition"] == "W":
                        W_seen[key] = r["choice"]
                    R[key] = r
        seeds[name] = R
    eps = {e["episode_id"]: e for e in map(json.loads, (hub / "data" / f"{split}.jsonl").read_text().splitlines())}
    world = {e: eps[e]["family"] for e in ids}
    per = {s: {c: {e: metrics(eps[e], R, c) for e in ids} for c in CONDS if all((eps[e]["queries"][0]["qid"], c) in R for e in ids)}
           for s, R in seeds.items()}
    conds = [c for c in CONDS if all(c in per[s] for s in per)]
    keys = list(METRICS) + sorted({k for s in per for c in per[s] for e in per[s][c] for k in per[s][c][e] if k.startswith("flip:")})
    avg = {c: {e: {k: statistics.mean(per[s][c][e][k] for s in per) for k in keys if all(k in per[s][c][e] for s in per)}
               for e in ids} for c in conds}
    report = {"split": split, "episodes": len(ids), "seeds": list(seeds), "unit": "episode (seed-averaged)",
              "conditions": conds, "means": {}, "contrasts": {}, "per_seed": {}}
    for c in conds:
        report["means"][c] = {k: dict(zip(("pooled", "by_world"), world_mean({e: avg[c][e][k] for e in ids if k in avg[c][e]}, world)[:2])) for k in keys}
    for hi, lo in CONTRASTS:
        if hi in conds and lo in conds:
            block = {}
            for k in METRICS:
                d = {e: avg[hi][e][k] - avg[lo][e][k] for e in ids}
                pooled, wm, by = world_mean(d, world)
                block[k] = {"diff": pooled, "ci95": bootstrap(by), "by_world": wm,
                            "episodes_better": sum(v > 0 for v in d.values()), "episodes_worse": sum(v < 0 for v in d.values())}
            report["contrasts"][f"{hi} - {lo}"] = block
    for s in per:
        report["per_seed"][s] = {f"{hi} - {lo}": {k: world_mean({e: per[s][hi][e][k] - per[s][lo][e][k] for e in ids}, world)[0]
                                                  for k in ("complete_pair", "marginal", "correction", "stale")}
                                 for hi, lo in CONTRASTS if hi in conds and lo in conds}
    Path(a.out).write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ("contrasts", "per_seed")}, indent=1))


if __name__ == "__main__":
    sys.exit(main())
