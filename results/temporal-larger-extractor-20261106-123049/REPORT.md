# Larger extractor on a structural holdout (V1.19.0): report

- **Date:** 2026-11-06.
- **Frozen setup:** freeze `config/FROZEN-PROTOCOL.json` (sha256 `b71486ca…`, source `9d066ace…`); primary per
  `config/AMENDMENT-01-DISPOSITION.md` and `PRIMARY-SELECTION.json` (option i). Commits `6702983` (1.18.0) and
  `92d3cb3` (1.19.0).
- **Collection:** SMALL block then LARGE block, under the frozen settings and the 12 h cap.
- **Completion: 640/640 calls ok for each model** (main), plus 32/32 each in smoke. No infrastructure failure, no
  resume, no content retry.
- **Software gates all pass:** H1 canonical exact and canonical replay equal to the independent reference, 640/640;
  H2 identical prompts across models; H3 complete accounting, 1,280/1,280.
- **One earlier failure is preserved:** the first LARGE smoke attempt failed before loading (manifest layout,
  0 calls), in `stages/smoke-LARGE-attempt1-failed/`.

The analysis JSON still says amendment 01 is "proposed" and "until settled". That wording is fixed text in the frozen
analysis code, written before the decision. The amendment was settled as option (i) before main collection.

## Primary: exact extraction, structural holdout (512 targets per model, n = 64 groups)

| | Qwen3-8B NF4 (SMALL) | Qwen3-32B NF4 (LARGE) |
|---|---|---|
| Exact extraction (group-weighted) | **0.346** (177/512) | **0.688** (352/512) |

**LARGE − SMALL = +0.342 [+0.299, +0.385]**: paired group bootstrap within the 8 strata, 10,000 resamples, seed
20261106; descriptive. LARGE is higher in every stratum family.

**Paired targets:** both correct 144; LARGE only 208; SMALL only 33; neither 127.

Under the frozen rule, the positive primary with its interval above 0 supports the larger quantized checkpoint under
FACT-v1 *on this authored holdout*. It is not a scaling law, a 32B threshold, a quantization effect, or transfer
beyond the four families.

## Immediately after: compilation loss and the fixed end-to-end ceiling
- **The ceiling.** Contract v1 (`from_v02`) has no `valid_to`, so a finite correction interval is dropped even from a
  perfect extraction. The canonical end-to-end ceiling is **448/512 = 87.5%** on the holdout (560/640 across main).
  That loss belongs to the mapper, not to either model.
- **Model outputs whose interval end was dropped** by the mapper: SMALL 65, LARGE 45.
- **End-to-end exactness** (extraction exact and no compilation loss): SMALL **0.244**, LARGE **0.604**.
  Difference **+0.359 [+0.322, +0.397]**, out of a maximum of 0.875.
- **Finite-exclusion sensitivity** (6 or 8 targets per group, so the act weights differ from the primary):
  **+0.419 [+0.374, +0.465]**. This is a sensitivity view only and is not promoted.
- **Restricted replay agreement:** SMALL 286/512, LARGE 400/512. Replay is blind to `valid_to`, stated priors, rid
  and status (`phase0/hold/COVERAGE.json`), so it is not fidelity evidence.

## By class (holdout; exact extraction, SMALL → LARGE)

| | SMALL → LARGE | Both histories exact, out of 64 groups (SMALL → LARGE) |
|---|---|---|
| Arrival | 24 → 78 /128 | 6 → 28 |
| Observation | 29 → 88 /128 | 8 → 34 |
| Removal | 18 → 84 /128 | 5 → 30 |
| **Correction** | **106 → 102 /128 (LARGE −4)** | 43 → 44 |
| F1 two-hop | 67 → 108 | |
| F2 slot join | 43 → 101 | |
| F3 historical occupant | 31 → 83 | |
| **F4 measurement order** | **36 → 60 (weakest)** | |
| Immediate reception | 82 → 175 /256 | |
| Delayed reception | 95 → 177 /256 | |

**Corrections are the one class where LARGE is not better.** Its errors there are 20 mixed acts (a correct revision
plus extra state claims, e.g. at the interval end) and 4 rejected wrong targets. SMALL's correction errors are mostly
20 `correction_target` rejections.

## Failure modes (accepted false claims are part of the result)

| Holdout, 512 targets each | SMALL | LARGE |
|---|---|---|
| Compiled to one act / accepted | 281 / 260 | 462 / 458 |
| Pending (failed compilation) | 231 (mixed acts 183, invalid 22, mixed times 14, parse 11) | 50 (mixed acts 23, multiple events 22) |
| Truncated (256 cap) | **11** | 0 |
| Binding correct, raw claims | 208 | 391 |
| **Accepted with the wrong binding** | **68** | **85** |
| Slot field claimed instead of stock | 149 | 29 |
| False revisions: raw / accepted | 121 / 2 | 1 / 0 |
| Event omitted (no event on X), of 256 events | 177 | 71 |
| **Accepted state-only events** | 4 | **32** |
| Stated prior correct, of 128 | 88 | 123 |
| Finite `valid_to` correct, of 64 | 64 | 62 |
| Reception time correct | 479 | 511 |
| Quotation valid | 474 | 467 |

