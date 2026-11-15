# Dependency-aware query selection (V1.14.0): report

- **Date:** 2026-11-05. CPU only. **Zero model calls.**
- **Brief:** `design/BRIEF-copy.md`. **Plan:** `design/STUDY-PLAN.md`, frozen in `config/FROZEN-PROTOCOL.json`; no amendments.
- **Source:** `Code/DREAM-project-1.14.0-dependency-query-20261105`. Source sha256 is `62333ae1…f69a`. All 154 inherited 1.13.0 source, script and test files are byte-identical.
- **Tests:** 185/185 temporal tests pass (173 inherited + 12 new).
- **Predecessor:** 1.13.0 was committed and pushed as `648aa08` with erratum E1. DEFER recovered three, not four, of the newly menu-feasible goals; a06/B declined on its unqueried stock field. Scores are unchanged.
- **Runtime and size:** main 5.2 s wall. 272 executed trajectories (BASE 96, DEPENDENCY 96, RANDOM_EXTRA subsets 80), each with an independent reference. 288 policy cells. 704 leakage re-runs (four alternative tapes per field list). Maximum support size 8 (S2 and post-reading).

## Correctness gates: all pass

| Gate | Result |
|---|---|
| G1 support, candidate classes and choice exactly equal the independent temporal reference, for every arm and every random subset | 0 / 272 failures |
| G2 actual state in support; no unsupported choice, invalid attempt or false completion | 0 / 272 |
| G3 cheapest guaranteed candidate whenever one exists; menu gaps never labelled infeasible | 0 / 272 |
| G4 frozen selector rule (matches the exhaustive independent selector check); Q0 preserved; cap 2; exact enumeration and weights; S2 fully represented; no stable augmentation; field lists independent of the tape; identical readings give identical beliefs and choices | 0 / 96 |
| G5 shared clock (measure t = 2, act t = 4, wait 4); identical pre-action state across arms; equal common-field readings; history and provenance preserved; invariants; cost identity | 0 / 272 |

Pre-run validation (`phase0/VALIDATION.md`) also passed:
- BASE, run through the new code path, reproduces all 96 stored 1.13.0 DEFER trajectories: fields, readings, support, plan, success and utility.
- That includes the eight residual declines.
- On that old panel, the regression fixture a06/B shows that DEPENDENCY adds the unqueried stock field `Nedudefe.on_hand`.
- The 1.13.0 panel has no zero-query copies, so the zero-query path is covered by fixtures (`test_12`).

## Results (changing environment, λ = 1, n = 24 worlds; descriptive domain-stratified bootstrap)

| Contrast | Mean | 95% interval | worlds better / equal / worse |
|---|---|---|---|
| **PRIMARY: DEPENDENCY − BASE** (extra fees charged) | **+2.46** | **[+1.58, +3.35]** | 19 / 2 / 3 |
| **SELECTION: DEPENDENCY − RANDOM_EXTRA** (equal count, fees and timing) | **+1.65** | **[+1.13, +2.15]** | 17 / 7 / 0 |
| RANDOM_EXTRA − BASE | +0.81 | [+0.37, +1.25] | 15 / 2 / 7 |
| DEPENDENCY − BASE, goal A / goal B | +1.88 / +3.04 | [+0.75, +3.08] / [+1.67, +4.38] | 12/5/7 · 14/6/4 |
| DEPENDENCY − RANDOM_EXTRA, goal A / goal B | +1.33 / +1.97 | [+0.67, +2.04] / [+1.21, +2.69] | 10/14/0 · 14/10/0 |
| DEPENDENCY − BASE, delivery / assembly | +1.88 / +3.04 | [+0.79, +3.08] / [+1.75, +4.33] | 9/1/2 · 10/1/1 |
| DEPENDENCY − RANDOM_EXTRA, delivery / assembly | +1.23 / +2.07 | [+0.60, +1.92] / [+1.28, +2.81] | 8/4/0 · 9/3/0 |
| Control: stable DEPENDENCY − BASE; stable RANDOM_EXTRA − BASE | 0 exactly | — | 0 / 24 / 0 |

