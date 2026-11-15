# ESUB-v1 explicit-subject development comparison

**Status: COMPLETE. Development screen: REVIEW_NEW_FAILURE_TYPES.** Not a qualification gate.

Arms: SUB_ORIG (anchor), KEEP_CLAR (current), KEEP_SUBJ (KEEP_CLAR + one explicit-subject sentence). Qwen3-32B NF4, greedy, thinking off. Fresh generated worlds; F1:F2:F3 = 1:1:4.

## Side by side

| Arm / act | Exact | Accepted wrong binding | Accepted state-only | Accepted inexact | Rejected | Withdrawn value | Wrong revision start | Truncated |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| SUB_ORIG arrival | 178/288 | 0 | 109 | 109 | 1 | 0 | 0 | 0 |
| SUB_ORIG correction | 191/192 | 0 | 0 | 0 | 1 | 1 | 0 | 0 |
| KEEP_CLAR arrival | 251/288 | 4 | 31 | 35 | 2 | 0 | 0 | 0 |
| KEEP_CLAR correction | 192/192 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| KEEP_SUBJ arrival | 250/288 | 1 | 32 | 33 | 5 | 0 | 0 | 2 |
| KEEP_SUBJ correction | 192/192 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

## Paired stem differences (descriptive bootstrap intervals, not gates)

| Contrast | Stems | Difference (points) | Bootstrap 95% (points) | Rescues / breaks |
|---|---:|---:|---:|---:|
| arrival|KEEP_SUBJ-KEEP_CLAR | 144 | -0.35 | [-4.51, +3.82] | 16 / 17 |
| arrival|KEEP_SUBJ-SUB_ORIG | 144 | +25.00 | [+18.40, +31.94] | 77 / 5 |
| arrival|KEEP_CLAR-SUB_ORIG | 144 | +25.35 | [+18.06, +32.99] | 81 / 8 |
| arrival|usable_exact|KEEP_SUBJ-KEEP_CLAR | 144 | -0.35 | [-4.51, +3.82] | 16 / 17 |
| correction|KEEP_SUBJ-KEEP_CLAR | 48 | +0.00 | [+0.00, +0.00] | 0 / 0 |
| correction|KEEP_SUBJ-SUB_ORIG | 48 | +0.52 | [+0.00, +1.56] | 1 / 0 |
| correction|KEEP_CLAR-SUB_ORIG | 48 | +0.52 | [+0.00, +1.56] | 1 / 0 |
| correction|usable_exact|KEEP_SUBJ-KEEP_CLAR | 48 | +0.00 | [+0.00, +0.00] | 0 / 0 |

## Reading guide (frozen before output)

| Criterion | Result |
|---|---|
| wrong_bindings_not_more | pass |
| arrival_exact_not_lower_than_3_points | pass |
| state_only_not_more_than_plus_3 | pass |
| correction_exact_not_lower_than_3_64 | pass |

Accepted wrong bindings (all acts): {'SUB_ORIG': 0, 'KEEP_CLAR': 4, 'KEEP_SUBJ': 1}; F3 history-B arrivals: {'SUB_ORIG': 0, 'KEEP_CLAR': 4, 'KEEP_SUBJ': 1}. State-only arrivals: {'SUB_ORIG': 109, 'KEEP_CLAR': 31, 'KEEP_SUBJ': 32}.
New outcome classes in KEEP_SUBJ (absent in KEEP_CLAR): {'arrival': {'rejected (parse)': 2}, 'correction': {}}.

## F3 history B arrivals

| Arm | Exact | Wrong binding | State-only |
|---|---:|---:|---:|
| SUB_ORIG | 59/96 | 0 | 36 |
| KEEP_CLAR | 85/96 | 4 | 6 |
| KEEP_SUBJ | 87/96 | 1 | 8 |

## Guarded replay (IGUARD-v0.1 decision function, unchanged)

| Arm / act | Exact → usable exact | Wrong binding before → after | Exact blocked | Guard dispositions |
|---|---:|---:|---:|---|
| SUB_ORIG arrival | 178 → 178 | 0 → 0 | 0 | {'pass': 287, 'compile_rejected': 1} |
| SUB_ORIG correction | 191 → 191 | 0 → 0 | 0 | {'pass': 191, 'compile_rejected': 1} |
| KEEP_CLAR arrival | 251 → 251 | 4 → 0 | 0 | {'pass': 282, 'identity_mismatch': 4, 'compile_rejected': 2} |
| KEEP_CLAR correction | 192 → 192 | 0 → 0 | 0 | {'pass': 192} |
| KEEP_SUBJ arrival | 250 → 250 | 1 → 0 | 0 | {'pass': 282, 'compile_rejected': 5, 'identity_mismatch': 1} |
| KEEP_SUBJ correction | 192 → 192 | 0 → 0 | 0 | {'pass': 192} |

Accepted wrong bindings (all listed):

- `e25-g0023|arrival|na|B|KEEP_CLAR` bits 010 delayed: guard identity_mismatch (['Dudokeho.on_hand'] vs Dehacedo.on_hand)
- `e25-g0035|arrival|na|B|KEEP_CLAR` bits 010 delayed: guard identity_mismatch (['Dihucufo.on_hand'] vs Cecihide.on_hand)
- `e25-g0057|arrival|na|B|KEEP_CLAR` bits 000 delayed: guard identity_mismatch (['Bidoduhu.on_hand'] vs Fojacode.on_hand)
- `e25-g0091|arrival|na|B|KEEP_SUBJ` bits 010 immediate: guard identity_mismatch (['Dujekuca.on_hand'] vs Dokojicu.on_hand)
- `e25-g0131|arrival|na|B|KEEP_CLAR` bits 010 delayed: guard identity_mismatch (['Kucakube.on_hand'] vs Fibucado.on_hand)

## Cost

- SUB_ORIG: mean 11.7 s/call, max input 1469 tokens, mean output 135 tokens
- KEEP_CLAR: mean 12.8 s/call, max input 1536 tokens, mean output 148 tokens
- KEEP_SUBJ: mean 13.1 s/call, max input 1563 tokens, mean output 152 tokens

## Scope

- Development screen on fresh generated worlds of the declared families, one model and fixed decoding.
- About 3–4 KEEP_CLAR F3 history-B wrong bindings were expected from earlier panels; a small difference in this count cannot distinguish a real change from chance. Regressions are what this panel can expose.
- Rejected answers remain wrong. The guard and the prompt address different things; neither targets state-only arrivals.
- No qualification, transfer, rare-error elimination or safety claim. The protocol stops after reporting.

Full data: `analysis/dev/ANALYSIS.json`, per-call `analysis/dev/scored.jsonl`.