**Key caveat.** LARGE's errors are more often *accepted*. It produces more accepted wrong-binding records (85 vs 68)
and more accepted state-only events (32 vs 4), because SMALL's wrong outputs mostly failed to compile.

LARGE's accepted wrong bindings are concentrated, and almost all name the **competitor part**:
- **F4 measurement order: 50** (44 competitor) — it chooses the wrong measurement order;
- **F3 historical occupant: 29** (28 competitor) — it chooses the later occupant.

These are confident, structurally valid misreadings, the class behind the earlier unsafe executions. No actions were
measured here.

## Calibration (familiar dependencies, 16 groups; secondary, no interval by design)
- **Exact extraction:** SMALL 0.688, LARGE 0.797 (+0.109).
- **Holdout minus calibration:** SMALL −0.342, LARGE −0.109. Both models are worse on the new dependency
  structures, SMALL much more so.
- **Corrections on familiar cases are again worse for LARGE:** SMALL 32/32, LARGE 23/32 (9 mixed acts).

## Cost

| | SMALL NF4 | LARGE NF4 |
|---|---|---|
| Main block wall time | 5,177 s (load 29 s) | 7,598 s (load 105 s) |
| Peak GPU | 7.05 GiB | 18.75 GiB |
| Peak host RSS | 4.6 GiB | 4.6 GiB |
| Generation, holdout | 4,234 s | 6,024 s |
| Output tokens, holdout | 80,186 | 67,599 |

Both ran GPU-only, with no offload. Main total wall time was 12,780 s (3.55 h), inside the 12 h cap.

## Interpretation and limits
- **Capacity matters here.** Under the frozen FACT-v1 interface and identical NF4 settings, the 32B checkpoint
  roughly doubles exact extraction on four authored reference-dependency families (+0.34). The gain spans arrivals,
  observations and removals and every family. Its larger share of compilable output also nearly eliminates false
  revisions.
- **The remaining errors move into accepted, confident misreadings:** wrong-part bindings on measurement-order and
  historical-occupant references, and state-only events. Corrections do not improve. More output reaching the engine
  is not more reliable output.
- **End to end, under contract v1:** at most 87.5%. LARGE reaches 0.604.
- **Not established:** a scaling law, a threshold, a quantization effect, transfer beyond these families, utility,
  action safety or reliable execution. The comparison does not isolate parameter count from other checkpoint
  differences.
- **Prior results unchanged:** the earlier +1.95 utility result remains conditional on its fixed mixture, beside its
  5 unsafe world-goal cases (18 executions).

## Files
- `stages/main-{SMALL,LARGE}/calls/`: raw replies; `LOAD.json`, `END.json`, `main-*.log`, `main-driver.log`.
- `analysis/hold/ANALYSIS.json`: all blocks, diagnostics and disagreements.
- `analysis/hold/scored.jsonl`: every target with its compiler trace, acceptance, scores and replay.
- `analysis/holdsmoke/`, `phase0/`, `design/` (`CLAIM-EVIDENCE.md` is filled in with these results).

**Stopped after this report.**

---

## Clarifications (appended 2026-11-06 after review; original text above unchanged; scores unchanged)
1. **"Calibration … no interval by design"** means that no bootstrap *confidence* interval is computed for the
   16-group calibration panel. It does not refer to correction validity intervals. The calibration panel contains
   **16 finite-interval correction targets** (80 finite in main − 64 in the holdout). Both models have exact
   `valid_to` on all 16, and compilation loss is SMALL 16, LARGE 7.
2. **Per-call speed.** My chat summary said 9.4 s and 6.6 s per holdout call, which divides by 640 instead of 512.
   The correct holdout generation times are **6,024.3 s / 512 = 11.77 s (LARGE)** and **4,233.7 s / 512 = 8.27 s
   (SMALL)**. Calibration: 11.45 s and 7.12 s. The report's table above gives totals only and is unaffected.
3. **Accepted wrong bindings use two denominators**, which answer different questions:

| Holdout | SMALL | LARGE |
|---|---|---|
| Per target (all 512) | 68/512 = **13.3%** | 85/512 = **16.6%** |
| Per accepted record | 68/260 = **26.2%** | 85/458 = **18.6%** |

   LARGE produces more accepted wrong-binding records in total, because far more of its output is accepted, but a
   smaller share of its accepted records is wrong. Neither rate is a measured probability or a confidence, and no
   improvement in action safety is implied (no actions were measured).
