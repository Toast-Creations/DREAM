# Older Qwen3 Pilots: Review and Amendments

October 30, 2026. These are exploratory diagnostics, not confirmatory effectiveness results. Claude Code assisted David with execution; Codex independently reviewed the saved records and summary code.

The October 29–30 run completed 72 DREAM trials with reasoning off, 72 with reasoning on, 433 of 504 DREAM 2 cells with reasoning off, and a 14-cell single-world reasoning-on slice. All 447 completed DREAM 2 records report verified reset. No non-fixture welfare pause was triggered; limited pattern coverage prevents interpreting this as proof that every possible report was absent. The recorded ML suite passed 42 tests without skips.

## Interpretation corrections

All 24 correct post-learning composition rows came from the same question in development world 1101-0002. Its three operations mapped the starting number 4 back to 4. Returning the input was therefore sufficient to pass that probe; the successes cannot establish learned composition.

The generator repeated this question within every world's composition set, leaving three distinct questions in four rows. The original paired contrast of coupled versus ordinary learning, at learning multiplier 0.5, reproduced as +1.39 percentage points with an exploratory world-bootstrap interval from 0 to +4.17 points. Counting distinct composition questions once gave +0.93 points, interval 0 to +2.78. Both depended on the same ambiguous probe. Zero observed contrasts elsewhere do not establish equivalence or absence of effects on other tasks.

Training supplied rules/facts in context; evaluation removed them. Logged loss declined across successive different examples, ending with lookups whose answers were supplied in their prompts. These records establish poor context-free recall and transfer, not a proven diagnosis of memorization. Direct post-training memory checks are needed.

DREAM's reasoning-off outputs all hit the 64-token cap. With reasoning on, empty intermediate answers propagated into integration and produced repeated empty-candidate rejections. DREAM 2's reasoning-on slice had 157 of 375 distinct calls reach the 1,024-token cap (41.9%). The parser marked 182 calls as unfinished thinking (48.5%), including 25 short JSON responses without a closing thinking tag. A diagnostic reading of those 25 JSON objects restored arithmetic anchors but no composition, direct, paraphrase or lookup success.

The older evaluation also forced greedy decoding in thinking mode despite Qwen's recommendation for sampling. This is a plausible contributor, not an isolated causal diagnosis. The correct scientific wording is: no reliable useful steering benefit was demonstrated under that protocol.

## Changes in 1.1.4

- Added a direct, fixed-five concept-association comparison with explicit reasoning modes and equal sampled decoding/caps.
- Preserved raw text, thinking and EOS/length stop classification. Direct JSON without a thinking block is recoverable only at EOS and remains flagged as a format deviation.
- Stopped the legacy pipeline before incomplete anchor or exploration output can enter the next stage.
- Fixed repeated numeric composition probes, varied starting inputs and prevented copy-input/sign-flip success in the regenerated fixtures. Old numeric datasets remain in old versions; new outcomes must not be silently pooled with them.
- Strengthened plan-only enforcement. The previous launcher already loaded data and counted trials, but did not enforce the selected world/task cap there; that additional cap now fails before model loading.
- Extended evidence hashing to scripts and dependency declarations, alongside source and tests.

The new concept pilot does not repeat the older adapter factorial or claim that its learning failure is repaired. The concept-learning extension remains proposed in document 15. All older source trees, archives and original run records remain historical evidence.
