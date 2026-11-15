# Does the observation-policy benefit survive text interpretation? (V1.9.1): report (development only)

## Status
- **Brief and plan:** brief `TEXT-INTERFACE-POLICY-TEST-BRIEF.md`; plan `design/STUDY-PLAN.md`, frozen before any output (`config/FROZEN-PROTOCOL.json`; budget in `config/MAIN-CONFIG-FROZEN.json`).
- **Source and tests:** source 1.9.1. Tests 110/110 in the container, including a byte-for-byte regeneration of all 144 scored 1.8.2 prose prompts.
- **Ran 2026-11-05:**
  - Smoke: 24/24 calls, at 12:44, not pooled.
  - Main: 144/144 calls, 12:57–13:06 (503 s; 481 s generation; 16,314 output tokens).
  - No call failed or was truncated, and there were no infrastructure retries. Nothing changed after smoke.
  - The run shared the GPU with Hearthstone, with David's approval.
- **Model and inputs:** Qwen3-8B rev b968826d…, bf16, thinking off, greedy decoding. Frozen 1.8.2 extraction prompt, adapter v1, engine v0.3, and the P0/P1/P2 policies unchanged.
- **Sample:** 24 fresh episodes × 3 policies × 2 channels = 144 trajectories. The sensor stayed structured.

## Main results (24 episodes, paired)
| Channel : policy | Utility, mean [95% CI] | Success | Invalid attempts | False blocks | Facts queried | Decisions with a conflict |
|---|---|---|---|---|---|---|
| structured : P0 accepted | 1.583 [0.29, 2.96] | 10/24 | 4 | 8 | 0 | 0 |
| structured : P1 always | 3.125 [2.17, 3.96] | 22/24 | 0 | 0 | 36 | 0 |
| structured : P2 selective | 3.667 [2.71, 4.50] | 22/24 | 0 | 0 | 23 | 0 |
| **text : P0 accepted** | 1.292 [0.08, 2.62] | 9/24 | 4 | 9 | 0 | 1 |
| **text : P1 always** | 2.833 [1.79, 3.75] | 21/24 | 0 | 1 | 36 | 1 |
| **text : P2 selective** | **3.333 [2.33, 4.25]** | **21/24** | **0** | 1 | 24 | 1 |

Each channel has 2 episodes with no valid plan (`no_plan`), where declining is correct.

| Contrast (per episode) | Utility | Better / equal / worse |
|---|---|---|
| **Text: P2 − P0 (primary)** | **+2.04 [0.71, 3.38]** | 11 / 6 / 7 |
| Text: P2 − P1 | +0.50 [0.25, 0.75] | 10 / 14 / 0 |
| Structured: P2 − P0 / P2 − P1 | +2.08 [0.79, 3.42] / +0.54 [0.29, 0.83] | |
| Each policy, text − structured | P0 −0.29, P1 −0.29, P2 −0.33 | 0 / 23 / 1 for each |
| Change in P2's benefit, text − structured | −0.04 for both P2 − P0 and P2 − P1 [−0.12, 0.00] | 0 / 23 / 1 |

**The policy benefit survived the text interface almost intact.** In 23 of 24 episodes, every text trajectory matched its structured clone exactly: the same plan, the same queries, the same outcome. Selective verification kept its advantage over acting on accepted evidence (+2.04) and over always verifying (+0.50). The text channel cost each policy about 0.3 utility, and all of that loss came from the one episode below.

## Where the language interface lost
**The one decision-relevant error.** In `textpol-ass-verified_settled-1`, the report "it is verified that at time 5 part Mutomedi arrived for you and is now on hand" was transcribed as a **state assertion** ("on hand at time 5") instead of a delivery **event**. The verified opening report said the part was not on hand at time 0, and no change was recorded in between, so the frozen contract treats this as a **conflict between two verified claims**. It keeps the conflict rather than choosing between them.
- **P0** declined: the conflict blocks any guaranteed plan.
- **P1** queried both relevant facts, but the sensor reading cannot resolve a verified–verified conflict under the contract, so it declined after spending 2 queries.
- **P2** queried only the conflicted fact (stock), then declined.

All three missed a feasible opportunity. **None made an invalid attempt.** The conflict made the system cautious; it did not make it act wrongly. This is the same semantic error as in the last two studies ("delivered to you" read as a fact). The contract now turns it into a visible conflict rather than a silent wrong state.

**Extraction overall** (144 records):
- 140 accepted; 4 unprocessed (could not be mapped).
- 124 meaning-preserving and fully covered; mean assertion coverage 0.861.
- 0 wrong statuses. N3 fired 7 times.
- 20 records did not preserve meaning, all from change or observation records, and all but one about padding entities that no decision depends on:
  - 10 assembly or delivery events transcribed as state assertions, 1 of them decision-relevant (above);
  - **6 "taken by another team" events read as a correction of an earlier report.** This is a new error type;
  - 4 not mappable.
- So the extraction error rate for records (20/144) was much higher than its effect on decisions (1/24 episodes). How much an error matters depends on whether it touches a decision-relevant fact.

**Limit, declared before the run:** a wrongly extracted *verified* claim looks settled, so P2's evidence-status trigger cannot single it out. Here the error contradicted other verified evidence and surfaced as a conflict, so P2 did query that fact. An error that didn't contradict any other verified report would have passed unnoticed under every policy.

## Integrity
- **Earlier-information view:** preserved in all 144 trajectories.
- **Planning:** never changed the log (asserted).
- **Shared extractions:** the six extractions per episode were shared across the three text clones.
- **No repairs:** no gold value was used to correct the channel, nothing was retried, and no conflict was overridden.

## Reading (plan rules)
- **Supported, under the stated assumptions:** P2 still saves observations without losing outcomes when its input comes through the frozen text extractor. That supports this fixed end-to-end system on these 24 new instances, assuming a reliable structured sensor, a stable world, and relevance supplied in advance. It does not show optimal or learned querying, and the broad idea of selective verification is not new (DIVA, REVOIR and the ACL 2026 value-of-information work all precede it).
- **Where the remaining loss sits:** event-versus-state transcription of "delivered" or "arrived" reports, and change-versus-correction confusion. Both are extraction errors. No loss came from query selection or from handling the fresh sensor evidence.
- **Next questions (not started):**
  - targeted handling of those two extraction errors;
  - whether a fresh verified sensor reading should be allowed to resolve a verified–verified conflict about the current value. That would be a contract change, and would need its own justification and test;
  - and, kept separate: sensor noise, change during the observation delay, value-of-information query selection that can stop when resolving a fact can't change the decision, reversible versus costly mistakes, and a budget-matched random-query baseline.

## Artifacts
- **Analysis:** `analysis-textpol/{trajectories.jsonl, extraction.jsonl, ANALYSIS.json, TABLES.md}`; smoke in `analysis-textpolsmoke/`.
- **Raw replies:** `stages/{smoke,main}/calls/`.
- **Inputs:** `data/` (episodes with prose texts, calls, gold, commitments).
- **Re-score:** `python3 -B scripts/textpol_analyze.py --hub HUB --set textpol --stage main`
