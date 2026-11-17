# Preregistration: confirmatory analysis plan for E1–E5

*DREAM3 · prospective analysis specification*

> **Status: written 16 November 2026, before any fresh run exists; amended 17 November 2026 (Section 10), still before any generation.** No confirmation or full-run generation has been made for Qwen3-8B or Mistral-7B. Both main hubs completed only `smoke`/`devqual`/`pilot` (`COMPLETE.json`, 1 November 2026). Section 9 records the author's decisions of 16 November 2026 and the artefact hashes; all items are closed. The file is binding from its public push to GitHub (branch `proposals-refs-prereg-20261116`), which is its timestamp, and that push precedes any fresh generation. As [E1](E1.md) says, a local freeze is not a public preregistration.

David Cook · 16 November 2026 · Preregistration v1.3 (v1.0 had §9 as open items; v1.1 left five items open; v1.2 was the first public version; v1.3 is Amendment 1, Section 10, made 17 November 2026 before any generation)

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
- **Smallest effect of interest (SESOI):** a net preference of **+0.25**, which is a tie-adjusted win share of (1 + 0.25) / 2 = **0.625** (Section 9.1). Precision is judged relative to it. The analysis reports whether the interval excludes zero, includes the SESOI, or rules it out (upper bound below +0.25). An interval that includes zero is reported as inconclusive, not as a null.

## 5. Recency diagnostic guardrail

For every run, and separately for each model × contrast, the analysis reports the hard-flip rate (hard flips divided by pairs), the order-consistency rate and the second-position win rate.

- A **flip rate above 15%** raises a **stability warning**. The warning is printed in the headline next to the primary result.
- A warning does not exclude data, trigger a re-run or change the instrument. Counterbalanced averaging stays the primary analysis in every case.
- The pilot's rate was 14/72 (19.4%), so a warning on fresh data is plausible.

## 6. Secondary endpoints

1. **Dimension net preference:** the same coding and task averaging for Novelty, Usefulness and Coherence, for C−A, C−B and C−D. These get intervals and Holm-adjusted permutation p-values across the three dimensions. They can only support descriptive claims.
2. **Lineage survival attribution:** each delivered final member of every chain in a pair (all four arms) is rated by `prereg/run_e1_lineage.py`, one call per member, with the chain's original ledger and its earlier final members, using the frozen **scope-v5c lineage prompt**, the one that scored 8/8 on its lineage traps. Its files are `package/prompts/lineage_system_prompt.txt` (`0d8218ecf2ace42abcf3e0216ba9c6829c58dc55bf0897e1c537de24c0e64730`) and `package/schemas/lineage_schema.json` (`2009d7a7875888c2aa2b71ee9597a57f52f4fdead670192a1e9868150e8afbf6`), read from the frozen `judging/scope-v5c/` directory and never copied or edited there. Results are written elsewhere.
   - The analysis reports, by arm, the share of finals rated faithful development or productive reinterpretation. It also reports, among C's Useful Originality pair wins, the share whose steering final is source-linked rather than an unrelated replacement.
   - **Limits:** scope-v5c *failed* its overall qualification. Only its lineage gate passed, on 8 traps authored inside this project. The prompt has never been run on pilot outputs. These lineage results are therefore secondary and descriptive. Missing members and failed calls are reported as unrated, by arm.
3. **Process outcomes:** completion, delivery, duplicates, unrelated replacements, tokens and runtime for each arm, as listed in E1. These come from the generation run records, not from the pairwise analysis script.

## 7. Mapping to E2–E5

