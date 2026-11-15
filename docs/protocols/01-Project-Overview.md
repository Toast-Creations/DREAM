# Project Overview

**V1.1.4 update — October 30, 2026.** The current executable addition is the paired reasoning comparison in [document 13](13-Concept-Association-and-Reasoning-Study.md). Read [current checks](10-Implementation-and-Testing.md) and [results/status](16-Concept-Comparison-Results.md) for readiness; historical V1.1 descriptions below are retained as design background. New concept learning is proposed in document 15.

DREAM and DREAM 2 form a computational research program led by David Cook. V1.1 turns the original position papers into a more controlled experimental package while retaining their motivation: a model's usual operating regime may not be optimal for every stage of problem solving.

DREAM tests temporary exploratory inference followed by unsteered evaluation. DREAM 2 tests whether an exploratory representation during parameter updates changes what is retained in a reversible low-rank adapter. These are related but separate hypotheses. Success in one does not establish success in the other.

## Motivation and scope

A language model can represent many associations while rarely retrieving some of them under ordinary prompting. Activation steering changes intermediate representations without requiring a new foundation model. A temporary intervention might reveal useful alternatives, or it might merely change wording, inject noise, and reduce reliability.

The neuroscience analogy concerns flexibility, stability, and learning windows. It is inspiration for a computational intervention, not evidence that a transformer reproduces receptors, subjective experience, or a biological critical period. No human drug administration or human-participant experiment is part of this release.

## Questions that can be tested

DREAM asks whether steering improves the usefulness of final answers after an identical integration procedure, compared with zero steering and a matched temperature control.

DREAM 2 asks whether steering during supervised, target-only LoRA learning improves held-out compositional accuracy after the hook is removed. The strongest local comparison is a paired coupled-versus-unsteered adaptation comparison at the same learning multiplier, verified experience, and update count.

The broader claim that training-time representational state can influence learning already has precedents. This project's potential contribution lies in its exploration objective, specific comparisons, procedural benchmark, and reproducible evidence.

## V1.1 decisions

| Decision | Reason |
|---|---|
| Keep base parameters frozen | Restrict parameter changes to inspectable adapters |
| Use synthetic integer worlds | Provide executable truth and avoid pretraining factual recall as the sole outcome |
| Score complete typed answers | Prevent substring and yes/no-prefix false positives |
| Include an identical zero-dose DREAM pipeline | Separate steering from prompting and extra inference |
| Treat preexposure as a redundant-exposure control | No persistent first-phase state is carried into learning |
| Disable promotion in shipped pilots | Debugging evidence is insufficient for retaining a model for use |
| Require local models and content manifests | Remove automatic model downloading from experimental runs |
| Preserve raw stages and failures | Make conclusions auditable and reruns distinguishable |

## Current readiness

The local ML environment passed 50 tests without skips, including six tiny-model integration tests. The older Qwen3-8B pilots established execution with reversible adapters but did not establish useful transfer. The new concept comparison qualifies the exact model separately and records completion, cost and rating status in document 16.

The observed desktop has an RTX 3090 with 24 GB VRAM and limited host RAM. CUDA loading is direct to the GPU; available-memory checks and external worker limits still apply. An insufficient reserve stops the run before model loading.

This remains a research prototype. Current checks establish specific implementation behavior; they do not validate the concept task as a general creativity measure or establish an effectiveness result.

## Documentation revision 1.1.1

The October 29 revision updates prior-work credit, paper citations, bibliography, contribution boundaries, and proposed experiments. It preserves the commented V1.1 experiment logic. No model run, training result, additional schedule implementation, or successful ML integration check is implied. Start with the [literature comparison](07-Literature-and-Novelty.md) and [source catalog](12-References-and-Method-Credits.md) for the research context.
