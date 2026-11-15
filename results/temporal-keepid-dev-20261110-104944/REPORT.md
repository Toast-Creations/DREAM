# KEEP+ID representation, development screen (V1.21.0)

**Completed November 10, 2026. Development on the inspected 1.20 panel; not fresh confirmation.**

On the 64 F1–F3 arrival targets, KEEP+ID (original sentence plus one identity annotation line) was exact on **58/64**, against **45/64 for SUB** (the 1.20 deterministic rewrite) and **48/64 for BASE**. The focal development difference, KEEP+ID − SUB, was **+0.203**, with a 95% stratified group-bootstrap interval of **[+0.063, +0.344]**.

The cost showed up in corrections. On the 64 F1–F3 corrections, KEEP+ID was exact on **59/64**, against **62/64 for SUB** (−0.047 [−0.109, +0.016]). That sits exactly on the pre-declared tolerance (SUB − 3).

There were no accepted wrong bindings in either identity arm. Accepted state-only arrivals fell from 18 (SUB) to 6 (KEEP+ID) on F1–F3. All five KEEP+ID correction errors were rejected by the engine, not accepted. Under the pre-declared development guide, the evidence **warrants preparing a fresh confirmation**. The correction condition passed only at its boundary, so it should be a co-primary or a guarded secondary in that confirmation (see the end).

## What was compared

| Arm | Source | Target sentence | Identity |
|---|---|---|---|
| BASE | 1.20 main-A `BASE` records (cached) | original | none: a reference comparison, not identity-matched |
| SUB | 1.20 main-A `DET` records (cached) | phrase replaced by `part X` | in the sentence |
| KEEP+ID | 192 new calls | original, unchanged | separate line: `Resolved reference: "<phrase>" = part X (field X.on_hand).` |

**How the KEEP+ID prompt was built:**
- The KEEP+ID prompt is the 1.20 BASE prompt byte-for-byte, plus that single line placed directly before `New record to convert:`.
- X comes only from the frozen 1.20 deterministic resolver, run over public input.
- The construction labels agreed with X on 192/192 targets. They were checked separately, after the prompts were built.
- SUB names the same part on 192/192.
- No reasoning scaffold, act hint or extra instruction was added.
- The learned RES-MODEL outputs were not used.

**What this comparison can and cannot show.** KEEP+ID vs SUB compares two representation packages. Sentence wording, length and how the identity is presented all differ. A gain supports this tested workflow. It does not isolate shortening or name substitution as the cause.

**Targets.** The targets are the 1.20 panel's 96 arrival and 96 correction targets:
- **MAIN:** F1 two-hop (8 groups), F2 slot join (8) and F3 historical occupant (16). That is 32 groups and 128 targets.
- **F4:** measurement order, 16 groups and 64 targets, reported separately and never pooled with MAIN.

**Statistics.** The construction group is the unit, so both histories stay together. The interval is a 10,000-resample bootstrap stratified by family × reception, seed 20261110. These intervals describe this inspected panel and are descriptive.

## Main development set (F1–F3)

| Act | BASE | SUB | KEEP+ID | KEEP+ID − SUB | KEEP+ID − BASE | SUB − BASE |
|---|---:|---:|---:|---:|---:|---:|
| **Arrival (focal)** | 48/64 | 45/64 | **58/64** | **+0.203 [0.063, 0.344]** | +0.156 [0.078, 0.234] | −0.047 [−0.234, 0.125] |
| Correction (regression check) | 61/64 | 62/64 | 59/64 | −0.047 [−0.109, 0.016] | −0.031 [−0.094, 0.031] | +0.016 [−0.047, 0.078] |
| Both acts | 109/128 | 107/128 | 117/128 | +0.078 [0.008, 0.148] | +0.063 [0.008, 0.117] | −0.016 [−0.109, 0.070] |

**Paired targets, KEEP+ID vs SUB:**
- Arrivals: 43 both exact, 15 KEEP+ID only, 2 SUB only, 4 neither.
- Corrections: 58 both, 1 KEEP+ID only, 4 SUB only, 1 neither.

