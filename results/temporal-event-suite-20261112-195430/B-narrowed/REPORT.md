# EVTR-v1 development screen: narrowed event sentence (KEEP_EVTR)

**Status: COMPLETE. Reading: DOES_NOT_WARRANT.** development screen.

Qwen3-32B NF4, greedy, thinking off. Fresh generated worlds (assembly domain). RESULT and TRANSITION arrival wordings balanced in every family x reception stratum.

## Side by side

| Arm / act | Exact | Usable exact (guard) | State-only | Wrong binding (before → after guard) | Exact blocked | Rejected | Truncated | With revision objects | With event objects |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| KEEP_CLAR arrival | 264/288 | 264/288 | 21 | 3 → 0 | 0 | 0 | 0 | 0 | 267 |
| KEEP_CLAR correction | 192/192 | 192/192 | 0 | 0 → 0 | 0 | 0 | 0 | 192 | 0 |
| KEEP_EVT arrival | 281/288 | 281/288 | 0 | 2 → 0 | 0 | 5 | 0 | 1 | 288 |
| KEEP_EVT correction | 192/192 | 192/192 | 0 | 0 → 0 | 0 | 0 | 0 | 192 | 0 |
| KEEP_EVTR arrival | 255/288 | 255/288 | 28 | 3 → 0 | 0 | 2 | 0 | 2 | 260 |
| KEEP_EVTR correction | 192/192 | 192/192 | 0 | 0 → 0 | 0 | 0 | 0 | 192 | 0 |

Object-presence counts come from normalized parsed raw claims, including compiler-rejected replies; replies that fail parsing/normalization are excluded from them.

## Arrivals by wording

| Arm | Wording | Exact | Usable exact | State-only | Wrong binding | Rejected |
|---|---|---:|---:|---:|---:|---:|
| KEEP_CLAR | RESULT | 123/144 | 123/144 | 21 | 0 | 0 |
| KEEP_CLAR | TRANSITION | 141/144 | 141/144 | 0 | 3 | 0 |
| KEEP_EVT | RESULT | 140/144 | 140/144 | 0 | 0 | 4 |
| KEEP_EVT | TRANSITION | 141/144 | 141/144 | 0 | 2 | 1 |
| KEEP_EVTR | RESULT | 115/144 | 115/144 | 28 | 0 | 1 |
| KEEP_EVTR | TRANSITION | 140/144 | 140/144 | 0 | 3 | 1 |

## Paired stem differences

