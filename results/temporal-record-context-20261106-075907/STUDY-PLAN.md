# Record-context ablation, FULL vs LOCAL extraction (V1.17.0): frozen plan

- **Brief:** `RECORD-CONTEXT-ABLATION-BRIEF.md` (copy in `design/BRIEF-copy.md`). Record-interpretation diagnostic. There is no action utility or safety estimate.
- **Freezing.** This plan is hashed in `config/FROZEN-PROTOCOL.json` before main output. Amendments go to `config/AMENDMENTS.md`.
- **Predecessor.** 1.16.0 is preserved as `4a09069`: completed and inconclusive. Notes N1 and N2 (`1b7407a`) record:
  - the four null-using correct arrivals were already correct under ORIGINAL;
  - the single gain used a non-null prior;
  - the two downstream regressions are observed outcomes of the changed prompt, not noise;
  - the narrowed claims;
  - the arrivals span nine families, not ten.

  Nullable-prior wording variants are stopped.
- **Source.** `Code/DREAM-project-1.17.0-record-context-20261106` is 1.16.0 plus `src/tempo/ctxablate.py`, `scripts/cab_{generate,validate,analyze}.py` and `tests/test_ctxablate.py`. Every 1.16.0 file is byte-identical. Tests: 205/205.

## Conditions (one controlled change)
- **FULL:** the frozen extraction prompt with the prior raw reports, the new report, the domain header and rules, the field registry and the instruction.
- **LOCAL:** the same prompt with the prior-report lines replaced by the frozen empty-context marker `(none)`. That is the line the frozen prompt already prints when a record has no predecessors.
- **Diff check.** The diff is checked automatically for every call. The registry and its order are identical in both conditions.
- **Schema.** Both conditions use the 1.16.0 NULL_PRIOR schema (`nullprior.null_prompt`). This is a design choice, not the adoption of a winner.
- **Model.** Qwen3-8B `b968826d…`, BF16, thinking off, greedy, 256 tokens. One fresh call per cell; no content retry, best-of or repair. One infrastructure retry is allowed (1.11.0 configuration).
- **Order.** A precommitted balanced schedule (`order: as_committed`): units are in a seeded order (seed 20261106), the order alternates by unit, and each condition goes first in 246 of 492 units.

## Main corpus: 120 self-contained miniature-history groups (no redraws)
- **Worlds and fields.** Assembly worlds from `worlds.make_world` (unchanged). The target is part G's stock and the competitor is part D's stock. The registry is the world's fixed fields (slot T, G stock, slot S2, D stock), identical whatever the mention order.
- **Variants.** Each group forks one prefix skeleton into four target variants:

| Variant | Prefix record for P | Target |
|---|---|---|
| Arrival | verified "not on hand" | verified change no → yes ("delivered to you / arrived for you, now on hand") |
| Observation | verified "on hand" | verified observation "on hand" (no arrival asserted) |
| Removal | verified "on hand" | verified change yes → no ("taken away") |
| Correction | **provisional** "on hand" (rid rX) | verified correction of rX, naming rX and the field: not on hand from that time |

- **Shared skeleton.** Each group also includes a verified stock observation of the competitor D, a verified installation into slot T (the lure), and, in long prefixes, a verified slot S2 observation.
- **Strata.** 8 cells × 15 groups, precommitted:
  - prefix length 3 or 4 (the target is r04 or r05);
  - P's record before or after D's;
  - the lure: an installation of part **P itself** into slot T (the overnight "delivered → installed" confusion) or of the low-rated part W.
- **Templates.** Frozen templates only. The arrival phrasing cycles through all 12 (header × body × change) combinations, 10 groups each. The renderer seed is chosen before any output, and the same seed renders the group's other variants.
- **Validation.** Every rendering passes `check_equivalent`. Labels are distinct and prefixes compatible: arrival after "not on hand", removal after "on hand", the correction targets the provisional record (checked per group).
- **Correlation.** The variants are correlated controls, not independent samples.
- **Size.** 120 × 4 × 2 = **960 calls**, including **120 arrival pairs**.

## Context-required controls: 12 groups (outside the primary)
- **Histories.** Two alternative histories each. r01 and r02 are verified "not on hand" observations of P and D in swapped order; r03 is a slot T observation.
- **Target.** One identical new report r04: *"…the part whose stock was checked in r02 was delivered to you, so it is now on hand."* This is a declared control-only phrasing, because the frozen renderer always names the entity.
- **Gold.** History A gives D's stock change; history B gives P's.
- **Identity.** The header, registry and new report are byte-identical, so the two **LOCAL prompts are identical** (asserted). LOCAL is called once and scored against both alternatives (cached). The two FULL calls are distinct.
- **Size.** 12 × (2 FULL + 1 LOCAL) = **36 unique calls**, 48 scored cells.

## Workload
- **Main:** **996 unique calls**, 1,008 scored cells.
- **Smoke:** disjoint; 4 groups and 2 controls; 38 calls and 40 cells.
- **Forecast:** about 3 s per call, roughly 50 min. **Overall cap 90 min** (runner budget 5,100 s). An incomplete run is preserved and labelled incomplete.

## Scoring and gates
- **Scores.** Source-aware exact meaning (`contract_validate.score_record`, unchanged) plus `nul_evaluate.record_diag`:
  - event kind, field, result, meta (time, status, rid) and prior use;
  - category (state / event / correction; initial and observation both count as state);
  - correction-target correctness.
- **Acceptance.** The contract is checked against the **same canonical prefix in both conditions**. This is evaluator only, never a model input. Malformed or unmapped replies count as incorrect.
- **Software gates:**
  - G1: prompt isolation and diff, schema, cap, no labels in inputs;
  - G2: model configuration and committed order;
  - G3: labels, prefix compatibility, control identity and cache accounting;
  - G4: complete paired scoring.

  G1–G3 also passed before collection (`phase0`). A genuine harness defect stops the study; semantic mistakes are the results.

## Outcomes (fixed now)
- **Primary:** LOCAL − FULL exact meaning on the **120 arrivals**, with both-correct, LOCAL-only, FULL-only and neither.
- **Interval:** unit = group (**n = 120**). Bootstrap groups within the 8 strata, 10,000 resamples, **seed 20261106**; descriptive.
- **Secondary:**
  - exact meaning, kind, field, result, meta and acceptance for observations, removals and corrections separately, with paired tables and differences;
  - category confusion; prior use; correction targets; wrong-field records (also with exact quotation);
  - arrival accuracy by stratum;
  - all discordant cases;
  - controls: FULL correct on both alternatives, and the shared LOCAL reply's match to A versus B (one reply; a match to one alternative may be a guess);
  - tokens, runtime and truncation.
- **Pooling.** Controls are never pooled into the primary.

## Interpretation (fixed now) and stop
- **Primary positive, interval above 0:** supports a benefit from withholding raw history *for these self-contained stock reports*. It is not a general context-free policy.
- **Trade-offs.** If LOCAL helps arrivals but harms observations or corrections, that trade-off is reported.
- **Controls.** FULL success on them shows why context is kept for reference resolution. FULL failure there is reported as a limitation.
- **Inconclusive or negative:** historical interference is not established, and context independence is not proven either. Context-window variants stop after this comparison.
- **Entity binding.** Wrong entity or field bindings remain unresolved regardless of the primary. Nothing here establishes reliability or the removal of the overnight unsafe class.
- **Stop after the report.**