**History pairs (both histories exact), out of 32 group × act units per act:**
- Arrivals: BASE 19, SUB 20, KEEP+ID 28. KEEP+ID vs SUB: 19 both, 9 KEEP+ID only, 1 SUB only, 3 neither.
- Corrections: BASE 29, SUB 30, KEEP+ID 27.

**By family and act:**

| | BASE | SUB | KEEP+ID |
|---|---:|---:|---:|
| F1 arrival | 10/16 | 11/16 | 11/16 |
| F2 arrival | 15/16 | 12/16 | 16/16 |
| F3 arrival | 23/32 | 22/32 | 31/32 |
| F1 correction | 16/16 | 16/16 | 16/16 |
| F2 correction | 14/16 | 15/16 | 13/16 |
| F3 correction | 31/32 | 31/32 | 30/32 |

**By reception:**
- Arrivals, immediate: BASE 23/32, SUB 23/32, KEEP+ID 28/32.
- Arrivals, delayed: BASE 25/32, SUB 22/32, KEEP+ID 30/32.
- Corrections, immediate: 31, 31 and 29 of 32.
- Corrections, delayed: 30, 31 and 30 of 32.

The arrival gain is concentrated in F3 (+9 over SUB) and F2 (+4). F1 is unchanged at 11/16. All five KEEP+ID F1 misses are state-only arrivals; four of them are also inexact in SUB and BASE. Subgroup counts are descriptive.

### Errors and acceptance (F1–F3, 128 targets per arm)

| Diagnostic | BASE | SUB | KEEP+ID |
|---|---:|---:|---:|
| Exact | 109 | 107 | 117 |
| Accepted | 124 | 125 | 123 |
| Accepted wrong binding | 8 | 0 | 0 |
| Accepted but inexact | 15 | 18 | 6 |
| Accepted state-only arrival (of 64) | 6 | 18 | 6 |
| Arrival without an event on the gold field | 15 | 18 | 6 |
| Mixed state/revision correction (of 64) | 2 | 2 | 3 |
| Value contradiction, internal / against gold | 2 / 2 | 2 / 2 | 3 / 3 |
| Rejected (codes) | 4 (2 mixed_acts, 1 multiple_events, 1 correction_target) | 3 (mixed_acts) | 5 (3 mixed_acts, 2 empty) |
| Accepted false revision | 1 | 0 | 0 |
| Truncated, or incomplete | 0 | 0 | 0 |

Categories overlap and must not be added.

**What remains wrong in KEEP+ID:**
- **Arrivals:** all six accepted inexact outputs are state-only arrivals that drop the event. Five are F1: g033 A and B, g034 A and B, and g035 A. Of these, only g033 B is exact in SUB. The sixth is g001 A (F3), which is exact in both SUB and BASE.
- **Corrections:** the five errors are all rejected.
  - Three are the NO-state + YES-revision contradiction: g041 A and g047 B (new relative to SUB), and g044 A (also in SUB).
  - Two are new empty replies (g003 B, g016 B). The model returned all-empty lists with a correct quotation, and the engine rejected them as `empty`.

These correction failures fail closed. Accepted inexact corrections are 0 in every arm.

## F4 measurement order (separate stratum, supplied identity)

| Act | BASE | SUB | KEEP+ID | KEEP+ID − SUB | KEEP+ID − BASE |
|---|---:|---:|---:|---:|---:|
| Arrival | 8/32 | 21/32 | 24/32 | +0.094 [0.000, 0.250] | +0.500 [0.281, 0.719] |
| Correction | 28/32 | 30/32 | 31/32 | +0.031 [0.000, 0.094] | +0.094 [−0.031, 0.219] |

Paired F4 arrivals, KEEP+ID vs SUB: 21 both, 3 KEEP+ID only, 0 SUB only, 8 neither.

