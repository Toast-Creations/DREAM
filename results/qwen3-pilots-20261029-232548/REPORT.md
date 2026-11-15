# Qwen3-8B DREAM pilots — thinking off vs on (exploratory)

Run: `qwen3-pilots-20261029-232548` · Model: Qwen/Qwen3-8B @ b968826d · Source: DREAM 1.1.3 (thinking control)
Development data only. Exploratory: no significance claims. Prepared by Claude Code for David Cook, 2026-10-30.

## What ran

| Stage | Trials | Time | Outcome |
|---|---|---|---|
| DREAM, thinking off | 72 / 72 | ~5 min | complete |
| DREAM 2, thinking off | 433 / 504 (seeds 11, 22 full; seed 33 partial) | 3 h | stopped by its 3-hour time budget (planned) |
| DREAM, thinking on | 72 / 72 | ~56 min | complete |
| DREAM 2, thinking on (slice: seed 11, world 1101-0000) | 14 / 14 | ~2 h 14 min | complete, after an input amendment (below) |

Safety record: no welfare pauses, in either answers or reasoning text. Every DREAM 2 adapter reset was verified (447 of 447). Peak use was 5.5 GB RAM and 18.4 GB GPU, within limits. The worker ran offline in the sandbox throughout.

Amendment: the first DREAM 2 thinking-on launch refused to start. It made no model calls. The cause was that `max_worlds: 1` is a cap, not a selector. Its data file was repointed to a one-world copy holding the same first world that thinking-off ran with seed 11. This is recorded in `amendment-dream2-on.json`, and nothing else changed.

## DREAM 2 — does learning (and steering) improve composition?

The model learns the training examples but not the rules behind them.
- Training loss falls from about 3.9 to about 0.5 (learning-rate ×0.5) or 0.0 (×1 and ×2), so the adapter memorizes the 12 exposure examples.
- After learning, accuracy on simple single-rule questions is only 2–8%. On paraphrases and lookups it is 0%.
- Before learning, the model answers with the start number or a sign flip, e.g. "7 → {"answer": 14}", where the correct answer is −14.

Composition gain (after minus before, thinking off, mean over trials):

| Condition | gain |
|---|---|
| frozen, exploration-only (steering, no learning) | 0.000 |
| learning only, rate ×0.5 / ×1 | +0.032 / 0.000 |
| steering + learning (coupled), λ 0.05 or 0.1, rate ×0.5 | +0.048 |
| coupled, rate ×1 | 0.000 |
| high learning rate ×2 | 0.000 |
| pre-exposure controls | same as learning-only |

- Every nonzero gain came from a single world (1101-0002) at learning rate ×0.5. It appeared in learning-only and pre-exposure controls too, so it reflects learning in that world, not steering.
- Official paired contrast (coupled − learning-only, world bootstrap): +0.014 at rate ×0.5, interval [0.000, 0.042]; 0.000 at rate ×1. That is effectively no steering effect, the same as the 0.5B pilot.

With thinking on (the 14-trial slice): composition stayed at 0 before and after in every condition, and the official contrast was 0.000.
- The model doesn't know the invented operations, because the rules are never in the prompt; they can only come from learning. So it reasons at length, e.g. "I don't have access to that specific adapter's details…".
- In 48% of answers it hit the 1,024-token limit before answering. Those answers count as wrong.
- High-learning-rate artifact: at rate ×2 the adapter taught the model to skip reasoning entirely. It then answered after only 6 tokens, without closing its thinking tag. The code marks such answers as "no answer", so that cell scored 0% overall. The training targets contain no thinking block, which is the asymmetry noted in the plan. This is a scoring artifact to fix, not a real collapse.
- On the same world and seed with thinking off, before/after scores were identical to the thinking-on slice apart from small contradiction/scope/anchor differences. So thinking did not help.

## DREAM — does steering change the 3-step pipeline's answers?

DREAM has no automatic scorer; external verification and human ratings are still pending. So these are measures of how much the outputs differ, not of quality.
- **Thinking off:** every step hit the 64-token limit, so all answers are cut off mid-sentence. The final answers do change with steering. Their text similarity to the unsteered run was 0.66 at λ 0.05 and 0.52 at λ 0.1, versus 0.40 for the temperature-only control. In other words, steering perturbed outputs less than random sampling did.
- **Thinking on:** the 1,024-token limit dominated.
  - 60 of 72 first-step ("anchor") answers ran out of tokens while still reasoning, so they were empty, as were 51 of 72 exploratory steps.
  - The final step was then often asked to judge an empty candidate, and answered "REJECT, the candidate is empty".
  - The many "identical" outputs across conditions (11–13 of 18) are mostly these identical empty-input rejections, not a real lack of steering effect.
- The reasoning itself looked competent; e.g. it correctly sets up even = 2k for the even-sum proof. It just needed more room.

## Comparison with the 0.5B pilot

- Pipeline reliability: the same. Everything ran, every reset was verified, and the records are complete.
- The steering effect on DREAM 2 learning is the same too: none (0.5B: 0.0; 8B: +0.014 with an interval touching 0).
- The 8B model formats perfectly (0% invalid with thinking off), which the 0.5B couldn't. That removes formatting as an excuse: the real limit is that the learning step memorizes examples instead of learning rules.

## What this suggests (for David's decision; nothing has been changed)

1. DREAM 2 learning design: with 12 examples, one step each, the adapter memorizes rather than generalizes. More varied exposure examples or held-out checks during learning would test whether rules can be learned at all. Until then, steering has nothing to amplify.
2. Thinking-on token budget: 1,024 is too small. The project caps it at 1,024 in `config.py`, so raising it needs a new recorded source revision (e.g. 4,096). Empty answers should also stop the pipeline rather than flow into the next step.
3. Thinking detection: an answer that closes without `</think>` but is short (well under the cap) should be scored as an answer, not as "no answer". Alternatively, the training targets could include an empty thinking block.
4. DREAM thinking-off: 64 tokens truncates every step. A meaningful quality comparison needs a larger budget and the pending external scoring.

Data: `run/results/runs/*` (trial records), `output/supervision/*/events.jsonl` (every prompt, reasoning and answer), and the official summaries computed on copies (originals untouched).
