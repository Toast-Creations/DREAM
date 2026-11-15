# EVTT-v1 development screen: combined event + state-time sentence (KEEP_EVTT)

**Status: COMPLETE. Reading: WARRANTS_CONFIRMATION_DESIGN.** development screen.

Qwen3-32B NF4, greedy, thinking off. Fresh generated worlds (assembly domain). RESULT and TRANSITION arrival wordings balanced in every family x reception stratum.

## Side by side

| Arm / act | Exact | Usable exact (guard) | State-only | Wrong binding (before → after guard) | Exact blocked | Rejected | Truncated | With revision objects | With event objects |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| KEEP_CLAR arrival | 438/480 | 438/480 | 32 | 7 → 0 | 0 | 3 | 0 | 1 | 448 |
| KEEP_CLAR correction | 60/60 | 60/60 | 0 | 0 → 0 | 0 | 0 | 0 | 60 | 0 |
| KEEP_EVT arrival | 466/480 | 466/480 | 0 | 7 → 0 | 0 | 7 | 0 | 0 | 480 |
| KEEP_EVT correction | 59/60 | 59/60 | 0 | 0 → 0 | 0 | 1 | 1 | 59 | 0 |
| KEEP_EVTT arrival | 475/480 | 475/480 | 0 | 5 → 0 | 0 | 0 | 0 | 0 | 480 |
| KEEP_EVTT correction | 60/60 | 60/60 | 0 | 0 → 0 | 0 | 0 | 0 | 60 | 0 |

Object-presence counts come from normalized parsed raw claims, including compiler-rejected replies; replies that fail parsing/normalization are excluded from them.

## Arrivals by wording

| Arm | Wording | Exact | Usable exact | State-only | Wrong binding | Rejected |
|---|---|---:|---:|---:|---:|---:|
| KEEP_CLAR | RESULT | 204/240 | 204/240 | 32 | 1 | 3 |
| KEEP_CLAR | TRANSITION | 234/240 | 234/240 | 0 | 6 | 0 |
| KEEP_EVT | RESULT | 233/240 | 233/240 | 0 | 0 | 7 |
| KEEP_EVT | TRANSITION | 233/240 | 233/240 | 0 | 7 | 0 |
| KEEP_EVTT | RESULT | 239/240 | 239/240 | 0 | 1 | 0 |
| KEEP_EVTT | TRANSITION | 236/240 | 236/240 | 0 | 4 | 0 |

## Arrivals by wording x reception (declared)

| Arm | Wording | Reception | Exact | State-only | Reception-dated | Wrong binding | Rejected |
|---|---|---|---:|---:|---:|---:|---:|
| KEEP_CLAR | RESULT | immediate | 43/64 | 21 | 0 | 0 | 0 |
| KEEP_CLAR | RESULT | delayed | 161/176 | 11 | 2 | 1 | 3 |
| KEEP_CLAR | TRANSITION | immediate | 64/64 | 0 | 0 | 0 | 0 |
| KEEP_CLAR | TRANSITION | delayed | 170/176 | 0 | 0 | 6 | 0 |
| KEEP_EVT | RESULT | immediate | 64/64 | 0 | 0 | 0 | 0 |
| KEEP_EVT | RESULT | delayed | 169/176 | 0 | 7 | 0 | 7 |
| KEEP_EVT | TRANSITION | immediate | 64/64 | 0 | 0 | 0 | 0 |
| KEEP_EVT | TRANSITION | delayed | 169/176 | 0 | 0 | 7 | 0 |
| KEEP_EVTT | RESULT | immediate | 64/64 | 0 | 0 | 0 | 0 |
| KEEP_EVTT | RESULT | delayed | 175/176 | 0 | 0 | 1 | 0 |
| KEEP_EVTT | TRANSITION | immediate | 64/64 | 0 | 0 | 0 | 0 |
| KEEP_EVTT | TRANSITION | delayed | 172/176 | 0 | 0 | 4 | 0 |

Reception-dated replies (all arrivals): {'KEEP_CLAR': 2, 'KEEP_EVT': 7, 'KEEP_EVTT': 0}. By cell: {'KEEP_CLAR\|F3': 2, 'KEEP_CLAR\|history B': 2, 'KEEP_EVT\|F1': 1, 'KEEP_EVT\|F3': 6, 'KEEP_EVT\|history A': 1, 'KEEP_EVT\|history B': 6}.

Stems with any reception-dated reply, discordant between arms (descriptive):

