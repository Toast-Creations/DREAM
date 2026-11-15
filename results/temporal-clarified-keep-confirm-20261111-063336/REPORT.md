# Clarified KEEP package confirmation

**Integrity: COMPLETE. Qualification: QUALIFIED.**

Recorded calls: 2340/2340; failed-attempt entries: 0.
The primary comparison is KEEP_CLAR minus SUB_ORIG. SUB_CLAR is a descriptive reference and cannot rescue a failed primary gate.

Main: 2304/2304 records; 8.05 hours; END 2026-11-11T15:14:05.
Smoke: 36/36 records; 0.16 hours; END 2026-11-11T07:11:21.

Hard deadline: 2026-11-11T19:02:02-05:00 (epoch clock authority; America/New_York).

## Primary results

| Component | Independent stems | KEEP − SUB (points) | One-sided 97.5% lower bound (points, approximate) | Exact T > 40? | Paired rescues / breaks |
|---|---:|---:|---:|---:|---:|
| arrival | 224 | +26.56 | +17.5989 | pass | 131 / 12 |
| correction | 160 | +0.94 | -2.0307 | pass | 8 / 2 |

Arrival rescues involve 79 independent stems; breaks involve 10.
Correction rescues involve 8 independent stems; breaks involve 2.

Arrival requires T(0)>40. Correction requires T(−3/64)>40. Equality fails. Exact rational evidence and direct decisions are stored in `analysis/confirm/ANALYSIS.json`; rounded bounds never decide qualification.
Qualification is conditional on the 3/64 correction tolerance. It does not establish no correction harm.
Both outcomes are shown together: arrival gains do not compensate for a failed correction gate.
The displayed lower bound is the conservative inverted endpoint. Its exact enclosing numerical bracket is retained in JSON as a calculation certificate, not a population interval.
Arrival boundary flags: all stem differences zero=False; both arms at observed ceiling=False; empty pass set=False; numerical censoring=False.
Arrival equal-family sensitivity: +23.96 points (descriptive only; the frozen 1:1:2 gate is unchanged).
Correction boundary flags: all stem differences zero=False; both arms at observed ceiling=False; empty pass set=False; numerical censoring=False.
Correction equal-family sensitivity: +0.73 points (descriptive only; the frozen 1:1:2 gate is unchanged).
Observed equal or perfect outputs do not establish equivalence; the bound retains uncertainty about rare future losses.

## Matched references (descriptive only)

| Contrast | Independent stems | Targets/arm | Difference (points) | Rescues / breaks |
|---|---:|---:|---:|---:|
| arrival|KEEP_CLAR_minus_SUB_CLAR | 32 | 64 | +35.94 | 23 / 0 |
| arrival|SUB_CLAR_minus_SUB_ORIG | 32 | 64 | -12.50 | 0 / 8 |
| correction|KEEP_CLAR_minus_SUB_CLAR | 16 | 64 | +0.00 | 0 / 0 |
| correction|SUB_CLAR_minus_SUB_ORIG | 16 | 64 | +0.00 | 0 / 0 |

References use their paired 32-arrival/16-correction stem subsets; they are not whole-panel comparisons, representation-only tests, or fallback qualification claims.
Reference uncertainty is not estimated here. These sparse matched subsets cannot establish preservation, equivalence, or no effect.

## Side-by-side exactness

| Act / arm | Exact / scheduled (usable) | Withdrawn-value errors | State-only arrivals | Accepted wrong bindings | Truncated |
|---|---:|---:|---:|---:|---:|
| arrival|KEEP_CLAR | 399/448 (usable 448) | 0 | 45 | 4 | 0 |
| arrival|SUB_CLAR | 36/64 (usable 64) | 0 | 28 | 0 | 0 |
| arrival|SUB_ORIG | 280/448 (usable 448) | 0 | 167 | 0 | 0 |
| correction|KEEP_CLAR | 638/640 (usable 640) | 0 | 0 | 0 | 0 |
| correction|SUB_CLAR | 64/64 (usable 64) | 0 | 0 | 0 | 0 |
| correction|SUB_ORIG | 632/640 (usable 640) | 8 | 0 | 0 | 0 |

## Counts by family

