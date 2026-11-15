# Text-interface policy study (V1.9.1): frozen plan

- **Brief:** `TEXT-INTERFACE-POLICY-TEST-BRIEF.md` (copy in `design/`). This plan is hashed in `config/FROZEN-PROTOCOL.json` before any model output; the main budget is set after smoke. Development only.
- **Source:** `<DREAM_HOME>/Code/DREAM-project-1.9.1-text-policy-20261105`, which is 1.9.0 plus:
  - `src/tempo/text_channel.py`, `scripts/textpol_{generate,analyze}.py`, `tests/test_textpol.py`;
  - a refactor in `policy.py` so episodes can be built with their world object and policies can run on an input channel.

  The structured study reproduces exactly under 1.9.1: same committed episodes, same counts. Tests: 110/110 in the container.

## Unchanged from the structured policy study
- Episode allocation and types; relevant fields.
- The reliable structured sensor (1 per fact, delay 1, at most 2 facts).
- A stable world after the decision.
- The planner, actions, goal and utility (10·success − action cost − 3·invalid − 1·fact queried).
- One attempt per episode.
- P0, P1 and P2 exactly as frozen in 1.9.0.
- Model: Qwen3-8B rev b968826d…, bf16, thinking off, greedy. Extraction cap 256 tokens. No retry.

## Episodes and channels
- **Episodes:** 24 fresh, from pool `textpol` (four-syllable names from `bdgkmtz`), base seed 20261112, with 0 rejected attempts. Each has six reports before the decision cutoff.
- **Structured channel:** the public contract-v1 reports, with no model calls.
- **Text channel:** the reports rendered by the already-tested prose generator from the repair/prose study (`prose_study.line_fn`, surface "prose"). Every rendering passes `check_equivalent`.
  - One frozen extraction call per report: 24 × 6 = **144 calls**.
  - The prompt is byte-identical in construction to the scored 1.8.2 prose channel. A test regenerates all 144 committed 1.8.2 prompts exactly.
  - All three text-policy clones of an episode share the same six extractions; before the decision their public histories are identical.
- **Adapter v1** (`text_channel.py`, deterministic):
  - parse;
  - the frozen 1.8.2 normaliser (N0–N3);
  - `from_v02` mapping, with two declared rules:
    - M1: an unrecorded-result event without `from` becomes an event with an unstated prior value;
    - M2: a correction whose `event_at` is still non-null is not mapped.
  - Engine v0.3 ingestion. A report that can't be mapped or is structurally rejected is registered as unprocessed, so the fields it names are incomplete.
  - No gold correction, no filling of missing assertions, no override of conflicts.
- **Sensor responses:** these stay structured in both channels.
- **Totals:** 144 trajectories (24 episodes × 3 policies × 2 channels), 144 model calls, plus a smoke of at most 24 calls on 4 disjoint episodes.

## Known before outputs (from no-model tests)
- **A wrong "verified" extraction looks settled.** If the extractor turns a verified report into a wrong verified claim, P2's evidence-status trigger has no reason to query it. If a sensor reading does arrive (P1), the result is a verified–verified conflict that the frozen contract keeps, and the planner declines.
- **Incompleteness persists.** An unprocessed report keeps its fields incomplete even after a fresh sensor reading, under the frozen contract. A decision that depends on such a field is `unresolved_pending`.

Both will be reported as language-interface consequences, not repaired.

## Outcomes
**PRIMARY:** P2 − P0 utility in the text channel, paired per episode. The bootstrap is domain-stratified, 10,000 resamples, seed 20261105.

**Also reported:**
- P2 − P1 and P1 − P0 in each channel;
- each policy's utility, text − structured;
- the change in each policy benefit (P2 − P0 and P2 − P1) from structured to text, within episodes.

**Kept visible:**
- success and feasibility (2 `no_plan` slots per domain);
- invalid attempts, false blocks, missed opportunities and declines;
- decisions made with conflicted or incomplete relevant fields;
- facts queried;
- utility components, action cost and delay;
- belief correctness on the relevant facts, before and at the decision;
- whether the earlier-information view is preserved.

**Extraction:**
- meaning-preserving records (temporal denotation) and assertion coverage, as in contract_validate;
- type-class equality and wrong status;
- unprocessed codes and normaliser applications.

**Where text and structured differ:** every text trajectory that differs from its structured clone is listed, tagged with:
- conflict at the decision;
- incomplete at the decision;
- a different provisional flag or status before the decision;
- different queries;
- a wrong belief at the decision.

Tokens, generation time and engine cost are reported separately from utility; the utility formula is unchanged.

## Stop
Stop after this report. Sensor noise, change during the delay, repeated recovery, new actions and learned query selection are later, separate tests.
