# Factored assertion extraction (V1.18.0): report

- **Date:** 2026-11-06.
- **Plan:** `design/STUDY-PLAN.md`, frozen in `config/FROZEN-PROTOCOL.json` (source `4f33656b…6459`). The run finished unchanged, with no amendments.
- **Calls:** **1,008/1,008 main calls ok** plus 40/40 smoke. **0 truncated** in either interface; no content retries.
- **Software gates G1–G4 all pass** (0 failures): matched prompts and blocks; model configuration and committed order; labels and prefixes, exact compilation of canonical replies, and **canonical replay equal to the independent temporal reference (600 checks)**; complete accounting.

## Primary: four-class macro exact meaning (n = 120 groups)
**EXCLUSIVE 0.696 → FACTORED 0.852. FACTORED − EXCLUSIVE = +0.156 [+0.125, +0.185].** This uses a group bootstrap within the 8 strata (10,000 resamples, seed 20261106; descriptive). FACTORED is higher in all 8 strata.

Under the frozen rule, this supports the representation-and-compiler package on this four-class corpus. The class results below show where the gain comes from and what still fails.

## All four classes

| Class (n = 120) | EXCLUSIVE exact | FACTORED exact | FACTORED − EXCLUSIVE | Paired (both / FACTORED only / EXCLUSIVE only / neither) |
|---|---|---|---|---|
| **Arrival** | 17 | **75** | **+0.483 [+0.392, +0.575]** | 17 / 58 / 0 / 45 |
| Observation | 115 | 120 | +0.042 [+0.008, +0.075] | 115 / 5 / 0 / 0 |
| **Removal** | 92 | 94 | **+0.017 [−0.050, +0.083]** | 83 / 11 / 9 / 17 |
| Genuine correction | 110 | 120 | +0.083 [+0.042, +0.133] | 110 / 10 / 0 / 0 |

- **Most of the gain is in arrivals.** No arrival that EXCLUSIVE got right was lost.
- **The removal effect is inconclusive.** 11 groups gained and 9 lost.
- **Observation and correction gains** come from fewer malformed replies.

## Three things kept separate

### 1. Correct source meaning (a correct endpoint is not a correct act)
**Arrivals:**
- Both interfaces almost always produced the right resulting value: 110 (EXCLUSIVE) and 118 (FACTORED).
- The **act** was where they differed:
  - EXCLUSIVE wrote 93 arrivals as state-only records, against 17 events.
  - FACTORED emitted the event in 75. It still emitted a **state only, with no event, in 43**: factorization fails there, as allowed.
  - 2 FACTORED replies were an event plus a contradictory state (mixed acts).

**Removals: the key failure to watch.**
- **EXCLUSIVE rewrote 12 physical removals as revisions of the earlier report, and all 12 were accepted by the contract. FACTORED did this 0 times.**
- FACTORED did not achieve this through more rejections. Its removal replies that failed to compile or were rejected numbered **3** (2 mixed acts, 1 multiple events). EXCLUSIVE had **5** (4 unmapped, 1 time-order rejection).
- FACTORED's remaining removal errors are **23 state-only replies, all accepted**. That is a different wrong-act failure: no false revision, but the event is lost. EXCLUSIVE had 11 of those.
- So the false-revision failure was replaced largely by state-only omission, and removal exact meaning did not measurably improve (+0.017).

**Revisions claimed where none existed:** 0 under FACTORED in arrivals, observations or removals (the one removal revision sat inside a mixed act). EXCLUSIVE had 12, the removals above.

**Entity/field binding:**

| | Arrival | Observation | Removal | Correction |
|---|---|---|---|---|
| EXCLUSIVE | 110 | 115 | 116 | 110 |
| FACTORED | 118 | 120 | 117 | 120 |

Only one compiled record named a wrong field (g022 arrival, EXCLUSIVE: a slot). Raw FACTORED claims mentioned another field in 2 arrivals and 2 removals, all inside non-compiling mixed acts.

### 2. Compiler and adapter acceptance or rejection

| | Arrival | Observation | Removal | Correction |
|---|---|---|---|---|
| EXCLUSIVE adapter unmapped | 9 | 5 | 4 | 10 |
| EXCLUSIVE contract-rejected | 0 | 0 | 1 | 0 |
| EXCLUSIVE accepted | 111 | 115 | 115 | 110 |
| FACTORED compiler pending | 2 | 0 | 3 | 0 |
| FACTORED accepted | 118 | 120 | 117 | 120 |

