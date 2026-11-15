# EVTC-v1 confirmation: KEEP_EVT + IGUARD vs KEEP_CLAR + IGUARD

**Status: COMPLETE. Reading: REVIEW_NEW_FAILURE_TYPES.** confirmation on one fresh panel.

Qwen3-32B NF4, greedy, thinking off. Fresh generated worlds (assembly domain). RESULT and TRANSITION arrival wordings balanced in every family x reception stratum.

## Side by side

| Arm / act | Exact | Usable exact (guard) | State-only | Wrong binding (before → after guard) | Exact blocked | Rejected | Truncated | With revision objects | With event objects |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| KEEP_CLAR arrival | 523/576 | 523/576 | 47 | 5 → 0 | 0 | 1 | 0 | 1 | 529 |
| KEEP_CLAR correction | 192/192 | 192/192 | 0 | 0 → 0 | 0 | 0 | 0 | 192 | 0 |
| KEEP_EVT arrival | 561/576 | 561/576 | 0 | 8 → 0 | 0 | 7 | 1 | 1 | 575 |
| KEEP_EVT correction | 192/192 | 192/192 | 0 | 0 → 0 | 0 | 0 | 0 | 192 | 0 |

Object-presence counts come from normalized parsed raw claims, including compiler-rejected replies; replies that fail parsing/normalization are excluded from them.

## Arrivals by wording

| Arm | Wording | Exact | Usable exact | State-only | Wrong binding | Rejected |
|---|---|---:|---:|---:|---:|---:|
| KEEP_CLAR | RESULT | 239/288 | 239/288 | 47 | 1 | 1 |
| KEEP_CLAR | TRANSITION | 284/288 | 284/288 | 0 | 4 | 0 |
| KEEP_EVT | RESULT | 283/288 | 283/288 | 0 | 0 | 5 |
| KEEP_EVT | TRANSITION | 278/288 | 278/288 | 0 | 8 | 2 |

## Paired stem differences

| Contrast | Stems | Difference (points) | Bootstrap 95% (points) | Target rescues / breaks |
|---|---:|---:|---:|---:|
| arrival\|KEEP_EVT-KEEP_CLAR | 288 | +6.60 | [+3.65, +9.55] | 50 / 12 |
| correction\|KEEP_EVT-KEEP_CLAR | 48 | +0.00 | [+0.00, +0.00] | 0 / 0 |
| arrival\|RESULT\|KEEP_EVT-KEEP_CLAR | 144 | +15.28 | [+10.76, +19.79] | 48 / 4 |
| arrival\|TRANSITION\|KEEP_EVT-KEEP_CLAR | 144 | -2.08 | [-4.17, +0.00] | 2 / 8 |
| arrival\|usable_exact\|KEEP_EVT-KEEP_CLAR | 288 | +6.60 | [+3.65, +9.55] | 50 / 12 |
| correction\|usable_exact\|KEEP_EVT-KEEP_CLAR | 48 | +0.00 | [+0.00, +0.00] | 0 / 0 |
| arrival\|RESULT\|usable_exact\|KEEP_EVT-KEEP_CLAR | 144 | +15.28 | [+10.76, +19.79] | 48 / 4 |
| arrival\|TRANSITION\|usable_exact\|KEEP_EVT-KEEP_CLAR | 144 | -2.08 | [-4.17, +0.00] | 2 / 8 |

Bootstrap use: 95% percentile interval; its lower bound is a declared gate for the primary criterion only; all other intervals descriptive.

## Reading (frozen before output)

| Criterion | Rule | Result |
|---|---|---|
| usable_exact_arrival_gain | difference > 0 points AND bootstrap 95% lower bound > 0 points | pass |
| transition_usable_exact_not_lower_than_3_points | TRANSITION-wording usable-exact difference >= -3 | pass |
| post_guard_wrong_bindings_not_more | post-guard accepted wrong bindings KEEP_EVT <= KEEP_CLAR | pass |
| exact_blocked_at_most_1_per_arm | exact answers blocked by the guard <= 1 in each arm | pass |
| correction_usable_exact_not_lower_than_3_64 | correction usable-exact difference >= -3/64 | pass |

New outcome classes or sub-patterns under the candidate: {'arrival\|outcomes': {'rejected (parse)': 1, 'rejected event + extra state (multiple_events)': 1}, 'arrival\|subpatterns': {'arrival with correct event and result state dated at the true receipt time': 4, 'unparsed (truncated)': 1, 'rejected event + extra state (multiple_events)': 1}}.

**Interpretation fixed before output:** The TRANSITION and correction screens permit point-estimate losses of up to 3 and 4.6875 percentage points respectively. Passing them is not evidence of no cost or statistical non-inferiority. Pre-guard wrong-binding increases remain adverse descriptive evidence even when the guarded policy passes.

