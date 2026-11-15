# EVTB-v1 descriptive wrong-binding panel (history-B arrivals)

**Status: COMPLETE. Reading: DESCRIPTIVE_COMPLETE.** descriptive wrong-binding panel; no gate.

Qwen3-32B NF4, greedy, thinking off. Fresh generated worlds (assembly domain). RESULT and TRANSITION arrival wordings balanced in every family x reception stratum.

## Side by side

| Arm / act | Exact | Usable exact (guard) | State-only | Wrong binding (before → after guard) | Exact blocked | Rejected | Truncated | With revision objects | With event objects |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| KEEP_CLAR arrival | 365/384 | 365/384 | 15 | 3 → 0 | 0 | 1 | 0 | 0 | 369 |
| KEEP_EVT arrival | 371/384 | 371/384 | 0 | 8 → 0 | 0 | 5 | 0 | 0 | 384 |
| KEEP_EVTR arrival | 358/384 | 358/384 | 23 | 3 → 0 | 0 | 0 | 0 | 0 | 361 |

Object-presence counts come from normalized parsed raw claims, including compiler-rejected replies; replies that fail parsing/normalization are excluded from them.

## Arrivals by wording

| Arm | Wording | Exact | Usable exact | State-only | Wrong binding | Rejected |
|---|---|---:|---:|---:|---:|---:|
| KEEP_CLAR | RESULT | 177/192 | 177/192 | 14 | 0 | 1 |
| KEEP_CLAR | TRANSITION | 188/192 | 188/192 | 1 | 3 | 0 |
| KEEP_EVT | RESULT | 187/192 | 187/192 | 0 | 0 | 5 |
| KEEP_EVT | TRANSITION | 184/192 | 184/192 | 0 | 8 | 0 |
| KEEP_EVTR | RESULT | 169/192 | 169/192 | 23 | 0 | 0 |
| KEEP_EVTR | TRANSITION | 189/192 | 189/192 | 0 | 3 | 0 |

## Paired stem differences

| Contrast | Stems | Difference (points) | Bootstrap 95% (points) | Target rescues / breaks |
|---|---:|---:|---:|---:|
| arrival\|KEEP_EVT-KEEP_CLAR | 384 | +1.56 | [-1.04, +4.17] | 16 / 10 |
| arrival\|RESULT\|KEEP_EVT-KEEP_CLAR | 192 | +5.21 | [+1.04, +9.38] | 14 / 4 |
| arrival\|TRANSITION\|KEEP_EVT-KEEP_CLAR | 192 | -2.08 | [-5.21, +0.52] | 2 / 6 |
| arrival\|usable_exact\|KEEP_EVT-KEEP_CLAR | 384 | +1.56 | [-1.04, +4.17] | 16 / 10 |
| arrival\|RESULT\|usable_exact\|KEEP_EVT-KEEP_CLAR | 192 | +5.21 | [+1.04, +9.38] | 14 / 4 |
| arrival\|TRANSITION\|usable_exact\|KEEP_EVT-KEEP_CLAR | 192 | -2.08 | [-5.21, +0.52] | 2 / 6 |
| arrival\|KEEP_EVTR-KEEP_CLAR | 384 | -1.82 | [-4.17, +0.52] | 8 / 15 |
| arrival\|RESULT\|KEEP_EVTR-KEEP_CLAR | 192 | -4.17 | [-8.85, +0.00] | 6 / 14 |
| arrival\|TRANSITION\|KEEP_EVTR-KEEP_CLAR | 192 | +0.52 | [-1.04, +2.60] | 2 / 1 |
| arrival\|usable_exact\|KEEP_EVTR-KEEP_CLAR | 384 | -1.82 | [-4.17, +0.52] | 8 / 15 |
| arrival\|RESULT\|usable_exact\|KEEP_EVTR-KEEP_CLAR | 192 | -4.17 | [-8.85, +0.00] | 6 / 14 |
| arrival\|TRANSITION\|usable_exact\|KEEP_EVTR-KEEP_CLAR | 192 | +0.52 | [-1.04, +2.60] | 2 / 1 |
| arrival\|KEEP_EVTR-KEEP_EVT | 384 | -3.39 | [-6.25, -0.52] | 11 / 24 |
| arrival\|RESULT\|KEEP_EVTR-KEEP_EVT | 192 | -9.38 | [-14.06, -4.69] | 5 / 23 |
| arrival\|TRANSITION\|KEEP_EVTR-KEEP_EVT | 192 | +2.60 | [+0.00, +5.21] | 6 / 1 |
| arrival\|usable_exact\|KEEP_EVTR-KEEP_EVT | 384 | -3.39 | [-6.25, -0.52] | 11 / 24 |
| arrival\|RESULT\|usable_exact\|KEEP_EVTR-KEEP_EVT | 192 | -9.38 | [-14.06, -4.69] | 5 / 23 |
| arrival\|TRANSITION\|usable_exact\|KEEP_EVTR-KEEP_EVT | 192 | +2.60 | [+0.00, +5.21] | 6 / 1 |

