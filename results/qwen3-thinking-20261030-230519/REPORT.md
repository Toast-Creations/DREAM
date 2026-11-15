# Qwen3-8B thinking pilots: DREAM with thinking, longer thinking, and DREAM 2 learning (exploratory)

Run: `qwen3-thinking-20261030-230519` · Model: Qwen/Qwen3-8B @ b968826d · Source: DREAM 1.3.1 (unmodified copy)
Harness: `Tools/Qwen3-Thinking-Pilots` (copy of the Qwen3-Pilots harness). Development data only. Exploratory: no significance claims.
Requested by David Cook on 2026-10-30. Prepared by Claude Code, 2026-10-31.

## What ran

| Stage | Token budget | Trials | Time | Outcome |
|---|---|---|---|---|
| 1. DREAM, thinking on | 4,096 | 4 / 72 | 11 min | halted: an exploration step hit the cap |
| 2. DREAM, longer thinking | 8,192 | 48 / 72 (tasks 00–03 complete) | 2 h 10 min | halted: the anchor for task 04 looped in its reasoning |
| 3. DREAM 2, thinking on (seed 11, world 1101-0000) | 4,096 | 14 / 14 | 3 h 54 min | complete |

Safety record:
- No welfare pauses in any answer or reasoning text.
- All 14 DREAM 2 adapter rollbacks were verified.
- Peaks: 5.0 GB RAM, 19.2 GB GPU. Offline sandbox throughout.
- Qualification passed: 81/81 tests and all fixtures.

Start-up issues, all before any model call and all recorded in `output/`:
- The container was stopped, so the first attempt never started (folder `attempt-1-container-stopped`).
- The first hub (`qwen3-thinking-20261030-230351`, marked `ABANDONED.json`) lacked `steering-validation-prompts.json`. 1.3.1 needs that file to build the vector, and the harness now copies it.

Decisions after each halt are recorded in `decision-after-dream-think.json` (David) and `decision-after-dream-think-long.json` (Claude, continuing David's earlier choice).

## DREAM: thinking budget

1.3.1 stops the pipeline when the anchor or exploration step runs out of tokens. This is deliberate: empty answers no longer flow into the next step, as they did in the previous pilot.

Token use per step in run 2:

| Step | Median tokens | Max tokens |
|---|---|---|
| anchor | ~1,800 | 2,600 |
| exploration | ~3,100 | 5,500 |
| integration | ~1,700 | 8,192 (hit the cap 2 times) |

- 4,096 is therefore too small for exploration.
- 8,192 was enough for every step except one. The task-04 anchor (temperature 0, i.e. greedy decoding) went into a reasoning loop: "Wait, the user's message is the task…", repeated until the cap, with no answer. Qwen3's guidance warns that greedy decoding with thinking on can repeat endlessly, so a bigger budget would not fix this. Fixing it needs a source change, e.g. a small temperature or a repetition penalty for the anchor. That needs a new revision and David's approval.

Effect of steering (run 2, 48 trials; text similarity of the final answer to the unsteered answer, same task and seed):

| Condition | similarity |
|---|---|
| steering λ 0.05 | 0.12 |
| steering λ 0.1 | 0.11 |
| temperature-only control | 0.15 |

Long reasoned answers differ a lot run to run, and steering changed them about as much as extra randomness did. Integration labels were mostly RETAIN (137), with REJECT 6 and VERIFY 2. These are difference measures, not quality; external scoring is still pending.

Compared with the previous pilot (1,024 tokens): 60 of 72 anchors were empty then. Now the steps complete and the reasoning reaches real answers.

## DREAM 2: learning with thinking on

- Truncation is mostly solved. At 1,024 tokens, 48% of answers hit the cap. At 4,096, at most 1 of 25 answers per trial was truncated.
- The model still doesn't learn the rules. After learning, accuracy on single-rule ("direct") and lookup items is 0 in every condition. It answers with the start number, e.g. "Start with 7, apply opjzjezrd" → 7, where the right answer is −14. Its reasoning says it doesn't know the custom operation.
- Training loss starts much higher with thinking on: 9.7, versus about 3.9 with thinking off. It falls to about 4.0 (rate ×0.5), 1.2 (×1) and 0.05 (×2), so the adapter again memorizes the 12 exposure examples. The higher starting loss suggests the thinking-format mismatch between training targets and generation noted in the previous report.
- Official paired contrast (coupled − learning-only, composition):
  - 0 in three cells;
  - +0.25 at λ 0.1, rate ×1. That is one composition item out of four, on one world and one seed. It is a single-item difference, not evidence of a steering effect. The other three coupled cells, and all controls, stayed at 0.
- Coupled λ 0.05 also got 1 of 3 paraphrase items right (0.33). Again a single item.
- The ×2 "skip reasoning" artifact from last time did not recur as no-answer scoring. The high-plasticity cell had 0 invalid answers and 0 truncations.

## What this suggests (for David's decision; nothing has been changed)

1. **DREAM with thinking:** use at least 8,192 tokens, and fix greedy-anchor looping (small temperature or repetition penalty) in a new recorded revision. Then rerun the full 72 trials.
2. **DREAM 2:** thinking doesn't rescue learning. The bottleneck is still the exposure design (12 examples, memorized), as in the previous pilot. Adding a thinking block to the training targets would make the thinking-on comparison fair.
3. The single +0.25 cell is worth checking on more worlds and seeds before anyone reads it as a signal.

Data:
- `run/results/runs/*`: trial records, plus the incomplete-anchor and incomplete-exploration records.
- `output/supervision/*/events.jsonl`: every prompt, reasoning and answer.
- The official summary was computed on a copy: `output/analysis/runs-copy/dream2-think/*/exploratory-summary.json`.
