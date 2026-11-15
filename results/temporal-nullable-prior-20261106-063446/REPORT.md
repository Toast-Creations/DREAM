# Nullable-prior extraction interface test (V1.16.0): report

- **Date:** 2026-11-06.
- **Plan:** `design/STUDY-PLAN.md`, frozen in `config/FROZEN-PROTOCOL.json` (source `1397ed75…aa84`). The run finished unchanged, with no amendments.
- **Calls:** **1,168/1,168 main calls ok** (584 per interface) plus 48/48 smoke. 0 truncated, no content retries.
- **Runtime:** generation 1,762 s (ORIGINAL) and 1,774 s (NULL_PRIOR), about 59,000 output tokens each. CPU evaluation took 20 s for 1,152 decision trajectories; the 3,456 verification runs are counted separately.
- **Order:** calls ran in the precommitted balanced order (`order: as_committed`, documented in the plan).

## Primary: the 23 stock-arrival pairs

| Paired outcome (same record, both interfaces) | Records |
|---|---|
| Both correct | **5** |
| NULL_PRIOR only | **1** (a10i1 r6) |
| ORIGINAL only | **0** |
| Neither correct | **17** |

**Exact meaning:** ORIGINAL 5/23 (22%), NULL_PRIOR 6/23 (26%). The difference is **+0.043 [0.000, +0.130]**, using a world bootstrap stratified by family (10,000 resamples, seed 20261105).

**The interface effect is unresolved.** One discordant pair in 23 cannot separate a small benefit from none, and the interval touches 0. The panel had only 23 arrivals, spread over 10 assembly families and absent from delivery families. Per-family counts are in `analysis/main/ANALYSIS.json`.

**Event-kind and entity/field accuracy on the same 23 records:**

| | ORIGINAL | NULL_PRIOR |
|---|---|---|
| Event kind correct (a change event, not a state) | 5 / 23 | 6 / 23 |
| Entity/field correct (mapped records naming the right field) | 21 / 23 | **23 / 23** |
| Result correct | 5 / 23 | 6 / 23 |
| Accepted by adapter and contract | 21 / 23 | 23 / 23 |

- **The failure is event-versus-state classification, not entity binding.** On these 23 arrivals, every NULL_PRIOR reply and every mapped ORIGINAL reply named the correct part's stock field. In both interfaces, every wrong arrival was written as `kind: "initial"` (a verified state with the right value): 18 in ORIGINAL and 17 in NULL_PRIOR.
- **ORIGINAL's two missing field-attribution credits** (a01i1 r4, a10i1 r5) are `initial` replies whose payload lacked the `assign` wrapper. They were unmapped and left as pending evidence; the field inside them was correct.
- **Prior use among correct arrivals:** NULL_PRIOR used `null` in 4 of 6 and supplied a correct prior in 2. ORIGINAL supplied a correct prior in all 5.
- **So:** the advertised null was taken up when the model already chose `change`. It did not move the 17 state misreads.

## Secondary: other source classes (exact meaning, ORIGINAL / NULL_PRIOR)

| Class | n | Exact | Kind correct | Field correct |
|---|---|---|---|---|
| Stock removal | 16 | 12 / 12 | 12 / 12 | 16 / 15 |
| Location change | 84 | 83 / 83 | 83 / 83 | 84 / 84 |
| Slot change | 31 | 31 / 31 | 31 / 31 | 31 / 31 |
| Location / stock / slot observation | 196 / 122 / 96 | 196/195 · 120/121 · 94/94 | | |
| Uncertain change (location / slot) | 8 / 8 | 7/8 · 8/8 | | |

- **Removal difference:** 0.000 [−0.154, +0.143].
- **Field attribution:** no mapped record named the wrong field in either interface (the overnight run had misattributions).
- **Records that differ between interfaces:** 6. Four favour NULL_PRIOR: the a10i1 arrival, an a04i2 removal, an a10i1 stock observation, and a d11i3 uncertain change. Two favour ORIGINAL: an a07i4 removal that became unmapped, and a d12i1 location observation rejected for time order.
- **Uncertain changes:** NULL_PRIOR used `null` in 7 of 8 slot uncertain changes, where ORIGINAL had supplied the prior. This is legal and was scored correct.

