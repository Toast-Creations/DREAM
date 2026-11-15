# Reversible learning (DREAM2 and explicit context)

**Question.** Can a model learn something specific to one episode in temporary LoRA adapters, while the base weights stay frozen, and can the adapter then be removed so the model returns exactly to its original state?

**What was tested.**
- *DREAM 2 on Qwen3-8B, October 2026.* The adapters memorised their training worlds instead of learning the rules behind them, with thinking on or off. The closed-book concept-learning extension was specified but not run.
- *Explicit-context adapters (1.6.0–1.6.4, November 2026).* The primary outcome was complete-pair correctness on fact-flip pairs. This was chosen after a novelty check, because "adapter plus context beats context alone" is already established by earlier test-time-training work. Adapters learned their support examples well (choice accuracy rose from 0.85 to 0.97). The held-out gain was W+A−W **+0.056 [−0.007, 0.132]**, and an adapter trained on a *different* episode from the same world did about as well, so the gain is not specific to the episode. The recipe was stopped under a pre-declared decision rule. The sealed evaluation set was never opened.

**Engineering that held up.** Adapter reset and save/load are bit-exact. Rollback is verified by hashes. Adapters are never merged into the base weights.

**Read more.** See the [study index](../studies.md#reversible-learning-dream2-explicit-context) and protocol documents [03](../protocols/03-DREAM2-Research-Paper.md), [15](../protocols/15-Concept-Learning-Protocol.md) and [19](../protocols/19-Broad-Concept-Learning-Protocol.md). Proposal [E6](../proposals/E6.md) (identity imprinting) would continue this line.

**Code.** `src/dream2`, `src/ectx`, `scripts/ectx_*.py`.
