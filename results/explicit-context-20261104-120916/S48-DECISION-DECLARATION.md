# 48-step comparison: declaration (written before any 48-step stage exists; 2026-11-04)

David's instruction: one stronger-training comparison, 48 steps = four passes over the 12 examples, current lr (1e-4).
Same three seeds (2000, 3000, 4000), four conditions (W, W+A, W+X, W+Y), packets (dev_all_s12), episodes, W+X donors
(cyclic same-world) and W+Y donors (as in DONOR-AND-SEED-DECLARATION.md). All other settings fixed (S1, LoRA rank 8
alpha 16 q/k/v/o, n_aug 1, context loo, schedule each_source_once, weight decay 0, tolerance 0.0). Run source: Code 1.6.4
(run code identical to 1.6.3). Stages: s48-seed2000, s48-seed3000, s48-seed4000. Sealed replacement stays waiting.
This is a bounded test of "one pass was insufficient"; no further settings will be tried on this recipe after it.

## Measures (recorded)
Support learning: training-context (loo) support accuracy after training, mean over the 36 adapters, per seed and per
support type; choice-token NLL. Held-out: complete-pair (primary), marginal, corrections, stale, per world and per flip
type, analysed with ectx_seed_analysis.py (12 episodes as units, seeds averaged within episode, world-stratified
bootstrap, 10k). Cost: training seconds, training tokens, peak memory, eval seconds.

## Operational definitions (fixed now)
- Support learning is BETTER (not weak) if seed-averaged after-training support accuracy is >= 0.80, and it exceeds
  the matched 12-step stage by >= 0.10 in every seed (12-step values: 0.632, 0.632, 0.597).
- Held-out benefit: W+A − W complete-pair seed-averaged difference with 95% CI lower bound > 0.
- Own-adapter advantage: held-out benefit AND W+A − W+X complete-pair difference with 95% CI lower bound > 0 AND
  W+A − W+X > 0 in at least 2 of 3 seeds.
- Corrections worsen: W+A − W correction difference < 0, or W+A correction accuracy at 48 steps below the 12-step
  seed-averaged W+A value (0.444) by more than 0.05.

## Decision (applied in this order)
1. Support learning not better -> "Support learning remains weak": record the limitation of this training procedure
   and budget.
2. Corrections worsen -> stop this recipe.
3. Own-adapter advantage -> check the candidate on the remaining development episodes before freezing.
4. Held-out benefit without own-adapter advantage -> benefits remain shared with same-world adapters: end tuning aimed
   at episode specificity for this recipe; consider a reusable world adapter as a separate hypothesis.
5. Otherwise (no held-out benefit) -> stop this recipe.
Mechanism language beyond this table is not assigned from these results; all results are development observations.