| Contrast | Stems | Difference (points) | Bootstrap 95% (points) | Target rescues / breaks |
|---|---:|---:|---:|---:|
| arrival\|KEEP_EVTR-KEEP_CLAR | 144 | -3.12 | [-6.94, +0.69] | 9 / 18 |
| correction\|KEEP_EVTR-KEEP_CLAR | 48 | +0.00 | [+0.00, +0.00] | 0 / 0 |
| arrival\|RESULT\|KEEP_EVTR-KEEP_CLAR | 72 | -5.56 | [-12.50, +1.39] | 7 / 15 |
| arrival\|TRANSITION\|KEEP_EVTR-KEEP_CLAR | 72 | -0.69 | [-3.47, +2.08] | 2 / 3 |
| arrival\|usable_exact\|KEEP_EVTR-KEEP_CLAR | 144 | -3.12 | [-6.94, +0.69] | 9 / 18 |
| correction\|usable_exact\|KEEP_EVTR-KEEP_CLAR | 48 | +0.00 | [+0.00, +0.00] | 0 / 0 |
| arrival\|RESULT\|usable_exact\|KEEP_EVTR-KEEP_CLAR | 72 | -5.56 | [-12.50, +1.39] | 7 / 15 |
| arrival\|TRANSITION\|usable_exact\|KEEP_EVTR-KEEP_CLAR | 72 | -0.69 | [-3.47, +2.08] | 2 / 3 |
| arrival\|KEEP_EVT-KEEP_CLAR | 144 | +5.90 | [+2.08, +10.07] | 24 / 7 |
| correction\|KEEP_EVT-KEEP_CLAR | 48 | +0.00 | [+0.00, +0.00] | 0 / 0 |
| arrival\|RESULT\|KEEP_EVT-KEEP_CLAR | 72 | +11.81 | [+6.25, +17.36] | 21 / 4 |
| arrival\|TRANSITION\|KEEP_EVT-KEEP_CLAR | 72 | +0.00 | [-3.47, +3.47] | 3 / 3 |
| arrival\|usable_exact\|KEEP_EVT-KEEP_CLAR | 144 | +5.90 | [+2.08, +10.07] | 24 / 7 |
| correction\|usable_exact\|KEEP_EVT-KEEP_CLAR | 48 | +0.00 | [+0.00, +0.00] | 0 / 0 |
| arrival\|RESULT\|usable_exact\|KEEP_EVT-KEEP_CLAR | 72 | +11.81 | [+6.25, +17.36] | 21 / 4 |
| arrival\|TRANSITION\|usable_exact\|KEEP_EVT-KEEP_CLAR | 72 | +0.00 | [-3.47, +3.47] | 3 / 3 |
| arrival\|KEEP_EVTR-KEEP_EVT | 144 | -9.03 | [-13.54, -4.51] | 5 / 31 |
| correction\|KEEP_EVTR-KEEP_EVT | 48 | +0.00 | [+0.00, +0.00] | 0 / 0 |
| arrival\|RESULT\|KEEP_EVTR-KEEP_EVT | 72 | -17.36 | [-24.31, -10.42] | 4 / 29 |
| arrival\|TRANSITION\|KEEP_EVTR-KEEP_EVT | 72 | -0.69 | [-2.78, +1.39] | 1 / 2 |
| arrival\|usable_exact\|KEEP_EVTR-KEEP_EVT | 144 | -9.03 | [-13.54, -4.51] | 5 / 31 |
| correction\|usable_exact\|KEEP_EVTR-KEEP_EVT | 48 | +0.00 | [+0.00, +0.00] | 0 / 0 |
| arrival\|RESULT\|usable_exact\|KEEP_EVTR-KEEP_EVT | 72 | -17.36 | [-24.31, -10.42] | 4 / 29 |
| arrival\|TRANSITION\|usable_exact\|KEEP_EVTR-KEEP_EVT | 72 | -0.69 | [-2.78, +1.39] | 1 / 2 |

Bootstrap use: descriptive 95% percentile interval only; never a gate.

## Reading (frozen before output)

| Criterion | Rule | Result |
|---|---|---|
| state_only_halved_with_baseline_at_least_10 | KEEP_EVTR <= floor(KEEP_CLAR / 2) and KEEP_CLAR >= 10 | **fail** |
| arrival_exact_not_lower | arrival exact KEEP_EVTR-KEEP_CLAR >= 0 points | **fail** |
| transition_exact_not_lower_than_3_points | TRANSITION exact KEEP_EVTR-KEEP_CLAR >= -3 points | pass |
| transition_exact_not_below_keep_evt | TRANSITION exact KEEP_EVTR-KEEP_EVT >= 0 points | **fail** |
| wrong_bindings_within_pooled_tolerance | accepted wrong bindings KEEP_EVTR <= KEEP_CLAR + 4 | pass |
| correction_exact_not_lower_than_3_64 | correction exact KEEP_EVTR-KEEP_CLAR >= -3/64 | pass |

New outcome classes or sub-patterns under the candidate: {'arrival\|outcomes': {'rejected event + extra state (mixed_acts)': 2}, 'arrival\|subpatterns': {'arrival with spurious revisions': 2}}.

**Interpretation fixed before output:** Criterion transition_exact_not_below_keep_evt screens for no observed additional TRANSITION loss relative to KEEP_EVT. Equality can pass; it does not establish removal of KEEP_EVT's cost. The correction screen permits a point-estimate loss of up to 4.6875 percentage points. KEEP_EVTR is a composite of scope narrowing and a state-time instruction; this screen cannot attribute an effect to either clause.

