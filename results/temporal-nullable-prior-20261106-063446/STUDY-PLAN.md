# Nullable-prior extraction interface test (V1.16.0): frozen plan

- **Brief:** `NULLABLE-PRIOR-EXTRACTION-TEST-BRIEF.md` (copy in `design/BRIEF-copy.md`). Development diagnostic.
- **Freezing.** This plan is hashed in `config/FROZEN-PROTOCOL.json` before the main collection. Amendments go to `config/AMENDMENTS.md`.
- **Predecessors.** 1.15.0 and 1.15.1 are preserved as `e85a670`, with notes in `ERRATA/1.15-frozen-text.md` and N2 (`613d0e3`). The notes cover:
  - the qualified cost claim;
  - the 5 unsafe (block, world, goal) cases, which are 18 unsafe executions (12 invalid, 6 false completions) and are not independent incidents and not a risk estimate;
  - the b021/a04/B cause (slot empty, part not on hand);
  - the scope of the bottleneck claim.
- **Source.** `Code/DREAM-project-1.16.0-nullable-prior-20261106` is 1.15.1 plus:
  - `src/tempo/nullprior.py` (the interface pair, the 96-world rows, family ids);
  - `scripts/nul_{generate,validate,evaluate,analyze}.py`;
  - `tests/test_nullprior.py`;
  - one opt-in line in `scripts/tempo_run.py`: config `"order": "as_committed"` runs calls in the committed order instead of the seeded shuffle. Configs without the key behave exactly as before. Decoding and model handling are unchanged.

  Every other 1.15.1 file is byte-identical.
- **Tests.** 200/200 pass (`test-results/tests-1.16.0.txt`).

## Question and the single controlled change
- **Question.** Does advertising the legal null prior change the event-versus-state interpretation of stock-arrival prose?
- **ORIGINAL** is the frozen 1.15.1 prompt, byte-identical. This was re-verified against all 148 committed calls of overnight block b001.
- **NULL_PRIOR** is the same prompt with exactly one replacement, checked line by line with `difflib` in every prompt:
  - the payload line advertises `"from": "<value>" or null` for change and uncertain_change;
  - one added line follows it: *"For change and uncertain_change, include the from key. If the new record does not explicitly state the prior value, use JSON null. Otherwise transcribe the stated prior value."*
- **Shared:** source prose, historical context, header, registry, system message, model, decoding, adapter-v1 (a missing ordinary `from` key stays unmapped in both arms), engine, selector and temporal rules.
- **Not added:** arrival examples, trigger words, a source validator, quoting changes, context removal or correction changes.
- **Model.** Qwen3-8B `b968826d…`, BF16, thinking off, greedy, 256 tokens. Each report gets one fresh call per interface. There is no content retry, no best-of selection, and one infrastructure retry is allowed (the 1.11.0 configuration).
- **Schedule.** A precommitted balanced schedule: reports in a seeded order (seed 20261106), with the interface order alternating pair by pair. Main: each quarter of the run is exactly balanced, and each interface goes first in half of the pairs (`phase0/VALIDATION.json` §8).

## No-model checks (passed before collection)
`tests/test_nullprior.py` and `phase0` confirm:
1. A `from: null` stock event maps, is accepted, and gives the same current result as the canonical record.
2. The source-aware scorer credits a correct null-prior stock event.
3. A stated prior (crate location) is still required; dropping it is labelled `dropped_explicit` and not credited.
4. A missing `from` key is unmapped; uncertain-change behaviour (M1) is unchanged.
5. The only prompt difference is the declared one; prose and context are byte-identical.
6. Wrong-field, wrong-kind and state-for-event errors stay visible even with an exactly quoted source. All 5 overnight unsafe interpretations are flagged as fixtures (not exact, wrong field, quote present). They are not new model evidence.
7. ORIGINAL regression; channel plumbing, perfect parity and immutable history as in 1.15.

## Panel and workload (committed)
- **Main `nul`:** 96 worlds = 4 fresh instances of each of the 24 fixed families. 48 per domain. Seed 20261301. 29 redraws, all under the existing rules.
- **Reports:** 584. Source-kind counts:

| Source kind | Count |
|---|---|
| Location observation | 196 |
| Location change | 84 |
| Stock observation | 122 |
| **Stock arrival** | **23** |
| **Stock removal** | **16** |
| Slot observation | 96 |
| Slot change | 31 |
| Uncertain change (location / slot) | 8 / 8 |

- **Calls:** **1,168** (2 × 584), under the ceiling of 1,536.
- **Smoke `nulsmoke`:** 4 disjoint worlds, 48 calls, under the ceiling of 64.
- **Allocation.** Every instance reproduces its family's 1.14.0 per-copy structure (validation 5).
- **Downstream:** DEPENDENCY on structured, ORIGINAL and NULL_PRIOR × goals A/B × stable/changing = **1,152 trajectories**. Each interface's own stream drives Q0, S2, selection and post-query projection. Clones are isolated per interface and goal.
- **Time.** The forecast is about 1 h at 3.0 s per call. The overall cap is 2 h, and the runner budget is 6,600 s. An incomplete run is preserved and reported as incomplete.

## Software gates (stop, preserve and repair under a new version on failure)
- **S1:** the reference agrees given each channel's evidence.
- **S2:** the structured channel is safe.
- **S3:** the selector rule and independent check hold.
- **S4:** perfect parity, and gold-poisoning invariance for both interfaces.
- **S5:** clocks, fees, receipts and per-interface context isolation, history, invariants, cost identity, shared actual state and readings, tape independence, channel lengths.

Wrong parsed beliefs and actual-world harms are outcomes, not gate failures.

## Outcomes (fixed now)
- **Primary:** NULL_PRIOR − ORIGINAL in source-aware exact meaning (`denotation_equal`, unchanged), as a ratio over all **23** stock-arrival records. Also reported:
  - the paired 2×2 table (both correct, ORIGINAL only, NULL_PRIOR only, neither);
  - event-kind accuracy separately;
  - per-family arrival counts.
- **Interval:** resample worlds within each of the 24 families, preserving family size and keeping all records, goals and interfaces together. 10,000 resamples, seed 20261105.
- **Secondary:**
  - exact meaning, kind, field attribution, result, meta and acceptance by source class (removals, observations, crate and slot changes, uncertain changes);
  - prior use: null, correct, incorrect or `dropped_explicit`;
  - wrong-field records listed;
  - downstream DEPENDENCY utility NULL_PRIOR − ORIGINAL (changing; goals averaged within world first; stable separate; per domain) and interface losses against structured;
  - actual-state inclusion, representation, conflicts, pending, truthful readings incompatible with the parsed history, fees, success, missed menu-feasible goals, invalid actions, false completions and unsafe copies.

## Interpretation and stop
- **Primary positive, interval above 0:** on this panel the clarification improves arrival interpretation. It is not shown to explain every overnight error.
- **Inconclusive or negative:** kept as is. No added examples, rewording or context change.
- **Kind label alone is not enough.** Entity, field, result, times and decisions still matter.
- **Downstream utility is a separate finding.** Any wrong-item invalid action or false completion remains an unresolved failure. No harms observed on 96 worlds would not show the class is gone.
- **Stop after the report.** No larger replication, context ablation, grounding gate, reinterpretation, sensor-contract change, training or model comparison.
