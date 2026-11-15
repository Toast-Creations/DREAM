# Observation freshness when the world can change (V1.12.0): report (development only)

## Status
- **Brief and plan:**
  - brief `design/BRIEF-copy.md`;
  - plan `design/STUDY-PLAN.md`, frozen with the source, the committed panel, the validation results and the smoke results in `config/FROZEN-PROTOCOL.json` (source `73a84e4e…`) before the scored panel ran.
  - There were no amendments.
- **Predecessor:** 1.11.0 is committed and pushed as a snapshot (git `a85bbe7`). Every 1.11.0 module is byte-identical in 1.12.0 (checked in the freeze manifest).
- **Tests and pre-run validation:**
  - 162/162 temporal tests passed, including 23 new fixtures (`test-results/tests-1.12.0.txt`).
  - Pre-run validation (`phase0/`) had 0 failures. This includes the 1.11.0 parity replay: **192/192** trajectories identical, covering 96 scoped trajectories × 2 projections. Those 96 include real extractions and the four 1.11.0 recovery worlds.
- **Ran 2026-11-05:**
  - smoke: 4 disjoint worlds, 64 trajectories, all gates passed, not pooled;
  - scored panel: 21:51, **384 trajectories in 1.3 s of CPU**.
  - Zero model calls; the GPU was not touched.
  - Every run was offline in the research container with sleep blocked.
- **Projection size and cost:** maximum reachable set 8 states, maximum projection CPU 0.5 ms. Both are far inside the frozen limits (4,096 states, 5 s), and `LimitExceeded` never fired.
- **Sample:**
  - 24 fresh worlds (12 per domain) × goals A/B × delay 0/2 × stable/changing × carry-forward/temporal.
  - Unit of inference: the **24 worlds**.
  - P2 requested 52 facts: 1 fact in 44 goal copies and 2 in 4, identical across all conditions.

## Correctness gates: all pass

| Gate | Result |
|---|---|
| G1: temporal reachable set, candidate classes and choice exactly equal the independent reference | 0 / 192 disagreements |
| G2: no permission for a candidate that is not guaranteed; no actual invalid attempt | 0 / 192 |
| G3: picks the reference's cheapest guaranteed candidate whenever one exists (no pass by declining) | 0 / 148 misses |
| G4: stable gives temporal = carry-forward (both delays); delay 0 gives changing = stable (both projections) | 0 / 192 |
| G5: matching, provenance, history preservation, invariants, actual state in temporal support, hidden-tape leakage | 0 failures |

Details behind G5:
- **Inputs.** Requests were cloned unchanged across conditions. Receipt values were identical across conditions, and delivery time equalled the delay.
- **Shared records.** Within each condition, the two projections shared one log, one ledger and one historical reconstruction. The log prefix and the earlier-information record before the request were untouched.
- **Support.** Every state was admissible. The actual hidden state was inside the temporal support in **48/48** delayed-changing goal copies; for carry-forward it was 17/48.
- **Hidden tape.** The realized tape, an empty tape and an all-events tape gave identical beliefs and decisions in all 48 delayed-changing copies.

**Reading:** on this panel, TEMPORAL-OBSERVATION-v1 is a correct implementation of the supplied finite transition contract. This is a software property under supplied dynamics, not evidence about learned dynamics or model cognition.

## Three layers kept apart

| Layer | What it is | Where |
|---|---|---|
| Current evidence | historical reports plus point-time sensor readings (each certain about its measurement time only) | log, ledger, `readings`, `anchors` |
| Reachable possibilities | states the public transition relation allows at `execute_at` | temporal `states`, reference `states` |
| Actual hidden state | the environment at `execute_at` after the hidden tape | `actual_relevant_at_execute`, `valid_at_execute` (scorer only) |

## Main result: delayed-changing condition (the primary)