- KEEP_EVTT-KEEP_EVT: {'only_KEEP_EVTT': 0, 'only_KEEP_EVT': 7, 'both': 0, 'sign_test_two_sided_p': 0.015625}
- KEEP_EVT-KEEP_CLAR: {'only_KEEP_EVT': 7, 'only_KEEP_CLAR': 2, 'both': 0, 'sign_test_two_sided_p': 0.1796875}
- KEEP_EVTT-KEEP_CLAR: {'only_KEEP_EVTT': 0, 'only_KEEP_CLAR': 2, 'both': 0, 'sign_test_two_sided_p': 0.5}

## Paired stem differences

| Contrast | Stems | Difference (points) | Bootstrap 95% (points) | Target rescues / breaks |
|---|---:|---:|---:|---:|
| arrival\|KEEP_EVTT-KEEP_EVT | 240 | +1.88 | [+0.62, +3.33] | 10 / 1 |
| correction\|KEEP_EVTT-KEEP_EVT | 15 | +1.67 | [+0.00, +5.00] | 1 / 0 |
| arrival\|RESULT\|KEEP_EVTT-KEEP_EVT | 120 | +2.50 | [+0.42, +4.58] | 7 / 1 |
| arrival\|TRANSITION\|KEEP_EVTT-KEEP_EVT | 120 | +1.25 | [+0.00, +2.92] | 3 / 0 |
| arrival\|RESULT\|immediate\|KEEP_EVTT-KEEP_EVT | 32 | +0.00 | [+0.00, +0.00] | 0 / 0 |
| arrival\|RESULT\|delayed\|KEEP_EVTT-KEEP_EVT | 88 | +3.41 | [+0.57, +6.82] | 7 / 1 |
| arrival\|TRANSITION\|immediate\|KEEP_EVTT-KEEP_EVT | 32 | +0.00 | [+0.00, +0.00] | 0 / 0 |
| arrival\|TRANSITION\|delayed\|KEEP_EVTT-KEEP_EVT | 88 | +1.70 | [+0.00, +3.98] | 3 / 0 |
| arrival\|usable_exact\|KEEP_EVTT-KEEP_EVT | 240 | +1.88 | [+0.62, +3.33] | 10 / 1 |
| correction\|usable_exact\|KEEP_EVTT-KEEP_EVT | 15 | +1.67 | [+0.00, +5.00] | 1 / 0 |
| arrival\|RESULT\|usable_exact\|KEEP_EVTT-KEEP_EVT | 120 | +2.50 | [+0.42, +4.58] | 7 / 1 |
| arrival\|TRANSITION\|usable_exact\|KEEP_EVTT-KEEP_EVT | 120 | +1.25 | [+0.00, +2.92] | 3 / 0 |
| arrival\|RESULT\|immediate\|usable_exact\|KEEP_EVTT-KEEP_EVT | 32 | +0.00 | [+0.00, +0.00] | 0 / 0 |
| arrival\|RESULT\|delayed\|usable_exact\|KEEP_EVTT-KEEP_EVT | 88 | +3.41 | [+0.57, +6.82] | 7 / 1 |
| arrival\|TRANSITION\|immediate\|usable_exact\|KEEP_EVTT-KEEP_EVT | 32 | +0.00 | [+0.00, +0.00] | 0 / 0 |
| arrival\|TRANSITION\|delayed\|usable_exact\|KEEP_EVTT-KEEP_EVT | 88 | +1.70 | [+0.00, +3.98] | 3 / 0 |
| arrival\|KEEP_EVT-KEEP_CLAR | 240 | +5.83 | [+2.92, +8.75] | 36 / 8 |
| correction\|KEEP_EVT-KEEP_CLAR | 15 | -1.67 | [-5.00, +0.00] | 0 / 1 |
| arrival\|RESULT\|KEEP_EVT-KEEP_CLAR | 120 | +12.08 | [+7.92, +16.67] | 34 / 5 |
| arrival\|TRANSITION\|KEEP_EVT-KEEP_CLAR | 120 | -0.42 | [-2.08, +1.25] | 2 / 3 |
| arrival\|RESULT\|immediate\|KEEP_EVT-KEEP_CLAR | 32 | +32.81 | [+25.00, +42.19] | 21 / 0 |
| arrival\|RESULT\|delayed\|KEEP_EVT-KEEP_CLAR | 88 | +4.55 | [-0.57, +9.66] | 13 / 5 |
| arrival\|TRANSITION\|immediate\|KEEP_EVT-KEEP_CLAR | 32 | +0.00 | [+0.00, +0.00] | 0 / 0 |
| arrival\|TRANSITION\|delayed\|KEEP_EVT-KEEP_CLAR | 88 | -0.57 | [-2.84, +1.70] | 2 / 3 |
| arrival\|usable_exact\|KEEP_EVT-KEEP_CLAR | 240 | +5.83 | [+2.92, +8.75] | 36 / 8 |
| correction\|usable_exact\|KEEP_EVT-KEEP_CLAR | 15 | -1.67 | [-5.00, +0.00] | 0 / 1 |
| arrival\|RESULT\|usable_exact\|KEEP_EVT-KEEP_CLAR | 120 | +12.08 | [+7.92, +16.67] | 34 / 5 |
| arrival\|TRANSITION\|usable_exact\|KEEP_EVT-KEEP_CLAR | 120 | -0.42 | [-2.08, +1.25] | 2 / 3 |
| arrival\|RESULT\|immediate\|usable_exact\|KEEP_EVT-KEEP_CLAR | 32 | +32.81 | [+25.00, +42.19] | 21 / 0 |
| arrival\|RESULT\|delayed\|usable_exact\|KEEP_EVT-KEEP_CLAR | 88 | +4.55 | [-0.57, +9.66] | 13 / 5 |
| arrival\|TRANSITION\|immediate\|usable_exact\|KEEP_EVT-KEEP_CLAR | 32 | +0.00 | [+0.00, +0.00] | 0 / 0 |
| arrival\|TRANSITION\|delayed\|usable_exact\|KEEP_EVT-KEEP_CLAR | 88 | -0.57 | [-2.84, +1.70] | 2 / 3 |
| arrival\|KEEP_EVTT-KEEP_CLAR | 240 | +7.71 | [+5.00, +10.62] | 38 / 1 |
| correction\|KEEP_EVTT-KEEP_CLAR | 15 | +0.00 | [+0.00, +0.00] | 0 / 0 |
| arrival\|RESULT\|KEEP_EVTT-KEEP_CLAR | 120 | +14.58 | [+10.83, +18.75] | 35 / 0 |
| arrival\|TRANSITION\|KEEP_EVTT-KEEP_CLAR | 120 | +0.83 | [-0.83, +2.50] | 3 / 1 |
| arrival\|RESULT\|immediate\|KEEP_EVTT-KEEP_CLAR | 32 | +32.81 | [+25.00, +42.19] | 21 / 0 |
| arrival\|RESULT\|delayed\|KEEP_EVTT-KEEP_CLAR | 88 | +7.95 | [+3.98, +12.50] | 14 / 0 |
| arrival\|TRANSITION\|immediate\|KEEP_EVTT-KEEP_CLAR | 32 | +0.00 | [+0.00, +0.00] | 0 / 0 |
| arrival\|TRANSITION\|delayed\|KEEP_EVTT-KEEP_CLAR | 88 | +1.14 | [-1.14, +3.41] | 3 / 1 |
| arrival\|usable_exact\|KEEP_EVTT-KEEP_CLAR | 240 | +7.71 | [+5.00, +10.62] | 38 / 1 |
| correction\|usable_exact\|KEEP_EVTT-KEEP_CLAR | 15 | +0.00 | [+0.00, +0.00] | 0 / 0 |
| arrival\|RESULT\|usable_exact\|KEEP_EVTT-KEEP_CLAR | 120 | +14.58 | [+10.83, +18.75] | 35 / 0 |
| arrival\|TRANSITION\|usable_exact\|KEEP_EVTT-KEEP_CLAR | 120 | +0.83 | [-0.83, +2.50] | 3 / 1 |
| arrival\|RESULT\|immediate\|usable_exact\|KEEP_EVTT-KEEP_CLAR | 32 | +32.81 | [+25.00, +42.19] | 21 / 0 |
| arrival\|RESULT\|delayed\|usable_exact\|KEEP_EVTT-KEEP_CLAR | 88 | +7.95 | [+3.98, +12.50] | 14 / 0 |
| arrival\|TRANSITION\|immediate\|usable_exact\|KEEP_EVTT-KEEP_CLAR | 32 | +0.00 | [+0.00, +0.00] | 0 / 0 |
| arrival\|TRANSITION\|delayed\|usable_exact\|KEEP_EVTT-KEEP_CLAR | 88 | +1.14 | [-1.14, +3.41] | 3 / 1 |

