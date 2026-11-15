# Direction screen result (2026-11-02): no candidate passed

**Criteria:** `DIRECTION-SCREEN-CRITERIA.md`, fixed before running.
**Hub:** `gpu/qwen3-direction-screen-20261102-103314`; report: `output/DIRECTION-SCREEN-REPORT.json`.
**Scale:** 3,504 greedy probes plus 144 build generations. All probes were valid (100% healthy).

**Pre-declared outcome:** no candidate (D0, D1 or D2, at blocks −12, −8 and −4, at λ 0.10 and 0.20) beat all nine random directions on both category loosening and abstractness. As declared, there is no re-screen with new metrics or thresholds.

## Descriptive context (not part of the pass rule)

**1. Reading-only steering at λ ≤ 0.20 mostly does nothing.** For every direction, random included, 65–94% of greedy outputs were word-for-word identical to the unsteered output:

| Block | λ | Targeted directions, unchanged | Random directions, unchanged |
|---|---|---|---|
| −12 | 0.10 / 0.20 | 75–77% / 65–71% | 77% / 66% |
| −8 | 0.10 / 0.20 | 81–85% / 81–85% | 86% / 81% |
| −4 | 0.10 / 0.20 | 88–94% / 77–85% | 87% / 78% |

**2. Abstractness barely moved.** Shifts were at most 0.016 on a 1–5 concreteness scale for every cell.

**3. Category loosening: the new candidates rank higher than D0 among the random directions, but not decisively.**

| Block, λ | Random range | D0 | D1 | D2 |
|---|---|---|---|---|
| −12, 0.10 | 0.103–0.173 | 0.134 (beats 2/9) | **0.180 (9/9)** | 0.145 (3/9) |
| −8, 0.10 | 0.048–0.165 | 0.093 (3/9) | 0.141 (8/9) | 0.155 (8/9) |
| −8, 0.20 | 0.069–0.170 | 0.065 (0/9) | 0.152 (7/9) | 0.155 (7/9) |

The original method (D0) is never better than the median random direction. D1 (built from the model's own generated answers) and D2 (abstract vs concrete) usually rank near the top of the random null on category change, but not on abstractness.

**4. Rebuild check:** D0 at block −8 equals the pilot vector (cosine 1.00). D1 and D2 are distinct from D0 (cosine with D0 at −8: 0.40 and 0.23).

## Interpretation
At the strengths used in the continuity pilot, perceive-mode steering of a short span is weak: most outputs are untouched, whatever the direction. The screen therefore cannot validate any direction at these doses. This also qualifies the pilot itself. With sampling, any small perturbation reroutes the sampled text, so arm differences there may largely reflect different draws rather than decategorization.

Whether stronger doses produce a direction-specific effect is a separate question, and needs a separately declared dose extension (David's decision).
