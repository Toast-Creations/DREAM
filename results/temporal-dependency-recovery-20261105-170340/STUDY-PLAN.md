# Dependency parity and scoped current-observation recovery (V1.11.0): frozen plan

- **Brief:** `DEPENDENCY-AND-CURRENT-OBSERVATION-RECOVERY-BRIEF.md` (copy in `design/`). This plan is hashed in `config/FROZEN-PROTOCOL.json` before any model output. The main time budget is set after smoke. Development only.
- **Predecessor:** 1.10.0 is preserved as a completed snapshot: git `3b7b47c` in `dacook-blip/DREAM-code`, with errata in `ERRATA/1.10.0-deferred-goal.md` and in its run hub. It is listed in `config/FREEZE-1.10.0.json`.
- **Source:** `Code/DREAM-project-1.11.0-dependency-recovery-20261105`, which is 1.10.0 plus:
  - `src/tempo/agentstate.py` and `src/tempo/recovery.py`;
  - `scripts/deprec_{generate,validate,analyze}.py` and `tests/test_deprec.py`;
  - two pool names added to `transfer.CONS`.

  These are byte-unchanged:
  - engine v0.2/v0.3 and contract v1;
  - `policy.py`, `goals.py`, `text_channel.py`, the extraction prompt, adapter v1 and both renderers;
  - the world and history generators.

  Tests: 139/139 in the container (the 121 temporal tests plus 18 new).

## Question
1. **Repair.** Make the executor, the relevance rule, the belief states and validation agree on one state space.
2. **Comparison.** With the same evidence, does a named authority rule for a designated reliable sensor recover decisions that the strict contract leaves blocked?

## Part 1: dependency and invariant repair (both arms)
**What was wrong.** Engine v0.2/v0.3 derived "your hands are empty" from every crate's location. The declared relevance rule treated hands as a fixed agent-owned fact. The 1.10.0 sampler excluded "carried by you". So the three disagreed about which states extraction could hand to the executor.

**Explicit agent state** (`agentstate.py`):
- `agent.at` and `agent.hands` (either "empty" or the one crate held) are facts of the declared pre-action history. They come from the fixed facts "You are at P, with empty hands. You do not move unless you act".
- They are not constants:
  - `take X` sets `agent.hands = X`;
  - `put down X` sets it back to "empty";
  - `go` changes `agent.at`.
- The pre-decision phase contains no action of yours, so they hold their declared values there. The engine refuses to build a view once an action of yours is in the log.

**Declared invariants** (from the printed rules):
- `carry_link`: for every crate X, X is "carried by you" exactly when `agent.hands == X`. This covers "you can carry only one item at a time" and "an item is at a place only while it rests there".
- `slot_connector`: a slot holds nothing, or a part whose connector matches the slot. There are no adapters.

**Inconsistent extraction.** Before your first action, an assertion that a crate is carried conflicts with the declared empty hands. The field becomes an `invariant_conflict`:
- the assertion and its provenance are kept;
- the agent state is not changed to fit it;
- nothing is discarded or made consistent.

A supported value that is excluded but has an admissible alternative is listed as "narrowed".

**One predicate table, shared by every component:**
- action applicability and successors (planner and executor);
- relevance, including transitive dependencies: `order` reads the slots that can hold the part under `slot_connector`;
- compatible-state enumeration (the `AgentStateEngine` view);
- P2 query selection, using the operational view;
- validation sampling.

**Planner change.** A prerequisite that reads a field missing from a compatible state (conflicted or never described) is now unknown. In 1.9.x, `order` treated a missing stock field as "not on hand" and a missing slot as "not installed".

**History is untouched.** The per-field historical reconstruction (engine v0.3) is unchanged. The operational result is a separate layer.

**Repair parity** (pre-run validation, check 8):
- The strict contract reproduces 501 of 504 frozen trajectories: 216 from 1.9.0/1.9.1 and 288 from 1.10.0, including real extractions.
- The 3 changed trajectories are `goaltr-del-corrected-0` goal A, text channel, P0/P1/P2. The repair excluded the "carried by you" option for the unrelated crate, so all three now plan "here" and succeed: utilities 0/−1/0 become 7/6/7.
- This is a versioned repair, not a change to the 1.10.0 results.

## Part 2: the authority rule
**Strict (control):** the operational view of the log under contract v1. A verified–verified conflict stays a conflict after a sensor reading.

**Scoped (treatment): SCOPED-CURRENT-OBSERVATION-v1** (`recovery.py`).
- **Where receipts live.** Each sensor receipt records sensor ID, context, request, field, measurement time, reception time and value. Receipts go to a sensor ledger that only the sensor service writes.
- **The log is unchanged.** As before, the same measurement is also ingested into the log as the verified report q1, identically in both arms.
- **When a receipt anchors a field.** A receipt anchors a queried field for the current pre-action decision only if all of these hold:
  - its sensor is registered as a current-state authority for this context;
  - its context matches and its request names the field;
  - it was measured at or after the decision time (the declared stable interval) and received by the decision;
  - no evidence about the field is later than the measurement;
  - no action of yours has occurred;
  - every qualifying receipt agrees (equal-time contradictions stay conflicted, with no recency rule);
  - the value is admissible.
- **What an anchored field changes.** It takes the measured value in the operational projection only, and is then no longer conflicted, incomplete or unknown for this decision.
- **What the rule never does:**
  - edit the log or the historical reconstruction (conflicts and culprits are kept);
  - certify or suspend an extracted report;
  - create an event;
  - change an earlier-information view;
  - touch an unqueried field, another context, or any later state (later states come from action effects only).
- **Records kept.** The projection records rule, version, anchors (receipt IDs, measurement time, validity scope, historical status) and refused receipts with reasons.

