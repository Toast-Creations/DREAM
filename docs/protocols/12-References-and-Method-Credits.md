# References and Method Credits

Updated October 30, 2026 for research revision 1.2.0; 42 source records (8 added for the decategorization study, listed at the end). These are scholarly method credits. Citing a work does not identify its authors as DREAM collaborators or endorsers.

The source catalog is also available as [BibTeX](../../references.bib) and [structured JSON](../../references.json). Some author lists are explicitly abbreviated with et al.; the linked primary record supplies the full list. No source paper, figure, model weights, or third-party implementation was added to this revision.

## turner2023actadd

Turner, Alexander Matt et al.. 2023. [Steering Language Models With Activation Engineering](https://arxiv.org/abs/2308.10248).

Status: Research paper; revised 2024. Checked 2026-10-29.

Contrasting prompt activations supply additive inference-time steering directions.

## rimsky2023caa

Panickssery, Nina et al.. 2023. [Steering Llama 2 via Contrastive Activation Addition](https://arxiv.org/abs/2312.06681).

Status: Research paper; revised 2024; also indexed under Nina Rimsky. Checked 2026-10-29.

Mean differences across paired examples provide behavior-specific activation vectors.

## olson2024creativity

Olson, Matthew Lyle; Ratzlaff, Neale; Hinck, Musashi; Tseng, Shao-yen; Lal, Vasudev. 2024. [Steering Large Language Models to Evaluate and Amplify Creativity](https://arxiv.org/abs/2412.06060).

Status: NeurIPS 2024 Creativity and Generative AI workshop spotlight. Checked 2026-10-29.

Creative-versus-boring activation contrasts support assessment and steering of creative writing.

## rahn2024east

Rahn, Nate; D'Oro, Pierluca; Bellemare, Marc G.. 2024. [Controlling Large Language Model Agents with Entropic Activation Steering](https://arxiv.org/abs/2406.00244).

Status: Research paper. Checked 2026-10-29.

Entropy-weighted representation interventions modulate agent exploration beyond token sampling in the studied environments.

## yu2026thermometer

Yu, Zhiyuan; Xiao, Shijian; Nguyen, Cam-Tu; Yin, Zhangyue; Xing, Lekai; Li, Wenzhong; Lu, Sanglu. 2026. [Thermometer of Thoughts: Enhancing LLM's Exploration via Attention Temperature Modulation](https://aclanthology.org/2026.acl-long.200/).

Status: ACL 2026. Checked 2026-10-29.

Attention-temperature changes and difficulty-aware aggregation diversify and select reasoning traces.

## egjoni_drugs

EGjoni. Undated project. [DRUGS: Deep Random Micro-Glitch Sampling](https://github.com/EGjoni/DRUGS).

Status: Original public code prototype; no publication year assigned here. Checked 2026-10-29.

Internal noise at hidden states, Q/K/V, and attention outputs, with depth profiles and cache recomputation.

## cneckar_pihk

cneckar. Undated project. [PiHK.AI and Neuromod-LLM](https://github.com/cneckar/neuromod-llm-poc).

Status: Public research prototype; project page https://pihk.ai/index.html. Checked 2026-10-29.

Drug-inspired reversible residual, attention/logit, cache, and routing interventions; evidence here is project-level.

## rodriguez2024act

Rodriguez, Pau; Blaas, Arno; Klein, Michal; Zappella, Luca; Apostoloff, Nicholas; Cuturi, Marco; Suau, Xavier. 2024. [Controlling Language and Diffusion Models by Transporting Activations](https://arxiv.org/abs/2410.23054).

Status: ICLR 2025; preprint 2024. Checked 2026-10-29.

Distributional activation transport provides an alternative to a fixed additive direction.

## skifstad2026lqr

Skifstad, Julian; Yang, Xinyue Annie; Chou, Glen. 2026. [Local Linearity of LLMs Enables Activation Steering via Model-Based Linear Optimal Control](https://proceedings.mlr.press/v306/skifstad26a.html).

Status: ICML 2026. Checked 2026-10-29.

Locally linear models and feedback regulation steer layer-wise activations toward semantic setpoints.

## pai2026billy

Pai, Tsung-Min; Wang, Jui-I; Lu, Li-Chun; Sun, Shao-Hua; Lee, Hung-Yi; Chang, Kai-Wei. 2026. [BILLY: Steering Large Language Models via Merging Persona Vectors for Creative Generation](https://aclanthology.org/2026.eacl-long.369/).

Status: EACL 2026; preprint 2025. Checked 2026-10-29.

Blending multiple persona vectors supplies varied creative perspectives within one model.

## schapiro2026creativityneuro

Schapiro, Samuel; Park, Core Francisco; Sosa, Felix A.; Varshney, Lav. 2026. [CreativityNeuro: Steering Language Model Weights to Improve Divergent Thinking and Reduce Mode Collapse](https://proceedings.colm.cc/paper_files/paper/2026/hash/8edb116d5b288b6a9bba4c16ab647702-Abstract-Conference.html).

Status: COLM 2026 pre-proceedings record; abstract reviewed. Checked 2026-10-29.

Contrastive weight steering is a creativity comparator; its reported task transfer cautions against relying on vocabulary tests alone.

## hu2021lora

Hu, Edward J. et al.. 2021. [LoRA: Low-Rank Adaptation of Large Language Models](https://arxiv.org/abs/2106.09685).

Status: Research paper. Checked 2026-10-29.

Low-rank trainable weight updates on a frozen pretrained base supply the adapter machinery.

## hu2025ttl

Hu, Jinwu et al.. 2025. [Test-Time Learning for Large Language Models](https://arxiv.org/abs/2505.20633).

Status: ICML 2025, according to the paper record. Checked 2026-10-29.

Target-domain adaptation with a perplexity objective, sample selection, and LoRA is an ordinary-learning comparator.

## jain2023neftune

Jain, Neel et al.. 2023. [NEFTune: Noisy Embeddings Improve Instruction Finetuning](https://arxiv.org/abs/2310.05914).

Status: ICLR 2024; preprint 2023. Checked 2026-10-29.

Temporary embedding noise during fine-tuning provides a regularization alternative to an exploration explanation.

## wu2024reft

Wu, Zhengxuan et al.. 2024. [ReFT: Representation Finetuning for Language Models](https://arxiv.org/abs/2404.03592).

Status: Research paper. Checked 2026-10-29.

Trainable hidden-representation interventions on a frozen base are related but differ from removing the exploration hook after adapter learning.

## adila2026joint

Adila, Dyah; Cooper, John; Yun, Alexander; Trost, Avi; Sala, Frederic. 2026. [Weight Updates as Activation Shifts: A Principled Framework for Steering](https://proceedings.mlr.press/v306/adila26a.html).

Status: ICML 2026; proceedings abstract reviewed. Checked 2026-10-29.

Activation and weight changes are related analytically and trained jointly; broad joint adaptation is prior work.

## chen2025persona

Chen, Runjin; Arditi, Andy; Sleight, Henry; Evans, Owain; Lindsey, Jack. 2025. [Persona Vectors: Monitoring and Controlling Character Traits in Language Models](https://arxiv.org/abs/2507.21509).

Status: Research paper; v3 record checked. Checked 2026-10-29.

Training-time steering changes later trait acquisition, including compensatory reduction rather than simple imprinting.

## miconi2019backpropamine

Miconi, Thomas; Rawal, Aditya; Clune, Jeff; Stanley, Kenneth O.. 2019. [Backpropamine: Training Self-Modifying Neural Networks with Differentiable Neuromodulated Plasticity](https://arxiv.org/abs/2002.10585).

Status: ICLR 2019; arXiv posting 2020. Checked 2026-10-29.

Learned modulation of plasticity predates temporary learning-window proposals for transformers.

## madaan2023selfrefine

Madaan, Aman et al.. 2023. [Self-Refine: Iterative Refinement with Self-Feedback](https://arxiv.org/abs/2303.17651).

Status: Research paper. Checked 2026-10-29.

Generation, feedback, and revision without weight updates motivate compute-matched reflection controls.

## yao2023tot

Yao, Shunyu et al.. 2023. [Tree of Thoughts: Deliberate Problem Solving with Large Language Models](https://arxiv.org/abs/2305.10601).

Status: NeurIPS 2023. Checked 2026-10-29.

Text-level alternative-path search, evaluation, and backtracking are exploration baselines.

## anthropic2026axis

Anthropic. 2026. [The Assistant Axis: Situating and Stabilizing the Character of Large Language Models](https://www.anthropic.com/research/assistant-axis).

Status: Author research explanation, linking the paper. Checked 2026-10-29.

Mapping persona representations and constraining assistant-related activations are precedents for behavioral stability measurements.

## anthropic2024features

Anthropic. 2024. [Mapping the Mind of a Large Language Model](https://www.anthropic.com/research/mapping-mind-language-model).

Status: Author explanation of sparse-feature research. Checked 2026-10-29.

Dictionary learning and feature interventions provide precedents for internal-state measurement and causal tests.

## peeperkorn2024temperature

Peeperkorn, Max; Kouwenhoven, Tom; Brown, Dan; Jordanous, Anna. 2024. [Is Temperature the Creativity Parameter of Large Language Models?](https://arxiv.org/abs/2405.00492).

Status: Research paper. Checked 2026-10-29.

Narrative-generation experiments separate novelty, coherence, cohesion, and typicality; temperature is not a general creativity guarantee.

## zhou2024security

Zhou, Xin; Lu, Yi; Ma, Ruotian; Wei, Yujian; Gui, Tao; Zhang, Qi; Huang, Xuanjing. 2024. [Making Harmful Behaviors Unlearnable for Large Language Models](https://aclanthology.org/2024.findings-acl.611/).

Status: Findings of ACL 2024. Checked 2026-10-29.

Security vectors operate during fine-tuning and are deactivated afterward; temporary training-time intervention is established.

## casademunt2025caft

Casademunt, Helena; Juang, Caden; Karvonen, Adam; Marks, Samuel; Rajamanoharan, Senthooran; Nanda, Neel. 2025. [Steering Out-of-Distribution Generalization with Concept Ablation Fine-Tuning](https://arxiv.org/abs/2507.16795).

Status: Research paper; v2 record checked. Checked 2026-10-29.

Concept projections during fine-tuning change later out-of-distribution generalization without modifying the examples.

## guan2026temporal

Guan, Jing; Yang, Yachao; Liu, Zhaoliang; Zhang, Yuyao; Meng, Fanyu; Feng, Junlan. 2026. [Active Adaptation, Not Static Defense: Temporal Dynamics of Preventative Steering in Adversarial Fine-Tuning](https://aclanthology.org/2026.findings-emnlp.1991/).

Status: Findings of EMNLP 2026; updated from the V1.1 preprint citation. Checked 2026-10-29.

Temporal compensation and progressive intensity scheduling mean that time-varying training-time steering is also prior work.

## tandon2025ttt

Tandon, Arnuv et al.. 2025. [End-to-End Test-Time Training for Long Context](https://arxiv.org/abs/2512.23675).

Status: Research paper; v2 record checked. Checked 2026-10-29.

Continued next-token updates compress context into weights; persistence after context removal alone is insufficient novelty.

## zou2023repe

Zou, Andy et al.. 2023. [Representation Engineering: A Top-Down Approach to AI Transparency](https://arxiv.org/abs/2310.01405).

Status: Research paper; revised 2025. Checked 2026-10-29.

Population-level representations are monitored and manipulated to study high-level behavior.

## carhartharris2019rebus

Carhart-Harris, Robin L.; Friston, Karl J.. 2019. [REBUS and the Anarchic Brain: Toward a Unified Model of the Brain Action of Psychedelics](https://pubmed.ncbi.nlm.nih.gov/31221820/).

Status: Pharmacological Reviews; biological theory. Checked 2026-10-29.

Motivates a flexibility/precision analogy, not evidence for a transformer mechanism.

## nardou2023critical

Nardou, Romain et al.. 2023. [Psychedelics Reopen the Social Reward Learning Critical Period](https://pubmed.ncbi.nlm.nih.gov/37316665/).

Status: Nature; mouse study. Checked 2026-10-29.

Biological inspiration concerning learning windows, not a demonstration of analogous transformer plasticity.

## farquhar2024entropy

Farquhar, Sebastian; Kossen, Jannik; Kuhn, Lorenz; Gal, Yarin. 2024. [Detecting Hallucinations in Large Language Models Using Semantic Entropy](https://pmc.ncbi.nlm.nih.gov/articles/PMC11186750/).

Status: Nature. Checked 2026-10-29.

Meaning-level uncertainty is distinct from lexical diversity and is not automatically computed by the shipped runner.

## Evidence limits

The search was targeted rather than systematic. Entries distinguish original research, conference or workshop records, author explanations, and code prototypes. Several summaries use a primary abstract rather than a full-method audit, especially joint adaptation and CreativityNeuro. The PiHK paper could not be retrieved in full; its entry credits the public project and linked source repository. Reported benefits belong to the original studies and are not independent DREAM replications.

Biological analogy, unusual output, persona consistency, and activation geometry do not establish subjective experience. No effectiveness result is added by this documentation revision.

## chen2023association

Chen, Honghua and Ding, Nai. 2023. [Probing the Creativity of Large Language Models: Can models produce divergent semantic association?](https://aclanthology.org/2023.findings-emnlp.858/).

Status: Findings of EMNLP 2023. Checked 2026-10-30.

Prior LLM divergent-association evaluation; task and decoding choices affect measured divergence.

## nakajima2026conditional

Nakajima, Kumiko and Zuiderveld, Jan and Pezzelle, Sandro. 2026. [Beyond Divergent Creativity: A Human-Based Evaluation of Creativity in Large Language Models](https://arxiv.org/abs/2601.20546).

Status: Accepted to Findings of EACL 2026; arXiv author record checked. Checked 2026-10-30.

Conditional divergent associations require contextual appropriateness alongside novelty; motivates relevance-gated quality.

## qwen2025qwen3card

Qwen Team. 2025. [Qwen3-8B model card and thinking-mode guidance](https://huggingface.co/Qwen/Qwen3-8B).

Status: Official model documentation; accessed 2026-10-30. Checked 2026-10-30.

Exact-model thinking switch, output parsing and sampled-decoding recommendations; not evidence of a benefit on DREAM tasks.

## V1.2.0 additions (decategorization trip study)

## scalena2024dac

Scalena, Daniel; Sarti, Gabriele; Nissim, Malvina. 2024. [Multi-property Steering of Large Language Models with Dynamic Activation Composition](https://arxiv.org/abs/2406.17563).

Status: BlackboxNLP 2024. Located 2026-10-30 via abstract/search; full text not yet reviewed; verify details against the primary record.

Closest prior time-varying steering strength (per-token, divergence-adaptive); the V1.2.0 trip uses a fixed pharmacokinetic-style curve instead.

## ead2025annealed

Authors per primary record. 2025. [Let it Calm: Exploratory Annealed Decoding](https://arxiv.org/abs/2510.05251).

Status: Preprint. Located 2026-10-30 via abstract/search; full text not yet reviewed; verify details against the primary record.

Hot-to-cold temperature schedule within one generation; motivates the temperature_anneal control arm.

## nguyen2025creativedc

Nguyen; Singla. 2025. [CreativeDC: divergent-convergent generation for LLM creativity](https://arxiv.org/abs/2512.23601).

Status: Preprint. Located 2026-10-30 via abstract/search; full text not yet reviewed; verify details against the primary record.

Brainstorm-then-refine design; nearest analogue to the V1.2.0 sober pass.

## park2025categorical

Park, Kiho; Choe, Yo Joong; Jiang, Yibo; Veitch, Victor. 2025. [The Geometry of Categorical and Hierarchical Concepts in Large Language Models](https://arxiv.org/abs/2406.01506).

Status: ICLR 2025. Located 2026-10-30 via abstract/search; full text not yet reviewed; verify details against the primary record.

Category geometry in representation space; background for defining a decategorization direction.

## figurative2026concreteness

Authors per primary record. 2026. [Concreteness through a figurative lens (literal/figurative steering vectors)](https://arxiv.org/abs/2604.18296).

Status: ACL 2026. Located 2026-10-30 via abstract/search; full text not yet reviewed; verify details against the primary record.

Difference-of-means literal/figurative direction whose sign switches style; precedent for a signed category-looseness dial.

## wiessner2022lsd

Wießner, Isabel et al.. 2022. [LSD and creativity: Increased novelty and symbolic thinking, decreased utility and convergent thinking](https://cris.maastrichtuniversity.nl/en/publications/lsd-and-creativity-increased-novelty-and-symbolic-thinking-decrea).

Status: Journal of Psychopharmacology. Located 2026-10-30 via abstract/search; full text not yet reviewed; verify details against the primary record.

Human analogue: novelty up, usefulness down under LSD; motivates a separate sober reinterpretation. Analogy only.

## yan2026beyondnoise

Yan et al.. 2026. [Beyond Noise: separating creative synthesis from fabrication in LLM hallucinations](https://preview.aclanthology.org/ingest-acl/2026.acl-long.554/).

Status: ACL 2026. Located 2026-10-30 via abstract/search; full text not yet reviewed; verify details against the primary record.

Framing for 'nonsense with a kernel'; supports reviewing strange ideas instead of discarding them.

## hypobench2025

Authors per primary record. 2025. [HypoBench: evaluating hypothesis generation](https://arxiv.org/abs/2504.11524).

Status: Preprint. Located 2026-10-30 via abstract/search; full text not yet reviewed; verify details against the primary record.

LLM-judged novelty and plausibility ratings; informs the V1.2.0 blinded idea rubric.
