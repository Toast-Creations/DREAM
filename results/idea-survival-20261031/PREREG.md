# Continuity pilot: pre-registration (written 2026-11-02 before any pilot generation)

**Theory under test (David):** an idea introduced while the model is decategorized, then processed while it returns to baseline in the same context, yields more surprising-yet-workable (practical) or surprising-yet-intelligible (artistic) connections.

**Source:** `Code/DREAM-project-1.5.0-continuity-20261102` (142/142 tests).
**Model:** Qwen3-8B, reasoning off, layer −8 (block 28), using the qualified 1.2.3 decategorization vector and the frozen random set (seeds 271828…).

**Design:** 6 new development tasks (3 practical, 3 artistic) × seeds 11/23/47 × 5 arms = 90 chains, each one continuous generation (IDEAS, THINKING, DEVELOPMENT, FINAL).
- Arms: baseline; perceive_targeted / perceive_random (task text steered at prefill, λ = 0.20, then the decode dose glides to 0 over 300 tokens); generate_targeted / generate_random (smooth 50/250/300-token curve, peak 0.20).
- Strength 0.20 was chosen by the pre-declared smoke rule. Both 0.10 and 0.20 passed; see `gpu/qwen3-continuity-smoke-20261102-040513/output/SMOKE-REPORT.json`.

**Manipulation check result from the smoke (reported before the pilot):** on 2 tasks, the greedy category probe after a steered reading was identical to baseline for perceive_targeted at both strengths. perceive_random changed the categories on the artistic task (Jaccard distance 0.75). So the smoke shows no category loosening specific to the targeted direction. The probe runs again on all pilot chains.

**Primary endpoint:** blind pairwise judgements from the qualified pairwise-c1 instrument (Claude; `judging/pairwise-c1`, qualified 16/16 and 6/6 before any pilot pair).
- Per task and seed, FINAL sections are compared in both display orders: perceive_targeted vs perceive_random, and generate_targeted vs generate_random (**primary**, because random direction is the decisive control).
- Targeted vs baseline in each mode is **secondary**.
- Score per presentation: +1 targeted preferred, −1 other, 0 tie. Averaged within task; sign test across the 6 tasks; reported separately for practical and artistic.

**Interpretation rules:**
- Six tasks are descriptive. Even a 6/6 sign result (p = 0.03) is a pilot signal, not a confirmation.
- A positive pilot in a mode leads to a proposed confirmation on the sealed 24 tasks.
- No difference, or random ≥ targeted, is reported as the theory being tested and unsupported at this scale and strength.
- No resampling, no strength retuning, no post-hoc endpoint.

**Secondary measures:** the category probe; delivery (sections, EOS, ideas); token counts; order consistency.
