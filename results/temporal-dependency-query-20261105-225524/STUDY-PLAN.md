# Dependency-aware query selection (V1.14.0): frozen plan

- **Brief:** `DEPENDENCY-AWARE-QUERY-SELECTION-BRIEF.md` (copy in `design/BRIEF-copy.md`). Development only. **Zero model calls; CPU only; the GPU stays free.**
- **Freezing.** Before the scored panel, this plan is hashed in `config/FROZEN-PROTOCOL.json` with the source, the committed panels, the validation results and the smoke results. Amendments go to `config/AMENDMENTS.md` and keep the preceding version.
- **Predecessor.** 1.13.0 was committed and pushed as `648aa08`, with erratum E1 (DEFER recovered three, not four, of the newly menu-feasible goals; a06/B declined on its unqueried stock field). E1 is in `Code/ERRATA/1.13.0-query-timing.md` and in the 1.13.0 hub as `ERRATA.md`. Old report text, scores and traces are unchanged.
- **Source.** `Code/DREAM-project-1.14.0-dependency-query-20261105` is 1.13.0 plus:
  - `src/tempo/depquery.py` (DEPQUERY-v1: S2, registry, R, D, the three selectors, the arm runner);
  - `src/tempo/depref.py` (independent selector check);
  - `src/tempo/depgen.py` (new allocation; rows built with the unchanged `freshgen.build`);
  - `scripts/depq_{generate,validate,run,analyze}.py`;
  - `tests/test_depq.py`.

  Every 1.13.0 module is byte-identical (checked at freeze). The two new pool names are added to `freshgen.CONS` at import time; that table is data, and the file is not edited.
- **Tests.** 185/185 temporal tests pass: the 173 from 1.13.0 plus 12 new ones (`test-results/tests-1.14.0.txt`).

## Question
Can a shared temporal dependency model direct spare observations toward the current goal, recover decisions lost to unqueried prerequisites, and earn the extra query fees?

The mechanism is supplied program logic. It is not learned query selection, optimal value of information, or recovery from an extraction error that looks settled.

## Fixed environment and clock (unchanged TIMING-v1 DEFER schedule)
- **Origin and window.** The episode origin is absolute 12 (elapsed 0). Public external activity happens only in 0 < t < 2. A hidden, precommitted tape is independent of policy and requests. The world is declared stable after t = 2, including during plan execution.
- **Selection** happens just before one batch measured at t = 2. Delivery is at t = 4, and the decision and action boundary is also t = 4.
- **Waiting.** Every arm waits 4, including zero-query arms and declines. An empty list creates no request, receipt or fee.
- **Sensor.** Reliable; 1 per fact; at most 2 facts in total. One batch, no second batch, no early exit, no retry, and no free current-state reading.
- **Belief base.** The episode origin. The t = 2 reading filters the propagated joint trajectories at its own time (`freshness.temporal_project`, unchanged).
- **Utility.** `U = 10·success − action_cost − 3·invalid − queried_facts − 1·pre_action_wait`. Waiting cancels in every selector contrast, but extra fees do not.

## Selector inputs (public only) and rule DEPQUERY-v1
- **S2:** `temporal_project` over the public reports and the declared transitions, with base = origin, evidence cutoff = target = t = 2, and an empty sensor ledger.
- **Registry:** the entity fields of the public extraction registry, in key order, each with a finite declared value list. Agent state is declared, not sensed.
- **Q0:** P2's original list, `freshness.p2_request` at t = 0, in frozen order, cap 2. It may be empty.
- **R:** registry fields outside Q0 whose represented values vary across S2. It is computed over the whole context, including other-goal facts. A field absent from some S2 states counts as varying and is flagged; a field absent from all S2 states is flagged and excluded. Validation requires neither flag on the panel.
- **G:** the goal's dependency set, `recovery.context(...)["relevant"]`, which is the planner's own read table over the unchanged menus. No per-case field lists are used.
- **D:** R ∩ G, in registry order.
- **Empty S2:** reported. Q0 is kept and nothing is appended.

The three selectors:

| Selector | Fields measured at t = 2 |
|---|---|
| BASE | exactly Q0 |
| DEPENDENCY | Q0, then the first `e` fields of D up to the cap of 2. No replacement, no fee waiver, no answer-dependent condition. |
| RANDOM_EXTRA | Q0 plus `e` fields uniformly without replacement from R. Every `e`-subset (combinations in registry order) is executed and weighted 1/C(\|R\|, e). If `e` = 0, the BASE outcome is used. A single subset is a reported tie. |

## Panel (committed before any controller output; `phase0/VALIDATION.*`)
The panel has 24 new worlds, 12 per domain, built from new rows (`tempo.depgen.DELIVERY/ASSEMBLY`). The pool is `depq`, the base seed is 20261220, and there are 12 rejected redraws. Each world has goals A and B in stable and changing variants. The smoke panel `depqsmoke` (seed 20261221) has 4 disjoint worlds.

Allocation, computed from public inputs in the changing variant and frozen here:

