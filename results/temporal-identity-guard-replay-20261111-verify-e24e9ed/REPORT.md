# Identity-guard replay on saved outputs (IGUARD-v0.1)

**Status: COMPLETE / PROTOTYPE READY FOR FURTHER CONSIDERATION.** CPU replay of saved responses only; no model call, prompt variant, live policy change, baseline adoption or qualification. Codex independent verification: **pending**.

## What was checked

A rejection-only wrapper re-derives the stock subject from the original public target and prefix with the unchanged REFRES-v1 deterministic resolver, compiles each saved reply with the unchanged FACT-v1 compiler, and passes a reply only when its compiled assertion fields are exactly the resolved field. Unresolved or unsupported references abstain. Final acceptance = original acceptance AND guard pass. In this hub, decisions were generated from public inputs only and sealed before the evaluator joined hidden gold and saved scores; the evaluator re-verified every row's five input hashes before composing.

## Provenance and earlier decision generation

INPUT-MANIFEST disclosure (verbatim): Retrospective replay of already-completed and already-inspected panels. Before the original IGUARD-v0.1 utility/plan commit (a516c61) and its formal replay, a development smoke of the decision stage alone was run into a scratch directory (disposition counts only: V1.24 pass 2289 / compile_rejected 11 / identity_mismatch 4; V1.22 pass 2160 / compile_rejected 76 / identity_mismatch 4). The evaluator had not been run at that point. The decision rule is the one fixed in NEXT-STEP-PLAN.md and was not changed after that smoke. The original replay hub (commit a516c61, report text regenerated at c3af115) and any later hardening reruns are separate historical records; this manifest belongs only to the hub that contains it.

That decision-only scratch smoke preceded the original formal commit and replay; it is historical and is not part of this hub's outcomes. Earlier IGUARD-v0.1 hubs and commits (including any report-text-only regeneration) remain historical records and are not rewritten by this run. This hub's decisions were generated and sealed at utility commit `e24e9ed4a2722d652cf69551e85dd667a1b002fd` before its evaluator ran.

## Readiness criteria

| Criterion | Kind | Result |
|---|---|---|
| all_stages_succeeded | technical | pass |
| within_cpu_cap | technical | pass |
| frozen_manifests_verified | technical | pass |
| tests_pass | technical | pass |
| controls_pass | technical | pass |
| decisions_sealed_and_deterministic | technical | pass |
| coverage_complete | technical | pass |
| provenance_verified_before_composition | technical | pass |
| preservation_unchanged | technical | pass |
| supported_matching_controls_pass | substantive | pass |
| refusal_controls_abstain | substantive | pass |
| all_seven_known_bindings_blocked | substantive | pass |
| no_previously_exact_output_blocked | substantive | pass |
| acceptance_never_expands | substantive | pass |

These criteria are software acceptance on retrospective, already-inspected fixtures; not a statistical qualification gate, an allowed harm margin, or evidence of general reliability.

## V1.24 (primary retrospective census)

Evaluator status COMPLETE; 2304 responses, 1088 targets, 224 stems. Resolver: {'resolved': 2304}; resolved field equals source gold on 2304/2304 responses. Saved scores re-derived with the pinned scorer: 0 disagreements. Per-row input provenance verified before composition: 2304 rows. Sealed decisions `e5153f2c25702463…`.

SUB_CLAR rows are the scheduled matched references and keep their own denominators.

