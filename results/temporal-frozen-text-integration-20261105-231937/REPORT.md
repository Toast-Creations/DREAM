# Frozen-text integration of temporal observation coverage (V1.15.0): report

- **Date:** 2026-11-05.
- **Brief:** `design/BRIEF-copy.md`. **Plan:** `design/STUDY-PLAN.md`, frozen in `config/FROZEN-PROTOCOL.json` (source sha256 `d76273ce…e908`). No amendments.
- **Source:** `Code/DREAM-project-1.15.0-frozen-text-integration-20261105`. 162 inherited 1.14.0 files are byte-identical, including the selector, timing, projection, reference, text channel, adapter and call runner.
- **Tests:** 193/193 pass.
- **Predecessor:** 1.14.0 is pushed as `8378e1e`, with notes N1 and N2 (`6fadc9f`). The 1.14.0 provenance qualification, the scratch plumbing trial on its main allocation, is restated in the plan.
- **Plumbing for this study:** test fixtures; the disjoint smoke worlds with fake replies, in a deleted scratch folder; and old inspected panels. The new main panel was not run before the freeze.

## Execution
- **Model calls: 169 in total.**
  - **Smoke:** 25/25 ok, 78.5 s of generation. One reply was unmapped and was preserved as pending evidence.
  - **Main:** **144/144 ok** (6 reports × 24 worlds; the count is the natural one, under the ceiling of 192), 0 truncated, 0 retried, 430.8 s of generation, 14,565 output tokens.
  - **Runtime:** main stage 453 s wall including model load, against a frozen ceiling of 1,356 s. Peak GPU memory was 15.6 GiB.
- **Model:** Qwen3-8B `b968826d…`, BF16, thinking off, greedy, 256 tokens. This matches the 1.11.0 configuration (validation 7).
- **CPU evaluation:** 7 s for 384 decision trajectories (192 per channel). Verification runs are not observations: 384 perfect-channel and gold-poisoning clones, and 768 leakage runs.
- **Ingestion** finished before the simulated window. Model time is not inserted into virtual time.

## Software and readiness gates: all pass

| Gate | Result |
|---|---|
| S1 support, classes and choice equal the independent reference given the same evidence (both channels) | 0 / 384 failures |
| S2 structured: actual state in support; no unsupported choice, invalid attempt or false completion | 0 / 192 |
| S3 frozen selector rule on each channel's evidence; independent selector check | 0 / 192 |
| S4 perfect extraction reproduces structured; poisoning the gold reports changes no text result | 0 / 192 |
| S5 clock, fees, receipts and context isolation, history, invariants, cost identity, shared actual state and readings, tape independence, channel lengths | 0 / 384 |

These also passed before collection:
- 1.14.0 structured regression, 272/272;
- 1.14.0 perfect-channel regression, 192/192;
- 1.11.0 adapter replay on 144 stored replies, 24/24 streams identical;
- allowlist re-mapping, exact;
- `check_equivalent` on every rendering;
- the 1.14.0 allocation structure, reproduced exactly on the new instances.

## Results (changing environment unless noted; λ = 1; n = 24 worlds; descriptive domain-stratified bootstrap)

| Contrast | Mean | 95% interval | worlds + / = / − |
|---|---|---|---|
| **PRIMARY: text DEPENDENCY − BASE** | **+2.19** | **[+1.15, +3.27]** | 15 / 3 / 6 |
| Structured DEPENDENCY − BASE (calibration) | +2.67 | [+1.73, +3.62] | 18 / 3 / 3 |
| Interface loss text − structured, BASE | −0.29 | [−0.67, −0.06] | 0 / 18 / 6 |
| Interface loss text − structured, DEPENDENCY | −0.77 | [−1.31, −0.25] | 0 / 19 / 5 |
| Change in augmentation benefit (text − structured) | **−0.48** | [−0.94, −0.08] | 1 / 19 / 4 |
| Delivery: text = structured, DEPENDENCY − BASE | +2.21 | [+0.96, +3.58] | change in benefit exactly 0 |
| Assembly: text / structured, DEPENDENCY − BASE | +2.17 / +3.13 | [+0.54, +3.88] / [+1.75, +4.46] | change −0.96 [−1.88, −0.17] |
| Goal A / goal B, text DEPENDENCY − BASE | +1.33 / +3.04 | [+0.21, +2.58] / [+1.62, +4.46] | |
| Stable: DEPENDENCY − BASE (both channels) | 0 exactly | | |
| Stable: interface loss (either selector) | −0.94 | [−1.52, −0.38] | 0 / 18 / 6 |

**Read under the frozen rules:**
- **The primary is positive with its interval above 0.** On this panel, the relative utility benefit of DEPENDENCY over BASE **survived the language interface**, under the stated dynamics and costs.
- **The interface was not free.** Both arms lost utility, DEPENDENCY lost more, and the augmentation benefit shrank by about 0.48 per world. All of the shrinkage is in assembly. This is not an equivalence result, and no noninferiority margin was set.

