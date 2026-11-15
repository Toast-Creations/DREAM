# Idea-survival follow-up: amendment and operational-choice record

Written 2026-10-31, before any new judge or generation data. It is part of the execution of `<private-notes>/manuscript/CLAUDE-AFTER-CURRENT-BATCH.md`. Original proposal files are unchanged; this record says how conflicts between them were resolved for this execution. Later amendments are appended with a timestamp and never overwrite earlier entries.

## A. Sources and precedence

Precedence: the handoff, then TEST-PLAN-v0.1, then PROTOCOL-AND-PUBLICATION-PROPOSAL, then DREAM-Idea-Survival-Rubric-v0.1 and DREAM-Idea-Survival-Study-v0.1. David's AI-review preference overrides older human-rater text.

## B. Conflicts and operational choices

| # | Conflict | Choice for this execution |
|---|---|---|
| 1 | The rubric and study doc call for the median of three human raters. The protocol, test plan and handoff call for two AI families who must both score ≥3. | Two AI judge families. An idea qualifies only if **both** rate novelty, value and coherence ≥3/4. The endpoint is called **AI-rated task value**, not validated human utility. |
| 2 | The historical scale is 0–2 (interesting connections, semantic range, concrete development). The survival scale is 0–4 (novelty, value, coherence). | Each is validated separately in test 1. There is no conversion between them. Test 2 uses pairwise questions, not either scale. |
| 3 | The historical pilot peaked at +0.40 (the Study doc mentions 0.50). The protocol proposes +0.20. | **+0.20**, as proposed, is a qualification choice and not an optimum. Test 6 (strength 0/0.10/0.20/0.40) is written as a separate plan. |
| 4 | The historical schedule was 100/350/300 (750 tokens). The protocol proposes 50/100/200 (350 tokens). | 50/100/200 smooth (raised cosine), using the existing `schedules.dose` with shape `smooth`. Its values equal the protocol formulas exactly; tests check steps 0/25/50/149/250/350 and the unit-peak sum of 225, which is 45 at +0.20. |
| 5 | The historical temperature control annealed 1.3→0.6 over 750 tokens. Protocol arm B holds 1.3 constant. | Test 4/5 arm B uses a constant **T=1.3** for ideation. Test 2 compares against the historical anneal arm because that is the object it re-checks. |
| 6 | The historical run had one random vector (seed 20261030). The protocol uses nine. | Nine Gaussian unit directions, seeds **271828–271836**, built by `scripts/build_random_set.py`. Assignment is `(3·task_index + seed_index) mod 9`. |
| 7 | The hook site was given as config `layer_index −8` and as artifact `layer 28`. | Qwen3-8B has 36 decoder blocks, so −8 resolves to block **28**. The hook is on the residual output of that block at the final position, and `load_vector` refuses any artifact whose resolved layer or manifest hash differs. For Mistral-7B (32 blocks), −8 resolves to block 24, a model-specific choice recorded with its own vector. |
| 8 | The historical run used one seed and a 1,024-token input cap. | Seeds 11/23/47. Per-call input caps are 4,096 / 8,192 / 12,288, with 3,072 new tokens. The ledger is never truncated: an over-budget prompt is recorded as `input_budget_exceeded`, not cut. |
| 9 | The historical sober pass was one call. The proposal uses two calls. | Test 3 compares two two-call branches: a review/classification first pass or a development first pass, each followed by the common finalizer. The review branch is **not** a rerun of the historical one-pass reviewer. |
| 10 | Multiplicity is a "candidate" in the handoff. | Frozen before confirmation: two primary contrasts (C−A, C−B), each with a **97.5% percentile task-bootstrap interval**, 10,000 resamples stratified within the three task families, seed 861003. An added-value claim needs both lower bounds above 0. C−D (direction specificity) and genre contrasts are secondary, with 95% intervals. Imprecise or nonsignificant results are never called equivalence. The +0.5/5 target is the reference for precision. |
| 11 | Loop handling is not specified in the protocol. | Every generation uses the calibrated V1.3.3 loop guard (1,200-token window, 16-grams, 0.80 share, checked every 16 tokens). A loop is an outcome (`finish_reason=loop`) and is never resampled. The guard was calibrated on Qwen3 thinking outputs; its behaviour on non-thinking and Mistral outputs is reported. |
| 12 | Retry rule. | One identical retry, only after an infrastructure exception (RuntimeError/OSError such as CUDA OOM). A second failure is recorded as `external_failure` and treated as missing (bounded), never resampled. Judge-call retries follow the same rule: one retry for a CLI or network failure, never for an unwelcome answer. |
| 13 | The historical starting sets have KEEPERS JSON, not I1–I5. | For test 3, the original ledger is the five recorded KEEPERS ideas, written verbatim as `I1`–`I5` with their `idea`, `reasoning` and `would_prove_wrong` fields. When the KEEPERS block failed to parse, the full raw stage-1 text is used verbatim and flagged. The task text is the historical stage-1 task. |
| 14 | Lineage and duplicate rules for the primary count. | An idea counts only if both judges give lineage `faithful` or `productive_reinterpretation`, both give constraint status `pass` or `not_applicable`, and **neither** marks it a duplicate or merger of an earlier counted final idea in the same chain. Faithful and reinterpretation are counted separately. "New idea" notes and `unrelated_replacement` are scored separately and never earn survival credit. Sensitivity analyses use "either judge" and single-judge rules and thresholds of ≥2 and ≥4. |
| 15 | Missing ratings. | Not zero. Yield is reported as lower and upper bounds, with missing counted as fail and as pass, plus complete-case values. |
| 16 | Second generator family. | David chose **mistralai/Mistral-7B-Instruct-v0.3**: pinned revision, fetched once with `fetch_model.py`, run offline. It has no reasoning switch. Its chat template has no separate system role, so the system text is folded in by its own template, and this is recorded. It gets its own vector build and qualification, its own development pilot, and tuning effort comparable to Qwen's before confirmation. |