| Cell (48 goal copies) | Utility | Success | Invalid attempts | Unsupported permissions | Declines (reference has no guarantee / has one) | Missed opportunities |
|---|---|---|---|---|---|---|
| Carry-forward | **123** | 30 | **11** | **20** | 6 (6 / 0) | 13 |
| Temporal | **107** | 22 | **0** | **0** | 26 (26 / 0) | 21 |
| Either projection, stable or delay 0 (control) | 238 | 42 | 0 | 0 | 6 (6 / 0) | 0 |

| Contrast (per world, goals averaged; n = 24; descriptive) | Mean [95%] | Better / equal / worse |
|---|---|---|
| **PRIMARY: changing d2, temporal − carry-forward** | **−0.33 [−1.38, +0.67]** | **9 / 7 / 8** |
| Goal A | +0.17 [−1.50, +1.67] | 8 / 12 / 4 |
| Goal B | −0.83 [−2.21, +0.38] | 3 / 17 / 4 |
| Controls: stable d2, stable d0, changing d0 | 0.00 [0, 0] each | 0 / 24 / 0 |
| Cost of possible change, carry-forward (changing d2 − stable d2) | −2.40 [−3.50, −1.33] | 0 / 13 / 11 |
| Cost of possible change, temporal (changing d2 − stable d2) | −2.73 [−3.48, −1.98] | 0 / 6 / 18 |

**The utility contrast is inconclusive.** The interval includes 0, and worlds split 9 better, 7 equal and 8 worse. Correctness did not translate into higher utility on this allocation under these costs. The two projections trade different errors:

**Carry-forward:**
- **11 invalid attempts.** The relevant fact really changed (a01, a03, a05, a08B, a09A, a12, d01, d03, d08B, d10A, d10B).
- **8 unsupported but lucky successes.** A change was possible but did not happen (a02, a04, a07B, a09B, a11B, d02, d04B, d11).
- **1 failure that was not an invalid attempt.** In a10/A the empty "already" plan was chosen after another technician had returned G to stock. The goal silently no longer held (U −1).

**Temporal:**
- **20 guaranteed candidates lost to possible change.** All were justified: the reference had no guaranteed candidate in every one of its 26 declines.
- **No permission it could not guarantee.**
- **21 justified declines where the hidden world allowed action.** That includes the 8 no-change worlds, where it stayed uncertain because it was never told that nothing happened.

**Where the utility difference comes from:**
- Carry-forward's lucky successes in the 8 no-change copies earned about +6 each on average. Its invalid attempts cost about −5.
- Temporal paid −1 or −2 (the query cost) in every decline.
- With 7 realized-loss and 7 possible-no-change copies of the main loss type, these roughly cancel.
- The sign would follow the ratio of realized to unrealized changes, which this panel fixed by allocation and did not sample from any real rate.

## What the temporal projection did right (by intended label, changing d2)

