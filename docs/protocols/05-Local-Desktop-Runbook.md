# Local Desktop Runbook

**V1.1.4 update — October 30, 2026.** The current measured desktop is Linux with a local ML container. The new direct-to-GPU loader avoids a full host-RAM model copy. The Windows setup below is retained as a portability guide, not a description of the current machine. Use the concept commands and controller workflow added at the end; current measured checks supersede older missing-runtime statements.

Use a normal non-administrator Python environment. The experimental scripts never download a model. They require local safetensors weights, a native instruction chat template, and a content manifest.

## Windows environment

Install a normal Python 3.10 or newer interpreter. If python opens the Microsoft Store or reports a missing interpreter, install Python and reopen PowerShell. Avoid using an unrelated application's embedded interpreter for your ongoing project.

From the V1.1 project directory:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-ml.txt
.\.venv\Scripts\python.exe scripts/run_tests.py --require-ml
.\.venv\Scripts\python.exe -m pip freeze > environment-lock.txt
```

The dependency file specifies candidate compatible bounds, not a tested platform lock. Resolve a maintained PyTorch build appropriate for Windows and the GPU using its official installation selector. If an install produces a CPU-only build, CUDA will be unavailable and the run will fail rather than silently offload the model. Record the exact successful stack. Do not globally upgrade unrelated applications' dependencies.

The earlier release-authoring runtime lacked the ML stack. The current Linux container has a working stack with 50 no-skip tests; Windows setup remains platform-specific and must be checked separately.

## Trusted local model preparation

Obtain a supported instruction model from its official publisher and review its license and format. The original reference model is Qwen2.5 7B Instruct, but a smaller supported model is preferable for a first wiring check. Keep one model family fixed within an experiment.

Record the publisher's actual immutable 40-character repository commit and the model ID. Model identity must come from a verified source, not a hash-shaped invented value. No download helper is provided, so network preparation remains separate from experiment execution.

Create a content manifest:

```powershell
python scripts/create_model_manifest.py `
  --model-dir C:/models/your-model `
  --model-id publisher/model `
  --revision ACTUAL_40_CHARACTER_COMMIT `
  --output C:/models/your-model-manifest.json
```

The uppercase revision argument above is an instruction placeholder and must be replaced. The script refuses it. The manifest detects later changes to the recorded bytes; it does not authenticate their upstream origin.

Edit a copy of the smoke JSON config. Set model.path and model.manifest to your actual local locations. Relative paths resolve from the config file directory. Set the appropriate layer index for the chosen model. A tiny two-layer model needs a valid layer such as zero rather than the shipped minus-eight reference.

Use CPU with float32 for a small CPU model or CUDA with bfloat16 on supported hardware. V1.1 deliberately excludes FP16 training until an explicit scaling policy is implemented. Multi-device sharding, CPU offload, quantization, and remote custom code are outside this version's tested design.

## Plan before loading

```powershell
python scripts/run_experiment.py --config configs/dream2-smoke.json --plan-only
python scripts/run_experiment.py --config configs/dream-smoke.json --plan-only
```

The smoke plans contain six DREAM 2 cells or three DREAM 1 cells per seed and one development item. The pilot plans are larger and need explicit budgeting. Plan-only performs no model loading.

## Build the intervention

```powershell
python scripts/build_steering_vector.py --config configs/dream2-smoke.json
```

The JSON artifact is bound to the exact model manifest and resolved layer. Reuse is allowed only when those identities match. Changing models or layers requires a new vector path and artifact; existing artifacts are not silently overwritten.

## Run a bounded smoke experiment

```powershell
python scripts/run_experiment.py --config configs/dream2-smoke.json
python scripts/run_experiment.py --config configs/dream-smoke.json
```

Monitor the first run. The observed RTX 3090 has 24 GB VRAM, but weight size alone does not predict peak memory. Start short. OOM is a failed experiment, not permission to silently change quantization or move half the model to CPU.

Each run receives a unique timestamp-and-random ID. Configuration, environment, hashes, status, and completed trial records are saved incrementally. Dataset and vector identity are recorded. End-to-end base hashing can be slow for large models; disabling per-trial hashing is a documented deviation, not a silent performance fix.

## Review and recover

If interrupted, inspect status.json and failed-trial records. Completed trial records remain available. The process checks time between calls; max_seconds is not an operating-system watchdog capable of interrupting a hung GPU kernel. A hard runtime boundary requires an external process supervisor or manual termination.

Do not reuse an adapter from an invalid run. Repair the cause, retain the failed run, and start a new run ID. Configuration edits create a new experimental condition.

For DREAM 2 exploratory summaries:

```powershell
python scripts/summarize_runs.py runs/YOUR_RUN_ID
```

For DREAM 1 reviewer tables:

```powershell
python scripts/export_blinded_review.py runs/YOUR_RUN_ID
```

Give reviewers the original tasks and rubric. Keep private-condition-key.csv private until scoring is complete.

A validation-selected candidate can be checked in a new process with scripts/verify_candidate.py. That script verifies identities and produces a research-only report. It never merges weights or activates the adapter in another application.


## Current concept workflow

Use scripts/prepare_concept_run.py with explicit controller-template, model-directory, model-manifest and output-root arguments. It creates a new disposable copy, development-only concept inputs, configs and a run plan. scripts/run_concept_queue.py HUB then qualifies the copied controller, runs current ML tests, validates plans and containment, and inhibits sleep during the bounded model queue. It stops on a failed qualification, resource block, invalid output or welfare pause; it never automatically resumes.

The default concept configurations use a common 4,096-token generation cap and sampled decoding at temperature 0.6, top-p 0.95, top-k 20. Start with the four-response smoke qualification before the 12-response pilot. The first comparison requires no steering vector. The separate steering configuration requires a common pinned vector and a documented manipulation check.

After completion, run scripts/summarize_concepts.py RUN_DIRECTORY NEW_ANALYSIS_DIRECTORY. It preserves originals, exports only final answers for blinded review and writes a separate private condition key. Quality scores stay pending until reviewed under document 13. Keep the raw reasoning for audit and welfare review, away from quality raters.
