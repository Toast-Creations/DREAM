# Query timing and the cost of waiting (V1.13.0): frozen plan

- **Brief:** `QUERY-TIMING-AND-WAITING-COST-BRIEF.md` (copy in `design/BRIEF-copy.md`). Development only. **Zero model calls; the GPU stays free.**
- **Freezing.** Before the scored panel, this plan is hashed in `config/FROZEN-PROTOCOL.json` with the source, the committed panel, the validation results and the smoke results. Amendments go to `config/AMENDMENTS.md` and keep the preceding version.
- **Predecessor.** 1.12.0 was pushed as `f29a3c8`, with erratum E1 (candidate-plan changes are not the same as feasibility changes) in `ERRATA/1.12.0-observation-freshness.md` and its hub. Old scores are unchanged.
- **Source.** `Code/DREAM-project-1.13.0-query-timing-20261105` is 1.12.0 plus:
  - `src/tempo/timing.py` (TIMING-v1);
  - `src/tempo/timinggen.py`;
  - `scripts/timing_{generate,validate,run,analyze}.py`;
  - `tests/test_timing.py`.

  Every 1.12.0 module is byte-identical. The two new pool names are added to `freshgen.CONS` at import time; that table is data and the file is not edited.
- **Tests.** 173/173 temporal tests pass: the 162 from 1.12.0 plus 11 new ones.

## Question
Does moving the same paid measurement later recover useful decisions, and is that benefit worth the extra waiting under declared costs?

The study compares fixed schedules. It is not an optimal observation controller and it does not test learned dynamics.

## Assumptions changed from 1.12.0
**Fixed environment clock.** The environment no longer follows the controller's clock.
- The episode origin is absolute 12 (elapsed 0).
- One public activity window, (12, 14) (elapsed 0 < t < 2), applies to every schedule. Declarations carry the numeric window `{"lo": 12, "hi": 14}`.
- The world is declared stable after t = 2. The stable variant allows no external change at any time.
- The hidden tape fixes events at elapsed 0.5 or 1.5, independently of requests, receipts, waiting, actions and declines.
- Every schedule acts at t ≥ 2, so no external change happens during a plan.
- The actual pre-action state is identical across schedules, which is checked.
- **Substantive assumption:** a known quiet period follows the window. The result does not show that waiting can discover when an uncontrolled world has become stable.

**Projection base.** The belief base is the episode origin for every schedule; it is never the late request time. The 1.12.0 `temporal_project` (unchanged) is called with:
- base = origin;
- evidence cutoff = the schedule's decision time;
- target = its action boundary.

Readings at the origin anchor their field (EARLY, EARLY_WAIT). DEFER's reading at t = 2 filters the propagated set at its own time, and joint states, one-shot counts and invariants are kept. The reference (`freshref`, unchanged) receives the same base, cutoff, target and windows.

**Outcome kinds.**
- **Execute:** a non-empty plan, checked step by step.
- **Complete:** the empty `already` plan. It succeeds only if the actual goal holds at the boundary; otherwise it is a *false completion*, recorded separately from an invalid attempt.
- **Decline:** no candidate is selected. The actual goal truth is reported separately (`decline_goal_already_true`).

Selection uses `plan is not None`.

## Schedules (same sensor, P2 fields, tape and fees)

| Schedule | Request / measure | Receive | Decide / first action | Pre-action wait |
|---|---|---|---|---|
| EARLY | t = 0 | 2 | 2 | 2 |
| EARLY_WAIT | t = 0 | 2 | 4 | 4 |
| DEFER | t = 2 | 4 | 4 | 4 |

- **Sensor:** reliable; costs 1 per fact; delivers 2 time units after measuring; budget 2; one batch; no retry or early exit.
- **Fees and waiting** are paid on declines too.
- **P2's request** is computed once at t = 0 from the initial structured operational view, using the frozen `needs_verification` in registry order with a cap of 2. It is then cloned into every schedule and environment.

## Utility and contrasts (fixed now)
**Utility:** `U_λ = 10·success − action_cost − 3·invalid − queried_facts − λ·pre_action_wait`.
- The primary price is **λ = 1**, a declared convention rather than an estimate.
- Sensitivity at λ ∈ {0, 0.25, 0.5, 1, 2} is computed analytically on the same trajectories.

**Contrasts** (changing environment, temporal projection; all at λ = 1):
- **Primary:** DEFER − EARLY.
- **Mechanism:** DEFER − EARLY_WAIT (equal fees and equal waiting).
- **Per goal:** DEFER − EARLY for A and B separately.
- **Controls:**
  - changing: EARLY_WAIT − EARLY = −2 exactly, with identical states and choices;
  - stable: DEFER − EARLY_WAIT = 0 exactly;
  - stable: DEFER − EARLY = −2 exactly;
  - stable: identical states, choice, success, action cost and fees across all three schedules.

**Break-even:** ΔU_λ = ΔU₀ − 2λ, so λ* = ΔU₀ / 2, reported per world and for the panel.
- If ΔU₀ < 0, no nonnegative price favours DEFER.
- If ΔU₀ = 0, the two tie only at a price of 0.
- None of this is extrapolated to real change rates.

**Statistics:** domain-stratified bootstrap, 10,000 resamples, seed 20261105, **n = 24 worlds**; descriptive.

