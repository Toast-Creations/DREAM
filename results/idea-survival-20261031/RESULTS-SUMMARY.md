# Preliminary results summary — measurement audit
1 November 2026 · Development evidence

Both matched generation pilots are complete: Qwen3-8B and Mistral-7B each have 72 chains and 216 calls. Their saved rating calls cover initial ideas only; no final pilot content or pilot lineage has been rated. There is no complete pilot survival comparison.

The developer-qualification data have 12 source sets forked into review and develop, producing 24 branches. Under the original ≥3/both-judges rule, both branches have mean qualifying yield 0.00. Under the prespecified ≥2/both-judges sensitivity, both still have mean qualifying yield 0.00. The declared workflow rule retains develop by default; this is not an equivalence result.

A subsequent saved-rationale audit identifies an assessment-unit mismatch: judges receive one extracted idea with the full task requesting five and sometimes penalize the item for not containing the entire requested set. The observed floor therefore cannot be attributed solely to output quality or harsh scale anchors. Corrected ratings may still be low; their direction and magnitude are unknown.

Both pilot rating jobs and active children were stopped at 14:20:53 EST. Old ratings and instrument freeze are preserved. The proposed scope-corrected prompt and lower-cost scoring plan are drafts awaiting qualification/adoption. Confirmation remains on hold.

Read [the full audit](rating-floor-audit-20261101/REPORT.md), [the machine-readable audit](rating-floor-audit-20261101/audit.json), and [the operational stop record](PILOT-RATING-STOP-20261101.json).


---

## Update (1 November 2026, evening): extraction repaired
Final answers were re-extracted offline with source 1.4.2. Old and new tables are both kept; see `extraction-v2/EXTRACTION-DEFECT-NOTE.md`.
- **Mistral pilot:** 319 → 339 sourced final members, and 29 → 65 unsourced notes. Arm delivery is now level at 84–85 of 90. Under v1, targeted steering's apparent lead (85 vs 74–82) was an artifact.
- **Qwen pilot:** one member reclassified to a note.
- **Qwen devqual:** 10 self-labelled new ideas moved from scored slots to notes (develop 3, review 7). Zero yield is unchanged.

The scoped-v4 pilot packets for Mistral (and for any Qwen set whose members changed) must be rebuilt from the v2 extraction before pilot judging. Qualification is still incomplete: Codex is out of quota, and Claude has finished 3 of its 36 qualification assessments.

## Addendum (2026-11-01, 19:30): scoped-v4 judge qualification failed
Neither judge family passed:
- **Claude:** anchors 4/6. It gave value 2 to plain, workable anchors and cited familiarity, so its novelty and value scores were mixed together.
- **Codex:** scope 12/18 and repeat 12/18. It was unstable, mostly coherence 4↔3.

No instrument changes were made after seeing the responses, and no AI-rated yield is reported under scoped-v4. See `judging/scope-v4/QUALIFICATION-RESULT-20261101.md`. Proposed paper text is in `manuscript/REVISION-PROPOSAL-2026-11-01-extraction-repair.md` (section "Added 19:30").

## Addendum (2026-11-02): scoped-v5 and exploratory Claude-only ratings
- **Scoped-v5 qualification:** Claude passed every gate. Codex failed scope constraints, 11/12, on a flawed authored fixture. Under the pre-declared rule this is the second failure.
- **Exploratory Claude-only ratings** (1,249 calls): **0 qualifying final ideas in every arm, model and cohort.** Novelty is the binding facet: 1 of 698 pilot finals scores ≥3. Repeat-audit agreement is 0.89–0.96 exact.
- **Consequences:** the precision check is "uninformative: floor", so the confirmation is not run under this endpoint.
- **Where to look:** full tables in `judging/scope-v5-claude-only/EXPLORATORY-RESULTS.md`; paper text in the manuscript revision proposal, section "Added 2 November".
