# Baseline: DREAM, thinking on, 8,192 tokens, sampled anchor (V1.3.2)

Run `qwen3-thinking-20261031-083543`, Qwen3-8B @ b968826d. Original six development tasks, 3 seeds, 4 cells. Development data only; exploratory.
Requested by David Cook ("Fix the anchor loop and rerun DREAM at 8192"). Kept as the baseline for 1.3.3 ("Having a baseline is important").

## What ran

- **72 / 72 trials complete**, in 3 h 6 min. No halts and no welfare pauses.
- Peaks: 5.1 GB RAM, 19.7 GB GPU.

## Results

**Anchor fix worked.** No anchor hit the cap. The task-04 anchor that looped in 1.3.1 finished normally.

Token use per step:

| Step | Median | Max | Hit the cap |
|---|---|---|---|
| anchor | 1,490 | 3,800 | 0 |
| exploration | 2,645 | 5,760 | 0 |
| integration | 1,708 | 8,192 | 4 |

**Integration still loops.** At temperature 0.3, 4 integrations ran to the cap with empty answers:
- task 02, temperature control;
- task 03, λ 0.05;
- task 04, λ 0 (seeds 22 and 33).

The loop-guard replay classed 3 of them as reasoning loops. 1.3.3 samples integration with the Qwen3 thinking preset and adds the loop guard.

**Arithmetic control:** 11 of 12 answers give 43. The twelfth is one of the empty capped integrations, not a wrong sum.

**Steering vs randomness.** Text similarity of each final answer to the unsteered one (same task and seed):

| Condition | similarity |
|---|---|
| λ 0.05 | 0.12 |
| λ 0.1 | 0.12 |
| temperature control | 0.11 |

Steering changed answers about as much as extra randomness.

**Integration labels:** RETAIN 213, VERIFY 32, REJECT 19, REVISE 4.

Quality is not scored here. These tasks are the old, mostly math/logic set; the 1.3.3 broad tasks are rated by blinded review.