## Panel (committed before any controller output)
**Size.** 24 new base worlds (12 per domain) × A/B × stable/changing × 3 schedules = **288 trajectories**. Temporal projection only, structured input only.

**Pools and seeds.**
- Main: pool `timing`, base seed **20261210**.
- Smoke: pool `timingsmoke`, base seed 20261211, 4 disjoint worlds, 48 trajectories, not pooled.
- During implementation, the pipeline was debugged on pool `timingsmoke` with base seed 999 and discarded. The main seed was not run before the commitment.

**Allocation.** The same 24 predeclared kinds of change as 1.12.0 (`freshgen.DELIVERY` / `ASSEMBLY` rows; see the 1.12.0 plan for the table), instantiated in new worlds with new names and seeds:
- realized and unrealized relevant changes;
- irrelevant changes;
- guard-false preservation, and an effect that does not touch the plan;
- new candidate plans;
- genuinely newly feasible goals (d05/A, d07/B, d12/B, a06/B kinds);
- unqueried prerequisites, independent (a03, a04, a12 kinds) and correlated return-to-stock (a10 kind).

16 worlds realize a change and 8 realize none. Evidence is meaning-correct, and every goal copy requests 1–2 facts.

**Expected by construction, not tuned:** DEFER cannot resolve an independently changing unqueried prerequisite, but can resolve the correlated one indirectly. DEFER is not required to dominate EARLY_WAIT.

## Fixtures (`tests/test_timing.py`)
1. Fixed event timing; identical pre-action state; offsets and elapsed times.
2. A late request keeps the origin base and the window.
3. Request-time sampling differs between EARLY and DEFER.
4. A receipt does not appear before it is received; one-shot counts hold, including the B→C→B chain.
5. The stable and EARLY = EARLY_WAIT equalities and the cost identities.
6. DEFER resolves a queried change; an independent unqueried prerequisite stays unresolved; the correlated one is resolved indirectly.
7. A false completion, a true completion, an invalid attempt, and a decline whose goal was already true are each scored distinctly.
8. A candidate gain or loss while the goal stays feasible, versus a goal that becomes newly feasible.
9. Zero-query compatibility path; equal-time conflicting receipts. Missing fields, invariants and limits are covered by the unchanged 1.12.0 fixtures in the suite.
10. Hidden-schedule leakage: identical observations give identical beliefs; different later observations may differ.
11. EARLY equals the 1.12.0 temporal projection at delay 2.

## Pre-run validation (`phase0/`)
1. Declarations are well formed and invariant-preserving, with the fixed window (12, 14).
2. Fixed environment:
   - every tape event happens at a half-tick inside (12, 14);
   - the pre-action state is identical for every schedule;
   - the stable variant realizes nothing;
   - the sensor's value equals the actual environment value at its measurement time.
3. The support contains the actual initial state.
4. The request contains 1–2 facts and equals the intended set.
5. Allocation.
6. Reference only: DEFER has both guaranteed and no-guarantee cases.
7. Public and hidden data are separated.
8. Compatibility:
   - the 1.12.0 scored panel re-runs to its 384 stored trajectories;
   - EARLY on the 1.12.0 panel equals 1.12.0 temporal delay 2 (96 cases).

## Gates (each schedule separately; on failure: report the defect and stop)
- **G1:** reachable states, candidate classes and choice exactly match the independent reference.
- **G2:** the actual state is in the support, and there is no unsupported choice, invalid attempt or false completion.
- **G3:** the reference's cheapest guaranteed candidate is chosen whenever one exists, so declining everything cannot pass.
- **G4:**
  - fixed clock (expected clocks, base = origin) and identical pre-action states;
  - the request is cloned;
  - delivery takes 2;
  - log, history and earlier-information records are preserved, and a receipt is absent before it is received;
  - no refusals; all states admissible;
  - the controls and cost identities above hold;
  - hidden-tape leakage: across four alternative tapes, identical receipts give identical beliefs and choices.

Passing is an implementation property under a supplied contract. It does not require a positive utility contrast.

## Reported outcomes
**Per schedule and environment:**
- utility at every λ;
- success and actual goal truth;
- selected empty plans and false completions;
- invalid attempts and unsupported choices;
- declines and justified declines, plus declines where the goal was already true;
- missed menu-feasible opportunities;
- menu feasibility and full-domain feasibility (both independent solvers);
- queried facts, action cost and waiting;
- support size and actual-state inclusion;
- uncertain queried versus unqueried prerequisites;
- runtime.

**Diagnostics (changing):**
- DEFER succeeds where EARLY_WAIT does not;
- the earlier measurement was more useful;
- DEFER's support is larger;
- DEFER's residual declines, by cause (unqueried prerequisite / queried prerequisite / no menu candidate);
- unqueried facts resolved indirectly;
- candidate gains and losses relative to t = 0, kept separate from goals that became newly menu-feasible or newly menu-infeasible;
- feasible in the full domain but with no menu candidate.

All schedule disagreements are listed with their event, measurement, receipt and action timelines.

## Interpretation and stop
- **Primary positive with an interval above 0:** deferred sampling earned its waiting cost on this designed allocation under the known-window contract.
- **Primary inconclusive or negative:** reported unchanged. The mechanism contrast and break-even prices still show when later sensing helps.
- **Neither outcome shows** optimal querying, calibrated risk, or behaviour without a known quiet period.
- **Stop after the report.**
