# Getting started

## Requirements

- Python 3.10 or later. The core logic has no dependencies.
- For model runs: `torch`, `transformers`, `peft`, `safetensors` and `accelerate` (`pip install -e '.[ml]'`), plus `bitsandbytes` for the NF4 Qwen3-32B studies. Every study used a single 24 GB GPU (an RTX 3090).
- The original runs used a Fedora-based `distrobox` container with a dedicated virtual environment. Nothing here depends on that setup.

## Tests

```bash
pip install -e .
python -B scripts/run_tests.py                 # CPU logic; ML integration tests are reported as skipped
python -B scripts/run_tests.py --require-ml    # fails unless the ML stack is present and every test runs
```

The runner writes a JSON record (default `test-results/latest.json`) with the counts and a source digest. ML integration tests build a tiny random transformer locally, so no download is needed.

A few tests compare files against earlier archived source versions, or read saved run folders. When those folders are missing they **skip** and say why. Point them at your own copies with the environment variables below.

## Local paths

Scripts find local resources through environment variables (see `src/dream_core/localpaths.py`):

| Variable | Meaning | Default |
|---|---|---|
| `DREAM_HOME` | project folder holding `Runs/` and `Code/` | `~/DREAM` |
| `DREAM_RUNS` | run hubs (study outputs) | `$DREAM_HOME/Runs` |
| `DREAM_CODE` | archived per-version source copies (optional) | `$DREAM_HOME/Code` |
| `DREAM_MODELS` | model store | `~/DREAM-models` |
| `DREAM_PY` | Python interpreter for child runs | the current interpreter |

## Models

Shipped configurations leave model paths unset on purpose. Download the weights yourself, then point a config or script at a local snapshot directory and its manifest. The loader refuses remote code and checks the snapshot against the manifest's content hashes. The studies used:

- `Qwen/Qwen3-8B`, revision `b968826d9c46dd6066d109eabc6255188de91218`
- `Qwen/Qwen3-32B`, revision `9216db5781bf21249d130ec9da846c4624c16137`, loaded in NF4
- `mistralai/Mistral-7B-Instruct-v0.3` for one idea-survival pilot, and `Qwen/Qwen2.5-0.5B` for the earliest attended pilots

## Running a study

Each study has a `*_generate`/`*_prepare` script, a `*_run` script and an `*_analyze` script, all under `scripts/`. Its plan in [`results/<hub>/STUDY-PLAN.md`](../results/) gives the exact stages. Most scripts support `--help`, and the experiment runner supports `--plan-only`:

```bash
python -B scripts/run_experiment.py --config configs/concepts-smoke.json --plan-only
```

Read the [safety notes](safety.md) before running anything that lets a model write or execute code.
