# Frozen-text integration of temporal observation coverage (V1.15.0): frozen plan

- **Brief:** `FROZEN-TEXT-TEMPORAL-INTEGRATION-BRIEF.md` (copy in `design/BRIEF-copy.md`). Development study.
- **Freezing.** This plan is hashed in `config/FROZEN-PROTOCOL.json` before the main collection, together with the source, the input commitments, the exact call counts, the model configuration, the validation results and the smoke results. Amendments go to `config/AMENDMENTS.md` and keep the preceding version.
- **Predecessor.** 1.14.0 was committed and pushed as `8378e1e`, with reporting notes N1 and N2 (`6fadc9f`) in `Code/ERRATA/1.14.0-dependency-query.md` and the 1.14.0 hub `ERRATA.md`. Those notes cover:
  - fee counts: 39 facts over 37 copies; 28 for the recovered successes, 11 for the no-gain copies, 9 for the insufficient copies;
  - d06/B, where the loss equals the added fee;
  - how to read the frozen label: "lower utility than BASE".

  **Provenance qualification, kept prominent.** The 1.14.0 scored run is the frozen one. Its main allocation had earlier been executed once in a scratch folder for plumbing; only row counts were inspected, and the outputs were deleted unread.

  For this study, plumbing used only:
  - test-only fixture worlds;
  - the disjoint smoke worlds, with *fake* replies, in a scratch folder that was deleted afterwards;
  - old inspected panels (1.14.0, and the stored 1.11.0 replies).

  The new main panel is not executed before the freeze.
- **Source.** `Code/DREAM-project-1.15.0-frozen-text-integration-20261105` is 1.14.0 plus:
  - `src/tempo/textdep.py`: the FTX-v1 channel-aware Q0, S2 and selection, the runner, the reference wrappers and the channel builder;
  - `src/tempo/ftxgen.py`: the allowlisted text inputs;
  - `scripts/ftx_{generate,validate,evaluate,analyze}.py`;
  - `tests/test_ftx.py`.

  Every 1.14.0 file is byte-identical, including `depquery.py`, `timing.py`, `freshness.py`, `freshref.py`, `text_channel.py`, `repair.py`, `assertions.py` and `scripts/tempo_run.py`.
- **Tests.** 193/193 temporal tests pass: 185 inherited plus 8 new (`test-results/tests-1.15.0.txt`).

## Question
Does DEPENDENCY still improve utility over BASE when the same frozen model interprets each past report from prose, instead of the engine receiving its structured meaning?

Only the past-report channel changes. These stay structured and unchanged:
- goals and action rules;
- the sensor registry and sensor receipts;
- the public transition declarations and the fixed activity window;
- the executor.

The model does not infer dynamics or plan. This tests the integration of a language interface with a supplied temporal engine.

## Fixed from 1.14.0 (unchanged code)
- **BASE** is P2's Q0 (cap 2). **DEPENDENCY** is Q0 plus D in registry order up to the cap. Selection uses the pre-query support S2 at t = 2.
- **Clock.** One reliable batch is measured at t = 2 and received at t = 4; the decision and action are at t = 4 for every arm, including zero-query arms. Activity happens only in 0 < t < 2, and the world is stable afterwards.
- **Planner.** The cheapest guaranteed menu candidate, with no utility opt-out.
- **Utility.** `U = 10·success − action_cost − 3·invalid − queried_facts − 4`.
- **RANDOM_EXTRA** is omitted; its old regressions are kept (validation 6a).

## Channel threading (FTX-v1)
Each channel's own evidence drives all three stages:
1. **Q0:** `freshness.p2_request(pub, gc, channel)`.
2. **S2 and selection:** `textdep.selection_for`. This is depquery's rule with the channel passed to `engine_from`.
3. **Post-query support and plan:** `textdep.run`. This is `timing.run` line for line, with the channel passed to `engine_from`. Sensor readings go into that clone's own log and ledger.

The reference gets the same evidence: `freshref.reference_for(..., channel)` and `textdep.selection_reference`, which uses an exhaustive S2.

Text clones receive a public copy with **no structured reports** (`reports = None`). The shared items G, menus, invariants and registry come from the public definitions.

**Channel builder.** It is `text_channel.build_channel` with adapter-v1 unchanged (`text_channel.adapt`, the 1.8.2 normaliser, M1 and M2). There are two plumbing changes, neither semantic:
- the input lists must have equal length;
- an unprocessed report takes its reception time from the public call metadata, not from the gold record.

Malformed, rejected or unmapped replies enter as pending evidence. Nothing is repaired against gold.

**Pre-declared resource rule.** On a text channel, a projection exceeding the frozen limits (4096 states, 5 s) gives no support (`limit_exceeded`) and a decline, logged and counted. On the structured channel the same event is a software failure.

