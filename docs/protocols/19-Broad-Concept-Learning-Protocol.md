# Broad Tests and Concept Learning: Protocol V1.3.3

Version 1.3.3, October 31, 2026. Development pilot; exploratory, no significance claims. It implements the design that document 15 proposed.

## Why

The Qwen3-8B thinking pilots (`Runs/qwen3-thinking-20261030-230519`, `Runs/qwen3-thinking-20261031-083543`) showed four things.

1. **Greedy decoding loops with reasoning on.** The greedy anchor looped until the cap; 1.3.2 fixed it. Integration at temperature 0.3 also hit the 8,192 cap.
2. **Numeric DREAM 2 learning could not store a rule.** Every exposure prompt contained the rule text, while every test omitted it.
3. **Format mismatch.** Direct JSON targets competed with the model's `<think>` opening, so starting loss was 9.7 with reasoning on against about 3.9 with it off.
4. **Number tasks leave no room for creativity.** David Cook: "the tests should examine things that could be more broadly affected by decategorization. Numbers typically don't leave any room for creativity in a broad sense. The questions need to be written and answers are not to be judged harshly."

## Broad DREAM pilot (`configs/dream-broad-pilot.json`)

**Tasks** (`data/tasks-broad.jsonl`), six development tasks:
- unusual uses for a ladder;
- explaining grief through a river;
- a bus stop for a floating town;
- what a beehive and a library share;
- a myth for missing socks, with a testable rule;
- the exact arithmetic negative control.

**Settings:**
- reasoning on, 8,192 new and 8,192 input tokens;
- seeded Qwen3 thinking sampling (0.6 / 0.95 / 20) for both the anchor and integration;
- exploration unchanged (0.7 / 0.9).

**Cells:**
- divergent λ 0, 0.05 and 0.1;
- temperature control (1.3);
- **decategorization λ 0.20**, a new extra arm using the document 17 direction.

Size: 3 seeds × 6 tasks × 5 cells = 90 trials.

The legacy steering curve still scales with the 8,192 planned budget: it rises over the first 15% and holds to 60%. Answers of 2,000–5,000 tokens therefore receive most of their dose during reasoning. This is recorded as a limitation.

## DREAM 2 concept learning (`configs/dream2-concepts-pilot.json`, experiment `dream2_concepts`)

**Worlds** (`data/concept-worlds-development.jsonl`):
- three invented concepts: a glorp, the velk rule, a mirrorday;
- three real ones: feedback, threshold, symmetry.

**Exposure.** Twelve items per world:
- six open-book items, which show the definition, facts and an example;
- the same six questions closed-book, with no context.

Closed-book items force the adapter to hold the concept itself. Targets are plain text. Training renders with reasoning off, so the target follows Qwen3's empty think block; nothing teaches the model to skip reasoning at evaluation. Three steps per example; base learning rate 1e-4 × η.

**Evaluation.** Six open questions per world:
- recall;
- a surprising property;
- three new uses;
- a cooking analogy;
- combination with a bicycle;
- a failure or edge case.

No question contains the definition (enforced by the validator). Each is answered with reasoning off (0.7 / 0.8 / 20) and on (0.6 / 0.95 / 20), with the same seeds for every learned state.

**Conditions** (seed 11):
- frozen;
- learning only (η 1);
- exploration only (λ 0.1, η 0);
- coupled divergent (λ 0.1, η 1);
- pre-exposure control (divergent 0.1, then learning);
- coupled decategorization (λ 0.20, η 1).

Size: 36 trials, plus one shared before-learning baseline per world. Adapters are reset and verified after every trial.

## Loop guard (option A)

With `limits.loop_guard` set, generation stops once at least 80% of the 16-token sequences in the last 1,200 generated tokens repeat. The step is recorded with `finish_reason: "loop"`, the stopping token and the repeated tail, and the run continues:

| Looped step | What happens |
|---|---|
| anchor | the task/seed is skipped |
| exploration | that cell is skipped |
| integration | the trial is marked looped |
| concept answer | counted as unanswered |

Loop rate per arm is itself a result, because strong steering is known to cause looping (document 17).

**Calibration.** The guard was replayed over every recorded Qwen3 generation from this project, 13,502 in all (`scripts/calibrate_loop_guard.py`; `study-results/loop-guard-calibration-20261031/`):
- no naturally finished answer was flagged; the most repetitive finished answer scored 0.68;
- 18 generations that hit their token cap were caught, all scoring at least 0.83;
- this includes the task-04 anchor loop, which would have stopped at token 2,720 instead of 8,192;
- in total the guard would have saved about 48,000 tokens.

Truncation without a loop still halts DREAM, as before.

## Lenient blinded review

`scripts/export_concept_review.py` writes shuffled, unlinked pools of final DREAM answers and concept answers. Reasoning text is never shown. The private key is kept separately. Each answer is scored:

| Score | Range | Credit |
|---|---|---|
| **uses_taught_idea** | 0–2 | any sensible use of the concept counts; loose or metaphorical use earns credit |
| **creative_connection** | 0–2 | unexpected but defensible links score up; strangeness is never penalized |
| **coherent** | 0–1 | a format slip does not count against it |

For DREAM tasks, "taught idea" means the task's own subject, and the arithmetic control is checked exactly. The ratings hash is recorded before the key is opened.

The reviewer is Claude. Claude designed the study and has seen pilot outputs, so this is not an independent review.

## Reading the results

| Question | Comparison |
|---|---|
| Does learning store a concept? | before vs after, invented worlds, closed-book recall |
| Does steering during learning change transfer? | coupled vs learning-only, and the pre-exposure control |
| Does decategorization differ from divergent? | the two coupled arms, and the two DREAM arms |
| Does reasoning help? | the same learned state, reasoning off vs on |

Taught-term overlap is a diagnostic, never a score. One seed and six worlds support only descriptive comparisons.
