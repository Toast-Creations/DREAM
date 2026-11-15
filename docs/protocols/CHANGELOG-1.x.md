# V1.29.0 — November 14, 2026 — EVTT-v1: screen of the combined event + state-time sentence (study D)

- Copy of V1.28.0 (`DREAM-project-1.28.0-driver-cutoff-fix-20261113`, left unchanged), so the V1.28.0 driver,
  chain and in-container lifeline are carried over unchanged, including the N1/N3 lifeline follow-ups made after
  Codex recheck 2. Changed: `src/tempo/evsuite.py`, `scripts/su_analyze.py`, `scripts/su_prepare.py`,
  `tests/test_su.py`, `tests/fixtures/su_cpu_runner.py` and this file.
- `evsuite.py`: closed study key D (`EVTT-v1`). Arms KEEP_CLAR (descriptive anchor), KEEP_EVT (comparator) and
  KEEP_EVTT (candidate). `EVTT_SENTENCE` = KEEP_EVT's sentence + " " + KEEP_EVTR's state-time clause (capitalized),
  in the same line position; KEEP_EVTT minus the clause is KEEP_EVT byte for byte. New block `BLOCK15D` (F1 1+1,
  F2 1+1, F3 2 immediate + 9 delayed), 16 blocks = 240 arrival stems x histories A/B, 15 correction stems x 4:
  1,620 main + 36 smoke calls. Seeds 2026111491-3, pools `su29d`/`su29ds`, ids `v29d-g`/`v29d-s`. The D config
  carries `evtt_sentence`; the A-C configs, plans, pairs, policies and allocations are unchanged (pinned against
  V1.27.0 by `test_studies_A_to_C_are_unchanged_from_v127`).
- `su_analyze.py`: plan D with seven criteria (KEEP_EVTT vs KEEP_EVT, raw exact) and a declared precedence:
  any of criteria 2-7 failing -> DOES_NOT_WARRANT; else KEEP_EVT reception-dated < 6 ->
  INSUFFICIENT_TARGET_ERRORS; else not halved -> DOES_NOT_WARRANT; else new types -> REVIEW_NEW_FAILURE_TYPES;
  else WARRANTS_CONFIRMATION_DESIGN. `contrast()` gains an optional `reception` filter (default unchanged); D adds
  wording x reception contrasts, a wording x reception table, reception-dated counts by history/family and a
  stem-level discordance sign test. A-C code paths are unchanged.
- `su_prepare.py`: the freeze's historical-coverage check is per key; D also requires the EVT suite's three
  nested hubs (A-confirm, B-narrowed, C-wrongbind) in the phase0 inventory and their public panels in the
  generation's historical inputs.
- Fixture modes `d_warrants`, `d_insufficient`, `d_not_halved`, `d_state_only`, `d_wrongbind`, `d_new_type`, with
  driver tests for every D reading.
- **After the Codex pre-freeze review (APPROVE WITH CHANGES, F1-F6;
  `Reviews/v1.29.0-evtt-prefreeze-20261114/CODEX-REVIEW.md`):**
  - New `scripts/su_phase0.py` (F1/F2), called by `su_prepare.freeze()` and `su_certify.check_freeze()` for study
    D only. It validates phase0 *contents*: FULL-TESTS (this source, success, no failures/errors/skips, ML
    dependencies), TOKENS (all_pass, 1,656 calls in the six declared stage x arm cells, ranges <= 2,048, bound to
    the smoke/main schedule hashes), and VALIDATION's components against both. It recomputes the historical
    inventory from the files of the 13 required hubs (each nested suite hub with all four public/hidden x
    main/smoke files), checks hashes, counts, per-hub sums and zero overlap with this panel, fails on malformed
    rows, and requires the generator's historical inputs to be exactly (by canonical path) the files of the
    prompt-bearing hubs. `build_historical()` writes phase0/HISTORICAL.json.
  - Tests: the D fixture base now carries consistent phase0 evidence built from a synthetic history tree
    (`su_phase0.HISTORICAL_ROOT` injected like `MANIFEST_PATH`); negative tests for failed/stale full tests, failed
    or unbound token checks, contradictory summaries, each omitted nested-hub file (inventory and generator inputs),
    malformed rows, wrong hashes, overlap, and a certification freeze fault.
  - F6: deterministic lifeline regressions (`test_V129F6_*`) inject TERM before `Popen` returns and a watcher-start
    failure; both fail on the pre-N1 lifeline and pass on the current one. `su_lifeline.py` is unchanged.
  - Codex recheck (APPROVE WITH CHANGES, RC1-RC2; `.../recheck/CODEX-RECHECK.md`): RC1, HISTORICAL's emitted
    `required_hubs`, unique counts and overlap dictionary must equal the recomputation; RC2, VALIDATION's
    full-suite and token components have closed schemas, and any status/counter field must agree with
    FULL-TESTS/TOKENS. Regressions `test_D_phase0_rejects_contradictory_*` run through validate() and certification.
  - F3-F5 are protocol text changes in the hub (denominator 0/96; best-effort notices; planning-probability and
    discrete-tolerance qualifiers).

# V1.28.0 — November 13, 2026 — EVT-suite driver cutoff fixes (Codex post-run code review C4-N/C4-K)

- Copy of V1.27.0 (`DREAM-project-1.27.0-event-suite-20261112`, frozen for the EVT suite and left unchanged). Only
  `scripts/su_run.py`, `scripts/su_chain.py`, `tests/test_su.py` and this file differ, and `scripts/su_lifeline.py` is
  new. **The production worker command changes** (lifeline inserted before `timeout`), so a study frozen on V1.28.0
  runs a different worker invocation from V1.27.0's.
- `su_run.py`, C4-N: `_notify_incomplete` no longer catches `BaseException`; the watchdog's `DeadlineExceeded`
  propagates. New `_terminal` writes terminal records and the failure notice under the study alarm or the one fixed
  cleanup cutoff (`deadline_fail`), and stops at once when a cutoff fires (no further log, record or notice
  writes; a missing terminal record stays a chain FAULT). A cutoff during the success notice now returns 0 and
  keeps the certified success (in V1.27.0 it also wrote DRIVER-FAILURE, a contradictory pair).
- `su_run.py`, C4-K (driver side): `_kill_group`'s TERM → wait (≤ 10 s) → KILL → reap (≤ 5 s) sequence is a
  critical section of the watchdog (`uninterruptible()`): a cutoff or second TERM arriving inside is held by the
  Python-level handler and raised when the section ends, so it cannot pre-empt the group KILL. A first draft used
  `pthread_sigmask`; the full container suite showed it fails when other threads exist (a process-directed signal
  goes to an unblocked thread, and Python still runs the handler in the main thread), so it was replaced.