**Error counts on the 64 F4 targets:**
- Accepted wrong binding: BASE 17, SUB 0, KEEP+ID 0.
- Accepted state-only arrivals: BASE 13, SUB 11, KEEP+ID 8.
- Mixed corrections: SUB 2, KEEP+ID 1. The KEEP+ID case is g030 B, NO state + YES revision, rejected. It is new; SUB was exact there.

Six F4 groups (g019, g025, g027 and g028 in both histories) are state-only in both identity arms. The supplied identity here bypasses the resolver weakness that dominated F4 in 1.20, so these numbers say nothing about F4 resolution.

## The 19 correct-resolution regression probes

The SUB classes were recomputed from the cached records and match the corrected classification on all 19:
- 14 accepted state-only arrivals;
- `g012|arrival|B` rejected for mixed acts (event kept with `from:"no"`, plus a reception-time state; not an event omission);
- four corrections with a NO state and a contradictory YES revision.

BASE was exact on all 19, by construction of the probe set. KEEP+ID was exact on **18/19**.

| Target | Family, reception | SUB (1.20) | KEEP+ID | KEEP+ID claims (events / states / revisions) |
|---|---|---|---|---|
| g002 arrival A | F3 delayed | accepted state-only | exact | event Kadekebo no→yes @9 / state yes @9 / – |
| g002 arrival B | F3 delayed | accepted state-only | exact | event Kajufaci no→yes @9 / state yes @9 / – |
| g003 arrival A | F3 immediate | accepted state-only | exact | event Hujekoba no→yes @9 / state yes @9 / – |
| g003 arrival B | F3 immediate | accepted state-only | exact | event Jukefaco no→yes @9 / state yes @9 / – |
| g009 arrival A | F3 immediate | accepted state-only | exact | event Fubecaha no→yes @9 / state yes @9 / – |
| g010 arrival A | F3 delayed | accepted state-only | exact | event Dihukihu no→yes @10 / state yes @10 / – |
| g010 arrival B | F3 delayed | accepted state-only | exact | event Haduceco no→yes @10 / state yes @10 / – |
| g011 arrival A | F3 immediate | accepted state-only | exact | event Bubefobu no→yes @10 / – / – |
| g011 arrival B | F3 immediate | accepted state-only | exact | event Johehice no→yes @10 / – / – |
| g012 arrival B | F3 delayed | rejected: event + reception-time state (mixed_acts) | exact | event Dahukibe no→yes @10 / – / – |
| g036 arrival B | F1 delayed | accepted state-only | exact | event Hajajehe no→yes @10 / state yes @10 / – |
| g041 arrival A | F2 immediate | accepted state-only | exact | event Dabihuhe no→yes @9 / state yes @9 / – |
| g041 arrival B | F2 immediate | accepted state-only | exact | event Hifokije no→yes @9 / state yes @9 / – |
| g042 arrival A | F2 delayed | accepted state-only | exact | event Dajobeki no→yes @8 / state yes @8 / – |
| g042 arrival B | F2 delayed | accepted state-only | exact | event Hufaface no→yes @8 / state yes @8 / – |
| g005 correction A | F3 immediate | rejected: state NO + revision YES | exact | – / – / revision Habuhofu no from 3 |
| g018 correction A | F4 delayed | rejected: state NO + revision YES | exact | – / state no @3 / revision no from 3 |
| g030 correction A | F4 delayed | rejected: state NO + revision YES | exact | – / state no @4 / revision no from 4 |
| g044 correction A | F2 delayed | rejected: state NO + revision YES | rejected: state NO + revision YES | – / state no @6 / revision **yes** from 6 |

The states that accompany events and revisions in the exact rows are redundant claims of the same value; the frozen reduction removes them. The probes were selected because SUB regressed on them. They are development cases, so 18/19 is not an unbiased rate.

## Decision guide (declared before output)

| Condition | Threshold | Observed | Met |
|---|---|---|---|
| MAIN arrival KEEP+ID − SUB | point > 0 and 95% lower bound > 0 | +0.203, lower bound +0.063 | yes |
| MAIN correction exact | KEEP+ID ≥ SUB − 3 | 59 ≥ 62 − 3 = 59 | yes, at the boundary |
| MAIN accepted wrong binding | KEEP+ID ≤ SUB + 2 | 0 ≤ 2 | yes |

