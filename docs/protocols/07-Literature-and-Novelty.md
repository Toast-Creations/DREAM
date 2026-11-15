# Literature and Contribution Boundaries

**V1.1.4 update — October 30, 2026.** The new task also credits [LLM divergent-association evaluation](https://aclanthology.org/2023.findings-emnlp.858/) and [conditional divergent associations](https://arxiv.org/abs/2601.20546), which emphasize novelty and appropriateness. The five-item concept task is a local exploratory design, not a new claim to invent association testing. Qwen model-specific decoding guidance informs implementation, not evidence that reasoning will help.

Updated October 29, 2026. DREAM uses established activation and adaptation machinery. Its potential contribution is controlled evidence about useful discovery and retained composition under a specified intervention, task, and evaluation design. This release reports no effectiveness result and does not establish scientific priority.

## Exploration and inference

| Prior work | Credit and relationship |
|---|---|
| [Steering Language Models With Activation Engineering](https://arxiv.org/abs/2308.10248) | Contrasting prompt activations supply additive inference-time steering directions. |
| [Steering Llama 2 via Contrastive Activation Addition](https://arxiv.org/abs/2312.06681) | Mean differences across paired examples provide behavior-specific activation vectors. |
| [Representation Engineering: A Top-Down Approach to AI Transparency](https://arxiv.org/abs/2310.01405) | Population-level representations are monitored and manipulated to study high-level behavior. |
| [Steering Large Language Models to Evaluate and Amplify Creativity](https://arxiv.org/abs/2412.06060) | Creative-versus-boring activation contrasts support assessment and steering of creative writing. |
| [Controlling Large Language Model Agents with Entropic Activation Steering](https://arxiv.org/abs/2406.00244) | Entropy-weighted representation interventions modulate agent exploration beyond token sampling in the studied environments. |
| [Thermometer of Thoughts: Enhancing LLM's Exploration via Attention Temperature Modulation](https://aclanthology.org/2026.acl-long.200/) | Attention-temperature changes and difficulty-aware aggregation diversify and select reasoning traces. |
| [DRUGS: Deep Random Micro-Glitch Sampling](https://github.com/EGjoni/DRUGS) | Internal noise at hidden states, Q/K/V, and attention outputs, with depth profiles and cache recomputation. |
| [PiHK.AI and Neuromod-LLM](https://github.com/cneckar/neuromod-llm-poc) | Drug-inspired reversible residual, attention/logit, cache, and routing interventions; evidence here is project-level. |
| [Controlling Language and Diffusion Models by Transporting Activations](https://arxiv.org/abs/2410.23054) | Distributional activation transport provides an alternative to a fixed additive direction. |
| [Local Linearity of LLMs Enables Activation Steering via Model-Based Linear Optimal Control](https://proceedings.mlr.press/v306/skifstad26a.html) | Locally linear models and feedback regulation steer layer-wise activations toward semantic setpoints. |
| [BILLY: Steering Large Language Models via Merging Persona Vectors for Creative Generation](https://aclanthology.org/2026.eacl-long.369/) | Blending multiple persona vectors supplies varied creative perspectives within one model. |
| [CreativityNeuro: Steering Language Model Weights to Improve Divergent Thinking and Reduce Mode Collapse](https://proceedings.colm.cc/paper_files/paper/2026/hash/8edb116d5b288b6a9bba4c16ab647702-Abstract-Conference.html) | Contrastive weight steering is a creativity comparator; its reported task transfer cautions against relying on vocabulary tests alone. |

## Learning and time-varying interventions

| Prior work | Credit and relationship |
|---|---|
| [LoRA: Low-Rank Adaptation of Large Language Models](https://arxiv.org/abs/2106.09685) | Low-rank trainable weight updates on a frozen pretrained base supply the adapter machinery. |
| [Test-Time Learning for Large Language Models](https://arxiv.org/abs/2505.20633) | Target-domain adaptation with a perplexity objective, sample selection, and LoRA is an ordinary-learning comparator. |
| [End-to-End Test-Time Training for Long Context](https://arxiv.org/abs/2512.23675) | Continued next-token updates compress context into weights; persistence after context removal alone is insufficient novelty. |
| [NEFTune: Noisy Embeddings Improve Instruction Finetuning](https://arxiv.org/abs/2310.05914) | Temporary embedding noise during fine-tuning provides a regularization alternative to an exploration explanation. |
| [ReFT: Representation Finetuning for Language Models](https://arxiv.org/abs/2404.03592) | Trainable hidden-representation interventions on a frozen base are related but differ from removing the exploration hook after adapter learning. |
| [Making Harmful Behaviors Unlearnable for Large Language Models](https://aclanthology.org/2024.findings-acl.611/) | Security vectors operate during fine-tuning and are deactivated afterward; temporary training-time intervention is established. |
| [Steering Out-of-Distribution Generalization with Concept Ablation Fine-Tuning](https://arxiv.org/abs/2507.16795) | Concept projections during fine-tuning change later out-of-distribution generalization without modifying the examples. |
| [Persona Vectors: Monitoring and Controlling Character Traits in Language Models](https://arxiv.org/abs/2507.21509) | Training-time steering changes later trait acquisition, including compensatory reduction rather than simple imprinting. |
| [Weight Updates as Activation Shifts: A Principled Framework for Steering](https://proceedings.mlr.press/v306/adila26a.html) | Activation and weight changes are related analytically and trained jointly; broad joint adaptation is prior work. |
| [Active Adaptation, Not Static Defense: Temporal Dynamics of Preventative Steering in Adversarial Fine-Tuning](https://aclanthology.org/2026.findings-emnlp.1991/) | Temporal compensation and progressive intensity scheduling mean that time-varying training-time steering is also prior work. |
| [Backpropamine: Training Self-Modifying Neural Networks with Differentiable Neuromodulated Plasticity](https://arxiv.org/abs/2002.10585) | Learned modulation of plasticity predates temporary learning-window proposals for transformers. |

## Reflection, instrumentation, and biological inspiration

[Self-Refine](https://arxiv.org/abs/2303.17651) and [Tree of Thoughts](https://arxiv.org/abs/2305.10601) motivate matched reflection and search controls. [Sparse-feature research](https://www.anthropic.com/research/mapping-mind-language-model) and [Assistant Axis](https://www.anthropic.com/research/assistant-axis) supply precedents for measuring and controlling internal representations. [Semantic entropy](https://pmc.ncbi.nlm.nih.gov/articles/PMC11186750/) distinguishes uncertainty over meanings from wording variation; it is not automatically measured by the current runner. [Temperature-and-creativity experiments](https://arxiv.org/abs/2405.00492) motivate measuring quality and coherence separately from diversity.

[REBUS](https://pubmed.ncbi.nlm.nih.gov/31221820/) and [the mouse critical-period study](https://pubmed.ncbi.nlm.nih.gov/37316665/) are biological inspiration. They do not validate a transformer analogue or show that subjective experience is needed for learning.

## Proposed contribution and explicit exclusions

DREAM proposes testing whether temporary exploration-oriented steering improves verified useful ideas after a matched, unsteered integration stage. DREAM 2 proposes testing held-out composition after reversible adapter learning with the steering removed, the experience absent from context, and appropriate ordinary-learning and perturbation controls.

Neither proposal originates contrastive steering, creativity vectors, attention modulation, drug-inspired perturbation, representation interventions during fine-tuning, LoRA, test-time learning, modulated plasticity, candidate evaluation, or temporal steering schedules. Guan et al. already study temporal adaptation and changing intensity; our bell/plateau/recovery comparisons would concern a different objective and need direct comparison. Combining known methods is not by itself evidence of a new mechanism.

An observed benefit could reflect style, longer generation, ordinary noise regularization, gradient magnitude, compensatory adaptation, or candidate selection. Timing, recovery learning, identity conditioning, attention modulation, and richer internal instrumentation are proposed extensions, not newly implemented features of 1.1.1.

Read the [complete source catalog](12-References-and-Method-Credits.md), [method-to-file credits](../../METHOD_CREDITS.md), [attribution record](08-Attribution-and-Collaboration.md), and [research roadmap](11-Research-Roadmap.md). Bibliographic records are in [references.bib](../../references.bib) and [references.json](../../references.json). Official runtime API references retained from V1.1 are [causal language modeling](https://huggingface.co/docs/transformers/v4.45.2/en/tasks/language_modeling), [Qwen2](https://huggingface.co/docs/transformers/v4.55.4/en/model_doc/qwen2), and [LoRA](https://huggingface.co/docs/peft/v0.17.0/en/package_reference/lora).
