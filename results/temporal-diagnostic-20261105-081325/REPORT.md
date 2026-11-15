# Temporal diagnostic V1.7.2: report (development only)

## Status
- Plan: `design/DIAGNOSTIC-PLAN.md`, frozen before any output (`config/FROZEN-PROTOCOL.json`; source 8b7d35ca…, calls 10d0df09…). Optional block E was included by a decision made before launch.
- Ran 2026-11-05, 08:15–08:26 America/New_York:
  - Smoke: 24/24 calls.
  - Stage diag1: 432/432 calls in 509 s.
  - Stage diag2 (C step 2): 48/48 calls in 44 s.
  - Every call completed; 0 invalid replies, 0 truncations, 0 infrastructure retries, 0 upstream failures. Longest input was 1,245 tokens; peak GPU memory 15.6 GiB.
- Model: Qwen3-8B rev b968826d…, bf16, thinking off, greedy. Same 24 pilot groups, short length.
  - The extra calls are correlated observations of these groups, not new evidence: n = 24 groups (12 per domain, 2 per pattern per domain).
- Reproducibility: all 4 exact-prompt repeats of pilot calls (smoke) gave replies byte-identical to the saved pilot outputs. So the A − old contrast carries no run-to-run noise.
- Pilot artifacts are unchanged (tested). Corrections to the pilot's report are in `../temporal-pilot-20261104-232811/ERRATA.md`.

## Main results

Decisions, one row per side. Each block × arm has 48 rows: 44 determined and 4 uncertain controls. E has only the 44 determined rows.

| Block : arm | complete pair (count; weighted [95% CI]) | determined correct | unneeded observe | invalid-plan choice | uncertain controls → observe |
|---|---|---|---|---|---|
| old (pilot) C0 | 8/24; 0.333 [0.17, 0.50] | 23/44 | 18/44 | 3 | 3/4 |
| A domain facts C0 | 9/24; 0.375 [0.21, 0.58] | 26/44 | 13/44 | 5 | 3/4 |
| B policy wording C0 | 15/24; 0.625 [0.42, 0.79] | 35/44 | 4/44 | 5 | 3/4 |
| E no observe option C0 | 10/20†; 0.500 | 33/44 | — | 11 | — |
| old (pilot) C1 | 0/24; 0.000 | 2/44 | 42/44 | 0 | 3/4 |
| A C1 | 1/24; 0.042 [0.00, 0.12] | 3/44 | 40/44 | 1 | 3/4 |
| B C1 | 1/24; 0.042 [0.00, 0.12] | 7/44 | 30/44 | 7 | 3/4 |
| C state-first C1 | 0/24; 0.000 | 5/44 | 36/44 | 3 | 4/4 |
| E C1 | 4/20†; 0.200 | 24/44 | — | 20 | — |

† E pairs exist only in the 20 groups where both sides are determined (patterns 1–5). The pre-declared E outcome is determined-row accuracy.

Paired group-level contrasts (domain-weighted; cluster bootstrap with 10,000 resamples). "Groups" counts better / equal / worse.

| Contrast | Complete pair | Groups | Determined-row accuracy | Groups |
|---|---|---|---|---|
| A − old, C0 | +0.042 [−0.08, 0.17] | 2 / 21 / 1 | +0.042 [−0.06, 0.15] | 4 / 19 / 1 |
| A − old, C1 | +0.042 [0.00, 0.12] | 1 / 23 / 0 | +0.000 [−0.10, 0.08] | 2 / 21 / 1 |
| **B − A, C0** | **+0.250 [0.08, 0.42]** | 6 / 18 / 0 | **+0.188 [0.06, 0.33]** | 6 / 18 / 0 |
| B − A, C1 | +0.000 [0.00, 0.00] | 0 / 24 / 0 | +0.083 [0.02, 0.17] | 4 / 20 / 0 |
| C − B, C1 | −0.042 [−0.12, 0.00] | 0 / 23 / 1 | −0.042 [−0.10, 0.00] | 0 / 22 / 2 |
| E − B, C0 | | | −0.042 [−0.19, 0.10] | 3 / 16 / 5 |
| E − B, C1 | | | +0.396 [0.27, 0.52] | 17 / 6 / 1 |

### Interpretation, per contrast (development data; the intervals are descriptive)

- **Completed domain facts (A − old).** Adding the unprinted defaults barely changed anything: unneeded observe fell 18→13 in C0 and 42→40 in C1. The omitted defaults are **not** a material cause of the abstention. That alternative explanation is now largely ruled out. Old records and keys stand.
- **Wording (B − A).**
  - With the state supplied (C0), the operational policy roughly doubled the gain on the pilot: complete pair 0.375 → 0.625, and unneeded observe 13 → 4 of 44. Much of C0's abstention in the pilot was a response to the cautious wording.
  - With history (C1), the same wording cut unneeded observe only from 40 to 30. Almost all of that drop was in assembly (18 → 9); delivery stayed at 21–22 of 22. The C1 commitments that did happen were often wrong (7 invalid-plan choices against 7 correct), so complete pair didn't move.
