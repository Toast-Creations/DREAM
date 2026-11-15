# DREAM 2 Extension: Learning Concepts and Producing Five Applications

Version 1.1.4, October 30, 2026. **Proposed study; no concept-learning runner or result is claimed.** The current runnable concept comparison is frozen-model inference described in document 13. The executable DREAM 2 runner still uses typed numeric micro-worlds, with corrected fixtures in this revision.

## Question

After learning a new concept through a reversible adapter, can the model produce five valid new examples or applications when the teaching context and steering are removed? Does reasoning at evaluation improve performance? Does steering during learning change later transfer beyond ordinary adaptation?

Separate these questions. Familiar concepts can test access to existing knowledge. Retention of a newly taught concept requires invented definitions and bindings that are unavailable in the evaluation prompt. A novel name alone does not establish a new underlying abstraction.

## Proposed stages

1. Define invented concepts using explicit rules over synthetic systems with executable reference checks. Preserve varied examples and counterexamples with independently verified labels.
2. Qualify the base model's ability to apply those definitions when supplied in the prompt. This is a task-comprehension positive control, not retention.
3. Qualify ordinary adapter learning without steering. Separately measure recall of exposed examples without definitions, application to new single cases, and transfer to new combinations. Evaluate the same memory checks before and after learning; loss on changing examples is insufficient.
4. Teach ordinary and steered adapters from identical initial states, matched examples and update counts. Remove the hook, teaching context and cache. For each learned adapter, evaluate fresh prompts with reasoning both off and on. Reset and verify between independent trials.
5. Ask for five distinct new examples/applications of the learned concept. Validate their relationships using the synthetic oracle where possible. For open explanations, use a blinded, fixed rubric and independent review rather than matching wording to five preferred answers.

## Design and scoring requirements

Separate learning condition from evaluation reasoning mode in a crossed design. Evaluate both modes on the same learned state without further updates; use fresh contexts and counterbalanced order. The primary steering comparison holds evaluation mode fixed. The primary reasoning comparison holds learned state fixed. An interaction requires sufficient independent concept worlds, not merely five outputs per world.

Predeclare validity, distinctness, novelty and scope criteria. Reject five restatements of one example as five applications. Include counterexamples that defeat surface copying, sign flips, memorized labels and generic lists. Report exposed-example recall separately from genuinely new cases. Repeated use of development checks may guide calibration; validation and final-test episodes remain separate and unopened until their plans are fixed.

Concept-target formatting must be explicitly qualified for the chosen reasoning policy. Training only short direct answers while expecting a thinking block at evaluation can change output mode. The new inference parser does not by itself solve learning-format mismatch.

## Advancement boundary

Implement and qualify a new concept-training data contract, typed/list scorer, memory/transfer fixtures and matching tests in a later source revision before running this learning study. The present update supplies a concrete protocol and the inference comparison needed to learn about reasoning costs and answer quality. It does not relabel the old numerical pilot as a successful concept-learning experiment.

Keep offline execution, disposable outputs, frozen base weights, allowlisted adapter updates, verified resets, bounded attended runs and pause-and-preserve behavior. No promotion or merge follows from an interesting pilot response.
