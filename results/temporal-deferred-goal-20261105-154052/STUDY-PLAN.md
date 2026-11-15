# Deferred-goal transfer (V1.10.0): frozen plan

- **Brief:** `DEFERRED-GOAL-TRANSFER-BRIEF.md` (copy in `design/`). This plan is hashed in `config/FROZEN-PROTOCOL.json` before any model output. The main budget is set after smoke. Development only.
- **Freeze of 1.9.1:** `config/FREEZE-1.9.1.json` lists 233 files with their hashes, at git commit `ee51aa8` in the private repo `dacook-blip/DREAM-code`.
- **Source:** `Code/DREAM-project-1.10.0-deferred-goal-20261105`, which is 1.9.1 plus:
  - `src/tempo/goals.py` and `src/tempo/transfer.py`;
  - `scripts/goaltr_{generate,validate,analyze}.py`;
  - `tests/test_goaltr.py`.

  `policy.py`, `text_channel.py`, the extraction prompt, the N0–N3 normaliser, adapter v1, engine v0.3 and both renderers are byte-unchanged. Tests: 120/120 in the container (the 110 temporal tests plus 10 new).

## Question
Does the stored context stay usable when a different public goal makes other stored facts decision-relevant? The extractor never sees a goal. Each goal is revealed afterwards, in isolated copies of the same stored state.

## Unchanged from the text-policy study
- **Model:** Qwen3-8B rev b968826d…, bf16, thinking off, greedy decoding, extraction cap 256 tokens, no retry.
- **Extraction pipeline:** the same extraction prompt construction and the same adapter.
- **Contract and policies:** contract v1 and engine v0.3. Verified–verified conflicts stay unresolved: there is no newest-verified-wins rule and no gold repair.
- **Sensor:** the same structured sensor (cost 1 per fact, delay 1, at most 2 facts).
- **World and decisions:** a stable world after the decision, the same action definitions, and the same planner rule (cheapest candidate plan guaranteed in every compatible state, otherwise decline). One attempt per goal clone.
- **Utility:** U = 10·success − action cost − 3·invalid − 1·fact queried.
- **Policies:** P0, P1 and P2 with unchanged rules.