- **E1:** Sections 3–6 as written above.
- **E2:** for each size s, ΔA(s) and ΔB(s) are the primary task-averaged net preferences. The co-primary interactions are large-minus-small. Paired task blocks are kept when resampling. The checkpoints are named in the size addendum (Section 1).
- **E3:** the primary interaction is the C−A net preference under the large developer minus the same quantity under the small developer, averaged over generator sizes. Fork pairing is kept. C−B corroborates.
- **E4:** **its primary estimand is unchanged** (the task-grouped Brier-score difference against independent checks). Under E4, pairwise-v1 is a candidate instrument to be validated, not the outcome. E4 validation data may never become E1 confirmation data.
- **E5:** the linear-in-log-parameters forecast and the flat comparator forecast the C−A and C−B net preference at the held-out size. Both forecasts are registered before the held-out result is revealed.

## 8. Data handling and analysis code

- The analysis script and driver are hashed in Section 9.1 and must not change. The analysis computes Sections 3–6 exactly as written.
- Failed calls follow the frozen runner's retry policy.
- A pair missing either order is left out of the primary analysis and reported, with no replacement or imputation. Generation failures stay outcomes.
- The arm key stays sealed until every call is complete. All raw replies, logs and deviations are released.

## 9. Decisions and registered artefacts

### 9.1. Decisions (author, 16 November 2026)

All items below were confirmed by the author on 16 November 2026. Wording and mechanics were drafted by Claude to implement them.

1. **SESOI = +0.25 net preference**, which is a 0.625 tie-adjusted win share. It applies to the primary endpoint for each model × contrast (Section 4).
2. **Judge and cross-family audit.** The primary judge is single-family: `claude-opus-5-5`, through pairwise-v1 exactly as frozen (Section 2). E1's two-family endpoint is amended to this, and claims are worded as "AI-judged pairwise preference (one judge family)".
   - **Fixture provenance (disclosed):** the qualification fixture `qual_24.json` was authored by the same model that judges (`claude-opus-5-5`). Its anchors are author-specified and are not external human norms.
   - **Cross-family audit (Codex; report-only; 20% stratified).** Codex CLI (OpenAI family, default model `gpt-6.1-sol`, effort medium; the exact model is recorded in every raw call) re-judges a deterministic stratified sample in both orders.
     - **Sample:** per model × baseline × family, the first 5 of 8 tasks by `sha256("e1-cross-family-audit-v1|…")` rank, with one seed per task by the same rule. That is 90 of 432 pairs (20.8%), 180 calls.
     - **Instrument:** the frozen pairwise-v1 system prompt, schema and payload renderer. Codex has no system-prompt channel, so the frozen system prompt and payload are sent as one message; this transport difference is recorded per call.
     - **Reporting:** sign agreement, exact pair-score agreement, and both judges' net preference on the subset. No threshold is set, and the audit never changes the primary result.
3. **E4 human-calibration gate (before unblinding E1).** No arm-level E1 confirmatory result is computed or read until this gate has passed. Judge calls may run first, because the judge sees only masked pairs.
   - **Pairs:** 24 condition-masked pilot pairs, 8 practical, 8 analogy and 8 artistic: two per family × model × baseline cell, one per pilot task, chosen by `sha256("e4-human-calibration-v1|…")` rank (`e4_calibration.py select`).
   - **Packet:** the packet shows each pair's task and the two FINAL answers as A/B, with sides set by hash. Arm names, model names and pairwise-v1 verdicts are withheld.
   - **Ratings:** one or more human reviewers rate every pair blind and independently: Useful Originality (A/B/TIE, with the pairwise-v1 definition), and for each answer whether it relies on a physically impossible mechanism, pseudoscience or folklore treated as fact. The human verdict for a pair is the majority of reviewers' Useful Originality votes; an even split is a tie.
   - **Pass criteria** (both required):
     - **(a)** directional agreement between the human verdict and the counterbalanced pairwise-v1 pilot verdict of **≥ 75%**, on pairs that are non-tie for both. At least one such pair must exist.
     - **(b)** **0** practical pairs in which the human-preferred answer is the one a majority of reviewers flagged as impossible while the other answer was not flagged. If no practical pair has exactly one flagged answer, (b) passes vacuously; the summary says so.
   - **Enforcement:** `e4_calibration.py record` writes the E4 record. `analyze_e1_pairwise.py` then:
     - checks the record's schema, the 24 registered pair IDs, the 8/8/8 family split, one review per reviewer per pair, and the registered pilot-pairs file (sha `c0821bf765fca3d0d1109c566d6cf5235fc855d4a645d9e7d041a11504f62c8f`);
     - recomputes (a) and (b);
     - refuses arm-level output unless the gate passes.
   - **Limits:** the 24 pairs are pilot pairs, already judged by pairwise-v1, and the gate measures agreement with that judge, not ground truth. E4's full validation study (Brier estimand, Section 7) remains separate.