| Property | Count |
|---|---|
| Competing-addition worlds (some copy has e > 0 and more than one eligible subset) | **20** (delivery 10: d01–d08, d11, d12; assembly 10: a01–a07, a10–a12) |
| Goal copies with e > 0 and >1 subset | 35 (delivery 16, assembly 19) |
| Singleton random pools (ties) | 2 (a09/A, d09/A) |
| Two fields added | 2 (a07/A, a12/B) |
| Full Q0, no spare capacity | 2 (a05/A, a08/B) |
| e = 0 with uncertainty only outside own dependencies | 9 |
| Q0 empty | 30 |
| Stable exact-parity copies (e = 0) | 48/48. No stable copy has an uncovered initial dependency. |

Scorer-side controls, from the hidden truth at the action boundary:
- **Menu gap, full-domain feasible:** 5 (a10/A, d03/A, d04/A, d11/A, d12/A).
- **Full-domain infeasible:** 3 (a04/B, a07/B, a12/B).

Joint-effect redundancy is predeclared for a04/A: Q0's stock reading determines the slot. Uncertainty confined to the other goal is predeclared for d07/A, d08/A, d11/B, d12/B, a08/A and a09/B. d09/B has a plan that is guaranteed despite uncertainty elsewhere.

| Dimension | Values |
|---|---|
| Worlds × goals × environments × selectors | 24 × 2 × 2 × 3 = **288 policy cells** |
| BASE + DEPENDENCY trajectories | **192** |
| RANDOM_EXTRA subset trajectories (computed from public inputs) | **80** (all in the changing variant; e = 0 cells reuse BASE) |
| Total executed trajectories | **272**, each with an independent reference |
| Model calls | **0** |

## Contrasts (fixed now)
- **Primary:** changing; per world, the mean over goals of U(DEPENDENCY) − U(BASE). It includes every extra fee and is not an equal-cost comparison.
- **Selection:** changing; per world, the mean over goals of U(DEPENDENCY) − E_uniform[U(RANDOM_EXTRA)]. It holds query count, fees, timing and budget equal.
- **Secondary (descriptive):** RANDOM_EXTRA − BASE; per goal; per domain; and stable parity controls (expected exactly 0).
- **Averaging.** Subsets are averaged within world, goal and environment with exact weights, then goals within world. **n = 24 worlds.**
- **Interval.** Domain-stratified bootstrap, 10,000 resamples, seed 20261105. Intervals are descriptive.

## Correctness gates (stop and report on any failure; utility is a separate outcome)
- **G1.** Every arm and enumerated subset matches the independent temporal reference (`freshref`) exactly: support, candidate classes and choice.
- **G2.** The actual state stays in support. No unsupported choice, invalid attempt or false completion.
- **G3.** The cheapest guaranteed candidate is chosen whenever one exists. Menu gaps are never labelled infeasible.
- **G4.** The selector obeys DEPQUERY-v1 and matches the independent selector check (`depref`, exhaustive S2 via `freshref.reachable`):
  - Q0 is preserved and the cap is respected;
  - random enumeration and weights are exact;
  - S2 is fully represented and stable copies are not augmented;
  - the field list never depends on the tape;
  - under four alternative tapes, identical readings give identical beliefs and choices.
- **G5.** Shared fixed clock and wait 4; identical actual pre-action state across all arms of a world and environment; equal readings for any common field; history, provenance and log preserved; invariants hold; the cost identity holds.

## Post-hoc diagnostics (never fed back)
DEPENDENCY's added fields are labelled from matched saved outcomes:
- **decision-changing:** the plan differs from BASE;
- **redundant given Q0's readings:** the field is already constant in BASE's post-reading support;
- **unnecessary:** BASE already had a guaranteed plan;
- **insufficient:** the decision is unchanged and DEPENDENCY still declines.

The report also covers:
- added checks on menu gaps and on infeasible goals;
- cases where DEPENDENCY costs more without helping;
- decline reasons: menu gap, full-domain infeasible, or information insufficient (queried or unqueried);
- per-copy query fields, R, D, pool size, S2 uncertainty, post-reading support, choice and utility.

## Interpretation (fixed now)
- **Primary positive, with its interval above 0:** augmentation earned its fees on this designed panel.
- **Selection positive, with its interval above 0:** goal-dependent choice beat uniform uncertain-field additions on this panel.
- **Primary positive but selection inconclusive:** extra sensing helped, but no advantage in field choice is established.
- **Negative or inconclusive:** recorded as is. Nothing is tuned after outputs: not the registry order, the pool, the redundancy handling or the worlds.
- **Scope.** This is a designed mechanism panel. It does not estimate natural frequencies, optimal acquisition, learned querying, robustness to unknown quiet periods, or transfer to new action types.

## Stages and stop
1. Validation (`phase0/`). PASS.
2. Disjoint smoke (`depqsmoke`, stage `smoke`): gates must pass.
3. Freeze.
4. Main (`depq`, stage `main`, `--require-freeze`), then analysis.
5. `REPORT.md`.

**Stop after the report.** Do not launch text extraction, adaptive timing, noisy sensing, menu expansion or a larger model.
