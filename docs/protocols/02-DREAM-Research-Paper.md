# DREAM Research Paper

## V1.2.0 amendment: decategorization and the trip curve

David Cook proposes that creative exploration can be modulated by **decategorization**: temporarily loosening the model's sense of what kind of thing an object is, so that it can be redescribed as a detachable pattern and linked with distant domains. V1.2.0 adds a dedicated contrast direction for this. It is built from 36 matched "categorical" versus "decategorized" prompt pairs about concrete objects, with 12 differently worded held-out pairs for qualification. The intervention may be signed. Negative strength pushes toward rigid, box-bound description and serves as a check on what the dial controls.

Strength can now follow a **trip curve** in absolute generated tokens: a smooth raised-cosine come-up, a plateau, and a smooth come-down to zero. The aim is that the model explores loosely and then gradually narrows within one answer. A second design runs a separate unsteered sober pass that reinterprets the loose text and is instructed to keep strange ideas with a kernel (PARK) rather than reject oddness. The hypothesis is that some seemingly nonsensical output under strong interference contains ideas worth exploring. It is untested.

Controls separate these explanations from simpler ones:
- a zero-dose two-step control isolates the effect of the extra sober call;
- a hot-to-cold temperature schedule isolates decoding randomness;
- a norm-matched random direction on the same curve isolates any same-size perturbation.

Tasks are twelve concrete objects. Each answer gives five ideas with reasoning and a falsifying observation. Review is AI-assisted, blind to arm, with ratings committed before unblinding. See [document 17](17-Decategorization-Trip-Protocol.md). The psychedelic vocabulary describes the curve shape, not model experience. V1.2.0 contains no decategorization results.

## V1.1.4 amendment: concepts and reasoning

The next executable study is a direct association task: given a concept and a short definition, produce five distinct examples or applications and explain each connection. The six development concepts span feedback, bottlenecks, redundancy, thresholds, reciprocity and symmetry. The first primary contrast is reasoning enabled minus disabled at zero steering. Identical prompts, seed, sampled decoding and total generation caps isolate the mode comparison under a stated budget. Actual compute remains an outcome.

David Cook expects reasoning to improve association quality. The primary outcome is relevance-gated useful association quality: each item earns zero for an invalid/duplicate connection, one for a valid familiar connection, or two for a valid less-obvious and informative connection. Five scores sum to 0–10. Blind reviewers see final answers and definitions, not reasoning or condition keys. Breadth, validity and token cost are secondary. Schema checks alone never establish semantic quality.

This direct task is a distinct protocol from the legacy anchor/explore/integrate pipeline below. Its first comparison does not test whether activation steering helps. Optional steering/temperature arms are separate and preserve the reasoning factor. Six curated concepts and one generation seed support exploratory diagnostics, not a general creativity claim. Familiar concepts test access to existing knowledge; later concept learning requires a separate retention design.