4. **Steering arm locked to the pilot** (`prereg/steering_lock.json`, unchanged): ideation only, layer −8, **peak strength 0.2**, absolute cap 0.4, and a smooth schedule of 50/100/200 tokens. The per-model targeted vector and nine random directions are pinned by SHA-256, and sampling is T 0.6 (high-temperature arm 1.3 at ideation), top-p 0.95, top-k 20, with thinking off. No pilot ran at a peak of 0.4. The driver checks every fresh unit against the lock and refuses to judge on any mismatch; `--check-hub` checks the vector and random set before generation.
5. **Task set** (`prereg/tasks_e1_24.json`; split label corrected by Amendment 1, Section 10; `tasks_e1_24.jsonl` is the same 24 rows, one per line, for the generator).
   - **Contents:** 8 practical, 8 analogy and 8 artistic tasks in the pilot schema (`split: test`, the label the pinned `confirm` config selects; v1.2 had `confirmation`, see Section 10). With 3 seeds and 4 arms that is 288 chains per model, 216 pairs per model and 864 primary calls.
   - **Disjointness:** subjects were checked against the pilot, smoke and devqual tasks, the unused 31 October confirmation sets, the diagnostics, every qualification fixture and the public repo's task data.
   - **Authorship:** the tasks were written by Claude, the judge's family. The earlier `tasks-v2` set (sha `bcc9497a…`) is not used.
6. **Generation code and configuration** (`prereg/generation_pin.json`).
   - **Source:** `Code/DREAM-project-1.4.2-extraction-fix-20261101` in the private DREAM-code repository, commit `ee51aa869522a3226d3e429001558db13799cbd2` (on `origin/main`), directory tree `7a73f9b1cf26f5bb802c90803a4892ed73db60b9`. Key files are pinned by SHA-256 in the JSON.
   - **Entry point:** `scripts/run_experiment.py` (`87dc1408d9a0afc470b88687359f2eb8e1b9b5a3747611f3b0553583310c4908`).
   - **Base config:** `configs/survival-pilot.json` (`764575a5b3b618e8afd07886e0dd9292247e87c3d9be6f550bd7d5e21988efe4`). It is identical to both pilots' configs apart from paths.
   - **Orchestration:** `Tools/Idea-Survival/prepare_run.py` (`dcf44d47d6834ff1227e9c4328210c366f13f2b72b9eb40796c720b488c9e095`), `run_queue.py` (`968ae3e0188a7522a9789f045d0ff4524d7c272c4a27cecbaf3bfd48214e58f0`) and `check_extraction.py` (`9fc987faa8b524b8d0b7c279f4c8f24cee3a2dd64ed4844b6955953900344aa7`). They are local and not under version control, so the hashes pin them.
   - **Stage:** `confirm`, with `--tasks tasks_e1_24.jsonl --source <1.4.2>`. Mistral also gets `--vector <its pilot-hub vector>`.
   - **Parameters:** arms `strong_prompt`, `high_temperature` (T = 1.3 at ideation), `targeted` and `random`; strong prompt as in `src/survival/prompts.py` (`698b7319847383ab14fcdee36f8b30291666c44f96dde7c5ce6b57201b2a752d`); 3 seeds (11, 23, 47); order seed 20261031; workflow `develop`; T 0.6, top-p 0.95, top-k 20; layer −8; `peak_strength = 0.2`; `max_abs_strength = 0.4`; `max_trials = 288`. The full expected `confirm.json` for each model is in `generation_pin.json`.
   - **Equivalence to the pilots:** 1.4.2 generation code is identical to 1.4.1, the Mistral pilot's source. It differs from 1.4.0, the Qwen pilot's source, only in dropping `token_type_ids` before `generate()` and stopping on non-budget errors.
   - **Pre-generation check:** `run_e1_pairwise.py --check-hub HUB --hub-model M` must report `hub OK` after the random-set stage and before any chain. It compares the exact config, the task file, the model revision, the vector, the nine random directions and the pinned source files.
   - **Public repo base commit:** the public repo was at `0b0358b356034ea4b2e9d0eb9bb4c8f438be809e` (main) before this preregistration branch.

