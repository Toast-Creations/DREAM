# Preregistration: confirmatory analysis plan for E1–E5

*DREAM3 · prospective analysis specification*

> **Status: written 16 November 2026, before any fresh run exists.** No confirmation or full-run generation has been made for Qwen3-8B or Mistral-7B. Both main hubs completed only `smoke`/`devqual`/`pilot` (`COMPLETE.json`, 1 November 2026). This file becomes binding only when the open items in Section 9 are filled and its SHA-256 is published with a timestamp. As [E1](E1.md) says, a local freeze is not a public preregistration.

David Cook · 16 November 2026 · Preregistration draft v1.0

## 1. Prospective hold rule

E1–E5 stay strictly prospective until the full, unseen Qwen3-8B and Mistral-7B runs have finished generating.

- No E1–E5 claim may use the 144 pilot chains. They were rated under scoped-v5 and then pairwise-v1, so they are exploratory development evidence (*From Strange to Useful* working manuscript v0.4, §4.9).
- Nobody may read the fresh outputs, run judge calls on them or open the arm key until (a) generation for both models is complete and (b) the analysis script in Section 8 is hashed.
- Sizes other than 7B/8B (the E2 ladder, the E3 large generator and developer, the E5 held-out checkpoint) are not covered by the fresh runs. Each needs a dated addendum to this file, naming its checkpoints, before its own generation starts.

## 2. Instrument (frozen; no changes)

The judge is **pairwise-v1** as qualified on 16 November 2026: judge `claude-opus-5-5`, effort `medium`, `claude -p --output-format json --json-schema`, subscription authentication (no `--bare`). Files under `judging/pairwise-v1/` in the idea-survival hub, verified against these hashes on 16 November 2026:

| File | SHA-256 |
| --- | --- |
| `SPEC.json` | `9a4e7aedd12c087da1ebe9276e668bcf470ee639743c2c8647785a74c0dcb22e` |
| `prompts/pairwise_v1_system.txt` | `a3cbf1181d998661c7760c31c606c7c95e43f78228cf8efbcce6da45560ed58f` |
| `schemas/pairwise_v1_schema.json` | `eecdf76df7a75a0a6b01b7bce450aace90041fe87f3d9f48a29e9ff48863ec1f` |
| `fixtures/qual_24.json` | `e8c84e5e7d2cc4106a462ed32fe9af245a3b3de5977e41cff74ac32efd5ae3e0` |
| `scripts/run_pairwise_v1.py` | `225728ff8040fb3d037e9f88ff53a2a3bc13afcaf72fc52852419abd65625c96` |

If any of these files differs at run time, the run falls outside this plan. Re-qualifying is not allowed, and neither is retuning the prompt, schema, fixture or gates. A changed instrument needs a new instrument name and a new preregistration.

## 3. Units and coding

- **Block:** one model × task × generation seed.
- **Pair:** within a block, the FINAL section of the targeted-steering chain (C) against one comparison chain: strong prompt (A), high temperature (B) or random direction (D). Arm labels are masked, and which side each arm appears on is assigned at random.
- **Call:** each pair is judged in both orders, (X, Y) and (Y, X). Each verdict is mapped back to the underlying chains and coded from steering's side as +1 (steering preferred), 0 (TIE) or −1.
- **Pair score:** the mean of the two order codes, so it is one of −1, −0.5, 0, +0.5 or +1. A **hard flip** (steering wins in one order and loses in the other) scores **0** and counts as a tie.
- **Task score:** the mean pair score over the seeds of that task. The task is the independent unit, and seeds and calls are not.

## 4. Primary endpoint

**Task-averaged counterbalanced net preference on Useful Originality**, for C−A and C−B, computed separately for each model.

- **Estimate:** the mean of task scores, with a 95% bootstrap interval that resamples tasks (10,000 resamples, seed fixed in the analysis script).
- **Primary test:** an exact two-sided sign-flip permutation test on the task scores. Tasks with a score of 0 are kept in the permutation test.
- **Corroborating test:** a two-sided exact sign test over tasks with a non-zero score.
- **Order-adjusted Bradley–Terry model:** strengths for C, A, B and D, with steering fixed at 0, plus one presentation-position parameter. Ties count as half wins. The model is fitted on call-level games. It is reported as an estimate and is not a decision test. Only steering-vs-comparison games are played, so baseline-vs-baseline gaps are inferred through C.
- **Decision rule (E1):** an added-value claim for a model requires **both** C−A and C−B to be positive with permutation p < 0.05. This is an intersection–union rule, so no adjustment is applied within a model. Across the two models, a Holm adjustment is applied to each contrast. C−D is a direction-specificity check and is not part of the claim.
- **Smallest effect of interest:** see Section 9. Precision is judged relative to it. An interval that includes zero is reported as inconclusive, not as a null.

