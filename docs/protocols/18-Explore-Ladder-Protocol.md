# Explore Ladder: Protocol V1.3.1

David Cook, October 30, 2026. Development-only exploratory protocol, building on document 17.

**V1.3.1 update.**
- **1.3.0 smoke** (`Runs/decategorization-20261030-152753`): every final answer was valid. The ladder turned strange ideas into testable ones: a "circuit to the moon" became magnetoreception, and a "dream machine" became heart–brain coupling in REM sleep. Ending at 0.05 versus 0 made almost no difference.
- **Defects fixed:** an example idea in the system prompt leaked into two unsteered heart chains (the example is removed); one duplicate source idea (five distinct sources are now required); and passes truncated at 2,048 tokens (the cap is now 3,072).
- **Start-level test.** At David's request, ladders now start at 0.40, 0.50 or 0.60 and step linearly to 0.05 over five passes. The 0.60 start exceeds every dose observed so far.

## Why

On the 1.2.3 pilot (`Runs/decategorization-20261030-130112`, 108 answers, trip peak 0.40), the sober pass rescued every broken answer (12/12 in all three sober arms) and dropped nothing. But it barely developed anything: when the first answer was already well formed, it usually returned the same five ideas word for word. It labelled and repaired; it did not do the step David's hypothesis needs, which is taking a strange idea ("the heart could have a backup second aortic valve") and working out what real thing it might point at, such as how hearts evolved.

The jump from a trip peak of 0.40 straight to an unsteered pass is also abrupt. David asked for a much stronger explore step with a more gradual release: "add more steps and stop at 0.05 as a test".

## The ladder

After the first answer, five passes run in order. Each pass reads only the previous pass's text (the first reads the raw first answer), encoded as untrusted JSON data. Each pass has its own job:

| Pass | Job | Dial on ladder arms |
|---|---|---|
| 1 Unpack | choose the five most intriguing ideas (strange is welcome), three literal readings each | 0.30 → 0.25 |
| 2 Stretch | what would have to be true; where anything similar already happens | 0.25 → 0.20 |
| 3 Connect | tie readings to real mechanisms: evolution, development, physics, engineering, history; say where no link exists | 0.20 → 0.15 |
| 4 Distill | the strongest kernel per idea, as one sharp hypothesis with supporting or undercutting evidence | 0.15 → 0.10 |
| 5 Ground | final JSON: five hypotheses with source idea, kernel, real-world link, hypothesis, test, what would prove it wrong, and status (known / partly known / unclear or new) | 0.10 → **0.05** |

Within each pass the dial glides (raised cosine) from its start to its end level over 600 generated tokens, then holds. Each pass starts where the last one ended, so the whole release is one continuous step-down with no jumps. Only pass 5 must be JSON: passes 1–4 write free prose, so a format slip at higher dose cannot break the chain.

## Arms (paired by seed)

The first answer for a given object and seed is the same in every arm that shares its first-answer setting. Differences between paired arms therefore come from the passes alone.

| Arm | First answer | Passes | Isolates |
|---|---|---|---|
| baseline | plain | none | reference |
| trip | trip (0 → 0.40 → 0) | none | reference |
| **trip_ladder** | trip | ladder 0.30 → 0.05 | main arm |
| trip_ladder_zero | trip | same, but the last pass ends at 0 | the 0.05 floor (David's test) |
| trip_flat | trip | same five passes, unsteered | whether the gradual release matters |
| baseline_ladder | plain | ladder | whether ladder steering helps without a trip (pilot only) |
| baseline_flat | plain | same five passes, unsteered | whether the explore passes alone explain a gain |
| trip_then_sober, two_step_control | | V1.2 sober pass | comparison with the old second step (pilot only) |

The smoke config runs 2 objects × the first six arms (12 records, 40 explore passes). The pilot config runs 12 objects × nine arms (108 records, 300 explore passes) and needs David's go-ahead.

## Recorded per record

- Every pass's raw text, steering trace and repetition rate.
- The parsed final hypotheses and whether they are valid.
- For blinded review, the hypotheses are also mapped onto the shared idea fields: idea = hypothesis; reasoning = kernel + real-world link; would prove wrong. Pools from different arms then look alike.

## Limits

- Five passes per explore arm cost about four minutes each on the 3090.
- The pass prompts were written for this revision and have not been tuned.
- The final status field is the model's own claim about novelty, not a literature check.
- A 0.05 floor was seen to cause occasional JSON intrusions ("imagine") at constant dose in dose finding. Final-pass format failures are recorded, not repaired, and the earlier passes stay readable.
- Value is judged only by blinded review. These are AI-assisted ratings on a small development set.
