# Donor controls and seed repeats — declared 2026-11-04 before any of these stages ran

Approved by David (2026-11-04) as a bounded development check. Sealed replacement still waiting.

Episodes: the 12 dev_all_s12 episodes of s12-loo (4 per world). Packets, scored questions, settings fixed.
Seeds (training randomness only: adapter init, schedule order, relabeled-variant draws): 2000 (original s12-loo),
3000, 4000. Per-episode adapter seed = seed + episode index.

Conditions for every seed: W (text alone), W+A (own adapter), W+X (wrong, same world), W+Y (wrong, different world).
Seed 2000 gets W+Y from its saved adapters (stage s12-loo-cross; W re-run there must be identical).

W+X donors (unchanged from s12-loo; cyclic within world):
{
 "devall-delivery-000": "devall-delivery-001",
 "devall-delivery-001": "devall-delivery-002",
 "devall-delivery-002": "devall-delivery-003",
 "devall-delivery-003": "devall-delivery-000",
 "devall-assembly-000": "devall-assembly-001",
 "devall-assembly-001": "devall-assembly-002",
 "devall-assembly-002": "devall-assembly-003",
 "devall-assembly-003": "devall-assembly-000",
 "devall-workshop-000": "devall-workshop-001",
 "devall-workshop-001": "devall-workshop-002",
 "devall-workshop-002": "devall-workshop-003",
 "devall-workshop-003": "devall-workshop-000"
}

W+Y donors (each adapter donated exactly once; each world's targets draw two donors from each other world):
{
 "devall-delivery-000": "devall-assembly-000",
 "devall-delivery-001": "devall-workshop-001",
 "devall-delivery-002": "devall-assembly-002",
 "devall-delivery-003": "devall-workshop-003",
 "devall-assembly-000": "devall-workshop-000",
 "devall-assembly-001": "devall-delivery-001",
 "devall-assembly-002": "devall-workshop-002",
 "devall-assembly-003": "devall-delivery-003",
 "devall-workshop-000": "devall-delivery-000",
 "devall-workshop-001": "devall-assembly-001",
 "devall-workshop-002": "devall-delivery-002",
 "devall-workshop-003": "devall-assembly-003"
}

Analysis (scripts/ectx_seed_analysis.py, source 1.6.3): 12 independent episodes, seeds averaged within episode
(not 36 units); world-stratified bootstrap over episodes, equal world weights, 10,000 resamples, 95% percentile.
Primary: complete-pair W+A - W. Mechanism diagnostics: W+A - W+X and W+X - W+Y. Also W+X - W, W+Y - W.
Reported alongside: corrections, stale choices, each world, each seed. No mechanism is assigned before the
contrasts and their uncertainty are reported; different-world gains would not uniquely establish "format practice".
