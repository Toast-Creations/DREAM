# Observation freshness when the world can change (V1.12.0): frozen plan

- **Brief:** `OBSERVATION-FRESHNESS-BRIEF.md` (copy in `design/BRIEF-copy.md`). Development only. **Zero model calls; the GPU stays free.**
- **This plan** is hashed in `config/FROZEN-PROTOCOL.json` together with the source, the committed panel and the smoke results, before the scored panel runs. Any later amendment is recorded in `config/AMENDMENTS.md`, keeping the preceding version.
- **Predecessor:** 1.11.0 is a completed snapshot (git `a85bbe7`, pushed 2026-11-05). Its artifacts and scores are unchanged.
- **Source:** `Code/DREAM-project-1.12.0-observation-freshness-20261105`, which is 1.11.0 plus:
  - `src/tempo/freshness.py` (clock, transition contract, environment, sensor, both projections, matched loop);
  - `src/tempo/freshref.py` (independent reference);
  - `src/tempo/freshgen.py` (panel allocation and generator);
  - `scripts/fresh_{generate,validate,run,analyze}.py` and `tests/test_fresh.py`.

  Every 1.11.0 module is byte-unchanged: agentstate, recovery, goals, policy, assertions, engine, transfer and text_channel.
- **Tests:** 162/162 temporal tests (the 139 from 1.11.0 plus 23 new) in the research container, offline.

## Question
Can a temporal operational projection do three things together?
- Keep what a reliable reading established at its measurement time.
- Propagate only the publicly allowed changes up to the time action begins.
- Choose a plan that is valid in every state still possible at that time.

This tests software against a **supplied** finite transition model. It does not test learned dynamics, sensor noise, interpretation of prose, or observation policy.

## Clock and ordering (published before any scored trace)

| Name | Definition |
|---|---|
| `requested_at` | 12 (absolute; `DECIDE`); elapsed 0; offset 12 |
| `measured_at` | the request instant: every field in a batch shares this one time |
| `received_at` | `measured_at` + delay, with delay ∈ {0, 2} (1.11.0 used 1) |
| `decision_at` | `received_at` |
| `execute_at` | the scheduled first-action boundary: `received_at` + gap. The gap is 0 in the panel; one fixture uses 1. The boundary applies even when the controller declines, so support and missed opportunities are evaluated at it. |

Every trace stores the absolute times, the elapsed times and the offset.

**Ordering:**
- Observations, receptions, decisions and actions happen at integer instants. At one instant the order is measure, then receive, then decide, then first action.
- External changes happen only at half-ticks strictly inside the open window (`requested_at`, `execute_at`). So a change cannot be ordered at or after an action, and with delay 0 the window is empty.
- External changes are disabled from `execute_at` onwards. During the plan, only your own actions change the world, through the existing action rules.

## Environment contract
**Two variants per base world:**
- **Stable:** declares no transition.
- **Changing:** declares one or two one-shot transitions.

**What a declaration contains** (public): `{id, text, guard, effect, window = (requested_at, execute_at), max_occurrences = 1}`.
- A declared change may happen once, at an unannounced time inside its window, if its guard holds at that moment. It may also not happen: the no-change branch always exists.
- Correlated effects form a single transition. The panel's only two-field transition is the assembly "return to stock" change: the slot becomes empty and the part becomes on hand.
- Effects never touch agent state. They are checked to preserve `carry_link` and `slot_connector` on every admissible state, so a crate cannot enter your empty hands.
- At most two entity fields per world are involved.

**Hidden** (environment and scorer only, kept in `data/hidden/`): the realized event tape, the seeds, the case labels and the true state.
- The tape fixes events at elapsed 0.5 or 1.5, so they are realized only with delay 2.
- The tape is precommitted and independent of the projection, and the world is never regenerated.
- Both projections see the same world up to the shared first-action time.
- A field can change with no report of the change, so the absence of a report is not a guarantee that a fact persisted.

## Projections (same log, same P2 request, same receipts, same ledger)
**Carry-forward: an ablation that omits temporal propagation.**
- It is 1.11.0's `recovery.project` (SCOPED-CURRENT-OBSERVATION-v1), unchanged, applied at `decision_at`.
- Its states are used at `execute_at` as if nothing could change.
- In stable conditions it is exactly 1.11.0's contract. In changing conditions it deliberately extrapolates beyond 1.11.0's guarantee, so its errors there are not regressions of the 1.11.0 result.

