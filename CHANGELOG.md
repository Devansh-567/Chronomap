# Changelog

All notable changes to ChronoMap are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
ChronoMap follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

<!-- Add entries here while developing. Move to a release section on tag. -->

---

## [2.2.0] — 2025-10-21

### Added
- `LRUCache` class for 10× faster hot-key reads (`cache_size` parameter)
- `max_history` parameter — auto-prune old versions to prevent memory leaks
- Background `TTLCleanupThread` with configurable interval (`enable_ttl_cleanup`, `ttl_cleanup_interval`)
- `MemoryMonitor` with hard limits and 80% usage warnings (`max_memory_mb`)
- Multi-algorithm compression: `zlib`, `gzip`, `bz2`, `lzma` in `save_pickle` / `to_dict`
- `get_or_set(key, default_factory, ttl)` — cache-aside helper
- `get_or_default(key, default, ttl)` — simpler variant accepting a plain value
- `keys_with_history_count()` — returns `{key: version_count}` for all live keys
- `subscribe(key, callback)` / `unsubscribe(key, callback)` — per-key change callbacks
- `AsyncChronoMap.keys_with_history_count()`, `get_or_set()`, `get_or_default()`
- `prune_all_history(keep_last, older_than)` — bulk pruning across all keys
- `get_stats()` now returns `cache_hit_rate`, `cache_size`, `auto_prunes`, `ttl_cleanup_count`

### Changed
- `put_many()` acquires the write lock once for the entire batch (≈3× faster)
- `snapshot()` disables cache and TTL cleanup on the snapshot object

### Fixed
- `rollback()` now clears the LRU cache to prevent stale reads after restore
- `merge()` with `timestamp` strategy no longer mutates the source map's versions list

---

## [2.1.0] — 2025-04-15

### Added
- `RWLock` — read-write lock for improved concurrent read throughput (`use_rwlock=True`)
- `AsyncChronoMap` — full `asyncio` support with async callbacks
- `query(predicate, timestamp)` — filter keys by a lambda at any point in time
- `aggregate(func, keys, timestamp)` — reduce values across keys
- `count(predicate, timestamp)` — count matching keys
- `on_change(callback)` / `remove_change_callback(callback)` — global change hooks
- `snapshot_context()` — context manager with automatic rollback on exception
- `merge(other, strategy)` — combine two ChronoMaps (`timestamp` or `overwrite`)
- `diff(other)` / `diff_detailed(other)` — compare maps
- `get_range(key, start_ts, end_ts)` — time-range slice of a key's history
- `get_latest_keys(n)` — most recently updated keys
- `get_keys_by_value(value, timestamp)` — reverse lookup
- `to_dataframe()` — export to Pandas DataFrame (requires `pandas` extra)
- `prune_history(key, keep_last, older_than)` — trim a single key's history
- ISO 8601 string timestamps: `cm.put('k', 'v', timestamp="2025-01-01T12:00:00")`
- `reset_stats()` — reset operation counters

---

## [2.0.0] — 2024-10-21

### Added
- Initial public release
- Core `ChronoMap` with time-versioned `put` / `get` / `delete`
- TTL support with `ttl` parameter on `put`
- `snapshot()` / `rollback(snapshot)` — point-in-time restore
- `put_many()` / `delete_many()` — batch operations
- JSON and Pickle persistence (`save_json`, `load_json`, `save_pickle`, `load_pickle`)
- `clean_expired_keys()` — manual TTL cleanup
- `get_stats()` — basic operation counters
- `to_dict()` / `from_dict()` with optional `zlib` compression
- Full Python container protocol: `__getitem__`, `__setitem__`, `__delitem__`, `__contains__`, `__len__`, `__iter__`, `__eq__`, `__bool__`, `__repr__`
- CLI (`python -m chronomap`) with interactive shell, `--demo`, `--benchmark`, `--file`
- MIT licence

[Unreleased]: https://github.com/Devansh-567/chronomap/compare/v2.2.0...HEAD
[2.2.0]: https://github.com/Devansh-567/chronomap/compare/v2.1.0...v2.2.0
[2.1.0]: https://github.com/Devansh-567/chronomap/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/Devansh-567/chronomap/releases/tag/v2.0.0
