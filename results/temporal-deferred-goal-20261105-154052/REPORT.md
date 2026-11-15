# Does stored context stay usable when the goal changes? (V1.10.0): report (development only)

## Status
- **Brief and plan:** brief `DEFERRED-GOAL-TRANSFER-BRIEF.md`; plan `design/STUDY-PLAN.md`, frozen before any output (`config/FROZEN-PROTOCOL.json`).
- **Freeze of 1.9.1:** `config/FREEZE-1.9.1.json` (233 files, git `ee51aa8`).
- **Source and tests:** source 1.10.0. Tests 121/121 in the container (temporal modules).
- **Pre-run validation:** `phase0/`, 0 failures. Goal A reproduces all 216 committed 1.9.0/1.9.1 trajectories exactly.
- **Ran 2026-11-05:**
  - Smoke: 24/24 calls at 15:43, not pooled.
  - Main: 144/144 calls, 15:45–15:53 (482 s; 460 s generation; 15,348 output tokens).
  - No call failed or was truncated, and there were no infrastructure retries. The GPU was free apart from desktop apps.
- **Amendment S1 (after smoke, before main):** a `.get` lookup, analysis only. When the text view never described a relevant fact, the `unresolved_decline` flag raised KeyError. Model inputs and all decision values are unchanged. The amendment is recorded in `config/MAIN-CONFIG-FROZEN.json` with a regression test.
- **Sample:** 24 worlds × 2 goals × 2 channels × 3 policies = 288 trajectories, sharing 144 extraction calls that never saw a goal. The independent units are the **24 worlds**.

## Main result
| Policy | Text loss, goal A | Text loss, goal B | **B − A** (paired per world) |
|---|---|---|---|
| P0 accepted | −0.58 [−1.46, 0.00] | −0.83 [−1.92, 0.04] | −0.25 [−1.33, 0.92] (1 / 21 / 2) |
| P1 always | −0.58 [−1.46, 0.00] | −1.29 [−2.33, −0.33] | −0.71 [−2.00, 0.29] (1 / 20 / 3) |
| **P2 selective (primary)** | −0.63 [−1.58, 0.00] | **−1.46 [−2.62, −0.38]** | **−0.83 [−2.17, 0.25] (1 / 19 / 4)** |

Text loss = U_text − U_structured. P2's components: A structured 4.17, A text 3.54, B structured 4.63, B text 3.17. The last column gives worlds better / equal / worse.

**The text channel lost more under the alternate goal, but the paired difference is not clearly different from zero.**
- P2's text loss more than doubled, from −0.63 under A to −1.46 under B.
- Text trajectories differed from their structured clones in 6 worlds under B, against 2 under A.
- The primary contrast, −0.83, has a 95% interval of [−2.17, +0.25] across 24 worlds. Four worlds were worse and one was better.

The direction supports the concern in the brief. The size is not established.

| Cell (24 worlds) | Utility | Success | Invalid | False blocks | Queried | Conflict / incomplete at decision | Relevant state correct before |
|---|---|---|---|---|---|---|---|
| A structured P0 / P1 / P2 | 1.75 / 3.63 / 4.17 | 10 / 22 / 22 | 4 / 0 / 0 | 8 / 0 / 0 | 0 / 36 / 23 | 0 / 0 | 12 |
| A text P0 / P1 / P2 | 1.17 / 3.04 / 3.54 | 8 / 20 / 20 | 4 / 0 / 0 | 10 / 2 / 2 | 0 / 36 / 24 | 1 / 0 | 11 |
| B structured P0 / P1 / P2 | 3.29 / 3.54 / 4.63 | 14 / 21 / 21 | 2 / 0 / 0 | 6 / 0 / 0 | 0 / 36 / 10 | 0 / 0 | 16 |
| B text P0 / P1 / P2 | 2.46 / 2.25 / 3.17 | 11 / 17 / 17 | 1 / 0 / 0 | 10 / 4 / 4 | 0 / 36 / 14 | 4 / 2 | 13 |

Feasible worlds: A 22/24, B 21/24.

**Selective verification under each goal (text channel):**
- **P2 − P1:** +0.50 [0.25, 0.75] under A and +0.92 [0.71, 1.12] under B. P2 never did worse than P1.
- **P2 − P0:** +2.38 [0.92, 3.88] under A, but only +0.71 [−0.17, 1.71] under B. The structured reference has +1.33 [0.46, 2.29] under B.
- **Why the B advantage over P0 shrinks:** under B most of the text loss comes from verified-looking errors. These are settled-looking claims, which P2 does not select for checking.

**Integrity:**
- The earlier-information view was preserved in every trajectory.
- No decision was taken with budget exhausted, and no text-channel decision produced an invalid attempt that the structured clone avoided.
- Whole declared-state agreement between text and structured before any query: 91.8% of registry fields; 17/24 worlds fully equal.

## Where the language interface lost
**Extraction (144 records):**
- 142 accepted, 133 meaning-preserving, mean coverage 0.938, 0 wrong statuses.
- All 11 errors kept a correct source status. These are semantic errors that inherit a correct "verified" or "provisional" label.

| Report class | Errors / records |
|---|---|
| **"part … was delivered to you / arrived for you" (event)** | **7 / 8** |
| Unrecorded-result event (option values written as "on hand" / "not on hand", rejected by the adapter) | 1 / 8 |
| Initial report with an invented extra fact | 2 / 24 |
| Observation read as a correction (unmapped) | 1 / 72 |
| Crate moved by another worker | 0 / 22 |
| "Taken by another team" | 0 / 4 (in 1.9.1, 6 were read as corrections) |
| Other observations, corrections, slot events | 0 |