**Temporal: TEMPORAL-OBSERVATION-v1.**
- **Times:** target state time `execute_at`; evidence cutoff `decision_at`; base time `requested_at`.
- **Steps:**
  1. **Base support.** Take the historical operational view at the base time. It is built from the non-sensor evidence received by the cutoff, in a shadow engine over the shared log minus the sensor's log copies, so a later reading is never carried backwards by persistence.
  2. **Receipt screening.** Receipts are screened as in 1.11.0: registered sensor, context, requested field, received by the cutoff, no action yet, and admissible value. Two further conditions apply: the receipt was measured at or after its request, and not after `execute_at`. Equal-time contradictory receipts are an authority conflict and are not used; no recency rule applies.
  3. **Applying readings.** Readings at the base time anchor their field there; this is 1.11.0's scoped authority, at the measurement time only. Readings at later times filter the propagated set at their own times.
  4. **Propagation.** Between observation instants, every declared transition whose window overlaps the segment and that has not yet occurred may occur, in any order, when its guard holds. This applies to unqueried facts as well. If a guard reads a field that is absent, the fields its effect writes become absent.
  5. **Possible states at execution** are the reachable set at `execute_at`.
- **Planner (unchanged):** the cheapest candidate that succeeds in every state, with the tie broken by (cost, key). An empty set counts as a conflict, never as permission.
- **Never:** it does not edit the log, the history, source statuses, conflicts or earlier-information views. It does not invent events. It does not use the hidden tape, a time-to-live, recency, or probabilities.
- **Out of scope in this version:** reports about a time after the request time return no support, flagged `out_of_scope_later_report`. The panel contains none.
- **Limits (frozen):** at most `MAX_STATES = 4096` states per frontier and `CPU_LIMIT_S = 5.0` s of CPU per projection. Exceeding either raises `LimitExceeded`: the run stops and reports it, and no subset is substituted.

## Matching
- **P2's request** is computed once per base world and goal from the initial structured operational view at `requested_at`, before any delay condition or receipt exists. It uses the frozen `recovery.needs_verification` with a budget of 2, and the exact request is cloned into all four environment and delay conditions and both projections.
- **Receipts:** every condition measures the same initial hidden state at the same request time, so receipt values agree across conditions and only delivery times differ.
- **Shared within each condition:** both projections share the requests, readings, delivery times, ledger entries and raw evidence.
- **Not tested:** query timing, waiting or rechecking. There is one batch, with no retry, no second query and no free final measurement.

## Independent reference (`freshref.py`)
**What it may and may not share.** It shares only declarative inputs: the predicate table and invariants, the goal test, the plan costs and the declarations. It never calls the production propagation, `guaranteed` or `choose`.

**Inputs** (public): the historical support at the base time, the receipts received by the cutoff, and the declarations.

**Method.**
- It enumerates whole trajectories. Each transition is either absent or placed in one elementary gap inside its window, and every order is tried within a gap.
- Guards are checked at their turn and readings at their times; base-time readings are anchors.
- It then classifies candidates (guaranteed, possible or impossible) and picks the minimum (cost, key).

**Separate evaluator.** The environment evaluator (the actual hidden state at `execute_at`) answers a different question: what was really valid.

## No-model fixtures (`tests/test_fresh.py`, 23 tests, all passing before the panel)
1. **Stable parity:**
   - temporal equals carry-forward for delays 0, 1 and 2, and equals 1.11.0's `recovery.run` scoped result at delay 1;
   - a verified–verified conflict is recovered exactly as in 1.11.0;
   - pre-run check 8 replays all 96 committed 1.11.0 scoped trajectories, including the four recovery worlds and real extractions.
2. A relevant change during delivery makes the old plan illegal: carry-forward makes an invalid attempt; temporal declines.
3. A change is possible but none is realized: uncertainty is kept and the missed opportunity is counted.
4. A change to an unrelated field: the decision stays usable.
5. A transition changes a value but preserves the needed predicate. A guard that is false in every supported state keeps an old reading decisive.
6. A delayed old reading versus a fresh reading measured after the change, in separate reset branches (hand-worked: certain).
7. A change between receipt and execution (gap 1): propagation ends at action time.
8. An unqueried verified prerequisite becomes uncertain while a different fact is in transit: no fallback.
9. Two readings at different times are processed jointly with a correlated transition (hand-worked sets); the naive snapshot is shown to differ.
10. An arrival after measurement opens an opportunity, and it is counted as missed.
11. Absent guard fields; empty support; invariant-violating declarations rejected (carried-by-you, agent state, wrong connector); the correlated effect stays joint; the receipt refusals (unregistered sensor or text claiming to be one, other context, unrequested field, not yet received, measured before the request, measured after the target time, inadmissible value); equal-time contradictions.
12. Hidden-tape leakage: three alternative tapes produce identical receipts, ledger, states, candidates, plan and log.

