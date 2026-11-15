# ERRATA: V1.12.0 observation freshness (append-only; old scores, traces and REPORT.md unchanged)

## E1 (2026-11-05): "opened/closed opportunities" counted candidate-plan changes, not feasibility changes
The categories `opportunity_opened_by_actual_change` (13) and `opportunity_closed_by_actual_change` (12) in
`analysis/main/TABLES.md` and REPORT.md compare sets of valid candidate-plan keys at measurement vs action time.
They are not counts of goals becoming feasible or infeasible; 9 goal copies both gain and lose candidates.

Corrected wording: In 1.12.0, 13 goal copies gained at least one newly valid candidate plan and 12 lost at least one
previously valid candidate plan. Only four became newly menu-feasible: d05/A, d07/B, d12/B, and a06/B. Three became
menu-infeasible: d01/A, d08/B, and a12/A. This accounts for the change from 42 to 43 feasible goal copies. Both
projections failed to complete the goal in all 13 candidate-gain cases, including the four newly feasible cases.
The original numerical results are unchanged.

(Verified from `stages/main/trajectories.jsonl`: 13 gain, 12 loss, 9 both; 4 newly feasible, 3 newly infeasible;
0 successes in the 13 gain cases under either projection.)

## Retained note
a10/A: carry-forward selected the empty `already` plan after the slot changed. No invalid physical attempt occurred,
but the goal no longer held (U −1). No-invalid-attempt and successful completion are separate outcomes.