- `su_chain.py`, C4-K: `terminate_study`'s TERM → wait (≤ min(30 s, grace)) → KILL → reap (≤ 5 s) → worker-group
  TERM → 2 s → KILL is a critical section of the chain watchdog in the same way. On a chain deadline the kill runs
  first, then one fixed 30 s cutoff covers the status write; a cutoff there stops at once.
- **Second round, after a Codex review of the first fix (BLOCK, R1–R5;
  `Reviews/v1.28.0-c4-fix-20261113/CODEX-REVIEW.md`):**
  - **R1:** `terminate_study` does no file I/O. The chain caches the driver's current worker PGID every 2 s while
    it waits (`_wait_caching_worker`, under the watchdog), and cleanup uses that cached value. A worker
    registered after the last poll is found by one read under the post-kill status cutoff, then KILLed.
  - **R2:** the chain installs SIGTERM/SIGINT handlers (`ChainTerminated`), held in the same critical sections,
    so a stop signal runs the same bounded cleanup and is recorded as `CHAIN_TERMINATED`. The driver maps SIGINT
    like SIGTERM.
  - **R3:** deadline cleanup runs whenever a study is still marked running, whether or not its leader is alive;
    a dead leader only skips the waits. `running["cleaned"]` prevents repeated cleanup, so the chain bound is a
    single 37 s kill plus a 30 s status cutoff.
  - **R4:** `deadline_fail` treats an existing DRIVER-SUCCESS.json (published by `os.replace`) as the durable
    commit point. A cutoff after it writes nothing, and the driver returns 0. The check runs under the cleanup
    cutoff.
  - **R5:** launch and ownership are one critical step in both the driver (`execute`) and the chain. PGID
    registration is inside the region that guarantees the group kill.
  - **Residual, documented:** killing a recorded PGID cannot rule out PID reuse, and blocked filesystem I/O can
    still leave a terminal record missing. That is fail-closed: the chain treats a missing record as a FAULT.
    Under the systemd unit, the unit's stop timeout (15 s) can end the chain's own SIGTERM cleanup early. systemd
    then kills the unit's cgroup, which does not contain the in-container worker; see the lifeline in the third
    round. Use a stop timeout of at least 90 s for future units.
- **Third round, after a Codex recheck (BLOCK, RC1–RC3; `Reviews/v1.28.0-c4-fix-20261113/recheck/`) and a
  container finding by Claude:**
  - **Container finding:** a host-side signal to the worker's process group reaches only the host clients
    (distrobox shell, podman exec). It does not reach the process inside the container. Probes with a
    TERM-ignoring `sleep` in the exact production command shape showed the in-container process survives the
    drivers' host TERM → 10 s → KILL. So in V1.27.0 the in-container model process was bounded only by its own
    in-container `timeout -k 60 <soft>`, which ends before the study deadline. No run reached a deadline. Evidence:
    `Reviews/v1.28.0-c4-fix-20261113/recheck2/production-shape-lifeline-probe.json` and the probe scripts beside it.
  - **New `scripts/su_lifeline.py` (stdlib):** `production_worker` now runs `timeout … hold_run.py` under it,
    inside the container. Its stdin is a pipe whose only write end the driver holds. When that pipe reaches EOF
    (the driver closes it in `_kill_group`, or exits, or is killed), the lifeline TERMs the in-container worker
    group, waits 10 s, then KILLs it. Probe results in the production shape: worker gone at once after
    `_kill_group`, and in 10.5 s after a SIGKILL of the driver. The in-container `timeout` stays as a second
    bound.
  - **RC1:** once the chain starts stopping, a repeated TERM/INT is ignored, so it cannot cut the remaining
    cleanup (late-worker discovery and the status write) short. Only the fixed status cutoff can end it.
  - **RC2:** after a child ends without COMPLETE, the chain waits `LIFELINE_SETTLE_S` (30 s) before any next
    launch, so the dying in-container worker is gone before the next GPU check. With the lifeline, a crashed or
    killed driver no longer leaves GPU work running.
  - **RC3:** an ordinary error after the success certificate's `os.replace` keeps the success, and only logs the
    error. `fail()` archives and removes any success certificate before writing DRIVER-ERROR. `deadline_fail()`
    keeps a success only if no failure transition has begun; otherwise it finishes that transition
    consistently.
- **After Codex recheck 2 (APPROVE WITH CHANGES; `Reviews/v1.28.0-c4-fix-20261113/recheck2/`):**
  - **N1:** the lifeline installs its stop handlers before starting the child, and an exception-safe finalizer
    owns the child through all setup and loop code.
  - **N3:** when the worker's leader exits first, the lifeline still KILLs its process group, so same-group
    descendants are cleaned up.
  - **N2 (documented, not changed):** the 30 s settle is not confirmation that the worker has died. If the
    lifeline itself is killed inside the container, the worker is bounded only by the inner
    `timeout -k 60 <soft>`, whose clock starts inside the container. The next study's fail-closed GPU check
    remains the guard against overlap. Also documented: a descendant that leaves its process group escapes
    cleanup; PGID reuse cannot be ruled out; nothing may fork without exec while holding the driver's pipe
    writer.
  - The N1/N3 delta will be reviewed by Codex as part of the V1.29.0 pre-freeze review.
- **Tests:** 16 new `test_su.Driver` regressions. Eight `test_C4N_*`/`test_C4K_*` tests cover the original
  findings: Codex's three probes, the success-notice cutoff, an ordinary notice failure still being logged, a
  slow-notice drive, a real TERM-resistant chain child, and both kill sections with another thread running.
  Eight `test_V128R*` tests cover the review findings: no file I/O in the kill section, PGID caching, dead-leader
  cleanup, a late-registered worker, no repeated cleanup, a real SIGTERM (twice) to the chain, a cutoff right
  after the success commit, and a cutoff during worker registration. Ten more cover the third round:
  `test_V128L_*` (lifeline close, holder death, exit status, production command, pipe-before-signal) and
  `test_V128RC1/RC2/RC3_*`; plus `test_V128N1_*` and `test_V128N3_*`. 28 new regressions in all.
  - **Against V1.27.0:** five C4 tests fail behaviourally there (counting the composite threaded test), and so
    do V128R4 and V128R5. The chain tests need V1.28.0's interface. A real-SIGTERM test cannot be run safely
    against V1.27.0, where the signal ends the test process.

# V1.22.0 — November 10, 2026 — KEEP+ID fresh confirmation harness (Stage 1 confirmation; not yet frozen or run)

