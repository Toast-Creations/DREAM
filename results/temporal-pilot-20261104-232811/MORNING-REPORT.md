# DREAM temporal pilot: morning report

## Status and main finding

- Run: stage `main`, source 1.7.1 (`<DREAM_HOME>/Code/DREAM-project-1.7.1-temporal-c0-order-20261105`), hub `<DREAM_HOME>/Runs/temporal-pilot-20261104-232811`. Ran 2026-11-04 23:34–23:49 America/New_York.
- **Completed**: 792/792 planned calls, all `ok`, 0 invalid replies, 0 truncations, 0 infrastructure retries.
- **Main finding.** With the full record history (C1), Qwen3-8B almost always chose "observe first": 195 of 216 decisions, at every length (66/72 short, 63/72 medium, 66/72 long), including 177 of 192 where the state was fully determined. So **C1 complete-pair correctness was 0.0** (0/72 pair cells), against **0.333 for the supplied-state diagnostic C0**: C1 − C0 = −0.333 [−0.50, −0.18], 9 groups worse, 15 equal, 0 better. The same model read the goal fact's current value correctly from the same histories 85% of the time (S0, separate call). So the C1 deficit is mainly a **decision-use / over-abstention** failure, not a failure to reconstruct state.
- **Uncertain.** It's unclear how much of the abstention comes from my prompt wording ("sure to work", the "observe first" option, rule 7 about "unknown") rather than the model's handling of histories. The pilot can't separate them, because C0 uses the same wording and abstains less (79/192). Every cell is small (2 groups per pattern per domain).

## What actually ran

| Block | Planned independent groups | Attempted groups | Completed matched groups | Completed calls / planned calls | Status |
| --- | ---: | ---: | ---: | ---: | --- |
| E1 state/history (D0/D1/I1, S0) | 24 | 24 | 24 | 360 / 360 | complete |
| E2 evidence revision (P0, K0; D0/D1 in patterns 2–6) | 24 | 24 | 24 | 144 / 144 (+ decisions above) | complete |
| E3 one-step consequences (A0) | 24 | 24 | 24 | 144 / 144 | complete |
| Optional extensions (C2 ledger, C3 latest-message, E4 clocks) | — | 0 | 0 | 0 | not run (not budgeted) |

There are 24 unique independent groups across all blocks (12 delivery, 12 assembly; 6 patterns × 2 per domain), each with 3 nested lengths. Nothing was omitted. Smoke: `smoke2`, 52 calls on 4 disjoint groups, never pooled.

## Conditions and integrity

- Model: Qwen3-8B rev `b968826d9c46dd6066d109eabc6255188de91218`, bf16, CUDA, thinking off, greedy. Output caps: decisions 64, S0 384, P0/K0 256, A0 512 (max used: 112). Input ceiling 8,192 (max used: 1,904 tokens).
- Hashes: `config/FROZEN-PROTOCOL.json` (source `b5bdad9b…`, calls `0301deae…`, gold, groups, stage config, analysis script, design docs), frozen before any main output. Development data only. No old sealed data was read.
- Arms run: C0 (supported current state, unknowns shown with both possibilities) and C1 (all records up to the cutoff). There were no extra ledger calls.
- Simulator/checker agreement: two resolvers, two plan solvers and two A0 implementations agreed on every item. 0 rejected generation attempts.
- Prefix isolation, gold exclusion and branch isolation were checked by tests on all 792 calls (VALIDATION-PLAN.md).
- Infrastructure retries 0; parser failures 0; truncations 0; incomplete records 0.
- Amendment A1 (23:31, before any main output): C0 listed facts in an order that cued the correction side. Fixed in 1.7.1; C1 prompts are byte-identical. The 1.7.0 inputs and smoke are preserved.
- Not pre-registered: the breakdowns marked *exploratory* below were computed after viewing the frozen-analysis output.

## Results

All values are group-level means with domains weighted equally; intervals are descriptive (domain-stratified cluster bootstrap, 10,000 resamples, seed 20261105).

| Outcome | C0 exact-state diagnostic | C1 full history | Optional C2 ledger | Denominator and interpretation |
| --- | --- | --- | --- | --- |
| Complete-pair action correctness | 0.333 [0.18, 0.50] | 0.000 | not run | 72 pair cells per arm (24 groups × 3 lengths); same at every length |
| D0 / D1 / I1 accuracy | 0.50 / 0.54 / 0.49 | 0.14 / 0.08 / 0.14 | | 72 each |
| Same choice on both pair sides | 0.375 | 0.986 | | fixed-response signature |
| Current-state correctness (S0) | not applicable | exact 0.44; field 0.76; goal fact 0.85 | | 72; exact suffers from false "unknown" on other fields |
| Historical-state correctness (P0) | not applicable | exact 0.49; goal fact 0.71 | | 72 |
| Supported-then (K0) | not applicable | exact 0.58; goal fact 0.81 | | 72 |
| Correction handling (patterns 3, 5; goal fact) | | P0 1.00 / 1.00; K0 0.92 / 1.00 | | 12 rows each; corrections applied to the past, withheld from the earlier prefix |
| Delayed report (pattern 2; goal fact) | | S0 0.50; P0 0.17; K0 0.50 | | 12 rows; the weakest pattern |
| Stale (lure) choice rate, D0 | 0.10 | 0.05 | | patterns 1–5; low because C1 mostly abstains |
| Unknown handling: D0 "observe" correct (pattern 6) | 0.75 | 0.75 | | 12 rows |
| Resolved D1 plan correct (pattern 6) | 0.92 | 0.25 | | 12 rows |
| Needless "observe" (key is a plan) | 0.37 | 0.90 | | 192 rows (D0/D1/I1) |
| False "unknown" fields in readouts | | S0 35, P0 23, K0 27 fields | | mostly non-goal fields of provisional or late reports (patterns 2, 3, 5) |
| A0 applicability correct | 0.71 | 0.40 | | 72; by class (C0 / C1): true 1.00 / 0.54, **false 0.12 / 0.00** (21 rows), unknown 0.75 / 0.75 (12) |
| Changed-fact prediction | 1.00 | 1.00 | | 39 rows with a determinate changed field (only applicable actions) |
| Unchanged-fact preservation (A0 preserve fields) | 0.88 | 0.75 | | 72 |
| Observed world unchanged by the hypothetical (A0) | 0.76 | 0.44 | | 72 |
| A0 all three parts correct | 0.375 | 0.056 | | 72 |
| Irrelevant-change invariance: I1 same as D0 / both correct | 0.94 / 0.47 | 0.99 / 0.14 | | 72; C1 is invariant because it abstains in both |

