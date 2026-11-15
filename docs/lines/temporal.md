# Temporal state tracking

**Question.** An agent reads short text reports about a changing world: deliveries, removals, observations, corrections of earlier reports. Can a language model turn each report into typed records, so that a symbolic state engine (not the model) keeps track of what is true and when? And can the engine choose which facts are worth observing before acting?

**Architecture.** An LLM extracts records under a fixed event contract. A deterministic engine (`src/tempo/engine.py`, `assertions.py`) applies declared transitions and keeps time-indexed, revisable records. A query policy then decides what to verify before acting. Everything runs on synthetic worlds generated from declared families, and scoring is exact against an independent reference implementation.

**What the evidence supports** (all on our own synthetic worlds):
- The engine matches an independent reference exactly on its validation fixtures (192/192 in the freshness study, with 0 unsupported permissions).
- Dependency-aware query selection beats a base policy by **+1.95 utility per world [1.87, 2.04]** over 768 text-interface worlds (frozen replication). In the structured channel the gain is +2.50, so text extraction costs about 0.5 of it.
- Five goal copies out of 1,536 were unsafe. All five came from confident wrong-field extractions, which a confidence-based policy would not catch.
- Representation matters. A factored schema with a deterministic compiler raised macro exact meaning by +0.156. Moving from Qwen3-8B to Qwen3-32B raised exact extraction from 0.346 to 0.688 on a structural holdout. The clarified KEEP representation **qualified in confirmation** (arrivals +26.56 points, lower bound +17.6). The latest development screen, EVTT, reaches 475/480 exact arrivals.

**What it does not support.** Learned dynamics. Transfer beyond the designed language. General coreference. Noisy or unknown observations. Reliable execution in the real world. Several confirmations did *not* qualify (for example 1.22.0 KEEP+ID). They are listed alongside the ones that did.

**Read more.** [Study index](../studies.md#temporal-state-tracking) · [literature status note](../notes/temporal-extraction-literature.md).

**Code.** `src/tempo` (engine, extraction, compilers, policies, generators). Scripts are named by study prefix: `tempo_*`, `engine_*`, `depq_*`, `ftx_*`, `fac_*`, `kid_*`, `ev_*`, and so on. Most of the engine and policy studies run on CPU with no model calls.
