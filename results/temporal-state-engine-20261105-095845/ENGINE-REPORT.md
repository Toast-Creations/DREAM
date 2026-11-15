# Temporal state engine v0.1: architecture, contract and validation (no model calls)

**Brief:** `TEMPORAL-STATE-ENGINE-BRIEF.md` (copy: `BRIEF-copy.md`).

**Source:** `<DREAM_HOME>/Code/DREAM-project-1.8.0-state-engine-20261105`, a copy of 1.7.4 plus:
- `src/tempo/engine.py`: the engine;
- `src/tempo/engine_fixtures.py`: adapters from saved artifacts, used only by tests and validation;
- `scripts/engine_validate.py`;
- `tests/test_engine.py`.

No earlier run or source was changed.

**Status:** engineering infrastructure. Its guarantees are properties of code, **not capabilities of the language model.**

## What the engine guarantees, and what it doesn't
- **Guarantee:** consistency with the evidence it holds and the explicit rules.
  - A blocked action never has effects.
  - An unresolved action keeps every compatible outcome.
  - Hypotheticals never change the log.
  - Views never see evidence outside their cutoff.
- **No guarantee:** that the evidence is right.
  - If a record is extracted wrongly (for example, the crate is put in the wrong place), the engine will faithfully authorise or block actions relative to that wrong state.
  - Its decisions can then differ from what is actually legal in the environment.
  - A deterministic gate does not fix extraction errors. Milestone 2 measures exactly this gap.

## Architecture
| Part | Content |
|---|---|
| `WorldSpec` | The episode's fixed facts, taken from the printed text: places, roads, closed roads (none), the courier's position and non-portable crates (none); or slots, connectors, parts, prices, adapters (none) and fitted adapters (none). It also holds an **entity registry**: only registered entity attributes may appear in records. |
| `EvidenceLog` | Append-only, one context. Each entry carries a sequence number (reception order), its body, the previous hash and its own hash. There are two entry types: `record` (a public evidence record) and `execution` (an executed-action outcome). The version is the number of entries. |
| Supported state | Recomputed from the log by **two independent public-record resolvers**: `tempo.resolve`, which works from the latest assertion, and `tempo.enumcheck`, which enumerates trajectories. The engine raises if they disagree. The result is a value or "unknown" per field, the options for each unknown, and the explicit joint compatible states. Entities not yet described at the queried time are listed separately. |
| Views | **current**: all evidence, at now. **retrospective**: all evidence, at an earlier time; later corrections and late reports revise it. **earlier**: only the records received by a cutoff, at a time; the cache is keyed to that prefix's hash, so later evidence can never leak in. |
| Actions | Defined explicitly, with prerequisites, effects and failure semantics (a blocked action changes nothing). **delivery:** `take`, `go`, `put`. **assembly:** `install`, `remove`, `order`, `fit`. Every prerequisite is named, for example `crate_at_your_place`, `hands_empty`, `crate_portable`; `part_on_hand`, `slot_empty`, `connector_matches`. |
| `Branch` | A hypothetical: a list of joint compatible states, plus the actions imagined on it. It holds no reference to the log. Correlations an action creates are preserved: the "A carried" alternative is also the "hands full" alternative. |
| Audit | `audit_model_action` keeps three things side by side: the raw model reply, the engine's decision, and the engine's successor. A model's true/false answer is never used as authority. |

### Interfaces (from the brief)
| Interface | Behaviour as implemented |
|---|---|
| `ingest_report` / `commit_observation` | **Validation:** strict public schema. Unknown keys are rejected, including scorer and simulator keys such as `_src`, `ordinal`, `key` and `hidden`. Entities must be registered and values allowed. Records arrive in reception order, a record cannot be about a time after it was received, and rids are unique within the context. **Consistency:** the record is first added to a trial copy and checked with the trajectory resolver; inconsistent evidence is rejected and nothing is appended. **Immutability:** status and provenance (`source`, `evidence`) are stored as given and never changed later. |
| `apply_correction` | Takes verified correction records only. The target must be a report in this context that asserted the named field. Only open intervals `[valid_from, ∞)` are accepted, because that is what the record rules define; bounded intervals are rejected in v0.1. Replay is implicit, since every view is recomputed from the log. The original report stays in the log and `explain()` shows it as "withdrawn by rNN". |
| `check_action` | Returns allowed, blocked or unresolved over all compatible states, with three-valued prerequisites. Blocked means false in every compatible state: one known-false requirement blocks even if another is unknown. |
| `predict_action` | Runs on a branch copy. Each compatible state gets its own outcome: the effects if the action is allowed there, unchanged otherwise. Unaffected known facts stay known. |
| `commit_execution` | **Idempotent per execution id:** a duplicate never executes twice. **Allowed:** the effects are appended as verified change records with source `execution:<id>`, provided the effect is the same in every compatible state; otherwise the engine refuses. **Blocked:** a failed attempt with no effect is recorded. **Unresolved:** refused; the outcome must arrive as an observation. The courier's own moves are predicted on branches but not committed in v0.1. |
| `save` / `load` | `save` writes a whole file atomically (temporary file, fsync, rename). `load` verifies every line, the sequence and the hash chain, then replays each record through full validation. A torn final line or a tampered entry raises `IncompleteWrite`, so an incomplete write can never be read back as a committed event. |

## Acceptance checks (brief §"Acceptance checks")
**Contract tests:** 18 hand fixtures in `tests/test_engine.py`. Their expected values were written by hand from the rules. In the container, the full suite passes **65/65**: 24 pilot + 12 diagnostic + 11 probe + 18 engine tests, with ResourceWarnings treated as errors (`test-results/tests-1.8.0.txt`).