Complete-pair correctness by pattern (C0): change 0.17, delayed 0.00, correction 0.42, return 0.50, scoped correction 0.25, uncertain 0.67. By domain (C0): delivery 0.17, assembly 0.50. C1 is 0.00 in every cell. The group-level table is `stages/main/analysis/TABLES.md`.

*Exploratory (after viewing):* among decisions where a plan, not "observe", was the key, C0 chose a plan in 113 of 192 and was right in 92 of those 113 (81%; delivery 33/39, assembly 59/74). C1 chose a plan in only 15 of 192 (delivery 0/96; assembly 15/96, 8 correct). When the proposed action was not allowed, C1 answered `true` 16 times and `unknown` 5 times, never `false`. C0 answered `true` in 18 of 21.

## Costs and operational record

- Elapsed 947 s including 21 s model load; 923.5 s of generation (1.17 s per call). Peak 15.72 GiB GPU allocated. Input mean 1,178 tokens, max 1,904. Output total 26,854 tokens (cap sum 165,888). Stage disk use 3.5 MB.
- Smoke2: 85 s for 52 calls. First smoke (1.7.0, superseded): 85 s.
- Hard cap 6 h / 792 calls. The stop reason was a finished queue (END.json); no overshoot.
- GPU: the explicit-context S48 stage ended at 23:17, and its declared analysis was applied at 23:20 (decision 5, stop that recipe). The temporal stages ran after it, one at a time. Sleep was blocked only while each stage ran.
- Resume: not needed; the run is complete. Re-scoring: `python3 -B scripts/tempo_analyze.py --hub HUB --stage main --set main` from the source directory.

## Interpretation and next action

- **Exact-state diagnostic (planning and rule use).** When C0 committed to a plan it was mostly right (81%), but it abstained on 41% of determined items, especially in delivery (57/96). Rule application is reasonable; the willingness to commit is the weak point even with state supplied.
- **History contrast (reconstruction burden).** The C1 − C0 gap (−0.33) is almost all extra abstention: C1 picked "observe" 90% of the time on determined items, while its separate state readouts got the goal fact right 85% (S0). This matches the specification's case "correct readout with wrong actions": the problem is state-to-decision integration, here as over-caution. It does not show a reconstruction failure. Length did not matter (6 vs 30 records).
- **Corrections and delayed reports.** Corrections were handled well in readouts: past state revised (P0 goal fact 1.00) and kept out of the earlier prefix (K0 0.92–1.00). Delayed old reports were the hardest case (P0 goal fact 0.17). The model also often answered "unknown" for facts given only by a provisional or late report, contrary to rule 5.
- **One-step predictions.** Changes were predicted correctly when the action was allowed (1.00, 39 rows). But the model almost never recognized that an action was not allowed (0.12 / 0.00). That is the same missed-prerequisite pattern the explicit-context audit found (occupied and on-hand cases). In C1, the "observed world" answer was often blurred into "unknown" (0.44 exact).
- **Recommended next action**, choosing among the specification's options: improve the model's use of a state it already has correct, with a small, separately labelled diagnostic. On the same 24 groups, run (a) the decision query without the "observe first" option for determined items, and (b) a two-step version where the model first writes the state and then decides from its own readout (the C2 incremental-ledger idea). Separately, (c) a prerequisite-focused A0 set where half the actions are not allowed. This is about 300–600 calls and well under an hour. Don't add adapters, scale up the model, or tune prompts on these items in response.
- **Claims this pilot cannot support.** Any statement about temporal memory capacity or a learned world model; that the model "cannot use history" (its readouts show it can); that the abstention is a model trait rather than a response to this wording; any generalization beyond these two templates and one checkpoint; anything about adapters, creativity or confirmation. Pattern and domain cells hold only 2 groups each.

## Artifacts

- Raw responses: `<DREAM_HOME>/Runs/temporal-pilot-20261104-232811/stages/main/calls/`
- Scores: `<DREAM_HOME>/Runs/temporal-pilot-20261104-232811/stages/main/analysis/scores.jsonl`
- Analysis: `<DREAM_HOME>/Runs/temporal-pilot-20261104-232811/stages/main/analysis/ANALYSIS.json`
- Group table: `<DREAM_HOME>/Runs/temporal-pilot-20261104-232811/stages/main/analysis/TABLES.md`
- Protocol and amendments: `<DREAM_HOME>/Runs/temporal-pilot-20261104-232811/design/` and `<DREAM_HOME>/Runs/temporal-pilot-20261104-232811/config/FROZEN-PROTOCOL.json`
- Analysis entry point: `<DREAM_HOME>/Code/DREAM-project-1.7.1-temporal-c0-order-20261105/scripts/tempo_analyze.py`
