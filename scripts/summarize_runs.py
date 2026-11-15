"""Exploratory paired summaries with world-cluster bootstrap uncertainty."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import random
from _bootstrap import ROOT
from dream_core.ledger import atomic_json


def paired_world_summary(trials, repetitions=2000, seed=2026):
    grouped=defaultdict(dict)
    for row in trials:
        if row.get("status")!="completed" or "metrics" not in row: continue
        key=(row["world_id"],row["seed"],row["eta"])
        grouped[key][(row["condition"],row["lambda"])]=row["metrics"]["accuracy"]["composition"]
    contrasts=defaultdict(lambda:defaultdict(list))
    for (world,trial_seed,eta),cells in grouped.items():
        baseline=cells.get(("plasticity_only",0.0))
        if baseline is None: continue
        for (condition,lam),value in cells.items():
            if condition=="coupled" and value is not None:
                contrasts[(lam,eta)][world].append(value-baseline)
    rng=random.Random(seed); output=[]
    for (lam,eta),worlds in sorted(contrasts.items()):
        values=[sum(v)/len(v) for v in worlds.values()]
        distribution=sorted(sum(rng.choices(values,k=len(values)))/len(values) for _ in range(repetitions))
        # No confidence interval claim for fewer than two independent worlds.
        interval=None if len(values)<2 else [distribution[int(.025*(repetitions-1))],distribution[int(.975*(repetitions-1))]]
        output.append({"lambda":lam,"eta":eta,"worlds":len(values),"mean_paired_composition_gain":sum(values)/len(values),
                       "exploratory_world_bootstrap_95_interval":interval,"multiple_comparison_adjusted":False})
    return output


def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument("run_directory")
    args=parser.parse_args(); root=Path(args.run_directory).resolve()
    trials=[json.loads(p.read_text(encoding="utf-8")) for p in sorted(root.glob("trial-*.json"))]
    output=root/"exploratory-summary.json"
    if output.exists(): raise FileExistsError("Preserve existing summaries; choose a copied analysis directory")
    atomic_json(output,{"status":"exploratory only; no confirmatory significance claim", "trials":len(trials),
        "contrasts":paired_world_summary(trials),"note":"Seeds are averaged within each world before resampling worlds. No best-dose selection on final-test results."})
    print(output)


if __name__=="__main__": main()