**Registered files** (frozen evaluation files in Section 2 unchanged):

| File | SHA-256 | Role |
| --- | --- | --- |
| `judging/pairwise-v1/SPEC.json` | `9a4e7aedd12c087da1ebe9276e668bcf470ee639743c2c8647785a74c0dcb22e` | frozen instrument spec |
| `judging/pairwise-v1/scripts/run_pairwise_v1.py` | `225728ff8040fb3d037e9f88ff53a2a3bc13afcaf72fc52852419abd65625c96` | frozen judge runner |
| `judging/scope-v5c/package/prompts/lineage_system_prompt.txt` | `0d8218ecf2ace42abcf3e0216ba9c6829c58dc55bf0897e1c537de24c0e64730` | frozen lineage prompt |
| `judging/scope-v5c/package/schemas/lineage_schema.json` | `2009d7a7875888c2aa2b71ee9597a57f52f4fdead670192a1e9868150e8afbf6` | frozen lineage schema |
| `prereg/analyze_e1_pairwise.py` | `7981fa9fdbc3492ac4fc41f4f81c2ae34b882906427d566ba8d4e4f63a811115` | preregistered analysis + E4 gate check |
| `prereg/run_e1_pairwise.py` | `9707046f08a47c8d147b0fc0cde581a759ca273471f600685684307df9cb2ea9` | E1 primary driver + `--check-hub` |
| `prereg/run_e1_audit_codex.py` | `967efb9f454b63a661d97c1db53245d9ee0935a15433b4677d68467ba47eb346` | Codex cross-family audit runner |
| `prereg/run_e1_lineage.py` | `6e750be89232819ef7ed41d042e2605addb7fef9ddd55dd767cdf2c263a94e7c` | scope-v5c lineage runner (verifies pins before any call) |
| `prereg/e4_calibration.py` | `5757c3d63f49fcfd7d0ea40552744c0a9d185c4574251a141c889eb2e521fbb1` | E4 selection, masked packet, record |
| `prereg/tasks_e1_24.json` | `1ed8ab1a99c7d1740004003c0d33a99523ba352359a781b041c48dda08b7a240` | E1 task set |
| `prereg/tasks_e1_24.jsonl` | `a296738662de76992c548af7b305a4b5d5142be5251e15a5a09bf6e6a4a4e978` | same tasks, generator format |
| `prereg/steering_lock.json` | `2361358bec3d8b2b4ee236f7cda9b6616b67cd2618a59f2c8a749915a65c18b2` | arm C/D and sampling lock |
| `prereg/generation_pin.json` | `1e3c4e865491a3fe207b97b1a2614be2b736179c958785c888d0bd68c0690f85` | generation source, tools and expected configs |

