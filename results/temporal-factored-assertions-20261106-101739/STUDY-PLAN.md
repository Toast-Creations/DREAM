# Factored assertion extraction (V1.18.0): frozen plan

- **Brief:** `FACTORED-ASSERTION-EXTRACTION-BRIEF.md` (copy in `design/BRIEF-copy.md`). A representation-and-compiler diagnostic; there is no action or safety estimate.
- **Freezing.** This plan is hashed in `config/FROZEN-PROTOCOL.json` before main output. Amendments go to `config/AMENDMENTS.md`.
- **Predecessor.** 1.17.0 is preserved as `48e575f`; the context-window branch is closed. Note N1 (`0a15ca3`) records:
  - FULL produced 92 raw `initial` arrival replies (84 mapped plus 8 malformed): 76.7% raw states and 70% mapped;
  - FULL's control replies were 11 exact, 8 unmapped and **5** accepted wrong-kind;
  - the prefix-length pattern is descriptive only.
- **Source.** `Code/DREAM-project-1.18.0-factored-assertions-20261106` is 1.17.0 plus:
  - `src/tempo/factored.py`: the FACT-v1 prompt, corpus builder and compiler;
  - `scripts/fac_{generate,validate,analyze}.py`;
  - `tests/test_factored.py`: the hand-worked compiler and score fixtures.

  Every 1.17.0 file is byte-identical. Tests: 213/213.

## Interfaces (one call each; FULL raw history in both)
- **EXCLUSIVE:** the 1.16–1.17 FULL prompt with the NULL_PRIOR schema (`ctxablate.full_prompt`). Adapter-v1 is unchanged.
- **FACTORED:** the same prompt with exactly two blocks replaced (asserted per call; the diff is 5 lines out, 5 lines in):
  - the instruction and kinds lines become independent lists of `events`, `states` and `revisions`, empty when none apply. Earlier records may be used only to identify referents; no claims may be added;
  - the reply schema becomes a generic field/value schema for those lists, with nullable unstated priors.

  There are no worked examples, no arrival wording, no verifier and no routing.
- **Both:** Qwen3-8B `b968826d…`, BF16, thinking off, greedy, **256-token cap**. No content retry; one infrastructure retry.
- **Token budget.** Canonical replies, tokenized: FACTORED max 173 / mean 149; EXCLUSIVE max 173 / mean 127. Both fit the cap. Truncations and tokens are reported as interface costs.

## Compiler (structural only; never gold, actual states, generator classes or phrase lists)
- **C1.** Parse one JSON object; take the top-level rid, received_at and status, and the three lists.
- **C2.** Validate each assertion against the registry, allowed values (N1) and integer times (N2). Otherwise reject as `invalid_assertion`.
- **C3.** Redundancy rules only:
  - **R1:** identical duplicates;
  - **R2:** a state at exactly an event's time, with the same field and the event's result: keep the event;
  - **R3:** a state at exactly a revision's valid_from, with the same field and value: keep the revision.

  A state at reception time is never dropped.
- **C4.** A single reporting act is translated to the existing v0.2 record via `assertions.from_v02`:
  - one event becomes a change or uncertain change;
  - states at one time become an observation or initial record;
  - one revision becomes a correction with a null event_at.

  Anything else is **pending** (`empty`, `mixed_acts`, `multiple_events`, `multiple_revisions`, `states_mixed_times`) and counts as incorrect. The raw output, normalisation log, reduced claims and compiled record are all preserved.

## Common meaning score (frozen before outputs)
- Both interfaces become canonical v1 reports, scored by the **unchanged** `contract_validate.score_record`.
- The existing prior conventions apply: an unstated stock prior may be null or correctly inferred; a wrong prior is an error.
- An event plus its result state equals the event (R2). A state alone is **not** the event. A revision is **not** a physical event. Unsupported extra claims, giving mixed acts, are errors. Empty lists are not an interpretation.
- **Fixtures** (`tests/test_factored.py`): event plus state; state-only arrival; removal versus retraction; wrong entity with an exact quote; contradictory or extra claims; missing and invalid times; duplicates; revision plus valid-from state; a reception-time state with a revision; empty lists; the prompt diff.

