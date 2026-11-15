# Changelog

## 2.0.0 (15 November 2026): first public release

- One public package that folds together all private research versions 1.0–1.29 (27 October to 14 November 2026). The code in `src/` and `scripts/` is the 1.29.0 source. The only changes are that local absolute paths were moved into `src/dream_core/localpaths.py` (environment variables), and tests that need archived versions or saved run folders now skip when those are absent.
- Added: public README, the research-line pages, the study index, the getting-started and safety pages, the DREAM3 proposals, manuscript v0.7, per-study reports and errata in `results/`, and CPU CI.
- Copyright holder: Toast Creations LLC. License unchanged (Apache-2.0).

See [docs/provenance.md](docs/provenance.md) for every file that differs from 1.29.0.

The detailed history of each private version is in the study reports listed in [docs/studies.md](docs/studies.md). The per-version changelog that was used during development is kept in [docs/protocols/CHANGELOG-1.x.md](docs/protocols/CHANGELOG-1.x.md).
