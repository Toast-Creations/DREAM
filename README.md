# DREAM

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.24261209.svg)](https://doi.org/10.5281/zenodo.24261209) [![Data DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.24264840.svg)](https://doi.org/10.5281/zenodo.24264840) [![tests](https://github.com/Toast-Creations/DREAM/actions/workflows/tests.yml/badge.svg)](https://github.com/Toast-Creations/DREAM/actions/workflows/tests.yml)

DREAM is an independent research project. It runs controlled, pre-specified experiments on open-weight language models (mostly Qwen3-8B and Qwen3-32B) on a single 24 GB GPU. Everything is published here: the code, the frozen study plans, the reports and the errata, including the experiments that failed.

Maintained by **Toast Creations LLC**. Research lead: **David Cook**.

> **Status, November 2026.** Most of the results in this repository are negative or still exploratory. Two research lines did not find the effect they were looking for. The third (temporal state tracking) has measured gains on synthetic tasks we designed ourselves, and it has not been tested on outside benchmarks. Each study page says exactly which claims its data supports.

## Three research lines

| Line | Question | Where it stands |
|---|---|---|
| [Creativity steering (DREAM, DREAM3)](docs/lines/creativity.md) | Can activation steering put a model into a "decategorized" state that produces better ideas, which are then developed normally? | **Negative.** Pre-specified screens found no direction that beat random directions and then replicated. The best candidate *tightened* category membership. See the [manuscript](docs/papers/manuscript-v0.7.md) and six [follow-up proposals](docs/proposals/README.md) (not run). |
| [Reversible learning (DREAM2)](docs/lines/dream2.md) | Can temporary LoRA adapters learn rules or episode-specific facts, then be rolled back cleanly? | **No supported gain.** The adapters memorised their support examples. Held-out complete-pair gains were small, their intervals crossed zero, and they were not specific to the episode. |
| [Temporal state tracking](docs/lines/temporal.md) | Can an LLM turn text reports into typed records for a symbolic state engine, and can the engine choose what to observe? | **Measured gains on our own synthetic worlds.** Dependency-aware query selection: +1.95 utility per world over 768 text worlds. Extraction representations: arrival exact rate up to 475/480 in the latest development screen. Not yet tested on external data. |

The full list of studies, each with its result and errata, is in **[docs/studies.md](docs/studies.md)**.

## Why publish negative results

The studies follow the same discipline. Designs and analysis rules are frozen before data are opened. Sealed evaluation sets stay sealed. Measurement instruments must pass qualification before they are used, and a failed instrument stays failed. Corrections are added as dated errata rather than overwriting the original report. Publishing everything, including what didn't work, lets other people check that this discipline was actually followed.

## Repository layout

```
src/            Python packages: dream_core (shared model/steering/ledger code), dream, dream2,
                survival (idea survival), ectx (explicit context), tempo (temporal state engine and studies)
scripts/        study entry points (generate / run / validate / analyze), test runner
tests/          unit and integration tests (CPU fixtures; ML tests build a tiny random model)
configs/        experiment configurations (model paths intentionally unset)
data/           task and fixture files used by the studies
docs/           research lines, protocols, study index, proposals, manuscript
results/        per-study reports, plans and errata copied from the run folders
```

Raw model outputs, judge ratings, logs and LoRA adapters (52,528 files) are not in git. They are archived on Zenodo as **[DREAM run data, archive v1](https://doi.org/10.5281/zenodo.24264840)** (DOI 10.5281/zenodo.24264840): one zip per run folder, byte-identical to what the studies produced, with a sha256 manifest. Unzip the folders side by side and set `DREAM_RUNS` to that directory.

## Quick start

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e .                 # core logic, no ML dependencies
python -B scripts/run_tests.py   # CPU suite; ML integration tests are skipped and reported as skipped
pip install -e '.[ml]'           # torch, transformers, peft, safetensors, accelerate
python -B scripts/run_tests.py --require-ml
```

Running real studies needs local model weights with a verified manifest. See [docs/getting-started.md](docs/getting-started.md) and the [safety notes](docs/safety.md).

## How to cite

Cook, D. (2026). *DREAM: pre-specified experiments on activation steering, reversible learning and temporal state tracking in open-weight language models.* Toast Creations LLC. https://doi.org/10.5281/zenodo.24261209

That DOI always points to the latest version. Each release also has its own DOI, listed on its [Zenodo record](https://doi.org/10.5281/zenodo.24261209); the latest, v2.0.2, is [10.5281/zenodo.24264554](https://doi.org/10.5281/zenodo.24264554). Please cite the version you used. If you use the run data, please also cite the data archive: Cook, D. (2026). *DREAM run data, archive v1.* Toast Creations LLC. https://doi.org/10.5281/zenodo.24264840. Machine-readable metadata is in [CITATION.cff](CITATION.cff).

## AI assistance

AI tools (Anthropic's Claude and OpenAI's Codex/GPT models) helped write code, tests, analysis and text, and also served as model judges in some studies. Where AI judges were used, they had to pass a qualification step first, and each study report says what was judged by a model and what by a human. AI systems are not listed as authors. See [NOTICE](NOTICE).

## License

Code and documentation: [Apache License 2.0](LICENSE). Copyright 2026 Toast Creations LLC. Third-party models, libraries and cited publications keep their own licenses. No model weights are included.
