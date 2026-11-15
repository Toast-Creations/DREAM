# Larger extractor on a structural holdout (V1.19.0): frozen plan, pre-collection

- **Brief:** `LARGER-EXTRACTOR-STRUCTURAL-HOLDOUT-BRIEF.md` (copy in `design/BRIEF-copy.md`).
- **Scope.** Implementation, validation, familiar smoke, resource forecast and freeze. **Main collection is not
  launched**: it waits for David, together with `config/AMENDMENT-01-PROPOSED.md`.
- **Freezing.** This plan is hashed in `config/FROZEN-PROTOCOL.json`.
- **Predecessor.** 1.18.0 is uncommitted. Its notes (19 raw false revisions in the controls) are in that hub's
  `ERRATA.md`. The research report keeps its appended corrections.
- **Source.** `Code/DREAM-project-1.19.0-larger-extractor-holdout-20261106` is 1.18.0 plus:
  - `src/tempo/holdout.py`: the HOLD-v1 corpus and prompt builder;
  - `src/tempo/holdeval.py`: the HOLD-EVAL-v1 scorer, independent temporal reference and replay;
  - `src/dream_core/modeling_q.py`: the QLOAD-NF4-v1 loader. The V1.1 loader is unchanged and still refuses
    quantized checkpoints;
  - `scripts/hold_{generate,validate,run,analyze}.py`;
  - `tests/test_holdout.py`.

  Every 1.18.0 file is byte-identical, including `factored.py` (FACT-v1 frozen), `assertions.py`, `tempo_run.py`,
  `contract_validate.py` and `fac_analyze.py`. Tests: 220/220.
- **Environment.** One package was added to the shared research venv: **bitsandbytes 0.48.2** (pinned wheel,
  `--no-deps`). A `pip freeze` diff shows no other change. Weights for Qwen3-32B were downloaded at the pinned
  revision and every file was verified against the publisher hashes (`DREAM-models/Qwen3-32B/model-provenance.json`).

## Interface and models
- **FACT-v1, frozen.** The instructions, generic schema, nullable priors, normalisation, R1–R3 and single-act
  compiler are byte-identical to 1.18.0. The FULL raw prefix is used, with the target report last. No canonical
  prefix or earlier interpretation enters model context.
- **Models:**

| Arm | Checkpoint | Revision |
|---|---|---|
| SMALL | Qwen/Qwen3-8B | `b968826d…` |
| LARGE | Qwen/Qwen3-32B | `9216db57…` |

  `tokenizer.json` is byte-identical between the two.
- **QLOAD-NF4-v1, identical for both:**
  - bitsandbytes NF4 with double quantization, BF16 compute and BF16 non-quantized modules;
  - batch 1; `device_map {"": 0}`, so any module off the GPU is an error; low-memory streaming; `sdpa` attention;
  - thinking disabled through the publisher chat template; greedy decoding, **256** generated tokens;
  - **input ceiling 2,048 tokens**, with no truncation (an over-limit call is recorded as `input_too_long`);
  - one content attempt per call, with an infrastructure-only resume.

  Runtime versions, devices, load time and peak host and GPU memory go to `stages/*/LOAD.json`.
- **What is compared.** The primary is LARGE NF4 against SMALL NF4. It is not compared with historical 8B BF16
  results, and it does not isolate parameter count from every checkpoint difference.

## Structural holdout (HOLD-v1)
- **Inventory.** `design/CONSTRUCTION-INVENTORY.md` was written before any output. It shows that the only inspected
  identity constructions are explicit names and the one-hop "part whose stock was checked in rK".
- **Primary families.** Each is absent from that inventory:

| Family | Dependency |
|---|---|
| F1 | two-hop report reference |
| F2 | slot-occupancy → stock field join |
| F3 | historical occupant at a named time, never the latest |
| F4 | selection by measurement order, opposite to reception order |

- **Structure per group.** 4 acts (arrival, observation, removal, genuine correction) × 2 alternative histories,
  with different bindings, **byte-identical target wording** and an identical registry. The histories differ only
  by which part fills fixed record positions. The correction revises the selected part's own provisional claim, so
  it concerns the selected field in both histories.
- **Strata.** 8 = family × target reception (immediate; delayed by 2). Each stratum has 8 groups that enumerate
  three secondary factors exactly once each:
  - the order of X's records against the competitor's;
  - a stated or unstated event prior;
  - a finite or open correction interval.

  A competitor extra mention appears when the first two factors differ.
- **Calibration** (familiar, secondary): 8 explicit-name groups and 8 one-hop groups.
- **Smoke** (familiar only): 4 groups.
- **Redraws.** 18, all under model-independent construction checks, logged in the commitment.

