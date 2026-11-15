# Exploratory Claude-only ratings (scoped-v5 prompt): results, 2026-11-02

**Status:** EXPLORATORY, single judge (claude-opus-5-5). This is not the pre-registered endpoint; scoped-v5 failed two-family qualification.
- Design: `scope-v5/EXPLORATORY-CLAUDE-ONLY.json`, plus amendment 1 (one fence-less reply kept, no resampling).
- Calls: 1,249 of the 1,400 ceiling, over 5 launches.
- Content issues: 1 (the fence-less reply). Lineage issues: 0.

## Qualifying final ideas
Qualifying means all facets ≥3, the constraint passes, the lineage is faithful or a reinterpretation, and the idea is not a duplicate.

| Set | Strong prompt | T=1.3 | Targeted | Random | Useful new-idea notes |
|---|---:|---:|---:|---:|---:|
| Qwen3 pilot | 0 / 90 | 0 / 89 | 0 / 90 | 0 / 90 | 0 / 12 |
| Mistral pilot | 0 / 84 | 0 / 85 | 0 / 85 | 0 / 85 | 0 / 65 |

Qwen3 developer cohort (no arms): 0 of 57 development-first and 0 of 51 review-first finals qualify; 0 of 18 notes are useful.

**No final idea in any arm, model or cohort qualifies.** The precision check reports "uninformative: floor" for every contrast in both pilots.

## Facet means of the sourced finals (and the count scoring ≥3)
| Arm | Qwen novelty | Qwen value | Qwen coherence | Mistral novelty | Mistral value | Mistral coherence |
|---|---|---|---|---|---|---|
| Strong prompt | 1.28 (0) | 1.82 (7) | 2.00 (11) | 1.08 (0) | 1.52 (3) | 1.85 (6) |
| T=1.3 | 1.28 (0) | 1.67 (5) | 2.00 (11) | 1.15 (0) | 1.48 (1) | 1.81 (2) |
| Targeted | 1.30 (1) | 1.80 (7) | 1.98 (9) | 1.19 (0) | 1.61 (5) | 1.91 (8) |
| Random | 1.28 (0) | 1.84 (5) | 2.06 (11) | 1.22 (0) | 1.59 (4) | 1.94 (10) |

Novelty is the binding facet: across 698 pilot finals from both models, one scores 3 (Qwen, targeted). Developer cohort (108 finals): novelty is mostly 1, value 1–2, coherence mostly 2.

## Lineage (Claude)
| Set | Faithful | Reinterpretation | Unrelated replacement |
|---|---:|---:|---:|
| Qwen developer cohort | 90 | 17 | 1 |
| Qwen pilot | 300 | 58 | 1 |
| Mistral pilot | 258 | 69 | 12 |

## Judge reliability (10% repeat audit, final pool)
| Set | Comparisons | Exact agreement | v5 agreement (same ≥3 decision and ≤1 step) |
|---|---:|---:|---:|
| Developer cohort | 78 | 0.96 | 0.99 |
| Qwen pilot | 198 | 0.90 | 0.98 |
| Mistral pilot | 252 | 0.89 | 0.98 |

## Interpretation limits
- Single judge, exploratory, six tasks per model.
- A floor means the endpoint cannot distinguish the arms. That is not evidence that the arms are equal, and not evidence that steering has no effect on other properties.
- Per the precision rule declared before any v4/v5 rating ("uninformative → stop before the freeze"), the Qwen confirmation is not frozen or run under this endpoint.