- FACTORED's pending codes were mixed acts (2 arrivals, 2 removals) and multiple events (1 removal). It had no parse, invalid-assertion or empty results.
- **Redundancy rules applied:** R2 (an event's matching result state) 85 times; R3 (a revision's valid-from state) 21 times.
- **Acceptance is not correctness:** 43 state-only arrivals and 23 state-only removals were *accepted* under FACTORED.

### 3. Temporal replay
Same canonical prefix; queries on P: Q1 the anchor value with all evidence, Q2 the value now, Q3 the anchor value known before reception.

| | All three queries correct | Q1 / Q2 / Q3 |
|---|---|---|
| Arrival, EXCLUSIVE | 17 | 27 / 17 / 120 |
| Arrival, FACTORED | 75 | 77 / 75 / 120 |
| Removal, EXCLUSIVE | 92 | 97 / 104 / 120 |
| Removal, FACTORED | 94 | 97 / 94 / 120 |
| Observation, both | 120 | |
| Correction, EXCLUSIVE | 110 | |
| Correction, FACTORED | 120 | |

- **Replay success matched exact meaning in every class.**
- **No backward leak:** Q3 (knowledge before reception) was correct in every case, in both interfaces.
- **State-only arrivals** made both "now" and the historical anchor wrong, because the verified state at reception conflicts with the earlier verified "not on hand".
- **EXCLUSIVE's accepted false revisions of removals** rewrote the historical anchor value (Q1 wrong) while leaving "now" right (Q2 104 vs 92 exact). The history was revised instead of a physical change being recorded.

## Context-required controls (12 groups × 2 histories; outside the primary)

| | Correct on both histories | Exact by history | Right referent field (raw claims) |
|---|---|---|---|
| EXCLUSIVE | **2/12** | 3 + 4 | 19/24 |
| FACTORED | **0/12** | 0 + 0 | **21/24** |

- **FACTORED failed these controls completely**, although it **identified the referenced part more often** than EXCLUSIVE.
- **It never emitted an event for "the part whose stock was checked in r02 was delivered to you".**
  - 18 replies were a state **plus an invented revision of r02**: the reference to an earlier record was read as revising it. These are non-compiling mixed acts.
  - 5 were state-only; 1 was a revision.
- **EXCLUSIVE** mostly rewrote the same report as a correction (13/24).
- The controls use a declared control-only phrasing. They show that **reference to an earlier report pulls FACTORED towards false revisions**, the failure class the brief warned about. The compiler rejected those cases, and the result is a failure, not an improvement.

## Cost
- **Output tokens:** EXCLUSIVE 56,665 (mean 112.4 per call); FACTORED 63,702 (mean 126.4), about +12%.
- **Generation time:** 1,751 s against 1,945 s (+11%).
- **Truncations:** none in either interface.

## Interpretation (frozen rules) and limits
- **Macro primary positive, interval above 0.** The package of factored lists plus a deterministic compiler improves exact source meaning on this four-class corpus, and the gain sits mainly in arrivals.
- **Removals accepted as revisions fell from 12 to 0 without extra rejections.** Removal exact meaning did not improve, though: the failure moved to accepted state-only replies.
- **The dominant remaining errors are accepted state-only physical events:** 43 arrivals and 23 removals. That is the event-omission failure the brief named.
- **Controls show a new hazard in this representation.** A report that refers to an earlier record yields invented revisions (18/24), so FACTORED is worse than EXCLUSIVE on referent-dependent reports. It must not be described as reliable.
- **Binding was near ceiling on this corpus.** That says nothing about the overnight wrong-entity unsafe class (5 copies in 1,536). No actions, utility or safety were measured. One model, one domain's stock language, frozen templates.
- **No deployment, verifier, retraining, sensor change or further replication was launched.**

## Files
- `data/`: calls in the committed schedule, public targets, commitments; `hidden/`: gold, groups.
- `stages/main/calls/`: raw paired replies.
- `analysis/main/scored.jsonl`: every cell with the raw reply, normalised and reduced claims, compiler trace and pending code, compiled report, acceptance, scores and replay.
- `analysis/main/ANALYSIS.json`: primary, all classes, strata, discordant cases, controls, runtime.
- `phase0/` (including the token-budget check), `stages/smoke/`, `run_stage.sh`.

**Stopped after this report.** The 1.18.0 source is not committed.
