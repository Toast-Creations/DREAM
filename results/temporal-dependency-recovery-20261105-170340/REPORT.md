# Dependency parity and scoped current-observation recovery (V1.11.0): report (development only)

## Status
- **Brief and plan:** brief `DEPENDENCY-AND-CURRENT-OBSERVATION-RECOVERY-BRIEF.md`; plan `design/STUDY-PLAN.md`, frozen before any model output (`config/FROZEN-PROTOCOL.json`, source `984e9ee8…`, unchanged through the main run).
- **Predecessor:** 1.10.0 is preserved as a snapshot (git `3b7b47c`, pushed). Errata are in `ERRATA/1.10.0-deferred-goal.md` and the 1.10.0 hub's `ERRATA.md`. Its frozen manifest is `config/FREEZE-1.10.0.json`.
- **Tests and validation:** 139/139 tests in the container; pre-run validation `phase0/`, 0 failures.
- **Ran 2026-11-05:**
  - Smoke: 24/24 calls at 17:11–17:13, not pooled.
  - Main: 144/144 calls, 17:13–17:21 (480 s; 459.5 s generation; 15,297 output tokens).
  - No failures, no truncation, no retries, and no amendments. The GPU was free apart from desktop apps.
- **Sample:** 24 worlds × 2 goals × 2 channels × 2 contracts, all under P2: 192 trajectories sharing 144 extraction calls made without a goal. The independent units are the **24 worlds**.

## Part 1: the dependency/invariant repair
- **What changed:**
  - Agent state is explicit: `agent.at` and `agent.hands` are declared for the pre-action phase and updated by take, put and go.
  - The invariants `carry_link` and `slot_connector` are declared and enforced.
  - The planner, executor, relevance calculation, P2 query selection and validation all read one predicate table.
  - A prerequisite that reads an absent field is now unknown.
- **Validation:**
  - Relevance is unchanged on 48/48 goal clones.
  - Dependency sensitivity is now sampled over the engine's full domains: 0 failing contexts.
  - Inadmissible samples are counted rather than excluded (delivery 4,387; assembly 5,356). The same admissibility test is used by the engine view and the executor.
- **Repair parity against frozen runs:** strict reproduces **501/504** trajectories:
  - all 216 from 1.9.0/1.9.1;
  - 285/288 from 1.10.0, including its real extractions.

  The 3 changes are 1.10.0's `del-corrected-0`, goal A, text channel, under P0/P1/P2. The unrelated crate's "carried by you" option is now excluded by `carry_link` and listed as "narrowed" with its supporting reports. The utilities 0 / −1 / 0 become 7 / 6 / 7. This is a versioned repair; 1.10.0's scores stand.
- **In the fresh worlds:** no extraction produced an invariant diagnostic (0 text trajectories). The repair was not exercised by new outputs, so its evidence is the parity result and the no-model fixtures.

## Part 2: main result
**The scoped rule recovered every opportunity the strict contract lost to a conflict in the text channel. It introduced no false permission and changed nothing in the structured channel.**

| Contrast (text channel unless stated) | Mean [95%] | Better / equal / worse |
|---|---|---|
| **PRIMARY: scoped − strict, mean over goals** | **+0.56 [+0.15, +1.10]** | **4 / 20 / 0** |
| Goal A: scoped − strict | +0.29 [0.00, 0.88] | 1 / 23 / 0 |
| Goal B: scoped − strict | +0.83 [0.00, 1.83] | 3 / 21 / 0 |
| Negative control: structured, scoped − strict | 0.00 [0.00, 0.00] | 0 / 24 / 0 |
| Text − structured under strict | −0.65 [−1.27, −0.17] | 0 / 20 / 4 |
| Text − structured under scoped | −0.08 [−0.17, −0.02] | 0 / 20 / 4 |

Components (mean utility per world): A strict 3.46, A scoped 3.75; B strict 2.75, B scoped 3.58. Structured: A 3.79, B 3.71 under both contracts.

All of the plan's "supported" conditions held:
- the primary is positive and its interval excludes 0;
- there are 0 new false permissions;
- the negative control is exactly 0;
- matching is complete: 96/96 pairs have identical queries and sensor receipts, and an identical log and historical reconstruction.

| Cell (24 worlds) | Utility total | Success / menu-feasible | False permissions | False blocks | Queried | Conflict at decision | Operational relevant state correct at decision |
|---|---|---|---|---|---|---|---|
| A structured, strict = scoped | 91 | 22 / 22 | 0 | 0 | 23 | 0 | 24 |
| A text, strict | 83 | 21 / 22 | 0 | 1 | 24 | 1 | 23 |
| A text, scoped | 90 | 22 / 22 | 0 | 0 | 24 | 0 | 24 |
| B structured, strict = scoped | 89 | 19 / 19 | 0 | 0 | 10 | 0 | 24 |
| B text, strict | 66 | 16 / 19 | 0 | 3 | 13 | 3 | 21 |
| B text, scoped | 86 | 19 / 19 | 0 | 0 | 13 | 0 | 24 |

