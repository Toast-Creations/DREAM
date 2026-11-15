# Experimental Protocol

**V1.1.4 update — October 30, 2026.** The new direct five-association study has its own fixed [protocol](13-Concept-Association-and-Reasoning-Study.md): zero-steering reasoning on/off, matched sampling/caps, six development concepts, five explained items, blinded relevance-gated quality, concept-level paired analysis and separately reported costs. The older numeric/staged protocols below remain distinct. V1.1.4 numeric composition probes are now unique, varied-input and protected against copy-input/sign-flip shortcuts.

This protocol separates wiring checks, exploratory pilots, validation selection, and final testing. It defines what the code does and what still requires a study-specific decision.

## Stage sequence

First run the regression suite, then the optional tiny Qwen2 model tests with ML coverage required. Next run a small local open-weight smoke experiment to verify memory, tokenization, gradients, raw records, and rollback. Exploratory pilot outcomes may guide design. Freeze a confirmatory plan before opening final-test results.

A completed shell command is not proof of learning. For DREAM 2, qualify ordinary unsteered adaptation as a learnability positive control. A failing baseline warrants diagnosis before a larger steering comparison; it does not logically prove that an intervention could never help.

## Shipped fixture sizes

The full DREAM 2 fixture contains 12 worlds for each of development, validation, and test. The smoke fixture contains one per split. These sizes are practical fixtures, not a power calculation. Generate larger independently seeded files when designing a study.

Each world has twelve exposure examples and twenty-five evaluation probes: three direct, three paraphrase, four composition, six balanced contradiction, three scope, four anchors, and two lookup queries. The code is the authoritative source if this schema changes; document changes and regenerate provenance.

The DREAM 1 fixture contains six tasks per split spanning analogy, symbolic design, algorithms, exact arithmetic, reasoning, and fictional-system synthesis. The smoke fixture retains the exact-arithmetic negative control. Split variants are related tasks, so they should not be mistaken for unrelated domains.

## Scoring contract

Ask for one JSON object containing only the answer key. The scorer also accepts a complete plain integer or complete Boolean token. Strings are case-sensitive and must match exactly. It rejects multiple answers, narrative explanations around a number, duplicate JSON answer keys, extra keys, float-as-integer values, wrong signs, and yes/no prefixes embedded in words.

Format failure counts as incorrect and is logged separately. Preserve raw output so a parser change can be audited, but do not silently rescore a final study with an improved parser after viewing effects. Version the scorer and report any sensitivity analysis as such.

## Paired comparisons

DREAM 1 compares nonzero steering with zero steering through the same prompts and stages. The temperature pipeline changes only exploration temperature. Report stage-specific token counts and realized steering traces. Blinded human ratings remain external to the runner.

DREAM 2 pairs conditions within each world and adapter seed. Ordinary learning at the same eta is the principal contrast. The four-cell interaction is secondary unless explicitly made primary. Preexposure is a redundant-state control. Every arm has two forward exposure phases; update counts match for a fixed eta and step setting. Actual wall time and token counts may differ.

The optimizer, clipping, precision, target modules, sequence cap, loss mask, and experience order must be the same across paired arms. Default AdamW has zero weight decay. SGD is available for studies where an update-space interpretation is important, but exact norm matching is not implemented.

## Independent units and uncertainty

Questions in one world share rules, and seeds in one world share a task distribution. Do not treat all query rows as independent observations. The included exploratory summary averages seed-level paired composition gains within each world and bootstraps worlds.

A confidence interval is omitted for one independent world. Bootstrap intervals are exploratory, not a power analysis or a corrected multiple-testing procedure. With several doses, models, layers, and outcomes, preregister one primary contrast or a multiple-comparison policy.

DREAM 1 should be analyzed with task-level paired effects and reviewer uncertainty. Embedding distances must be computed within tasks if added later; no calibrated semantic-entropy estimator is included.

## Validation and final test

Choose layers, directions, dose regions, and operational thresholds using development data. Use validation episodes for explicitly planned selection. Keep final-test episodes closed until the plan and code versions are frozen.

Adapter selection, serialization checks, and final scientific evaluation are different decisions. A candidate reload check reuses its validation world to test persistence and does not constitute independent generalization evidence.

## Outcomes and exclusions

Report direct, composition, paraphrase, contradiction, scope, anchor, lookup, format validity, update counts, losses, pre-clipping gradient norms, and adapter displacement separately. Report failures and incomplete trials alongside completed trials.

Only preregistered exclusions may remove a run. OOM, timeout, invalid references, and numerical failure are recorded as invalid runs; they do not become hidden missing data. Stop after the fixed budget or declared failure criterion. Do not extend sampling until an attractive dose appears.

No numerical efficacy or retention threshold is universally justified by this package. Complete the preregistration worksheet and justify sample counts before a confirmatory study.


## Additional comparisons proposed by the October 29 literature revision

Before treating a new phase as confirmatory, specify matched random/noise interventions, a NEFTune-style training-noise baseline, attention-temperature exploration, and equally budgeted reflection/search as appropriate to its hypothesis. Add learning-rate and update-magnitude comparisons when claiming an effect beyond stronger optimization. These additions are proposals; the shipped configs do not silently acquire new conditions.

Define intervention timing and learning timing independently. For a delayed-learning arm, identify the exact verified mediator that survives exploration and match access to it across conditions. Evaluate after hook removal and fresh cache/context construction. Keep concept transfer, lexical diversity, correctness, false-rule learning, and regression separate. Cite the [methods catalog](12-References-and-Method-Credits.md) when preregistering these comparisons.
