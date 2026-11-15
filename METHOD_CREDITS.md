# Method credits and source provenance

Documentation revision 1.1.1, October 29, 2026. This table credits intellectual methods. It does not claim that source code was copied from the cited projects or that the cited authors contributed to DREAM.

| DREAM component | Location | Methodological credit |
|---|---|---|
| Contrast extraction and additive intervention | [src/dream_core/steering.py](src/dream_core/steering.py) | [turner2023actadd](https://arxiv.org/abs/2308.10248); [rimsky2023caa](https://arxiv.org/abs/2312.06681); [olson2024creativity](https://arxiv.org/abs/2412.06060) |
| Exploration objective and comparisons | [src/dream/experiment.py](src/dream/experiment.py) | [rahn2024east](https://arxiv.org/abs/2406.00244); [yu2026thermometer](https://aclanthology.org/2026.acl-long.200/); [madaan2023selfrefine](https://arxiv.org/abs/2303.17651); [yao2023tot](https://arxiv.org/abs/2305.10601) |
| Reversible low-rank adaptation | [src/dream2/plasticity.py](src/dream2/plasticity.py) | [hu2021lora](https://arxiv.org/abs/2106.09685); [hu2025ttl](https://arxiv.org/abs/2505.20633) |
| Steering while the adapter learns | [src/dream2/training.py](src/dream2/training.py) | [zhou2024security](https://aclanthology.org/2024.findings-acl.611/); [casademunt2025caft](https://arxiv.org/abs/2507.16795); [chen2025persona](https://arxiv.org/abs/2507.21509); [jain2023neftune](https://arxiv.org/abs/2310.05914); [adila2026joint](https://proceedings.mlr.press/v306/adila26a.html) |
| Proposed timing and internal-state studies | [documents/11-Research-Roadmap.md](docs/protocols/11-Research-Roadmap.md) | [guan2026temporal](https://aclanthology.org/2026.findings-emnlp.1991/); [skifstad2026lqr](https://proceedings.mlr.press/v306/skifstad26a.html); [anthropic2024features](https://www.anthropic.com/research/mapping-mind-language-model); [anthropic2026axis](https://www.anthropic.com/research/assistant-axis) |

The proposal's specific benchmark, controls, measures, safeguards, and analysis need their own evidence; citations are not validation of those choices. This revision adds no third-party implementation or model weights. It is not a forensic audit of every pre-existing source line. Any later copied or adapted code must record the exact source/version, applicable license, modified files, and required notices separately from scholarly citations.

Project lead: David Cook. AI tools assisted drafting, synthesis, code, review, and checks as described in [attribution](docs/protocols/08-Attribution-and-Collaboration.md). No cited researcher is listed as a DREAM coauthor or endorser. The existing [Apache-2.0 license](LICENSE) and original notices are preserved.

## V1.1.4 concept-association study

The direct association task and blinded quality rubric in src/dream/concepts.py and document 13 build on association-based evaluation (Chen and Ding, 2023) and the distinction between novelty and appropriateness (Nakajima, Zuiderveld and Pezzelle, 2026). Neither exact wording nor implementation was copied from those papers. Qwen's official model guidance informs explicit thinking-mode rendering, splitting and sampled decoding. The local fixed-five task has not been validated as a general creativity instrument.

David Cook requested the concept task, the five-related-items response format, the reasoning comparison and the broad subject mix, and stated his expectation of a positive reasoning effect. Codex assisted with protocol detail, implementation, testing and analysis. Claude Code assisted with the earlier Qwen3 pilots; original notices and method credits remain preserved.

## V1.2.0 decategorization trip study

The signed decategorization direction reuses the additive contrast method credited above (ActAdd; CAA). Literal/figurative steering work (2026) and category geometry (Park et al., ICLR 2025) are the closest precedents for a category-looseness direction. The time-varying dose relates to dynamic activation composition (Scalena et al., 2024), and the temperature-anneal control to exploratory annealed decoding (2025). The sober pass relates to divergent-then-convergent generation (CreativeDC, 2025). Human psychedelic creativity findings (Wießner et al., 2022) are an analogy only. The review rubric draws on novelty/plausibility judging (HypoBench, 2025). No code or wording was copied from these works.

David Cook proposed decategorization as the variable, the smooth trip with self-correction that keeps interesting ideas, both trip styles, concrete objects, and Claude review. Claude Code (Claude Opus 5.5) assisted with the literature check, design, implementation and tests.

