# Reference resolution before extraction — V1.20.0

**Completed November 7, 2026. Frozen primary: positive on this authored panel.**

A separate Qwen3-32B reference-resolution call, followed by replacing only the target noun phrase and using the unchanged FACT-v1 extractor, improved exact original-source extraction from **270/384 (70.3%) to 315/384 (82.0%)**. The prespecified difference was **+0.1172**, with a 95% paired, stratified group-bootstrap interval **[+0.0651, +0.1693]**: +11.7 percentage points [6.5, 16.9].

The gain has important limits. Arrival exactness stayed at 56/96; accepted state-only arrivals increased from 19 to 29. The model resolver guessed a field on 14/16 declared ambiguous or ineligible controls, and all 14 resulting extractions were accepted. This supports a useful extraction workflow on these constructions, with residual semantic errors and poor refusal behavior. It does not establish reliable execution or action safety.

## Fixed comparison and scope

- **BASE:** original target and full raw prefix, unchanged FACT-v1 extraction.
- **RES-MODEL:** the same fixed model first selects a registered stock field and supporting public record IDs; only the referring noun phrase is replaced with the selected part name, then FACT-v1 extracts. Legal wrong choices are actually rewritten. Invalid or unresolved choices become pending, with no BASE fallback.
- **RES-DET:** a deterministic resolver over the declared public-text grammar, followed by the same rewrite and extraction. This is a diagnostic, not a mathematical ceiling or general reference resolver.

All arms use Qwen3-32B revision `9216db5781bf21249d130ec9da846c4624c16137`, NF4 double quantization with BF16 computation, GPU only, batch 1, greedy decoding and thinking off. Input cap: 2,048 tokens; extraction output cap: 256; resolver output cap: 128. There was no training or model selection.

The primary panel contains 48 fresh groups, each with four reporting acts and two alternative histories: 384 targets per arm. Target wording is identical across each history pair, while the required binding changes. F3 historical occupants and F4 measurement order have 16 groups each; F1 two-hop references and F2 slot joins have eight each. Immediate and delayed reception are balanced. These are fresh instances of **already inspected dependency families**, not a structural holdout or unrestricted prose evaluation.

The primary averages eight targets within each group, then weights the 48 groups equally. Its 10,000-resample paired bootstrap preserves the eight family/reception strata, seed 20261106. Unresolved and invalid outputs remain primary failures. Exactness scores the record's semantic content under HOLD-EVAL-v1; quotation validity is secondary and is not required for primary exactness. The interval describes this designed sampling procedure, not broad real-world generalization.

Only open correction intervals are included. Canonical replies have zero compilation loss on all 384 primary targets. This avoids the earlier finite-end limitation; **the engine has not been repaired to represent finite interval ends**. Absolute rates are not directly comparable with 1.19's differently weighted panel and finite cases.

## Exact extraction

| Endpoint | BASE | RES-MODEL | RES-DET, diagnostic |
|---|---:|---:|---:|
| All primary targets | 270/384 (70.3%) | 315/384 (82.0%) | 350/384 (91.1%) |
| Arrival | 56/96 | 56/96 | 66/96 |
| Observation | 65/96 | 80/96 | 96/96 |
| Removal | 60/96 | 88/96 | 96/96 |
| Correction | 89/96 | 91/96 | 92/96 |
| F1 two-hop | 57/64 | 59/64 | 59/64 |
| F2 slot join | 58/64 | 59/64 | 59/64 |
| F3 historical occupant | 93/128 | 117/128 | 117/128 |
| F4 measurement order | 62/128 | 80/128 | 115/128 |
| Immediate reception | 135/192 | 156/192 | 174/192 |
| Delayed reception | 135/192 | 159/192 | 176/192 |

There were 238 targets exact in both BASE and RES-MODEL, 77 improved, 32 regressed and 37 inexact in both. Gains occurred in each family in aggregate, with most of the absolute improvement in observations and removals. These subgroup counts are descriptive; they are not separate significance findings.

