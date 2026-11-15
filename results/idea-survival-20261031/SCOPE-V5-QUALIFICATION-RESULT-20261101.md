# Scoped-v5 qualification result: Claude PASS, Codex FAIL (one requirements check) — 2026-11-01, 20:40 EST

Source: `scope-v5/qualification/score.json`. 76 provider calls (cap 96); all 38 presentations × 2 families parsed.
`INSTRUMENT-FREEZE-v5.json` was NOT written, and pilot judging is blocked by the code. Nothing was changed after seeing these responses.

| Check (gate) | Claude | Codex |
|---|---|---|
| Scope agreement (≥17/18) | 18/18 ✔ | 17/18 ✔ |
| Repeat agreement (≥17/18) | 18/18 ✔ | 17/18 ✔ |
| Direction (≥5/6) | 6/6 ✔ | 6/6 ✔ |
| Anchors (≥7/8) | 8/8 ✔ | 8/8 ✔ |
| Scope constraints (12/12) | 12/12 ✔ | **11/12 ✘** |

**The single failure:** Codex marked one presentation of the "town map that redraws itself after lies" premise (XAG4Y6VDM) `uncertain` on the rule requirement, with coherence 2. That one response also caused its only scope and repeat disagreements; its other two presentations of the same premise got coherence 3 and `pass`.

Codex's stated reason: "confession reversing the displacement is not established by the stated rule that lies move streets."

**Author's note:** this criticism is substantively correct. The authored premise states only that lies move streets, yet resolves by moving a street back after a confession. The fixture was imperfect, and the judge noticed it inconsistently, once out of three presentations.

Under the pre-declared v5 rule ("If v5 fails: stop and report as the second failure; no v6"), this is reported as a failure. The item was not replaced, re-scored or removed.