**Totals over 48 changing goal copies:**

| Arm | Successes | Declines | Fees | U |
|---|---|---|---|---|
| Structured BASE | 13 | 35 | 20 | −125 |
| Structured DEPENDENCY | 40 | 8 | 59 | +3 |
| Text BASE | 12 | 36 | 26 | −139 |
| Text DEPENDENCY | 35 | 13 | 62 | −34 |

- **Invalid actual attempts and false completions:** **0** on every channel and arm. There were 0 projection-limit events.
- **Actual state in support:** 42/48 text copies (48/48 structured). The other 6 had **empty support**: a declined decision, not a false permission.
- **Query effects in the text channel:** 35 augmented copies with 36 added facts.
  - Success gain in 23 copies (23 facts).
  - No decision change in 12 copies (13 facts).
  - Lower utility than BASE in 13 copies.

  For comparison, structured had 37 copies with 39 facts: 27 gains (28 facts) and 10 with no change (11 facts).

## Where the interface failed: one interpretation class
**Extraction audit** (deterministic scorer; 144 records):
- Structural results: 144 parsed, 144 mapped, 144 accepted.
- Meaning: **136 exactly correct**, with no wrong statuses. The 8 errors each have 0 coverage and 1 spurious atom.

**All 8 errors are stock-change events in assembly:**
- **"Part X arrived for you / was delivered to you, so it is now on hand": 6 of 6 misread.** The model wrote a verified *state* (`initial`) with the right value instead of a change event (a01 r2, a02 r6, a07 r6, a08 r3, a10 r6, a12 r6).
- **"Part X was taken away / is no longer on hand": 2 of 3 misread.** One became an observation (a04 r4) and one a correction (a09 r4).
- Every **location change (28/28)**, **slot change (4/4)**, observation (103/103) and uncertain change (4/4) was correct.

This is the same failure class found in 1.10.0 ("delivered/arrived for you" read as a state, 7 of 8 losses there). It persists under the frozen prompt.

**How the error propagates** (traced per copy):
1. The misread state contradicts the earlier verified stock observation, producing a verified–verified **historical conflict**. This affected 7 worlds (both goal copies of each, 14 copies).
2. For the goal that needs that part, P2 now queries the conflicted stock field, adding a fee. This happened in 6 copies: a01/A, a04/B, a07/A, a08/A, a10/B and a12/A.
3. The truthful t = 2 reading is incompatible with every trajectory implied by the conflicted history. Support is **empty**, so the copy **declines**.
4. As frozen, the conflict is kept, and sensor authority is not extended to hide it.
5. These 6 copies decline under both selectors and in both environments. Where structured succeeded, text loses the success: under DEPENDENCY in a01/A, a07/A, a10/B and a12/A (changing), and under both selectors in a08/A (both environments). a04/B is full-domain infeasible either way and only pays the extra fee.

In the other 8 conflicted copies (the other goal of each affected world, plus a09), S2 differed from structured but the plan and outcome did not. Each cell has 14 of 48 copies with a divergent S2, and 6 of those 14 have a downstream consequence. **Delivery was untouched:** the text channel agreed with the structured one in every delivery copy.

## Interpretation and limits
- **Augmentation helps in both channels.** Its benefit survives a frozen language interface that reads 94% of reports exactly. The cost of interpretation errors lands as *declines*, not unsafe actions, because conflict handling stays conservative.
- **The bottleneck is language interpretation, not observation coverage, evidence representation or the cost policy.** It is one specific class: stock-change events. "Arrived / delivered → now on hand" is read as a state report.
  - The engine then does the right conservative thing, and a truthful reading cannot rescue it under the frozen authority rule.
  - DEPENDENCY is hurt more than BASE because it would otherwise have recovered those goals.
- **Not shown:** a learned world model, robustness to other phrasings, or other models. The panel is designed, and the error class is concentrated in assembly. This is not real-time operation. Zero invalid attempts holds for this panel only. No wording repair, reinterpretation or authority change was launched.

## Files
- `data/`: public worlds, the public goal-blind text inputs, calls with prompt hashes, commitments; `data/hidden/` holds truth, tape, gold.
- `stages/main/calls/`: raw replies, tokens, seconds.
- `stages/main/eval/`:
  - `channels.jsonl` (the shared goal-blind stream, with adapter logs);
  - `selections.jsonl` (channel-specific Q0, S2 and selection);
  - `trajectories.jsonl` (sensor ledgers in the receipts);
  - `selcheck`, `reference`, `parity`, `poison`, `leakage`, `feasibility` and `extraction` files;
  - `EVAL-META.json`.
- `analysis/main/ANALYSIS.json` and `TABLES.md` (all divergence traces); `phase0/`; `stages/smoke/`; `run_stage.sh STAGE SET [--require-freeze]`.

**Stopped after this report.** The 1.15.0 source is not committed to Git.
