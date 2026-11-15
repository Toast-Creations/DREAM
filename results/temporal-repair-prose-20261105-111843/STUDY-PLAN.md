# Bounded record repair and prose robustness (V1.8.2): frozen plan

- **Brief:** `SCHEMA-REPAIR-AND-PROSE-TRANSFER-BRIEF.md` (copy: `design/BRIEF-copy.md`). This plan is hashed in `config/FROZEN-PROTOCOL.json` before any model output; the main budget is recorded after smoke in `config/MAIN-CONFIG-FROZEN.json`. Development only.
- **Source:** `<DREAM_HOME>/Code/DREAM-project-1.8.2-repair-prose-20261105`. Tests: 88/88 in the container. Earlier sources and runs are untouched (old run hashes tested).
- **Fixed:** model Qwen3-8B rev b968826d…, bf16, thinking off, greedy decoding; trust and persistence rules; world semantics; action definitions; the extraction instruction (the same for both surfaces); output cap of 256 tokens.

## 1. Engine v0.2 (`src/tempo/engine.py`)
- **Typed rejections:** every input rejection carries one of the enumerated codes in `REJECT_CODES`. The v0.1 `KeyError` path, an event on a fact with no earlier accepted statement, is now `missing_prior_state`.
- **Explicit type checks** replace accidental `TypeError`s. Unexpected internal failures propagate as their own exceptions and are never counted as rejections (tested).
- **Received but unprocessed evidence:** `record_unprocessed()` stores the raw report, the candidate extraction, the code and the message. Its affected scope is the registered entity attributes named in the raw text; if none are named, the whole context is marked incomplete. Unprocessed entries are hash-chained in the log and survive save/load.
- **Views:** `per_field` keeps the last accepted values ("old policy"). `complete_per_field` marks affected fields "incomplete" (completeness-aware).
- **Action verdicts:**
  - blocked: a requirement is known false, even when the incomplete fields are allowed every value;
  - unresolved: the ingested evidence permits alternatives;
  - unresolved_pending: the verdict depends on received evidence that wasn't processed.
- **Provisional reports:** still accepted until corrected. No new caution policy.
- **Revalidation:** fixture validation on all earlier saved artifacts still gives 0 disagreements. The two milestone-2 crash records now give typed rejections: `missing_prior_state`, and `schema` for a one-option unrecorded result.

## 2. Normaliser and one retry (`src/tempo/repair.py`)
- **Normaliser:** applied identically in both branches. Every conversion is logged with its rule ID and the original value.
  - N1: value spelling — case, spaces, trailing full stop, or a leading entity word, when it matches exactly one allowed value.
  - N2: a time given as a digit-only string.
  - N3: a correction's `event_at` equal to its own `valid_from` (with a string target and a null `valid_to`) becomes null.
  - N0: unrequested top-level keys are dropped and logged.
  - Nothing else is changed: no inferred times, kinds, alternatives, entities, targets or values. Counterexamples are tested.
- **Retry:** at most one per record, in the one-retry branch only.
  - Trigger: a parse failure or an engine `RecordRejected`. Nothing else, and never a comparison with gold.
  - Feedback: the original extraction prompt (raw prose, permitted prefix, registry and schema), the previous reply, the violated rule's text, and the validator message. It never includes gold, the expected kind or value, hidden state, or a scorer explanation.
  - If the retry also fails, the record is registered as unprocessed. It is never backfilled.

## 3. Matrix
- **Histories:** 24 fresh six-record histories, base seed 20261110, with three-syllable names from `bdgkmtz`; 0 rejected generation attempts.
  - 12 delivery and 12 assembly (6 where the slot is the uncertain fact, 6 where the stock is).
  - Patterns 1–6 × 2 per domain; pattern 6 uses side b.
  - Checkpoints after records 2, 4 and 6, with 2 hypothetical action tests each, as in milestone 2.
- **Two surfaces per record:**
  - "lines": the existing `record_line`;
  - "prose": `src/tempo/prose.py`, several seeded phrasings per kind.
  - The record ID and reception time stay explicit. Status is worded "confirmed/verified" or "provisional/unconfirmed, not yet verified". Correction target and validity start are stated, and both possibilities of an unrecorded result are named.
  - Every prose rendering passes `check_equivalent`, and I reviewed the templates by reading them.
  - All renderings are uniquely answerable; none was classified as ambiguous.
- **Calls:**
  - 288 initial extraction calls (24 × 6 × 2), committed up front. The initial access is identical for both branches: prose prefix, registry and schema, with no engine state.
  - Retries are live, made by `scripts/repair_run.py`, one-retry branch only. Each retry is written atomically, with the hash of its prompt, before the pipeline continues.
  - Ceiling: 288 retries. Smoke: 18 initial calls plus at most 6 retries.
- **Branches:**
  - no_retry: the shared initial replies, normaliser, engine v0.2 and unprocessed tracking.
  - one_retry: the same, plus the retry policy.
  - S: structured public records, as the engine reference.

## 4. Outcomes (unit: the history; 24, domain-stratified cluster bootstrap, 10,000 resamples, seed 20261105)
- **PRIMARY:** an exact, completeness-aware supported state at the final checkpoint. A field touched by unprocessed evidence counts as not exact.
- **Paired contrasts:** one_retry − no_retry within each surface, and prose − lines within each policy.
- **Secondary:**
  - all-checkpoint exactness;
  - action-verdict accuracy;
  - the old-policy final state, under its own label.
- **Separately counted:**
  - initial and retried semantic exactness;
  - engine acceptance;
  - accepted-but-wrong records, including valid-looking wrong repairs;
  - correct records rejected, which are cascades;
  - unprocessed records;
  - normalisation-rule counts;
  - false unknowns, wrong definite values and outdated ones (values the evidence asserted earlier), and incomplete fields;
  - verdicts, including `unresolved_pending`;
  - wrong permissions and wrong blocks against the hidden truth, kept separate from correctness against the supported state;
  - whether genuinely unknown facts stay unknown;
  - action tests that leave the log unchanged;
  - calls, tokens, seconds and engine replay time.

## 5. Run controls and stop
- **Run controls:**
  - offline (`unshare -rn`); sleep blocked;
  - LOCK hashes; one infrastructure retry, logged;
  - GPU ownership checked before each stage.
- **Main retry budget:** set after smoke; it can't exceed 288 calls.
- **Reading the results:**
  - If retries fix conventions but prose interpretation fails: work on the concrete semantic errors.
  - If both surfaces hold up: new action compositions are the next transfer test.
  - If accepted-but-wrong repairs rise: a higher acceptance rate is not progress.
- **Stop:** after this report. No tuning cycle.