| Component | Groups | Targets | Calls (2 models) |
|---|---|---|---|
| Primary holdout | 64 | 512 | 1,024 |
| Calibration | 16 | 128 | 256 |
| Smoke | 4 | 32 | 64 |
| **Total** | 84 | 672 | **1,344** |

- **Scheduling.** Sequential model blocks: SMALL first, then LARGE. Within-model permutations are frozen (seeds
  20261611 and 20261612; `order: as_committed`). Prompts are byte-identical across models and unique within each.
- **Budgets.** Every prompt and every canonical FACT-v1 output was tokenized under both tokenizers. The limits are
  2,048 in and 256 out (`phase0/*/VALIDATION.json`).

## Evaluation (HOLD-EVAL-v1; historical scorers unchanged)
- **Exact source meaning** requires all of the following:
  - the reply compiles to one act and is accepted by the unchanged contract over the canonical prefix (evaluator
    only);
  - rid, received_at and status are correct;
  - the reduced claims equal the canonical meaning: event field, time and result; a stated prior equal to the
    source; an unstated prior null or correct; the state field, time and value; the revision target, value,
    **valid_from and valid_to**;
  - no extras.

  Pending, rejected, malformed and truncated replies are incorrect. Quotation validity is scored separately.
- **Temporal replay.** Engine answers are compared with an **independently written** contract-v1 reference, using
  case-specific queries:
  - **Q_hist:** the anchor time, with all evidence;
  - **Q_now:** time 12, for events, observations and open corrections;
  - **Q_before:** the event time, or valid_from, using only what was known before reception;
  - **Q_unaffected:** for finite corrections, the later unaffected field.
- **Gate H1.** Canonical replies score exact and canonical replay equals the reference for all targets; this
  passed. Replay of predicted meanings is an accuracy outcome.
- **Proposed amendment 01.** The frozen contract has no `valid_to`, so there is no query after a finite interval's
  end. Both boundaries are scored in meaning.

## Primary, secondaries and interpretation (fixed now)
- **Primary:** LARGE − SMALL exact meaning on the 64 holdout groups. Average the 8 targets within each group, then
  the group differences. Paired group bootstrap within the 8 strata, 10,000 resamples, seed 20261106. **n = 64
  groups**, conditional on the four authored families. Report absolute accuracies and paired target counts.
- **Mandatory secondaries:**
  - every act, family and reception;
  - correctness on both histories per act and group;
  - binding before compilation and after acceptance; slot fields claimed;
  - raw, mixed or rejected, compiled and accepted false revisions;
  - event omission and accepted state-only events; a correct endpoint that is not exact;
  - revision target, start and end (finite only); stated-prior, event-time and reception-time errors;
  - acceptance and pending codes; quotation validity; replay;
  - calibration, and each model's holdout-minus-calibration difference;
  - all disagreements; tokens, truncations, latency, load time, peak memory, attempts and completion.
- **Interpretation:**
  - A positive complete primary with its interval above 0 supports the larger quantized checkpoint under FACT-v1
    on this authored holdout. Class losses and accepted false claims remain part of that result.
  - An interval including 0 is inconclusive.
  - Nothing here measures a scaling law, a quantization effect, a 32B threshold, action safety or utility.

## Resource limits and stop
- **Collection cap:** at most 12 h of smoke plus main inference, forecast from the familiar smoke including loads.
- **Infeasibility.** If 32B NF4 cannot load GPU-only, or cannot complete the smoke, the study stops and reports
  that. No substitute model, quantizer or offload is used.
- **Stop after the freeze.** Main collection waits for David.

## Brief addendum (Nov 6 process update), incorporated before the freeze
- **Brief versions:** `design/BRIEF-copy.md` (original, sha256 ee1602414d2a2116…) and `design/BRIEF-copy-v2-addendum.md`
  (with §8, sha256 473d8878046bc55e…). Both are hashed in the freeze.
- **Artifacts:** `design/READER-TAKEAWAY.md`, `design/CLAIM-EVIDENCE.md` (planned; estimates are filled in only after
  collection) and `design/SEMANTIC-COVERAGE.md`, with mutation records in `phase0/*/COVERAGE.json`.
- **Reported separately:** extraction exactness, compilation loss (also on canonical replies, 80/640) and
  restricted replay. The primary is computed as `exact_extraction`, as `exact_end_to_end` and as a no-finite
  sensitivity. **Which one is the primary waits for David's decision on amendment 01.**
- **Records, not tense.** Each completed step is backed by a record:
  - download: `DREAM-models/Qwen3-32B/model-provenance.json` and `download.log`;
  - validation: `phase0/*/VALIDATION.json`;
  - coverage: `phase0/*/COVERAGE.json`;
  - smoke: `stages/smoke-*/END.json`, `LOAD.json` and the logs;
  - freeze: `config/FROZEN-PROTOCOL.json`.

  Any statement in this plan without a record is a plan, not a result.
