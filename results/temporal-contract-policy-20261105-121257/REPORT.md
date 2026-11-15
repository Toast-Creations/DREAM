# Event-contract cleanup and active observation (V1.9.0): report (no model calls)

**Brief:** `EVENT-CONTRACT-AND-OBSERVATION-POLICY-BRIEF.md` (copy in `design/`).

**Source:** `<DREAM_HOME>/Code/DREAM-project-1.9.0-event-contract-policy-20261105`. Tests: 103/103 in the container (`test-results/tests-1.9.0.txt`).

**Freeze:** `config/FROZEN-PROTOCOL.json`, written before the main episodes were generated.

**Earlier runs:** no earlier source, run or score was changed. The repair/prose errata are in `../temporal-repair-prose-20261105-111843/ERRATA.md`.

## Phase 1: event contract v1 and assertion engine v0.3
The contract is in `design/EVENT-CONTRACT.md`; the implementation is `src/tempo/assertions.py`. Engine v0.2 is unchanged.

**What changed**
- **Reports are bundles of timed assertions.** A report holds state, event or correction assertions, with as many facts as the source states. There is no separate "initial" label. State assertions are constraints, not setters, so a later statement can't reset a timeline.
- **Events may leave the prior value unstated.** The engine derives the prior value from earlier evidence and never writes it into the source's assertion. Events, state assertions and corrections stay distinct.
- **Corrections withdraw exactly one claim:** the target report's assertion about the named field. A multi-fact report keeps its other claims.
- **A verified report outranks a provisional one it contradicts.** The provisional claim is suspended; no event is invented, and the earlier-information view is preserved.
- **Verified evidence that is inconsistent is kept as a conflict.** Every report stays, and the reports whose removal would restore consistency are listed as culprits. A correct later report is never forced to fit an earlier wrong one.
- **Each fact's state is reported separately:** value, unknown, conflict, incomplete (not processed), or not yet described, plus whether the value rests on provisional evidence. Action verdicts add `unresolved_conflict`.
- **Rejections are structural only.** Consistency is never a reason to reject.

**Validation** (`phase1/CONTRACT-VALIDATION.{json,md}`)

| Check (v0.3 fed the canonical mapping of the gold public records) | Agree / total |
|---|---|
| Current state, pilot variants | 252 / 252 |
| Plan validity (3 plans per variant) | 756 / 756 |
| Retrospective (P0) and earlier-information (K0) views | 84 / 84 and 84 / 84 |
| A0 applicability and successor | 84 / 84 |
| Probe rows (applicability and requirement vector) | 56 / 56 |
| Milestone-2 and prose-study checkpoints (state and both action verdicts) | 72 / 72 and 72 / 72 |

- **Unstated prior values:** with every event's `from` removed, 0 of 2,297 retrospective views change. In these histories the stated prior value never carried information beyond earlier evidence.
- **Hand fixtures:** 9 tests, with expected values written by hand from the contract. They cover:
  - multi-fact bundles and scoped corrections;
  - events with unstated prior values, including an entity introduced by an event;
  - no timeline reset, and delayed old reports;
  - uncertain events without `from`, settled later;
  - a verified observation suspending a provisional claim, with the earlier view kept and no event invented;
  - a verified conflict kept with culprit candidates, and an action on a conflicted field giving `unresolved_conflict`;
  - every structural rejection code, scorer keys included;
  - pending and incomplete reports with save/load;
  - parity with the old mapping and actions.

**Post-hoc replay of saved extractions (development analysis only).** I replayed the saved model extractions from milestone 2 and the repair/prose study under contract v1. Their original exact-schema scores are unchanged. The replay doesn't show the model improved, and it confirms nothing.

| Cell | Same meaning as source (old strict exact) | Mean assertion coverage | Final state exact under v0.3 (originally) | Conflict-field checkpoints |
|---|---|---|---|---|
| milestone 2, lines | 138 / 144 (135) | 0.960 | 21 / 24 (20) | 4 |
| prose study, lines, no retry | 130 / 144 (130) | 0.913 | 20 / 24 (19) | 7 |
| prose study, lines, one retry | 133 / 144 (133) | 0.934 | 20 / 24 (19) | 8 |
| prose study, prose, no retry | 123 / 144 (88) | 0.870 | 20 / 24 (19) | 22 |
| prose study, prose, one retry | 125 / 144 (90) | 0.884 | 20 / 24 (19) | 21 |

- **Two new scores:** "same meaning" (temporal denotation) means the extracted report induces the same constraints as the source, with a matching record ID, status and reception time. Coverage is the share of the source's atomic assertions that were recovered. A prior value is required only when the text itself states it.
- **Most of prose's lower exact score was the label mismatch.** Under the new contract, 123 prose records match the source's meaning, against 88 under the old strict scorer.
- **The real semantic errors remain** (an event read as a fact, a multi-fact report compressed to one fact). They now appear as retained conflicts rather than rejections and cascades.

**Readiness:** v0.3 reproduces every fixture value and passes the contract checks. It is ready to serve as the state layer, and Phase 2 uses it.

## Phase 2: when to trust temporal context, and when to look again
Plan: `design/POLICY-PLAN.md`. The 24 episodes (12 per domain) each get six public structured reports and hidden truth only the environment sees. Each episode is cloned into three matched policies: 72 trajectories, with no model calls.

