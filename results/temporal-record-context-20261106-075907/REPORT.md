# Record-context ablation, FULL vs LOCAL extraction (V1.17.0): report

- **Date:** 2026-11-06.
- **Plan:** `design/STUDY-PLAN.md`, frozen in `config/FROZEN-PROTOCOL.json` (source `c87b3b16…e65b`). The run finished unchanged, with no amendments.
- **Calls:** **996/996 unique main calls ok**, scored as 1,008 cells. The 12 control LOCAL replies are cached once and scored against both alternatives. Smoke: 38/38.
- **Runtime:** 0 truncated, no content retries. Generation took 3,454 s (57.6 min, inside the 90-min cap) and produced 113,412 output tokens.
- **Software gates G1–G4 all pass** (0 failures): prompt isolation (FULL and LOCAL differ only in the context block, both use the NULL_PRIOR schema, no labels in inputs), model configuration and committed order, labels with compatible prefixes, control identity and cache accounting, and complete paired scoring.

## Primary: 120 self-contained arrivals (unit = group, n = 120)

| Paired outcome | Groups |
|---|---|
| Both correct | 25 |
| **LOCAL only** | **24** |
| **FULL only** | **3** |
| Neither | 68 |

**Exact meaning:** FULL 28/120 (23%), LOCAL 49/120 (41%). LOCAL − FULL = **+0.175 [+0.100, +0.250]**, using a group bootstrap within the 8 strata (10,000 resamples, seed 20261106; descriptive).

- **What the rule supports.** The primary is positive with its interval above 0, so the frozen rule supports a benefit from withholding raw history *for these self-contained stock-arrival reports*.
- **Event kind and entity/field are reported separately:**
  - Event kind correct: FULL 28, LOCAL 49. Kind and exact meaning coincide here.
  - Entity/field correct: FULL 112/120, LOCAL **120/120**.
  - Under FULL, 84 arrivals were written as states and 8 were unmapped. These 8 are `initial` replies with no `assign` wrapper; their field was correct in content.
  - Under LOCAL, 71 were states.
- **Prior use:** FULL used a correct prior in 22 arrivals and null in 6; LOCAL used null in all 49. No arrival in either condition named the wrong part.
- **The state misread still dominates in both conditions.** 59% of LOCAL arrivals and 70% of FULL arrivals are states. Removing history helps, but LOCAL still classifies most arrivals wrongly.
- **Descriptive pattern by prefix length** (strata are not separately powered):

| Prefix | FULL | LOCAL |
|---|---|---|
| 3 records | 19 / 60 | 24 / 60 |
| 4 records | **9 / 60** | **25 / 60** |

  FULL degrades with a longer history while LOCAL does not. Lure type and mention order show no clear pattern (`by_stratum_arrival`).

## Secondary: the trade-off (same groups, same records)

| Variant (n = 120) | FULL exact | LOCAL exact | LOCAL − FULL | Paired (both / LOCAL only / FULL only / neither) |
|---|---|---|---|---|
| Arrival | 28 | 49 | **+0.175 [+0.10, +0.25]** | 25 / 24 / 3 / 68 |
| Observation | 116 | 119 | +0.025 [−0.008, +0.058] | 115 / 4 / 1 / 0 |
| **Removal** | **102** | **73** | **−0.242 [−0.333, −0.158]** | 69 / 4 / 33 / 14 |
| **Genuine correction** | **112** | **94** | **−0.150 [−0.233, −0.067]** | 89 / 5 / 23 / 3 |

**LOCAL helps arrivals but harms removals and corrections.** As the frozen rules require, this is reported as a trade-off. It is not a justification for a context-free policy.

**Removals under LOCAL** (47 wrong):
- 30 were written as states.
- 17 were rewritten as **corrections of an invented earlier report**: targets such as "r00" or "r03" that do not hold the claim. The evaluator, using the same canonical prefix, rejected them as `correction_target`.

**Removals under FULL** (18 wrong):
- 15 were rewritten as corrections of the actual earlier stock report of P (r01 or r02). They were *accepted* by the contract.
- That is a physical removal re-expressed as "the earlier report was wrong". It is semantically wrong but structurally valid, so it is the more dangerous form.
- 3 were states.

**Corrections:**
- Under LOCAL, 24 replies were unmapped because they put a non-null `event_at` on a correction, which the frozen adapter rule M2 rejects. 2 named the wrong field: a slot instead of a stock field (g055, g075).
- Under FULL, 8 were unmapped for the same M2 reason.
- Every mapped correction had the right target in both conditions (FULL 112/112, LOCAL 96/96).

**Observations:** near ceiling in both conditions. One LOCAL observation named the wrong field (g055: slot instead of stock).

**Wrong-field records with an exact quotation:** FULL 0, LOCAL 3 (g055 observation, g055 correction, g075 correction). All bind to a slot field.

## Context-required controls (12 groups; outside the primary; not a harm rate)
- **FULL** resolved the referent and read the event exactly on **both** alternatives in only **5/12** groups (exact 6/12 under A, 5/12 under B). The field was right on both in 7/12.
  - 8 FULL replies were unmapped (M2): the model rewrote "the part … checked in r02 was delivered" as a *correction* of r02.
  - 4 were accepted corrections or states with the right field but the wrong kind.
  - **FULL often fails these reference-resolution controls.** That is a limitation, and it does not validate FULL.
- **LOCAL** (one shared reply per group) wrote a **state of part G's stock in all 12 groups**, G being the first-listed stock part. Its field matches alternative B in 12/12 and A in 0/12, and it is exact on neither, because it is a state, not an event.
  - This is the intended information limit: a consistent default guess, not resolution.
  - It shows why withholding history cannot be a universal rule wherever referents depend on prior reports.

## Interpretation (frozen rules) and limits
- **Historical interference contributes to arrival misclassification on this designed corpus.** The FULL history turns about 18 percentage points more arrivals into states, and more so with longer prefixes.
- **The same context supports removals and corrections.** Without it, the model fabricates correction targets, turns removals into states, and puts event times on corrections.
- **Neither condition is adequate.** LOCAL still misreads 59% of arrivals, and FULL misreads 70%. FULL also turns some removals into accepted corrections of real earlier reports.
- **Entity/field binding.** On self-contained stock reports, the field was almost always correct: FULL 0 wrong mapped; LOCAL 3 wrong, all bound to slots. That does not establish reliability, and it does not show that the overnight wrong-entity unsafe class (5 copies in 1,536) is resolved. Nothing here measured actions.
- **Scope:** one model, one domain's stock-report language, and frozen templates. No action utility, safety or end-to-end estimate.
- **Stop.** Per the plan, context-window variants stop here. No prefix-length search, rewording, verifier, LOCAL integration or fine-tuning was launched. The next decision is one for David.

## Files
- `data/`: calls in the committed schedule, public targets, commitments; `hidden/`: gold, groups, strata, templates.
- `stages/main/calls/`: raw replies.
- `analysis/main/scored.jsonl`: every cell with the raw reply, adapter log, report, scores, category, acceptance and correction-target check.
- `analysis/main/ANALYSIS.json`: primary, per-variant tables, strata, all discordant cases, controls.
- `phase0/`, `stages/smoke/`, `run_stage.sh STAGE SET [--require-freeze]`.

**Stopped after this report.** The 1.17.0 source is not committed.