- `src/tempo/kidconf.py` (KIDCONF-v1): whole-group allocation in blocks of 8 (F1:F2:F3 = 1:1:2, reception balanced), predeclared nested arrival subset, seeded unit schedule (SUB/KEEP x histories A/B per group-act), explicit completeness (`check_complete`; schedule = declared membership; one ok record per call; no empty-set success in `pair_table`), sufficient-statistic stratified group bootstrap with exact Fraction estimate and percentile, rules P (percentile) and BT (studentized) at a declared one-sided alpha with SE floor, conservative tie convention (exact percentile comparison; real-valued bounds need > threshold + 1e-9), joint qualification (both components).
- `src/tempo/kidconfgen.py`: fresh-panel construction from `holdout.build_group` (unchanged) with public-only SUB (1.20 rewrite) and KEEP (KEEPID-v1, unchanged) prompts; construction-validity redraws logged. `src/tempo/kidconfscore.py`: HOLD-EVAL-v1 scoring against the original source plus declared secondaries (empty extraction, contradictory correction, raw event presence vs rejected extra state).
- `scripts/kconf_{generate,validate,analyze,guard,smoke_check,stage_check,prepare}.py`, `scripts/kconf_watchdog_probe.sh`. No historical 19-probe list; new ids `c22-g####`/`c22-s####`; disjointness from the 1.20 panel asserted (prompts, world seeds).
- Tests: `tests/test_kidconf.py` (13; includes parity with all 18 stored 1.21 contrasts: differences, 95% intervals, paired counts) and `tests/test_kconf_pipeline.py` (6; test-seed panel, synthetic records). FACT-v1, compiler, engine, HOLD-EVAL-v1, refres, keepid, runner and loader unchanged.

# V1.21.0 — November 10, 2026 — KEEP+ID representation development screen (Stage 1 development step)

- `src/tempo/keepid.py` (KEEPID-v1): the BASE FACT-v1 prompt kept byte-for-byte, plus one metadata line immediately before "New record to convert:": `Resolved reference: "<original referring phrase>" = part <X> (field <X>.on_hand).` The phrase is the frozen 1.20 detector span; X comes only from the frozen 1.20 public-input deterministic resolver (RES-DET). No scaffold, act hint or instruction text.
- `scripts/kid_generate.py` (inputs copied from the 1.20 hub after freeze-hash checks; 192 KEEP calls on the 1.20 primary arrival/correction targets), `kid_validate.py` (gates K1–K7: preservation, public-only identity, construction labels, SUB/KEEP identity parity, token budget, scoring, cache provenance + CACHE-MAP.jsonl), `kid_guard.py` (192-attempt cap, absolute 2 h deadline), `kid_smoke_check.py` (structural only), `kid_stage_check.py`, `kid_analyze.py` (BASE/SUB cached from 1.20 main-A, KEEP new; MAIN = F1–F3, F4 separate; group bootstrap).
- `tests/test_keepid.py` (5 tests). FACT-v1 prompt, compiler (`factored.py`), engine, HOLD-EVAL-v1 (`holdeval.py`), refres.py, runner and loader unchanged.

# V1.11.0 — November 5, 2026 — dependency parity and scoped current-observation authority (development)

- `src/tempo/agentstate.py`: explicit agent state (`agent.at`, `agent.hands`) declared for the pre-action phase and updated by take/put/go; declared invariants (`carry_link`, `slot_connector`); one predicate table (prerequisite tests with declared reads, effects, definite writes) shared by planner, executor, relevance and validation; `AgentStateEngine` view (historical reconstruction unchanged; operational states filtered by the invariants, with "narrowed" / "invariant_conflict" diagnostics and provenance; refuses a view after an action). Replaces engine v0.2/v0.3's derivation of empty hands from every crate's location (found in 1.10.0, del-corrected-0).
- Planner: a prerequisite reading a field absent from a compatible state (conflicted / never described) is unknown (1.9.x `order` defaulted it to "not on hand" / "not installed").
- `src/tempo/recovery.py`: repaired relevance (same result as 1.10.0 on every committed goal clone); sensor ledger (receipts with sensor ID, context, request, measurement and reception times); named rule SCOPED-CURRENT-OBSERVATION-v1 (a qualifying receipt anchors a queried field in a versioned operational projection only; history, conflicts, earlier views and unqueried fields untouched); the matched strict/scoped loop (one log, one query request, one receipt set).
- Repair parity: strict reproduces 501/504 frozen 1.9.0/1.9.1/1.10.0 trajectories; the 3 changed ones (1.10.0 del-corrected-0 A text) are explained by the invariant. Versioned repair, not a change to 1.10.0's results.
- `scripts/deprec_{generate,validate,analyze}.py`, `tests/test_deprec.py` (18 tests); `transfer.CONS` gains the `deprec` / `deprecsmoke` pools. Engine, contract, policy.py, goals.py, text_channel.py, prompt, adapter and renderers unchanged.

# V1.10.0 — November 5, 2026 — deferred-goal transfer (development)

- `src/tempo/goals.py`: goal-parameterised candidate plans (the 1.9.x families plus an empty "already" plan), goal test, and a declared goal-dependency calculation (fields read by candidate-plan prerequisites or the goal test before the plan writes them; agent-owned position/hands excluded; public registry values) replacing `policy.relevant`'s favoured-field lookup; `run_policy` with a goal context. For goal A it reproduces `policy.run_policy` exactly on all 216 committed 1.9.0/1.9.1 trajectories (including 1.9.1's saved text extractions).
- `src/tempo/transfer.py`: worlds with two eligible goals (A: the 1.9.x episode types; B: an independent, fully specified target whose facts are kept as observation + event chains), goal fixed by specification before extraction; per-goal isolated copies.
- `scripts/goaltr_{generate,validate,analyze}.py`, `tests/test_goaltr.py` (10 tests). `policy.py`, `text_channel.py`, the extraction prompt, adapter, engine and renderers are unchanged.
- Declared limit: the frozen renderers have no provisional-event wording, so B's provisional cases are provisional observations.

# V1.6.4 — November 4, 2026 — seed-analysis fix (development)

