# Study index

Each row links to the study's report in [`results/`](../results/). The reports are copied unchanged from the run folders, except that local absolute paths are replaced with placeholders: `<DREAM_HOME>` is the project folder, `<DREAM_MODELS>` the model store, `<venv>` the Python environment. Where a study has errata, the [errata files](../results/ERRATA/) or the hub's `ERRATA.md` take precedence over the report text.

"Version" is the source version used for the study. Every version's code is folded into the single current package in `src/`; the per-version copies stay in the project's private archive.

**Reading the status column.** *Development* means exploratory, tuned on the data it reports. *Frozen* means the plan and analysis were fixed before the data were opened. *Confirmation* means fresh data under a frozen plan.

## Creativity steering (DREAM, DREAM3)

| Version | Study | Status | Result (scoped) |
|---|---|---|---|
| 1.1.3 | [Qwen3-8B pilots, thinking off vs on](../results/qwen3-pilots-20261029-232548/REPORT.md) | Development | No steering effect; DREAM 2 learning memorised instead of learning rules; thinking-on runs cut off by the 1,024-token cap |
| 1.1.4 | [Five Related Things: reasoning on vs off](../results/concept-reasoning-20261030/README.md) | Development | No clear quality advantage: preliminary score 5.17/10 with reasoning vs 5.00 without, on 6 concepts, from one AI-assisted blinded reviewer ([protocol 16](protocols/16-Concept-Comparison-Results.md)) |
| 1.3.1 | [Thinking pilots](../results/qwen3-thinking-20261030-230519/REPORT.md) | Development | DREAM exploration needs ~3–5.5k thinking tokens; greedy anchors loop at 8,192; DREAM 2 still no rule learning |
| 1.3.2 | [Sampled-anchor baseline](../results/qwen3-thinking-20261031-083543/REPORT.md) | Development | Sampled anchor removes the greedy loop |
| 1.4.x | [Idea-survival pilots, Qwen3-8B and Mistral-7B](../results/idea-survival-20261031/RESULTS-SUMMARY.md) | Development | 144 chains executed. Judge instrument scoped-v4 [failed qualification](../results/idea-survival-20261031/SCOPE-V4-QUALIFICATION-RESULT-20261101.md); scoped-v5 [Claude-only exploratory ratings](../results/idea-survival-20261031/SCOPE-V5-EXPLORATORY-RESULTS.md): 0 qualifying finals in every arm |
| 1.5.0 | [Continuity pilot](../results/idea-survival-20261031/PILOT-RESULTS.md) | Pre-registered pilot | Targeted vs random 22–14 (perceive mode), not confirmed; an author masked review did not reproduce it |
| 1.5.1–1.5.2 | [Direction screen](../results/idea-survival-20261031/DIRECTION-SCREEN-RESULT.md), [dose extension](../results/idea-survival-20261031/DIRECTION-SCREEN-DOSE-EXTENSION-RESULT.md) | Frozen criteria | No direction beat random directions and replicated |
| 1.5.5 | [Categorization check v2](../results/idea-survival-20261031/CATEGORIZATION-CHECK-v2-RESULT.md) | Frozen criteria | Targeted steer-then-release *tightened* membership; prompt control changed categories but not selectively |
| — | [Manuscript v0.7](papers/manuscript-v0.7.md) | Paper | Pre-specified negative result (Studies 1–4) |
| — | [DREAM3 proposals E1–E6](proposals/README.md) | Not run | Designs only |

## Reversible learning (DREAM2, explicit context)

| Version | Study | Status | Result (scoped) |
|---|---|---|---|
| 1.6.0–1.6.4 | [Explicit-context adapters](../results/explicit-context-20261104-120916/RUN-STATUS.md) ([S48 report](../results/explicit-context-20261104-120916/S48-REPORT.json), [seeds/donors](../results/explicit-context-20261104-120916/SEEDS-DONORS.json)) | Development; sealed set never opened | Adapters learn support examples. Held-out complete-pair W+A−W +0.056 [−0.007, 0.132], and a wrong-episode adapter does about as well, so the gain is not episode-specific. Recipe stopped |

## Temporal state tracking