## C. Judges (David's choice, this session)

| Family | Access | Model ID requested | Isolation |
|---|---|---|---|
| Anthropic | `claude -p` (Claude Code 2.1.316) | `claude-opus-5-5` (as reported by the CLI) | fresh process per call, `--tools ""`, `--safe-mode`, `--strict-mcp-config`, `--no-session-persistence`, empty temp working directory, dedicated judge system prompt |
| OpenAI | `codex exec` (codex-cli 0.166.0-alpha.5.1) | `gpt-6.1-sol` (the CLI does not echo the served model; the requested slug is recorded and the served ID is marked "unknown") | `--ephemeral`, `--ignore-user-config`, `--ignore-rules`, `--sandbox read-only`, empty temp working directory; Codex's built-in agent instructions cannot be removed, which is recorded |

- **Gemini.** Not automated. The submitted Gemini ratings are kept unchanged and reported only as an earlier sensitivity check.
- **No orchestration judging.** The orchestration conversation (this Claude Code session) is never a judge.
- **Blinding.** Judges never receive condition keys, arm names, manuscript text or expected results. Items get fresh random IDs for each presentation.

## D. Gates (screening targets, not validated thresholds)

- **Test 1 gate.** At least 90% consistency on content-preserving checks and at least 80% of prespecified directional checks pass, per rubric and per judge family. Results are reported with denominators.
- **Test 1 revision.** One revision is allowed, on a new unseen 12, with the failed version preserved.
- **Confirmation hold.** If the gate still fails, confirmation tasks are not spent.
- **Developer workflow.** The workflow is chosen on test-3 development evidence and frozen before the pilot's development calls are read for a decision. A change after the pilot starts is a recorded amendment.

## E. Development-evidence labelling

All already-inspected material (the 1.2.3 decategorization pilot, the 108-response packet, Gemini ratings, the current Qwen3 thinking batch, tests 1–4 of this programme) is **development evidence**. Only the frozen confirmation package (test 5) is prospective, and it is not a public preregistration.

## F. Appended amendments (timestamped; earlier entries unchanged)

**2026-10-31 17:15 EDT — judge prompt v2 (test-1 calibration only).**
- v1 failed content-preserving consistency on calibration. Directional checks were 20/20.
- v2 (`judging/prompts/rubric0{2,4}_v2.md`) adds four instructions: score each item in isolation against the anchors; at a boundary, take the lower level unless the higher anchor is fully met; write the rationale before the scores; return exactly N lines.
- v1 replies and scores are preserved.

**2026-10-31 17:20 EDT — replicate aggregation.**
- Identical Claude prompts differed on 16% of 0–4 facets (70/432), always by ±1.
- The instrument therefore uses three independent fresh calls per presentation, with the median per facet (low median for an even count) and the mode for labels. Missing replicates reduce the count and are never zero-filled.

**2026-10-31 17:25 EDT — presentation.**
- Claude's medians still differed between exact copies placed in different batches; for example, one idea scored (3,2,2) three times in one batch and (2,1,2) in another. That is a batch-context effect.
- Candidate fix: Claude scores each item alone (`--solo claude`). Codex keeps batches of 12; it passes 0–4 calibration in batches (35–36/36 consistency, 20/20 directional).
- Each family's presentation is qualified separately on the same diagnostics. The final choice is recorded below before any unseen scoring.

**2026-10-31 17:22 EDT — judge quota.**
- The ChatGPT account (Codex) hit a rolling usage limit ("try again at 5:24 PM").
- The harness now waits for the stated reset and resends the identical prompt. This is an infrastructure wait, not a content retry. No service was purchased.

**2026-10-31 18:45 EDT — confirmation task 20 replaced before the freeze.**
- `tasks-v1` task 20 used "umbrella stand", which overlaps the diagnostic subject "umbrella".
- `tasks-v2.jsonl` replaces it with "lost glove". `tasks-v1` is preserved.
- No confirmation output exists.

**2026-10-31 18:40 EDT — Mistral tokenizer.**
- `model.tokenizer_loader: fast_json` loads the publisher's `tokenizer.json`.
- `consolidated.safetensors` and `params.json` (Mistral-native duplicates) were not downloaded; the full upstream metadata is kept as `publisher-metadata-full.json`.

**2026-10-31 19:00 EDT — instrument frozen before unseen scoring** (`judging/INSTRUMENT-FREEZE-v2.json`, hashes inside).
- **Calibration results** (3 replicates):

  | Judge | Presentation | 0–2 consistency | 0–4 consistency | Directional |
  |---|---|---|---|---|
  | Claude | solo | 16/16 | 34/36 | 20/20 on both |
  | Codex | batches of 12 | 14/16 | 35/36 | 20/20 on both |