Bootstrap use: descriptive 95% percentile interval only; never a gate.

## Reading (frozen before output)

| Arm | Wrong bindings | Rate | Clopper-Pearson 95% | After guard | Exact blocked |
|---|---:|---:|---:|---:|---:|
| KEEP_CLAR | 3/384 | 0.78% | [0.16%, 2.27%] | 0 | 0 |
| KEEP_EVT | 8/384 | 2.08% | [0.90%, 4.06%] | 0 | 0 |
| KEEP_EVTR | 3/384 | 0.78% | [0.16%, 2.27%] | 0 | 0 |

Pairwise discordant wrong-binding stems (pre-declared, descriptive):

- KEEP_EVT-KEEP_CLAR: {'only_KEEP_EVT': 6, 'only_KEEP_CLAR': 1, 'both': 2, 'sign_test_two_sided_p': 0.125}
- KEEP_EVTR-KEEP_CLAR: {'only_KEEP_EVTR': 1, 'only_KEEP_CLAR': 1, 'both': 2, 'sign_test_two_sided_p': 1.0}
- KEEP_EVTR-KEEP_EVT: {'only_KEEP_EVTR': 1, 'only_KEEP_EVT': 6, 'both': 2, 'sign_test_two_sided_p': 0.125}

Wrong-binding rates by subgroup (nominal descriptive 95% intervals; no simultaneous coverage):

| Subgroup | n | Wrong bindings [95%] | After guard [95%] |
|---|---:|---:|---:|
| KEEP_CLAR\|RESULT | 192 | 0 [0.00%, 1.90%] | 0 [0.00%, 1.90%] |
| KEEP_CLAR\|TRANSITION | 192 | 3 [0.32%, 4.50%] | 0 [0.00%, 1.90%] |
| KEEP_EVTR\|RESULT | 192 | 0 [0.00%, 1.90%] | 0 [0.00%, 1.90%] |
| KEEP_EVTR\|TRANSITION | 192 | 3 [0.32%, 4.50%] | 0 [0.00%, 1.90%] |
| KEEP_EVT\|RESULT | 192 | 0 [0.00%, 1.90%] | 0 [0.00%, 1.90%] |
| KEEP_EVT\|TRANSITION | 192 | 8 [1.82%, 8.04%] | 0 [0.00%, 1.90%] |
| KEEP_CLAR\|F2 | 96 | 0 [0.00%, 3.77%] | 0 [0.00%, 3.77%] |
| KEEP_CLAR\|F3 | 288 | 3 [0.22%, 3.01%] | 0 [0.00%, 1.27%] |
| KEEP_EVTR\|F2 | 96 | 0 [0.00%, 3.77%] | 0 [0.00%, 3.77%] |
| KEEP_EVTR\|F3 | 288 | 3 [0.22%, 3.01%] | 0 [0.00%, 1.27%] |
| KEEP_EVT\|F2 | 96 | 0 [0.00%, 3.77%] | 0 [0.00%, 3.77%] |
| KEEP_EVT\|F3 | 288 | 8 [1.21%, 5.40%] | 0 [0.00%, 1.27%] |

**Guard invariants:** These panels retain only targets on which the public identity resolver agrees with the construction's gold identity. With the pinned scorer and guard, zero post-guard accepted wrong bindings and zero exact answers blocked are expected structural invariants on retained targets. The guarded replay checks this pipeline behavior; it does not independently test resolver correctness, unsupported identities or guard safety. Violation in this run: none.

State-only arrivals: {'KEEP_CLAR': 15, 'KEEP_EVT': 0, 'KEEP_EVTR': 23}. Accepted wrong bindings: {'KEEP_CLAR': 3, 'KEEP_EVT': 8, 'KEEP_EVTR': 3}; after guard: {'KEEP_CLAR': 0, 'KEEP_EVT': 0, 'KEEP_EVTR': 0}; exact blocked: {'KEEP_CLAR': 0, 'KEEP_EVT': 0, 'KEEP_EVTR': 0}.

