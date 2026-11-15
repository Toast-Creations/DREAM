# V1.22.0 KEEP+ID fresh confirmation: report

Written by Claude on 2026-11-11, after a single complete run of the frozen protocol (`design/PROTOCOL.md`, `config/FROZEN-PROTOCOL.json`).

## Outcome: not qualified

| Component | Rule | Estimate (KEEP − SUB) | Gate lower bound | Threshold | Pass |
|---|---|---:|---:|---:|---|
| A. Arrival superiority | P@0.0175 | **+0.193** (65/336) | 0.131 (11/84) | > 0 | **yes** |
| C. Correction non-inferiority | P@0.01 | **−0.069** (−27/392) | −0.092 (−9/98) | > −3/64 (−0.047) | **no** |

Verdict, as written by the analyzer: "arrival superiority shown; correction non-inferiority not shown (trade-off or inconclusive)". Under the pre-registered reading, this is **not qualification**.

These are 95% percentile *reference* intervals, not gates:
- arrival [0.134, 0.253];
- correction [−0.088, −0.050].

The correction reference interval lies entirely below the −3/64 tolerance. Descriptively, the data point to a real correction cost of KEEP+ID relative to SUB, larger than the declared tolerance, not to a merely under-powered comparison. This is a description of the reference interval; the protocol did not pre-declare a harm test.

## Integrity

- **Status:** COMPLETE. There are 2,240 of 2,240 main records and 32 of 32 smoke records, all ok, with no duplicates.
- **Attempts:** 2,272 used out of a ceiling of 2,272. There were no failed attempts and no retries.
- **Timing:** the driver started at 16:06:17 and finished at 00:11:00, against a deadline of 04:06:17. The main stage took 7.9 h.
- **Freeze:** the source and frozen-file checks passed at start. The analysis plan hash 3fa4a113 equals the frozen hash. `DRIVER-SUCCESS.json` certifies every step.
- **Truncation:** none, in any arm or act.

## Secondary results (descriptive, untested)

Exact counts are per target-history; denominators are shown.

| Family | Arrival SUB | Arrival KEEP | Correction SUB | Correction KEEP |
|---|---:|---:|---:|---:|
| F1 | 50/84 | 51/84 | 196/196 | 196/196 |
| F2 | 53/84 | 78/84 | 191/196 | **148/196** |
| F3 | 102/168 | 141/168 | 386/392 | 375/392 |

| Reception | Arrival SUB | Arrival KEEP | Correction SUB | Correction KEEP |
|---|---:|---:|---:|---:|
| immediate | 102/168 | 124/168 | 389/392 | 359/392 |
| delayed | 103/168 | 146/168 | 384/392 | 360/392 |

- **Arrival.** SUB fails only by accepted state-only output (131/336, event omitted). KEEP cuts this to 62/336.
  - KEEP introduces 3 accepted wrong bindings (SUB has 0) and 1 rejection (mixed_acts).
  - The gain comes from F2 and F3. F1 shows essentially no difference (50 vs 51 of 84).
- **Correction.** KEEP has 65/784 rejections:
  - 59 mixed_acts (mixed state/revision; 58 also contradictory);
  - 5 empty;
  - 1 correction_target.
  
  SUB has 11/784 rejections: 10 mixed_acts and 1 empty. Every correction failure in both arms was a rejection; there were no accepted inexact corrections.
  - The KEEP correction loss is concentrated in **F2** (−43 of 196). It is small in F3 and absent in F1.
- **Paired target-histories:**
  - arrival: KEEP-only exact 78, SUB-only exact 13;
  - correction: SUB-only exact 59, KEEP-only exact 5.
- **Cost:** mean seconds per call were, for arrival, SUB 10.6 and KEEP 11.6; for correction, SUB 13.2 and KEEP 13.7.

## Interpretation and caveats

- KEEP+ID improves arrival exactness on fresh F2/F3 instances. It fails the separate correction requirement, and the arrival gain cannot compensate for that. So on these families, as measured, KEEP+ID is a trade-off against SUB and does not qualify. **SUB stays the baseline.**
- **"Mixed acts" is the observed failure mode, not an established cause.** Of KEEP's 59 mixed corrections, 58 were also marked contradictory. That makes relaxing the compiler unjustified on this evidence.
- **The family × act table is a declared secondary** (descriptive, untested). Any explanation of why the loss concentrates in F2 is exploratory.
- **Smallest useful follow-up (not started):** audit the saved, paired F2 correction outputs against their intended corrections, separating semantic contradictions from representation problems.
  - It needs no new model calls.
  - The frozen scores stay as they are.
- Scope:
  - these are fresh instances of the 1.20 families F1–F3, not unseen families;
  - one model (Qwen3-32B NF4), greedy decoding, thinking off;
  - SUB vs KEEP only, with no BASE or F4 arms.
- Calibration caveat: the rules were checked by model-based simulation under declared scenarios.
  - One correction-null cell straddled 0.025 (0.0232 [0.0213, 0.0254]).
  - That caveat does not bear on this outcome, because C failed and A passed by a wide margin (lower bound 0.131 vs threshold 0).
- The development-stage correction difference had already predicted low P(C) (`SELECTED-RULE-POWER.md`). The result is consistent with that.

## Files

- `analysis/confirm/ANALYSIS.json` (gates, qualification, descriptives) and `analysis/confirm/scored.jsonl`
- `driver.log`, `DRIVER-SUCCESS.json`, and `stages/{smoke,main}/`

No next stage has been started.
