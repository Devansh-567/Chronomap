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

### Fixed
- **`ChronoMap.merge(strategy='timestamp')` was broken.** The out-of-order
  insert branch referenced an undefined variable (`value` instead of
  `val`) and inserted into the wrong list (`versions`, the *source* data
  from the other map, instead of `target_versions`). Any merge where a
  key's timestamps interleaved out of order would raise `NameError` and
  could corrupt the source map's history in the process. Added a
  regression test (`test_merge_timestamp_strategy_does_not_crash_on_out_of_order_writes`).

## [2.1.0] - 2025-10-21
- Last release under the single-file layout. See git history for details
  predating this changelog.
