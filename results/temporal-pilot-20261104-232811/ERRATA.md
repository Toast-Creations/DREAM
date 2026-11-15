# Errata and refinements to MORNING-REPORT.md (2026-11-05; MORNING-REPORT.md itself is kept unchanged)

Source: review of the completed pilot (pasted decision memo, 2026-11-05), checked against stages/main/analysis/scores.jsonl.

## Erratum E-1 (documentation arithmetic)
"What actually ran", E1 row: 360/360 is wrong. E1 = 432 D0/D1/I1 calls + 72 S0 = **504/504**; E2 144; E3 144; total 792. No data were missing.

## Refinements (more precise statements; counts verified)
- "Reads current state correctly 85%": the goal/focal fact is correct in 61/72 S0 calls; the whole requested state in 32/72.
- "Not reconstruction failure": abstention is a major observed bottleneck, but reconstruction errors coexist; separate readout calls do not reveal the state used inside decision calls.
- Observation on plan-key rows, pooled counts: C1 177/192 (92.2%), C0 79/192 (41.1%). The report's 90%/37% figures are group/domain-weighted — different estimands, not arithmetic errors.
- Exploratory join (S0 × D0, same group/length): among 27 determined D0 cells whose separate S0 readout was entirely correct (11 groups), C1 chose observe in 26 and got 0 right.
- "Allowed actions predicted correctly": changed fields 39/39 in each arm on applicable rows, but exact successor C0 27/39, C1 20/39; applicability + exact successor C0 27/39, C1 6/39; all three A0 parts C0 27/39, C1 4/39.
- "Length did not matter": complete-pair accuracy was at the floor (0) at all three lengths; a floor cannot show length invariance.
- "Corrections handled well": the corrected focal historical fact was right in the tested correction patterns; not whole-state correctness or every revision type.
- Delayed-report retrospective focal result 2/12 rows comes from 4 independent groups: a localized weakness, not a validated general limitation.

## Prompt-completeness issue (found in review)
The solvers assume all roads open (delivery, `closed=[]`) and no adapters (assembly), but the temporal prompts did not say so, while the printed rules mention closed roads and adapters. Under a strict "sure to work" reading, observing could be defensible on some items scored as determined. This is an alternative explanation, not proof that the keys are wrong; old records and scores stay unchanged. Tested in the V1.7.2 diagnostic (../temporal-diagnostic-20261105-081325, amendment D1).