- **Remaining text loss under scoped:** −0.08. It is entirely the one extra query in each of the 4 recovered worlds, where the structured clone needed none.
- **No text missed opportunities remain under scoped:** every menu-feasible goal succeeded.
- **Menu feasibility** is relative to the supplied menu. Three candidate-family coverage gaps (independent optima 10, 9, 8) are menu declines in both contracts.

## The four recovered worlds
In each world the strict contract paid for the query, then declined on a verified–verified conflict. The scoped rule anchored the queried field to the sensor value and the plan succeeded. **In all four the historical reconstruction stays conflicted, and its culprit list is kept.**

| World / goal | Extraction error | Historical culprit(s) kept | Strict → scoped |
|---|---|---|---|
| ass-verified_settled-0 / A | "part … was delivered to you, so it is now on hand" read as a verified state | r01 | −1 → +6 (remove, install) |
| ass-corrected-0 / B | "part … arrived for you" read as a state | r04 | −1 → +7 (install) |
| ass-no_plan-0 / B | the same arrival report, unmapped (unprocessed), so the field is incomplete; the sensor reading then contradicts the earlier verified "not on hand" with no recorded event | q1 (the sensor report itself) | −1 → +6 (remove, install) |
| del-verified_settled-1 / B | initial report attributed to the wrong crate (an invented fact about B's crate) | r01 | −1 → +4 (here) |

**Recovery came from a fresh observation, not from interpreting the source correctly:**
- The arrival/delivery wording was misread in 6 of 8 reports, against 7 of 8 in 1.10.0.
- "Taken by another team" was read as a correction in 1 of 1.
- No extraction was certified, re-parsed or repaired. Each error is still in the log and is still a historical conflict.

**Integrity in all 192 trajectories:**
- earlier-information views were preserved;
- unanchored fields were identical between the two contracts;
- no receipt was refused in the main run, and there were no authority conflicts.

The refusal paths are exercised only by the no-model fixtures: stale, other-context, unregistered-sensor, unrequested-field, pre-stability, contradictory equal-time, inadmissible-value, and text claiming to be a sensor. In the structured channel, receipts anchored values that were already settled, with no behaviour change.

## Extraction (144 records)
- 141 accepted, 132 meaning-preserving, 0 source-status errors.
- 3 unprocessed: 1 `time_order`, 2 unmapped.
- **Errors touching relevant facts:** A only 1, B only 2, both 2, neither 7.
- **Settled-looking errors that P2 never queried** caused no utility loss in these worlds. That class remains outside the rule's reach.

## Reading (plan rules)
**Supported under the stated assumptions:**
- A named, scoped authority rule for a designated reliable current-state sensor recovers decisions that the strict contract leaves blocked by verified–verified conflicts, using exactly the same queries and receipts.
- It does so without false permissions and without changing any history, earlier view or unqueried field.
- On these 24 worlds, it removed almost all of the text interface's loss: −0.65 became −0.08.

**What this does not show:**
- learned dynamics;
- correct interpretation of earlier prose (the arrival class is still misread);
- recovery under noisy or delayed sensors, or in a changing world;
- recovery of a wrong extraction that looks settled and is never queried.

The gain rests on 4 of 24 worlds, all P2 queries of fields that were already flagged.

**The dependency repair is a correctness fix confirmed by parity and fixtures.** The fresh outputs did not reproduce the hands case.

## Limits
- **Sample:** 24 worlds; the primary is descriptive.
- **The gain depends on the error mix.** It depends on how often extraction errors become visible conflicts on queried fields. In this generator that is mostly the arrival class in assembly.
- **Assumptions:** a reliable sensor, a stable world after the decision time, and P2 only.
- **Interface limits unchanged:** the frozen renderers still have no provisional-event wording, and the 3 candidate-family coverage gaps are unchanged.

## Next choices (none started)
- arrival/correction classification or source-based reinterpretation, with recovery measured separately from this rule;
- sensor noise or delay;
- candidate-menu expansion and unrestricted planning;
- new action compositions.

## Artifacts
- **Analysis:** `analysis-deprec/{trajectories.jsonl, extraction.jsonl, ANALYSIS.json, TABLES.md}`; smoke in `analysis-deprecsmoke/`.
- **Raw replies:** `stages/{smoke,main}/calls/`.
- **Inputs:** `data/`.
- **Validation:** `phase0/VALIDATION.{json,md}`.
- **Configs and freezes:** `config/`.
- **Re-score:** `python3 -B scripts/deprec_analyze.py --hub HUB --set deprec --stage main`