Bootstrap use: descriptive 95% percentile interval only; never a gate.

## Reading (frozen before output)

| Criterion | Rule | Result |
|---|---|---|
| reception_dated_halved_with_keep_evt_at_least_6 | RECEPTION_DATED arrivals KEEP_EVTT <= floor(KEEP_EVT / 2) and KEEP_EVT >= 6 | pass |
| arrival_exact_not_lower | arrival exact KEEP_EVTT-KEEP_EVT >= 0 points | pass |
| state_only_within_2 | accepted state-only arrivals KEEP_EVTT <= KEEP_EVT + 2 | pass |
| immediate_result_exact_not_lower_than_3_points | immediate-reception RESULT-wording arrival exact KEEP_EVTT-KEEP_EVT >= -3 points | pass |
| transition_exact_not_lower_than_3_points | TRANSITION-wording arrival exact KEEP_EVTT-KEEP_EVT >= -3 points | pass |
| wrong_bindings_within_4 | pre-guard accepted wrong bindings KEEP_EVTT <= KEEP_EVT + 4 | pass |
| correction_exact_not_lower_than_3_64 | correction exact KEEP_EVTT-KEEP_EVT >= -3/64 | pass |

New outcome classes or sub-patterns under the candidate: none.

Target-error floor (KEEP_EVT reception-dated >= 6): met ({'KEEP_CLAR': 2, 'KEEP_EVT': 7, 'KEEP_EVTT': 0}). Precedence: any of criteria 2-7 fails -> DOES_NOT_WARRANT; else KEEP_EVT RECEPTION_DATED < 6 -> INSUFFICIENT_TARGET_ERRORS; else KEEP_EVTT > floor(KEEP_EVT / 2) -> DOES_NOT_WARRANT; else outcome classes or non-exact sub-patterns present under KEEP_EVTT but absent under KEEP_EVT (per act) -> REVIEW_NEW_FAILURE_TYPES; else WARRANTS_CONFIRMATION_DESIGN (justifies a confirmation design, not adoption); a pipeline-invariant violation overrides all of these (INCOMPLETE).

