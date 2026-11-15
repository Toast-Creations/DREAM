# Milestone 2: history interpretation over state engine v0.1 (development only)

## Status
- **Protocol:** `design/PROTOCOL.md` and `design/IMPLEMENTATION-NOTES.md`, frozen before any output (`config/FROZEN-PROTOCOL.json`; main config in `config/MAIN-CONFIG-FROZEN.json`).
- **Source:** 1.8.1, with engine v0.1 unchanged. Tests: 71/71.
- **Ran:** 2026-11-05, 10:08–10:18 America/New_York.
  - Smoke: 24/24 calls, not pooled.
  - Main: **216/216** calls in 574 s. No calls failed, were truncated or needed retries. Longest input was 1,384 tokens; peak memory 15.6 GiB.
  - Nothing was changed after smoke.
- **Setup:** Qwen3-8B rev b968826d…, bf16, thinking off, greedy decoding. Prompts use the 1.7.1 rules plus the 1.7.2 domain statements.
- **Histories:** 24 fresh histories (12 delivery, 12 assembly), each with 6 records and 3 checkpoints, and 2 hypothetical action tests per checkpoint. The history is the independent unit; everything else is nested inside it.

## Main results (paired over 24 histories; domain-weighted)
| System | Final state exact | Action-verdict accuracy (vs supported state) |
|---|---|---|
| **S**, structured records (reference, 0 calls) | 24/24, 1.000 | 144/144, 1.000 |
| **X**, per-record extraction (144 calls) | 20/24, 0.833 [0.71, 0.96] | 131/144, 0.910 [0.81, 0.99] |
| **R**, full-history readout (72 calls) | 10/24, 0.417 [0.25, 0.54] | 122/144, 0.847 [0.74, 0.94] |

R's ceiling under its frozen format is 142/144 verdicts; this was declared before the run.

| Contrast | Final state exact | Verdict accuracy |
|---|---|---|
| X − S | −0.167 [−0.29, −0.04] (0 better / 20 equal / 4 worse) | −0.090 [−0.19, −0.01] (0/20/4) |
| R − S | −0.583 [−0.75, −0.46] (0/10/14) | −0.153 [−0.26, −0.06] (0/14/10) |
| **X − R** | **+0.417 [0.25, 0.58] (10/14/0)** | +0.062 [−0.08, 0.20] (8/14/2) |

- **The structured reference passed** at every checkpoint, so the engine and its specification held. The X and R results can be read as interpretation effects.
- **Per-record extraction plus the engine** beat full-history readout on final state in 10 histories, and was worse in none. On action verdicts the difference is smaller and its interval crosses zero.
- **No action test changed any log:** 216/216 checkpoint logs were unchanged.

## Where the errors are

### X: per-record extraction (144 records)
- **Parsing and linkage:** all 144 parsed, and every evidence quote was found in its record. That shows linkage only, not correctness.
- **Accuracy:** 135/144 exact, and 133 accepted by the engine.
- **Delivery:** 72/72 exact and accepted. The final state and all verdicts are identical to S.
- **Assembly:** 63/72 exact. Every error is in assembly. The concrete records:
  - **Correction convention (3 of the 8 corrections):** the model gave `event_at: 0` where the schema says `null` for a correction. The engine rejected these records, so the system went on believing the provisional report. This causes most of X's state errors. The target and `valid_from` were right in 8/8.
  - **"Delivered to you" event read as a new statement of fact (2):** it came back as `initial` instead of `change`. The engine rejected it as inconsistent, and later correct records about the same part were then rejected too, as a cascade (2 more).
  - **Observation missing its time (2):** `event_at: null` on an observation, rejected as not an integer.
  - **One initial record with four facts transcribed as a single observation:** accepted but wrong. That is the only wrong record the engine accepted.
  - **An unrecorded removal read as `uncertain_change` with one option:** rejected.
- **Unit counts:**
  - X's state errors: 8 fields missing, from rejected records, and 6 wrong values. It made **no** false "unknown" answers and **no** false certainty.
  - Its verdict errors fall in 4 assembly histories: 7 allowed actions became blocked, and 6 blocked actions became allowed.

### R: full-history readout
- **Pattern:** the dominant error is the same one seen in the pilot and the probe. **32 false "unknown" fields**, all on non-focal fields; the focal fact was wrong only twice. There was no false certainty, and 5 wrong definite values.
- **Final state:** wrong in 14 of 24 histories (delivery 3, assembly 11).
- **By pattern:** the correction pattern (3) is worst, with 3/12 checkpoints exact.
- **Verdicts:** "unknown" fields made 17 verdicts unresolved where the supported state decides them.

### Supported state vs hidden truth
- Even S, which is exact, allowed 5 actions that are illegal in the true world and blocked 5 that are legal. These come from evidence that was correct to accept but hadn't yet been corrected or settled: provisional reports not yet corrected, and unrecorded results not yet observed.
- So the gap between "consistent with the evidence" and "actually legal" exists even with perfect interpretation.
- Against the truth, X wrongly allowed 11 actions and R 8. That is S's 5 plus interpretation errors.

## Engine defect found (no effect on results)
- **The defect:** an extracted `change` can introduce an entity that no earlier record described, for example after the true first record was rejected or mis-transcribed. In that case engine v0.1 raises a plain `KeyError` instead of `RecordRejected` (2 records).
- **Why the results are unaffected:** the frozen analysis treats any engine exception at ingest as a rejection, so both records were skipped like any other rejected record.
- **Fix:** not patched after seeing outputs. To fix in the next engine version: reject such a record with a clear reason.

## Cost
- **X:** 6 calls per history, 15,300 output tokens, 443 s in total (about 3.1 s per record).
- **R:** 3 calls per history, 3,655 output tokens, 112 s.
- **Engine:** under 6 ms per history.
- The pipelines differ in calls and computation, so this is not an equal-cost comparison.

## Reading (protocol rules)
- **S passed:** the engine is sound.
- **X's errors are concrete record errors**, and so are classifiable.
- **The single biggest one is a schema convention** (`event_at` for corrections), which a model-independent validator could flag and send back to the extractor. That is a system design choice, and would itself need a test.
- **A "delivered to you" event read as a fact** is a genuine semantic error.
- **R is worse than X on maintained state:** in this setup, full-history readout is a bottleneck that per-record extraction plus the engine avoids. Most of R's loss is the over-cautious "unknown" seen across this whole series.
- **Next research question (not started):** whether this pipeline transfers to new action compositions or context families, and whether extraction holds up on less templated prose than the pilot's semi-structured record lines.

## Not supported
- Any claim about learned dynamics, temporal memory or weights.
- Equal-cost comparisons.
- Transfer beyond these two record and action templates.
- Generalising from cells of 2 histories per pattern and domain.
- Treating the engine's guarantees as model capability.

## Artifacts
- **Analysis:** `analysis-hist/ANALYSIS.json`, `TABLES.md`, `records.jsonl` (raw reply, normalised record, comparison, engine accept/reason) and `checkpoints.jsonl`; smoke in `analysis-histsmoke/`.
- **Raw replies:** `stages/{smoke,main}/calls/`.
- **Inputs:** `data/`.
- **Source:** `<DREAM_HOME>/Code/DREAM-project-1.8.1-history-interpretation-20261105`.
- **Re-score:** `python3 -B scripts/hist_analyze.py --hub HUB --set hist --stage main`.
