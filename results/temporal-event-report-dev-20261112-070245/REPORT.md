# EVT-v1 event-reporting development comparison

**Status: COMPLETE. Development screen: DOES_NOT_WARRANT.** Not a qualification gate.

Arms: KEEP_CLAR (current), KEEP_EVT (KEEP_CLAR + one event-reporting sentence). Qwen3-32B NF4, greedy, thinking off. Fresh generated worlds; F1:F2:F3 = 1:1:4; RESULT and TRANSITION arrival wordings balanced.

## Side by side

| Arm / act | Exact | Accepted state-only | Accepted wrong binding | Accepted inexact | Rejected | Withdrawn value | Truncated | With revision objects | With event objects |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| KEEP_CLAR arrival | 258/288 | 26 | 1 | 27 | 3 | 0 | 0 | 3 | 262 |
| KEEP_CLAR correction | 192/192 | 0 | 0 | 0 | 0 | 0 | 0 | 192 | 0 |
| KEEP_EVT arrival | 279/288 | 0 | 4 | 4 | 5 | 0 | 0 | 2 | 288 |
| KEEP_EVT correction | 192/192 | 0 | 0 | 0 | 0 | 0 | 0 | 192 | 0 |

Revision objects on arrivals and event objects on corrections are spurious for these targets; counts are from compiled replies (unparseable replies are not counted there).

## Arrivals by wording

| Arm | Wording | Exact | Accepted state-only | Rejected |
|---|---|---:|---:|---:|
| KEEP_CLAR | RESULT | 115/144 | 26 | 3 |
| KEEP_CLAR | TRANSITION | 143/144 | 0 | 0 |
| KEEP_EVT | RESULT | 140/144 | 0 | 4 |
| KEEP_EVT | TRANSITION | 139/144 | 0 | 1 |

## Paired stem differences (descriptive bootstrap intervals, not gates)

| Contrast | Stems | Difference (points) | Bootstrap 95% (points) | Target rescues / breaks |
|---|---:|---:|---:|---:|
| arrival: KEEP_EVT-KEEP_CLAR | 144 | +7.29 | [+2.78, +12.15] | 29 / 8 |
| arrival: usable_exact KEEP_EVT-KEEP_CLAR | 144 | +7.29 | [+2.78, +12.15] | 29 / 8 |
| correction: KEEP_EVT-KEEP_CLAR | 48 | +0.00 | [+0.00, +0.00] | 0 / 0 |
| correction: usable_exact KEEP_EVT-KEEP_CLAR | 48 | +0.00 | [+0.00, +0.00] | 0 / 0 |
| arrival: RESULT KEEP_EVT-KEEP_CLAR | 72 | +17.36 | [+9.72, +25.00] | 29 / 4 |
| arrival: TRANSITION KEEP_EVT-KEEP_CLAR | 72 | -2.78 | [-5.56, -0.69] | 0 / 4 |

## Reading guide (frozen before output)

| Criterion | Result |
|---|---|
| state_only_halved_with_baseline_at_least_10 | pass |
| arrival_exact_not_lower | pass |
| transition_wording_arrival_exact_not_lower_than_3_points | pass |
| wrong_bindings_not_more_than_plus_2 | **fail** |
| correction_exact_not_lower_than_3_64 | pass |

State-only arrivals: {'KEEP_CLAR': 26, 'KEEP_EVT': 0}. Accepted wrong bindings (all acts): {'KEEP_CLAR': 1, 'KEEP_EVT': 4}.
New outcome classes in KEEP_EVT (absent in KEEP_CLAR): {'arrival': {}, 'correction': {}}.

## Guarded replay (IGUARD-v0.1 decision function, unchanged)

| Arm / act | Exact → usable exact | Wrong binding before → after | Exact blocked | Guard dispositions |
|---|---:|---:|---:|---|
| KEEP_CLAR arrival | 258 → 258 | 1 → 0 | 0 | {'pass': 284, 'identity_mismatch': 1, 'compile_rejected': 3} |
| KEEP_CLAR correction | 192 → 192 | 0 → 0 | 0 | {'pass': 192} |
| KEEP_EVT arrival | 279 → 279 | 4 → 0 | 0 | {'pass': 279, 'identity_mismatch': 4, 'compile_rejected': 5} |
| KEEP_EVT correction | 192 → 192 | 0 → 0 | 0 | {'pass': 192} |

Accepted wrong bindings (all listed):

- `v26-g0007|arrival|na|B|KEEP_EVT` bits 010 immediate: guard identity_mismatch (['Jihuhudo.on_hand'] vs Coboceje.on_hand)
- `v26-g0019|arrival|na|B|KEEP_EVT` bits 010 immediate: guard identity_mismatch (['Fudekobo.on_hand'] vs Hubufude.on_hand)
- `v26-g0047|arrival|na|B|KEEP_CLAR` bits 010 delayed: guard identity_mismatch (['Dokekako.on_hand'] vs Cejefuka.on_hand)
- `v26-g0047|arrival|na|B|KEEP_EVT` bits 010 delayed: guard identity_mismatch (['Dokekako.on_hand'] vs Cejefuka.on_hand)
- `v26-g0088|arrival|na|B|KEEP_EVT` bits 110 delayed: guard identity_mismatch (['Kidehofe.on_hand'] vs Jocadodu.on_hand)

Truncated replies: none.

## Cost

- KEEP_CLAR: mean 12.8 s/call, max input 1532 tokens, mean output 149 tokens
- KEEP_EVT: mean 13.4 s/call, max input 1572 tokens, mean output 155 tokens

## Scope

- Development screen on fresh generated worlds of the declared families (assembly domain only), one model and fixed decoding. The sentence's examples name actions from this world's rules.
- Passing a threshold on a point estimate is not equivalence or non-inferiority; intervals are descriptive.
- Rejected answers remain wrong. The guard addresses identity, not event omission.
- No qualification, transfer, rare-error elimination or safety claim. The protocol stops after reporting.

Full data: `analysis/dev/ANALYSIS.json`, per-call `analysis/dev/scored.jsonl`.
