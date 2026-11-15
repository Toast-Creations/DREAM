# Continuity pilot results (Qwen3-8B), 2026-11-02

**Pre-registration:** `output/continuity/PREREG.md` (sha256 f413846c…), written before generation.
**Generation:** hub `gpu/qwen3-continuity-pilot-20261102-064109`.
**Judging:** `judging/pairwise-c1/continuity-pilot-qwen3/` (`analysis.json`, `rows.csv`; the private key holds the arm identities).

## Delivery (judge-free)
- All 90 chains ended at EOS, with all four sections, 5 starting ideas and FINAL present. The extraction gate passed. Every steered schedule returned to 0, and every perceive arm recorded its prefill trace.
- Mean output tokens: baseline 1,050; perceive_targeted 1,032; perceive_random 1,048; generate_targeted 1,012; generate_random 1,047.

## Manipulation check: category probe (greedy, 18 task-seed cells)
| Reading condition | Cells where categories changed vs baseline | Mean Jaccard distance |
|---|---:|---:|
| Steered with the decategorization direction | 3 / 18 | 0.06 |
| Steered with a random direction | 7 / 18 | 0.31 |

Reading under the decategorization direction barely changes how the model categorizes the subject, and less than a random direction of equal size does. **The intervention does not show decategorization at the reading stage.**

## Primary endpoint: blind pairwise judgements, targeted vs random (pairwise-c1, Claude, both display orders)
Score per presentation: +1 if targeted is preferred, −1 if the other arm is, 0 for a tie.

| Mode | Presentations won (targeted–other–tie) | Tasks favouring targeted / other / even | Sign test p | Practical mean | Artistic mean | Order-consistent pairs |
|---|---|---|---:|---:|---:|---:|
| Perceive (steered reading) | 22–14–0 | 3 / 2 / 1 | 1.00 | +0.22 | +0.22 | 16/18 |
| Generate (steered writing) | 21–15–0 | 3 / 2 / 1 | 1.00 | −0.22 | +0.56 | 17/18 |

## Secondary: targeted vs baseline
| Mode | Presentations won (targeted–baseline–tie) | Tasks favouring targeted / baseline / even | Sign test p | Practical mean | Artistic mean | Order-consistent pairs |
|---|---|---|---:|---:|---:|---:|
| Perceive | 23–13–0 | 4 / 0 / 2 | 0.125 | +0.22 | +0.33 | 13/18 |
| Generate | 16–19–1 | 2 / 3 / 1 | 1.00 | −0.28 | +0.11 | 15/18 |

## Reading, under the pre-registered rules
- **Primary contrasts:** targeted is preferred in slightly more presentations (about 60%) in both modes, but tasks split 3 to 2 and nothing approaches a signal at six tasks. A direction-specific benefit is not shown.
- **Most suggestive secondary result:** perceive_targeted vs baseline, with no task favouring baseline (4/0/2). It is secondary, and perceive_random was not compared with baseline, so generic perturbation during reading could explain it. Together with the manipulation check, which shows less category change than random, it does not support a decategorization mechanism.
- **Generate mode, artistic tasks:** +0.56 for targeted vs random (tasks 04/05/06: +0.33, +0.33, +1.00), against −0.22 on practical tasks. This is a post-hoc subgroup of three tasks: a hypothesis for a future pre-registered test, not a finding.
- **Rule outcome:** the pre-registered positive condition for proposing a confirmation (a mode beating random) is not met. The theory has been tested at this scale (Qwen3-8B, λ = 0.20, block 28) and is not supported. It is not refuted for other strengths, layers, directions or models.

## Exploratory addition (after the results above were seen; not pre-registered): random vs baseline
72 more Claude calls using the same frozen pairwise-c1 instrument (`judging/pairwise_c1_exploratory.py`).

| Comparison | Presentations won | Tasks + / − / even | Order-consistent pairs |
|---|---|---|---:|
| perceive_random vs baseline | 18–18–0 | 3 / 2 / 1 | 14/18 |
| generate_random vs baseline | 18–18–0 | 3 / 3 / 0 | 18/18 |

**Perceive mode, all three comparisons together:**
- targeted beats baseline 23–13 (tasks 4/0/2);
- targeted beats random 22–14 (tasks 3/2/1);
- random ties baseline 18–18.

The ordering targeted > random ≈ baseline is consistent with a small, direction-specific benefit of steered reading, not a generic perturbation effect. But the category probe shows this direction changes the model's categories *less* than random, so whatever it does during reading is not visible as category loosening.

Six tasks, one judge, exploratory: this is the best-supported lead for a pre-registered follow-up (perceive mode, targeted vs random, more tasks, human comparison). It is not a finding.