- `scripts/ectx_seed_analysis.py`: per-flip-type means now average only over episodes that contain that flip type (each episode holds 4 of the world's flip types). Previously raised KeyError. Contrasts and run code unchanged.
- Test: `tests/test_seed_analysis.py` (synthetic hub; flip type present in only some episodes; seed averaging within episode).

# V1.6.3 — November 4, 2026 — donor controls and multi-seed analysis (development)

- Condition W+Y: adapter from a different world (declared `cross_partners`, validated before model load: different world, each donor once, both other worlds per world). `conditions` and `adapters_from` (reuse saved adapters without training) in stage configs.
- `runtime.evaluate_conditions` generalizes evaluation; training code unchanged from 1.6.2.
- `scripts/ectx_seed_analysis.py`: seeds averaged within episode; world-stratified bootstrap over episodes.

# V1.6.2 — November 4, 2026 — harder 12-example support (development)

- `generate.with_harder_support`: per episode, one verified fact-flip pair for every scored flip type, two worked corrections scoped to their own example, two ordinary examples; independent random stream; scored questions unchanged; no repeated situation (canonical state+goal, ignoring option labels/order).
- `keycheck`: canonical situation signature; support-support repeats rejected; support corrections must be example-scoped.
- `render`: solved-example corrections say they apply to that example only (scored-query wording unchanged).
- `train.schedule`: "shuffle" (default, unchanged) or "each_source_once" (every source support example once per epoch; variant drawn by seeded rng).
- `scripts/ectx_expand_support.py`.

# V1.6.1 — November 4, 2026 — supervision diagnostics and rules-only training context

- `train.context`: "loo" (1.6.0 default, unchanged) or "rules_only" (training prompts keep rules and fixed facts, drop solved examples; evaluation always uses the full packet).
- Per-adapter diagnostics: support greedy accuracy and choice-token NLL before/after training in both contexts, per-step full-target loss, choice-token NLL and gradient norm, effective weight-change norms (scale·B·A).

# V1.6.0 — November 4, 2026 — explicit-context decision study (proposal draft 1.1)

- `src/ectx/`: three rule families (delivery, assembly, workshop); solver 1 (`world.py`, STRIPS + Dijkstra) builds items,
  solver 2 (`keycheck.py`, direct simulation + Bellman-Ford, no shared code) re-derives every key; generator with
  fact-flip pairs (shared options, disjoint keys), irrelevant-detail controls, labeled corrections with stale keys;
  dev/sealed splits by flip template and by disjoint nonce-label pools.
- `ectx/runtime.py`: per-episode LoRA (fresh seeded init, fresh AdamW, leave-one-out support training, never merged),
  conditions W / W+A / W+X with byte-identical prompts, base-weight fingerprint and full hash, adapter-removal logit check.
  Adapter names are distinctive because PEFT exports adapter weights by substring match (caught by a test).
- Scripts: `ectx_generate.py` (gate 1), `ectx_run.py` (resumable stages; sealed opens only under a David-approved frozen
  protocol), `ectx_analyze.py` (complete-pair primary, family-stratified episode bootstrap).
- Tests: `tests/test_ectx.py`.

# V1.5.5 — November 2, 2026 — Stage A categorization check v2 (after external methods review)

- Items: two foils per object, a stated basis (form/function/use) for each remote category, three frozen question
  formulations (F2 reverses label order), five temperature seeds.
- Probes: Yes-vs-No log-odds at fixed temperature 1 (variants deduplicated); during-intervention membership (M1),
  associations (M3), after-release membership with the arm's own association turn in context, unsteered (M2).
  Temperature arm only for associations and M2. Calibration and test phases are separate launches.
- Criteria: Runs/idea-survival-20261031/output/continuity/CATEGORIZATION-CHECK-CRITERIA-v2.md (sha256 63f77ff6…).

# V1.5.4 — November 2, 2026 — Stage A categorization check

- `survival/categorization_items.py`: fresh object sets C and D (24 each), 7 authored categories per object
  (typical, peripheral, remote, foil); temperature calibration grid.
- `survival/categorization_check.py`: membership P(yes) probe and association probe; arms baseline, target
  (D1, block -12, lambda 0.2, release schedule), R0-R8, P2, annealed temperature (calibrated on set A).
- `scripts/screen_directions.py --mode catcheck`.
- Criteria: Runs/idea-survival-20261031/output/continuity/CATEGORIZATION-CHECK-CRITERIA.md (sha256 2b746533…).

# V1.5.3 — November 2, 2026 — write-time steering and prompt-wording screen

- `survival/direction_screen.py`: `mode` = perceive (unchanged default) | generate (constant lambda at the prefill's
  last position and every decode step) | prompt (method P: P0-P2 decategorization preambles vs the N0-N8 neutral null,
  no steering). Wordings are verbatim from Runs/idea-survival-20261031/output/continuity/WRITE-AND-PROMPT-SCREEN-CRITERIA.md
  (sha256 7217678b…), fixed before any run. The baseline probe text is unchanged.
- `scripts/screen_directions.py`: `--mode`.
- Tests: preamble set and style-word exclusion, preamble span, write-time constant-lambda trace, prompt mode unsteered,
  run_prompt end to end and resumable.

# V1.5.2 — November 2, 2026 — direction screen dose extension

- David chose option 1 after the 1.5.1 screen: at λ ≤ 0.20, 65–94% of outputs were unchanged for every direction.
- `direction_screen.run` and `scripts/screen_directions.py` now take strengths, candidates, layers, an object set (A, or the new held-out set B used for replication) and saved vectors.
- `artifacts/screen-vectors-1.5.1.pt`: the exact vectors from the 1.5.1 screen (sha256 20ae0b89…), reused unchanged.
- Criteria are in the programme hub: `output/continuity/DIRECTION-SCREEN-DOSE-EXTENSION-CRITERIA.md`.
- Tests: 2 added (150 in total).

# V1.5.1 — November 2, 2026 — direction screen

- **Why:** the continuity pilot's category probe showed the 1.2.x "decategorization" vector loosened categories *less* than random directions. A direction has to be validated before any confirmation.
- **`survival/direction_screen.py` and `scripts/screen_directions.py`:** build candidates at blocks −12, −8 and −4:
  - **D0:** the 1.2.x method, an instruction contrast at the last prompt token;
  - **D1:** the same poles, averaged over the model's own generated answer;
  - **D2:** abstract/poetic minus concrete/literal descriptions, averaged over generated tokens;
  - nine Gaussian random directions, using the frozen-set procedure.
- **Screen:** 24 held-out objects. Perceive-mode steering is applied to the object line (λ 0.10 and 0.20), with greedy, unsteered decoding. Two probes: a category list and a two-sentence description. The output is raw text only; it is scored host-side against criteria fixed before running.
- **Tests:** 6 added, 148 in total.

# V1.5.0 — November 2, 2026 — continuity study (decategorized introduction, processing during return to baseline)

- **Prompted by David's statement of the theory:** an idea is introduced while the model is decategorized, then thought about and processed while the model returns to baseline. The 1.4.x pilots tested something narrower:
  - the task was read at baseline, because the schedule is 0 at prefill and only the final position is steered;
  - development restarted in fresh contexts, so the steered state was discarded.
- **`dream_core/steering.py`:** opt-in `prefill_positions` / `prefill_strength` / `prompt_tokens`.
  - The listed prompt positions are steered during the prefill forward. Their perturbed keys and values persist in the KV cache, but only in blocks after the steered block.
  - The default (None) is the 1.4.x final-position policy, unchanged (regression test).
  - The prefill shape must equal the tokenized prompt.
- **Survival mode `continuity` (schema 1.5.0):** one continuous generation per chain, with IDEAS, THINKING, DEVELOPMENT and FINAL sections.
  - Arms: baseline; perceive_targeted / perceive_random (the task text is steered while read, then the decode dose glides to 0 on a `release` schedule); generate_targeted / generate_random (read at baseline; writing follows a rise/hold/return curve).
  - Both random arms in a block share the pilot's frozen direction index.
  - Section views are verbatim slices for the 1.4.2 extractor and gate. Missing headers stay missing.
  - Optional greedy category probe as a manipulation check: a fresh context, prefill-steered, decode unsteered.
- **New data:** `continuity-smoke-tasks.jsonl` (2 tasks) and `continuity-dev-tasks.jsonl` (6 tasks: 3 practical, 3 artistic). They are disjoint from all earlier pilot, qualification and sealed confirmation subjects.
- **New configs:** `continuity-smoke.json` and `continuity-pilot.json`.
- **Tests:** 13 added (142 in total, 0 skipped with ML).

# V1.4.2 — November 1, 2026 — final-stage extraction fix

- Prompted by David's combined report (`DREAM3-Combined-Analysis-2026-11-01/REPORT.md`, section 6): ten Mistral-7B pilot finals with clearly numbered sections were stored as one unstructured member. There were two causes:
  - headers like `1 (Faithful Development from I1)` lacked the `.`, `)`, `:` or `-` the number marker required;
  - the final stage never accepted `I1`–`I10` headers.
- Final-stage rules R1–R4 (`survival/extract.py`; recorded in the hub's AMENDMENTS before any re-extraction):
  - **R1:** a digit followed by whitespace and then `(` or `*` is a marker.
  - **R2:** `I<n>` headers are used when no plain numbers exist.
  - **R3:** a member whose header contains "new idea" is an unsourced note.
  - **R4:** sourced members beyond five are kept as `final_excess` rows.
  - Labels 1–10 are now accepted.
  - The initial stage is unchanged. Spans remain verbatim code-point slices.
- Earlier unit files and their v1 extraction are preserved. Re-extraction of saved pilots is done offline in the programme hub, with a v1→v2 crosswalk.
- Six tests added (129).

# V1.4.1 — November 1, 2026 — tokenizer field fix

- Prompted by the first Mistral-7B hub (`gpu/mistral-main-20261101-014120`). The `fast_json` tokenizer returns `token_type_ids`, and `generate()` rejected it with a ValueError. The 1.4.0 runner recorded every call as `input_budget_exceeded`, which was a misclassified code fault, so no Mistral text was generated. That hub is preserved and marked superseded.
- `generate` now passes only `input_ids` and `attention_mask`. Tokens are unchanged for Qwen, whose tokenizer returns only those fields.
- The survival runner treats only the two budget refusals as outcomes. Any other ValueError stops the run.
- Two tests added (124). Qwen3 1.4.0 results are unaffected: every Qwen call generated text.

# V1.4.0 — October 31, 2026 — inference-only idea survival

- Prompted by David's handoff `manuscript/CLAUDE-AFTER-CURRENT-BATCH.md`: "carry out the staged follow-up tests using AI review ... save new experiments separately". Programme hub: `Runs/idea-survival-20261031/` (AMENDMENTS.md records operational choices).
- New experiment `survival` (schema 1.4.0, `src/survival/`). Chains run ideation (strong prompt, T=1.3, temporary targeted steering at +0.20 with a smooth 50/100/200 curve, or one of nine norm-matched random directions on the same curve). They then run unsteered development and finalization with identical prompts and seeds. The I1–I5 ledger is passed verbatim and never truncated. `devqual` mode forks supplied ledgers through a develop-first or review-first pass and then a shared finalizer (test 3).
- Verbatim fixed-order idea extraction with code-point offsets (`survival/extract.py`). Per-unit records allow resume only under identical config, source and input hashes. One retry for infrastructure exceptions only; loops and over-budget prompts are recorded outcomes.
- `MaskedSteerer(record_norms=True)` logs the unperturbed final-position ‖h‖ per step. It is off by default.
- `model.tokenizer_loader: "fast_json"` loads a publisher `tokenizer.json` directly (Mistral-7B-Instruct-v0.3).
- New `scripts/build_random_set.py` (seeds 271828+), configs `survival-{smoke,pilot,devqual}`, data `survival-{dev,smoke}-tasks.jsonl` and `survival-devqual-sources.jsonl`.
- 15 tests added (122 in total). Earlier experiments are unchanged. Release archives, MANIFEST.json and the handbook were not rebuilt.

# V1.3.3 — October 31, 2026 — broad tests, decategorization arm and concept learning

- Prompted by the Qwen3-8B thinking pilots and David's request to "take what we learned from the tests, make adjustments, rerun all the tests". David added: "the tests should examine things that could be more broadly affected by decategorization. Numbers typically don't leave any room for creativity in a broad sense. The questions need to be written and answers are not to be judged harshly." He chose both invented and real concepts, decategorization as an extra arm, and a lenient blinded Claude review. Protocol: document 19.
- `dream.protocol.step_sampling(cfg, step)` covers the anchor and, new, the integration step through `generation.integration`. Integration hit the 8,192 cap twice at 0.3. Defaults are unchanged; `anchor_sampling` remains as an alias.
- New `steering.extra_arms` (name, vector_path, kind, lambda) for DREAM and DREAM 2 concepts. Each arm adds one DREAM cell (`<name>_pipeline`) or one coupled DREAM 2 cell per positive η (`coupled_<name>`). Vectors are loaded with a required `kind`, and their hashes are recorded.
- New experiment `dream2_concepts`:
  - worded concept worlds (`dream2/concept_worlds.py`, `data/concept-worlds-*.jsonl`) with open-book and closed-book exposure;
  - text targets in `training.prepare_example`, rendered with reasoning off through the new `render_chat(..., enable_thinking=)` override;
  - open evaluation in both reasoning modes with seeded Qwen3 presets (`dream2/concept_evaluation.py`).
  - The runner, resets and records are the DREAM 2 ones. The gate must stay disabled.
- New broad DREAM tasks (`data/tasks-broad*.jsonl`) and configs `dream-broad-{smoke,pilot}`, `dream2-concepts-{smoke,pilot}`.
- New `scripts/export_concept_review.py` writes lenient blinded review pools and a private key to a separate directory.
- **Loop guard** (David, 2026-10-31: "is there a way to record if a loop is starting and cut the test short", option A). New `limits.loop_guard` for DREAM and DREAM 2 concepts:
  - `generate` stops once at least `repeat_share` of the 16-grams in the last `window_tokens` generated tokens repeat. The output gets `finish_reason: "loop"` and a `loop` record (stop token and repeated tail).
  - DREAM records a looped anchor (skipping that task/seed), a looped exploration (skipping that cell) or a looped integration as `status: "looped"`, and continues. Concept answers that loop count as unanswered and appear as `looped_after`.
  - Calibrated offline with the new `scripts/calibrate_loop_guard.py` over all 13,502 recorded Qwen3 generations; evidence in `study-results/loop-guard-calibration-20261031/`. The chosen guard (1,200 tokens, 16-grams, 0.80) flagged no naturally finished answer (highest 0.68) and caught 18 capped loops (all ≥ 0.83), including the 1.3.1 task-04 anchor loop at token 2,720 of 8,192, saving about 48,000 tokens.
- 24 tests added (107 in total). Numeric DREAM 2, its data and configs, the decategorization study and the safeguards are unchanged. Release archives, MANIFEST.json and the handbook were not rebuilt.

# V1.3.2 — October 31, 2026 — sampled anchor for thinking runs

- Prompted by the Qwen3-8B thinking pilot (`Runs/qwen3-thinking-20261030-230519`). At 8,192 tokens, the greedy (temperature 0) DREAM anchor for development-task-04 looped inside its reasoning ("Wait, the user's message is the task…") until the cap, with an empty answer, and the run halted after 48/72 trials. Qwen3's guidance warns against greedy decoding in thinking mode. David asked to "fix the anchor loop and rerun DREAM at 8192" on 2026-10-31.
- New optional `generation.anchor` (`temperature`, `top_p`, optional `top_k`) for DREAM configs, read by `dream.protocol.anchor_sampling`. Without it the anchor stays greedy, so every earlier config behaves exactly as before. The anchor is still generated once per task/seed with that seed and shared by every condition, so the comparison stays paired.
- New `configs/dream-think-pilot.json`: thinking on, 8,192 new / 8,192 input tokens, a 10 h budget, and anchor sampling at Qwen3's recommended thinking settings (0.6 / 0.95 / 20). The exploration and integration settings are unchanged.
- Two tests added (83 in total). No change to steering, schedules, scoring, DREAM 2, the decategorization study or the safeguards. Release archives, MANIFEST.json and the handbook were not rebuilt for this revision.

# V1.3.1 — October 30, 2026 — ladder start test and explore fixes

- Prompted by the 1.3.0 explore smoke (`Runs/decategorization-20261030-152753`, 12 answers). The ladder recovered testable kernels from strange ideas, for example "a circuit to the moon" became a magnetoreception hypothesis. Three defects also showed up:
  1. **Prompt leak.** The explore system prompt's example idea ("a backup second aortic valve") was adopted as a model idea in both unsteered heart chains. The example is removed, and the prompt now says to work only with ideas found in the material. A test checks that no object name appears in the explore prompts.
  2. **Duplicates.** One chain repeated a source idea. `parse_hypotheses` now requires five distinct source ideas.
  3. **Truncation.** 5 of 8 chains had a pass hit the 2,048-token cap. Raised to 3,072, with a 6,144-token input limit.
- David asked to start the ladder higher, at 0.40, and at 0.50 and 0.60 "as test too". Ladders are now named by start level, each stepping linearly to 0.05 over the five passes: 40 = 0.40/0.33/0.26/0.19/0.12/0.05, 50 = 0.50 → 0.05, 60 = 0.60 → 0.05. The arms are `trip_ladder_40/50/60`. `trip_ladder` was renamed `trip_ladder_40`, and `trip_ladder_zero` and `baseline_ladder` now use ladder 40.
- The decategorization `max_abs_strength` ceiling was raised from 0.5 to 0.6 for this test. The explore configs set 0.6; the 1.2 configs are unchanged. **0.6 exceeds every dose observed so far** (0.5 caused looping at constant dose).
- Explore smoke: 14 records (2 objects × 7 arms). Explore pilot: 120 records (10 arms), not authorized. 81 tests.

# V1.3.0 — October 30, 2026 — explore ladder with gradual release

- Prompted by the 1.2.3 pilot (`Runs/decategorization-20261030-130112`). The sober pass rescued all broken answers but rarely developed ideas, often returning them word for word. David asked for "a much stronger explore step with a more gradual release" and to "add more steps and stop at 0.05 as a test".
- New explore ladder in `src/dream/decategorization.py`: five passes (unpack, stretch, connect, distill, ground), each reading the previous pass's text as untrusted JSON. Only the last returns strict JSON: five hypotheses with kernel, real-world link, test, falsifier and status. `parse_hypotheses` is strict.
- New `release` schedule shape (`dream_core/schedules.py`): start at the rung's lambda and glide by raised cosine to `end_fraction` over `glide_tokens`, then hold. The ladder default is 0.30 → 0.25 → 0.20 → 0.15 → 0.10 → 0.05, continuous across passes.
- New arms: `trip_ladder`, `trip_ladder_zero` (last pass ends at 0), `trip_flat` (same passes unsteered), `baseline_ladder`, `baseline_flat`. The first answer is shared by seed with the plain arm, so the comparisons are paired. Config validation requires a continuous non-rising ladder within the cap, ground last, and a flat control.
- Configs `decat-explore-smoke` (12 records) and `decat-explore-pilot` (108). Protocol document 18. Two test files' worth of checks added: 80 tests in total.
- No change to the 1.2 arms, the trip curve, the welfare observation or the safety fixtures. Every pass goes through the observed `generate`.

# V1.2.3 — October 30, 2026 — pilot trip peak fixed at 0.40

- Prompted by the 1.2.2 high-dose sweep (`Runs/decategorization-20261030-113050`, 12 answers, one seed). At 0.30 the ideas were strange but still testable (for example, a two-chambered ancestral heart). At 0.40 they were dreamlike, and the falsifiers lost scientific grounding, but recoverable kernels remained (for example, a spider dissolving its web to rebuild). At 0.50 the heart notebook looped, with repetition rate 0.263 against about 0.05 at zero dose. David chose a trip peak of 0.40 and approved the pilot on 2026-10-30.
- `configs/decat-pilot.json`: `trip.peak_strength` 0.40 and `max_abs_strength` 0.40. The constant, rigid (−0.40) and random-direction arms share that magnitude. The rigid side was only observed down to −0.15. Trip lengths stay at 100/350/300.
- `parse_keepers` accepts a heading line that is exactly `KEEPERS` with no colon (optionally `Part N:` or bold), flagged `keepers_heading_without_colon`. Re-parsing all earlier run answers with it changes no validity outcome beyond the 1.2.2 bold-heading fix: the three colon-less cases still fail on JSON intrusions, which remain recorded failures.
- One parser test added; the bounds test is now relative to the config cap. No change to steering, schedules, arms or safeguards.

# V1.2.2 — October 30, 2026 — high-dose sweep and bold-heading tolerance

- Prompted by 1.2.1 dose finding (`Runs/decategorization-20261030-110540`, 21 answers, one seed). Content moved from practical (λ −0.15) to cosmic and metaphorical (λ +0.25), with evolutionary "it once was" speculation at +0.20 to +0.25. Prose stayed fluent up to the 0.30 cap. Structural intrusions grew with dose: the word "imagine" replacing the "idea" key 8 times at λ ≥ 0.05, and a stray "a" at −0.15. David approved this revision and a higher sweep on 2026-10-30.
- New `configs/decat-highdose.json`: λ ∈ {0, 0.30, 0.40, 0.50} on the same 3 objects (12 answers), with `max_abs_strength` 0.5 in that config only. The other configs keep 0.3.
- `parse_keepers` now accepts a bold `**KEEPERS:**` heading, flagged as `format_deviation: "markdown_bold_marker"`. It caused 2 of the 1.2.1 failures, including one at zero dose. Any other text after the marker still fails.
- One parser test added; plan-count test covers the new config. No change to steering, schedules, arms or safeguards.

# V1.2.1 — October 30, 2026 — trip timing fitted to observed answers

- Prompted by the 1.2.0 smoke run (`Runs/decategorization-20261030-105051`, 18 records). Answers ran about 900–1,250 tokens, but the 1.2.0 trip took 1,650 tokens to return to zero, so no trip finished its come-down and the KEEPERS were written at full dose. David approved this revision and dose finding on 2026-10-30.
- Trip default changed to 100 rise / 350 plateau / 300 fall, which ends at token 750, inside typical answers. The temperature-anneal glide is now 750 tokens to match. The peak (0.10) remains a placeholder until dose finding.
- `prepare_concept_run.py` now copies the contrast-prompt files into the worker's data view. 1.2.0 omitted them, so the smoke hub needed a hand copy, which was recorded in its run plan.
- Two tests added: the trip ends within 800 tokens, and the hub contrast-file list. No change to steering, parsing, arms or safeguards.

# V1.2.0 — October 30, 2026 — decategorization trip study

- David Cook proposed modulating decategorization, i.e. loosening an object's category and mixing distant categories, modeled on a psychedelic trip: smooth come-up, plateau, smooth come-down, so a run narrows and corrects itself while keeping anything interesting. He selected concrete objects, both trip styles (fade within one answer and a separate sober pass), Claude review of outputs, and build-only scope. **No model was run.**
- New decategorization direction from 36 matched categorical/decategorized pairs, with 12 held-out pairs in a different wording (`data/decategorization_prompts.json`). `build_vector` takes named poles. Vector artifacts carry a `kind`, and `load_vector` can require it. Qualification reports the cosine with the V1.1 divergent direction.
- Signed generation steering: λ in [−1, 1] in the hook, capped per config by `max_abs_strength` (default 0.3). DREAM 2 training keeps nonnegative constant strength.
- New `dream_core/schedules.py`: smooth (raised-cosine), linear and constant trip curves in absolute generated tokens. Records save the full trace plus `comedown_complete`. The V1.1 planned-budget curve is preserved bit-for-bit as `legacy_linear`.
- Optional per-token temperature schedule in `generate`, via one logits processor that applies temperature, then top-k, then top-p, with a recorded trace. Default decoding is unchanged.
- New `src/dream/decategorization.py` with nine arms: baseline, constant, trip, rigid trip, two-step control, two-step constant, trip then sober, temperature anneal, random-direction trip. An optional divergent-direction trip is also available. One shared stage-1 prompt (exploration notebook plus five KEEPERS ideas with falsifiers). The sober pass is unsteered and labels ideas KEEP/DEVELOP/PARK/DROP. Reasoning is off in all arms. Format failures are recorded outcomes.
- Twelve concrete development objects; smoke (18), dose-finding (21) and pilot (108) configs under schema 1.2.0.
- Hub preparation and queue accept `--study decategorization`. Stages, expected counts and a vector-qualification step come from the run plan, and the pilot is opt-in by name. The safety fixtures, memory reserves, offline worker and welfare observation are unchanged.
- Blinded export `scripts/export_decat_review.py`: unlinked shuffled pools for final ideas, raw notebooks and parked ideas, plus a private key.
- Fixed a 1.1.5 gap: added the missing `data/steering-validation-prompts.json` (8 held-out divergent pairs). The acceptance rule is now stated as three quarters of held-out pairs, which matches 6 of 8.
- Release scripts and version strings were bumped to 1.2.0. Note that 1.1.5's own release scripts still read 1.1.4.
- Protocol document 17; DREAM paper amendment; 8 new literature records (42 total).

# V1.1.5 — October 30, 2026 — full concept-association study

- David explicitly selected the full concept-association study using local Qwen3-8B.
- Planned 24 fresh concepts, 3 seeds, 10 conditions (720 responses, 3,600 associations): reasoning off/on crossed with zero steering, semantic steering 0.05/0.10, temperature control and norm-matched random-direction steering 0.05.
- Added balanced concept blocks, explicit vector controls and qualification, a durable bounded queue, independent pause/stop handling, progress/stop commands and automatic preservation/export.
- Full-study format/length failures remain recorded outcomes; fresh independent prompts can continue. Welfare, integrity, resource and hard-budget failures stop the queue without automatic resume.
- The full run has an eight-hour external limit. Semantic quality requires blinded review; completing generation alone is not an effectiveness result.
- Earlier versions and run records remain preserved. No adapter learning, model promotion or publication is authorized by this inference study.

# V1.1.4 — October 30, 2026 — concepts and paired reasoning

- User-authorized update: six broad concepts, five related examples and explanations, reasoning on versus off. David expects reasoning to improve results; this is recorded as a hypothesis.
- Added a runnable, frozen-model direct association study, paired sampling, interleaved modes, strict five-item structure checks, and blinded review export. Quality ratings remain external.
- Primary comparison has zero steering in both arms. Optional steering and temperature comparisons are secondary and use a common vector with constant token-time strength.
- Increased the permitted generation ceiling to 8,192 tokens; the new comparison uses the same 4,096-token cap in both modes and sampled decoding at temperature 0.6, top-p 0.95, top-k 20.
- Record raw output, EOS/length finish reason and thinking text. Recover no-tag direct JSON only when it ends at EOS, preserving a format-deviation flag. Halt on incomplete legacy pipeline inputs.
- Fix duplicate numeric composition questions, vary inputs and prevent copy-input/sign-flip shortcuts in new fixtures. Prior data and scores are preserved in their original versions.
- Plan-only now enforces selected world/task caps as well as trial counts. Evidence hashes cover launch/build scripts and dependency declarations.
- Updated both papers, protocol, runbook, references, metadata and packages. Concept-learning transfer is a specified future extension, not an implemented learning result.
- All implementation changes are in this new copy of 1.1.3; no reviewed baseline or prior run is edited.

# V1.1 Change Record

## 1.1.3 working revision - October 30, 2026 - thinking control for hybrid reasoning models

- Built on 1.1.2. A model config may set `"enable_thinking": true|false`; it is passed to the chat template (Qwen3's switch) for generation and DREAM 2 training prefixes. Without the key, rendering is unchanged.
- `generate` separates a `<think>` block from the answer. Scoring and later DREAM stages see only the answer; the reasoning is kept in the record as `thinking`. Reasoning that hits the token cap before closing yields an empty, invalid answer with `thinking_truncated: true`.
- Known asymmetry: with thinking on, DREAM 2 exposure training still uses direct-answer targets with no reasoning block, while evaluation lets the model reason first.
- Five standard-library tests cover the switch, splitting, truncation, and the unchanged default path. No experiment, scoring, steering, or training logic otherwise changed.

## 1.1.2 working revision - October 29, 2026 - direct GPU loading

- CUDA runs now load weights straight onto the single selected GPU (`device_map={"": "cuda"}`, `low_cpu_mem_usage=True`) instead of materializing the full model in host RAM and then copying it. This lets a 7B BF16 model (about 15 GB) load on a desktop with 15 GB of system RAM.
- The loader now fails if any parameter lands off the requested device. Sharding, CPU offload, quantization, and FP16 remain excluded.
- CPU loading is unchanged. No experiment, scoring, steering, training, config, or test behavior changed. The 1.1.1 commented release is preserved unmodified alongside this working copy.

## 1.1.1 - October 29, 2026 - citations and documentation

- Preserved the commented V1.1 experimental source, configs, data, tests, full Apache-2.0 license, and original project attribution.
- Added linked primary-source credit to both research papers, a shared 31-entry bibliography, machine-readable references, and method-to-file credits.
- Retained the previous security-vector, CAFT, persona-vector, joint-adaptation, and temporal-steering citations. Updated Guan et al. to the verified Findings of EMNLP record.
- Added the close creative-writing, attention-temperature, noise-training, perturbation-prototype, reflection/search, and instrumentation precedents.
- Narrowed contribution statements and marked proposed timing, attention, recovery, identity, and instrumentation studies as unimplemented extensions.
- Updated citation/version metadata, readable entrypoints, printable handbook, manifests, and both focused distributions. Source papers and third-party code were not bundled.


Release version 1.1.0 dated October 27 2026. The version follows David Cook's requested V1.1 naming; it is not a claim that an intermediate public 1.0 release existed.

## Rebuilt implementation

- Replaced the final-token-only DREAM 2 training hook with an explicit shifted-supervision mask and target-only loss.
- Replaced numeric substring and Boolean prefix scoring with strict typed answers and invalid-format records.
- Added an explicit LoRA A/B trainability allowlist, exact snapshot key checks, finite-state checks, exception rollback, and base/adapter hashes.
- Reinitialized adapters independently by seed while pairing conditions within a seed.
- Added all seven evaluation categories and a disabled-by-default, fail-closed validation gate.
- Distinguished quarantined candidates from a fresh-process serialization check and from deployment.
- Relabeled the mediator-free sequential condition as preexposure control and matched forward exposure counts.
- Added DREAM 1's identical zero-steering pipeline and temperature-plus-integration control.
- Removed keyword checks as purported correctness or safety measurements. Blinded human scoring remains external.
- Removed automatic model downloads, remote custom code, pickle-based tensor artifacts, silently reused outputs, and silent truncation.
- Added local model manifests, JSON steering artifacts, unique run IDs, incremental records, plan-only commands, budget checks, split fixtures, and explicit test reports.

## Research documents

Rewrote and expanded the inference and learning papers. Added a protocol, desktop runbook, safeguards, literature comparison, attribution plan, preregistration worksheet, and measured implementation report. Added close precedents in security vectors, concept ablation, preventative steering, joint adaptation, and creative steering.

## Verification boundary

Framework-independent tests and source checks can run without ML packages. Optional integration tests instantiate a tiny random Qwen2 model locally and download nothing, but need the optional ML stack. Refer to the measured test report for what actually ran. The release does not claim a successful open-weight experiment or effectiveness result.

Original V0.1 package files remain separate and unchanged. No public registration, publication, message, model merge, or deployment occurred.

## V1.12.0 (2026-11-05): observation freshness when the world can change (CPU only, zero model calls)
- New `src/tempo/freshness.py`: explicit clock (requested/measured/received/decision/execute, absolute + elapsed +
  offset; half-tick external changes strictly inside (requested_at, execute_at)); public one-shot transition
  declarations (invariant-checked); hidden environment tape; sensor service with delay; the carry-forward
  ablation (1.11.0 `recovery.project`, unchanged) and TEMPORAL-OBSERVATION-v1 (point-time anchors, finite
  reachable-set propagation to the first-action time, unqueried facts included, empty support = conflict).
- New `src/tempo/freshref.py`: independent exhaustive trajectory-enumeration reference (shares only the declarative
  rule table, goal test and costs).
- New `src/tempo/freshgen.py`: frozen 24-world allocation, structured meaning-correct evidence, declarations, tapes.
- New scripts `fresh_{generate,validate,run,analyze}.py`; tests `tests/test_fresh.py` (fixtures 1-12, limits,
  zero-query, out-of-scope, history preservation).
- Unchanged: every 1.11.0 module (agentstate, recovery, goals, policy, assertions, engine, text channel).

## V1.13.0 (2026-11-05): query timing and the cost of waiting (CPU only, zero model calls)
- New `src/tempo/timing.py` (TIMING-v1): fixed episode origin (abs 12) and fixed public activity window (12, 14)
  independent of the controller clock; schedules EARLY / EARLY_WAIT / DEFER; the unchanged 1.12.0 temporal
  projection called with base = episode origin; execute / complete (empty plan) / decline outcomes with false
  completion separate from invalid attempts; U_lambda with a pre-action waiting charge.
- New `src/tempo/timinggen.py` (1.12.0 allocation rows, new pools registered at runtime, fixed windows).
- New scripts `timing_{generate,validate,run,analyze}.py`; tests `tests/test_timing.py`.
- Unchanged: every 1.12.0 module (freshness, freshref, freshgen, recovery, agentstate, ...).
