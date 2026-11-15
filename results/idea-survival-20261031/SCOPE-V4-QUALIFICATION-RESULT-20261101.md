# Scoped-v4 qualification result: FAIL for both judge families (2026-11-01, 19:07 EST)

Source: `scope-v4/qualification/score.json` (written by the frozen scorer; instrument-spec sha256 afd1cef8…, packet sha256 0a5064c6…).
All 36 presentations × 2 families were completed and parsed, with no parse issues. `INSTRUMENT-FREEZE-v4.json` was NOT written, and pilot judging is blocked by the code.
Nothing was tuned, rerun or relaxed after these responses were seen.

| Check (gate) | Claude (claude-opus-5-5) | Codex (gpt-6.1-sol) |
|---|---|---|
| Scope invariance, exact facet agreement (≥17/18) | 18/18 ✔ | **12/18 ✘** |
| Repeat stability, exact facet agreement (≥17/18) | 17/18 ✔ | **12/18 ✘** |
| Direction (≥5/6) | 6/6 ✔ | 6/6 ✔ |
| Anchors (≥5/6) | **4/6 ✘** | 6/6 ✔ |
| Scope constraints (12/12) | 12/12 ✔ | 12/12 ✔ |

**Claude's failure is calibration.** It rates value 2 on two anchors authored as useful and coherent (value 3–4 expected): X9E3J8UR6 and XABUSZSCB, both rated novelty 1, value 2, coherence 3. Codex rated both 4/4. Claude is stricter on value at exactly the ≥3 boundary that the "both judges" rule uses.

**Codex's failure is instability.** 9 of its 12 disagreements are coherence 4↔3, which is above threshold. The others are novelty 2↔1 (twice), novelty 3↔2 (once, crossing the threshold), and one pair at value and coherence 2↔3 (crossing).

**Descriptive only, post hoc, not a gate:** agreement on the binary ≥3 decision per facet is as follows. This was not pre-declared and cannot qualify the instrument.
- Claude: scope 18/18, repeat 17/18.
- Codex: scope 16/18, repeat 17/18.

Even this looser reading would leave Codex scope below 17/18.

Per the frozen protocol, the result is reported as a measurement limit. Prompts, anchors and gates were not changed.