- **Frozen choices.** Claude scores solo and Codex in batches of 12; both use the median of 3 replicates with the v2 prompts.
- **0–2 rubric.** Codex 0–2 is below the 90% screening target on calibration. It is carried to the unseen test unchanged and reported as it is. The 0–2 rubric is not part of the survival endpoint.

**2026-11-01 01:50 EDT — the single permitted revision cycle (0–4 endpoint rubric).**
- **Trigger.** On the v1 unseen split, Codex (batches of 12) failed content-preserving consistency at 26/36. Directional checks were 20/20. The inconsistent items differed by ±1 between batches, the same context effect Claude showed.
- **Revision.** Codex also scores one item per call (solo). Prompts (v2), three replicates and median aggregation are unchanged, so both families now share the same presentation.
- **Requalification.** Codex is requalified on a new unseen set, `materials/diagnostics_v2.py`: 12 examples, packet sha256 af625e63…, written before scoring. Only the 0–4 rubric is requalified.
- **Unchanged.** Claude's frozen solo instrument is unchanged and keeps its v1-unseen result. The failed v1 Codex result is preserved.
- **If the gate fails again.** No further revision is allowed. Measurement is then reported as unreliable for that family, and confirmation tasks are not spent on a claimed benefit.

**2026-11-01 02:20 EDT — endpoint instrument qualified and frozen** (`judging/INSTRUMENT-FREEZE-v3.json`).
- **Claude solo.** v1 unseen: 35/36 consistency, 20/20 directional.
- **Codex solo.** v2 unseen (the revision cycle): 36/36 consistency, 20/20 directional.
- **Historical 0–2 rubric.** Claude 14/16 and Codex 15/16 consistency, both 20/20 directional. This is only a partial validation, and the rubric is not used for the endpoint.
- **Lineage prompt.** It is not covered by the diagnostics. Its between-family agreement is reported instead.
- **Tool-use flag correction.** The flag had wrongly counted Codex transport notices ("Falling back from WebSockets to HTTPS") as tool use. Every archived event stream was re-checked: there were no command, file, web or MCP actions in any Codex call.

### 2026-11-01 03:05 EST — judge scheduling fix (no instrument change)
`judge.run_many` used one shared thread pool for both families, so while Codex waited on its usage limit (reset 6:28 AM) every thread slept and Claude calls starved. It now uses one pool per family, as its docstring said. Prompts, model settings, and parsing are unchanged. The running rate jobs were stopped and restarted; completed raw replies are reused and only missing calls are sent.

### 2026-11-01 06:50 EST — quota-message detection fix (no instrument change)
Claude CLI's limit message ("You've hit your 5-hour limit · resets 6:40am") did not match `judge.quota_wait`, so about 4,100 Claude content calls (and 83 in devqual) were stored as `failed` with no rating instead of waiting. The detector now also matches "hit your … limit" and "resets H:MMam". The failed records were moved unchanged to `survival/<label>/failed-attempts-archive/`, and the identical prompts were resent. No answer was discarded: those calls produced no rating.