## Corpus (committed; no redraws)
- **Main.** 120 fresh assembly miniature-history groups. The four variants are those of 1.17.0 (arrival, observation, removal, genuine correction), each with a compatible forked prefix.
- **Strata.** 8 strata × 15 groups: the **target part** (the world's G or D, counterbalanced) × prefix length 3/4 × mention order.
- **Lure.** An installation into slot T of part G (for target G, the target itself; for target D, the competitor) or of the low-rated part W. It alternates within each stratum, 64/56 overall.
- **Templates.** The 12 arrival phrasings, 10 groups each. Frozen templates only. Every rendering passes `check_equivalent`.
- **Calls.** 960 main.
- **Controls.** 12 context-required groups (the 1.17 construction), 2 histories × 2 interfaces = **48 distinct calls** with FULL history in both. They are outside the primary.
- **Totals.** **1,008 main calls.** Smoke: 4 groups and 2 controls, 40 calls (disjoint).
- **Order.** A precommitted balanced schedule (`order: as_committed`): each interface goes first in 252 of 504 units, and every quarter is exactly balanced.
- **Time.** The cap is 2 h overall (runner budget 6,900 s), forecast from the smoke. An incomplete run is preserved and labelled as such.

## Temporal replay diagnostic
- **Setup.** The canonical prefix plus the interface's accepted target is replayed in the unchanged engine. A non-accepted target enters as pending evidence. Three queries on the target field P:
  - **Q1:** the value at the historical anchor (P's prefix record time), using all evidence (cutoff 12);
  - **Q2:** the value now (12);
  - **Q3:** the value at the anchor known before the target's reception (cutoff t−1).
- **Independent reference** (hand rules over the source meaning):

| Variant | Q1 / Q2 / Q3 |
|---|---|
| Arrival | no / yes / no |
| Observation | yes / yes / yes |
| Removal | yes / no / yes |
| Correction | no / no / yes |

- The canonical replay must equal the reference: a software gate, which passed in phase0. Each interface's replay accuracy is an outcome.

## Gates
- **G1:** matched prompts and blocks, shared context, cap, no labels.
- **G2:** model configuration and committed order.
- **G3:** labels and prefixes; canonical replies compile exactly; canonical replay equals the reference; accounting.
- **G4:** complete scoring.

Wrong claims and cleanly handled failed compilations are outcomes.

## Outcomes (fixed now)
- **Primary:** FACTORED − EXCLUSIVE in the group's mean exact meaning over the 4 equally weighted classes (n = 120 groups). Bootstrap groups within the 8 strata, 10,000 resamples, seed 20261106; descriptive.
- **Mandatory per class:**
  - exact meaning and its difference;
  - paired counts (both, FACTORED only, EXCLUSIVE only, neither);
  - field binding;
  - a correct result value without exact meaning (a correct endpoint is not a correct act);
  - category and pending codes;
  - contract acceptance and rejection codes;
  - event omission (no event on P), states on P, revisions claimed (false revisions outside corrections), other fields claimed;
  - **removals accepted as corrections**;
  - replay accuracy per query;
  - truncation.
- **Also reported:** the redundancy rules applied; macro accuracy per stratum; all discordant cases; tokens and latency per interface.
- **Controls:** correct on both histories, per interface.

## Interpretation (fixed now) and stop
- **Primary positive, interval above 0:** supports this representation-and-compiler package on the four-class corpus. Per-class trade-offs must still be inspected.
- **Not reliability.** A gain with more accepted false revisions, or worse binding, does not establish a reliable interface.
- **Failure is allowed.** State-only arrivals under FACTORED are reported directly. Fewer accepted wrong revisions achieved only through more rejections is not a semantic improvement.
- **Out of scope.** Nothing here establishes learned dynamics, optimal context routing, safe execution, or the disappearance of the overnight wrong-entity class.
- **Stop after the report.**
