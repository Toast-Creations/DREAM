# Concept Reasoning Comparison: Initial Results

Version 1.1.4, October 30, 2026. Project lead: David Cook. Execution and preliminary review assistance: Codex. The fixed development protocol is [document 13](13-Concept-Association-and-Reasoning-Study.md).

**Result: reasoning changed the associations, but this small pilot did not show a clear overall quality advantage.** The preliminary primary score was 5.17/10 with reasoning versus 5.00/10 without. Two concepts favored reasoning, two favored reasoning off, and two tied. These are one AI-assisted reviewer's subjective scores, saved before the condition key was opened. No significance or general model-superiority claim is made.

## What ran

Qwen3-8B at immutable revision b968826d9c46dd6066d109eabc6255188de91218 ran on the local RTX 3090. The first attempt stopped before model loading because available host memory was just below the existing 6 GiB reserve. The reserve was preserved. A fresh run began after available memory recovered.

The copied offline worker passed 50 tests without skips and the acknowledgment, answer/reasoning pause, timeout, resource-stop, plan and containment checks. Four smoke responses completed successfully. The separate primary pilot completed all 12 responses: six concepts in both reasoning modes, seed 11, zero steering, temperature 0.6, top-p 0.95, top-k 20, and a common 4,096-token cap.

All 12 pilot answers finished at EOS and contained five complete association objects. No response hit the length cap. All six reasoning-on responses contained reasoning text; none of the six reasoning-off responses did. No non-fixture welfare trigger was detected, and the worker processes exited. The scoped sleep inhibitor was released. No adapter was created and no parameter learning occurred.

## Preliminary blinded review

The reviewer saw only shuffled final answers, concepts and definitions. Per-item ratings and notes were committed before opening the condition key; the recorded ratings hash is 14479b279e4209f8150467c416dcbbfb86abdd3b559899fc97452732c48f8a55. Output style may partly reveal a mode, and the reviewer also implemented the study. This is preliminary AI-assisted assessment, with no independent human raters or agreement estimate.

Each item scored 0 for an unsupported/incorrect/duplicate connection, 1 for a valid familiar connection, or 2 for a valid less-obvious informative connection. Semantic distinctness, breadth and novelty remain judgment-dependent. Some illustrative examples receive credit with qualifications. Under-explained connections were not credited; this does not mean no valid connection could be constructed.

| Concept | Reasoning off, /10 | Reasoning on, /10 | On minus off |
|---|---:|---:|---:|
| Bottleneck | 7 | 6 | -1 |
| Feedback | 5 | 6 | +1 |
| Reciprocity | 5 | 5 | +0 |
| Redundancy | 3 | 5 | +2 |
| Symmetry | 5 | 4 | -1 |
| Threshold | 5 | 5 | +0 |
| Mean | 5.00 | 5.17 | +0.17 |

The review credited 28 of 30 associations without reasoning and 24 of 30 with reasoning as sufficiently supported and distinct. These are review judgments, not independently established accuracy measurements. Reasoning sometimes earned extra quality credit for less-obvious useful connections, while also attempting more questionable ones. The five items are nested within each of six concepts; they are not 30 independent experiments per arm.

## Examples and factual checks

- Without reasoning, the redundancy answer treated the heart's two ventricles as substitutes. With reasoning, that example was replaced by alternative blood-flow pathways. The ventricles normally serve different circulation circuits: the right pumps toward the lungs and the left toward the body. [NHLBI anatomy and blood flow](https://www.nhlbi.nih.gov/health/heart/blood-flow).
- With reasoning, the symmetry answer linked time translation to energy conservation but incorrectly explained it as preserving the system's state over time. The relevant invariance is in the dynamics/laws, with a conserved quantity; it does not require a motionless state. [David Tong's mechanics notes](https://www.damtp.cam.ac.uk/user/dt281/dynamics/dynhtml/S2.html).
- The same answer claimed that using a shared encryption key preserves data integrity. Symmetric encryption alone does not guarantee integrity, and the response did not identify the invariant required by the supplied concept definition. [NIST confidentiality modes](https://csrc.nist.gov/pubs/sp/800/38/a/final) and [authenticated-encryption specification](https://csrc.nist.gov/pubs/sp/800/38/d/final).
- The reasoning-on threshold answer described lactate threshold as an aerobic-to-anaerobic switch. That binary explanation is misleading; lactate production also occurs under aerobic conditions. [Research discussion by George A. Brooks](https://pmc.ncbi.nlm.nih.gov/articles/PMC9124087/).

Other disputed examples, including legal fallback guarantees and an ecological feedback claim, were not credited because their explanations did not establish the asserted relationship. The full item-level notes are included; a fresh independent reviewer may reasonably disagree with some judgments.

## Cost and execution

The six reasoning-on responses used 5,487 generated tokens in total, including thinking. The six reasoning-off responses used 888. That is approximately 6.18 times as many generated tokens under the same cap. It is a token-cost comparison, not an exact FLOP or energy measurement.

The four-response smoke stage took about 126 seconds and the 12-response pilot about 247 seconds, including model startup within each supervised stage. Sampled peak use stayed below about 4.35 GB host RAM and 17.08 GB GPU memory, in decimal units. These are sampled measurements, not guaranteed instantaneous maxima.

## Interpretation and next decision

David's expectation that reasoning would help received mixed preliminary evidence: a small average quality difference, some better connections, more uncredited associations, and much greater token use. This result neither establishes a benefit nor rules one out. The sample uses six curated development concepts, one seed, a subjective rubric and one AI-assisted reviewer. Some item judgments and the cost budget could materially change the interpretation.

The next useful assessment is an independent blinded review of these same final answers, followed by a predeclared broader concept set and repeated paired seeds if warranted. Avoid simply adding responses until a desired result appears. Steering-specific effects and new concept learning remain separate questions and were not tested by this zero-steering pilot.

## Included evidence

The [study evidence directory](../../results/concept-reasoning-20261030/README.md) contains all smoke and pilot trial copies, output text and reasoning, the original unfilled blinded export, committed item ratings, the later condition key, structural summaries, paired results and source/model identities. The original run directories remain separate and preserved. No public registration, model promotion or deployment occurred.