- **State-first workflow (C − B, C1).** No help (−0.04). The model's own readout named the focal fact correctly in 44/48 sides; the whole state was exact in 26/48, with 24 false "unknown" fields. Yet the decision step still observed in 36 of 44 determined rows.
  - *Exploratory:* in 33 of the 41 determined sides whose readout had the focal fact right, step 2 chose "observe" even with that correct readout in front of it.
  - Joint table over all 48 sides: readout exact & decision correct 4; exact & wrong 22; inexact & correct 5; inexact & wrong 17.
  - So, with history present, a correct, explicit, self-written state does not turn into a decision. In this setup the bottleneck is not extracting or holding the state.
- **Forced choice (E − B).**
  - C0: removing the option didn't help (35 → 33 of 44). Invalid-plan choices rose from 5 to 11, because the rows B had abstained on were mostly guessed wrong.
  - C1: determined accuracy rose 7 → 24 of 44 (+0.40), but 20 of 44 choices were plans that fail in the supported state.
  - *Exploratory:* typical errors were travelling to B to take a crate that already rests at your place (6), "take it here" when it rests at B (2), "order" when the part is already on hand (7), and "install" without first removing the occupying part (2) or without ordering it first (2).
  - So when abstention is impossible, plan selection from history is near chance among the three plans. Most errors violate the same prerequisites block D tests. This shows available plan-selection ability, not calibration.
- **Uncertain controls.** Observation on the 4 genuinely unresolved rows stayed at 3/4 in every block (4/4 in C). The B wording did not buy commitment by dropping appropriate caution.

### D: prerequisite pairs (same action text; one prerequisite differs)

| Arm | valid: applicable correct | invalid: applicable correct | balanced applicability | pair correct | valid: all three parts | invalid: all three | uncertain controls |
|---|---|---|---|---|---|---|---|
| C0 | 24/24 | **1/24** (23 said true) | 0.521 [0.50, 0.56] | 1/24 | 19/24 | 0/24 | 3/4 unknown |
| C1 | 17/24 (7 said unknown) | **0/24** (14 true, 10 unknown) | 0.354 [0.27, 0.44] | 0/24 | 8/24 | 0/24 | 3/4 unknown |

- Changed fields on valid rows were correct 24/24 in each arm.
- On invalid rows, no successor was ever predicted as "no effect" (0/24 in each arm). The model applies the action's effects regardless of whether it is allowed.
- Observed-world exact: C0 19/24 on valid rows and 19/24 on invalid; C1 10/24 and 14/24.
- Even with the exact state printed (C0), the model treated `take X` with X elsewhere, `install g in T` with T occupied, and `install` with g not on hand as allowed 23 times in 24. This is a rule and precondition reasoning failure that doesn't depend on history. It fits block E's error pattern and the explicit-context audit's missed prerequisites.

## What this changes

1. The pilot's C1 deficit is **not explained** by the missing domain defaults or by self-tracking of state. Policy wording explains most of C0's abstention but little of C1's: with history, and especially in delivery, the model still declines to commit even after writing the correct state itself.
2. Separately, and more fundamentally, the model **does not check action preconditions**. With the state given, it judged inapplicable actions allowed in 23/24 cases, and forced plan choices from history often break a prerequisite. This is now the clearest repair target. Under the plan's reading rules, "C0 still misses known prerequisites" means rule and precondition reasoning comes first.
3. The delayed-report historical weakness from the pilot remains a separate target; this diagnostic didn't test it.

## Recommended next step (not run)

The step is a model-free design change, followed later by a fresh-world check: a precondition-focused probe.
- Ask for each prerequisite of an action explicitly (for example "Is crate X at your place? Are your hands empty?") before asking about applicability. This separates "can't read the condition" from "doesn't apply the rule".
- Run it on newly generated worlds, not on these 24 groups, since they have now been used for adaptive diagnosis.
- Keep the B wording as the decision baseline. Do not tune wording further on these items. No adapters and no model scaling.

## Claims not supported
- Anything about temporal memory capacity, learned world models, or adapters.
- That B's gain will transfer (validate on fresh worlds first).
- That C1 abstention is a fixed model trait beyond these two templates and one checkpoint.
- Calibration claims from E.
- Any generalisation from cells of 2 groups.

## Artifacts
- Analysis: `analysis-diag/ANALYSIS.json`, `TABLES.md` and `scores.jsonl`; smoke in `analysis-diagsmoke/`.
- Raw replies: `stages/{smoke1,smoke2,diag1,diag2}/calls/`.
- Inputs: `data/` (commitments for diag, diagc2, diagsmoke, diagsmokec2).
- Source: `<DREAM_HOME>/Code/DREAM-project-1.7.2-temporal-diagnostic-20261105`; tests 36/36 in `test-results/tempo-diag-tests-1.7.2.txt`.
- Re-score: `python3 -B scripts/diag_analyze.py --hub HUB --set diag --stage1 diag1 --stage2 diag2 --pilot-hub ../temporal-pilot-20261104-232811`
