# Implementation and Testing — V1.3.1

Current source passed 81 tests with 0 failures, 0 errors and 0 skips in the local ML environment. 13 plans passed without loading a model. Machine-readable reports are in test-results/latest.json and test-results/release-qa.json.

The ML tests use tiny random Qwen2 fixtures. They exercise target-only loss, masked intervention, allowed adapter parameters, updates and rollback. They do not establish Qwen3 reasoning-format compatibility or scientific effectiveness.

V1.2.0 checks cover the decategorization study: smooth and linear trip curves in absolute tokens (rise, plateau, fall, zero tail), bit-for-bit preservation of the legacy curve, signed generation steering that flips the activation change on a tiny Qwen2 block, a recorded trace and come-down flag through real Hugging Face generation, named contrast poles, direction-kind binding of vector artifacts, the hot-to-cold temperature processor (temperature before top-k/top-p, with a trace), config bounds and required zero-dose and two-step controls, strict KEEPERS and sober-pass parsers, reasoning off in every arm, an unsteered sober pass, and the blinded export. V1.3.1 shortens the trip curve to fit observed answer lengths and copies the contrast files into the worker's data view; the 1.2.0 smoke and vector qualification are the only exact-model decategorization evidence.

Inherited checks cover exactly five association objects, duplicate and malformed output rejection, paired prompts and decoding, EOS-qualified direct JSON, preservation and stopping on incomplete answers, unique numeric probes, plan-only world caps, and source evidence covering launchers.

The concept runner freezes model weights and creates no adapter. Each response uses a fresh context/cache. The primary contrast is reasoning on versus off at zero steering, with equal prompts, seeds, sampling and caps. Schema validity is separate from semantic quality. Ratings stay pending until independently reviewed.

Evidence hashes cover src, tests, scripts and dependency declarations. Per-run records separately identify model, data, configuration and any vector. Hashes detect changes; they are not authenticated security attestations.

See document 13 for the fixed development protocol, document 14 for the older pilot's limitations, and document 16 for the exact-model comparison status/results. No public registration, model merge or deployment is implied. Previous versions and runs remain preserved.
