# Decategorization Trip Study: Protocol V1.2.3

David Cook, October 30, 2026. Development-only exploratory protocol.

**Status:** On 1.2.0, the vector qualification passed and an 18-answer smoke run completed (`Runs/decategorization-20261030-105051`).
- Answers ran about 1,000 tokens.
- No trip finished its come-down under the 1.2.0 lengths, which is why V1.2.1 shortened them.
- At λ = 0.10, steered single-pass answers often broke the KEEPERS format: 5 of 8, versus 0 of 4 unsteered.
- The sober pass produced valid answers in all 6 two-step cases.

These are wiring checks, not results.

Dose finding on 1.2.1 used constant λ from −0.15 to 0.25 on 3 objects, one seed (`Runs/decategorization-20261030-110540`):
- Ideas moved from practical and engineering-minded (negative λ) to cosmic, mystical and metaphorical (+0.20 to +0.25).
- Evolutionary "it once was" speculation appeared at the top doses.
- Prose stayed fluent throughout.
- Structural intrusions (the word "imagine" replacing a JSON key) grew with dose.

The high-dose sweep on 1.2.2 used constant λ 0, 0.30, 0.40 and 0.50 on the same 3 objects, one seed (`Runs/decategorization-20261030-113050`):
- **0.30:** strange but still testable ideas (for example, a heart descended from a two-chambered pump).
- **0.40:** dreamlike and poetic; falsifiers became circular, but kernels remained (for example, a spider dissolving its web to rebuild it).
- **0.50:** the heart notebook looped on "Maybe it's not just…" phrasing (4-gram repetition 0.263); ideas centred on imagination itself.

**Fixed for the pilot (V1.2.3):** trip peak 0.40, chosen by David as just past the edge where single-pass answers stop being testable, so the sober arms have kernels to recover. The constant, rigid and random arms use the same magnitude. The rigid side has only been observed to −0.15.

**Pilot (1.2.3, `Runs/decategorization-20261030-130112`):**
- The sober pass rescued all broken answers, but rarely developed ideas.
- The rigid trip at −0.40 produced repetitive textbook loops.
- A random direction of the same size left the ideas ordinary.

V1.3.0 replaces the weak second step with the explore ladder (document 18).

## Question

Does temporarily loosening a language model's sense of "what kind of thing this is" help it produce ideas worth exploring, especially when the loosening comes on smoothly and wears off smoothly within one answer, or when a separate sober pass reinterprets the loose output?

David's hypothesis: under strong interference much of the output looks like nonsense, but some of it hides a real insight. For example, "the heart could have a second aortic valve as a backup" might point toward how the heart evolved. A clearer pass can recover those kernels if it is told to keep strange ideas instead of rejecting them. This is a hypothesis, not a finding.

## What "decategorization" means here

Two linked effects:

1. **Loosening a category:** the model treats an object less as a typical member of its category ("a heart is an organ") and more as a detachable pattern ("a rhythmic pressure source that anything moving fluid could have").
2. **Mixing distant categories:** ideas from far-apart domains come together.

Operationally, the dial is a direction in the model's residual stream. It is the mean last-token activation for "decategorized" prompts minus the mean for "categorical" prompts at layer −8, unit-normalized (`data/decategorization_prompts.json`).
- **Build set:** 36 matched pairs in three wording families.
- **Held-out set:** 12 pairs in a fourth wording, using different objects.
- No task object appears in either set.

The intervention is the existing DREAM rule `h_prime = h + lambda_t * norm(h) * v`. Positive λ pushes toward decategorized; **negative λ pushes toward rigid, box-bound description**. The rigid arm tests whether the dial really controls category looseness: if looser helps and more rigid hurts, the dial means what we think.

**Qualification before any study run** (`build_steering_vector.py --direction decategorization --qualify-full`):
- The interleaved split-half cosine must be > 0.
- At least three quarters of held-out pairs must align positively.
- The report also gives the cosine with the V1.1 divergent ("be creative") direction. A high value would mean the new dial is mostly the old one under a new name.
- This is a consistency check only, not evidence of creativity.

## The trip curve

The dose is measured in **generated tokens**, not as a share of the answer cap (the V1.1 curve stretched with the cap):

- **Come-up:** raised-cosine rise from 0 to the peak over `onset_tokens` (default 100).
- **Plateau:** hold at the peak for `plateau_tokens` (default 350).
- **Come-down:** raised-cosine fall to 0 over `comedown_tokens` (default 300; the dose is back to zero at token 750), then zero for the rest of the answer.

Raised-cosine ramps start and end with zero slope, so the change is gentle at every transition. Each record saves the applied λ for every generated token, plus `comedown_complete`. That flag is false if the model stopped writing before the dose returned to zero. The psychedelic language describes the curve shape only. It makes no claim about model experience, and token entropy is not neural entropy (see document 02).

