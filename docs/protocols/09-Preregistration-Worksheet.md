# Preregistration Worksheet

**V1.1.4 update — October 30, 2026.** The six-concept reasoning study is a development-only exploratory pilot with its outcome and comparison fixed in [document 13](13-Concept-Association-and-Reasoning-Study.md). David expects a positive reasoning effect. No public registration or confirmatory claim is implied. A later registered study must expand independent concepts, specify raters and justify sample size; five items are nested within one concept response.

Complete this worksheet before confirmatory data collection. An unfilled worksheet is not a preregistration. Record a submitted registration identifier only after it exists.

## Identity and contributions

Record study title, David Cook's role, any collaborators and their actual contributions, AI assistance, intended venue, disclosure route, and whether patent advice is needed before sharing. Identify the exact code release and source hash.

## Primary question

Choose DREAM, DREAM 2, or separate registered studies. State one primary effect or contrast, its direction if justified, and a minimum meaningful effect. Explain what would count as an informative null result.

## Models and execution

Record model ID, immutable revision, verified local manifest, tokenizer/chat-template version, hardware, dtype, dependency lock, device policy, and model license. State supported architecture and any deviation from a single CPU or CUDA device.

Record base-integrity checks, adapter module allowlist, LoRA rank and alpha, optimizer, learning rate, clipping, examples, update counts, experience order, and seed initialization policy. If FP16, quantization, sharding, or a different adapter is introduced, treat it as a new implementation requiring tests.

## Intervention

Record contrast prompts, extraction topics, pooling, vector hash, resolved layer, normalization, lambda values, schedule, supervised predictor mask, and manipulation checks. State how style or verbosity effects will be detected.

For DREAM 2 specify eta values, first-phase exposures, ordinary learning and high-eta controls. Do not describe a mediator-free preexposure pass as delayed plasticity.

## Benchmark and separation

Record generator version, independent seeds, world counts per split, training/evaluation sizes, token caps, benchmark hashes, and held-out composition rules. State how truth balance, unknowns, scope limits, anchors, and lookup controls are defined.

Explain which data can tune the design, which can select candidates, and which remain untouched until the final analysis. Define unit of independence and how repeated seeds are clustered.

## Outcomes and scoring

Choose primary and secondary outcomes separately. Record strict parser version, invalid-format treatment, reference oracle tests, human rubric, reviewer blinding, disagreement handling, and independent verification.

State whether gradient magnitude or update displacement matching is required. Those controls are not implemented merely by logging a norm.

## Analysis and compute

Declare paired contrasts, model specification, uncertainty method, multiple-comparison policy, bootstrap seed where applicable, sample size rationale, missing-data handling, and exclusions. Do not choose the best dose on final-test data.

Record actual tokens, calls, updates, and elapsed time to report. State whether comparisons are matched by caps, realized tokens, wall time, or another budget and justify it.

## Candidate policy

Shipped promotion is disabled. If enabling a validation gate, supply min_composition_gain, max_anchor_regression, max_error_rate, and min_items_per_category. Justify these values and the requirement of zero invalid formats. Define what happens to an invalid or insufficiently measured candidate.

State the fresh-process reload procedure and which independent evaluation remains afterward. A KEEP_CANDIDATE decision is not deployment authorization.

## Stop rules and deviations

Define numerical failure, OOM, timeout, context overflow, hash mismatch, rollback failure, and unexpected parameter changes as explicit outcomes. Record every interrupted run.

After data collection, preserve this original plan and append dated deviations. Do not rewrite the preregistration retrospectively to match observed results.