**Which errors matter depends on the goal:**
- Of the 11 erroneous records, 1 touches only A's relevant facts, 5 only B's, 2 both, and 3 neither.
- The arrival/delivery class is almost always misread, and the B design puts that event on decision-relevant facts more often. Under A it appears on a relevant fact only in the verified_settled assembly worlds.
- **This concentrates the loss in assembly.** P2 utility totals, structured → text:

  | Domain | Goal A | Goal B |
  |---|---|---|
  | Assembly | 55 → 47 | 75 → 41 |
  | Delivery | 45 → 38 | 36 → 35 |

**Every world where text and structured differ:**

| World | Goal | Effect | Cause |
|---|---|---|---|
| ass-provisional_correct-1 | B | all three policies decline (P2 −9) | "arrived for you" read as a verified state, which conflicts with the earlier verified "not on hand" (verified–verified conflict on D's stock) |
| ass-corrected-0 | B | the same (P2 −9) | the same |
| ass-verified_settled-0 | B **and** A | the same, under both goals (P2 −8 under each) | the same error on D's stock (B) **and** on G's stock (A). One history, two misread deliveries. |
| ass-unresolved-0 | B | P1 and P2 decline (P2 −8); P0 had declined in both channels | unrecorded-result options not mapped, so the report is unprocessed: the field is incomplete and in conflict, and the sensor can't settle it under the contract |
| del-false_block-0 | B | P2 queries one extra fact and still succeeds (−1) | an observation read as a correction is unmapped, leaving the field incomplete, so P2 checks it |
| del-corrected-0 | **A** | all three policies decline (P2 −7) | **cross-goal interference** (below) |
| del-corrected-0 | B | P0 declines instead of making an invalid attempt (**+3**, the one "better" world) | the same invented fact made B's crate unknown |

**Conflict behaviour (unchanged contract).** Every misread delivery became a visible verified–verified conflict. The frozen contract does not let a fresh sensor reading override it, so P1 and P2 paid for queries and then declined. None of these errors caused an invalid attempt: the system lost opportunities, not safety. A current-state authority rule could plausibly have recovered the three delivery-conflict worlds under B (and the one under A) for P1 and P2. That is untested here and deliberately not part of this study.

**New finding: a hidden dependency the declared relevance procedure misses.**
- In `del-corrected-0`, the extractor added a provisional claim about goal B's crate (at time 0) to an initial report that never mentioned it. That claim contradicts a later provisional report, so both are suspended. The crate's location becomes unknown over its whole domain, including "carried by you".
- The frozen engine works out "hands empty" from crate locations, so every `take` becomes unresolved and goal A declines.
- The declared dependency procedure treats your hands as agent-owned and fixed by the public statement "you start with empty hands", so it did not list the other crate. P2 therefore didn't query it, and the pre-run sensitivity check excluded "carried by you" from its sampled values for the same reason.
- The public-domain argument is sound. **The engine does not encode it.** An unrelated fact's corrupted state can block the active goal through a prerequisite that relevance treats as settled. Structured records never produce this case. It is reported as found, not repaired.

## Reading (plan rules)
- **Supported, under the stated assumptions:**
  - The stored context mostly transfers: under the alternate goal, 18 of 24 worlds were identical to their structured clones.
  - The text-interface loss was larger under the alternate goal (P2: −1.46 vs −0.63).
  - The paired increase (−0.83 [−2.17, 0.25]) is not established on 24 worlds.
  - Selective verification still beat always-verify under both goals. Its advantage over acting on accepted evidence fell under B, because most B losses were verified-looking errors that no status-based trigger selects.
  - This is still relevance supplied by the program on fixed families, with a reliable sensor and a stable world.
- **Where the remaining loss sits:**
  - one wording class, delivery/arrival events read as states (7 of 8 misread), which becomes consequential whenever a goal depends on that part's stock;
  - one unmapped unrecorded-result report;
  - one invented fact that reached the active goal through the engine's derived "hands empty".
  - None of the loss came from query selection or from mishandling sensor evidence.
- **By the plan's rule, the next target is interpretation recovery and current-state authority**, using the preserved raw evidence. Three things are separate decisions, none started:
  1. Targeted handling of the delivery/arrival event class. The raw text is preserved for re-interpretation.
  2. A scoped current-state authority rule: a designated fresh verified reading establishes a current value, without erasing the historical conflict. It needs its own specification and test.
  3. Making the agent-owned "hands empty" an explicit fixed fact in the engine, or including the facts it derives from in the dependency set. That would be a contract or engine change with its own parity test.

## Limits
- **Sample:** 24 worlds. The primary is descriptive, not a powered test.
- **Design choices:** the B types and their event mix are design choices. B places the delivery event on relevant facts more often than A does, so the size of the B loss partly reflects which event classes the alternate goal's facts carry. This is the mechanism, not a general rate.
- **Provisional events:** the frozen renderers have no provisional-event wording, so B's provisional cases are observations.
- **Coverage gaps:** 3 declared gaps are kept as no-plan. They are the same in both channels.

## Artifacts
- **Analysis:** `analysis-goaltr/{trajectories.jsonl, extraction.jsonl, ANALYSIS.json, TABLES.md}`; smoke in `analysis-goaltrsmoke/`.
- **Raw replies:** `stages/{smoke,main}/calls/`.
- **Inputs:** `data/` (episodes with goals, prose texts, calls, gold, commitments).
- **Validation:** `phase0/VALIDATION.{json,md}`.
- **Re-score:** `python3 -B scripts/goaltr_analyze.py --hub HUB --set goaltr --stage main`
