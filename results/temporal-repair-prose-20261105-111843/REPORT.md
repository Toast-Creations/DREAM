# Bounded record repair and prose robustness (V1.8.2): report (development only)

## Status
- **Plan:** `design/STUDY-PLAN.md`, frozen before any output (`config/FROZEN-PROTOCOL.json`; budget in `config/MAIN-CONFIG-FROZEN.json`).
- **Source:** 1.8.2 with engine v0.2. Tests 88/88 in the container. Engine v0.2 still has 0 disagreements on all earlier fixtures.
- **Run:** 2026-11-05, 11:20–11:39 America/New_York.
  - Smoke: 18 initial calls and 1 retry, not pooled.
  - Main: **288/288 initial** calls (904 s) and **41 retries** (140 s; the ceiling was 288).
  - No call failed or was truncated, and no infrastructure retries were needed. Nothing was changed after smoke.
- **Setup:** Qwen3-8B rev b968826d…, bf16, thinking off, greedy decoding. One fixed extraction instruction for both surfaces.
- **Histories:** 24 fresh histories (12 delivery, 12 assembly), each with 6 records, 3 checkpoints and 2 action tests per checkpoint. The history is the independent unit.

## Primary outcome: completeness-aware exact state at the final checkpoint
| Surface | no retry | one retry | one retry − no retry |
|---|---|---|---|
| Record lines | 19/24, 0.792 [0.67, 0.92] | 19/24, 0.792 | 0.000 (0 better / 24 equal / 0 worse) |
| Natural prose | 19/24, 0.792 [0.62, 0.92] | 19/24, 0.792 | 0.000 (0/24/0) |
| prose − lines | 0.000 [−0.21, 0.17] (3/18/3) | 0.000 [−0.21, 0.17] (3/18/3) | |
| Structured reference | 24/24 | | |

- **Retry:** **no effect** on the primary outcome on either surface.
- **Prose:** **no measurable degradation** in final state. Lines and prose each lost 5 histories, but not the same 5: each surface was better in 3 histories and worse in 3.

Secondary outcomes:

| Cell | All checkpoints exact | Action verdicts (vs supported state) | Wrongly allowed / blocked vs hidden truth | Unknown kept unknown | Unprocessed records |
|---|---|---|---|---|---|
| structured reference | 72/72 | 144/144 | 3 / 8 | 5/5 | 0 |
| lines, no retry | 57/72 | 124/144 | 6 / 8 | 2/5 | 16 |
| lines, one retry | 57/72 | 124/144 | 6 / 8 | 2/5 | 13 |
| prose, no retry | 61/72 | 132/144 | 3 / 8 | 2/5 | 26 |
| prose, one retry | 63/72 | 136/144 | 3 / 8 | 4/5 | 23 |

- **Verdict differences:**
  - prose − lines: +0.056 [−0.01, 0.14] without retry, and +0.083 [0.00, 0.17] with one retry;
  - retry on prose: +0.028 [0.00, 0.08].
  - All are small and uncertain.
- **Old-policy view** (last accepted values, ignoring incompleteness): 20/24 in every cell. In one history per cell, an old value happened to be right even though evidence about that fact had not been processed. The completeness-aware score doesn't give credit for that.
- **No false certainty:** no cell answered a field "unknown" that the records settle, or gave a definite value for a fact the records leave unknown.
- **What the missing credit consists of:**
  - Lines: 10 incomplete fields.
  - Prose: 8 incomplete fields without retry and 6 with it, plus 3 wrong definite values; none were outdated.

## Record-level results (all 144 records per cell)
| Cell | Exact | Accepted | Accepted but wrong | Correct but rejected (cascade) | Unprocessed |
|---|---|---|---|---|---|
| lines, no retry | 130 | 128 | 5 | 7 | 16 |
| lines, one retry | 133 | 131 | 4 | 6 | 13 |
| prose, no retry | 88 | 118 | 36 | 6 | 26 |
| prose, one retry | 90 | 121 | 36 | 5 | 23 |

