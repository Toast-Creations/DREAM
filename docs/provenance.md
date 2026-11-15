# Provenance of the public code

The code in `src/`, `scripts/`, `tests/`, `configs/`, `data/` and `artifacts/` is the private research version **1.29.0** (14 November 2026). It is copied unchanged except for the files listed below.

All of the changes are of four kinds:

1. **Local paths.** Hard-coded absolute paths on the research desktop were replaced with values from `src/dream_core/localpaths.py`, which reads the environment variables `DREAM_HOME`, `DREAM_RUNS`, `DREAM_CODE`, `DREAM_MODELS` and `DREAM_PY`. Each affected file gains one import line (marked `# public release`).
2. **Identity-guard location.** `scripts/es_analyze.py` and `scripts/ev_analyze.py` now load the IGUARD-v0.1 decision function from `tools/identity-guard-replay/guard/decide.py` in this repository. The file is byte-identical, so the pinned sha256 check is unchanged.
3. **Skips for data that isn't in the repository.** Tests that read saved run folders now skip with a stated reason when those folders are absent. Tests that check byte-identity against archived per-version source trees now run only when `DREAM_VERIFY_ARCHIVE=1` is set. Because of change 1, some of those files intentionally differ from the archive now, by the import line and the path lines.
4. **CPU-only environments.** One test that needs `torch` now skips when `torch` is missing.
5. **Python 3.10 timestamps** (after 2.0.1). `scripts/cc_analyze.py` and `scripts/su_certify.py` parse timestamps with `dream_core.isotime.fromisoformat`. On Python 3.11+ this is exactly `datetime.fromisoformat`, so results there are unchanged. Added `src/dream_core/isotime.py` and `tests/test_isotime.py`.

No algorithm, prompt, scoring rule, configuration or data file was changed. Change 5 alters behaviour only on Python 3.10, where it makes timestamps readable that would otherwise raise an error.

Changed or added files compared with 1.29.0:

```
changed  scripts/cab_analyze.py
changed  scripts/cc_analyze.py
changed  scripts/cc_prepare.py
changed  scripts/cc_run.py
changed  scripts/clar_prepare.py
changed  scripts/contract_validate.py
changed  scripts/depq_validate.py
changed  scripts/deprec_validate.py
changed  scripts/ectx_run.py
changed  scripts/engine_validate.py
changed  scripts/es_analyze.py
changed  scripts/es_prepare.py
changed  scripts/es_run.py
changed  scripts/ev_analyze.py
changed  scripts/ev_prepare.py
changed  scripts/ev_run.py
changed  scripts/fac_analyze.py
changed  scripts/fresh_validate.py
changed  scripts/ftx_validate.py
changed  scripts/goaltr_validate.py
changed  scripts/kconf_freeze.py
changed  scripts/kconf_prepare.py
changed  scripts/kconf_watchdog_probe.sh
changed  scripts/nul_validate.py
changed  scripts/su_certify.py
changed  scripts/su_phase0.py
changed  scripts/su_run.py
changed  scripts/timing_validate.py
added    src/dream_core/isotime.py
added    src/dream_core/localpaths.py
changed  tests/test_broad_concepts.py
changed  tests/test_deprec.py
changed  tests/test_diag.py
changed  tests/test_ectx.py
changed  tests/test_es.py
changed  tests/test_ev.py
changed  tests/test_goaltr.py
changed  tests/test_history.py
added    tests/test_isotime.py
changed  tests/test_probe.py
changed  tests/test_repair.py
changed  tests/test_su.py
changed  tests/test_survival.py
changed  tests/test_textpol.py
```

Studies 1.0–1.28 ran on earlier versions. Their reports in `results/` record the exact source version and hashes that were used. Those per-version source trees are kept in the project's private archive.