| # | Check | Evidence |
|---|---|---|
| 1 | A blocked action leaves the branch unchanged even when a saved reply describes success | Hand tests: delivery location; assembly occupied slot, part already on hand, and no adapter. **Saved replies:** all 188 blocked rows from the diagnostic and the probe; 186 of them described the action succeeding. In each one the engine's successor equals the current state. |
| 2 | Allowed actions apply their effects and preserve other facts; duplicates don't execute twice | Hand tests: `take`, then a duplicate id (log unchanged), then a second `take` blocked because hands are full; and remove → install. Fixtures agree on 84/84 pilot A0 rows and 756/756 plan validity checks. |
| 3 | Unresolved prerequisites give the supported alternatives | Hand tests: unknown-only → unresolved with 2 alternatives; false + unknown → blocked; later observation settles the value retroactively; known unaffected facts stay known. Fixtures: all 8 probe controls and the 4 diagnostic uncertain rows (two arms each) agree with the independent gold values. |
| 4 | Prediction never changes the log or the views; only a commit does | Hand test: a 3-step hypothetical leaves the head hash, the views and the execution list unchanged. **Audit:** the log was unchanged in 384/384 replayed rows. |
| 5 | Corrections, late old reports and validity intervals update the right view | Hand tests: a correction revises the retrospective view but not the earlier one; scoped correction; original record kept; late old report doesn't override; correction target and field checks; inconsistent evidence rejected without being appended. **Fixtures:** current state agrees on 252/252 pilot variants (24 main + 4 smoke groups × 3 lengths × 3 variants); retrospective (P0) on 84/84; earlier-information (K0) on 84/84. |
| 6 | Earlier-information queries can't see future corrections | Hand test: the earlier view is identical before and after a correction arrives. By construction, the cache is keyed to the prefix's hash. |
| 7 | Scope, save/load/replay, incomplete writes | Hand tests: separate contexts; duplicate rid; unregistered entity; disallowed value; reception order; time sanity. A saved and reloaded log has identical views and head hash, and execution idempotency survives reload. A torn final write and a tampered entry each raise `IncompleteWrite`. |
| 8 | Raw output, decision and state stay separate; no scorer keys or hidden state reach the engine | Hand tests: scorer and simulator keys rejected; the engine module imports only `resolve` and `enumcheck` (no generator, gold or scorer); the audit object keeps raw, model, check and successor apart. |

### Fixture validation on saved development artifacts (`validation/VALIDATION.{json,md}`)
The expected values come from the generators' own independent implementations, as committed: resolver 1 vs resolver 2, `apply_own` vs keycheck, and the `ectx.world` vs keycheck plan solvers. The engine received only public records and the printed fixed facts.

| Check | Agree / total |
|---|---|
| Current supported state (all fields) | 252 / 252 |
| Plan guaranteed-validity (all 3 plans per variant) | 756 / 756 |
| Retrospective (P0) | 84 / 84 |
| Earlier-information (K0) | 84 / 84 |
| A0 applicability + successor + observed world + log unchanged | 84 / 84 |
| Probe rows (applicability, successor, observed) | 56 / 56 |
| Probe requirement vectors | 56 / 56 |
| Diagnostic block D rows | 104 / 104 |
| **Disagreements** | **0** |

**Audit of the 384 saved model replies.** These are the probe's 280 and the diagnostic's 104 block-D replies, with the engine's decision placed next to each.
- On blocked rows:
  - the replies described the action's effects 186 times out of 188;
  - in 38 of those 186, the same reply had said the action was **not allowed** (probe checklist C0 invalid rows: 24 of 24);
  - the engine's successor equals the current state in all 188.
- Where the engine says "allowed" (168 rows), the model's successor still differed from the engine's in 43. Those were mistakes in the unaffected or observed fields.
- The remaining 28 rows are unresolved. All 384 replies parsed.

Taken together, a system that executes through the engine has no ungated effects in these replays. But each repaired row is a **system result**: the raw replies are kept, and they remain the model's evidence.

## Costs (measured, CPU, this machine)
| History | Ingest (validation + consistency) | View + check | Log on disk | Reload + replay |
|---|---|---|---|---|
| 6 records | 0.4 ms | 0.11 ms | 2.6 kB | 0.5 ms |
| 30 records | 5.1 ms | 0.41 ms | 11.2 kB | 5.6 ms |

Recomputing the retrospective view after a correction took 0.29 ms. Ingest is quadratic in the number of records, because each new record re-checks consistency over the whole log. That is fine at this scale; incremental checking would be needed for long logs.

## Known limits of v0.1
- **Joint uncertainty:** the record language constrains one field at a time, so the initial set of compatible states is the product of each field's options. Joint uncertainty can't be expressed in a record. Correlations that actions create are kept.
- **Correction intervals:** only open-ended correction intervals; bounded `valid_to` is rejected.
- **Courier moves:** the courier's own moves can't be committed; its position is a fixed fact in these episodes.
- **Episode scope:** one context per engine; nothing merges contexts.
- **Truth of evidence:** status and provenance are kept exactly as supplied. The engine can't know whether an extractor labelled a provisional report as verified; milestone 2 scores that separately.

## Readiness
The engine passes every acceptance check, and agrees with every independent fixture value on the saved artifacts. It is ready to sit under the milestone 2 comparison: `HISTORY-INTERPRETATION-PROTOCOL.md`, which has been written but not run.
