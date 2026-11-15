# Audit of the three zero-scoring pair types (development only; 2026-11-04)

Scope: every pair of type `elsewhere` (delivery), `occupied` and `onhand` (assembly) in the 12 dev_all_s12 episodes
used by the s12 stages: 4 pairs per type, 12 pairs, 24 questions; choices from all 4 conditions × 3 seeds.
Files: zero_pairs_dump.py/.txt (options, keys, choices, rendered prompt tail), zero_pairs_rendered.txt (rendered fixed
facts and both states per pair), zero_pairs_classify.py/.txt and ZERO-PAIRS-CLASSES.json (classification).

## Keys and rendering
- Each of the 12 pairs was traced by hand from the rendered rules, fixed facts (roads/costs, connectors, adapters,
  prices) and both rendered states. Every key matches the hand-computed lowest-cost valid plan, every option's
  validity/cost matches, and the rendered state shows the flipped fact explicitly on both sides.
- The classifier (solver-2 step functions) reproduced the stored `correct` flag for all 288 rows.
- No defective item found. All 12 pairs kept unchanged as valid difficult cases.

## Failure classes (288 condition×seed×question rows)
| type | correct | missed prerequisite | missed goal | cost error |
|---|---|---|---|---|
| occupied | 48 | 48 | 0 | 0 |
| onhand | 48 | 48 | 0 | 0 |
| elsewhere | 39 | 56 | 1 | 0 |

- occupied: in every pair, condition and seed the model picks the same plan on both sides: the plan for an EMPTY slot
  (no "remove" step). Correct on the empty side; on the occupied side it fits/installs into an occupied slot.
- onhand: in every pair, condition and seed the same plan on both sides: the plan that assumes the part is ALREADY ON
  HAND (no "order" step). Correct on that side; on the other side it installs a part that is not on hand.
- So these two types score 0.5 per question but 0 complete pairs; the error is always on the side whose fact requires
  the extra step. No condition (text, own, same-world or other-world adapter) changes this.
- elsewhere: the same choice on both sides in 35/48 side-pairs. Wrong choices are plans that take the item at a place
  where it does not rest, often near-miss plans with a skipped or inconsistent move (e.g. D6, U3, T4). One missed goal.
  Own adapters shift some choices between near-miss plans but do not fix the location check.
- Every error is a missed prerequisite tied to the flipped fact; there are no cost errors.
- Support examples of the same types (one solved pair per type per episode) were themselves at about chance before and
  after 12-step training: occupied 3/8→4/8, onhand 4/8→4/8, elsewhere 3/8→3/8 (seed 2000; other seeds similar).
