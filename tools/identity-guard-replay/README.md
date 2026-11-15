> **Archived tool.** This is the IGUARD-v0.1 replay as it was run on 11 November 2026, with local paths moved to environment variables. It replays saved outputs against the archived V1.24.0 and V1.22.0 source trees (set `DREAM_HOME`), which are not included in this repository. Results: [results/temporal-identity-guard-replay-20261111-verify-e24e9ed](../../results/temporal-identity-guard-replay-20261111-verify-e24e9ed/REPORT.md).

# DREAM identity-guard replay v0.1 (IGUARD-v0.1)

Offline, CPU-only, rejection-only identity-consistency check replayed on saved V1.24 and V1.22 responses.
Plan: private planning notes (not published).

- `guard/decide.py`: the decision function. Inputs are only original public prefix, original target text, public
  registry/order and the raw reply. Unchanged `refres` resolves the subject (unresolved/unsupported → abstain);
  unchanged `factored.compile_reply` compiles; pass only when the compiled field set equals the resolved field.
- `guard/pins.py`: frozen V1.24.0 source tree imported read-only. `activate()` hash-checks only `refres.py` and
  `factored.py` before import; full-tree validation is `ig_plan`'s release-source-hash check against each study's
  FROZEN-PROTOCOL, and the evaluator refuses a seal whose recorded dependency hashes differ (see the docstring).
- `guard/studies.py`: public-only loader (refuses `hidden/` and `analysis/` paths; keeps only decision keys);
  membership/completeness checks. With expected totals enforced it also checks declared membership: allowed
  conditions, per-condition and per-act counts, every target scheduled, and pinned sha256 digests of the exact call
  and target IDs. `ig_plan` re-derives those digests from each study's frozen `config/stage-main.json` `select` list
  (hash-checked against FROZEN-PROTOCOL) and requires the schedule and public targets to equal it.
- `scripts/ig_decide.py` → sealed `DECISIONS-*.jsonl` + `SEAL-*.json` (public inputs only). Refuses (exit 3) if any
  output for that study already exists in `--out`; files are created exclusively and never overwritten.
- `scripts/ig_evaluate.py` → verifies the seal and, before any composition, every row's five input hashes against
  the public target/registry/order/prefix and saved raw reply it joins (plus seal metadata, duplicates, membership);
  any discrepancy → REFUSED, nothing composed. Then rescores with the pinned scorer, joins gold/scores, `RESULTS-*.json`.
- `scripts/ig_controls.py` + `fixtures/` → public-only controls with separately written expected labels.
- `scripts/ig_preserve.py`, `scripts/ig_plan.py`, `scripts/ig_report.py`; `run_replay.sh HUB` runs everything.
  `ig_report` separates technical criteria (stages, cap, manifests, tests, controls, sealed+deterministic ledgers,
  full-denominator coverage with verified provenance, preservation) from substantive outcome criteria: technical
  failure → INCOMPLETE / NOT READY; completed with an unfavourable outcome → COMPLETE / NOT READY.
- Tests: `PYTHONDONTWRITEBYTECODE=1 python -B -m unittest discover -s tests -v`.

Reproduce: `./run_replay.sh $DREAM_HOME/Runs/<new hub>` (refuses an existing hub or a dirty tree).
Whole-run cap 1800 s including reporting, enforced with `timeout` plus a per-run process-token sweep (in-container
processes included); `IGUARD_CAP_SECONDS` may only tighten it. Dependent stages are skipped after a failed
prerequisite. Exit: 0 technically complete (readiness in `READINESS.json`), 1 refused, 2 stage failure/incomplete,
124 cap reached, 130 interrupted; `TERMINAL.json` records the terminal state.

Provenance: before the original commit `a516c61` and its formal replay, the decision stage alone was smoke-run into a
scratch directory (disclosed in each hub's `INPUT-MANIFEST.json`, now quoted in `REPORT.md`). `c3af115` changed report
text only. Those commits and the original hub are historical and are not rewritten; later commits harden the runner,
evaluator provenance checks and report without changing `guard/decide.py`.
