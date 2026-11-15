# Notes: V1.15.0 frozen-text integration and V1.15.1 overnight replication (append-only)

## Qualified claim (both studies)
The DEPENDENCY − BASE utility benefit survived the frozen Qwen3-8B text interface:
- short panel: +2.19 [+1.15, +3.27];
- overnight 768 worlds: +1.95 [+1.87, +2.04], case-stratified and conditional on the 24 designed families.

This is a **qualified cost result**, not evidence of reliable operation. The interface shrank the benefit by
−0.55 [−0.63, −0.48], almost all in assembly (−1.08).

## Unsafe text cases (overnight; none on the structured channel)
5 of 1,536 text goal copies acted unsafely (3 invalid actual attempts, 2 false completions). Each repeats across
environments and selectors, and each is a wrong-field attribution that looks settled:
- b001 a06/A, b015 a06/A, b021 a04/B: "part X was taken by another team" was extracted as a verified correction that
  emptied a slot or another part's stock. The plan was an invalid `install`.
- b018 a08/A: "part X was delivered to you" was extracted as an event installing X into the goal slot. The plan was
  a false `already`.
- b021 d05/A (stable): a crate move was attributed to the wrong crate. The plan was a false `already`.

In all five, the parsed support was fully represented and excluded the actual state, so neither selector queried
the field. BASE and DEPENDENCY were affected identically.

## Interpretation bottleneck
Overnight exact meaning: stock arrivals 27/202, stock removals 74/118; every other class 97–99%.

## Provenance
- 1.15.0 hub: Runs/temporal-frozen-text-integration-20261105-231937.
- 1.15.1 queue: Runs/temporal-text-replication-20261105-233535.
- The 1.15.1 queue seeds and design were used exactly as handed over. The short-study outcomes had been inspected
  before the queue was prepared, and nothing was changed in response.

## N2 (2026-11-06): reporting precision
- The unsafe cases are 5 distinct (block, world, goal) copies. They repeat across selectors and environments into
  18 unsafe executions: 12 invalid attempts and 6 false completions. Stable text cells each hold 3 invalid and
  2 false; changing cells hold 3 and 1. These clones are not independent incidents, and 5/1,536 is not a
  deployment risk estimate.
- The invalid installs differ in cause. In b001 a06/A and b015 a06/A the target slot was occupied. In b021 a04/B
  the slot was empty and the part was not on hand, so the install failed on stock. (Verified from
  trajectories.jsonl, actual_relevant_at_execute.)
- The morning report says the bottleneck "is not observation coverage, evidence representation or the cost
  policy". That is too strong. The run identifies the principal *measured* language failure, and the known limits
  of the other components remain.
- Stock events account for 219 of the 300 inexact records (arrival 175 + removal 44).
Counts and conclusions are otherwise unchanged.
