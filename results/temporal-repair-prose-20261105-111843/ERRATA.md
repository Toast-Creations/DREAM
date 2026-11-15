# Errata to REPORT.md (2026-11-05; REPORT.md and all scores kept unchanged). None changes the primary 19/24 results.

Verified against analysis-prose/records.jsonl and checkpoints.jsonl:
- E-1 Retry partition. The 41 retries partition as 41 = 5 accepted exact repairs + 11 correct records rejected again + 25 wrong records still rejected. The report's "rejected for a different rule (1)" is one of those 25, not a 42nd attempt; its "5 + 11 + 25 + 1 = 41" line is wrong.
- E-2 Missing fields. The lines cells also contain 29 missing field cells (fields absent from the engine state because the record introducing them was rejected) in addition to the 10 incomplete cells; the report's field-error summary omitted the missing component. Prose cells have 0 missing.
- E-3 First mentions. The exploratory "28 first mentions" count was computed from an error-pattern filter, not from first mention. Against the canonical public prefix, the 37 prose observation->initial outputs comprise 20 first mentions (field not stated by any earlier record) and 17 already-mentioned fields. The equivalence claim is retained only with that definition: for a first mention, a one-fact initial and an observation induce the same engine state.
- E-4 Interpretation. Equal prose/lines means with a [-0.21, 0.17] interval is a bounded null result, not evidence of equivalence.