## Downstream: DEPENDENCY on all 96 worlds (goals averaged within world; family-stratified bootstrap)

| Contrast | Mean | 95% interval | worlds + / = / − |
|---|---|---|---|
| Changing: NULL_PRIOR − ORIGINAL | −0.026 | [−0.068, 0.000] | 0 / 94 / 2 |
| Stable: NULL_PRIOR − ORIGINAL | 0.000 | [−0.010, +0.010] | 1 / 94 / 1 |
| Changing: ORIGINAL − structured | −0.64 | [−0.90, −0.40] | 0 / 82 / 14 |
| Changing: NULL_PRIOR − structured | −0.67 | [−0.92, −0.42] | 0 / 80 / 16 |
| Stable: either interface − structured | −0.85 | [−1.18, −0.56] | |

- **The two worse worlds** are the two ORIGINAL-favouring record differences above:
  - **a07i4/B:** the removal reply was unmapped, so the record became pending, an extra fact was queried, support was empty and the copy declined. U −6 against −5.
  - **d12i1/B:** the observation was rejected for time order, support was empty, and a success was lost. U −5 against −1.

  The one NULL_PRIOR arrival gain changed no decision.
- **Totals over 192 changing copies:**

| Channel | U | Successes | Empty support | Historical conflict |
|---|---|---|---|---|
| Structured | −26 | 160 | 0 | 0 |
| ORIGINAL | −149 | 145 | 19 | 30 |
| NULL_PRIOR | −154 | 144 | 21 | 30 |

- **Invalid actual attempts and false completions:** 0 in every channel and environment. There are no unsafe copies.

**Software gates:** S1–S5 all pass with 0 failures. That covers the reference given each interface's own evidence; structured safety; the selector rule with its independent check; perfect parity; gold-poisoning invariance for both interfaces; and clocks, receipts, per-interface context isolation, history, invariants, costs, shared actual state, tape independence and channel lengths.

## Interpretation (frozen rules)
- **Primary inconclusive.** NULL_PRIOR read 1 more arrival correctly, with 0 losses and an interval touching 0. The advertised null is not shown to change event-versus-state classification on this panel. It is also not shown to be harmless or helpful downstream: utility is −0.026 [−0.068, 0.000], driven by 2 unrelated record differences.
- **The dominant failure persists unchanged:** "arrived / delivered → now on hand" is written as a verified state (17–18 of 23). The schema's apparent demand for a prior value was **not a material obstacle** to choosing `change` here.
- **Zero unsafe outcomes and zero wrong-field records on 96 worlds do not show the overnight wrong-entity failure class is fixed.** That class produced 5 copies in 1,536 overnight. This panel is far too small to see it, and nothing here targeted it.
- **Next decision** (not launched):
  - Event classification for stock arrivals remains weak, independently of the null-prior wording.
  - Entity/field binding still needs its own fresh challenge study if it is to be tested.
  - No arrival examples, rewording, context ablation or grounding gate was started.

## Files
- `data/` (commitments, the balanced call schedule, source-kind counts; `hidden/`).
- `stages/main/calls/`: raw paired replies.
- `stages/main/eval/`:
  - `channels.jsonl` (per-interface goal-blind streams and adapter logs);
  - `extraction.jsonl` (source-aware scores, kind, field, result, meta, prior use);
  - `selections.jsonl`, `trajectories.jsonl`, `reference`, `selcheck`, `parity`, `poison`, `leakage`, `feasibility`;
  - `EVAL-META.json`.
- `analysis/main/{ANALYSIS.json, TABLES.md}`, `phase0/`, `stages/smoke/`.

**Stopped after this report.** The 1.16.0 source is not committed.
