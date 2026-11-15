# Notes: V1.17.0 record-context ablation (append-only)
- Status: completed. LOCAL helps arrivals (+0.175 [+0.10, +0.25]) but harms removals (−0.24) and corrections (−0.15).
  It is a trade-off, not a policy result. The context-window branch is closed (2026-11-06).
- No actions were measured. Nothing here bears on the overnight wrong-entity unsafe class.

## N1 (2026-11-06): reporting clarifications (scores unchanged)
- FULL produced 92 raw `initial` arrival replies: 84 mapped states and 8 malformed state replies (unmapped). Raw
  state classification was 76.7%, the mapped-state fraction 70%. LOCAL produced 71 mapped states (59.2%).
- FULL's 24 control replies were 11 exact events, 8 unmapped, and **5** accepted wrong-kind replies (the report said
  4). The 5 groups correct on both alternatives are unchanged.
- The prefix-length pattern is descriptive. Three- and four-record prefixes are different groups, and the longer
  prefix adds a slot observation, so it does not isolate length as the cause.
(Verified from analysis/main/scored.jsonl.)
