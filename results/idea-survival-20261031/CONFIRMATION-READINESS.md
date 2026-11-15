# Confirmation readiness (test 5)

**David's decisions (1 Nov, 17:15):**
- Judges rate final-stage ideas only; starting ideas are released for outside review.
- No 10% audit in confirmation; the pilot audit gives the reliability estimate.
- Qwen first; Mistral is a separate later decision.

**Revised Qwen confirmation judging estimate:** 288 chains × about 5.15 final-stage items × 2 judges ≈ 2,970 calls, plus 576 lineage calls ≈ **3,550 calls**. That is about 1,775 per judge, or about 5 capped launches. The freeze script already encodes these decisions.

**Pilot judging (x2, final-only):** 2,490 calls, about 1,245 per judge, or 3–4 capped launches.

1 November 2026, evening. Nothing has been frozen or run. **Confirmation needs David's explicit go.**

## Ready
| Item | State |
|---|---|
| Tasks | `materials/confirmation/tasks-v2.jsonl`: 24 tasks (8 practical, 8 analogy, 8 artistic), sha256 `bcc9497a…`, never given to a generator |
| Source | `Code/DREAM-project-1.4.2-extraction-fix-20261101`: repaired extraction, 129/129 tests |
| Queue | `Tools/Idea-Survival/run_queue.py` requires ≥129 tests for 1.4.2 hubs and runs the extraction gate after every stage |
| Vectors | Qwen reuses the qualified 1.2.3 vector. Mistral reuses its pilot-hub vector via `prepare_run.py --vector` |
| Freeze script | `analysis/freeze_confirmation.py` points at 1.4.2 and scoped-v4. Its `--dry-run` finds 16/17 inputs; the missing one is `judging/INSTRUMENT-FREEZE-v4.json`, which is written when qualification passes |
| Analysis | `analysis/analyze.py --base judging/scope-v4/<label>` reads v4 outcome tables |

## Blocking, in order
1. **Judge qualification:** Codex resets at 7:03 PM tonight. Run `judging/resume_scope_v4_x2.py --release-quota --qualification-only`.
2. **Pilot judging (x2 packets):** needed for the precision check. The handoff requires estimating precision from the pilot before confirmation; if more than 24 tasks are needed, write an extension plan rather than silently expanding.
3. **Workflow choice:** "develop" by the declared default rule. The developer comparison can be rechecked once the x2 devqual packet is judged.
4. **David's go**, then the freeze, then the GPU runs.

## Measured costs (from the pilots, not guesses)
**GPU** (sequential, one model at a time; 288 chains = 4× the pilot):
- Qwen3-8B: 5,355 s per 72 chains, so about **6.0 h**.
- Mistral-7B: 4,149 s per 72 chains, so about **4.6 h**.
- Plus about 10 min of qualification fixtures per hub.

**Disk:** pilot unit records are about 5 MB per model, so about 20 MB per model for confirmation. 692 GB is free.

**Judging** (scoped v4: one primary call per judge per item, 10% audit with 2 extra calls per judge, lineage once per chain per judge):

| Model | Items per chain (pilot) | Items | Primary | Audit | Lineage | Total calls | Calls per judge |
|---|---:|---:|---:|---:|---:|---:|---:|
| Qwen3-8B | 10.15 | ≈2,924 | 5,848 | ≈1,168 | 576 | **≈7,590** | ≈3,800 |
| Mistral-7B | 10.61 | ≈3,056 | 6,112 | ≈1,224 | 576 | **≈7,910** | ≈3,960 |

That is about 15,500 calls in total. With the per-launch cap of 400 calls per judge, it takes about **20 launches**. At Codex's observed weekly cap (about 1,700 calls before the limit last week), Codex alone needs roughly **4–5 weeks** of quota, on top of about 1.3 weeks for pilot judging. The Claude calls draw on David's own Claude plan.

## Ways to cut judging cost (David's decision; must be declared before the freeze)
- **Rate final-stage members only.** Initial ideas feed secondary measures, not the primary endpoint. This roughly halves content calls, to about 8,800 in total.
- **Drop the 10% audit for confirmation**, using the pilot audit as the reliability estimate. This saves about 2,400 calls.
- **Run Qwen first, judge it, then decide on Mistral.** This keeps the option open without committing the full budget.

Each option changes what the confirmation can report and has to be written into the freeze, not decided after seeing outputs.