## Panel and calls (committed; `data/COMMITMENT-*.json`)
- **Main panel `ftx`:** 24 fresh worlds (12 per domain), seed 20261230, pools new. It uses the **1.14.0 allocation unchanged** (`depgen.ROWS`). Validation 4 confirms that the per-copy structure (row, goal, e, random-subset count, \|Q0\|) is identical to 1.14.0 for all 48 changing copies.
- **Redraws:** 9, all "no admissible m2 for goal B" (the existing assembly rule). No redraw was for prose and none for call count.
- **Smoke panel `ftxsmoke`:** 4 disjoint worlds (`depgen.SMOKE_ROWS`), seed 20261231.
- **Exact extraction calls:** **main N = 144** (6 reports in each of the 24 worlds), under the ceiling of 192; **smoke 25**, under the ceiling of 32. **Total scheduled: 169**, under the ceiling of 224.
- **Prompt and call hashes:** main calls sha256 `34c38f65…6cb`; smoke calls sha256 `468a8821…bd8403`; per-call `user_sha256` in the calls files.
- **Shared stream.** One goal-blind extraction stream per world is shared by every text clone. Goal, selector and environment clones create no calls.
- **Prompts.** The frozen 1.8.2/1.9.1 prose instruction (`text_channel.prompts`): header, rules, fixed facts, earlier prose reports as raw-text context, the new report, the v0.2 schema and the prefix field/value registry. Prompts come from an allowlist: public records (rid, kind, status, event_at, received_at, payload) and the renderer seed. They contain no goal, declaration, tape, truth or label (validation 3).
- **Model.** Qwen3-8B, revision `b968826d9c46dd6066d109eabc6255188de91218`, BF16, CUDA, thinking off, greedy, 256 output tokens, input cap 8192. Retry is limited to one infrastructure retry (`retry_limit` 1, the recorded 1.11.0 configuration). **There is no content retry.** Validation 7 checks the configuration equals 1.11.0 `stage-main.json`.
- **Ingestion.** It finishes before the simulated window. Real latency, tokens and wall time are logged separately from virtual time.

| Dimension | Values |
|---|---|
| Worlds × goals × environments × channels × selectors | 24 × 2 × 2 × 2 × 2 = **384 decision trajectories** |
| Extraction calls | **144** main, 25 smoke |
| CPU verification runs (not observations) | perfect-channel and gold-poisoning clones (2 × 192), leakage (four tapes per list, changing) |

## Gates
**Software and readiness gates.** Any failure means stop, preserve, and repair under a new version.
- **S1.** Support, candidate classes and choice equal the independent reference *given the same evidence*, on both channels.
- **S2.** On the structured channel, the actual state is in support and there is no invalid attempt, false completion or limit.
- **S3.** The frozen selector rule holds on each channel's evidence: Q0 preserved, cap 2, registry order, and agreement with the independent check. Structured stable copies are never augmented.
- **S4.** The perfect-extraction channel reproduces the structured Q0, S2, fields, support, choice and outcome. Poisoning the gold report container changes no text result.
- **S5.** Shared clock and fees; receipts at 14 and 16 in each clone's own context; history, provenance and log preserved; invariants; cost identity; identical actual pre-action state and common-field readings within each world and environment; field lists independent of the hidden tape, and identical readings giving identical beliefs and choices; complete channel lengths.

These checks also passed before collection:
- 1.14.0 structured regression, 272/272;
- 1.14.0 perfect-channel regression, 192/192;
- replay of the frozen 1.11.0 adapter on 144 stored replies, 24/24 streams identical;
- the allowlisted records re-map exactly to the structured reports;
- `check_equivalent` on every rendering;
- pre-sensor perfect parity on the main panel, 96/96.

**Measured outcomes (not gates).** These are results of the experiment:
- parse, mapping and rejection failures, and pending records;
- an empty, conflicted or incompletely represented S2;
- wrong settled claims and actual-state exclusion;
- receipts incompatible with the parsed set;
- lost success, false completion, invalid actual attempts, unnecessary queries and interpretation-caused utility loss.

They never cause a world to be removed, content to be retried or repaired, or the projection to be relaxed. Text stable contrasts need not be 0.

## Outcomes (fixed now)
- **Primary:** changing; text channel; per world, the mean over goals of U(DEPENDENCY) − U(BASE). Fees are charged.
- **Secondary:**
  1. structured DEPENDENCY − BASE on the same worlds (calibration; it need not reproduce +2.4583);
  2. interface loss, text − structured, for DEPENDENCY and for BASE;
  3. the change in augmentation benefit, (D − B)_text − (D − B)_structured;
  4. stable contrasts and losses;
  5. text/structured agreement on Q0, S2, fields, support, plan, outcome and utility, with every divergence traced through extraction errors → Q0 → S2 → query → post-reading support → plan → outcome.

  Results are also reported per goal and per domain.
- **Query effects** within each channel are reported as: success gain; success loss; same success with a plan or cost change; or no decision change. Added *facts* are counted alongside copies, and "lower utility than BASE" is reported separately.
- **Extraction audit.** The deterministic scorer (`contract_validate.score_record`) reports structural acceptance, exact denotation, coverage, wrong status and spurious atoms, by gold kind. There is no model judge.
- **Statistics.** Domain-stratified bootstrap, 10,000 resamples, seed 20261105; **n = 24 worlds**; intervals are descriptive. No noninferiority margin.

## Interpretation (fixed now)
- If a software gate fails, report the defect and stop; no benefit claim is made.
- If the complete text primary is positive with its interval above 0, the relative utility benefit survived this language interface under the stated dynamics and costs.
- If it is inconclusive or negative, the result stands as is, and the channel failures are diagnosed without wording repair.
- Invalid attempts and false completions are reported beside utility. A positive contrast together with such failures is a qualified cost result.
- Structured benefit or a small text loss never substitutes for the text primary. Nothing here establishes learned dynamics, optimal acquisition, an unknown quiet period or real-time operation.

## Stages and stop
1. Validation: `phase0/` (main) and `phase0/smoke/`. PASS.
2. GPU smoke: 25 calls, then CPU evaluation and analysis. Smoke checks execution and the preservation of invalid outputs, with no accuracy threshold and no tuning.
3. Freeze: source, plan, analysis, commitments, call counts, model configuration, validation, smoke, and a main wall-time ceiling = 3 × the smoke rate × 144 (the runner's own `max_seconds` stays the 1.11.0 value of 1800 s).
4. Main collection: 144 calls, no content retry. An incomplete run is preserved and reported as incomplete.
5. CPU evaluation with `--require-freeze`, then analysis, then `REPORT.md`.

**Stop after the report.**