| Condition / act | Responses (targets; stems) | Orig. accepted | Guard pass | Final accepted | Orig. exact → usable exact | Exact blocked | Newly rejected | Accepted wrong binding before → after | Accepted inexact before → after | Accepted state-only before → after |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| KEEP_CLAR arrival | 448 (448; 224) | 448 | 444 | 444 | 399 → 399 | 0 | 4 | 4 → 0 | 49 → 45 | 45 → 45 |
| KEEP_CLAR correction | 640 (640; 160) | 638 | 638 | 638 | 638 → 638 | 0 | 0 | 0 → 0 | 0 → 0 | 0 → 0 |
| SUB_ORIG arrival | 448 (448; 224) | 447 | 447 | 447 | 280 → 280 | 0 | 0 | 0 → 0 | 167 → 167 | 167 → 167 |
| SUB_ORIG correction | 640 (640; 160) | 632 | 632 | 632 | 632 → 632 | 0 | 0 | 0 → 0 | 0 → 0 | 0 → 0 |
| SUB_CLAR arrival | 64 (64; 32) | 64 | 64 | 64 | 36 → 36 | 0 | 0 | 0 → 0 | 28 → 28 | 28 → 28 |
| SUB_CLAR correction | 64 (64; 16) | 64 | 64 | 64 | 64 → 64 | 0 | 0 | 0 → 0 | 0 → 0 | 0 → 0 |

Joint original acceptance × guard disposition (a mismatch on an already rejected response is not a new rejection):

| Condition / act | accepted\|identity_mismatch | accepted\|pass | rejected\|compile_rejected |
|---|---:|---:|---:|
| KEEP_CLAR arrival | 4 | 444 | 0 |
| KEEP_CLAR correction | 0 | 638 | 2 |
| SUB_ORIG arrival | 0 | 447 | 1 |
| SUB_ORIG correction | 0 | 632 | 8 |
| SUB_CLAR arrival | 0 | 64 | 0 |
| SUB_CLAR correction | 0 | 64 | 0 |

Known accepted wrong bindings (regression fixtures, not independent validation):

| Call | Disposition | Resolved field | Compiled fields | Final accepted | Partners (usable exact) |
|---|---|---|---|---|---|
| `c24-g0045\|arrival\|na\|B\|KEEP_CLAR` | identity_mismatch | `Kecikefu.on_hand` | `['Cudoceci.on_hand']` | False | na\|A\|KEEP_CLAR: exact; na\|A\|SUB_ORIG: exact; na\|B\|SUB_ORIG: exact |
| `c24-g0125\|arrival\|na\|B\|KEEP_CLAR` | identity_mismatch | `Fajijeji.on_hand` | `['Jifojube.on_hand']` | False | na\|A\|KEEP_CLAR: exact; na\|A\|SUB_ORIG: exact; na\|B\|SUB_ORIG: exact |
| `c24-g0143\|arrival\|na\|B\|KEEP_CLAR` | identity_mismatch | `Cedubaho.on_hand` | `['Hujujidu.on_hand']` | False | na\|A\|KEEP_CLAR: exact; na\|A\|SUB_ORIG: exact; na\|B\|SUB_ORIG: exact |
| `c24-g0191\|arrival\|na\|B\|KEEP_CLAR` | identity_mismatch | `Cebodoji.on_hand` | `['Dudukafa.on_hand']` | False | na\|A\|KEEP_CLAR: exact; na\|A\|SUB_ORIG: exact; na\|B\|SUB_ORIG: exact |

No previously exact response was blocked in this study.

KEEP_CLAR inexact state-only arrivals: 45; guard dispositions {'pass, final_accepted=True': 45}. The subject matches, so these remain accepted-but-inexact; a subject check does not address the missing event.

Known KEEP_CLAR correction failures:

- `c24-g0038|correction|yes_to_no|A|KEEP_CLAR`: originally accepted=False (code invalid_assertion); guard compile_rejected; final accepted=False; remains inexact.
- `c24-g0120|correction|yes_to_no|A|KEEP_CLAR`: originally accepted=False (code mixed_acts); guard compile_rejected; final accepted=False; remains inexact.

## V1.22 (separate historical check)

Evaluator status COMPLETE; 2240 responses, 1120 targets, 392 stems. Resolver: {'resolved': 2240}; resolved field equals source gold on 2240/2240 responses. Saved scores re-derived with the pinned scorer: 0 disagreements. Per-row input provenance verified before composition: 2240 rows. Sealed decisions `e075131bcf88fcdb…`.

