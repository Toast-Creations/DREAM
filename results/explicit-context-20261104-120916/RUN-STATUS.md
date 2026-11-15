# Explicit-context decision study — run status (newest first)

Proposal: <private-notes>/Publication/Research-proposals-2026-11-04/PROPOSAL-Explicit-Context-Decisions.md (draft 1.1)
Source: <DREAM_HOME>/Code/DREAM-project-1.6.0-explicit-context-20261104 (175/175 tests, --require-ml; source sha 1bcef3cb…)
Model: Qwen3-8B rev b968826d…, thinking off (David's choice, 2026-11-04).
Plan: ~/.claude/plans/i-have-the-next-logical-newt.md (approved by David 2026-11-04).

## 2026-11-04 23:20 — 48-step comparison COMPLETE; declared decision = 5 (stop this recipe) — development only
- s48-seed4000 finished 23:17 (resumed run); all three seeds complete. Every reset/save-load check 0.0; base full hash unchanged at end.
- Analysis: analysis/SEEDS-S48.json (sha 318ff38b…, ectx_seed_analysis.py, source 1.6.4) and analysis/S48-REPORT.json (sha f4b6773a…, s48_report.py), declaration applied unchanged.
- Rule 1: support learning BETTER: seed-averaged support accuracy 0.898 (≥0.80); gain vs 12-step +0.264/+0.257/+0.313 (≥0.10 every seed).
- Rule 2: corrections do not worsen: W+A − W +0.125 [−0.069, 0.319]; W+A correction 0.50 vs 12-step 0.444.
- Rule 3: own-adapter advantage NOT met: W+A − W+X +0.035 [−0.049, 0.104]; per seed +0.021/+0.021/+0.063.
- Rule 4: held-out benefit NOT met: W+A − W complete-pair +0.090 [−0.014, 0.194] (interval crosses zero = criterion not demonstrated, not evidence of no effect).
- Decision 5: no demonstrated held-out benefit → stop this recipe. No further settings will be tried on it (per the declaration). Sealed replacement still not generated; old sealed file unopened.

## 2026-11-04 — s48-seed4000 RESUMED (David: "continue the DREAM research")
- Relaunched seed 4000 only (s48_resume4000.sh = s48_run.sh limited to 4000; same config, source 1.6.4, offline unshare -rn). The runner skips the 6 adapters with training records; the 7th (incomplete, no file or record) retrains from its seed. Earlier log kept as s48-seed4000.stopped-1.log.
- When it finishes: analysis/s48_report.py on all three seeds, then apply config/S48-DECISION-DECLARATION.md unchanged.

## 2026-11-04 — 48-step comparison STOPPED by David before completion
- Stopped at David's request; model unloaded from the GPU (memory back to ~0.7 GiB, desktop only).
- Complete: s48-seed2000 and s48-seed3000 (all resets 0.0, base full hash unchanged). Incomplete: s48-seed4000 (6/12 adapters trained, 0 evaluated; no end record).
- No results were analysed and the declared decision was not applied: the declaration requires all three seeds. The stage can be resumed (the runner skips finished adapters) with s48_run.sh limited to seed 4000.
- Sealed replacement still waiting; old sealed file unopened.

## 2026-11-04 — Zero-pair audit done; 48-step comparison launched (source 1.6.4)
- Audit (audit/ZERO-PAIRS-AUDIT.md): all 12 pairs of types elsewhere/occupied/onhand traced by hand; every key, cost and rendered state correct; no defective item; all kept as valid difficult cases. Every error is a missed prerequisite tied to the flipped fact (no cost errors; 1 missed goal). occupied and onhand: the same plan on both sides in every pair/condition/seed (empty-slot plan; part-already-on-hand plan), so 0.5 per question but 0 complete pairs. elsewhere: same choice on both sides in 35/48 side-pairs; wrong choices take the item where it does not rest.
- Declaration before running: config/S48-DECISION-DECLARATION.md (sha 180d2f75…), with operational thresholds and decision order.
- David (during the runs): keep the declaration unchanged. Reporting additions, which change no criteria: support learning by flip type from per-example answers (occupied, onhand, elsewhere checked directly); correction outcomes reported whichever rule fires; an interval crossing zero = criterion not demonstrated, not evidence of zero effect. Report script analysis/s48_report.py, dry-run on 12-step data reproduced SEEDS-DONORS.json values.
- Stages s48-seed2000/3000/4000: 48 steps (4 passes), lr 1e-4, otherwise identical to the 12-step stages; four conditions; same donors. Logs s48.log, s48-seed*.log.

## 2026-11-04 — Donor controls + seed repeats done — development only (analysis source 1.6.4)
- All three stages finished; every reset/save-load check 0.0, base fingerprints and full hash unchanged. W identical across all four seed-2000/3000/4000 stage runs (156/156 answers).
- Analysis: analysis/SEEDS-DONORS.json (sha 80029a4a…), 12 episodes as units, seeds averaged within episode, world-stratified bootstrap. Fix needed: 1.6.3 seed analysis raised KeyError on per-flip means (each episode holds 4 flip types); fixed in Code 1.6.4 (182/182 tests), run code unchanged.
- Primary complete-pair W+A − W: +0.056 [−0.007, 0.132], episodes 4 better / 2 worse; per seed +0.062/+0.042/+0.062; by world delivery −0.02, assembly +0.02, workshop +0.17. Marginal +0.039 [0.014, 0.069] (9/2).
- W+A − W+X (own vs same-world wrong): complete-pair +0.007 [−0.014, 0.028]; per seed −0.021/0/+0.042. No consistent episode-specific component.
- W+X − W+Y (same- vs different-world wrong): complete-pair +0.014 [−0.035, 0.062], per seed +0.042/+0.042/−0.042 (not consistent); corrections +0.111 [0.014, 0.222] (4/0), stale −0.097 [−0.208, −0.014].
- W+X − W complete-pair +0.049 [0.000, 0.111]; W+Y − W +0.035 [−0.014, 0.083] (gains in delivery/assembly, 0 in workshop) but corrections −0.056 [−0.125, 0.000] (0/3) and stale +0.042.
- Corrections W+A − W +0.069 [0.000, 0.139]; stale −0.042 [−0.111, 0.028].
- Support learning still partial: support accuracy 0.57 → 0.63/0.63/0.60.
- Flip types at floor in every condition: elsewhere, occupied, onhand (0); closed ≤0.25.
- Reading (no mechanism assigned yet): complete-pair gain small, uncertain, workshop-concentrated, not episode-specific; complete-pair contrasts across donor worlds do not separate within uncertainty; correction handling is the one clear world-specific difference (same-world adapters help, different-world adapters hurt).

## 2026-11-04 — Donor controls + seed repeats launched (source 1.6.3)
- David approved a bounded dev check; sealed replacement still waiting. Declaration: config/DONOR-AND-SEED-DECLARATION.md (sha 380acab4…), written before any of these stages ran.
- Seeds 2000 (original), 3000, 4000 — training randomness only. Conditions W, W+A, W+X (same-world wrong, unchanged donors), W+Y (different-world wrong; each adapter donated once, both other worlds per world).
- Stages: s12-loo-cross (W+Y for seed 2000 from saved adapters; W re-run as determinism check), s12-loo-seed3000, s12-loo-seed4000. Analysis: ectx_seed_analysis.py, 12 episodes as units (seeds averaged within episode).

## 2026-11-04 — 12-example comparison (s12-loo) done — development only
- Same 12 episodes/settings/seed as ctx-loo; identical expanded packets for W, W+A, W+X; all resets 0.0; analysis/COMPARE-ctx-loo-vs-s12-loo.json.
- 1 Learning: harder examples are harder (base support accuracy 0.57 vs 0.85 before; choice NLL 3.76). After training (one pass per example) 0.63, choice NLL 1.76: partial learning.
- Written context alone: W complete-pair 0.375 (6 examples) → 0.438 (12 examples); "already" pairs 0.375 → 0.875.
- 2 Transfer: W+A − W complete-pair +0.06 [−0.02, 0.15] (episodes 3 better / 1 worse); marginal +0.056 [0.03, 0.09] (6/0). Gain concentrated in workshop (0.625 → 0.812); assembly and delivery unchanged.
- 3 Correction: W+A − W +0.17 [0.04, 0.29] (4/0); stale −0.08 [−0.21, 0.04].
- 4 Specificity: FAILS. W+A − W+X complete-pair −0.02 [−0.10, 0.06]; the wrong-episode (same-world) adapter does as well: W+X − W complete-pair +0.08, correction +0.125, stale −0.125.
- Reading: training on this world's harder worked examples helps somewhat, but the gain is not specific to the episode's own facts; it looks like a same-world skill/format effect. CIs are wide (12 episodes).

## 2026-11-04 — 12-example support built; memory probe passed; comparison running (source 1.6.2)
- David: build harder dev examples; option (a) for the eventual sealed set (old sealed file stays unopened with its commitment; replacement generated with a fresh seed only after the support recipe is settled).
- data/dev_all_s12.jsonl (sha 75ca4e01…, support seed 487bd4ec72e5410d): same 24 episodes, scored questions byte-identical to dev_all; 12 worked examples each = one verified fact-flip pair per scored flip type + 2 worked corrections scoped to their own example + 2 ordinary; unique answers; no situation repeats a scored one or another example (canonical state+goal, ignoring option labels/order). 0 key problems.
- Training exposure change: schedule "each_source_once" — 12 steps visit each of the 12 source examples once (variant original/relabeled drawn by seeded rng). Old: 12 steps over 6 sources × 2 variants (each source twice).
- Memory probe (2 longest delivery episodes): peak 17.5 GiB; ~4.1k tokens/step (≈49.4k train tokens per adapter vs ≈24k before); train ~66 s, eval ~62 s per episode; resets 0.0.
- Running stage s12-loo: same 12 episodes, settings and seed as ctx-loo; W, W+A, W+X all with the identical expanded packet. Primary: W+A − W.

## 2026-11-04 — Steps 2–3 done: support learning, no held-out transfer (development only)
- 12 dev_all episodes, S1, both stages; W answers identical across stages (determinism check); all reset checks 0.0. analysis/COMPARE-ctx-loo-vs-ctx-rules_only.json, stages/ctx-*/SUPERVISION.json, ANALYSIS.json.
- 1 Learning: supervision was NOT saturated on the choice tokens — first-step choice NLL 1.21 (loo) / 2.71 (rules_only) while full-target loss was 0.15 / 0.34. Support accuracy (same prompt format) before→after: loo 0.85→0.97; rules_only 0.82→0.99 (in its own format; 0.85→0.90 in loo format).
- 2 Transfer: none. Complete-pair W 0.375; W+A 0.354 (loo, −0.02 [−0.08, 0.04]) and 0.333 (rules_only, −0.04 [−0.10, 0.00]); episodes better/worse vs W 1/2 and 0/2. No flip type improved; "rating" fell 0.25→0 in both.
- 3 Correction: +0.04 in both (one delivery item), stale −0.04; identical for W+X, so not adapter-specific.
- 4 Specificity: W+A−W+X +0.02 (loo) / +0.06 (rules_only); CIs include 0. Rules-only W+X was worst (−0.10 vs W).
- Pattern = "support learning without held-out improvement" → improve example coverage and difficulty. Support items are easier than scored items (base support accuracy 0.85 vs scored marginal 0.61) and cover the scored flip types only partially.

## 2026-11-04 13:14 — Step 1 (common instruction) done; steps 2–3 launched
- Text-only on all 24 dev_all episodes: complete-pair S0 0.333, S1 0.344, S2 0.323; correction 0.458/0.438/0.458; stale 0.50/0.52/0.52. S1 selected by the pre-declared rule (config/INSTRUCTION-SELECTION-RULE.md, RESULT.md); spread ≈ one pair in 96, not a meaningful difference. All reset checks 0.0.
- Steps 2–3 (source 1.6.1): 12 dev_all episodes (4 per world), S1, LoRA r8/α16 qkvo, 12 steps, lr 1e-4, n_aug 1, seed 2000; training context "loo" (1.6.0 method) vs "rules_only" (no solved examples in training prompts; rules and facts kept); evaluation always full packet. Records choice-token NLL, support accuracy before/after, gradient and weight-change norms.

## 2026-11-04 12:41 — Gate 2 smoke PASSED (technical); accuracy = development observation only
- 6 dev episodes (2 per world), Qwen3-8B thinking off, S1, LoRA r8/α16 q,k,v,o, 12 steps, lr 1e-4, offline (unshare -rn). stages/smoke/, ANALYSIS.json, smoke.log.
- Parsing: 432/432 replies were canonical {"choice": ID}; 0 invalid; an independent strict regex matched the parser on every row.
- Save/load: every adapter re-loaded bit-identical (weights) and gave identical task-probe logits (max diff 0.0); file hashes re-verified before use.
- Reset: tolerance 0.0 declared before adaptation; every check (start, after 6 trainings, after 6 evaluations, end; reference + task probes; disabled + null adapter) = 0.0. Base full sha256 identical start/end; fingerprint unchanged after every episode.
- GPU: peak 16.4 GiB of 24; ~26 s per adapter (≈24k train tokens), ~40 s per episode for W, W+A, W+X.
- Development observations (n=6, not evidence): W complete-pair 0.54, marginal 0.69, correction 0.33 (stale choice 0.42), unrelated 1.00. W+A−W complete-pair −0.08, W+X−W −0.13.
- Flag for development: support-training loss is near zero from the first step (mean first-step loss 0.14), i.e. the base model already answers leave-one-out support examples in context; the adapter still moves task-probe logits (max 0.7–2.1) but gets little gradient signal.

## 2026-11-04 — development fixtures and Gate 2 safeguards (David's review)
- David: proceed with dev-only Gate 2; sealed set stays unopened. Keep the empty-plan rule; keep same-type support examples, claimed precisely.
- Added data/dev_all.jsonl (24 dev-only episodes, one pair per each of the four flip types per world, incl. "goal already holds"), sha 5ad28b1f…, own commitment; 0 key problems. Sealed file untouched (not read or hashed).
- Support coverage recorded (data/DEV-FIXTURES-REPORT.json). Support examples are sampled from the permitted flip types, not guaranteed: in dev_all, 16/18/18 of 32 evaluated flip cases per world (delivery/assembly/workshop) have no same-type support example; in dev, 2/6/9 of 16. Committed dev split reproduced byte-for-byte from its seed to obtain this. Sealed coverage to be recorded when it opens.
- Runner: W+X mapping validated before model load; reset_tolerance declared in the stage config (smoke: 0.0, exact) and enforced at start, after every training, after every evaluation, and at end, on the reference probe and a dev-task probe, both with adapters disabled and with the zero null adapter; save/reload functional check on the task probe; adapter file hashes re-verified before use. 177/177 tests.
- Gate 2 smoke launched: 6 dev episodes (2 per world), offline (unshare -rn).

## 2026-11-04 12:10 — Gate 1 PASSED (no model)
- Seed 076f3d0ac5b2686d. Dev: 24 episodes (8 per family), sha 66971ee1…; sealed: 120 episodes (40 per family), sha db60b5e8… (file read-only, never opened by dev code).
- Every key in both splits (support + evaluation queries) re-derived by solver 2: 0 problems. Pairs share options and have disjoint keys; irrelevant controls keep keys; corrections flip keys.
- No invented label is shared between dev and sealed. Flip templates: dev closed/goalplace, rating/occupied, stock/goalitem; sealed already/elsewhere, already/onhand, owned/permit.
- Each episode: 6 support examples, 4 fact-flip pairs, 2 irrelevant-detail controls, 2 corrections; 4 options per query; prompts ≈1.5–2k tokens.
- Next: Gate 2 smoke (3 dev episodes) — awaiting David.
