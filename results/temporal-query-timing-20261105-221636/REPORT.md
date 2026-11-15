# Query timing and the cost of waiting (V1.13.0): report (development only)

## Status
- **Brief and plan.** Brief: `design/BRIEF-copy.md`. Plan: `design/STUDY-PLAN.md`, frozen in `config/FROZEN-PROTOCOL.json` (source `ba949b68…`) together with the panel, the validation and the smoke results, before the scored run. There were no amendments.
- **Predecessor.** 1.12.0 was committed and pushed as `f29a3c8`, with erratum E1 recorded both in `ERRATA/1.12.0-observation-freshness.md` and in the 1.12.0 hub. The erratum separates candidate-plan gains (13) and losses (12) from feasibility changes (4 goals became newly menu-feasible, 3 became menu-infeasible). Old scores are unchanged.
- **Unchanged modules.** Every 1.12.0 module is byte-identical. Tests: 173/173.
- **Pre-run validation** (`phase0/`): 0 failures.
  - Compatibility: re-running the 1.12.0 scored panel reproduces 384/384 stored trajectories.
  - TIMING EARLY on the 1.12.0 panel equals 1.12.0's temporal projection at delay 2 in 96/96 cases.
  - The actual pre-action state is identical across schedules in every world.
- **Ran 2026-11-05.**
  - Smoke: 48 trajectories on 4 disjoint worlds; all gates pass; not pooled.
  - Main: **288 trajectories**, 4.8 s wall time including the reference and leakage runs.
  - Zero model calls; the GPU was not touched; offline; sleep blocked.
  - Maximum reachable set: 8 states. Maximum projection CPU: 0.3 ms.
- **Sample.** 24 new worlds × goals A/B × stable/changing × EARLY, EARLY_WAIT, DEFER. The temporal projection uses structured input. The unit of inference is the **24 worlds**.

## Correctness gates: all pass, every schedule

| Gate | EARLY | EARLY_WAIT | DEFER |
|---|---|---|---|
| G1: exact reachable states, classes and choice match the independent reference | 0/96 | 0/96 | 0/96 |
| G2: actual state in support; no unsupported choice, invalid attempt or false completion | 0/96 | 0/96 | 0/96 |
| G3: reference choice taken whenever one exists | 0/64 | 0/64 | 0/82 |

**G4 also passes (0 failures).** It covers:
- fixed clocks, with the base at the episode origin, and identical pre-action states;
- the cloned request and a delivery delay of 2;
- preserved history and log;
- no receipt appearing before it is received;
- admissible states and no refusals;
- the controls, all exact: stable states and choice are equal across schedules; changing EARLY = EARLY_WAIT; the cost identities hold at every λ;
- leakage: across four alternative tapes, identical receipts always gave identical beliefs and choices.

There were **no false completions**. 11 empty "already" plans were selected under DEFER (changing), and every one was true at its boundary.

## Results (changing environment; λ = 1 unless stated)

| Schedule | U₀ | U₁ | Success | Invalid | Declines (all justified) | Missed menu-feasible | Mean states | Uncertain queried / unqueried |
|---|---|---|---|---|---|---|---|---|
| EARLY | 93 | −3 | 22 | 0 | 26 | 21 | 2.48 | 21 / 6 |
| EARLY_WAIT | 93 | −99 | 22 | 0 | 26 | 21 | 2.48 | 21 / 6 |
| DEFER | **211** | 19 | **40** | 0 | **8** | **3** | 1.88 | **0** / 5 |
| Stable (all schedules) | 217 | 121 / 25 / 25 | 42 | 0 | 6 | 0 | 1.17 | 0 / 0 |

| Contrast (per world, goals averaged, n = 24; descriptive) | Mean [95%] | Better / equal / worse |
|---|---|---|
| **PRIMARY: DEFER − EARLY, λ = 1** | **+0.46 [−0.42, +1.40]** | **12 / 1 / 11** |
| **MECHANISM: DEFER − EARLY_WAIT, λ = 1** (equal fees and waiting) | **+2.46 [+1.58, +3.40]** | **15 / 9 / 0** |
| Goal A, DEFER − EARLY | +0.75 [−0.71, +2.38] | 9 / 0 / 15 |
| Goal B, DEFER − EARLY | +0.17 [−1.17, +1.71] | 6 / 1 / 17 |
| Control: changing EARLY_WAIT − EARLY | −2.00 exactly | 0 / 0 / 24 |
| Control: stable DEFER − EARLY_WAIT | 0.00 exactly | 0 / 24 / 0 |
| Control: stable DEFER − EARLY | −2.00 exactly | 0 / 0 / 24 |

**Primary result: inconclusive.** At the declared waiting price λ = 1, DEFER − EARLY is +0.46 with an interval that includes 0, and the worlds split 12 / 1 / 11.

**Mechanism: clearly positive.** At equal elapsed time and equal fees, measuring after the activity window beat measuring at its start.
- DEFER succeeded in 18 goal copies where EARLY_WAIT did not. That includes all 7 possible-but-unrealized changes, which earlier sensing could never rule out, and all 4 genuinely newly feasible goals (d05/A, d07/B, d12/B, a06/B kind).
- **No goal copy had an earlier measurement that was more useful**, and DEFER's support was never larger than EARLY_WAIT's. On this allocation, every reading taken after the window is at least as informative for the plan as one taken at its start. That held here; it was not required by the design.