Outcome: **warrants preparing fresh confirmation.** This is a development reading on data that had already been inspected. The probes and family structure were known before the screen, and the arms share the 1.20 panel. It is not a confirmatory result, and one correction fewer would have flipped the guide to "does not warrant".

## Cost and collection

**Collection:**
- All 192 KEEP+ID calls were scheduled, attempted once, and completed with status `ok` and EOS stops. There were 0 failures, 0 retries and 0 truncations: 192/192 attempts.
- Smoke: 4 scheduled calls, reused in the analysis, 10:59:43–11:02:20.
- Main: 188 calls, 11:02–11:47:05. Analysis finished at 12:03.
- Deadline 12:59:43 (driver start + 2 h), not reached.

**Hardware and model:**
- Both stages ran on `cuda:0` only. Peak allocated GPU memory was 18.75 GiB; host RSS at load was 4.9 GiB.
- Model: Qwen3-32B @9216db57, NF4 double quantization, BF16 compute, greedy decoding, thinking off. Input cap 2,048 (the longest KEEP+ID input was 1,517 tokens); output cap 256 (the longest output was 194).

**Per-target cost:**

| Arm | Mean input tokens | Mean output tokens | Mean generation s | Total s (192) |
|---|---:|---:|---:|---:|
| BASE (1.20 run) | 1,376.0 | 139.2 | 12.24 | 2,350.5 |
| SUB (1.20 run) | 1,367.1 | 140.0 | 12.30 | 2,361.1 |
| KEEP+ID (this run) | 1,409.1 | 152.3 | 13.82 | 2,653.4 |

- KEEP+ID adds about 33–42 input tokens and about 12 output tokens per target. Its generation time is about 12% higher than SUB's.
- The BASE and SUB times were measured in the 1.20 session on November 6, so they are not a same-session timing comparison.
- Neither identity arm includes the cost of finding the identity. Here that was a deterministic CPU resolver over a declared grammar, which does not exist for open text.

## Integrity and provenance

**Before collection** (gates K1–K7 all pass; `phase0/VALIDATION.md`):
- **Prompt preservation:** removing the annotation line returns the 1.20 BASE prompt byte-for-byte.
- **Public-only identity construction:** an allowlisted rebuild is byte-identical, and the prompt-building code reads no hidden fields.
- **Labels and identity:** construction labels and SUB/KEEP+ID identity parity hold on 192/192.
- **Token budget:** checked with the pinned tokenizer, which also reproduces the 1.20 BASE counts.
- **Scoring:** canonical replies are exact, semantic mutations are inexact, and the cached 1.20 BASE and SUB replies re-score identically.
- **Cache provenance:**
  - Every reused record has status ok, one attempt and the pinned model settings.
  - `user_sha256` equals the stored prompt and the 1.20 committed call.
  - The 1.20 main-A LOCK binds the 1.20 freeze hashes.
  - The explicit mapping is in `data/CACHE-MAP.jsonl`.

**Tests:** 421/421 pass with `--require-ml`, including 5 new tests.

**Hashes:**
- Source: `Code/DREAM-project-1.21.0-keep-id-dev-20261110`, release hash `f7205cb0…`. It is not committed to git and not pushed.
- FACT-v1, the compiler, the engine, HOLD-EVAL-v1, `refres.py`, the runner and the loader are byte-identical to 1.20.
- Freeze: `config/FROZEN-PROTOCOL.json`, sha `2440751a2bb4…`, written before any model output. It holds the source, input, configuration, schedule, cache-map, validation, driver and protocol hashes.
- Schedule `kid-calls.jsonl`: `bf371ef6…`. Results: `analysis/kid/ANALYSIS.json` `74bba547…` and `scored.jsonl` `9e5bb09d…`.

**After collection:** the 44 hashed 1.20 frozen and completion artifacts and the 1.20 source (`384d2fd0…`) were re-verified as unchanged. All 1.21 frozen files were re-verified as unchanged.

