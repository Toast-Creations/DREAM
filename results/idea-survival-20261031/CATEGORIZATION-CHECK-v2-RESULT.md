# Stage A categorization check v2: result (2026-11-02)

- **Criteria:** `CATEGORIZATION-CHECK-CRITERIA-v2.md` (sha256 63f77ff6…), fixed before running.
- **Hub:** `gpu/qwen3-categorization-check-v2-20261102-152031`.
- **Source:** 1.5.5; the sandbox ran 160/160 tests.
- **Calibration:** `CALIBRATION-FROZEN.json` (sha256 f07a390a…), frozen before the test launch.
- **Report:** `output/CATEGORIZATION-CHECK-v2-REPORT.json` in the hub.
- **Scope:** 34,224 records; scored once with the frozen scorer; no judge calls.

## Decision: no demonstrated change in categorization under these conditions. The steering branch is closed.

**Validity checks:**
- **Instrument check:** passed on both sets. Baseline log-odds order typical > peripheral > remote > foil; on C: +16.6 > +2.0 > −20.2 > −32.8.
- **Positive control:** P2 passed (detection criteria a and b). The null is therefore interpretable, not inconclusive.

## Calibration (frozen before C and D)
- **Temperature:** T = 1.5 was chosen at the **top of the grid**. The target's semantic shift on the calibration objects (0.117) exceeded every temperature tested (0.6–1.5: 0.039–0.078), so the temperature arm under-matches the steering's disruption.
- **Association measure:** it qualified. Unrelated lists showed dispersion 0.974 vs baseline 0.807, and relevance 0.064 vs 0.390.
- **Frozen thresholds:** dispersion gain ≥ 0.033; relevance drop ≤ 0.081.

## Results (target = D1, block −12, λ 0.2, steer-then-release; n = 24 objects per set; 95% bootstrap CIs)

**M1, membership during the intervention** (peripheral and remote, log-odds vs baseline)

| | target | best random | target − random mean |
|---|---|---|---|
| C | **−0.55** [−0.81, −0.31] | +1.51 | **−0.74** [−1.00, −0.48] |
| D | **−0.65** [−0.96, −0.35] | +1.45 | **−0.84** [−1.15, −0.53] |

- The target made the model **less** willing to accept peripheral and remote categories than both baseline and random directions, on both sets.
- It also lowered typical acceptance (−2.9 and −3.0) and slightly raised foils (+0.57 on both sets).
- So it fails health and has no selective effect. The pattern reads as a general shift away from confident judgments that leans toward "No", not as loosening.
- The shift is negative in all three formulations.

**M2, membership after release** (the arm's own association list re-read unsteered)

| | target | best random | target − random mean |
|---|---|---|---|
| C | −0.86 [−2.10, +0.22] | +0.81 | −0.91 [−2.05, +0.15] |
| D | **−2.28** [−3.22, −1.38] | +0.42 | **−2.20** [−3.10, −1.38] |

- After release the direction is the same, so whatever carries over in the steered association text pushes *toward* tighter categories, not looser.
- The temperature arm was close to zero on both sets (−0.13 and −0.51).

**M3, association dispersion** (relevance-safeguarded)

| | target | best random | target − random mean | relevance change |
|---|---|---|---|---|
| C | +0.0086 | +0.0068 | +0.0107 [+0.000, +0.022] | −0.023 |
| D | +0.0047 | +0.0005 | +0.0089 [−0.004, +0.022] | −0.039 |

- The target edged above all nine random directions on both sets, but the gain is a quarter of the declared minimum (0.033). The CI upper bounds (0.022) sit below that minimum.
- Target vs temperature: +0.009 [−0.001, +0.019] on C and +0.007 [−0.007, +0.021] on D, which is not distinguishable.

**What this rules out** (CI upper bounds below the declared sizes, both sets):
- loosening of ≥ 0.5 log-odds, during the intervention or after release;
- a dispersion gain of ≥ 0.033.

**Example association lists (set C):**
- Lunchbox:
  - baseline: "lunchbox, meal, food, lunch, container, snack, portable, packed…"
  - target: "lunchbox, meal, food, snack, container, lunch, break, school, portable, packed"
  - P2: "portability, nostalgia, compartmentalization, sustenance, insulation, convenience, childhood…"
- Sieve:
  - baseline: "sieve, mesh, bowl, strain, liquid, powder, sift, food, kitchen, filter"
  - target: "straining, sifting, mesh, bowl, liquid, powder, holes, filtering, grain, basket"
  - P2: "filter, weave, residue, mesh, strainer, texture, flow, capture, release, boundary"

## The positive control is informative in its own right: P2's effect is not selective

| P2 | peripheral/remote | typical | foil |
|---|---|---|---|
| C, during | +7.4 | −12.6 | **+11.6** |
| D, during | +6.1 | −13.4 | **+11.8** |
| C, after release | +3.7 | −4.4 | +0.8 |
| D, after release | +2.1 | −5.0 | +0.7 |

- **During:** P2 raised acceptance of clearly false categories more than acceptance of remote ones, and sharply reduced confidence in typical ones. This is an across-the-board flattening of category judgments (log-odds pulled toward zero), not selective loosening. It would fail the health limits that applied to the target.
- **Associations:** P2's dispersion gain (+0.05) came with a relevance drop of 0.16–0.18, about twice the safeguard limit.
- **Implication:** P2 detects as a change, but by the review's standard ("more acceptance of defensible remote categories without more acceptance of false ones") it is not decategorization either. A future prompting study would first need a manipulation that passes these health limits.

## Interpretation
- **Steering:** in Qwen3-8B, the targeted direction under steer-then-release did not loosen categories, during or after release, and did not broaden associations by a meaningful amount, compared with matched random perturbations. Its measurable effect on membership runs the other way.
- **Programme:** with the earlier screens (reading-only, dose extension, write-time), the steering branch is closed, as declared.
- **Limits:** this does not show that decategorization cannot be induced in language models. It covers these directions, this model, λ 0.2, block −12, and this schedule.
- **Prompting:** the prompting result is reclassified. P2 produces a strong, replicated *framing and style* shift, but on these measures it is indiscriminate category acceptance rather than selective loosening.

## Correction (2026-11-02, after a cross-check by the GPT preparation audit; verified against the report JSON)

- **During the intervention (M1), not every random direction scored higher than the target.**
  - On set C, R1 (−0.73) and R4 (−0.97) were below the target (−0.55).
  - On set D, R4 (−0.66) was below the target (−0.65).
  - The target is below the **mean** of the nine random directions (CIs above), not below each one. Statements above that the target was less willing "than … random directions" and that "the target made the model less willing … than both baseline and random directions" should be read as "than the random-direction mean".
- **After release (M2), the target was below all nine random directions on both sets.**
- **M3 sample sizes and intervals:**
  - the common-valid association gate used n = 24 on C and n = 23 on D (P2: 24 and 22);
  - the target-vs-baseline dispersion CI upper bounds were +0.0193 (C) and +0.0184 (D), against the +0.0334 minimum.
- **Unchanged:** the decision and the pass/fail of every gate.