| Label | n | Temporal success / decline / U | Carry-forward success / invalid / U |
|---|---|---|---|
| loss_realized | 7 | 0 / 7 / −7 | 0 / 7 / −32 |
| loss_possible_no_change | 7 | 0 / 7 / −8 | 7 / 0 / +44 |
| unqueried_loss_realized | 2 | 0 / 2 / −2 | 0 / 2 / −14 |
| unqueried_loss_possible_no_change | 1 | 0 / 1 / −1 | 1 / 0 / +6 |
| unqueried_correlated_loss_realized | 1 | 0 / 1 / −1 | 0 / 0 / −1 (silent goal failure) |
| loss_realized_opens_other | 2 | 0 / 2 / −3 | 0 / 2 / −9 |
| gain_realized / gain_possible_no_change | 4 / 1 | all decline | all decline |
| preserved (guard false; effect irrelevant) | 2 | 2 / 0 / +13 | 2 / 0 / +13 |
| irrelevant (change to the other goal's fact or a third crate) | 21 | 20 / 1 / +121 | 20 / 0 / +121 |

- **Propagation was not "age makes everything unknown".**
  - Both preserved cases kept their plan: d08/A, where the declared move's guard is false, and a06/A, where G's stock changes but "already" does not read it.
  - All 21 irrelevant-change copies acted exactly as in the stable world. The one decline there is a menu coverage gap that occurs in every condition.
- **Unqueried prerequisites were propagated** (a03, a04, a10, a12: the verified slot was not the queried fact). There was no fallback to the stale historical value.
- **The correlated "return to stock" change stayed joint** (a10/A): the projection kept 2 states, not the 4-way product.
- **Opportunities opened by actual change (13) were all missed by both projections.** Examples are d05/A (a crate arrives at your place) and a06/B (part D delivered). With one batch measured at the request instant, no projection can learn of an arrival during delivery. This is a property of the matched design (no requery or waiting), not of either projection.

## Coverage and feasibility
- **Menu-feasible goal copies at action time:** 42/48 in the stable and delay-0 conditions; 43/48 in changing d2 (changes closed 12 opportunities and opened 13).
- **Candidate-family coverage gaps:** pre-run check 6 lists 16 conditions where a valid plan exists outside the supplied menu. Most involve delivery crates at C, and a few involve post-change states (d01/A, d08/B, a12/A in changing d2). These are menu declines, not infeasibility. Menus were not changed.

## What this shows and does not show
**Shown, under the stated assumptions:**
- reliable sensor; finite public one-shot transitions inside (request, first action); no changes during the plan; one batch at the request instant; structured, meaning-correct evidence;
- on that basis, the temporal projection keeps readings as point-time facts, propagates exactly the publicly possible changes (independently confirmed, 192/192 exact sets), never permits a plan it cannot guarantee, and reproduces 1.11.0 exactly wherever the world is declared stable or the window is empty.

**Not shown:**
- that conservative guaranteed planning is the better practical policy: the utility contrast is −0.33 [−1.38, +0.67];
- learned or inferred dynamics; noisy sensors; text extraction; arrival reinterpretation; the value of waiting, rechecking or timing queries; concurrent changes during multi-step plans; reports about times after the request (declared out of scope in this version and absent from the panel).

## Limits
- **Sample:** 24 worlds with a designed allocation. The realized/no-change mix (16 of 24 worlds realize a change) and the share of goal copies touched by a declaration are design choices, so utility magnitudes and their sign are allocation-dependent.
- **Small sets:** the dynamics are tiny (≤ 2 fields, ≤ 8 states), so scalability is not tested.
- **Implementation note:** the carry-forward ablation is 1.11.0's `recovery.project` called at the decision time; it is labelled an ablation everywhere.
- **Development disclosure:** a trial on pool `fresh` base seed 20261201 was run during implementation and discarded. The scored seed 20261207 was first run after the freeze.

## Next choices (none started)
- **Opportunity cost of conservatism:** a policy comparison with query schedules allowed to differ (re-measure at the action time, wait, or recheck one field) at a declared time cost.
- **Explicit risk policy:** a declared utility-based choice between guaranteed and possible plans. That needs probabilities the contract does not supply, so it would be a separately declared assumption.
- **Add the frozen text interface** on top of the temporal projection.
- **Larger or concurrent dynamics.**

## Artifacts
- **Traces:** `stages/main/{trajectories, reference, requests, leakage}.jsonl`, `RUN-META.json`; smoke in `stages/smoke/`.
- **Analysis:** `analysis/main/{ANALYSIS.json, TABLES.md}` (every disagreement trace is listed in TABLES.md).
- **Inputs:** public `data/public/`; hidden `data/hidden/`; commitments `data/COMMITMENT-*.json`.
- **Validation:** `phase0/VALIDATION.{json,md}` (smoke: `phase0/smoke/`).
- **Freeze:** `config/FROZEN-PROTOCOL.json`.
- **Re-run:** `run_stage.sh fresh main --require-freeze` (refuses to overwrite).