| Version | Study | Status | Result (scoped) |
|---|---|---|---|
| 1.7.1 | [Temporal pilot](../results/temporal-pilot-20261104-232811/MORNING-REPORT.md) ([errata](../results/temporal-pilot-20261104-232811/ERRATA.md)) | Development | History condition over-abstains ("observe first" 195/216) |
| 1.7.2 | [Diagnostic](../results/temporal-diagnostic-20261105-081325/REPORT.md) | Development | Policy wording fixes much state-condition abstention; precondition reasoning is the gap |
| 1.7.4 | [Precondition probe](../results/temporal-precondition-probe-20261105-085932/REPORT.md) | Development | Checklist-first fixes applicability 24/24 vs 1/24 |
| 1.8.0 | [State engine v0.1](../results/temporal-state-engine-20261105-095845/ENGINE-REPORT.md) | Validation, no model calls | 0 fixture disagreements |
| 1.8.1 | [History interpretation](../results/temporal-history-interpretation-20261105-100708/REPORT.md) | Development | Final state: structured 24/24, extracted 20/24, raw 10/24 |
| 1.8.2 | [Repair + prose](../results/temporal-repair-prose-20261105-111843/REPORT.md) | Development | Retry fixes conventions only; errors are semantic |
| 1.9.0 | [Event contract + observation policy](../results/temporal-contract-policy-20261105-121257/REPORT.md) | No model calls | Selective verification best (utility 3.54 vs 3.00) |
| 1.9.1 | [Text-interface policy](../results/temporal-text-policy-20261105-124150/REPORT.md) | Development | Policy benefit survives text (+2.04) |
| 1.10.0 | [Deferred-goal transfer](../results/temporal-deferred-goal-20261105-154052/REPORT.md) ([errata](../results/ERRATA/1.10.0-deferred-goal.md)) | Frozen plan, development | Text loss grows when the goal changes (selective policy B−A −0.83 [−2.17, 0.25], interval crosses 0); arrival/delivery wording read as state |
| 1.11.0 | [Dependency recovery](../results/temporal-dependency-recovery-20261105-170340/REPORT.md) | Development | Scoped-strict +0.56 [0.15, 1.10]; no false permissions |
| 1.12.0 | [Observation freshness](../results/temporal-observation-freshness-20261105-213302/REPORT.md) ([errata](../results/ERRATA/1.12.0-observation-freshness.md)) | No model calls | Correctness gates pass; primary −0.33 [−1.38, 0.67], inconclusive |
| 1.13.0 | [Query timing](../results/temporal-query-timing-20261105-221636/REPORT.md) ([errata](../results/ERRATA/1.13.0-query-timing.md)) | No model calls | Primary +0.46 [−0.42, 1.40], inconclusive; break-even λ* = 1.23 |
| 1.14.0 | [Dependency-aware query selection](../results/temporal-dependency-query-20261105-225524/REPORT.md) ([notes](../results/ERRATA/1.14.0-dependency-query.md)) | Frozen, no model calls | +2.46 [1.58, 3.35] over base; +1.65 [1.13, 2.15] over random |
| 1.15.0 | [Frozen-text integration](../results/temporal-frozen-text-integration-20261105-231937/REPORT.md) | Frozen | Text +2.19 [1.15, 3.27]; structured +2.67 |
| 1.15.1 | [Text replication, 768 worlds](../results/temporal-text-replication-20261105-233535/MORNING-REPORT.md) ([errata](../results/ERRATA/1.15-frozen-text.md)) | Frozen replication | Text +1.95 [1.87, 2.04]; 5 unsafe goal copies traced to wrong-field extractions |
| 1.16.0 | [Nullable prior](../results/temporal-nullable-prior-20261106-063446/REPORT.md) ([notes](../results/ERRATA/1.16.0-nullable-prior.md)) | Frozen | +0.043 [0, 0.13], inconclusive |
| 1.17.0 | [Record context FULL vs LOCAL](../results/temporal-record-context-20261106-075907/REPORT.md) ([notes](../results/ERRATA/1.17.0-record-context.md)) | Frozen | Arrivals +0.175 with LOCAL, but removals −0.24 and corrections −0.15 |
| 1.18.0 | [Factored assertions](../results/temporal-factored-assertions-20261106-101739/REPORT.md) ([notes](../results/ERRATA/1.18.0-factored-assertions.md)) | Frozen | Macro +0.156 [0.125, 0.185]; invented revisions remain on controls |
| 1.19.0 | [Larger extractor, 8B vs 32B](../results/temporal-larger-extractor-20261106-123049/REPORT.md) | Frozen holdout | Exact extraction 0.346 → 0.688 |
| 1.20.0 | [Reference resolution](../results/temporal-reference-resolution-20261106-171704/REPORT.md) | Frozen | +0.117 [0.065, 0.169]; arrivals flat |
| 1.21.0 | [KEEP+ID development](../results/temporal-keepid-dev-20261110-104944/REPORT.md) | Development | KEEP−SUB arrivals +0.203 [0.063, 0.344] |
| 1.22.0 | [KEEP+ID confirmation](../results/temporal-keepid-confirm-20261110-150658/REPORT.md) | Confirmation | **Not qualified** |
| 1.23.0 | [Revision-value clarification](../results/temporal-revision-value-clarification-20261111-015000/REPORT.md) | Pre-specified development | Clarified KEEP wording: exact +11.46 pts [6.25, 16.67], withdrawn-value errors −11.46 |
| 1.24.0 | [Clarified KEEP confirmation](../results/temporal-clarified-keep-confirm-20261111-063336/REPORT.md) | Confirmation | **Qualified:** arrivals +26.56 pts (LB +17.6); corrections within tolerance; 4 wrong bindings, all KEEP_CLAR |
| IGUARD-v0.1 | [Identity-guard replay](../results/temporal-identity-guard-replay-20261111/REPORT.md) ([verification](../results/temporal-identity-guard-replay-20261111-verify-e24e9ed/REPORT.md)) | CPU replay on saved outputs | Rejection-only identity guard; technical readiness criteria pass; prototype only |
| 1.25.0 | [Explicit-subject development](../results/temporal-explicit-subject-dev-20261111-210104/REPORT.md) | Development | Explicit-subject sentence: no arrival gain (−0.35 pts [−4.51, 3.82]); new failure types flagged for review |
| 1.26.0 | [Event-report development](../results/temporal-event-report-dev-20261112-070245/REPORT.md) | Development | Does not warrant confirmation |
| 1.27.0–1.28.0 | Event suite: [A confirm](../results/temporal-event-suite-20261112-195430/A-confirm/REPORT.md), [B narrowed](../results/temporal-event-suite-20261112-195430/B-narrowed/REPORT.md), [C wrong-binding](../results/temporal-event-suite-20261112-195430/C-wrongbind/REPORT.md) | Back-to-back chain | A: new failure types to review; B: does not warrant; C: descriptive |
| 1.29.0 | [EVTT development screen](../results/temporal-evtt-screen-20261114-052124/REPORT.md) | Development | Combined event + state-time sentence: arrivals 475/480; warrants a confirmation design |


A literature status note for this line, with its later corrections, is in [docs/notes/temporal-extraction-literature.md](notes/temporal-extraction-literature.md).
