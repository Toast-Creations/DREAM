# Notes: V1.16.0 nullable-prior extraction test (append-only; scores, traces and REPORT.md unchanged)

Status: completed, **inconclusive**. Nullable-prior wording variants are stopped here.

## N1 (2026-11-06): interpretation precision
- The four correct NULL_PRIOR arrivals that used `from: null` (a01i2 r7, a01i3 r6, a08i2 r3, a12i3 r6) were already
  correct under ORIGINAL. The single NULL_PRIOR-only improvement (a10i1 r6) supplied a non-null (correct) prior.
  So the advertised null produced no observed classification gain on its own.
- The two downstream regressions (a07i4/B: a removal became unmapped; d12i1/B: a location observation was rejected
  for time order) are observed outcomes of the changed prompt. My summary to David called them noise; that goes
  beyond the evidence. Their broader significance is uncertain on this panel.
(Verified from stages/main/eval/extraction.jsonl, paired by base record.)

## N2 (2026-11-06): narrowed statements
- REPORT.md says the schema's apparent demand for a prior "was not a material obstacle" and that the dominant failure
  persists "independently of the null-prior wording". Narrow both to: **the clarification did not produce a
  demonstrated improvement on this small panel; event-versus-state errors remained common.** The test neither
  establishes equivalence nor shows that schema wording is irrelevant.
- The 23 arrival records span **nine** assembly families (a01, a02, a03, a07, a08, a09, a10, a11, a12), not ten.
- The two downstream regressions total −5 utility, which is −0.026 over the per-world contrast of 96 worlds
  [−0.068, 0]. Both involve non-arrival records.
Scores unchanged.