**Waiting-price sensitivity** (computed analytically on the same trajectories):

| λ | DEFER − EARLY |
|---|---|
| 0 | +2.46 [+1.58, +3.40] (15 / 9 / 0) |
| 0.25 | +1.96 [+1.08, +2.90] (15 / 0 / 9) |
| 0.5 | +1.46 [+0.58, +2.40] (14 / 1 / 9) |
| **1 (primary)** | **+0.46 [−0.42, +1.40] (12 / 1 / 11)** |
| 2 | −1.54 [−2.42, −0.60] (6 / 4 / 14) |

**Break-even.** ΔU_λ = ΔU₀ − 2λ, so the panel break-even price is **λ\* = ΔU₀/2 = 2.46/2 = 1.23**.
- Per world, λ\* ranges from 0.5 to 3.75.
- In 9 worlds ΔU₀ = 0 (λ\* is "a tie only at 0"). Deferral buys nothing there: the change was irrelevant, a guard was false, an unqueried prerequisite stayed unresolved, or the menu had no candidate.
- This break-even holds only for this designed allocation and must not be read as a real-world rate.

## Residual DEFER declines (8, all justified by the reference)
- **4 caused by an unqueried, independently changing prerequisite** (a03/A, a04/A, a12/A: the verified slot T; a06/B: the unqueried stock of D). The late reading of P2's original field cannot resolve these. As planned, query selection was not changed.
- **4 with no valid menu candidate in the support** (a03/B, d01/A, d06/A, d08/B). In d01/A, d06/A and d08/B a valid plan exists outside the menu (full-domain feasible), as it does in a12/A. These are coverage gaps, not infeasibility.
- **Resolved indirectly** (a10/A): reading G's stock at t = 2 showed it on hand. Through the joint return-to-stock transition, this proves that slot T is empty, a fact P2 never queried. DEFER then installed G successfully.

## Feasibility versus candidate changes (corrected scorer, per erratum E1)
- 13 goal copies gained a valid candidate relative to t = 0, and 12 lost one.
- Only **4 became newly menu-feasible** (a06/B, d05/A, d07/B, d12/B). DEFER completed all 4; EARLY and EARLY_WAIT completed none.
- **3 became menu-infeasible** (a12/A, d01/A, d08/B). All three are still full-domain feasible.
- Menu-feasible at action time: 43/48 changing, 42/48 stable. Full-domain feasible: 47/48 changing, 46/48 stable.

## What this shows and does not show
**Shown, under the stated assumptions** (reliable sensor; known activity window (0, 2) followed by a declared quiet period; one batch of P2's original fields; structured, meaning-correct evidence):
- The fixed-clock temporal projection is correct for all three schedules, judged against an independent reference.
- Sampling after the activity window recovers most decisions that the start-of-window sample has to decline (mechanism +2.46, 15/9/0), with no invalid attempts and no false completions.
- Whether that benefit pays for two more units of waiting depends on the price. Under this allocation it does below λ ≈ 1.23, it does not at λ = 2, and at the declared λ = 1 the result is inconclusive.

**Not shown:**
- an optimal or adaptive query policy;
- the value of waiting when the quiet period is unknown;
- calibrated risk or probabilities;
- noisy sensors, text input, or larger or concurrent dynamics;
- resolution of prerequisites that P2 never queried (except through a declared joint transition).

## Limits
- **Designed allocation:** 24 worlds; 16 realize a change and 8 do not. The same 24 kinds of change as 1.12.0 are used, so magnitudes depend on the allocation.
- **Known quiet period:** the window is known and the world is stable afterwards. That is exactly why a late measurement can be decisive, and it is the main assumption.
- **Scope:** temporal projection only. Carry-forward was not part of this comparison.
- **Development disclosure:** the pipeline was debugged on pool `timingsmoke` with base seed 999, and that run was discarded. The main seed was first run after the freeze.

## Next choices (none started)
- An adaptive policy that chooses whether and when to measure, against these fixed schedules, at declared prices.
- Query selection that includes prerequisites a declared change can affect (the 4 unqueried-prerequisite declines).
- An unknown or partially known quiet period.
- Adding the frozen text interface.

## Artifacts
- **Traces and checks:** `stages/main/{trajectories, reference, requests, leakage, feasibility}.jsonl`, plus `RUN-META.json`.
- **Analysis:** `analysis/main/{ANALYSIS.json, TABLES.md}`. TABLES.md includes all 18 schedule disagreements with their timelines.
- **Inputs:**
  - `data/public/` (controller inputs)
  - `data/hidden/` (truth, tape, labels)
  - `data/COMMITMENT-*.json`
- **Validation:** `phase0/VALIDATION.{json,md}`; smoke validation in `phase0/smoke/`.
- **Freeze:** `config/FROZEN-PROTOCOL.json`.
- **Re-run:** `run_stage.sh timing main --require-freeze`.
