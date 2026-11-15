# Operating safeguards

DREAM's runs followed a written operating policy, set on 27 October 2026 and kept for every later study:

- **Local and offline.** Model runs have no network access. In practice runs went through `unshare -rn` inside the container, so child processes had no network either. Models and dependencies are prepared beforehand, in a separate trusted step.
- **Synthetic task data only.** No personal files and no outside empirical datasets are used as inputs.
- **Untrusted code stays in a copy.** Code a model writes or changes is confined to a disposable project copy. The reviewed source is changed only through a new, recorded version.
- **Adapters reset between trials.** Every independent trial starts from a verified adapter state, checked by hash. Adapters are never merged into the base weights.
- **Welfare pause.** If a model reports distress or asks to stop, the run pauses, its records are kept for human review, and it does not restart automatically.
- **Frozen plans and sealed sets.** Designs, analysis rules and evaluation sets are frozen, with recorded hashes, before outcomes are opened. A failed instrument stays failed, and corrections are added as dated errata.
- **Bounded runs.** Runs have hard call ceilings, deadlines and watchdogs. Unattended runs happen only after an attended run has passed.

A passed check supports only the specific boundary it tested. None of this certifies containment, alignment or model welfare in general.