(The primary mean, +2.4583, happens to equal 1.13.0's DEFER − EARLY_WAIT mechanism contrast. It is a different contrast on a different panel; the match is a coincidence.)

**Read under the frozen rules:**
- **Primary: positive, interval above 0.** On this designed panel, the augmentation earned its extra fees.
- **Selection: positive, interval above 0.** At matched query count and fees, the goal-dependent choice beat a uniform choice among uncertain, sensor-accessible fields. No world was worse than the random average.

**Totals over 48 goal copies:**

| Arm | Successes | Declines | Fees | U |
|---|---|---|---|---|
| BASE | 13 | 35 | 20 | −125 |
| DEPENDENCY | 40 | 8 | 59 | −7 |
| RANDOM_EXTRA (expected) | 26.7 | 21.3 | 59 | −86.2 |

All arms wait 4 per copy (192 in total). DEPENDENCY reaches every menu-feasible goal: 40/40 menu-feasible at action, 45 full-domain feasible. It still has 0 invalid attempts and 0 false completions. The stable variant is identical across arms (no augmentation in 48/48 copies).

## What the added measurements did (37 changing copies with e > 0; labels post hoc)
- **Decision-changing: 27.** In every one, BASE declined because a goal prerequisite was uncertain and unqueried, and DEPENDENCY then executed or completed. In 21 of the 27, Q0 was empty. The 27 also include both singleton ties (a09/A, d09/A).
- **Insufficient: 8.** One extra fee each, with no possible gain.
  - **Menu gaps:** a10/A, d03/A, d04/A, d11/A, d12/A. These goals are full-domain feasible, but the supplied menu has no valid plan.
  - **Full-domain infeasible:** a04/B, a07/B, a12/B. a12/B paid for two additions.
- **Redundant given Q0's readings: 1 (a04/A).** The late stock reading already fixed the slot through the joint return-to-stock transition. The slot check was still bought: U fell from 3 to 2.
- **Unnecessary: 1 (a06/A).** BASE's reading of the provisional slot already guaranteed `already`.
- **Lower utility than BASE: 11.**
  - In 10 of them, DEPENDENCY gained nothing: the eight insufficient cases plus a04/A and a06/A.
  - In the eleventh, **d06/B**, DEPENDENCY **succeeded** (b_cheap). The route cost 10, so the success did not pay for itself: U −5 against −4 for declining.
  - The analysis table labels all 11 "costs more without helping", which is accurate for 10. d06/B is a success that paid less than its cost.
- **Not augmented despite uncertainty elsewhere: 11.** Two had a full Q0 (a05/A, a08/B). Nine had uncertainty only outside their own dependency set (the other goal's crate or slot, or crate Z). This is the intended exclusion of other-goal uncertainty from D. Those fields remained in the random pool of the other goal copy.

## Interpretation and limits
- **What the result shows.** When a declared change can make a formerly verified prerequisite stale, P2's evidence-status rule misses it, and on this panel it does so most of the time (Q0 was empty in 30/48 changing copies). The goal's own dependency table is enough to aim the spare query.
- **Why random is a weak competitor here.** Most pools have two fields, one of them goal-relevant, so the random arm hits the right field about half the time. It also loses when its pick is the other goal's fact. The selection advantage is therefore expected to shrink as the pool fills with relevant fields, and to grow with more distractors. **This panel's pool sizes were designed (2 or 3) and do not measure that relationship.**
- **Cost.** The rule makes no attempt to avoid a field Q0 already determines, a goal with no menu plan, or a plan already guaranteed. That cost is visible (10 copies, about 1 fee each) and stays in the primary contrast as frozen.
- **What the result does not show.** The panel is a designed mechanism panel, and the allocation deliberately favours competing prerequisites, so it estimates nothing about natural frequencies. It does not establish:
  - optimal acquisition or learned querying;
  - robustness to unknown quiet periods or noisy sensing;
  - transfer to new action types;
  - recovery from an extraction error that looks settled.

  The menu-coverage gaps and the infeasible goals remain. Better observation cannot fix them under the unchanged planner.
- **For the frozen-text integration.** DEPENDENCY (Q0 + D, cap 2) is the selector these results support carrying into the next test. Its known overchecking cases should be listed explicitly.

## Files
- `stages/main/`:
  - `selections.jsonl` (selector traces, written before any sensor answer);
  - `selcheck.jsonl` (independent selector check);
  - `trajectories.jsonl` (every arm and subset, with exact weights);
  - `reference.jsonl`;
  - `feasibility.jsonl`;
  - `leakage.jsonl`;
  - `RUN-META.json`.
- `analysis/main/ANALYSIS.json`, which includes per-copy query fields, R, D, pool, S2 uncertainty, post-reading support, choice, decline reason, feasibility, costs and utility; and `TABLES.md`.
- `phase0/` (validation), `stages/smoke/` and `analysis/smoke/` (disjoint smoke, all gates pass), `config/FROZEN-PROTOCOL.json`, and `run_stage.sh SET STAGE`.

**Stopped after this report.** No text extraction, adaptive timing, noisy sensing, menu expansion or larger model was launched. The 1.14.0 source is not committed to Git.