**Interpretation fixed before output:** Criteria 2-7 are point-estimate screens, not equivalence or non-inferiority tests; passing them is not evidence of no cost. The panel is weighted toward delayed F3 arrivals, so overall arrival exactness is not comparable in composition with runs A-C. KEEP_EVTT-KEEP_EVT isolates the appended time clause given KEEP_EVT's scope; it says nothing about the clause in other scopes. A reception-dated reply count under KEEP_EVT below 6 makes the target-error criterion uninformative (INSUFFICIENT_TARGET_ERRORS), unless another criterion already fails. KEEP_CLAR enters no criterion.

**Guard invariants:** These panels retain only targets on which the public identity resolver agrees with the construction's gold identity. With the pinned scorer and guard, zero post-guard accepted wrong bindings and zero exact answers blocked are expected structural invariants on retained targets. The guarded replay checks this pipeline behavior; it does not independently test resolver correctness, unsupported identities or guard safety. Violation in this run: none.

State-only arrivals: {'KEEP_CLAR': 32, 'KEEP_EVT': 0, 'KEEP_EVTT': 0}. Accepted wrong bindings: {'KEEP_CLAR': 7, 'KEEP_EVT': 7, 'KEEP_EVTT': 5}; after guard: {'KEEP_CLAR': 0, 'KEEP_EVT': 0, 'KEEP_EVTT': 0}; exact blocked: {'KEEP_CLAR': 0, 'KEEP_EVT': 0, 'KEEP_EVTT': 0}.

## Non-exact sub-patterns (descriptive)

| Arm / act | Sub-patterns |
|---|---|
| KEEP_CLAR arrival | {'accepted state-only': 32, 'accepted wrong binding': 7, 'arrival with spurious revisions': 1, 'arrival with correct event and result state dated at the true receipt time': 2} |
| KEEP_CLAR correction | none |
| KEEP_EVT arrival | {'arrival with correct event and result state dated at the true receipt time': 7, 'accepted wrong binding': 7} |
| KEEP_EVT correction | {'unparsed (truncated)': 1} |
| KEEP_EVTT arrival | {'accepted wrong binding': 5} |
| KEEP_EVTT correction | none |

Accepted wrong bindings (all listed):