Also covered: zero-query behaviour, the state limit, out-of-scope later reports, and log/history preservation.

## Bounded generated panel (committed before any controller output)
**Size.** 24 fresh base worlds, 12 per domain × goals A/B × delay 0/2 × stable/changing × 2 projections = **384 trajectories**, structured only.

**Pools and seeds.**
- Main: pool `fresh`, base seed **20261207**.
- Smoke: pool `freshsmoke`, base seed 20261208, 4 disjoint worlds, 64 trajectories, not pooled.
- A development trial during implementation used pool `fresh` with base seed 20261201 and was discarded; the main seed was never run before the commitment. The allocation is fixed in code, so no seed or world is chosen from outputs.

**Evidence.**
- Every report is true.
- Statuses decide P2's request under the frozen rule:
  - `prov`: a correct provisional observation;
  - `unres:X`: a verified observation followed by a change whose result was not recorded, options {truth, X};
  - `ver`: verified.
- Each goal copy requests 1 or 2 relevant facts. Pre-run check 4 verifies this from public inputs, and it must equal the intended status.
- The initial support contains the actual initial state over the closed scope (pre-run check 3).

**Allocation** (`freshgen.DELIVERY` / `freshgen.ASSEMBLY`; the labels are the intended goal dependence, hidden):

| World | Declared change(s) | Tape | A | B |
|---|---|---|---|---|
| d01 | EA B→C | x1 at 0.5 | loss_realized | irrelevant |
| d02 | EA B→C | none | loss_possible_no_change | irrelevant |
| d03 | EA YOU→G | x1 at 1.5 | loss_realized | irrelevant |
| d04 | EB B→YOU | none | irrelevant | loss_possible_no_change |
| d05 | EA C→YOU | x1 at 0.5 | gain_realized | irrelevant |
| d06 | EA C→G | none | gain_possible_no_change | irrelevant |
| d07 | EB C→B | x1 at 1.5 | irrelevant | gain_realized |
| d08 | EA B→C (guard false); EB YOU→C | x2 at 0.5 | preserved_guard_false | loss_realized |
| d09 | crate Z moves | x1 at 0.5 | irrelevant | irrelevant |
| d10 | EA YOU→B; EB B→YOU | both | loss_realized | loss_realized |
| d11 | EA G→C | none | loss_possible_no_change | irrelevant |
| d12 | EB C→G | x1 at 1.5 | irrelevant | gain_realized |
| a01 | G taken away | x1 | loss_realized | irrelevant |
| a02 | W installed in T | none | loss_possible_no_change | irrelevant |
| a03 | W installed in T (T unqueried) | x1 | unqueried_loss_realized | irrelevant |
| a04 | W removed from T (T unqueried) | none | unqueried_loss_possible_no_change | irrelevant |
| a05 | G delivered | x1 | loss_realized_opens_other | irrelevant |
| a06 | G delivered; D delivered | both | preserved_effect_irrelevant | gain_realized |
| a07 | LO installed in S2 | none | irrelevant | loss_possible_no_change |
| a08 | HI installed in S2 | x1 | irrelevant | loss_realized_opens_other |
| a09 | W removed from T; D taken | x1 only | loss_realized | loss_possible_no_change |
| a10 | G returned from T to stock (two fields; T unqueried) | x1 | unqueried_correlated_loss_realized | irrelevant |
| a11 | HI removed from S2 | none | irrelevant | loss_possible_no_change |
| a12 | W installed in T (T unqueried) | x1 | unqueried_loss_realized | irrelevant |

Counts: 16 worlds realize at least one change and 8 realize none (4 per domain).

| Domain | Goal | Labels |
|---|---|---|
| Delivery | A | loss_realized 3; loss_possible_no_change 2; gain_realized 1; gain_possible_no_change 1; irrelevant 4; preserved 1 |
| Delivery | B | irrelevant 7; loss_possible_no_change 1; gain_realized 2; loss_realized 2 |
| Assembly | A | loss_realized 2; loss_possible_no_change 1; unqueried_loss_realized 2; unqueried_loss_possible_no_change 1; loss_realized_opens_other 1; preserved 1; irrelevant 3; unqueried_correlated_loss_realized 1 |
| Assembly | B | irrelevant 7; gain_realized 1; loss_possible_no_change 3; loss_realized_opens_other 1 |

