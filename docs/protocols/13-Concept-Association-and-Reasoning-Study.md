# Five Related Things: Concept Associations and Reasoning

Revision 1.1.4, October 30, 2026. Project lead: David Cook. Implementation assistance: Codex. Development-only exploratory protocol, specified before this comparison's model calls. This is not a public preregistration.

## Question and expectation

Does enabling Qwen3-8B's reasoning mode improve the quality of five related examples or applications of a concept? David expects that it will. That expectation is a directional hypothesis, not a finding or a reason to favor one condition during review.

This first comparison examines retrieval and association using existing conceptual knowledge. It does not measure newly learned adapter knowledge. The [concept-learning protocol](15-Concept-Learning-Protocol.md) separates that later DREAM 2 question.

## Task

Six development concepts span systems, biology, social exchange and mathematics: feedback, bottleneck, redundancy, threshold, reciprocity and symmetry. Each has a short supplied definition. Prompts are authored synthetic tasks, with no personal or customer data.

For each concept the model returns exactly five distinct examples or applications. Each item contains a name and one short sentence explaining its specific relationship to the definition. Both conditions receive the same request for at least two less obvious but accurate connections. The final answer is a JSON object containing an associations list; every element has only item and connection fields.

This is a direct association task, not the legacy anchor/explore/integrate pipeline. Reasoning text is retained for audit and the welfare pause, but is excluded from the quality-rating material. The definition and final answer are what the reviewer judges.

## Matched comparison

| Quantity | Fixed choice |
|---|---|
| Model | Qwen3-8B at the run's immutable revision and verified local manifest |
| Primary conditions | Reasoning disabled versus enabled, both with zero steering |
| Concepts | The same six definitions and questions |
| Generation seed | 11, paired within concept |
| Sampling | Temperature 0.6, top-p 0.95, top-k 20 in both modes |
| Input / output caps | 2,048 input tokens / 4,096 generated tokens in both modes |
| Final answers | Exactly five association objects per response |
| Order | A fixed shuffled order interleaves modes and concepts |
| Context | A fresh generation context/cache for every response |
| Parameter changes | None; all model parameters remain frozen |
| Primary pilot size | Six concepts times two modes: 12 responses |

Equal caps do not imply equal actual computation. The reasoning-on response includes its reasoning within the same total generated-token cap. Report reasoning presence, realized output tokens, length stops and resource/runtime measurements beside quality. This comparison estimates the effect of the mode under the stated budget; it does not isolate reasoning from additional computation or guarantee the effect of another budget.

Qwen recommends sampled decoding for this model's thinking mode and warns against greedy decoding. Its [official model card](https://huggingface.co/Qwen/Qwen3-8B) and [versioned quickstart](https://qwen.readthedocs.io/en/v3.0/getting_started/quickstart.html) inform the settings. The exact settings remain fixed across the two arms rather than using different recommended settings for each.

## Qualification and failures

The copied offline controller first exercises acknowledgment, answer/reasoning pause fixtures, timeout, resource stopping and containment. Current ML-inclusive tests must pass without skips. Plan-only must enforce both selected concept count and total response count.

A four-response smoke check uses feedback and symmetry in both modes. All four must finish at EOS, yield a complete final answer and pass the exact-five schema. This is format/runtime qualification, not a creativity result. These development observations are not pooled with the later 12-response pilot as extra independent evidence.

An incomplete or invalid answer is preserved and stops the queue for review. It is not passed into another stage. If a pilot is interrupted, report the incomplete pairing and all attempted cells; do not silently exclude the difficult condition or resume automatically. Any revised cap or prompt receives an explicit amendment and a distinct run. No final-test set is opened by these stages.

The primary pilot has a 3,600-second cooperative budget; smoke has 1,200 seconds. Each also has an external stop at its budget plus 60 seconds. The controller carries the previously qualified RAM, GPU and record limits, disables network access, restricts writes and inhibits desktop sleep for the bounded queue. A welfare trigger pauses and preserves the record for David. The pattern detector has limited coverage; absence of a trigger is not a welfare finding.

## Outcomes fixed before collection

**Primary outcome: relevance-gated useful association quality, 0 to 10 per response.** Score each of the five items:

- 0: wrong or unsupported relationship, missing explanation, or a substantive duplicate of an earlier credited item.
- 1: accurate, meaningfully distinct relationship, but familiar or generic, or with little explanatory value.
- 2: accurate, meaningfully distinct, less obvious relationship whose explanation identifies a concrete shared mechanism, structure or useful application.

Sum the five item scores. Mere unusual vocabulary, length, confident phrasing and an unsupported analogy do not earn the second point. A complete response that fails the five-item format receives zero for the fixed-format primary outcome, with the exact failure retained. Uncertain factual relationships require verification before a semantic score is finalized; leave ratings pending instead of guessing certainty.

**Secondary outcomes:** valid distinct item count (0–5), breadth of distinct contexts/domains (0–5), format completion, token cost, and a record of doubtful or repeated relationships. These diagnose whether reasoning improves relevance, variety or only verbosity. Do not pick a favorable secondary measure after seeing results and call it the primary result.

The deterministic parser checks structure and exact duplicate labels only. It cannot establish semantic accuracy, distinctness or originality. [Conditional divergent-association research](https://arxiv.org/abs/2601.20546) motivates retaining appropriateness alongside novelty. [Earlier LLM association research](https://aclanthology.org/2023.findings-emnlp.858/) is a related precedent, not validation of this six-concept task.

## Blinding and analysis

Export final answers in shuffled order with opaque review IDs. The reviewer sees the concept and definition but not mode, seed, thinking text, runtime or the private condition key. Score before joining the key. Style may partly reveal a condition; report that limitation. For a confirmatory study, use multiple independent human raters, fixed examples for the rubric and adjudication/agreement rules. A single AI-assisted review of this pilot is preliminary and must be labeled as such.

The analysis unit is the concept. Five items within an answer and repeated seeds are nested observations, not five or more independent experiments. Pair mode scores within each concept and report all six differences, their mean, and costs. With one seed and six deliberately chosen development concepts, do not claim population significance, broad model superiority or replicated creativity gains.

Optional steering and higher-temperature arms live in a separate concepts-steering configuration. They are secondary to the first reasoning comparison. Both reasoning modes use the same pinned vector; concept steering is constant over generated tokens, so raising the answer cap does not silently stretch a ramp. Validate the direction's intended effect independently before interpreting it as exploration-specific.

## Reproduction and scope

Use configs/concepts-smoke.json and configs/concepts-pilot.json. scripts/prepare_concept_run.py creates a new disposable hub from a supplied controller template and local model identity. scripts/run_concept_queue.py qualifies and runs that bounded hub without automatic resume. scripts/summarize_concepts.py exports structural summaries, an unfilled blinded rating sheet and a separate private condition key outside the original records.

Both focused research archives contain the same shared implementation and this protocol. No model weights, prior private conversations, automatic model promotion, public registration or publication are included.
