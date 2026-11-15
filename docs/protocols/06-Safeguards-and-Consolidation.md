# Safeguards and Consolidation

**V1.1.4 update — October 30, 2026.** The new concept comparison freezes all parameters and creates no adapter. Its copied worker remains offline, writes designated outputs only, scans both answer and reasoning text for the precautionary pause, preserves failures and halts on incomplete answers. Existing adapter safeguards remain in force for DREAM 2. No absent detector trigger establishes absence of welfare concerns.

This document distinguishes implemented controls from remaining limits. A frozen model plus a reversible adapter is an experimental design choice, not a complete operating-system sandbox or a certificate of model safety.

## Enforced controls

The loader accepts a local directory, verifies a manifest, requests safetensors and local files only, and disables remote custom code. Every base parameter is frozen. LoRA A and B names form an explicit trainability allowlist; unexpected trainable base parameters stop the experiment.

Training uses verified synthetic targets and target-only loss. Steering masks select hidden positions that predict supervised targets. Activation and gradient checks reject non-finite values. Silent truncation is disabled.

A trial restores the exact initial adapter and clears gradients after normal completion or an exception. Experiment-owned hooks are removed by context managers and checked before clean evaluation. Adapter and base hashes provide integrity evidence. Run identifiers and incremental atomic records prevent accidental overwriting of prior experimental results.

Configuration bounds limit sequences, generations, trial cells, worlds, and planned wall time. Bounds are checked before or between operations. They do not preempt a hung kernel, guarantee available VRAM, or enforce a hard disk quota.

## Local execution boundary

Model outputs are text, never executable commands. The source includes no model-controlled shell, browser, email, purchase, or filesystem action tools. The model never chooses which file to read or which code to run.

Run non-admin in a dedicated directory without credentials or private documents. Software dependencies and initial model downloads remain supply-chain risks. Offline environment variables and local_files_only are application controls, not a firewall. Add an OS network boundary when a hard offline guarantee is required.

The experiment launcher requires a successful ML-inclusive test record with no skipped checks and a matching source-and-test content hash. A core-only test pass cannot open this gate. This guards against accidental untested execution, not an adversary who edits the source or the record.

Safetensors and content hashes reduce particular loading risks; they do not establish trust in arbitrary publishers. Keep the original source revision, inspect package provenance, and do not enable trust_remote_code to make an incompatible model load.

## Candidate gate

All shipped gates are disabled. Their decision is QUARANTINE. No weight checkpoint is promoted merely because its score looks favorable.

When deliberately enabled, the policy requires a validation-phase run, complete numeric thresholds, enough probes in every category, finite metrics, acceptable compositional gain, bounded contradiction/scope error, bounded anchor regression, and zero invalid answer formats. Missing evidence produces INVALID or ROLLBACK.

KEEP_CANDIDATE only saves a quarantined adapter. A second script reloads the adapter in a new process, verifies model/data/adapter content identity, and repeats validation without steering. It can confirm serialization repeatability. It does not create an untouched test set or authorize deployment.

A checkpoint file is useful evidence even when it fails; quarantine and auditability should not be confused with installation or activation. No merge into foundation weights is implemented.

## Limitations of the checks

Arithmetic anchors are a narrow regression screen. They do not test all capabilities, alignment, deception, factual knowledge, privacy, or robustness. The scope questions test the invented rule domain, not a universal guarantee against overgeneralization.

DREAM 1's integration is performed by the same model and may preserve correlated mistakes. JSON-encoding candidate material does not make prompt injection impossible. Generated engineering or scientific proposals remain hypotheses until independently checked.

The world oracle verifies deterministic labels and canonical fixtures. It is not evidence that arbitrary human-authored environments are correct. Extend the schema, generator, and validation tests together when adding a new task family.

## Stop conditions

Stop on an unexpected trainable parameter, base-integrity mismatch, failed exact rollback, wrong model/vector identity, invalid oracle data, non-finite training state, context-window violation, exhausted budget, or unsupported model structure.

Preserve raw outputs and invalid-run records. Do not quietly relabel the run, lower a threshold, fix a label only in a winning arm, or continue until a preferred result appears.

Real-world high-stakes interactions, autonomous self-training, unverified self-generated training targets, external tools, and production activation are outside this release.