The [fixed protocol](13-Concept-Association-and-Reasoning-Study.md), [older pilot limitations](14-Qwen3-Pilot-Review-and-Amendments.md) and [current results](16-Concept-Comparison-Results.md) govern this revision. [Earlier association evaluation](https://aclanthology.org/2023.findings-emnlp.858/) and [conditional novelty with appropriateness](https://arxiv.org/abs/2601.20546) are close precedents. This task and its rubric are not claimed as validated instruments.

David Cook  
Dynamic Relaxation and Entropic Associative Modulation  
Version 1.1.1 computational research proposal - citation revision, October 29, 2026

## Abstract

DREAM examines whether temporary intervention on a language model's intermediate activations can improve useful exploration before final evaluation under ordinary inference. A normalized contrast direction derived from divergent and convergent prompt pairs is added to selected residual-stream states during candidate generation. The intervention is then removed and the same model integrates the candidate material against the original task. The central comparison uses an identical two-stage pipeline at zero and nonzero intervention strengths. A temperature control passes through the same integration procedure. The intended outcome is useful, verified conceptual variation rather than unusual wording alone. No effectiveness result is reported.

## Related work and attribution

The additive contrast method builds on [Turner et al. (ActAdd)](https://arxiv.org/abs/2308.10248) and [Rimsky/Panickssery et al. (CAA)](https://arxiv.org/abs/2312.06681). [Olson et al.](https://arxiv.org/abs/2412.06060) already extract creative-versus-boring directions and amplify creative writing; DREAM therefore does not originate a creativity vector. [Rahn et al. (EAST)](https://arxiv.org/abs/2406.00244) establish representation-level exploration control.

[Yu et al.](https://aclanthology.org/2026.acl-long.200/) change attention temperature and aggregate reasoning candidates. [DRUGS](https://github.com/EGjoni/DRUGS) and [PiHK/Neuromod-LLM](https://github.com/cneckar/neuromod-llm-poc) supply public perturbation prototypes. [Activation Transport](https://arxiv.org/abs/2410.23054), [feedback-controlled steering](https://proceedings.mlr.press/v306/skifstad26a.html), [BILLY](https://aclanthology.org/2026.eacl-long.369/), and [CreativityNeuro](https://proceedings.colm.cc/paper_files/paper/2026/hash/8edb116d5b288b6a9bba4c16ab647702-Abstract-Conference.html) provide related intervention and creativity comparisons. These methods differ in intervention location, evidence, and whether they change weights.

[Self-Refine](https://arxiv.org/abs/2303.17651) and [Tree of Thoughts](https://arxiv.org/abs/2305.10601) show why reflection and candidate selection need matched controls. [Peeperkorn et al.](https://arxiv.org/abs/2405.00492) and [Farquhar et al.](https://pmc.ncbi.nlm.nih.gov/articles/PMC11186750/) motivate distinguishing meaningful variation and reliability from token diversity. [REBUS](https://pubmed.ncbi.nlm.nih.gov/31221820/) is a biological analogy, not a demonstrated transformer mechanism.

The proposed contribution is the specified useful-idea-survival comparison under controlled steering and integration, not the first use of internal perturbation, creativity steering, or exploratory search. This targeted literature review does not establish uniqueness. See the [source catalog](12-References-and-Method-Credits.md) and [contribution boundaries](07-Literature-and-Novelty.md).

## Computational motivation

A conditional language model organizes generation around familiar trajectories. Prompting, decoding, training data, and previous generated tokens all influence which trajectories are accessible. It is plausible that an intermediate representation intervention changes this search process. It is equally plausible that it only introduces a stylistic bias or suppresses useful features.

Psychedelic neuroscience motivates a stability-flexibility analogy, but its constructs do not transfer automatically. DREAM does not equate token entropy with neural entropy, a residual vector with belief precision, or a generated narrative with subjective experience. A claim about relaxed priors would require additional operational evidence beyond a successful steering experiment.

## Intervention

For a layer l, let v be the unit-normalized mean divergent-prompt activation minus the mean convergent-prompt activation. The intervention is:

`h_prime[b,t] = h[b,t] + lambda_t * norm(h[b,t]) * v`

The coefficient is a fraction of the token-state L2 norm. A value of 0.05 adds a perturbation with approximately five percent of that norm at the intervention site. Equal relative norms do not guarantee equal behavioral effects across layers or models.

The current generation hook changes the final sequence position on each forward call, including the prefill position that predicts the first response token. A rise-hold-fall schedule is indexed over the planned generation cap. Early EOS can end a trajectory before the planned descent. The realized per-call coefficient trace is saved, so a completed schedule must not be assumed.

The contrast prompts are short calibration fixtures. Their length, wording, and abstraction style can confound the extracted direction. A serious study should use more matched pairs, held-out manipulation checks, and unrelated extraction topics.

## Architecture

The anchor is an unsteered restatement of facts, constraints, and assumptions. It is fallible and subordinate to the original task. The exploratory stage generates candidates and failure points. The integration stage receives the original task, anchor notes, and candidate text with steering absent.

Candidate text is serialized as data and described as untrusted. This reduces ambiguity but is not a security boundary against prompt injection. An unsteered copy of the same model is also not an independent truth oracle. Independent symbolic checks or reviewers must determine whether final ideas are actually defensible.

## Experimental comparisons

All primary conditions share the same original task, anchor, exploration instructions, integration instructions, per-stage token caps, and integration decoding policy.

The zero-dose condition runs the entire pipeline with lambda equal to zero. Nonzero-dose conditions change only the intervention strength. A temperature condition changes exploration temperature at zero steering while preserving top-p and the integration procedure.

The no-integration material is retained as the raw exploratory stage of each trial, rather than pretending that a shorter candidate-generation call is compute-matched to an integrated answer. This supports a paired assessment of what integration changes, with the difference in computation explicitly reported.

Actual input and output token counts are logged. Equal caps do not guarantee equal realized computation because outputs stop at different lengths. Analyses should report both the matched-cap comparison and a preregistered length sensitivity analysis.

## Outcomes

The primary scientific outcome should be a blinded assessment of useful, correct novelty or an objective task score chosen before data collection. Lexical variation and embedding distance are diagnostics, not evidence of insight or truth.

A reviewer should receive the original task and score novelty, usefulness, coherence, correctness, and structural correspondence. Record the shortest description of each central idea and whether it appears among the matched zero-dose outputs. Reviewers must not receive the private condition key. Presentation style can still partially reveal conditions, so assess reviewer guesses and disagreement.

The V1.1 runner preserves raw stages and exports a blinded review table. It does not automatically supply expert ratings or a calibrated semantic-entropy estimate. Diversity analyses should operate within the same task; pooling unrelated tasks confounds topic with exploration.

## Predictions and alternatives

A moderate intervention may produce useful alternatives that survive integration. Larger doses may instead degrade coherence. These are hypotheses, not an assured inverted-U curve. A non-monotonic result requires enough dose levels and independent tasks to distinguish it from noise or selection.

Prompting alone, increased temperature, longer responses, evaluator preference for complexity, or repeated familiar analogies may explain a gain. Independent task checks, matched pipelines, held-out extraction prompts, and per-task paired analysis are necessary to narrow those alternatives.

## Falsification and interpretation

If zero-dose prompting or temperature matches the useful output, activation steering has not demonstrated added value. If novelty increases while correctness or usefulness falls beyond preregistered limits, the intervention fails the intended objective.

A positive result supports only the tested model, layer, tasks, and intervention. Replication across a second family and blinded review are required before generalizing. Recurring motifs across models would require controls for shared pretraining data before being described as stable representational structure.

The study does not authorize applying generated engineering, scientific, or health proposals in the real world. The initial task fixtures are abstract, symbolic, and low stakes. The related-work document identifies ActAdd, EAST, CreativityNeuro, and other relevant precedents.