Delivery goal copies whose crate is at C have no menu candidate: the declared family gap. Pre-run check 6 lists these as candidate-family coverage gaps, together with their independent optimum, separately from infeasibility. Menus are not enlarged.

## Pre-run validation (`phase0/`; no comparison of controller outputs on the panel)
1. Declarations: well formed, invariant-preserving, no agent state, values publicly allowed, ≤ 2 fields per world.
2. Every tape event really happens with delay 2 at a half-tick; nothing happens with delay 0.
3. The support contains the actual initial state.
4. Requests contain 1–2 facts and equal the intended status.
5. Allocation counts.
6. Reference only: some delayed-changing copies have a guaranteed candidate and some have none. Opportunities are computed at the actual action time, and coverage gaps are checked against both solvers' independent optimum.
7. Public and hidden data are separated.
8. 1.11.0 parity replay.

## Gates (must all pass; otherwise report the defect and stop)
- **G1:** the temporal reachable set, candidate classes and choice equal the reference exactly, in all 192 temporal trajectories. Fixtures cover the exhaustive small cases.
- **G2:** the temporal projection gives no permission for a candidate that is not guaranteed in the reference, and makes no actual invalid attempt.
- **G3:** whenever the reference has a guaranteed candidate, the temporal projection selects it, so declining everything cannot pass.
- **G4:** stable conditions give temporal = carry-forward (states, plan, utility) at both delays. Delay 0 gives changing = stable for both projections.
- **G5:** matching and provenance hold:
  - the request is cloned; receipt values are equal across conditions; delivery equals the delay;
  - identical receipts, ledger, log and historical reconstruction across projections;
  - log and earlier-information records are preserved; all states are admissible;
  - the actual state is inside the temporal support;
  - no refused receipts and no authority conflicts in the panel;
  - hidden-tape leakage check: the realized tape, an empty tape and an all-events tape give identical beliefs.

Passing establishes an implementation property under a supplied finite contract. It is not evidence about model cognition or unrestricted deployment.

## Outcomes (reported whatever their sign)
**Per cell** (environment × delay × projection, and per goal):
- utility;
- success;
- actual invalid attempts;
- unsupported permissions relative to the reference;
- declines, split by whether the reference has a guaranteed candidate;
- missed menu-feasible opportunities at action time;
- queried facts;
- action cost;
- state-set size, and relevant fields left uncertain;
- inclusion of the actual state;
- exact-set agreement.

**Categories (delayed-changing):**
- guaranteed candidates lost to possible change;
- candidates preserved despite a declaration touching a relevant fact;
- opportunities opened or closed by actual change;
- justified declines where the hidden world allowed action;
- carry-forward invalid attempts, and its unsupported but lucky successes;
- uncertainty although nothing happened;
- declared changes to an unqueried prerequisite.

Results are also broken down by intended label. Every disagreement trace is listed, along with runtime and the maximum set size.

**Utility formula (unchanged):** U = 10·success − action cost − 3·invalid − queried facts. Waiting time is exposed but kept outside U.

**Contrasts** are computed per world (goals averaged) as temporal − carry-forward:
- **Primary:** delayed-changing.
- **Per goal:** delayed-changing for A and B separately.
- **Controls:** stable d2, stable d0 and changing d0 (expected exactly 0).
- **Cost of possible change:** changing d2 − stable d2, for each projection.

All are domain-stratified bootstrap, 10,000 resamples, seed 20261105, with **n = 24 worlds** (not 384), and descriptive.

## Interpretation and stop
- **If a gate fails:** report the defect and stop; launch no text calls.
- **If all gates pass:** the temporal projection is a correct implementation of the supplied contract on this panel. Its utility relative to carry-forward is a separate development finding, whatever its sign:
  - correct conservatism is expected to decline attractive but uncertain actions;
  - the declines are counted as justified (the reference has no guarantee) when the hidden world happened to allow action.
- **What a positive contrast would mean:** under these costs, avoiding invalid attempts outweighed the lost opportunities on this allocation. It would not show that conservative guaranteed planning is the best practical policy.
- **Stop after the report.** No text extraction, sensor noise, arrival reinterpretation, adaptive requerying, broader planning or learned transitions.