- **Normaliser:** N3 (a correction's redundant `event_at`) fired 8 times, all on prose, and fixed the milestone-2 convention problem without a model call. Corrections were 8/8 exact on both surfaces. No other rule fired.
- **The 41 retries (one-retry branch):** none produced an accepted wrong record.
  - **Fixed (5):** all 3 lines observations whose time came back as null; 1 prose value written as "not on hand" instead of "no"; and 1 prose kind error.
  - **Correct record re-sent, rejected again (11: 6 lines, 5 prose):** these were correct records rejected because an earlier wrong record had been accepted. The retry correctly repeated the same record, and it was rejected again. Feedback can't fix the branch's earlier error, and the policy correctly forbids rewriting the source to fit it.
  - **Same mistake repeated (25):** the model made the same semantic error again: 20 wrong kinds, including "delivered to you" read as an initial statement, and 4 unrecorded-result events missing their `from` value.
  - **Rejected for a different rule (1).**
  - Total: 5 + 11 + 25 + 1 = 41.
- **Main semantic errors, both surfaces:**
  1. **"Part X was delivered to you" read as an initial statement** rather than a change (lines 3, prose 13 among change records). In prose, 4 of these were accepted as wrong; the rest were rejected as inconsistent, starting a cascade.
  2. **A multi-fact initial record transcribed as a single observation** (lines 4, accepted). This drops facts; prose had only 1 such initial-record error.
  3. **An unrecorded-result event without its `from` value** (2 per surface).
- **Prose-specific:** 37 of 50 prose observations came back as kind `initial` with one fact; 29 were accepted. When the entity had never been mentioned before (28 cases, exploratory), this has the same effect on the engine state as an observation. That's why prose final states didn't suffer.
  - The frozen scorer counts it as a kind error, so **record exactness understates prose state fidelity**.
  - When the entity already had a history, the same mistake made the record inconsistent (8 rejected), with cascades.

## Reading (the plan's rules)
- **Retry, conventions:** bounded retry fixed conventions without introducing a single accepted wrong record. So did the deterministic N3 rule, without any call.
- **Retry, state:** it did not change final state. The errors that matter are **semantic** (event vs statement, a dropped `from`, multi-fact compression) and **cascade** rejections. One rule-only retry can't fix either.
  - Following the plan, the next step is the concrete semantic errors, not more retries.
- **Prose vs lines:** less templated prose did not degrade final state in this sample. Record exactness did fall (88 vs 130), but most of that is an equivalent kind relabelling. The interval for prose − lines on final state, [−0.21, 0.17], is wide.
- **Supported state vs hidden truth:** even the reference allowed 3 actions that are illegal in the true world and blocked 8 that are legal. These come from provisional reports and unrecorded outcomes; they are not interpretation errors. Closing that gap needs a separately specified observation or execution policy, which this study didn't change.
- **Accepted-but-wrong records did not rise with retry** (lines 5 → 4, prose 36 → 36). Acceptance rose slightly, so higher acceptance here was not paid for with wrong repairs.

## Not supported
- Equal-cost claims: retries cost 41 calls (3,999 output tokens, 122 s) on top of the 288 initial calls.
- Transfer to new action types.
- Generalising beyond these two templates and this prose generator.
- Treating validator acceptance as semantic correctness.

## Stop
I stopped after this report, as the plan requires. The next decision is yours: targeted semantic handling (event vs statement, multi-fact records), or a policy for the gap between supported state and the hidden truth.

## Artifacts
- **Analysis:** `analysis-prose/ANALYSIS.json`, `TABLES.md`, `records.jsonl` (initial/retry raw replies, normalisation log, comparisons, codes) and `checkpoints.jsonl`; smoke in `analysis-prosesmoke/`.
- **Raw replies:**
  - `stages/main/calls/` (initial);
  - `stages/main-retry/calls/` (retries, each with its exact prompt and that prompt's hash);
  - `stages/main-retry/RETRIES.json`.
- **Inputs:** `data/`, including both renderings of every record in `prose-histories.jsonl`.
- **Re-score:** `python3 -B scripts/repair_analyze.py --hub HUB --set prose --initial-stage main --retry-stage main-retry`
