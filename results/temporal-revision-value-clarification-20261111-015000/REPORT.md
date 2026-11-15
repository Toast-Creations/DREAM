# Revision-value clarification development comparison

**Status: COMPLETE.**
This is a prespecified development comparison; no qualification or formal harm/preservation test is defined.

## Integrity

Attempts: 688 / 688 ceiling; planned 688 calls (640 main and 48 structural smoke).
Frozen source/config/data checks and runner completion: passed.
Smoke stage: 0.20 hours; END at 2026-11-11T02:14:48.
Main stage: 2.42 hours; END at 2026-11-11T04:39:45.

## F2 prespecified contrasts

| Outcome / contrast | Estimate (points) | Descriptive 95% reference interval |
|---|---:|---:|
| exact: KEEP_clar_minus_orig | +11.46 | [+6.25, +16.67] |
| exact: SUB_clar_minus_orig | +3.12 | [+0.00, +8.33] |
| exact: interaction | +8.33 | [+2.08, +14.58] |
| withdrawn_value_error: KEEP_clar_minus_orig | -11.46 | [-16.67, -6.25] |
| withdrawn_value_error: SUB_clar_minus_orig | -3.12 | [-8.33, +0.00] |
| withdrawn_value_error: interaction | -8.33 | [-14.58, -2.08] |

A positive exactness contrast favors clarification; a negative withdrawn-value-error contrast favors clarification.
The interaction is the KEEP clarification effect minus the SUB clarification effect.
These estimates describe the assigned prompt manipulation on these authored families; error patterns do not establish an internal reasoning mechanism.

## Arrival guards

| Family / contrast | Estimate (points) | Descriptive 95% reference interval |
|---|---:|---:|
| F2: KEEP_clar_minus_orig | -4.17 | [-12.50, +0.00] |
| F2: SUB_clar_minus_orig | +4.17 | [+0.00, +12.50] |
| F2: KEEP_minus_SUB_CLAR | +8.33 | [-8.33, +29.17] |
| F1: KEEP_clar_minus_orig | +0.00 | [+0.00, +0.00] |
| F1: SUB_clar_minus_orig | -50.00 | [-50.00, -50.00] |
| F1: KEEP_minus_SUB_CLAR | +0.00 | [+0.00, +0.00] |
| F3: KEEP_clar_minus_orig | +0.00 | [+0.00, +0.00] |
| F3: SUB_clar_minus_orig | +0.00 | [+0.00, +0.00] |
| F3: KEEP_minus_SUB_CLAR | +25.00 | [+25.00, +25.00] |

These small arrival panels can reveal regressions; intervals crossing zero do not establish preservation.

## Counts

| Act / arm | Exact / scheduled | Usable | Withdrawn-value errors | Mixed correction |
|---|---:|---:|---:|---:|
| arrival|KEEP_CLAR | 25/32 | 32 | 0 | 0 |
| arrival|KEEP_ORIG | 26/32 | 32 | 0 | 0 |
| arrival|SUB_CLAR | 22/32 | 32 | 0 | 0 |
| arrival|SUB_ORIG | 23/32 | 32 | 0 | 0 |
| correction|KEEP_CLAR | 128/128 | 128 | 0 | 0 |
| correction|KEEP_ORIG | 116/128 | 128 | 12 | 12 |
| correction|SUB_CLAR | 128/128 | 128 | 0 | 0 |
| correction|SUB_ORIG | 125/128 | 128 | 3 | 3 |

## F2 corrections by direction

| Direction / arm | Exact / scheduled | Withdrawn-value errors / scheduled |
|---|---:|---:|
| yes_to_no: SUB_ORIG | 45/48 | 3/48 |
| yes_to_no: KEEP_ORIG | 40/48 | 8/48 |
| yes_to_no: SUB_CLAR | 48/48 | 0/48 |
| yes_to_no: KEEP_CLAR | 48/48 | 0/48 |
| no_to_yes: SUB_ORIG | 48/48 | 0/48 |
| no_to_yes: KEEP_ORIG | 45/48 | 3/48 |
| no_to_yes: SUB_CLAR | 48/48 | 0/48 |
| no_to_yes: KEEP_CLAR | 48/48 | 0/48 |

## Sentinel exact counts

| Family / act | SUB original | KEEP original | SUB clarified | KEEP clarified |
|---|---:|---:|---:|---:|
| F1: correction | 16/16 | 15/16 | 16/16 | 16/16 |
| F1: arrival | 4/4 | 2/4 | 2/4 | 2/4 |
| F3: correction | 16/16 | 16/16 | 16/16 | 16/16 |
| F3: arrival | 2/4 | 3/4 | 2/4 | 3/4 |

## Reading limits

- F2 is the primary family; F1/F3 are low-precision sentinels. No historical family weights are imposed.
- Both correction directions and paired histories remain together when resampling whole independent stems within family/reception.
- The nested arrival subset is resampled separately within its fixed family/reception allocation; arrival effects are guards, not preservation tests.
- The withdrawn-value diagnostic requires exactly one raw-normalized revision matching the expected field and target. Missing, multiple, invalid, and wrong-target/field revisions remain in the scheduled denominator and are counted separately.
- The historical contradictory-correction flag ignores times. The separate simultaneous-conflict diagnostic checks explicit points against half-open revision intervals without inferring persistence.
- Compiler, exactness scorer, model, and decoding are unchanged. No conclusion about unseen families, broader transfer, general safety, or absence of harm follows.

Full cells, paired counts, diagnostics, costs and reference intervals: `analysis/dev/ANALYSIS.json`; individual scores: `analysis/dev/scored.jsonl`.
No next stage is authorized by this report.

## Reporting addendum — November 11, 2026

Read [REPORT-ADDENDUM-20261111.md](REPORT-ADDENDUM-20261111.md) alongside this driver-generated report. It provides the paired rescue/break counts, places the net arrival losses beside the correction gains, and explains why the zero-width F1/F3 arrival intervals do not show precision. Both clarified arms reached the observed correction ceiling; this does not establish equivalence or qualify KEEP+ID. The original report body above, frozen files, raw outputs and scored results are unchanged.