- `v29d-g0027|arrival|na|B|KEEP_CLAR` TRANSITION bits 010 delayed: guard identity_mismatch (['Judebija.on_hand'] vs Dubakuha.on_hand)
- `v29d-g0027|arrival|na|B|KEEP_EVT` TRANSITION bits 010 delayed: guard identity_mismatch (['Judebija.on_hand'] vs Dubakuha.on_hand)
- `v29d-g0027|arrival|na|B|KEEP_EVTT` TRANSITION bits 010 delayed: guard identity_mismatch (['Judebija.on_hand'] vs Dubakuha.on_hand)
- `v29d-g0041|arrival|na|B|KEEP_CLAR` TRANSITION bits 010 delayed: guard identity_mismatch (['Johifacu.on_hand'] vs Dikehudo.on_hand)
- `v29d-g0041|arrival|na|B|KEEP_EVT` TRANSITION bits 010 delayed: guard identity_mismatch (['Johifacu.on_hand'] vs Dikehudo.on_hand)
- `v29d-g0041|arrival|na|B|KEEP_EVTT` TRANSITION bits 010 delayed: guard identity_mismatch (['Johifacu.on_hand'] vs Dikehudo.on_hand)
- `v29d-g0059|arrival|na|B|KEEP_CLAR` TRANSITION bits 010 delayed: guard identity_mismatch (['Cudedibo.on_hand'] vs Fudakefi.on_hand)
- `v29d-g0101|arrival|na|B|KEEP_CLAR` TRANSITION bits 010 delayed: guard identity_mismatch (['Dobabodu.on_hand'] vs Bekicehu.on_hand)
- `v29d-g0101|arrival|na|B|KEEP_EVT` TRANSITION bits 010 delayed: guard identity_mismatch (['Dobabodu.on_hand'] vs Bekicehu.on_hand)
- `v29d-g0157|arrival|na|B|KEEP_CLAR` TRANSITION bits 010 delayed: guard identity_mismatch (['Kuhujuda.on_hand'] vs Hakefido.on_hand)
- `v29d-g0157|arrival|na|B|KEEP_EVT` TRANSITION bits 010 delayed: guard identity_mismatch (['Kuhujuda.on_hand'] vs Hakefido.on_hand)
- `v29d-g0157|arrival|na|B|KEEP_EVTT` TRANSITION bits 010 delayed: guard identity_mismatch (['Kuhujuda.on_hand'] vs Hakefido.on_hand)
- `v29d-g0179|arrival|na|B|KEEP_CLAR` TRANSITION bits 010 delayed: guard identity_mismatch (['Docedeba.on_hand'] vs Hebikubu.on_hand)
- `v29d-g0205|arrival|na|B|KEEP_CLAR` RESULT bits 000 delayed: guard identity_mismatch (['Docudufo.on_hand'] vs Cadubafo.on_hand)
- `v29d-g0205|arrival|na|B|KEEP_EVTT` RESULT bits 000 delayed: guard identity_mismatch (['Docudufo.on_hand'] vs Cadubafo.on_hand)
- `v29d-g0221|arrival|na|B|KEEP_EVT` TRANSITION bits 010 delayed: guard identity_mismatch (['Jodokide.on_hand'] vs Duducufi.on_hand)
- `v29d-g0236|arrival|na|B|KEEP_EVT` TRANSITION bits 110 delayed: guard identity_mismatch (['Bebajiko.on_hand'] vs Cafobefe.on_hand)
- `v29d-g0239|arrival|na|B|KEEP_EVT` TRANSITION bits 010 delayed: guard identity_mismatch (['Bejakoko.on_hand'] vs Dojufudu.on_hand)
- `v29d-g0239|arrival|na|B|KEEP_EVTT` TRANSITION bits 010 delayed: guard identity_mismatch (['Bejakoko.on_hand'] vs Dojufudu.on_hand)

Truncated replies: ['v29d-g0008|correction|yes_to_no|A|KEEP_EVT']. Exact answers blocked by the guard: none.

## Cost

- KEEP_CLAR: mean 12.4 s/call, max input 1539 tokens, mean output 140 tokens (max 248)
- KEEP_EVT: mean 13.4 s/call, max input 1579 tokens, mean output 152 tokens (max 256)
- KEEP_EVTT: mean 14.0 s/call, max input 1603 tokens, mean output 159 tokens (max 191)

## Scope

- One fresh panel of generated worlds of the declared families (assembly domain only), one model, fixed decoding.
- Passing a threshold on a point estimate is not equivalence or non-inferiority.
- Rejected answers remain wrong; the guard turns detected identity mismatches into rejections. It does not address event omission.
- No qualification, transfer, rare-error elimination or safety claim. The protocol stops after reporting.

Full data: `analysis/dev/ANALYSIS.json`, per-call `analysis/dev/scored.jsonl`.