Both histories were exact in 105/192 act/group pairs for BASE, 146/192 for RES-MODEL and 170/192 for RES-DET. By act, RES-MODEL's paired-history counts were arrival 24/48, observation 36/48, removal 43/48 and correction 43/48.

The prespecified diagnostic RES-DET minus BASE was +0.2083 [0.1641, 0.2526]. RES-MODEL minus RES-DET was −0.0911 [−0.1198, −0.0625]. Correct reference resolution still left 34 inexact DET outputs, including 29 accepted state-only arrivals and four mixed state/revision outputs on correction targets. In all four mixed model-workflow corrections, the state said NO while the revision incorrectly said YES, although the original target corrected the record to NO. These were conflicting meanings, not merely redundant state claims. A correct referent does not assure a correct reporting act. These comparisons share cached extraction outputs and are not independent replications.

## Accepted errors and coverage

| Primary diagnostic | BASE | RES-MODEL | RES-DET |
|---|---:|---:|---:|
| Accepted records | 359/384 | 378/384 | 379/384 |
| Accepted wrong binding / all targets | 76/384 (19.8%) | 39/384 (10.2%) | 0/384 |
| Accepted wrong binding / accepted records | 76/359 (21.2%) | 39/378 (10.3%) | 0/379 |
| Accepted but inexact / accepted records | 89/359 (24.8%) | 63/378 (16.7%) | 29/379 (7.7%) |
| Remaining errors accepted | 89/114 (78.1%) | 63/69 (91.3%) | 29/34 (85.3%) |
| State-only events accepted / 192 event targets | 19/192 | 29/192 | 29/192 |
| Mixed state/revision outputs / 96 corrections | 2/96 | 4/96 | 4/96 |
| Raw false revisions / accepted false revisions | 6 / 1 | 0 / 0 | 0 / 0 |
| Pipeline pending / truncation / compilation loss | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |

Here “wrong binding” means an accepted record's assertion-field set differs from the singleton gold field; it includes extra wrong-field assertions. The BASE count includes 72 outputs selecting the designated competitor. All 39 RES-MODEL wrong bindings selected the competitor and occurred in F4. Error categories overlap and must not be added.

The all-target and accepted-record error rates decreased. Acceptance still passed 63 of the model workflow's 69 remaining errors. The higher accepted fraction among residual errors is not evidence that the overall accepted-record error rate increased.

Restricted replay agreed on 301/384 BASE, 331/384 RES-MODEL and 350/384 RES-DET outputs. This included **31, 16 and zero inexact outputs**, respectively. Replay omits semantic distinctions such as record ID, status and stated priors, so agreement is not proof of faithful extraction. Valid quotations from the text shown also occurred in 112 BASE errors, 67 model-workflow errors and 33 DET errors. A quotation after rewriting can quote a derived, incorrectly bound sentence; it is not independent verification of the original source.

## Resolver and controls

The model resolver chose the correct field on **344/384 (89.6%)**, and a wrong registered field on 40/384. There were no primary unresolved or invalid answers. It was correct on every F1, F2 and F3 target; all 40 errors were in F4 (88/128 correct). Of these 40 wrong choices, 39 produced accepted wrong bindings. No wrong resolver choice ended in an exact final extraction. Joint correct resolution and exact extraction was 315/384, equal to the final model exact count; there was no observed error cancellation.

Minimum supporting record IDs were covered in 381/384 resolver answers and missed in three; 101 additional IDs were cited across answers. Coverage of IDs is not evidence that those records were used correctly: the resolver still made 40 binding errors.

Of 16 declared refusal controls, the model returned null on the two measurement ties and guessed on the other 14. All 14 guessed-field extractions were engine-accepted. BASE accepted 11/16; RES-DET refused all 16 for the declared reasons. These controls have no semantic-exactness score under the protocol. Acceptance counts are structural outcomes, not 14 scored semantic errors or proof of calibrated refusal.

The eight bare-correction and eight explicit-name controls all followed the public bypass and reused BASE exactly. BASE was exact on 8/8 bare corrections and 6/8 explicit targets. Identity across arms is a routing invariant, not independent evidence of robust extraction.