| Cell / act / arm | Exact / scheduled (usable) |
|---|---:|
| F1|arrival|KEEP_CLAR | 85/112 (usable 112) |
| F1|arrival|SUB_CLAR | 10/16 (usable 16) |
| F1|arrival|SUB_ORIG | 78/112 (usable 112) |
| F1|correction|KEEP_CLAR | 160/160 (usable 160) |
| F1|correction|SUB_CLAR | 16/16 (usable 16) |
| F1|correction|SUB_ORIG | 160/160 (usable 160) |
| F2|arrival|KEEP_CLAR | 108/112 (usable 112) |
| F2|arrival|SUB_CLAR | 9/16 (usable 16) |
| F2|arrival|SUB_ORIG | 73/112 (usable 112) |
| F2|correction|KEEP_CLAR | 160/160 (usable 160) |
| F2|correction|SUB_CLAR | 16/16 (usable 16) |
| F2|correction|SUB_ORIG | 159/160 (usable 160) |
| F3|arrival|KEEP_CLAR | 206/224 (usable 224) |
| F3|arrival|SUB_CLAR | 17/32 (usable 32) |
| F3|arrival|SUB_ORIG | 129/224 (usable 224) |
| F3|correction|KEEP_CLAR | 318/320 (usable 320) |
| F3|correction|SUB_CLAR | 32/32 (usable 32) |
| F3|correction|SUB_ORIG | 313/320 (usable 320) |

## Counts by reception

| Cell / act / arm | Exact / scheduled (usable) |
|---|---:|
| delayed|arrival|KEEP_CLAR | 214/224 (usable 224) |
| delayed|arrival|SUB_CLAR | 20/32 (usable 32) |
| delayed|arrival|SUB_ORIG | 147/224 (usable 224) |
| delayed|correction|KEEP_CLAR | 319/320 (usable 320) |
| delayed|correction|SUB_CLAR | 32/32 (usable 32) |
| delayed|correction|SUB_ORIG | 315/320 (usable 320) |
| immediate|arrival|KEEP_CLAR | 185/224 (usable 224) |
| immediate|arrival|SUB_CLAR | 16/32 (usable 32) |
| immediate|arrival|SUB_ORIG | 133/224 (usable 224) |
| immediate|correction|KEEP_CLAR | 319/320 (usable 320) |
| immediate|correction|SUB_CLAR | 32/32 (usable 32) |
| immediate|correction|SUB_ORIG | 317/320 (usable 320) |

## Counts by direction

| Cell / act / arm | Exact / scheduled (usable) |
|---|---:|
| na|arrival|KEEP_CLAR | 399/448 (usable 448) |
| na|arrival|SUB_CLAR | 36/64 (usable 64) |
| na|arrival|SUB_ORIG | 280/448 (usable 448) |
| no_to_yes|correction|KEEP_CLAR | 320/320 (usable 320) |
| no_to_yes|correction|SUB_CLAR | 32/32 (usable 32) |
| no_to_yes|correction|SUB_ORIG | 318/320 (usable 320) |
| yes_to_no|correction|KEEP_CLAR | 318/320 (usable 320) |
| yes_to_no|correction|SUB_CLAR | 32/32 (usable 32) |
| yes_to_no|correction|SUB_ORIG | 314/320 (usable 320) |

## Scope and evidence

- Family allocation is the frozen 1:1:2 mixture with equal reception. Both histories/directions stay inside independent stems.
- This tests the clarified KEEP package against original SUB on fresh generated worlds of the declared authored families, one model and fixed decoding. It does not identify original model intent or show uniform family benefit, unseen-family transfer, safe execution, or general deployment safety.
- Exact extraction, preservation into the compiled contract, and restricted replay remain separate measurements. Open correction intervals only are in scope.
- Wrong/malformed/truncated model content is semantically incorrect in its scheduled denominator. Infrastructure failures suppress all confidence statements and qualification.
- The inherited contradictory-correction flag ignores times; simultaneous conflict checks explicit half-open interval overlap separately.

Full diagnostic cells, cost and exact evidence: `analysis/confirm/ANALYSIS.json`. Per-call scores: `analysis/confirm/scored.jsonl`. Independent-stem audit trail: `analysis/confirm/stem-differences.jsonl`.
The protocol stops after reporting. No next study, baseline replacement or publication is started.
