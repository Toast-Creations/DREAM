# DREAM 2 Research Paper

## V1.1.4 amendment: conceptual retention and reasoning

The next conceptual-learning question is whether a reversible adapter can retain a newly taught concept and produce five valid new applications after the definition, examples, cache and exploratory steering are removed. Reasoning at evaluation and steering during learning must be crossed rather than conflated. Ordinary-learning controls, exposed-example recall, fresh single cases and novel combinations establish different abilities.

The current runnable concept experiment freezes parameters and compares reasoning modes on familiar concepts. It supplies no concept-adapter learning evidence. A concrete [concept-learning protocol](15-Concept-Learning-Protocol.md) specifies the later data contract, memory checks, five-item validity/distinctness scoring and independent evaluation required before that extension can run.

The older Qwen3 pilots showed poor context-free transfer. Decreasing supervised loss with rules supplied did not establish memorization. Their few composition successes depended on a repeated question whose answer equaled its input. The new numeric fixtures replace that duplicate, vary inputs and prevent copy-input/sign-flip credit; outcomes using the changed fixtures belong to a new protocol. Reasoning-format mismatch and greedy decoding also limit the older thinking-on comparison. See [the review](14-Qwen3-Pilot-Review-and-Amendments.md).

No positive or negative general conclusion about conceptual learning follows yet. The numeric adapter method below remains implemented; the five-application learning extension remains proposed. David's expectation that reasoning helps is recorded for the new inference comparison, with [its results](16-Concept-Comparison-Results.md) kept separate from retention claims.

David Cook  
State Dependent Exploration During Reversible Adapter Learning  
Version 1.1.1 computational research proposal - citation revision, October 29, 2026

## Abstract

DREAM 2 tests whether exploration-oriented activation steering during verified, supervised adapter learning changes held-out compositional transfer after the intervention and exposure context are removed. A frozen foundation model receives trainable LoRA A and B matrices. Steering strength and learning-rate multiplier vary independently. A procedural integer benchmark supplies deterministic labels, balanced truth probes, unrelated anchors, scope questions, and lookup controls. V1.1 corrects a critical causal-loss indexing error in the original implementation and distinguishes a redundant preexposure control from a meaningful delayed-learning mechanism. The proposal does not claim to originate training-time representation interventions and reports no effectiveness result.

## Related work and attribution

