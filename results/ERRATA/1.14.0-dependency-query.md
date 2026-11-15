# ERRATA / reporting notes: V1.14.0 dependency-aware query selection (append-only; scores, traces and REPORT.md text unchanged)

## N1 (2026-11-05): fee accounting and d06/B
- The 37 augmented goal copies (changing, e > 0) bought **39** extra facts: a07/A and a12/B each added two.
- The ten copies with lower utility than BASE and no success gain (a04/A, a04/B, a06/A, a07/B, a10/A, a12/B,
  d03/A, d04/A, d11/A, d12/A) paid **11** extra fees (a12/B paid two).
- d06/B: REPORT.md says the 10-unit route meant "the success did not pay for itself". More precisely, the success
  reward (10) and the route cost (10) are equal, so execution is utility-neutral. The added query fee (1) is the
  whole of the loss: U -5 against -4 for BASE's decline.
All utility, success, correctness and contrast scores are unchanged.

(Verified from analysis/main/ANALYSIS.json per_copy: sum of e over changing copies with e > 0 = 39; d06/B DEPENDENCY
fees 1, action_cost 10, success True, U -5; BASE decline U -4.)

## Disclosure (repeated from the hub RUN-STATUS.md)
One plumbing trial of depq_run.py was made on the main allocation in a scratch directory before the analysis code
existed. Only row counts were viewed; its outputs were deleted unread. Analysis was developed on the disjoint smoke rows
and the 1.13.0 panel. The scored main run is the frozen one (config/FROZEN-PROTOCOL.json, source 62333ae1...).

## N2 (2026-11-05): further reporting precision
- The 27 recovered successes bought 28 extra facts (a07/A added two).
- The eight "insufficient" copies bought nine facts: seven bought one, and a12/B bought two. REPORT.md's
  "one extra fee each" is too broad.
- The frozen diagnostic label "costs more without helping" (11 copies) should be read as "lower utility than BASE".
  Ten of those copies had no decision benefit; d06/B succeeded (see N1). Success gain is reported separately.
Scores unchanged. (Verified from analysis/main/ANALYSIS.json per_copy.)