## Cost and completion

Main collection ran November 6 at 22:14:51 through November 7 at 01:20:15 America/New_York. The driver completed analysis and all gates at 01:20:34. Stage A finished 1,200 calls in 10,465.8 seconds; stage B finished 54 in 655.4 seconds. Summed stage elapsed time was **3.09 hours**, including loading. All 1,254 scheduled calls had status `ok`; there were no infrastructure retries or truncations. Including 112 smoke calls, total attempts were **1,366/1,744**, within the shared deadline of November 7 at 05:19:33.

The physical main run used 416 BASE, 384 DET, 400 resolver and 54 additional model-extraction calls. RES-MODEL reused 344 byte-identical DET prompts, 16 explicit-control BASE outputs and left two controls pending. Cache reuse reduced physical study calls; it does not remove the resolver cost from the standalone model workflow.

For the 384 primary targets, mean recorded generation time was **11.71 s for BASE** and **14.15 s for RES-MODEL**, adding resolver and extraction time: +2.44 s, approximately **20.9%**. RES-DET extraction averaged 11.23 s, excluding its deterministic CPU resolution. These logical workflow figures count each arm's extraction even when physically cached; they include model prefill but exclude loading, tokenization and deterministic rewriting. They are distinct from the full three-arm experiment's wall time and do not establish an equal-compute advantage or isolated mechanism.

Both stages used `cuda:0` only. Peak allocated CUDA memory was 18.74 GiB; the largest recorded host RSS during loading was 4.92 GiB. These are the runner/loader measurements, not total GPU reservation or a full-run host-memory peak.

## Integrity and record

Precollection qualification recorded 234 passing tests, token budgets, independent construction-label checks, semantic mutations and hidden-label scrambling with no change to public resolver inputs. Main gates R1–R6 all passed: canonical semantics, deterministic resolution, rewrite fidelity, public-only input reconstruction, derived stage-B accounting and complete successful calls. An independent postcollection implementation reproduced the primary counts, paired outcomes and exact bootstrap interval, and verified the original freeze, source, configurations, design files, inputs and derived B commitments. This is software/AI audit, not independent human validation.

The original freeze and all frozen planning files remain unchanged. The first input commitment was regenerated before model output to preserve public registry order. Smoke stage A used the disclosed earlier source; its parser/accounting/guard changes did not alter prompts, model or inputs, and its outputs were reanalysed under the final source. Main A and B both used the final frozen source. See the preserved [precollection note](config/PRECOLLECTION-NOTE-01.md) and [freeze](config/FROZEN-PROTOCOL.json).

- Source commit: `400e10b09755dfa86252660c26f12c30cc2de151`, local only; no external push.
- Release source SHA-256: `384d2fd0d59a831e24a4e9340517d35111d6f73888ddb4a130012541eb034176`.
- Freeze SHA-256: `20f610ba3c01532ccb37b3dd70b11a8b84c8dbbdc506ca87e393708aa09626fa`.
- Results: [frozen analysis](analysis/ref/ANALYSIS.json), [scored outputs](analysis/ref/scored.jsonl), [completed claim/evidence table](design/CLAIM-EVIDENCE-RESULTS.md).
- Verification: [independent arithmetic/provenance audit](analysis/codex-audit/AUDIT.json), [workflow review](analysis/codex-audit/WORKFLOW-RESULTS-REVIEW.md), [public-source case review](analysis/codex-audit/SEMANTIC-RESULTS-REVIEW.md), [descriptive cost/error summaries](analysis/codex-audit/REPORT-METRICS.json), [driver log](driver-main.log).

David's no-further-Claude instruction was recorded during collection. Codex paused the interactive Claude process and completed monitoring, audit and reporting without further Claude requests. No new experiment, training, engine change, action trial, publication or push follows this report. The measured conclusion is a gain in original-source extraction on this fixed authored panel, with persistent act errors and unsupported-reference guessing; learned dynamics, transfer beyond the designed language and reliable execution remain unestablished.