### 2026-11-01 06:55 EST — test-3 decision rule, declared before any devqual outcome was computed
Devqual content ratings exist on disk, but no outcome, yield or branch comparison has been computed or viewed. Rule:
- For each of the 12 sources, compute the paired difference in primary yield (`yield_lo`, frozen rule: both families ≥3, lineage supported, no duplicate) between the `review` and `develop` branches.
- Choose `review` only if its mean exceeds `develop` by ≥0.5 ideas per chain (the protocol's worthwhile effect) **and** its delivered finals are not lower on average.
- Otherwise keep `develop`. It is the default, already used by both pilots, so the pilots stay matched to confirmation.

Report `yield_hi`, the per-family rules, and lineage classes descriptively. Six-to-twelve sources cannot establish that the branches are equivalent.

### 2026-11-01 — pilot judging suspended; assessment-unit mismatch audit
Recorded 2026-11-01T14:29:54.826796-05:00. This entry follows inspection of development scores and saved rationales.

- At David's request, stopped pilot-qwen3 and pilot-mistral rating jobs and their active children at 14:20:53 EST. Saved calls, score files, original prompts, and the instrument freeze are preserved. No new calls were requested.
- Offline analysis confirms zero devqual yield under the primary ≥3 rule and under the already-declared ≥2/both-judges sensitivity. Current pilot ratings cover initial ideas only; final content and lineage remain unrated.
- Concrete mismatch: each judge sees one extracted idea plus the original task requesting five. Saved rationales explicitly penalize the member for supplying only one. This can affect facet scores and constraint decisions; the audit does not claim it explains every low score.
- Prepared a scope-corrected prompt and packet preview as DRAFT_NOT_FROZEN_OR_QUALIFIED. Per-idea requirements are separated from whole-set cardinality/diversity. No active harness, rubric anchors, primary threshold, or legacy score was changed.
- Proposed lower-cost design: one prespecified call per idea per judge; a deterministic 10% repeat-audit subset scored with the same designated first-call primary rule. This is a proposal, not authorization to send calls.
- Any amended instrument needs fresh qualification including scope invariance and scale-validity checks, a new call-ID namespace, and a recorded adoption decision before pilot rejudging/confirmation. The prior single-revision allowance is not reset or described as passed again.
- Confirmation remains on hold. Do not resume the ambiguous legacy rating jobs. See output/rating-floor-audit-20261101/REPORT.md for exact counts, scope examples, budget, limitations, and source identities.

### 2026-11-01 — David authorizes scoped v4 and reduced-repeat judging
Recorded 2026-11-01T14:42:10.058916-05:00 before any v4 assessment.

- Authorization: David replied “Do it” to the scope repair, qualification, and lower-cost judging recommendation.
- Adopted pending qualification: explicit one-member scope, separate per-idea/set-level requirements, unchanged 0–4 anchors, unchanged ≥3/both-family yield, primary replicate 1 for every item, and a deterministic 10% repeat audit. Audit repeats do not replace primary scores.
- Preserve all v3 content/lineage records and its qualification history. v4 uses new content identifiers and a separate data namespace. Existing developer lineage may be reused only when its full prompt hash is identical; reused records carry their source path.
- Before running, froze 36 diagnostic presentations × two families = 72 assessments. Hard upper limit: 96 provider attempts including infrastructure retries. Checks cover assessment-scope invariance, repeatability, directional differences, explicit constraint violations, and criterion-facing positive/null cases. These are authored checks, not independently normed human creativity ratings.
- Both judge families must pass every prespecified gate before any pilot rejudging. A quota/auth block stops further submissions without sleeping or automatic quota retries. A failed qualification holds pilot rejudging; no prompt tuning or gate relaxation after viewing these diagnostic outcomes is authorized by this run.
- After qualification, the planned content assessments are 448 for developer qualification and 3,454 for the two pilots, including repeat audits. Pilot lineage adds at most 288 new calls; the unchanged 48 developer-lineage records may be hash-matched and reused. Total planned new assessments after qualification: 4,190; hard provider-attempt ceiling: 4,600. Any unused budget is not spent on additional analyses.
- Model choices and existing signed-in CLI authentication are unchanged; no new API key or provider-billing route is introduced. Requested models and reported identities remain recorded as before.
- Confirmation remains on hold; no confirmation task is evaluated, frozen for launch, or spent by this authorization.
- Instrument specification SHA-256: afd1cef87d37083445c9e92fa03b542f01b42d871d63dea0094d760e31207a6d.

### 2026-11-01 — scoped-v4 qualification stops on provider quota
Recorded 2026-11-01T14:45:18.918939-05:00.

- Two provider invocations: Claude returned its five-hour limit (reported reset 4:40 p.m. America/New_York); Codex completed its first assessment.
- The quota circuit breaker stopped all later submissions. No v4 pilot call, confirmation call, or background quota retry was launched.
- Qualification is incomplete, not failed. No v4 qualified freeze was issued. Prompts, authored checks, gates, and the adopted specification remain unchanged after the first responses.
- Explicit resume tooling archives quota-block records and preserves successful answers and total provider counters. It may be used after provider availability changes; no automatic resume is scheduled.

### 2026-11-01 — combined analysis identifies fused Mistral final members
Recorded 2026-11-01T14:59:39.240489-05:00 during the requested combined analysis.

- Ten Mistral final answers have explicit numbered sections 1–5 but are represented as one unstructured member. This accounts for 40 of the 41-member gap in old extracted counts; the remaining answer contains four explicit outputs with a stated merger.
- Recorded PILOT-DATA-HOLD.json and a gate in the normal resume coordinator before pilot judging. Diagnostic qualification may continue; no new calls were made during this analysis.
- This operational gate changes no prompt, scoring threshold, diagnostic expectation, frozen packet, or raw output. It prevents spending judge calls on known fused units until a separately documented extraction/dataset revision is prepared.
- The combined report distinguishes historical whole-answer comparisons from the compromised per-idea instrument. No unfavorable historical result is removed or replaced, and no corrected quality or lineage score is invented.

### 2026-11-01 16:48 EST — extraction rules v2 (source 1.4.2), fixed before any re-extraction
Prompted by David's combined report (`DREAM3-Combined-Analysis-2026-11-01/REPORT.md`, section 6) and the pilot data hold (`judging/scope-v4/PILOT-DATA-HOLD.json`).

**Defect.** Ten Mistral pilot finals with clearly numbered sections were stored as one `unstructured` member. A read-only header check over the Qwen devqual, Qwen pilot and Mistral pilot sets found no other cases. There were two causes:
- The final-stage number marker required `.`, `)`, `:` or `-` after the digit, so headers like `1 (Faithful Development from I1)` were missed.
- The final stage never accepted `I<n>` headers.

**Rules (format only; no semantic judgement).** These apply to the final stage only; initial-stage extraction is unchanged.
- **R1.** A top-level marker may also be a digit followed by whitespace and then `(` or `*`. Indented nested lists still never start a member.
- **R2.** If a final has no plain-number markers, top-level `I<n>` headers (n = 1–10) mark members.
- **R3.** A member whose header line contains "new idea" (case-insensitive) is recorded as a `final_new_idea` note with no source credit, as the finalizer prompt requires. A bare top-level "New idea" line still opens the trailing note, as before. Slots take the first five remaining members in reading order.
- **R4.** Sourced members beyond five are kept as `final_excess` rows. They are never slotted or judged as finals.
- Markers labelled 1–10 are accepted (previously 1–5), so a top-level "6." no longer extends member 5's span.
- Spans remain verbatim code-point slices. Nothing is merged, completed or rewritten.

**Use.** The rules are applied offline to the saved raw texts. Outputs go to `output/extraction-v2/`; original unit files and all legacy tables and scores are untouched. Confirmation will generate with 1.4.2. Any unit outside the ten held units whose extraction changes will be listed and explained before packets are rebuilt.

**Expected effect.** Six of the ten fused answers contain a section headed "New idea", so the number of recovered sourced members will be below the 40 visible-section figure in the combined report. The post-repair counts supersede that figure.

### 2026-11-01 16:51 EST — R3 refined after the audit gate fired (format only; no scores consulted)
The first re-extraction pass (kept at `output/superseded/extraction-v2-first-pass-R3-unrefined/`) changed 37 units outside the ten held ones. Nearly all came from R3.

**A second v1 defect.** Both models often labelled a numbered final member "(New Idea)". The v1 extractor counted these self-declared unsourced ideas as sourced finals, making them eligible for survival credit. The finalizer prompt asks for them to go in a separate "New idea" note. This affects:
- Qwen devqual: 10 units;
- Qwen pilot: 1 unit;
- Mistral smoke: 1 unit;
- Mistral pilot: about 25 units.

**Refinement.** Some headers combine the phrase with a source, e.g. "New Idea - Merger of I1 and I2" or "New idea derived from I3". R3 now marks a member as a note only when its header (first line, first 160 characters) says "new idea" **and** cites no I1–I5. A member that cites a source stays sourced, and lineage judges decide it. A test was added (129 total).

The re-extraction gate now requires every changed row to be explained by a named rule.

### 2026-11-01 16:52 EST — extraction-fidelity gate added to the queue
David noted that the smoke test should have caught this defect. It could have: the Mistral smoke unit `survival-dev-01__s11__high_temperature` produced text byte-identical to the held pilot unit, and v1 extracted 1 member from 10 visible headers. The smoke gate checked only exit codes, EOS and steering traces.

`Tools/Idea-Survival/check_extraction.py` now runs after every generation stage, from `run_queue.py`. It counts visible top-level headers independently of the extractor and halts the queue on any of three failures:
- **lost_members:** fewer members extracted than headers visible;
- **fused_answer:** an answer stored as unstructured despite visible structure;
- **unsourced_new_idea_slotted:** a scored slot holding an unsourced "New idea".

**Validated against the existing hubs:**
- Legacy v1 extraction fails as expected:
  - Mistral smoke: 2 units;
  - Mistral pilot: 31;
  - Qwen pilot: 1;
  - Qwen devqual: 10;
  - Qwen smoke passes.
- Every v2 re-extracted set passes.

### 2026-11-01 17:00 EST — per-launch call cap (operational; no instrument change)
At David's request, `resume_scope_v4_x2.py` sends at most 400 new provider calls per judge family per launch (`--launch-cap N` to change). Cached records are free. On reaching the cap the run stops cleanly with exit code 4; unsent calls leave no record, and rerunning the same command continues. The phase ceilings (96 for qualification, 4,600 for the pilot), the prompts, scoring and packets are unchanged. Tested in `judging/test_scope_v4_x2.py`.

### 2026-11-01 17:05 EST — readiness work (no data or instrument change)
- `analysis/describe_pilots.py` adds judge-free process and delivery descriptives from the v2 extraction (`output/pilot-descriptives-20261101/`).
- `run_queue.py` requires at least 129 tests on 1.4.2 hubs.
- `freeze_confirmation.py` gains `--dry-run`, and `analyze.py` gains `--base` for v4 outcome folders.
- `output/CONFIRMATION-READINESS.md` records measured GPU and judging costs.
- A manuscript revision proposal was written as a new file: `<private-notes>/manuscript/REVISION-PROPOSAL-2026-11-01-extraction-repair.md`. The manuscript itself is unchanged.

### 2026-11-01 17:18 EST — David's scope decisions for pilot and confirmation judging (before any v4 pilot or confirmation rating)
David: "rating the final ideas and submitting the thoughts for review by others with the paper is a valid way forward. Skip the 10%, run and judge qwen first. We want a strong paper."

1. **Final-stage content only.** Judges rate sourced finals and new-idea notes, plus lineage. Initial ideas are not judged.
   - The primary endpoint is unaffected: it uses final ratings and lineage only, and lineage reads the source text, not source ratings.
   - The secondary "initial qualifying" measures become unestimated; they are not zero.
   - Applies to the x2 pilot judging (`resume_scope_v4_x2.py --pools final`, the default) and to confirmation.
   - Pilot planned calls fall from 4,370 to 2,490.
2. **Release for outside review.** All raw chains (task, initial ideas, development, finals) go out with the paper, with conditions masked and a separate key, so others can review the material the judges did not score.
3. **10% repeat audit.** It is kept in the pilot, restricted to final-pool items, as the reliability estimate. It is **dropped in confirmation**.
4. **Sequencing.** Qwen3-8B confirmation is frozen, generated, judged and analysed first. Mistral confirmation is a separate later decision.

The instrument prompt, anchors, threshold, rule and packets are unchanged.

### 2026-11-01 17:19 EST — release packet for outside review
`analysis/build_release_packet.py` built `output/release-pilots-20261101/`: 144 complete pilot chains (both models), shuffled with seed 20261101. Each chain has the task, raw and extracted starting ideas, development, the raw final answer, extracted finals and notes, plus four open written questions in line with David's preference for open, lenient review. Model, arm, seed and unit IDs appear only in `output/private/release-pilots-20261101-key.csv`, which must never be shared before reviews are submitted. A leak scan found no condition labels in the shareable files. The Qwen confirmation chains will get their own release packet after generation.

### 2026-11-01 17:27 EST — precision decision rule, declared before any pilot rating under v4
`analysis/precision_check.py` runs on the Qwen x2 pilot outcomes (primary metric `yield_lo`, task-level seed-averaged differences). The tasks needed for a 0.5 half-width are computed with z = 2.2414 for C−A and C−B, at the observed SD and at 1.5× that SD. The result is used as follows:
- **Both primary contrasts "adequate" or "adequate only at observed SD":** freeze and run the Qwen confirmation with the 24 frozen tasks, reporting the 1.5×-SD figure as a caveat.
- **Either contrast "extension plan needed":** write a justified extension plan with new tasks disjoint from all used material, and bring it to David before freezing. Do not expand silently.
- **Either contrast "uninformative" (floor, ceiling or zero variance):** stop before the freeze and report it. An endpoint stuck at the floor cannot show a difference, and the threshold will not be lowered to escape it.

The Mistral pilot is computed and reported too, but only Qwen gates the Qwen confirmation (David: Qwen first).

### 2026-11-01 19:10 EST — scoped-v4 qualification failed (both families); no changes made
The frozen gates were applied unchanged, and neither family qualified:
- **Claude:** anchors 4/6.
- **Codex:** scope 12/18 and repeat 12/18.

Details are in `judging/scope-v4/QUALIFICATION-RESULT-20261101.md`. The pilot and confirmation stay blocked. Any revised instrument needs David's decision, new unseen qualification items, and its own freeze before it sees pilot data.

### 2026-11-01 19:35 EST — draft only
- `judging/scope-v5-DRAFT/PROPOSAL.md` describes a possible revised instrument. It is not frozen, and there are no calls.
- Paper text for the v4 failure was appended to the manuscript revision proposal.
- The Qwen confirmation GPU run is not started: the precision check that precedes the freeze needs a qualified judge, and David has not chosen between reporting without AI ratings and qualifying v5.

### 2026-11-01 ~20:00 EST — scoped-v5 adopted and frozen (David: "approve v5, run it"); no v5 response yet
Frozen by `judging/prepare_scope_v5.py`. The instrument spec is `judging/scope-v5/instrument-spec.json`, sha256 5938b6f126b594e5…

**Changes from v4 (as drafted in `scope-v5-DRAFT/PROPOSAL.md`):**
- A facet-separation rule: familiarity affects novelty only.
- Value-3 wording: a plain idea that workably addresses the task qualifies.
- Rule 5 tie-break is lenient: choose the higher level if substantially met.
- Scope and repeat agreement require the same ≥3 decision and no more than one step apart (gate ≥17/18 each).

**Qualification items:** 38 presentations, all newly authored; none of the v4 qualification text and no confirmation subject is reused. There are 8 anchors (4 plain-but-workable), with a gate of 7/8. Direction stays at ≥5/6 and scope constraints at 12/12.

**Resolving an ambiguity in the draft:** the draft said both "anchors ≥5/6" and "add 2 anchors". The frozen version uses 8 anchors with one miss allowed, matching v4's tolerance of one miss.

**Pilot packets:** the x2 packets were copied unchanged in content and item IDs into `scope-v5/<label>`, with their x2 source hashes recorded. Only the final pool is judged.

**Budgets:**
- Qualification: 76 assessments, at most 96 provider calls.
- Pilot: at most 4,600 calls, and 400 new calls per family per launch.

**If v5 fails:** stop and report it as the second failure. There will be no v6.

**Offline tests:** `test_scoped_judge_v5.py` passes 5/5. The v4 and x2 tests still pass.

**File hashes:**
- `rubric05_scope_v5.md`: 198ccf8e1c81f8fe…
- `scoped_judge_v5.py`: 0b19c0c7484325ea…
- `judge.py`: 9c420e7eba58cbb7…
- `survival_judging.py`: 2f2b3e2f56caee60…
- `lineage_v1.md`: 5fb3824843807c34…
- `resume_scope_v5.py`: 71df01d6d8a04f7e…
- `prepare_scope_v5.py`: 8ee30651bb5acf43…

### 2026-11-01 20:45 EST — scoped-v5 qualification: Claude pass, Codex fail (scope constraints 11/12)
The failure is on fixture XAG4Y6VDM, whose authored premise has a real rule gap (noted by Codex on 1 of 3 presentations). Per the pre-declared rule this is the second failure; nothing was altered. Details are in `judging/scope-v5/QUALIFICATION-RESULT-20261101.md`.

### 2026-11-01 ~21:00 EST — EXPLORATORY Claude-only ratings authorized (David: "option 2, run the Claude-only ratings")
- Scoped-v5 remains failed as a two-family instrument, and `INSTRUMENT-FREEZE-v5.json` does not exist.
- Claude alone passed every v5 gate. `judging/run_claude_only_v5.py` rates the final-pool items of the three v5 (x2-content) pilot packets with Claude only:
  - one primary call per item;
  - a 10% repeat audit;
  - one lineage call per chain;
  - a threshold of 3, with every component of the outcome rule decided by Claude.
- Planned: 1,245 calls (devqual 176, Qwen pilot 509, Mistral pilot 560), with a ceiling of 1,400 and 400 per launch. Outputs go to `judging/scope-v5-claude-only/`.
- The design record `scope-v5/EXPLORATORY-CLAUDE-ONLY.json` is written before the first rating and hash-checked on every launch.
- These are single-judge, exploratory results, **not** the pre-registered endpoint.
- They do not authorize the confirmation freeze: `freeze_confirmation.py` still requires `INSTRUMENT-FREEZE-v5.json`.
- The precision check may be run on them only as an exploratory illustration.

### 2026-11-02 ~02:50 EST — Claude-only runner amendment 1 (format deviation, no resampling)
- **Trigger:** one Mistral reply (`v5-final-XGC8TMM3M-r1`) was a single valid rating object without the code fence, so the runner halted.
- **Change:** the runner now keeps such a reply as the first answer and logs it in `scope-v5-claude-only/format-deviations.json`; any other defect still halts. The survival outcome code already used this object, listing `no_code_block` in `judging-issues.json`.
- **Record:** `scope-v5/EXPLORATORY-CLAUDE-ONLY-AMENDMENT-1.json` names the old and new runner hashes. The original runner is kept in `output/superseded/`.
- No rating was resampled or changed.

### 2026-11-02 03:00 EST — precision rule applied
On the exploratory Claude-only outcomes, every contrast in both pilots is "uninformative: floor". Per the rule declared on 2026-11-01 at 17:27, the confirmation is not frozen or run under this endpoint. Nothing about the endpoint or threshold was changed.

### 2026-11-02 — continuity study (plan approved by David): source 1.5.0, smoke criteria, pairwise-c1
- **Source:** `Code/DREAM-project-1.5.0-continuity-20261102`, 142/142 tests. It adds prefill-span steering (reading under steering) and a one-context continuity mode.
- **Smoke criteria:** fixed before generation in `output/continuity/SMOKE-CRITERIA.md`.
- **Pairwise instrument c1:** Claude only; `judging/pairwise_c1.py` and `prompts/pairwise_c1.md`. Frozen with 22 newly authored qualification presentations (`pairwise-c1/SPEC.json` 9e1ce2d68d3bf559…).
- **Qualification result:** directional 16/16 (gate ≥15) and identical-pair ties 6/6 (gate ≥4). **PASSED**, before any pilot pair existed.

### 2026-11-02 — continuity pilot complete; pre-registered rule applied
Results are in `output/continuity/PILOT-RESULTS.md`. Primary targeted-vs-random contrasts: tasks 3/2/1 in both modes, so no confirmation is proposed. The generate-mode artistic pattern is labelled post hoc.

### 2026-11-02 — EXPLORATORY: random vs baseline comparison (after seeing the pilot results)
- **Why:** perceive_targeted beat baseline 23–13 (tasks 4/0/2), but whether any perturbation during reading does the same is unknown.
- **What:** `judging/pairwise_c1_exploratory.py` compares perceive_random and generate_random against baseline with the frozen pairwise-c1 instrument (72 Claude calls).
- **Status:** not pre-registered, so it is labelled exploratory everywhere. Interpretation is written down now, before running:
  - perceive_random ≈ perceive_targeted against baseline means a generic effect of perturbing the reading;
  - perceive_random ≈ 0 against baseline would hint at direction specificity, to be tested prospectively.

### 2026-11-02 — exploratory results, human packet, manuscript draft
- **Exploratory comparison:** random vs baseline is 18–18 in both modes. In perceive mode the ordering is targeted > random ≈ baseline. Recorded in `output/continuity/PILOT-RESULTS.md`.
- **Human packet:** `output/release-continuity-pairs-20261102/`, 36 masked perceive-mode pairs with the same question as pairwise-c1. The key is in `output/private/` and must not be shared until readers submit.
- **Manuscript:** `manuscript/manuscript-v0.4-draft.md` (a new file; v0.3 files unchanged), plus the new figure `figures/figure-5-continuity-pairwise.*` (script `analysis/figure_continuity_pairwise.py`).

### 2026-11-02 — direction screen (source 1.5.1): no candidate passed; stopped as declared
Results are in `output/continuity/DIRECTION-SCREEN-RESULT.md`. Reading-only steering at λ ≤ 0.20 leaves 65–94% of greedy outputs unchanged for every direction, random included. D1 and D2 rank high on category change versus the random null, but neither passes the pre-declared rule. No re-screen with new metrics. Next step is David's decision.

### 2026-11-02 — direction screen dose extension started (David: option 1)
- **Criteria:** `output/continuity/DIRECTION-SCREEN-DOSE-EXTENSION-CRITERIA.md`, fixed before running.
- **Design:** λ 0.4, 0.6 and 0.8; candidates D1 and D2, reusing the exact 1.5.1 vectors (sha256 20ae0b89…); same metrics and pass rule.
- **Replication:** any passing cell must replicate on held-out object set B, with at most two attempts.
- **Runs:** source `Code/DREAM-project-1.5.2-dose-extension-20261102` (150/150 tests); hub `gpu/qwen3-dose-extension-20261102-115545`.

## 2026-11-02: dose extension run (David chose option 1)

- **Criteria:** `continuity/DIRECTION-SCREEN-DOSE-EXTENSION-CRITERIA.md`, fixed before the run. Source 1.5.2 is a new copy; 1.5.1 is unchanged.
- **Launch:** the first launch halted at argparse (negative `--layers` value) before any probe ran. It was resumed with `--layers=`, with no resampling.
- **Outcome:** D1 at −12/0.4 passed on set A, then failed the pre-declared set-B replication on abstractness. No second passing cell existed.
- **Decision:** applied as declared. This is the final screen, with no further doses or metrics. Result: `continuity/DIRECTION-SCREEN-DOSE-EXTENSION-RESULT.md`.

## 2026-11-02: write-time steering and prompt-wording screen (David chose option 2), recorded before any run

- **Criteria:** `continuity/WRITE-AND-PROMPT-SCREEN-CRITERIA.md` (sha256 7217678b32ffcaae3ea6c096c72b2cec947e84d9a68b1c90d542b0553c4fca9a). Hashed locally before data; this is not a public preregistration.
- **Scope:** this is a new question, not a re-screen of perceive mode, which stays closed.
- **Source:** 1.5.3 is a new copy of 1.5.2; 1.5.2 is unchanged.
- **Tooling:**
  - The new report script is `analysis/direction_screen_report_v2.py`; v1 is unchanged. Re-scoring the dose-extension data with v2 reproduces v1 exactly.
  - `run_screen.py` MIN_TESTS is 155 for 1.5.3; the earlier copy is in history/.

## 2026-11-02: write/prompt screen outcome

- **Method P:** P2 passed on set A and replicated on set B, so it is the validated manipulation (prompting, not steering).
- **Method W:** two set-A passes (D0 −4/0.4 and D2 −4/0.2) both failed set B; W is closed.
- **Run:** no halts. The chain ran exactly as scripted. Result: `continuity/WRITE-AND-PROMPT-SCREEN-RESULT.md`.

## 2026-11-02: Stage A categorization check (David's hypothesis; choices: steer-then-release, P2 as positive control, reviewers decided after Stage A), recorded before any run

- **Criteria:** `continuity/CATEGORIZATION-CHECK-CRITERIA.md` (sha256 2b74653314b3ee7ae70d149ab0f288256bb9b4523f71a0cc5ed61ee84010eff2). Hashed locally; this is not a public preregistration.
- **Scope:** these are new measures for a new hypothesis, tested on fresh object sets C and D only.
- **Source:** 1.5.4 is a new copy of 1.5.3; 1.5.3 is unchanged.
- **Embeddings:** GloVe 6B 300d is added under `materials/embeddings/` (free download; source and hash recorded).
- **Tooling:** `run_screen.py` MIN_TESTS is 160 for 1.5.4; the earlier copy is in history/.

## 2026-11-02: Stage A v1 withdrawn before scoring; v2 to follow an external methods review

- **Why:** David pasted a methods review asking that Stage A be tightened before freezing. The six points were: clearly inapplicable categories and a stated membership interpretation; fixed-temperature log-odds with several frozen question formulations; temperature as a comparator for associations only, frozen on calibration objects; a relevance safeguard for GloVe dispersion; separate measurement during steering and after release; and quantitative thresholds with object-level uncertainty.
- **What was stopped:** the v1 run, at 161 set-C records. No set-C/D outcome was inspected, and the v1 scorer was never run. See the hub's `output/WITHDRAWN.md`.
- **What carries over:** sets C and D remain fresh for v2, because no outcome data from them was seen.

## 2026-11-02: Stage A v2 criteria recorded before any v2 run

- **Criteria:** `continuity/CATEGORIZATION-CHECK-CRITERIA-v2.md` (sha256 63f77ff687ca2b4c5c677a708b24000c7db3be5bc79f7db7aedc9f5317c4110e). Hashed locally; this is not a public preregistration.
- **Source:** 1.5.5 is a new copy of 1.5.4; 1.5.4 is unchanged.
- **Scorer:** `analysis/categorization_check_report_v2.py`; v1 is unchanged and unused. Both of its stages were tested on synthetic data only.
- **Tooling:** `run_screen.py` MIN_TESTS is 160 for 1.5.5; the earlier copy is in history/.

## 2026-11-02T20:26:45Z: Stage A v2 calibration frozen before the test launch

- **File:** `CALIBRATION-FROZEN.json` (sha256 f07a390a1a542594863ac24fbd7adf9b4c297cbd3801f0d88fb73422bbd4e83c).
- **Chosen temperature:** T = 1.5.
- **Dispersion qualified:** True.

## 2026-11-02: Stage A v2 outcome

- **Run:** the test launch completed with 34,224 records, no halts, and was scored once with the frozen scorer.
- **Decision (as declared):** no demonstrated change, so the steering branch is closed.
- **Also reported:** the calibration temperature sat at the grid edge (under-matched), and the P2 positive control is non-selective.
- **Result:** `continuity/CATEGORIZATION-CHECK-v2-RESULT.md`.

## 2026-11-02: publication decision

- **Decision:** David confirmed submitting the documented negative result to TMLR now ("yes submit now"). This supersedes LIVE-DECISIONS D001 (Nov 1), which was to complete a usefulness comparison before public publication.
- **Submission source:** `manuscript-v0.7-merged.md`, which is the GPT preparation candidate plus the Claude additions.
- **Build and packet:** `<DREAM_HOME>/Publication/tmlr-2026-11-02/`.