**Guard invariants:** These panels retain only targets on which the public identity resolver agrees with the construction's gold identity. With the pinned scorer and guard, zero post-guard accepted wrong bindings and zero exact answers blocked are expected structural invariants on retained targets. The guarded replay checks this pipeline behavior; it does not independently test resolver correctness, unsupported identities or guard safety. Violation in this run: none.

State-only arrivals: {'KEEP_CLAR': 47, 'KEEP_EVT': 0}. Accepted wrong bindings: {'KEEP_CLAR': 5, 'KEEP_EVT': 8}; after guard: {'KEEP_CLAR': 0, 'KEEP_EVT': 0}; exact blocked: {'KEEP_CLAR': 0, 'KEEP_EVT': 0}.

## Non-exact sub-patterns (descriptive)

| Arm / act | Sub-patterns |
|---|---|
| KEEP_CLAR arrival | {'accepted state-only': 47, 'arrival with spurious revisions': 1, 'accepted wrong binding': 5} |
| KEEP_CLAR correction | none |
| KEEP_EVT arrival | {'accepted wrong binding': 8, 'arrival with correct event and result state dated at the true receipt time': 4, 'unparsed (truncated)': 1, 'rejected event + extra state (multiple_events)': 1, 'arrival with spurious revisions': 1} |
| KEEP_EVT correction | none |

Accepted wrong bindings (all listed):

- `v27a-g0011|arrival|na|B|KEEP_EVT` TRANSITION bits 010 delayed: guard identity_mismatch (['Bohecife.on_hand'] vs Cojufihu.on_hand)
- `v27a-g0031|arrival|na|B|KEEP_CLAR` TRANSITION bits 010 immediate: guard identity_mismatch (['Didacaca.on_hand'] vs Dabicacu.on_hand)
- `v27a-g0031|arrival|na|B|KEEP_EVT` TRANSITION bits 010 immediate: guard identity_mismatch (['Didacaca.on_hand'] vs Dabicacu.on_hand)
- `v27a-g0059|arrival|na|B|KEEP_CLAR` TRANSITION bits 010 delayed: guard identity_mismatch (['Fihacufu.on_hand'] vs Cijufehu.on_hand)
- `v27a-g0059|arrival|na|B|KEEP_EVT` TRANSITION bits 010 delayed: guard identity_mismatch (['Fihacufu.on_hand'] vs Cijufehu.on_hand)
- `v27a-g0115|arrival|na|B|KEEP_EVT` TRANSITION bits 010 immediate: guard identity_mismatch (['Bobiceji.on_hand'] vs Fohofeju.on_hand)
- `v27a-g0139|arrival|na|B|KEEP_EVT` TRANSITION bits 010 immediate: guard identity_mismatch (['Hubujuka.on_hand'] vs Kakecubo.on_hand)
- `v27a-g0190|arrival|na|B|KEEP_CLAR` RESULT bits 100 delayed: guard identity_mismatch (['Dedofoho.on_hand'] vs Cikebifa.on_hand)
- `v27a-g0215|arrival|na|B|KEEP_CLAR` TRANSITION bits 010 delayed: guard identity_mismatch (['Fejodube.on_hand'] vs Kadakike.on_hand)
- `v27a-g0240|arrival|na|B|KEEP_EVT` TRANSITION bits 110 delayed: guard identity_mismatch (['Fejukaki.on_hand'] vs Cekakubo.on_hand)
- `v27a-g0267|arrival|na|B|KEEP_EVT` TRANSITION bits 010 immediate: guard identity_mismatch (['Hihocebe.on_hand'] vs Hibicede.on_hand)
- `v27a-g0271|arrival|na|B|KEEP_CLAR` TRANSITION bits 010 immediate: guard identity_mismatch (['Jefubobe.on_hand'] vs Hokidofa.on_hand)
- `v27a-g0283|arrival|na|B|KEEP_EVT` TRANSITION bits 010 immediate: guard identity_mismatch (['Cuficija.on_hand'] vs Bidodaca.on_hand)

Truncated replies: ['v27a-g0088|arrival|na|A|KEEP_EVT']. Exact answers blocked by the guard: none.

## Cost

- KEEP_CLAR: mean 12.4 s/call, max input 1534 tokens, mean output 145 tokens (max 201)
- KEEP_EVT: mean 13.1 s/call, max input 1574 tokens, mean output 154 tokens (max 256)

## Scope

- One fresh panel of generated worlds of the declared families (assembly domain only), one model, fixed decoding.
- Passing a threshold on a point estimate is not equivalence or non-inferiority.
- Rejected answers remain wrong; the guard turns detected identity mismatches into rejections. It does not address event omission.
- No qualification, transfer, rare-error elimination or safety claim. The protocol stops after reporting.

Full data: `analysis/dev/ANALYSIS.json`, per-call `analysis/dev/scored.jsonl`.