## 5. Recency diagnostic guardrail

For every run, and separately for each model × contrast, the analysis reports the hard-flip rate (hard flips divided by pairs), the order-consistency rate and the second-position win rate.

- A **flip rate above 15%** raises a **stability warning**. The warning is printed in the headline next to the primary result.
- A warning does not exclude data, trigger a re-run or change the instrument. Counterbalanced averaging stays the primary analysis in every case.
- The pilot's rate was 14/72 (19.4%), so a warning on fresh data is plausible.

## 6. Secondary endpoints

1. **Dimension net preference:** the same coding and task averaging for Novelty, Usefulness and Coherence, for C−A, C−B and C−D. These get intervals and Holm-adjusted permutation p-values across the three dimensions. They can only support descriptive claims.
2. **Lineage survival attribution:** each final member is rated with the frozen **scope-v5c lineage prompt**, the one that scored 8/8 on its lineage traps. Its files are `package/prompts/lineage_system_prompt.txt` (`0d8218ecf2ace42abcf3e0216ba9c6829c58dc55bf0897e1c537de24c0e64730`) and `package/schemas/lineage_schema.json` (`2009d7a7875888c2aa2b71ee9597a57f52f4fdead670192a1e9868150e8afbf6`), read from the frozen `judging/scope-v5c/` directory and never copied or edited there. Results are written elsewhere.
   - The analysis reports, by arm, the share of finals rated faithful development or productive reinterpretation. It also reports, among C's Useful Originality pair wins, the share whose steering final is source-linked rather than an unrelated replacement.
   - **Limits:** scope-v5c *failed* its overall qualification. Only its lineage gate passed, on 8 traps authored inside this project. The prompt has never been run on pilot outputs. These lineage results are therefore secondary and descriptive.
3. **Process outcomes:** completion, delivery, duplicates, unrelated replacements, tokens and runtime for each arm, as listed in E1.

## 7. Mapping to E2–E5

- **E1:** Sections 3–6 as written above.
- **E2:** for each size s, ΔA(s) and ΔB(s) are the primary task-averaged net preferences. The co-primary interactions are large-minus-small. Paired task blocks are kept when resampling. The checkpoints are named in the size addendum (Section 1).
- **E3:** the primary interaction is the C−A net preference under the large developer minus the same quantity under the small developer, averaged over generator sizes. Fork pairing is kept. C−B corroborates.
- **E4:** **its primary estimand is unchanged** (the task-grouped Brier-score difference against independent checks). Under E4, pairwise-v1 is a candidate instrument to be validated, not the outcome. E4 validation data may never become E1 confirmation data.
- **E5:** the linear-in-log-parameters forecast and the flat comparator forecast the C−A and C−B net preference at the held-out size. Both forecasts are registered before the held-out result is revealed.

## 8. Data handling and analysis code

- Before any judge call on fresh data, write the analysis script, record its SHA-256 in this file and leave it unchanged. It computes Sections 3–6 exactly as written.
- Failed calls follow the frozen runner's retry policy.
- A pair missing either order is left out of the primary analysis and reported, with no replacement or imputation. Generation failures stay outcomes.
- The arm key stays sealed until every call is complete. All raw replies, logs and deviations are released.

## 9. Open items before this plan is binding

These need the author's decision. Until they are filled, this file is a draft.

1. **Smallest effect of interest** for the net preference. The 0.5 qualifying ideas in E1 refers to a different scale, so it does not carry over.
2. **Endpoint amendment.** E1's candidate primary endpoint was qualifying surviving ideas rated by **two** independently qualified judge families. This plan replaces it with a **single-family** pairwise endpoint, and the qualification fixtures were authored by the same model family that judges. Claims will be worded as "AI-judged pairwise preference (one family)". The amendment needs confirming.
3. **E4 ordering.** The proposals index lists E4 as the first dependency of E1–E3. Running E1 under this plan first means no human validation of the endpoint has been done yet. This should be either confirmed or reordered.
4. **Intervention.** The [proposals index](README.md) notes that later screens found no evidence that the steering decategorizes. Before the fresh runs, it must be confirmed that arm C is still the targeted steering from the pilots.
5. **Task set and allocation.** E1 plans 24 new tasks (8 constrained design, 8 relational analogy, 8 artistic) × 3 seeds × 4 arms. The task identities and hashes must be registered.
6. **Analysis-script hash** (Section 8) and the **public timestamp** for this file's SHA-256.