**Script checks (16 November 2026, no model calls).**
- *Analysis:* on the already-seen pilot pairs (`--exploratory`), it reproduces the pilot report's pair-level W/T/L and its 14 hard flips. The exact permutation p matches brute force. On a synthetic 432-pair E1 layout the audit sample is 90 pairs, with 5 distinct tasks in every one of the 18 strata, and it does not depend on input order.
- *E4 tool and gate:* the selection is 8/8/8. The packet contains no arm or model names. Simulated sheets pass (full agreement, and 2-of-3 majority) and fail (disagreement 0/19, and 7 impossible-answer wins). Truncated, incomplete or malformed records are rejected. The analysis refuses confirmatory output when the gate fails or `--pilot-pairs` is missing.
- *Lineage runner:* it verifies the pinned prompt and schema against the scope-v5c freeze files and refuses a changed pin. On pilot units it would rate 698 final members and record 22 as missing, matching the extraction counts.
- *Hub check:* on the two pilot hubs it flags only the expected differences (pilot config and tasks, 1.4.0/1.4.1 source files). It accepts the Qwen pilot vector and both nine-direction random sets.
- *Driver (earlier check):* it reproduces the frozen pilot builder's pairs and presentation orders, refuses foreign tasks by hash, and flags a peak-0.4 lock.
- *Untested:* no live Codex or lineage call was made. The Codex transport follows the 1 November judge's jailed `codex exec`, with `--output-schema` added.

**Call budget** (planned): primary 864 Claude calls; audit 180 Codex calls; lineage about 2,880 Claude calls (one per delivered final member, 2 × 288 chains × up to 5).

### 9.2. Closed items

All items listed as open in v1.1 are closed above: the audit runner (item 2), the lineage runner (Section 6.2 and the table), the E4 gate definition (item 3), and the generation source and configuration (item 6). The public timestamp is the GitHub push of the commit that adds this text to `proposals-refs-prereg-20261116`. Fresh Qwen3-8B or Mistral-7B generation starts only after that push.

## 10. Amendment 1 (17 November 2026, before any generation)

**What changed.** In `prereg/tasks_e1_24.json` and `prereg/tasks_e1_24.jsonl`, the `split` field of all 24 tasks changed from `"confirmation"` to `"test"`. Nothing else in either file changed: ids, families, subjects, descriptions, prompts and quality constraints are byte-identical, and the order is unchanged.

**Why.** The pinned `confirm` config (`generation_pin.json`, `"phase": "test"`, as in the 31 October confirmation sets `tasks-v1`/`tasks-v2`) makes the generator keep only rows whose `split` equals the phase. With `"confirmation"` it found no rows and stopped. The v1.2 checks compared the hub's copy of the task file with the registered file, and never compared the label with the runner's filter, so they missed this.

**When it was found.** On 16 November 2026 at 20:22 EST the first launch from the v1.2 pins (hubs `gpu/qwen3-e1-20261116-202134` and `gpu/mistral-e1-20261116-202147`) passed the controller fixtures and the ML test suite. It then stopped at the plan-only `confirm-plan` step (`ValueError: No rows for declared phase`) with **0 generation calls**, and the Mistral hub never started. No E1 output existed then or at the time of this amendment. Both halted hubs are kept unchanged as the record. The relaunch uses new hubs.

**Effect on the hash chain.** The new task hashes change `generation_pin.json` (which pins them) and `run_e1_pairwise.py` (whose `REGISTERED` pins the tasks and the pin). The table in Section 9.1 shows the v1.3 values. The v1.2 values were `tasks_e1_24.json` `bafe147e…641c`, `tasks_e1_24.jsonl` `d4ff29b2…b549`, `generation_pin.json` `7166991a…ec1b` and `run_e1_pairwise.py` `97e7813e…ba51`. The analysis script, steering lock, audit, lineage and E4 scripts, the frozen instruments, the endpoints and the decision rules are unchanged. The E4 packet is built from pilot pairs only and is unaffected.

**Check before relaunch.** The pinned 1.4.2 `load_rows` and `plan_units`, run on the amended file with the pinned Qwen config, give 24 rows and 288 planned units.

