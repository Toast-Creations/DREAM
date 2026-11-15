# Creativity steering (DREAM, DREAM3)

**Question.** DREAM began from a two-step theory of creative work. First, introduce an idea while the usual category boundaries are loosened ("decategorized"). Then develop that idea in the ordinary state. The question was whether activation steering, which adds a fixed direction to one layer's activations, can create that loosened state in an open-weight model, and whether the ideas that result are better.

**What was tested** (Qwen3-8B, with a Mistral-7B pilot; October–November 2026):

1. *Write-time steering, then fresh-context development* (idea-survival pilots). Under a strict absolute endpoint, no final idea in any arm qualified, so that endpoint couldn't separate the arms. The first judge instrument (scoped-v4) failed its own qualification and was not used.
2. *Read-time steering, then same-context development* (continuity pilot). Under a model judge, targeted steering led a matched random direction 22–14. That's a small lead on six tasks and it was never confirmed. The author's condition-masked review of the same pairs did not reproduce it.
3. *Direction validation.* Pre-specified screens compared three candidate directions with nine random directions at three layers. No cell beat every random direction on both category change and abstractness *and* then replicated on held-out objects.
4. *Categorization check* (frozen before data, after an external methods review). Steer-then-release with the best direction *lowered* endorsement of peripheral and remote categories compared with random directions, both during the intervention and after release. A prompt-based positive control did change categorization, but not selectively: it raised acceptance of clearly false categories more than remote ones.

**Conclusion.** We found no evidence that this steering decategorizes. There is evidence against loosening of a meaningful size. The steering branch is closed.

**Read more.**
- [Manuscript v0.7](../papers/manuscript-v0.7.md): the full write-up of Studies 1–4.
- [Study index](../studies.md#creativity-steering-dream-dream3): every run, with its criteria and results.
- [DREAM3 proposals E1–E6](../proposals/README.md): six follow-up designs, written before the negative result was final. None has been run.
- Protocol documents in [docs/protocols/](../protocols/): documents 02, 04, 13 and 17–18 cover this line.

**Code.** `src/dream` (exploration runner), `src/dream_core/steering*`, `src/survival` (idea survival, continuity, direction screens).