## Task: concrete objects

Twelve development objects (`data/objects-development.jsonl`): heart, bird bone, tree roots, eye, octopus arm, kidney, spider web, beehive, coral reef, hand, suspension bridge, wheel.

Every arm gets the **same prompt**. The model writes a free exploration notebook, then a `KEEPERS:` line followed by five ideas. Each idea gives the idea, its reasoning, and an observation or experiment that would prove it wrong. The falsification field is what lets later review separate a kernel of insight from fluent nonsense.

Reasoning ("thinking") mode is off in every arm. Sampling is temperature 0.6, top-p 0.95, top-k 20 (except the anneal arm), seed 11, with a 3,072-token cap.

## Arms

| Arm | Inside the model while writing | Sober pass |
|---|---|---|
| baseline | nothing | – |
| constant | decategorization at peak, flat | – |
| **trip** | decategorization, smooth up–plateau–down | – |
| rigid_trip | same curve, negative sign | – |
| two_step_control | nothing | yes |
| **two_step_constant** | flat peak | yes |
| **trip_then_sober** | smooth trip | yes |
| temperature_anneal | nothing; sampling temperature glides 1.3 → 0.6 over 750 tokens | – |
| random_trip | smooth trip along a norm-matched random direction | – |
| divergent_trip (optional) | smooth trip along the V1.1 divergent direction | – |

The **sober pass** is a fresh call with no steering. It receives the full raw stage-1 text as JSON-encoded untrusted data, so even a broken notebook can be salvaged. It labels every idea it finds:
- **KEEP**
- **DEVELOP**
- **PARK:** strange and unclear but with a kernel, kept with a note on what to explore
- **DROP:** incoherent with nothing to salvage

Oddness alone is never grounds to drop. It then returns five developed ideas and the parked list.

What the controls separate:
- **Zero-dose two-step control:** whether the extra sober call alone explains a two-step gain.
- **Temperature anneal:** whether early randomness alone explains a trip gain (cf. exploratory annealed decoding).
- **Random-direction trip:** whether any same-size perturbation would do.

## Order of work (each step needs David's go-ahead)

1. **Qualify the vectors** (no generation).
2. **Smoke:** 2 objects × 9 arms = 18 records. Checks wiring, format and length.
3. **Dose finding:** constant λ ∈ {−0.15, 0, 0.05, 0.1, 0.15, 0.2, 0.25} on 3 objects, 21 records. Read coherence, format failures and repetition. Set the trip peak just past the point where coherence starts to break: the "nonsense edge" David wants to explore. Also set the trip lengths from the observed answer lengths so most trips complete their come-down. The three dose-finding objects are in the pilot too; report them separately.
4. **Pilot:** 12 objects × 9 arms = 108 records, plus 36 sober calls. Run it only after the peak is fixed and recorded.

## Review

`scripts/export_decat_review.py RUN_DIR` writes three shuffled pools with unlinked IDs and a private key:

1. **Final ideas:** the primary pool. All arms have identical fields.
2. **Raw notebooks.**
3. **Parked ideas.** These reveal sober arms, so they are opened only after primary ratings are committed.

**Review steps:**
- Claude rates each idea: novelty 1–5, plausibility 1–5, worth exploring (yes/no), and nonsense with a kernel (yes/no), plus notes. The review is blind to arm.
- Claude commits a hash of the ratings before opening the key, as in V1.1.4.
- Answers without valid ideas are counted per arm, never hidden.

**Recorded diagnostics, not decisive:**
- format validity;
- repetition rate;
- come-down completion;
- PARK fraction;
- tokens.

Coherence as perplexity under the unsteered model is computed at analysis time, not in the run, to protect GPU memory.

These are AI-assisted subjective ratings on a small development set: exploratory evidence only. A promising signal would justify human expert review of the top ideas and a predeclared larger study.

## Prior work this builds on

Full entries are in document 12:
- Time-varying control: dynamic activation composition (Scalena et al. 2024) and exploratory annealed decoding (2025). No prior work found used a pharmacokinetic rise–plateau–fall within one generation.
- Divergent-then-convergent generation (CreativeDC, 2025).
- Category geometry (Park et al., ICLR 2025) and literal/figurative steering directions (2026).
- Human psychedelic creativity: Wießner et al. 2022 found more novelty and less usefulness under LSD, which motivates a sober pass.
- Separating creative synthesis from fabrication ("Beyond Noise", ACL 2026).
- Judging novelty and plausibility of hypotheses (HypoBench, 2025).

## Safeguards

The study follows the existing operating decisions:
- offline worker, frozen weights, no adapter;
- every generation (both passes) goes through the observed `generate` call, so the welfare pause sees every answer;
- memory and GPU reserves;
- no automatic resume.

Development split only. No model promotion, training or publication is authorized by this protocol.
