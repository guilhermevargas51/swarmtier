# Changelog

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versions follow [SemVer](https://semver.org/).

## [0.2.0] - 2026-10-16

### Added
- `dashboard/`: local live board of the dispatch ledger (`python -m dashboard`, stdlib only, 127.0.0.1, light/dark theme, fullscreen).
- `examples/ledger-sample.jsonl`: sample ledger for the demo and the tests.
- `tests/test_dashboard.py`: reducer and server tests.

### Changed
- `core.config`: new `dashboard_port` key (default 8790).
- `.gitignore`: keeps `examples/ledger-sample.jsonl` while ignoring other `*.jsonl`.

## [0.1.1] - 2026-10-16

### Fixed
- `core.config`: the Python 3.10 TOML fallback read list values such as `forbid_max_for = ["sonnet"]` as a string; it now parses them as lists.

### Docs
- README (EN and pt-BR) cites Barry Zhang's talk "How We Build Effective Agents", which leaves budget-awareness as an open question.
- Star history chart hidden until the repository has stars.

## [0.1.0] - 2026-10-15

First public release.

### Added
- Claude Code plugin manifest and marketplace entry (`.claude-plugin/`).
- Hooks: `require-effort` (blocks dispatch without `effort`, refuses `max` on Sonnet), `delegation-ledger`,
  `cold-cache`, `cold-cache-watch`, `lesson-inject`, `lesson-capture`, `user-correction`.
- Core: `core.quota` (manual reading from `/usage`, with age), `core.swarm_split` (batches under a token ceiling),
  `core.learning` (lesson store and search), `core.ledger`, `core.config`.
- Agents: `triage` (Haiku), `executor` (Sonnet), `vision-reader` (Sonnet).
- Skills: `dispatch-by-cost`, `swarm-split`, `improve-skills`.
- Templates: orchestrator `CLAUDE.md` and `config.example.toml`.
- Docs: architecture, dispatch line, cost map, scenarios, FAQ.
- `scripts/pii_scan.py` personal-data scan, run in CI with the test suite.
- README in English and Brazilian Portuguese, CONTRIBUTING, SECURITY.
