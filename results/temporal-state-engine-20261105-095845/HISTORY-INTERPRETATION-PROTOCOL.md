# Milestone 2: history interpretation over the state engine (finalized protocol; NOT run)

**Status:** this is a design only. No inputs have been generated and no model calls have been made. Running it needs David's go-ahead.

**Sequence:**
1. Implement the generator, prompts and scorer in a new source version.
2. Pass the no-model checks listed below.
3. Commit the inputs and freeze the hashes.
4. Run a smoke of at most 24 calls, then the 216 main calls.
5. Write one report, then stop.

**Fixed:**
- Model: Qwen3-8B rev b968826d…, bf16, thinking off, greedy.
- Rules: the 1.7.1 system rules plus the 1.7.2 domain statements.
- Engine: v0.1 (source 1.8.0), used unchanged beneath every condition.
- Excluded: adapters, larger models, wording sweeps, and interactive action/feedback loops (a separately counted extension).

## Histories (24 fresh, independent units)
- **Domains:** 12 delivery and 12 assembly (6 where the slot is the uncertain fact, 6 where the part's stock is).
- **Patterns:** 1–6, two per domain:
  1. a real change;
  2. a delayed old report;
  3. a correction of a provisional report;
  4. a return to an earlier value;
  5. a scoped correction;
  6. a change whose result went unrecorded, settled by a later observation.
- **Provisional reports:** patterns 3 and 5 open with an accepted provisional report.
- **Construction:**
  - Each history has exactly 6 records, built with the existing `generate.base_records` (side a, or side b where noted) plus irrelevant padding.
  - Records are received at times ≤ 12.
  - Seeds come from base seed 20261109.
  - Names are three syllables from the `cjvwy` consonant pool, so they are disjoint from every earlier run; this is tested.
  - Smoke uses 4 more histories with three-syllable names from `fhlnprs`.
- **Hierarchy, recorded before generation:**
  - Each history is one unit.
  - Checkpoints, actions and conditions are nested inside it.
  - The known/unknown contrast is **within** a history: in pattern 6, the fact is unknown at the checkpoint after the unrecorded change and known after the settling observation.
  - The irrelevant-detail control is the padding records. Action verdicts must not depend on them, and the engine is checked to confirm this.
- **Checkpoints:** after the 2nd, 4th and 6th records, at the reception time of that record ("now").
- **Hidden simulator truth:** kept only in the scorer files, never shown to any system. It is the true physical trajectory: the records' own trajectory, plus the corrected value for corrected reports and the hidden actual value for unrecorded results.

## Systems (the same engine underneath each)
| System | What enters the engine | Calls |
|---|---|---:|
| **S, structured reference** | The 6 public records in typed form, ingested online at their reception times. This is an engineering reference: it skips language interpretation. | 0 |
| **X, text-to-event** | One model call per arriving record (6 per history). The extracted typed record is ingested online. | 144 |
| **R, full-history readout** | At each checkpoint, one model call reads all prose records received so far and reports the supported state. That state goes to the same action checker. | 72 |
| **Main total** | | **216** |

The three pipelines differ in number of calls, in representation and in computation. The comparison is not an equal-cost or memory claim.

### X: extraction call (exact access and prompt)
**Access:**
- the system rules;
- the world header (action rules, fixed facts and domain statements);
- the entity registry (every entity and field, with its allowed values);
- the prose of every earlier record, as context only;
- the new record's prose line.

No future record, engine state, gold or scorer annotation is shown.

**Prompt:** after the header,

```
Records received before this one (context only):
<prose lines r01 … r(k-1), as rendered by render.record_line>

New record to convert:
<prose line rk>

QUERY (record extraction)
Convert the new record into exactly one typed record. Report what the record itself states: its kind,
whether it is verified or provisional, the time it is about, the time it was received, and its content.
Do not decide what is true now and do not apply the record rules; only transcribe this record.
Kinds: "initial" (facts about one time), "observation" (one fact), "change" (an event with a recorded result),
"uncertain_change" (an event whose result was not recorded), "correction" (withdraws an earlier report's
statement about one fact).
Fields and allowed values:
<one line per field: "Field": one of ...>
Reply with only a JSON object:
{"rid": "<record ID>", "kind": "...", "status": "verified"|"provisional", "event_at": <int or null>,
 "received_at": <int>, "payload": {...}, "evidence": "<exact words from the new record>"}
Payload by kind: initial {"assign": {field: value, ...}}; observation {"field", "value"};
change {"field", "from", "to"}; uncertain_change {"field", "from", "options": [...]};
correction {"target": "<record ID>", "field", "value", "valid_from": <int>, "valid_to": null}
```

**How the engine handles the reply:**
- **Cap:** 256 new tokens.
- **Strict parsing:** at most one code fence, then exactly one JSON object.
- **Ingest:** the parsed record goes into the engine unchanged.
- **Rejections:** if the engine rejects the record (schema, unregistered entity, or inconsistency with earlier evidence), the system continues without it. The rejection counts as an extraction failure and is not repaired.
- **Valid-looking wrong records:** these are ingested and remain errors of the system.
- **Never:**
  - substituting gold;
  - resampling;
  - promoting a report's status.
- **The `evidence` quote:** it must be a substring of the new record. This is checked as linkage only; it is not proof of correctness.
- **What is kept per call:** the raw reply, the parsed record and the engine's accept/reject reason.

### R: readout call
- **Prompt:** the pilot's S0 current-state query under the completed header, covering all records received so far. It asks for every field the candidate actions read, with allowed values plus "unknown".
- **Cap:** 384 tokens.
- **Converting the readout to engine states:**
  - each definite value is used as is;
  - "unknown" becomes every allowed value for that field;
  - an invalid reply becomes "unknown" for every field.
- **Actions:** checked by the engine's action checker on those states, the same code as for S and X.

## Action tests at each checkpoint (hypothetical; never committed)
- **The tests:** two fixed candidate actions per history.
  - Delivery: `take X` (focal crate) and `take Y` (side crate).
  - Assembly: `install G in T` and `order G`.
- **Where they run:**
  - on a branch of each system's state;
  - on the gold supported state (the engine fed structured records);
  - on the hidden simulator truth.
- **Totals:** 24 × 3 × 2 = 144 action tests per system.
- **Checks:**
  - the log hash is unchanged after every test;
  - the six-record trace is never altered.

## Outcomes (all attempted calls, records, checkpoints and tests; fixed denominators)
1. **Typed-record accuracy (X):** for each of the 144 records:
   - **parse:** valid parse;
   - **engine:** accepted by the engine;
   - **fields:** entity/field, value(s), kind, event_at, received_at, status, correction target, valid_from;
   - **exact:** the whole record exact;
   - **evidence:** quote linkage.
   - Errors are classified as wrong field, wrong value, wrong time, wrong status, wrong kind, wrong target, or rejected.
2. **Supported state at each checkpoint:** S, X and R, against the gold supported state, over all fields the actions read and the asked fields. Reported as exact state, per-field accuracy, false unknowns, false certainty and wrong definite values, broken down by pattern, especially correction, delayed and uncertain.
3. **Action verdicts:**
   - **Against the gold supported state:** allowed, blocked or unresolved.
   - **Against actual legality in the simulator:** allowed or blocked. These two can differ, because the supported state may be unknown or provisional while the truth is fixed.
   - **Reported separately:** wrongly allowed (the system allows an action the truth blocks) and wrongly blocked.
4. **Successors and the observed world:** successors match the engine applied to that system's own state (consistency is guaranteed and reported as a check). Hypothetical commits: 0 expected, verified by hash.
5. **Cost:** calls, input and output tokens, latency, storage, and ingest/replay time.

**Pre-declared main comparisons:**
- **Unit:** the history (24), with domain-stratified cluster bootstrap, 10,000 resamples, seed 20261105.
- **Paired differences:**
  - **X − S** and **R − S**: final-checkpoint exact state, and action-verdict correctness against the supported gold over all 6 tests per history.
  - **X − R:** the same two outcomes.

Everything else is supporting or exploratory.

## No-model checks before inputs are committed
1. **S reproduces the gold supported state** and the action verdicts at every checkpoint, with resolvers 1 and 2 agreeing. If S fails, the engine or the specification is repaired first.
2. **The gold typed records round-trip:** each record → its prose line → the parse of a perfect reply → the identical engine state.
3. **Prompt leakage:** no prompt contains a future record, gold, hidden truth or scorer key.
4. **Fake-model pipeline:**
   - perfect replies give 1.0 everywhere;
   - injected wrong extractions (a wrong value, a dropped correction target, provisional changed to verified) give the expected error classes and the downstream state changes.
5. **Checkpoint prefixes are isolated**, and the action tests never change the log.

## Smoke, run controls and interpretation
- **Smoke:** at most 24 calls on 4 disjoint histories: all 6 extraction calls for 2 histories, and 3 readouts for each of 4 histories. It is technical only and never pooled.
- **Main time cap:** set from the measured smoke rate (×3, with a floor of 1,800 s).
- **Run controls:**
  - offline;
  - one logged retry, for infrastructure failures only;
  - LOCK hashes;
  - sleep blocked while running;
  - GPU ownership checked before each stage.
- **Reading the results:**
  - If S fails: fix the engine before interpreting anything else.
  - If X's records are wrong: classify the concrete record errors.
  - If X's records are right but its state is wrong: inspect update and replay (it should be impossible if S passes).
  - If R is worse than X: whole-history readout is the bottleneck, and per-record extraction plus the engine avoids it.
  - If X works: the next question is transfer to new action compositions or context families, not another sweep on these items.
- **Scope:** fresh seeds are not unfamiliar-template transfer and not broad confirmation. The result describes this engineered system.