**Fixed settings**
- **Sensor:** a reliable current-state sensor. Each fact costs 1 and the query delay is 1 time unit; at most 2 facts per episode.
- **World after the decision:** stable.
- **Decisions:** one per episode, and an invalid attempt ends the episode.
- **Utility:** U = 10·success − action cost − 3·invalid attempts − 1·facts queried.

| Policy | Utility, mean [95% CI] | Success | Invalid attempts | Missed opportunities | False blocks | Facts queried (episodes) | Wasted queries | Mean delay |
|---|---|---|---|---|---|---|---|---|
| P0, act on accepted evidence | 1.583 [0.21, 3.00] | 10 / 24 | 4 | 12 | 8 | 0 (0) | 0 | 1.42 |
| P1, always verify | 3.000 [2.00, 3.92] | 22 / 24 | 0 | 0 | 0 | 36 (24) | 18 | 3.63 |
| **P2, verify selectively** | **3.542 [2.50, 4.46]** | **22 / 24** | **0** | **0** | **0** | **23 (17)** | **7** | 3.33 |

The 2 remaining failures under P1 and P2 are the `no_plan` episodes, where no valid plan exists; declining there is correct.

| Paired contrast (24 episodes) | Utility | Success | Facts queried |
|---|---|---|---|
| P1 − P0 | +1.42 [−0.12, 3.00] (10 better / 1 equal / 13 worse) | +0.50 [0.29, 0.71] | +1.50 |
| P2 − P0 | **+1.96 [0.50, 3.46]** (10 / 8 / 6) | +0.50 [0.29, 0.71] | +0.96 |
| P2 − P1 | **+0.54 [0.29, 0.83]** (10 / 14 / 0) | 0.00 | −0.54 |

**By episode type** (success / invalid attempts / facts queried)

| Type (n) | P0 | P1 | P2 |
|---|---|---|---|
| false_block (4) | 0 / 0 / 0, all 4 falsely blocked | 4 / 0 / 6 | 4 / 0 / 6 |
| false_permission (4) | 0 / **4** / 0 | 4 / 0 / 6 | 4 / 0 / 6 |
| provisional_correct (4) | 4 / 0 / 0 | 4 / 0 / 6 (wasted) | 4 / 0 / 6 (wasted) |
| verified_settled (4) | 4 / 0 / 0 | 4 / 0 / 6 (wasted) | 4 / 0 / **0** |
| unresolved (4) | 0 / 0 / 0, all 4 declined | 4 / 0 / 6 | 4 / 0 / 4 |
| no_plan (2) | 0 / 0 / 0, correct decline | 0 / 0 / 3 (wasted) | 0 / 0 / **0** |
| corrected (2) | 2 / 0 / 0 | 2 / 0 / 3 | 2 / 0 / 1 |

**What the table shows**
- **Acting on accepted evidence** (P0) produced all 4 invalid attempts, in the uncorrected false provisional reports. It also lost 8 real opportunities: 4 false blocks from a false provisional report, and 4 declines on unrecorded outcomes.
- **Selective verification** (P2) looks again whenever the evidence for a decision-relevant fact is provisional or unresolved, whether the plan would be allowed or blocked. That recovered every false block as well as every false permission.
- **It skips settled facts.** P2 spent no queries on verified or settled episodes. Its only waste was on correct provisional reports, which cannot be told from wrong ones without looking: 6 of its 7 wasted queries.
- **Sensitivity (pre-declared):** if only 25% of uncorrected provisional reports were wrong, instead of the design's 67%, the weighted mean utility is P0 2.83, P1 2.79, P2 3.33. Always-verify then loses its advantage over acting on accepted evidence; selective verification keeps its lead.

**Integrity**
- In all 72 trajectories, the earlier-information view at the decision cutoff was preserved after the query arrived.
- Planning never changed the log (asserted).
- No query exceeded the budget.
- Every query that changed a belief also changed the plan: 12 of 12, for both P1 and P2.
- Belief matched the hidden truth on the relevant facts in 12/24 episodes before any query. With verification it matched in 24/24 for P1 and P2.

## Limits
- **Sensor:** it is reliable, and the world is stable between the query and the action. Either of these, relaxed, could change the ranking; neither was tested.
- **Design:** costs, rewards and the type allocation are design choices. Two thirds of uncorrected provisional reports are wrong by design, and the sensitivity analysis covers only that one dimension.
- **One decision per episode:** there is no replanning after a failure, which handicaps P0. Per-type results are given so the trade-offs can be read without the utility weights.
- **Sample:** 24 episodes in two action families, which is a small development sample. P2 is a fixed rule, not a learned or optimal policy.
- **Structured inputs:** with structured inputs, interpretation was deliberately excluded. Whether the benefit survives model-extracted inputs is untested.

## Stop and next decision
Both phases stop here, as the brief asks. Possible next steps, neither started:
1. Run the same policy comparison with the frozen text extractor as its input channel. A benefit that disappears would then point to a loss at the language interface.
2. Relax the sensor or stability assumptions.

Transfer to new action compositions remains separate.

## Artifacts
- `phase1/CONTRACT-VALIDATION.{json,md}`
- `analysis-policy/{trajectories.jsonl, ANALYSIS.json, TABLES.md}`
- `data/policy-episodes.jsonl` with `COMMITMENT-policy.json`
- `design/`
- **Re-run:**
  - `python3 -B scripts/contract_validate.py --out HUB/phase1`
  - `python3 -B scripts/policy_run.py --hub HUB --set policy` (verifies the committed episodes)
