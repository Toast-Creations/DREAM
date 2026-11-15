# Fresh-world precondition probe V1.7.4: report (development only)

## Status
- **Brief:** `PRECONDITION-PROBE-BRIEF.md`. **Plan:** `design/PROBE-PLAN.md`, frozen before any output (`config/FROZEN-PROTOCOL.json`). **Amendment P1** (`design/AMENDMENTS.md`, made before main): after smoke, the parser accepts "yes"/"no" as requirement values. Prompts and inputs are unchanged and byte-identical. **Main config frozen:** `config/MAIN-CONFIG-FROZEN.json`.
- **Ran:** 2026-11-05, 09:01–09:18 America/New_York.
  - Smoke: 23/23 calls (not pooled).
  - Main: 280/280 calls in 957 s.
  - Main had 0 invalid replies, 0 truncations and 0 infrastructure retries. Longest input: 1,381 tokens. Longest output: 151 tokens. Peak memory: 15.6 GiB.
- **Model:** Qwen3-8B rev b968826d…, bf16, thinking off, greedy decoding. The prompts include the 1.7.2 domain statements. No adapters were used.
- **Worlds:** 24 fresh worlds (12 delivery, 6 assembly-slot, 6 assembly-stock), all new names, 0 rejected generation attempts. These 24 worlds are the independent unit. Rows, controls and conditions are nested within them.
- **Earlier runs:** their files are unchanged (tested).

## Primary outcomes
| Condition : arm | Pair applicability correct | Invalid action rejected **and** no effect |
|---|---|---|
| direct C0 (state given) | 1/24 | 0/24 |
| direct C1 (history) | 0/24 | 0/24 |
| **checklist C0** | **24/24** | **0/24** |
| checklist C1 | 1/24 | 0/24 |
| supplied predicates, C0 | 1/24 | 0/24 |

Paired contrasts within worlds (domain-weighted; cluster bootstrap with 10,000 resamples). "Worlds" counts better / equal / worse.

| Contrast | Pair applicability | Worlds | Rejected + no effect |
|---|---|---|---|
| checklist − direct, C0 | **+0.958 [0.88, 1.00]** | 23 / 1 / 0 | 0.000 |
| checklist − direct, C1 | +0.042 [0.00, 0.12] | 1 / 23 / 0 | 0.000 |
| supplied − direct, C0 | 0.000 [−0.12, 0.12] | 1 / 22 / 1 | 0.000 |
| supplied − checklist, C0 | −0.958 [−1.00, −0.88] | 0 / 1 / 23 | 0.000 |

## The three mappings

1. **Evidence → predicates**
   - **C0, state given:** the requirement vector was exact in 55/56 rows. Every key was 28/28 except one `hands_empty` error in a carrying control. There were 0 false-certainty answers and 0 unneeded unknowns.
   - **C1, history:** the vector was exact in only 16/56 rows. The errors were almost all **unneeded "unknown"** (38 values); false certainty was 0, and 5 values were definite but wrong. The manipulated predicate was the weakest: `crate_at_your_place` 8/28, `part_on_hand` 16/28, `slot_empty` 19/28. "Unknown" answers occurred in every history pattern, including a plain change (pattern 1: 6 of 10 rows).
   - With history, then, the failure is in reading the condition out of the records. Over-caution about settled facts is the main error, not misreading.
2. **Predicates → applicability**
   - The applicability answer matched the conjunction of the model's own reported predicates in 56/56 rows (C0) and 55/56 rows (C1).
   - Asked to write out the requirements first, the model drew the correct conclusion from them: C0 invalid actions were rejected 24/24, against 1/24 when asked directly.
   - **Supplied predicates did not help.** With the correct requirement values printed in the prompt but not requested in the answer, the model still called 23/24 inapplicable actions allowed, the same as direct. In this format, the gain comes from the model producing the requirements itself, not from having the information available.
3. **Applicability → effects (transition gating)**
   - In every row where the checklist rejected an invalid action (C0 24/24, C1 7/7), the predicted successor still applied the action's effects. Examples: "carried by you" for a crate that isn't at your place; the part placed in an occupied slot.
   - "Rejected and no effect" was therefore 0/24 in every condition. This is a gating inconsistency, separate from extracting predicates and from combining them: the model states that the action fails and then describes it succeeding.
   - *Exploratory:* every one of the 24 C0 checklist invalid rows showed the action's own effect fields changed.

## Controls (4 rows each)
| Condition : arm | Unknown only: answered "unknown" | False + unknown: answered false |
|---|---|---|
| direct C0 | 3 | 0 (4 answered unknown) |
| direct C1 | 3 | 0 |
| checklist C0 | 4 | 3 |
| checklist C1 | 4 | 1 |
| supplied C0 | 4 | 0 |

Answering directly, the model never let a known-false requirement override an unresolved one. The checklist fixed this in C0 (3/4).

## Supporting outcomes
- **Applicable actions:** with the state given, applicability was correct 24/24 in every condition. The exact successor was right 18/24 (direct and supplied) and 19/24 (checklist). With history, applicability on these rows fell to 21/24 (direct) and 7/24 (checklist, mostly "unknown").
- **Observed world now** (not the action outcome) was exact on 17–20 of 24 rows in C0 and 7–10 in C1.
- **Balanced applicability:**
  - direct: 0.52 (C0), 0.44 (C1);
  - checklist: 1.00 (C0), 0.29 (C1);
  - supplied: 0.52.
- **Cost:** the checklist adds about 35 output tokens (about 0.8 s per call).
- **Key order:** every checklist reply put `preconditions` first, as requested. That is a response scaffold; it says nothing about hidden processing order.

## Reading, under the plan's rules
- **Direct baseline on fresh worlds:** the block-D failure recurs (C0 invalid rejected 1/24, the same as in V1.7.2). It is not specific to the earlier 24 groups.
- **With the state given:** the precondition failure is not an inability to evaluate or combine the conditions. The model does both correctly when it writes them out. Without that scaffold it answers as if the action is allowed. A checklist-first scaffold fixes applicability on fresh instances of these two action families. Transfer to other action templates is untested.
- **With history:** the remaining failure is evidence → predicate. Settled facts are reported as "unknown", consistent with the pilot's over-abstention and false "unknown" readouts. The scaffold doesn't fix this.
- **Gating:** a correct "not applicable" is not carried through to the successor. For a practical system, a deterministic step that applies effects only when the action is applicable would close this. As a model-behaviour target, it is distinct from the other two.

## Not supported
- Claims about internal mechanisms or hidden processing order.
- Transfer to unfamiliar dynamics or templates.
- Anything about adapters, larger models, or temporal memory capacity.
- Generalising from 4-row control cells.
- Treating smoke outputs as data.

## Stop
As the brief requires, I stopped after this report. The next intervention depends on which failure point you choose to target: history → predicate extraction, or effect gating.

## Artifacts
- Analysis: `analysis-probe/ANALYSIS.json`, `TABLES.md` and `scores.jsonl`. Smoke: `analysis-probesmoke/`.
- Raw replies: `stages/{smoke,main}/calls/`.
- Inputs: `data/` (probe and probesmoke worlds, calls, gold and commitments).
- Source: `<DREAM_HOME>/Code/DREAM-project-1.7.4-precondition-probe-yesno-20261105`. Inputs were generated by 1.7.3 and are byte-identical under 1.7.4. Tests 47/47 (`test-results/tempo-tests-1.7.4.txt`).
- Re-score: `python3 -B scripts/probe_analyze.py --hub HUB --set probe --stage main`
