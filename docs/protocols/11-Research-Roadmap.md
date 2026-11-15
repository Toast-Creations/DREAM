# Research Roadmap

**V1.1.4 update — October 30, 2026.** The immediate executable addition is the direct concept reasoning comparison in document 13. Its results and costs inform a later concept-learning implementation described in document 15. Preserve negative, incomplete and ceiling-limited outcomes; do not adopt more elaborate training until the basic learning and scoring checks work.

The original motivation reaches beyond a single steering direction. This roadmap preserves those questions while separating implemented V1.1 features from future studies.

## Mechanism before scale

First verify that steering changes scored activations and adapter gradients on a tiny model. Then show ordinary adaptation learns the procedural mappings. Only after those checks should a local open-weight pilot compare useful transfer across doses. More compute cannot compensate for an unscored intervention or an invalid answer parser.

## Richer representations of exploration

The present contrast direction can capture style, verbosity, or literal prompt content. Future work can compare prompt-matched directions, random unit vectors, reversed directions, orthogonal controls, sparse feature interventions, and learned low-dimensional subspaces. Random and reversed-direction controls are not implemented in the V1.1 runner and require explicit additions.

A manipulation check should measure behavior on held-out tasks and identify whether structural alternatives increase while facts and constraints remain intact. A larger hidden-state norm or more varied words is not sufficient evidence of exploration.

## Temporal and closed-loop control

DREAM currently uses a planned rise-hold-fall generation schedule. A future controller might adjust intervention strength using a measured exploration state, repetition, constraint violation, or uncertainty. Such a controller changes the experimental treatment and needs a fixed, validated signal and matched adaptive controls.

DREAM 2 uses constant coefficients within an exposure episode. Reopening a plasticity window after exploration is not meaningful in a stateless decoder unless a specified mediator survives. Candidate mediators include verified intermediate hypotheses, explicit external memory, recurrent state, or learned activation summaries. Each would introduce another variable and a separate contamination risk.

## Gradient direction and compensatory adaptation

Logging gradient norms is only an initial diagnostic. A mechanistic study should compare full gradient directions, preconditioned optimizer steps, layerwise update structure, and actual parameter displacement. Perturbation-magnitude matching and update-count matching answer different questions.

Steering during learning may induce a compensatory parameter change that opposes the injected feature. That outcome could explain a negative or reversed effect without invoking a biological analogy. Include this alternative before collecting data rather than retrofitting it afterward.

## Learning environments and consolidation

The integer worlds isolate new operator bindings, not all forms of conceptual learning. Future environments could test relational graphs, strings, programs with exact interpreters, or verified interactive feedback. New families need their own executable oracle and train/test separation.

Selective replay, adapter composition, longer retention intervals, and repeated episodes could test continual-learning questions. These extensions may increase forgetting and contamination. Do not treat a validated adapter for one world as general memory or automatically merge it into the base model.

## Recurring conceptual motifs

The original computational-archetype idea asks whether recurring structural motifs emerge across tasks and models. A careful study would compare unsteered baselines, multiple languages, unrelated model families, extraction prompts, and shared pretraining artifacts. Repeated motifs may reflect common training data or the benchmark's own structure.

Use descriptive language such as recurring representational motif. Cross-model recurrence alone is not evidence of a collective mind, an external realm, or privileged truth.

## Milestones and evidence

Proceed from verified wiring, to learnable synthetic tasks, to a paired exploratory signal, to preregistered replication, to mechanism analysis. If a simpler control matches the method or reliability deteriorates, record the negative result and stop scaling that configuration.

Each new step should state its hypothesis, closest prior work, additional safeguards, compute budget, failure rule, and contribution record. All items in this roadmap are proposed future work unless explicitly identified as part of the tested source release.

## Literature-grounded extensions recorded October 29, 2026

The following are proposed studies, not new runner features. Attention-temperature modulation has a direct predecessor in Yu et al.; compare it with residual steering and matched random perturbations rather than treating contextual mixing as a new mechanism. Fixed embeddings do not guarantee unchanged contextual word meaning.

Bell, plateau, pulsed, and long-recovery schedules should distinguish generation progress from optimizer steps. Guan et al. already study temporal steering and progressive intensity. Match relevant exposure, generated-token budgets, update counts, and reflection computation. Test whether a schedule changes useful idea survival or post-removal composition beyond ordinary adaptation and NEFTune-style noise. Waiting without computation is not reflection in a stateless transformer.

Internal-state studies should track comparable held-out probes, intervention delivery, concept/feature trajectories, and actual adapter updates before, during, and after the window. Test predictive signals with causal interventions, not only visual clustering. Dictionary-learning and persona-monitoring work are prior instrumentation methods.

Goal-conditioning needs prompt-only, learning-only, intervention-only, and coupled controls with fresh-context evaluation. Compensation can oppose the intervention. Persona stability is a behavioral result. Credits and limits are in the [source catalog](12-References-and-Method-Credits.md).
