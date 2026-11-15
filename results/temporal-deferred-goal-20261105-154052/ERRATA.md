# Errata for the V1.10.0 deferred-goal transfer report (added 2026-11-05, after the report)

REPORT.md, STUDY-PLAN.md, the validation files and all scores stay exactly as written. This file qualifies two statements. No number, denominator or trajectory changes.

## E1. The three "no-plan" cases are gaps in the candidate menu, not infeasible worlds
The three declared gaps all have valid plans outside the supplied candidate menu. Their independent optimal costs (from `phase0/VALIDATION.md`, both solvers) are:

| Case | What the menu lacks | Independent optimum |
|---|---|---|
| `goaltr-del-unresolved-0` B | the item is at C, and no delivery candidate starts from C | 6 |
| `goaltr-del-no_plan-0` A | the item is at C, and no delivery candidate starts from C | 11 |
| `goaltr-ass-no_plan-0` A | remove + order + install is not a candidate | 5 |

- **Call these candidate-family coverage gaps.** Declining is correct for the frozen menu. It does not show the goal cannot be achieved.
- **"Feasible worlds: A 22/24, B 21/24"** in the report and the plan means **feasible within the supplied candidate menu**. All 24 worlds are feasible under both goals for an unrestricted planner.
- The frozen scores, denominators, success counts and missed-opportunity counts are unchanged. Menu coverage should be reported separately from policy behaviour.

## E2. "None of the loss came from query selection" is too broad
REPORT.md, "Where the remaining loss sits", says: "None of the loss came from query selection or from mishandling sensor evidence."

That is wrong for `goaltr-del-corrected-0` under goal A:
- The declared relevance rule left out a transitive dependency. Hands-empty is derived from crate locations, and the rule left out the other crate.
- So P2 did not query a relevant ancestor of the failing prerequisite.

**Corrected statement:** the observed loss came from extraction errors together with a mismatch between the dependency rule and the contract/engine. The mismatch affected query selection in one world. No loss came from mishandling sensor evidence once it was received.

## E3. The primary's interpretation branch
The plan's branch "if the primary is clearly negative" was **not** met: the primary was −0.833 [−2.167, +0.250]. The follow-up work (V1.11.0) is justified by the repeated local failure class and by the implementation mismatch the study found, not by the primary passing.