## Non-exact sub-patterns (descriptive)

| Arm / act | Sub-patterns |
|---|---|
| KEEP_CLAR arrival | {'arrival with correct event and result state dated at the true receipt time': 1, 'accepted state-only': 15, 'accepted wrong binding': 3} |
| KEEP_EVT arrival | {'arrival with correct event and result state dated at the true receipt time': 5, 'accepted wrong binding': 8} |
| KEEP_EVTR arrival | {'accepted state-only': 23, 'accepted wrong binding': 3} |

Accepted wrong bindings (all listed):

- `v27c-g0019|arrival|na|B|KEEP_EVT` TRANSITION bits 010 immediate: guard identity_mismatch (['Bafodahi.on_hand'] vs Cejubede.on_hand)
- `v27c-g0064|arrival|na|B|KEEP_EVTR` TRANSITION bits 110 delayed: guard identity_mismatch (['Bidubohu.on_hand'] vs Facibicu.on_hand)
- `v27c-g0069|arrival|na|B|KEEP_EVT` TRANSITION bits 010 immediate: guard identity_mismatch (['Kacidabi.on_hand'] vs Jaduhiki.on_hand)
- `v27c-g0191|arrival|na|B|KEEP_CLAR` TRANSITION bits 010 delayed: guard identity_mismatch (['Jujajice.on_hand'] vs Decicebe.on_hand)
- `v27c-g0191|arrival|na|B|KEEP_EVT` TRANSITION bits 010 delayed: guard identity_mismatch (['Jujajice.on_hand'] vs Decicebe.on_hand)
- `v27c-g0191|arrival|na|B|KEEP_EVTR` TRANSITION bits 010 delayed: guard identity_mismatch (['Jujajice.on_hand'] vs Decicebe.on_hand)
- `v27c-g0214|arrival|na|B|KEEP_EVT` TRANSITION bits 010 delayed: guard identity_mismatch (['Bojohoji.on_hand'] vs Cicicica.on_hand)
- `v27c-g0246|arrival|na|B|KEEP_EVT` TRANSITION bits 010 delayed: guard identity_mismatch (['Dehociku.on_hand'] vs Jajehiko.on_hand)
- `v27c-g0261|arrival|na|B|KEEP_CLAR` TRANSITION bits 010 immediate: guard identity_mismatch (['Bocekihu.on_hand'] vs Kahikobe.on_hand)
- `v27c-g0261|arrival|na|B|KEEP_EVT` TRANSITION bits 010 immediate: guard identity_mismatch (['Bocekihu.on_hand'] vs Kahikobe.on_hand)
- `v27c-g0261|arrival|na|B|KEEP_EVTR` TRANSITION bits 010 immediate: guard identity_mismatch (['Bocekihu.on_hand'] vs Kahikobe.on_hand)
- `v27c-g0320|arrival|na|B|KEEP_EVT` TRANSITION bits 110 delayed: guard identity_mismatch (['Badokijo.on_hand'] vs Cofodifi.on_hand)
- `v27c-g0342|arrival|na|B|KEEP_EVT` TRANSITION bits 010 delayed: guard identity_mismatch (['Cacoboci.on_hand'] vs Kefadace.on_hand)
- `v27c-g0374|arrival|na|B|KEEP_CLAR` TRANSITION bits 010 delayed: guard identity_mismatch (['Dikibudi.on_hand'] vs Cufihaku.on_hand)

Truncated replies: none. Exact answers blocked by the guard: none.

## Cost

- KEEP_CLAR: mean 12.1 s/call, max input 1511 tokens, mean output 139 tokens (max 165)
- KEEP_EVT: mean 13.1 s/call, max input 1551 tokens, mean output 153 tokens (max 167)
- KEEP_EVTR: mean 13.5 s/call, max input 1561 tokens, mean output 158 tokens (max 167)

## Scope

- One fresh panel of generated worlds of the declared families (assembly domain only), one model, fixed decoding.
- Passing a threshold on a point estimate is not equivalence or non-inferiority.
- Rejected answers remain wrong; the guard turns detected identity mismatches into rejections. It does not address event omission.
- No qualification, transfer, rare-error elimination or safety claim. The protocol stops after reporting.

Full data: `analysis/dev/ANALYSIS.json`, per-call `analysis/dev/scored.jsonl`.