## What generalises (common to all channels and policies)
1. **Goal and candidate plans** (`goals.candidate_plans`). These are the 1.9.x families, parameterised by the goal.
   - **Delivery** ("crate E rests at G"): here; b_cheap; b_dear; and the empty plan "already".
   - **Assembly** ("slot S holds a part rated ≥ m", with the plans' part p): install; remove then install; order then install (only for the orderable part); and "already".
   - For goal A these are exactly the world's 1.9.x plans plus "already".
2. **Relevance from the public goal** (`goals.relevant_fields`). This replaces the old favoured-field lookup. A field is relevant if a candidate plan's step prerequisite, or the goal test, reads it before the plan itself has definitely written it.
   - The read and write tables follow the printed action rules.
   - Your position and your hands belong to the agent and are fixed public facts, so they are excluded.
   - Slot values come from the public registry.
   - Nothing here reads gold, hidden truth, extractions or role labels.
   - On the committed 1.9.0 and 1.9.1 episodes, this reproduces the old relevant fields and **all 216 trajectories exactly**, including 1.9.1's real text extractions.

   This is still relevance supplied by the program, not learned goal understanding.

## Worlds, goals and histories (24 worlds, 12 per domain; committed before any output)
- **Pool and inputs:** pool `goaltr`, base seed 20261113. There were 12 rejected draws, all because no assembly B threshold was admissible. The world generator is `worlds.make_world`, unchanged. Each history has six reports, received by time 12.
- **Goal A** keeps the familiar role, with the 1.9.x types per domain allocated as before (2,2,2,2,2,1,1).
  - Delivery: crate EA rests at G. EA is crate X in 6 worlds and crate Y in 6 (counterbalanced).
  - Assembly: slot T, part G (orderable).
  - A's base reports name only A's facts, plus crate Z in delivery.
- **Goal B** is an independent, fully specified target whose facts are stored the way 1.9.x stored padding: an observation followed by events by other workers.
  - **Delivery:** the other crate rests at G.
  - **Assembly:** slot S2 holds a part rated ≥ m2, with part D (not orderable). m2 is drawn so that D qualifies and exactly one of S2's other parts does.
  - **B types per domain:**

    | B type | Count | What it is |
    |---|---|---|
    | b_changed | 4 | outcome classes: here, b, already, no plan |
    | b_delayed | 2 | a verified report about an earlier time arrives after a later event |
    | b_prov_false | 2 | the target's only report is a provisional observation, and it is wrong |
    | b_prov_true | 1 | the same, but correct |
    | b_unresolved | 2 | the last event's result was not recorded |
    | b_corrected | 1 | a provisional observation is withdrawn by a verified correction |

  - The A and B types are paired by a seeded permutation.
  - **Declared limit:** the frozen renderers have no wording for a provisional *event*, so B's provisional cases are provisional observations.
- **Goals are fixed by the specification and generator before any extraction exists.** No goal was chosen after seeing outputs.
- **Exposure of the stored facts** (gold records, 144 in total):
  - 34 touch A's relevant facts: 24 initial reports, 4 events, 4 unrecorded results, 2 corrections.
  - 60 touch B's relevant facts: 40 observations (8 provisional), 14 verified events, 4 unrecorded results, 2 corrections.
  - 50 touch neither.

## Matrix
- **Extraction:** 24 worlds × 6 reports = **144 extraction calls**, made without a goal and shared by every goal and policy clone.
- **Trajectories:** 24 worlds × 2 goals × 2 channels (structured, text) × 3 policies = **288**.
- **Smoke:** 4 disjoint worlds (pool `goaltrsmoke`), 24 calls, not pooled.
- **Model-call ceiling:** 168 before infrastructure retries; the main ceiling is set from smoke.
- **No sequential execution:** A and B are never executed one after the other in a shared world. Each starts from an isolated copy of the same pre-decision state.

## Pre-run validation (`phase0/VALIDATION.{json,md}`, before any model call)
1. **Goal eligibility:** 48/48 goals fully specified. A and B have disjoint relevant fields, and B's threshold admits exactly one other part.
2. **Plan legality:** 180 candidate plans checked on the true states. Engine v0.3, solver 1 (`ectx.world`) and solver 2 (`ectx.keycheck`) agree on validity and cost for all 180.
3. **Optimality and coverage:** the cheapest valid candidate equals both solvers' optimum, except for **3 declared family gaps**:
   - `del-unresolved-0|B`: the item is at C;
   - `del-no_plan-0|A`: the item is at C;
   - `ass-no_plan-0|A`: the slot holds a low-rated part and G is not on hand.

   These are kept visible as no-plan.
4. **Dependency:** 300 sampled states per goal context. Varying a non-relevant field never changes any candidate's outcome. Every relevant field does change an outcome in some state (72/72).
5. **Isolation:** the extraction packets rebuilt from each goal clone are byte-identical to the committed calls (24/24). No prompt contains a goal statement or a role label.
6. **Structured integrity:** the earlier-information view is preserved in 144/144 trajectories. Planning never changes the log (asserted). The sensor stays within budget. Feasible worlds: A 22/24, B 21/24.
7. **Original-goal parity:** 216/216 trajectories identical.

**Structured reference** (known before outputs; no model involved), utility totals over 24 worlds:

| Goal | P0 | P1 | P2 |
|---|---|---|---|
| A | 42 | 87 | 100 |
| B | 79 | 85 | 111 |

## Outcomes
**PRIMARY:** the change in P2's text-interface loss across goals, paired per world:

`(U_text,B − U_structured,B) − (U_text,A − U_structured,A)`

More negative means the text channel loses more when the other stored facts become relevant. Every component mean is reported. The bootstrap is domain-stratified over the 24 worlds, 10,000 resamples, seed 20261105. This is a descriptive development diagnostic, not a powered equivalence test.

**Also reported, per goal:**
- the same loss change for P0 and P1;
- P2 − P0, P2 − P1 and P1 − P0 in each channel;
- text − structured for each policy;
- B − A within channel;
- success, feasibility, invalid attempts, false blocks, missed opportunities, declines;
- facts queried and budget exhaustion;
- decisions with a conflicted, incomplete or unknown relevant fact;
- whether the goal-relevant state was correct before and at the decision, and whether it was complete before the decision;
- agreement on the whole declared state between text and structured.

**Extraction:**
- meaning-preserved records and coverage;
- source-status errors versus semantic errors that carry a correct status;
- unprocessed codes;
- which erroneous records touch A's relevant facts, B's, or neither.

**Every text trajectory that differs from its structured clone is listed by goal and tagged:** conflict, incomplete, provisional flag, status, queries, wrong belief, invalid attempt.

Tokens, latency and engine cost are reported separately from utility. Primary outcomes are never conditioned on correct extraction or on the action taken. No counterfactual gold-repair analysis enters this report.

## Known before outputs
- **A wrongly extracted verified claim looks settled.** P2 won't query it unless it creates a conflict, an unknown or an incomplete fact. P1's sensor reading can expose a contradiction, but it can't resolve it under the frozen contract.
- **An event read as a state** (the 1.9.1 failure mode) contradicts an earlier verified observation of the same fact with no recorded change between them. That gives a verified–verified conflict. Under the goal that depends on the fact, every policy then declines. Under the other goal, nothing changes. A no-model test checks this.
- **A no-plan world in the structured reference is not an extraction failure.**

## Interpretation and stop
- **If errors that didn't matter under A become consequential under B** (the primary is clearly negative, and the text − structured differences concentrate in B), the next target is interpretation recovery and current-state authority, using the preserved raw evidence.
- **If transfer holds**, the next steps are an observation cost/delay challenge or new action compositions.
- **Either way, stop after this report.** There will be no repairs on these worlds, no conflict-authority rule, no wording patch, and no noisy sensor or changing world.
