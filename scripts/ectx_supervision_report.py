"""Summarize supervision diagnostics recorded in a stage's train/*.json (V1.6.1).

Answers: is supervision saturated on the answer-choice tokens, or is the full-target loss misleading?
Reports support accuracy and choice-token NLL before/after training in both contexts, first-step and mean
choice NLL during training, gradient norms, and effective weight-change norms.
"""
import argparse
import json
from pathlib import Path
import statistics
import sys


def mean(xs):
    xs = list(xs)
    return statistics.mean(xs) if xs else None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--hub", required=True)
    ap.add_argument("--stage", required=True)
    a = ap.parse_args()
    recs = [json.loads(p.read_text()) for p in sorted((Path(a.hub) / "stages" / a.stage / "train").glob("*.json"))]
    out = {"stage": a.stage, "adapters": len(recs), "training_context": sorted({r.get("context") for r in recs})}
    for when in ("support_before", "support_after"):
        for ctx in ("loo", "rules_only"):
            rows = [r[when][ctx] for r in recs]
            out[f"{when}[{ctx}]"] = {"accuracy": mean(x["accuracy"] for x in rows),
                                     "mean_choice_nll": mean(x["mean_choice_nll"] for x in rows),
                                     "mean_target_nll": mean(x["mean_target_nll"] for x in rows),
                                     "share_choice_nll_over_0.1": mean(e["choice_nll"] > 0.1 for x in rows for e in x["per_example"])}
    steps = [s for r in recs for s in r["steps_log"]]
    out["training"] = {"first_step_full_loss": mean(r["steps_log"][0]["loss"] for r in recs),
                       "first_step_choice_nll": mean(r["steps_log"][0]["choice_nll"] for r in recs),
                       "mean_step_full_loss": mean(s["loss"] for s in steps),
                       "mean_step_choice_nll": mean(s["choice_nll"] for s in steps),
                       "share_steps_choice_nll_over_0.1": mean(s["choice_nll"] > 0.1 for s in steps),
                       "mean_grad_norm": mean(s["grad_norm"] for s in steps),
                       "max_grad_norm": max(s["grad_norm"] for s in steps),
                       "mean_delta_norm_total": mean(r["delta_norm_total"] for r in recs),
                       "mean_delta_norm_max_module": mean(r["delta_norm_max"] for r in recs)}
    path = Path(a.hub) / "stages" / a.stage / "SUPERVISION.json"
    path.write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    sys.exit(main())