The adapter machinery is [LoRA (Hu et al.)](https://arxiv.org/abs/2106.09685). [Hu et al. on test-time learning](https://arxiv.org/abs/2505.20633) and [Tandon et al. on context-to-weight training](https://arxiv.org/abs/2512.23675) establish ordinary adaptation precedents. [NEFTune](https://arxiv.org/abs/2310.05914) already uses temporary embedding noise during training; structured exploration must be distinguished from regularization. [ReFT](https://arxiv.org/abs/2404.03592) learns representation interventions on frozen base models.

Temporary training-time intervention is also established in [Zhou et al. on security vectors](https://aclanthology.org/2024.findings-acl.611/), [Casademunt et al. on CAFT](https://arxiv.org/abs/2507.16795), and [Chen et al. on persona vectors](https://arxiv.org/abs/2507.21509). [Adila et al.](https://proceedings.mlr.press/v306/adila26a.html) train in activation and weight spaces jointly. [Guan et al.](https://aclanthology.org/2026.findings-emnlp.1991/) study temporal compensation and progressive intervention intensity. [Backpropamine](https://arxiv.org/abs/2002.10585) provides an earlier precedent for neuromodulated plasticity in a different architecture.

The narrower proposed contribution is a controlled test of exploration-oriented intervention during reversible learning on held-out composition, with context removal, scope checks, ordinary-learning baselines, and update diagnostics. Persistence, coupling, or a changing schedule alone is not claimed as new. A benefit can also arise from compensatory adaptation or regularization.

For a future identity or goal-conditioning study, score persistent behavior after removing the goal prompt, hook, and old cache. Persona-vector results warn that steering toward a trait during learning can reduce later acquisition. The direction of any imprinting effect is an empirical question, and behavioral stability would not demonstrate subjective identity. This extension is not implemented by the present citation revision.

See the [source catalog](12-References-and-Method-Credits.md) and [contribution boundaries](07-Literature-and-Novelty.md).

## Parameterization and computational hypothesis

For an adapted projection, the effective weight is:

`W_effective = W_frozen + (alpha / rank) * B * A`

Only the low-rank A and B matrices are trainable. The activation intervention uses the normalized direction and relative-state norm defined for DREAM. An optimizer changes adapter parameters using a reference learning rate multiplied by eta.

A steered state can alter the gradient because the loss is evaluated through different intermediate activations. However, the resulting update may compensate for the intervention, suppress the steered feature, change gradient magnitude, or impair learning. Useful exploration is one hypothesis among these alternatives.

For moderate lambda and eta, the target prediction is improved compositional transfer beyond ordinary adaptation at the same eta. A formal difference-in-differences contrast is:

`I = Q(lambda, eta) - Q(0, eta) - Q(lambda, 0) + Q(0, 0)`

In a stateless model evaluated after context and steering removal, both eta-zero arms are expected to match closely. Their role is to verify absence of unintended persistent state. They are not independent demonstrations that exploration has become memory.

## Correcting the original intervention

Autoregressive loss scores a hidden position t against the target token at t plus one. The final hidden position does not predict an available next-token label. V0.1 changed only that final position during teacher-forced training, so the intended perturbation could not affect the scored objective under standard causal decoding.

V1.1 creates explicit target-only labels and derives the steering mask from shifted supervision. It includes the last prompt position when it predicts the first answer token, includes answer positions that predict subsequent supervised tokens and EOS, excludes padding, and never selects the unscored final position.

The additive perturbation remains in the autograd computation. Its norm scale is detached; the target activation is not. The model runs in evaluation mode during gradient-enabled updates to disable dropout and isolate the intervention. This is intentional; evaluation mode does not disable gradients.

## Experience and truth

Each micro-world has randomly named deterministic operators and separate arbitrary lookup facts. Exposure examples contain verified rules or facts and typed answers. The loss covers the assistant target and EOS, not the prompt text.

An executable oracle recomputes all answers and canonical question text. Modified labels, rule contexts, and question/oracle disagreements are rejected. Composition queries are checked against exposure signatures. Invented vocabulary does not prove that underlying arithmetic is unknown to pretraining; the experiment primarily tests acquisition and use of novel symbol-to-rule bindings.

World identifiers, vocabularies, rule mappings, and inputs are separated across development, validation, and test splits. These are independent adaptation episodes: a new world receives its own adapter state. A final-test world is still exposed through its training examples; only its evaluation combinations are held out.

## Factorial and additional controls

The factorial varies lambda and eta with a zero level for each. The four qualitative cases are frozen, exploration-only exposure, ordinary plasticity, and coupled steering with plasticity.

Every condition also receives a first forward-only exposure phase. In the preexposure control that first phase is steered and the second learning phase is unsteered. In other conditions the first phase is unsteered. This matches forward-exposure count and update count.

No cache, generated interpretation, or activation summary is retained between phases. Consequently the preexposure control is expected to resemble ordinary learning. It is not a delayed-plasticity experiment. Testing a delayed effect would require a specified persistent mediator and additional controls; that extension is not implemented.

A high-eta ordinary-learning arm tests whether a stronger unsteered learning rate reproduces the benefit. It does not alone establish that gradient direction matters. Pre-clipping gradient norms and adapter displacement are recorded. V1.1 does not implement exact gradient-norm or update-displacement matching. If that analysis is required, preregister and implement it as a separate experiment; AdamW normalization makes naive gradient scaling especially difficult to interpret.

## Evaluation after the window

Hooks are removed and no optimizer steps occur during evaluation. Fresh prompts contain the world identifier and question without the exposure examples or rule list. The typed scorer evaluates direct application, paraphrase, composition, balanced true/false rule probes, domain scope, unrelated arithmetic anchors, and lookup memory.

The contradiction and scope categories measure different things. Balanced rule questions prevent an always-no shortcut; scope questions intentionally require rejecting universal extension of invented names. Unrelated arithmetic anchors cover a narrow capability slice and cannot establish broad alignment or absence of forgetting.

Each adapter begins from an identical seeded snapshot within its paired conditions. Different seeds construct new initialized adapters. A reversible trial restores the snapshot on success and on exceptions. Base hashes and parameter allowlists detect unintended changes.

## Consolidation and persistence

All shipped configurations disable promotion. A candidate may be saved only under an explicit validation-phase policy with complete finite metrics, sufficient counts, acceptable error and regression, and no invalid output formats.

A KEEP_CANDIDATE outcome means a quarantined checkpoint is eligible for a fresh-process reload check. It never means that a model is safe to deploy, a base merge is approved, or a scientific result is confirmed. The reload script checks model/data/adapter identities and repeats the validation comparison without steering.

The repeated validation check verifies serialization and repeatability. It is not a new independent test set. Final scientific claims require the untouched preregistered final-test episodes and suitable statistical uncertainty.

## Failure criteria

The hypothesis remains unsupported if ordinary adaptation matches coupled learning; only memorization improves; a stronger eta explains the difference; results depend on invalid scoring or leaked examples; scope or anchor performance deteriorates beyond the chosen limits; or the effect does not replicate.

A failure after correcting the intervention is informative. A null result from the original unscored-token hook would primarily reveal an implementation defect. Related work on preventative steering, concept ablation fine-tuning, security vectors, and joint adaptation constrains the novelty claim.
