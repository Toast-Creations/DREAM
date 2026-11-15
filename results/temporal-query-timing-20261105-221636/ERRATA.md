# ERRATA: V1.13.0 query timing (append-only; old scores, traces and REPORT.md unchanged)

## E1 (2026-11-05): DEFER completed three, not four, of the newly menu-feasible goals
Two passages in REPORT.md (Mechanism bullet: "all 4 genuinely newly feasible goals"; Feasibility section:
"DEFER completed all 4") overstate the result.

Corrected wording: In 1.13.0, DEFER completed three of the four newly menu-feasible goal copies: d05/A, d07/B,
and d12/B. It did not complete a06/B, which remained unresolved because the original P2 list omitted the relevant
stock field (Nedudefe.on_hand). The three recovered goals were already feasible in the full action domain at the
episode origin; their optimum costs changed 5→3, 11→8, and 10→0. Only a06/B became newly full-domain feasible
(None→2), and it was not recovered. All utility, success, correctness, and contrast scores are unchanged. The count
of 18 goal copies where DEFER succeeded and EARLY_WAIT did not is also unchanged (it includes the three recoveries).

The eight residual DEFER declines, by actual feasibility at the action boundary:
- menu plan valid, information insufficient (3): a03/A, a04/A, a06/B
- full-domain feasible, no valid plan in the supplied menu (4): a12/A, d01/A, d06/A, d08/B
- full-domain infeasible (1): a03/B
Separately, four declines are driven by unqueried uncertainty (a03/A, a04/A, a06/B, a12/A); a12/A is also a
menu-coverage gap.

(Verified 2026-11-05 from `stages/main/trajectories.jsonl` and `stages/main/feasibility.jsonl`: DEFER changing
success True for d05/A, d07/B, d12/B, False for a06/B with queried [Fovudihi.part], uncertain_unqueried
[Nedudefe.on_hand]; optimum_at_origin→at_action 5→3, 11→8, 10→0, None→2.)
