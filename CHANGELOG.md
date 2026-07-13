# Changelog

All notable changes to this project are documented here.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Changed
- Split the single-file `chronomap.py` module into a proper package
  (`src/chronomap/`): `core.py`, `asynchronous.py`, `_cache.py`,
  `_lock.py`, `_memory.py`, `_ttl_cleanup.py`, `_snapshot.py`,
  `exceptions.py`. Public API (`from chronomap import ChronoMap`)
  is unchanged.
- Replaced deprecated `datetime.utcnow()` calls with
  `datetime.now(timezone.utc)`.

### Added
- `chronomap/cli.py` — this was referenced in the old project structure
  and README but didn't exist in the code I had to work with. Written
  from scratch to satisfy the existing `tests/test_cli.py`: `parse_value`,
  `format_timestamp`, `colorize`, `load_and_display`, plus a small
  `show` subcommand for inspecting saved state files.
- Wired in the real `tests/test_chronomap.py` (170+ tests) and
  `tests/test_cli.py`. All pass against the restructured package
  unmodified — the public import surface didn't change.
- `tests/test_basic.py` — a small additional smoke-test file, mainly
  useful as the home for the `merge()` regression test below.

### Fixed
- **`ChronoMap.merge(strategy='timestamp')` was broken.** The out-of-order
  insert branch referenced an undefined variable (`value` instead of
  `val`) and inserted into the wrong list (`versions`, the *source* data
  from the other map, instead of `target_versions`). Any merge where a
  key's timestamps interleaved out of order would raise `NameError` and
  could corrupt the source map's history in the process. Added a
  regression test (`test_merge_timestamp_strategy_does_not_crash_on_out_of_order_writes`).

### Current test status
177 tests passing, 91% coverage (`pytest tests/ --cov=chronomap`).

## [2.1.0] - 2025-10-21
- Last release under the single-file layout. See git history for details
  predating this changelog.
