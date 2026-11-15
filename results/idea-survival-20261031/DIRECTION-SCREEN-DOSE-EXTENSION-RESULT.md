# Direction screen, dose extension: result (2026-11-02)

Criteria: `DIRECTION-SCREEN-DOSE-EXTENSION-CRITERIA.md`, fixed before running. Hub: `gpu/qwen3-dose-extension-20261102-115545`. Source: 1.5.2 (150 tests pass), with the 1.5.1 vectors reused (sha256 20ae0b89…). Reports: `output/DOSE-EXTENSION-REPORT.json` and `output/REPLICATION-1-REPORT.json` in the hub. No judge calls were used.

## Decision: nothing passed and replicated. This is the final screen.

Reading-only (perceive-mode) steering with these directions does not produce category loosening or abstractness beyond random perturbation, at any tested dose, in Qwen3-8B. As declared beforehand, there are no further doses or metrics.

## What happened

- **Object set A:** 18 cells were tested (D1 and D2 × blocks −12, −8 and −4 × λ 0.4, 0.6 and 0.8). One cell, D1 at block −12 and λ 0.4, passed the rule, but only just:
  - category distance 0.411 vs the best random 0.401;
  - abstractness shift 0.059 vs the best random 0.058.
  
  Every other cell failed at least one metric. All cells were 100% valid.
- **Replication on the held-out object set B (24 new objects), for the same cell:**
  - category distance 0.414 vs the best random 0.412, which passes;
  - abstractness shift 0.032 vs the best random 0.047, which **fails**.
  
  So the cell is not accepted. No second passing cell existed to try.
- **Abstractness:** with one cell's exception, the candidates never moved abstractness beyond random. The largest candidate shift at any dose was 0.059 on a 1–5 concreteness scale, which is negligible.

## Unchanged-output rates (share of greedy outputs identical to baseline)

| block | λ | D1 | D2 | random (mean of 9) |
|---|---|---|---|---|
| −12 | 0.4 | 0.42 | 0.44 | 0.43 |
| −12 | 0.6 | 0.23 | 0.27 | 0.29 |
| −12 | 0.8 | 0.15 | 0.19 | 0.21 |
| −8 | 0.4 | 0.67 | 0.62 | 0.66 |
| −8 | 0.6 | 0.52 | 0.42 | 0.50 |
| −8 | 0.8 | 0.44 | 0.29 | 0.38 |
| −4 | 0.4 | 0.79 | 0.73 | 0.67 |
| −4 | 0.6 | 0.71 | 0.71 | 0.56 |
| −4 | 0.8 | 0.67 | 0.52 | 0.46 |

Replication set B, D1 at −12 and λ 0.4: 0.31, against a random mean of 0.42.

Higher doses do change more outputs, but the candidates change them about as often as random directions do. The changes are the same kind as random ones: rewording, and swapping one category label for a near-synonym.

## Example outputs (block −12, greedy)

**Snow globe, categories**
- **Baseline:** decorative items, holiday decorations, glassware, collectibles, indoor decor
- **D1 at λ 0.4, 0.6 and 0.8 (identical):** decorative items, collectibles, holiday items, glassware, novelty items
- **D2 at λ 0.8:** decorative items, collectibles, holiday items, glassware, indoor decor
- **Random R0 at λ 0.8:** decorative objects, holiday items, collectibles, glassware, winter-themed items

**Snow globe, description**
- **Baseline:** "…a decorative glass ball filled with water and tiny snowflakes, enclosing a small scene that is often depicted as a winter landscape…"
- **D1 at λ 0.8:** "…enclosing a small scene that becomes visible when the globe is shaken. When agitated, the water and flakes swirl around, creating a gentle, sparkling effect that mimics a winter snowfall."
- **D2 at λ 0.8:** almost the same as D1 ("glass sphere", "simulating a winter snowfall").
- **Random R0 at λ 0.8:** identical to baseline.

**Wind chime, categories**
- **Baseline:** wind chimes, musical instruments, decorative items, outdoor accessories, sound producing objects
- **D1 and D2 at λ 0.8:** Decorative Objects, Musical Instruments, Outdoor Decor, Home Accents, Wind-Activated Objects
- **Random R0 at λ 0.8:** wind chimes, musical instruments, decorative items, outdoor accessories, acoustic devices

Even at the highest dose, the steered outputs stay literal, conventional descriptions. Nothing poetic or category-breaking appears.

## Interpretation

- The read-time steering hypothesis ("introduce the idea while decategorized") is not supported for these directions in Qwen3-8B. The steered object tokens only alter later blocks' keys and values. The unsteered instruction and decoding then pull the output back to the model's default framing.
- The plan's Step 1 stop condition is met. Per the plan, Steps 2–4 (ladder judge, ladder pilot, confirmation) are **not** started; David decides the next direction.
- **Not claimed:** this is not evidence that decategorization cannot be induced. It covers prefill-only steering, these three directions, blocks 24, 28 and 32, λ ≤ 0.8, greedy decoding, and an 8B model. Decode-time ("generate" mode) steering was not screened with these metrics.

## Housekeeping

The first launch exited with code 2 (`HALTED-direction-screen-7-8.json`) because argparse read `--layers -12,-8,-4` as a flag. No probes had run. The run was fixed with `--layers=` and resumed; nothing was resampled.