**Guard invariants:** These panels retain only targets on which the public identity resolver agrees with the construction's gold identity. With the pinned scorer and guard, zero post-guard accepted wrong bindings and zero exact answers blocked are expected structural invariants on retained targets. The guarded replay checks this pipeline behavior; it does not independently test resolver correctness, unsupported identities or guard safety. Violation in this run: none.

State-only arrivals: {'KEEP_CLAR': 21, 'KEEP_EVT': 0, 'KEEP_EVTR': 28}. Accepted wrong bindings: {'KEEP_CLAR': 3, 'KEEP_EVT': 2, 'KEEP_EVTR': 3}; after guard: {'KEEP_CLAR': 0, 'KEEP_EVT': 0, 'KEEP_EVTR': 0}; exact blocked: {'KEEP_CLAR': 0, 'KEEP_EVT': 0, 'KEEP_EVTR': 0}.

## Non-exact sub-patterns (descriptive)

| Arm / act | Sub-patterns |
|---|---|
| KEEP_CLAR arrival | {'accepted state-only': 21, 'accepted wrong binding': 3} |
| KEEP_CLAR correction | none |
| KEEP_EVT arrival | {'arrival with correct event and result state dated at the true receipt time': 4, 'accepted wrong binding': 2, 'arrival with spurious revisions': 1} |
| KEEP_EVT correction | none |
| KEEP_EVTR arrival | {'accepted state-only': 28, 'accepted wrong binding': 3, 'arrival with spurious revisions': 2} |
| KEEP_EVTR correction | none |

Accepted wrong bindings (all listed):

- `v27b-g0007|arrival|na|B|KEEP_CLAR` TRANSITION bits 010 immediate: guard identity_mismatch (['Jedadobe.on_hand'] vs Kufedici.on_hand)
- `v27b-g0031|arrival|na|B|KEEP_EVT` TRANSITION bits 010 immediate: guard identity_mismatch (['Jebikabo.on_hand'] vs Bofojuci.on_hand)
- `v27b-g0031|arrival|na|B|KEEP_EVTR` TRANSITION bits 010 immediate: guard identity_mismatch (['Jebikabo.on_hand'] vs Bofojuci.on_hand)
- `v27b-g0047|arrival|na|B|KEEP_CLAR` TRANSITION bits 010 delayed: guard identity_mismatch (['Hihiheku.on_hand'] vs Kofekabu.on_hand)
- `v27b-g0108|arrival|na|B|KEEP_EVT` TRANSITION bits 110 delayed: guard identity_mismatch (['Dudocada.on_hand'] vs Fucufada.on_hand)
- `v27b-g0108|arrival|na|B|KEEP_EVTR` TRANSITION bits 110 delayed: guard identity_mismatch (['Dudocada.on_hand'] vs Fucufada.on_hand)
- `v27b-g0143|arrival|na|A|KEEP_CLAR` TRANSITION bits 010 delayed: guard identity_mismatch (['Jebokobo.on_hand'] vs Jofacici.on_hand)
- `v27b-g0143|arrival|na|A|KEEP_EVTR` TRANSITION bits 010 delayed: guard identity_mismatch (['Jebokobo.on_hand'] vs Jofacici.on_hand)

Truncated replies: none. Exact answers blocked by the guard: none.

## Cost

- KEEP_CLAR: mean 12.7 s/call, max input 1542 tokens, mean output 148 tokens (max 195)
- KEEP_EVT: mean 13.3 s/call, max input 1582 tokens, mean output 155 tokens (max 211)
- KEEP_EVTR: mean 13.6 s/call, max input 1592 tokens, mean output 158 tokens (max 256)

## Scope

- One fresh panel of generated worlds of the declared families (assembly domain only), one model, fixed decoding.
- Passing a threshold on a point estimate is not equivalence or non-inferiority.
- Rejected answers remain wrong; the guard turns detected identity mismatches into rejections. It does not address event omission.
- No qualification, transfer, rare-error elimination or safety claim. The protocol stops after reporting.

Full data: `analysis/dev/ANALYSIS.json`, per-call `analysis/dev/scored.jsonl`.