| Condition / act | Responses (targets; stems) | Orig. accepted | Guard pass | Final accepted | Orig. exact → usable exact | Exact blocked | Newly rejected | Accepted wrong binding before → after | Accepted inexact before → after | Accepted state-only before → after |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| KEEP arrival | 336 (336; 168) | 335 | 332 | 332 | 270 → 270 | 0 | 3 | 3 → 0 | 65 → 62 | 62 → 62 |
| KEEP correction | 784 (784; 392) | 719 | 719 | 719 | 719 → 719 | 0 | 0 | 0 → 0 | 0 → 0 | 0 → 0 |
| SUB arrival | 336 (336; 168) | 336 | 336 | 336 | 205 → 205 | 0 | 0 | 0 → 0 | 131 → 131 | 131 → 131 |
| SUB correction | 784 (784; 392) | 773 | 773 | 773 | 773 → 773 | 0 | 0 | 0 → 0 | 0 → 0 | 0 → 0 |

Joint original acceptance × guard disposition (a mismatch on an already rejected response is not a new rejection):

| Condition / act | accepted\|identity_mismatch | accepted\|pass | rejected\|compile_rejected | rejected\|identity_mismatch |
|---|---:|---:|---:|---:|
| KEEP arrival | 3 | 332 | 1 | 0 |
| KEEP correction | 0 | 719 | 64 | 1 |
| SUB arrival | 0 | 336 | 0 | 0 |
| SUB correction | 0 | 773 | 11 | 0 |

Known accepted wrong bindings (regression fixtures, not independent validation):

| Call | Disposition | Resolved field | Compiled fields | Final accepted | Partners (usable exact) |
|---|---|---|---|---|---|
| `c22-g0016\|arrival\|B\|KEEP` | identity_mismatch | `Jehobofa.on_hand` | `['Jejudujo.on_hand']` | False | A\|KEEP: exact; A\|SUB: exact; B\|SUB: exact |
| `c22-g0095\|arrival\|B\|KEEP` | identity_mismatch | `Bekicaja.on_hand` | `['Dadubudo.on_hand']` | False | A\|KEEP: exact; A\|SUB: exact; B\|SUB: exact |
| `c22-g0111\|arrival\|B\|KEEP` | identity_mismatch | `Cacekihe.on_hand` | `['Hakojudi.on_hand']` | False | A\|KEEP: exact; A\|SUB: exact; B\|SUB: exact |

Other identity mismatches (all listed):

| Call | Originally accepted | Original code | Compiled fields | Resolved field |
|---|---|---|---|---|
| `c22-g0016\|correction\|B\|KEEP` | False | correction_target | `['Jejudujo.on_hand']` | `Jehobofa.on_hand` |

No previously exact response was blocked in this study.

## Controls (separate from study totals)

24 public-only fixtures; status PASS; supported matches pass: True; refusals abstain: True. Identity-only limits: a matching subject with a wrong time or value passes; it is not caught.

## Evidence preservation

Before/after hashes of both study hubs and both frozen source trees: unchanged (409, 420, 2450, 2331 files).

## Interpretation boundaries

- Both panels were constructed to keep cases where the public resolver matched gold, so preserving exact responses here is largely expected; this is not an independent validation of the resolver.
- Both panels were already inspected. Zero remaining accepted wrong bindings is a property of these selected cases under this guard's scope, not an estimated error rate or evidence of general safety.
- Blocked wrong answers stay wrong: rejection gives no exactness credit and rescues nothing.
- A matching subject with a wrong time or value passes this check (see controls).
- Abstentions in study data: V1.24 0, V1.22 0. Refusal/abstain behavior is therefore exercised only by the separate controls, not by these panels.
- The V1.24 COMPLETE / QUALIFIED and V1.22 results are unchanged historical evidence; the wrapper inherits no qualification. V1.24 and V1.22 counts are not pooled.

Artifacts: `PLAN.json`, `DEPENDENCIES.json`, `INPUT-MANIFEST.json`, `decisions/` (sealed ledgers), `DETERMINISM.json`, `results/` (RESULTS + per-call TRACE + EVALUATION-STATUS), `controls/CONTROLS.json`, `tests/`, `PRESERVATION.json`, `READINESS.json`, `RUNTIME.json`, `TERMINAL.json`.