No prompt, arm, mask or scoring change was made after output, and no harness defect was found. The smoke check was structural only, and no exactness was computed before the main stage.

**Pre-collection fixes, before any output:**
- One validator mutation fixture was corrected. It had added a state identical to the canonical one, which is not a mutation.
- The commitment was regenerated under the final source, giving the identical schedule hash.
- The driver gained a frozen-file check.

## Limitations

- **Inspected development data.** The 1.20 panel, its families and these 19 probes were examined before the screen. The arms are compared on the same 192 targets, and BASE and SUB come from a run four days earlier, under the same model settings.
- **Representation package, not mechanism.** KEEP+ID changes several things at once relative to SUB. The result does not show why it helps.
- **Interval scope.** The intervals are for 32 authored groups within the declared grammar. The correction difference is inconclusive in both directions; it does not establish equivalence or a regression.
- **Residual arrival error.** The state-only arrival error persists in F1 and F4 even with the original wording and the identity supplied (6 F1–F3 and 8 F4 accepted state-only outputs). KEEP+ID reduces this error on this panel; it does not remove it.
- **New correction failure modes.** KEEP+ID introduced two empty correction replies and two new NO/YES contradictions. They were rejected, but they are failures.
- **Gold identity.** The identity is gold from a declared-grammar resolver. Nothing here measures performance with a learned or imperfect resolver, on open text, or in action outcomes.

## Recommendation: preparing a fresh confirmation (not generated or collected)

The development evidence supports preparing the Stage 1 confirmation. These items would need to be frozen before any output:

1. **A fresh panel** from new seeds, not the 1.20 panel or these probes. Use the same four families, with F4 as a separate stratum with supplied identity. Decide whether all four acts are included, or only arrivals and corrections plus removal/observation as a non-regression check.
2. **The KEEPID-v1 wording and placement, exactly as here.** No retuning is justified by this screen.
3. **Arms:** BASE, SUB and KEEP+ID, all newly generated on the fresh panel. Cache reuse is allowed only for byte-identical prompts.
4. **Endpoints:**
   - Primary: arrival exactness KEEP+ID − SUB on F1–F3.
   - Correction exactness KEEP+ID − SUB as a co-primary non-inferiority test or a guarded secondary, with a margin fixed in advance. The development margin passed only at its boundary.
   - Accepted wrong binding as a safety check.
5. **Declared secondaries:** state-only arrivals, empty replies, NO/YES mixed corrections, and accepted inexact outputs.
6. **Sample size** chosen for the correction margin as well as the arrival effect. With about 64 corrections per arm, a 3-target difference is not resolvable.
7. **Fixed resources, plus a statistic and seed fixed before output.** Use the same model recipe and caps.

The draft plan's Stage 1 section has been updated to describe what was actually tested. The original draft is preserved in `history/arrival-plan-draft-0.1-20261110/`. Nothing beyond this report was started: no confirmation, no Stages 2–4, no training, no engine change, no publication or push.

---

## Errata (2026-11-10, appended after Codex review; text above left as originally written)

Both errata were checked against `analysis/kid/scored.jsonl` (sha 9e5bb09d…). Neither changes a count, interval, decision guide outcome or frozen file.

1. **F4 persistent state-only cases: four groups, not six.** The F4 section says "Six F4 groups (g019, g025, g027 and g028 in both histories) are state-only in both identity arms." The correct statement is **four groups (g019, g025, g027, g028), both histories each, i.e. 8 targets**, accepted state-only in both SUB and KEEP+ID.
2. **Where the KEEP+ID correction failures were rejected.** The summary and the "What remains wrong" section say the five F1–F3 KEEP+ID correction errors (and the F4 g030 B case) were "rejected by the engine". They were **rejected at FACT-v1 compilation, before engine ingestion** (`compiled: false`, `pending_code` `empty` or `mixed_acts`, `contract_code` null). They remain errors under HOLD-EVAL-v1, and none was accepted.

The earlier session summary to David carried the same two wordings and is corrected by this erratum.