**Matching:** one engine log, one P2 query request and one set of receipts per (world, goal, channel). Both contracts decide from them. Queries are selected before any receipt exists, from the strict operational view.

**No-model fixtures** (`tests/test_deprec.py`):
- the observed cross-goal case, both synthetic and the real 1.10.0 extraction;
- unsupported carrying;
- take/put sequences and one-item capacity;
- initial-state consistency;
- the connector invariant and transitive `order` relevance;
- absent-field reads;
- refusal of the view after an action;
- a conflict recovered while its history is kept;
- structured and perfect extraction unchanged by the rule;
- a query-free, coherent wrong verified extraction left untouched;
- refused receipts: stale, other-context, unregistered sensor, unrequested field, before the stable interval, contradictory equal-time, inadmissible value, and text claiming to be a sensor;
- an incomplete field anchored in the projection only.

Inspected 1.10.0 failures are used as development fixtures only.

## Unchanged
- **Model and extraction:**
  - model Qwen3-8B rev b968826d…, bf16, thinking off, greedy decoding, cap 256 tokens, no retry;
  - the extraction prompt and adapter v1;
  - no reinterpretation call, no arrival-specific wording and no source-based reinterpretation.
- **Decision setup:**
  - action rules and candidate menus (`goals.candidate_plans`);
  - the sensor's format, reliability, cost (1), delay (1) and budget (2);
  - the stable-world declaration;
  - the planner rule;
  - utility U = 10·success − action cost − 3·invalid − 1·fact queried;
  - P2's rule, applied to the operational view.

## Worlds (committed before any output)
- **Pools:** `deprec` (base seed 20261120; 8 draws rejected, all "no admissible m2 for goal B") and smoke `deprecsmoke` (4 disjoint worlds, 1 rejected draw).
- **Generator:** the same as the deferred-goal transfer study, unchanged:
  - A types 2,2,2,2,2,1,1 per domain;
  - B types b_changed 4, b_delayed 2, b_prov_false 2, b_prov_true 1, b_unresolved 2, b_corrected 1 per domain;
  - each goal clone isolated.
- **No selection on outputs.** No world was chosen for how its model responses turn out.
- **Hashes:**
  - calls `229f42ec…`, episodes `2a916103…`, gold `01c7d680…`;
  - smoke calls `db8196df…`.

## Matrix
- **Main extraction:** 24 worlds × 6 reports = **144 calls**, with no goal, shared by every clone.
- **Trajectories:** 24 worlds × 2 goals × 2 channels × 2 contracts, P2 only = **192**.
- **Smoke:** 24 calls, not pooled.
- **Ceiling:** 168 model calls before infrastructure retries.

## Known before outputs (no model)
- **Pre-run validation** (`phase0/VALIDATION.md`), 0 failures:
  - 48/48 goals eligible;
  - repaired relevance equals the 1.10.0 rule on 48/48 clones;
  - 180/180 plans agree across the executor and both solvers;
  - truth admissible and complete in 24/24 worlds;
  - declared reads complete in 24/24;
  - dependency sensitivity over the full engine domains: 0 failing contexts; inadmissible samples are reported, not hidden;
  - isolation 24/24.
- **Structured reference, P2:**

  | Goal | Strict | Scoped | Strict–scoped differences |
  |---|---|---|---|
  | A | 91 | 91 | 0 |
  | B | 89 | 89 | 0 |

  Structured histories have no conflict, so the rule has nothing to act on there.
- **Menu-feasible:** A 22/24, B 19/24.
- **Candidate-family coverage gaps** (valid plans outside the menu, kept as menu declines and not counted as infeasible):

  | Goal clone | Independent optimum |
  |---|---|
  | `deprec-del-false_block-1` B | 10 |
  | `deprec-del-no_plan-0` A | 9 |
  | `deprec-ass-no_plan-0` A | 8 |

- **Reach of the rule.** Scoped can differ from strict only when P2 queried a relevant field that is conflicted or incomplete at decision under strict. A settled-looking wrong extraction that P2 never queries is out of reach.

## Outcomes
**PRIMARY:** text channel, P2, the paired per-world utility U_scoped − U_strict, averaged over the two goal clones within each world. The bootstrap is domain-stratified over the 24 worlds, 10,000 resamples, seed 20261105. This is a descriptive development diagnostic.

**Also reported:**
- each goal separately, with each component's mean;
- the structured scoped − strict difference as a negative control, expected exactly 0;
- the text − structured difference under each contract;
- restored opportunities within the menu;
- success, false permissions (invalid attempts), false blocks, and declines by reason (conflict / incomplete / unresolved / absent);
- the exact queries and receipts, and confirmation that they match in both arms;
- operational current-state correctness before and at the decision;
- historical conflicts that remain;
- preservation of earlier-information views, unanchored fields, the log and the historical reconstruction;
- invariant diagnostics found in the text channel;
- extraction quality;
- tokens, latency and engine cost, separately from utility;
- every world and goal where scoped differs from strict, listed.

## Interpretation and stop
**Supported** (an engineered authority rule recovering decisions, under a reliable current-state sensor and a stable world):
- the primary is positive with its interval above 0;
- there are no new false permissions;
- the negative control is 0;
- matching is complete.

**Not supported in these worlds:** the primary is 0 or its interval includes 0. This is reported as is: no rerun, no wording variant, no world selection.

**Rule failure:** any new false permission, any structured-channel change, or any unmatched receipt. This is reported as a failure of the rule.

**What none of these outcomes would show:** learned dynamics, correct interpretation of earlier prose, or recovery under noisy sensors.

**Stop after the report.** Left as separate next choices:
- source-based reinterpretation;
- arrival/correction classification;
- sensor noise;
- delay dynamics;
- candidate expansion;
- new action compositions.
