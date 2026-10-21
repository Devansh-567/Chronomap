# API reference

This page documents the public API of the current `chronomap` package:
`ChronoMap`, `AsyncChronoMap`, the query builders, archive persistence,
`SnapshotContext`, the exception types, and the CLI module.

```python
from chronomap import (
    ArchiveInfo,
    AsyncChronoMap,
    ChronoMap,
    ChronoMapError,
    ChronoMapKeyError,
    ChronoMapMemoryError,
    ChronoMapTypeError,
    ChronoMapValueError,
    CodecError,
    CorruptArchiveError,
    LRUCache,
    PersistenceError,
    Query,
    QueryError,
    RWLock,
    SnapshotContext,
    UnsupportedFormatError,
    VersionQuery,
    __version__,
    dump,
    dumps,
    inspect,
    load,
    loads,
    query,
    versions,
)
```

All examples assume the package is installed with `pip install -e ".[dev]"`.

## Timestamps

Every API that accepts a timestamp accepts one of:

- a Unix timestamp as `int` or `float`
- an aware or naive `datetime` object
- an ISO-8601 string, for example `"2024-07-11T10:00:00+00:00"`

Timestamps are stored as floating-point epoch seconds. Reads at a timestamp
return the newest version whose timestamp is less than or equal to the query
timestamp. A read before a key's first version returns the supplied default,
or raises when `strict=True`.

## ChronoMap

### Constructor

```python
ChronoMap(
    debug=False,
    use_rwlock=True,
    max_history=None,
    cache_size=1000,
    enable_ttl_cleanup=True,
    ttl_cleanup_interval=60.0,
    max_memory_mb=None,
    wal_path=None,
    wal_sync=True,
    wal_auto_checkpoint_bytes=64 * 1024 * 1024,
)
```

| Parameter | Meaning |
| --- | --- |
| `debug` | Enables debug logging for operations. |
| `use_rwlock` | Uses an internal reader-writer lock. Set `False` to use a re-entrant lock instead. |
| `max_history` | Maximum versions kept per key. `None` keeps all versions. |
| `cache_size` | Number of cached current-value reads. `0` disables the cache. |
| `enable_ttl_cleanup` | Starts a background thread that sweeps expired keys. |
| `ttl_cleanup_interval` | Seconds between background sweeps. |
| `max_memory_mb` | Approximate memory ceiling used by the memory monitor. |
| `wal_path` | Enables the write-ahead journal at this path and replays it at construction. |
| `wal_sync` | Flushes and fsyncs each journal record before the mutation is applied. |
| `wal_auto_checkpoint_bytes` | Journal size that triggers an automatic checkpoint. `None` disables it. |

The default configuration is suitable for a single-process service:

```python
from chronomap import ChronoMap

cm = ChronoMap(max_history=1000, cache_size=256)
```

### Mapping protocol

`ChronoMap` supports the familiar dictionary operations:

```python
cm["key"] = "value"       # put()
cm["key"]                 # get(..., strict=True)
"key" in cm               # True if a non-expired version exists
del cm["key"]             # delete(); raises ChronoMapKeyError if absent
len(cm)                   # number of non-expired keys
list(cm)                  # list of non-expired keys
```

`__getitem__` raises `ChronoMapKeyError` for missing or expired keys instead of
returning a default.

### Reads

#### `get(key, timestamp=None, default=None, *, strict=False)`

Returns the value visible at `timestamp`, or the newest value when
`timestamp` is omitted.

```python
cm.put("cpu", 0.42, timestamp=100)
cm.put("cpu", 0.91, timestamp=200)

assert cm.get("cpu") == 0.91
assert cm.get("cpu", timestamp=150) == 0.42
assert cm.get("missing") is None
assert cm.get("missing", default="fallback") == "fallback"
```

With `strict=True`, a missing key or a timestamp before the key's first
version raises `ChronoMapKeyError`.

#### `get_range(key, start_ts=None, end_ts=None)`

Returns every `(timestamp, value)` pair for one key in the inclusive range.

```python
cm.put("cpu", 0.42, timestamp=100)
cm.put("cpu", 0.91, timestamp=200)
cm.put("cpu", 0.17, timestamp=300)

assert cm.get_range("cpu", 100, 200) == [
    (100.0, 0.42),
    (200.0, 0.91),
]
```

Omitted bounds mean negative infinity and the current time, respectively.

#### `history(key)` and `iter_history(key)`

`history()` returns a list of all stored versions. `iter_history()` yields the
same pairs without building the list. Both return nothing for expired keys.

```python
assert cm.history("cpu") == [
    (100.0, 0.42),
    (200.0, 0.91),
    (300.0, 0.17),
]
```

#### `latest()`

Returns a `{key: latest_value}` dictionary for every non-expired key.

#### `get_latest_keys(n)`

Returns the `n` most recently written `(key, timestamp, value)` triples across
all keys, sorted newest first.

```python
assert cm.get_latest_keys(1) == [("cpu", 300.0, 0.17)]
```

#### `keys()`, `values()`, `items()`

These are iterators over non-expired keys and their latest values. They
snapshot the key list before yielding, so iteration is safe while other
threads write.

```python
assert list(cm.keys()) == ["cpu"]
assert list(cm.values()) == [0.17]
assert list(cm.items()) == [("cpu", 0.17)]
```

#### `keys_with_history_count()`

Returns `{key: number_of_versions}` for every non-expired key.

#### `get_keys_by_value(value, timestamp=None)`

Returns every key whose value at `timestamp` equals `value`.

### Writes

#### `put(key, value, timestamp=None, ttl=None)`

Stores a new version. If `timestamp` is omitted, the current time is used.
Out-of-order timestamps are inserted into the key's sorted version list.

```python
cm.put("session", {"user": 7}, ttl=3600)
cm.put("session", {"user": 8}, timestamp=500)
```

`ttl` is measured from the write time, not from the supplied timestamp. A TTL
must be positive; `ChronoMapValueError` is raised otherwise.

#### `put_many(items, timestamp=None, ttl=None)`

Writes multiple keys under one lock acquisition.

```python
cm.put_many({"cpu": 0.4, "disk": 0.2}, timestamp=100)
```

#### `get_or_set(key, default_factory, ttl=None)`

Returns the current value if the key exists; otherwise calls
`default_factory()`, stores the result, and returns it.

```python
value = cm.get_or_set("feature:beta", lambda: {"enabled": False}, ttl=600)
```

The factory must be callable. It is not called when the key already has a live
value.

#### `get_or_default(key, default, ttl=None)`

A convenience form of `get_or_set()` for a plain value. If `default` is
callable it is used as a factory.

```python
assert cm.get_or_default("region", "us-east") == "us-east"
```

#### `delete(key)` and `delete_many(keys)`

`delete()` removes all versions for a key and returns `True` if it existed.
`delete_many()` returns the number of keys that were present.

```python
assert cm.delete("cpu") is True
assert cm.delete("cpu") is False
```

#### `clear()`

Removes all keys, TTL entries, history, and cached values.

### Query and aggregation

#### `query(predicate, timestamp=None)`

Returns a `{key: value}` dictionary for keys whose value at `timestamp`
satisfies `predicate(key, value)`.

```python
cm.put_many({"cpu": 0.4, "disk": 0.9})
busy = cm.query(lambda key, value: value > 0.5)
assert busy == {"disk": 0.9}
```

#### `aggregate(func, keys=None, timestamp=None)`

Calls `func(values)` with the list of values for the selected keys.

```python
total = cm.aggregate(sum)
total_for_cpu = cm.aggregate(sum, keys=["cpu"])
```

#### `count(predicate=None, timestamp=None)`

Counts all non-expired keys, or only keys matching a predicate.

```python
assert cm.count() == 2
assert cm.count(lambda key, value: value > 0.5) == 1
```

`query()` and `aggregate()` are O(n) scans over live keys. `count()` without a
predicate uses the map's current size.

### Snapshots and rollback

#### `snapshot()`

Returns a deep-copied `ChronoMap` with the same store and TTLs plus a fresh
snapshot timestamp. The snapshot is independent of later writes.

```python
before = cm.snapshot()
cm.put("cpu", 0.1)
cm.rollback(before)
```

#### `rollback(snapshot)`

Restores the store and TTLs from a snapshot created by `snapshot()`.

#### `snapshot_context()`

Returns a `SnapshotContext` for automatic rollback when a block raises.

```python
with cm.snapshot_context():
    cm.put("cpu", 0.9)
    raise RuntimeError("something failed")
# the write above was rolled back
```

The context manager commits on normal exit and rolls back on exception.

### Diff and merge

#### `diff(other)` and `diff_detailed(other)`

`diff()` returns the set of keys whose current values differ. Expired-state
differences also count. `diff_detailed()` returns
`(key, other_value, self_value)` triples instead.

```python
left = ChronoMap(cache_size=0, enable_ttl_cleanup=False)
right = ChronoMap(cache_size=0, enable_ttl_cleanup=False)

left.put("a", 1)
right.put("a", 2)
right.put("b", 3)

assert left.diff(right) == {"a", "b"}
assert sorted(left.diff_detailed(right), key=lambda item: item[0]) == [
    ("a", 2, 1),
    ("b", 3, None),
]
```

#### `merge(other, strategy="timestamp")`

Merges another map into this one.

- `"timestamp"` interleaves both histories by timestamp.
- `"overwrite"` replaces this map's history for keys present in `other`.

```python
left.merge(right, strategy="timestamp")
```

### History pruning

#### `prune_history(key, keep_last=None, older_than=None)`

Removes old versions for one key and returns the number removed. If both
`keep_last` and `older_than` are omitted, nothing is removed.

```python
cm.prune_history("cpu", keep_last=10)
cm.prune_history("cpu", older_than="2024-01-01T00:00:00")
```

`keep_last` keeps the newest N versions. `older_than` removes versions older
than the timestamp. Both can be combined.

#### `prune_all_history(keep_last=None, older_than=None)`

Applies the same rules to every key and returns the total number of removed
versions.

### Statistics

#### `get_stats()`

Returns operation counters plus current size information:

```python
stats = cm.get_stats()
# reads, writes, deletes, snapshots, auto_prunes,
# total_keys, total_versions, expired_keys
```

When the cache is enabled, `cache_hits`, `cache_misses`, `cache_size`, and
`cache_hit_rate` are included. When the cleanup thread is enabled,
`ttl_cleanup_count` is included as well. WAL-backed maps also expose
`journal_path`, `journal_bytes`, and `journal_sequence`.

#### `reset_stats()`

Resets counters and clears the read cache.

### Change notifications

#### `on_change(callback)`

Registers a global callback called after writes and `get_or_set()` creation.
The callback receives `(key, old_value, new_value, timestamp)`.

```python
def log_change(key, old, new, timestamp):
    print(key, old, "->", new)

cm.on_change(log_change)
```

Callback exceptions are logged and do not roll back the write.

#### `remove_change_callback(callback)`

Unregisters a global callback. Returns `True` if it was registered.

#### `subscribe(key, callback)`

Registers a callback for one key. The callback receives
`(old_value, new_value, timestamp)`.

#### `unsubscribe(key, callback)`

Unregisters a key callback. Returns `True` if it was registered.

### Durability

#### `wal_path` journals

Passing `wal_path` enables an append-only write-ahead log for the synchronous
map. Every mutating operation is encoded as a CRC-checked record before the
in-memory state changes. With the default `wal_sync=True`, each record is
flushed and fsynced first. Reopening a map at the same path restores the store,
TTL deadlines, and snapshot timestamp.

```python
cm = ChronoMap(wal_path="chronomap.wal")
cm.put("region", "us-east")
cm.close()

recovered = ChronoMap(wal_path="chronomap.wal")
assert recovered.get("region") == "us-east"
```

A torn final record is discarded during recovery. A complete record with a
bad checksum raises `JournalCorruptionError` instead of being skipped. Journals
use pickle and are trusted local state, not a format for untrusted input.

#### `checkpoint()`

Writes the current store and TTL table to `<wal_path>.checkpoint` atomically,
validates it with a length and CRC32 frame on read, then atomically resets the
journal while retaining the sequence counter. Automatic checkpoints run when the
journal reaches `wal_auto_checkpoint_bytes`; set it to `None` to compact only
when you call `checkpoint()` yourself. Automatic checkpoint failures are
logged and leave the journal intact rather than failing the user write.

```python
cm.checkpoint()
```

Calling `checkpoint()` without `wal_path`, or after the map is closed, raises
`JournalError` before writing a checkpoint.

#### `close()`

Stops the TTL cleanup thread and closes the journal. `ChronoMap` is also a
context manager:

```python
with ChronoMap(wal_path="chronomap.wal") as cm:
    cm.put("region", "us-east")
```

`close()` is idempotent. The WAL is designed for one live map per file; it does
not take a cross-process lock. `AsyncChronoMap` does not support WAL mode yet.
`from_dict(..., wal_path=...)` logs the imported state as a replacement record
so the imported map survives a later recovery.

### Persistence

#### `to_dict(compress=False)` and `from_dict(data, **kwargs)`

`to_dict()` returns a plain dictionary with `store`, `ttl`, `snapshot_time`,
`version`, and `max_history`. Pass `compress=True` (zlib) or
`compress="gzip"`, `"bz2"`, or `"lzma"` to get compressed bytes.

```python
data = cm.to_dict()
restored = ChronoMap.from_dict(data, cache_size=0, enable_ttl_cleanup=False)
```

#### `save_json(path)` / `load_json(path)`

Writes and reads the `to_dict()` shape as JSON. JSON has no non-string keys,
so every key is coerced with `str()` on save. Use pickle when key types matter.

```python
cm.save_json("state.json")
restored = ChronoMap.load_json("state.json")
```

#### `save_pickle(path, compress=False)` / `load_pickle(path)`

Uses `pickle` and preserves Python key/value types. Compressed output is
supported with the same compression names as `to_dict()`.

```python
cm.save_pickle("state.pkl", compress="gzip")
restored = ChronoMap.load_pickle("state.pkl")
```

Loading a pickle executes Python deserialization code. Only load files you
trust.

### Pandas export

#### `to_dataframe()`

Returns a pandas `DataFrame` with one row per version. Requires the optional
dependency:

```bash
pip install chronomap[pandas]
```

```python
frame = cm.to_dataframe()
```

## Query builders

The query layer provides lazy, chainable filters over current values and over
individual historical versions. Import the builders and their types from the
package root:

```python
from chronomap import Query, QueryError, VersionQuery, query, versions
```

`Query` is lazy: chained filters do not run until a terminal method such as
`keys()`, `count()`, or `sum()` is called, and the map is read once at that
point. `VersionQuery` snapshots its matching rows when the query is created.

### `query(source, timestamp=None)`

Builds a `Query` over a `ChronoMap` or any plain mapping. For a map,
`timestamp` selects the value visible at that time; omitting it uses the
current time. A plain mapping does not accept a timestamp.

```python
cm.put("cpu", 0.4, timestamp=100)
cm.put("cpu", 0.9, timestamp=200)
cm.put("disk", 0.2, timestamp=200)

busy = query(cm).where_value(lambda value: value > 0.5)
assert busy.to_dict() == {"cpu": 0.9}
assert query(cm, timestamp=150).keys() == ["cpu"]
assert query(cm, timestamp=200).keys() == ["cpu", "disk"]
```

Use `at(timestamp)` to move an existing chain to another point in time while
keeping its filters.

### `Query` filters and projections

| Method | Behavior |
| --- | --- |
| `where(func)` / `filter(func)` | Keep `(key, value)` pairs where `func(key, value)` is true. |
| `where_key(func)` | Keep pairs where `func(key)` is true. |
| `where_value(func)` | Keep pairs where `func(value)` is true. |
| `where_field(field, func)` | Keep mapping values with `field` and where `func(value[field])` is true. Other values are skipped. |
| `keys_in(keys)` | Keep keys in the given iterable. |
| `keys_like(pattern)` | Match stringified keys with an `fnmatch` pattern. |
| `keys_regex(pattern)` | Match stringified keys with `re.search`. |
| `values_in(values)` | Keep values equal to one of the supplied values. |
| `values_between(low, high, *, inclusive=True)` | Keep values in the range. |
| `distinct()` | Keep the first row for each distinct value. |
| `select_field(field)` | Keep mappings that contain `field` and replace each value with `value[field]`. |
| `transform(func)` | Replace each value with `func(key, value)`. |
| `sort_by(func)` | Sort rows by `func(key, value)`. |
| `sort_by_key(key=None, *, reverse=False)` | Sort by key, or by `key(key)`. |
| `sort_by_value(key=None, *, reverse=False)` | Sort by value, or by `key(value)`. |
| `limit(count)` / `offset(count)` | Slice the current row list. |

### `Query` terminal methods

`keys()`, `values()`, `items()`, and `to_dict()` return the selected rows.
`count()` returns the number of rows. `first()` and `first_item()` raise
`QueryError` when the result is empty unless a default is supplied.

Aggregations operate on the selected values:

| Method | Result |
| --- | --- |
| `sum()` / `mean()` / `median()` / `min()` / `max()` | Numeric or comparable aggregate; empty results raise `QueryError`. |
| `any(predicate=None)` / `all(predicate)` | Whether any or all selected values match. |
| `fold(func, initial)` | Left-fold over the selected values. |
| `group_by(func)` | Map from `func(key, value)` to a list of values. |
| `group_items(func)` | Map from `func(key, value)` to a list of `(key, value)` pairs. |

### `versions(source, start=None, end=None, keys=None)`

Builds a `VersionQuery` over individual versions of a `ChronoMap`. Each row is
a `(key, timestamp, value)` triple, and rows are sorted by timestamp. Bounds are
inclusive; omitted bounds are unbounded. `keys` restricts the source keys.

```python
history = versions(cm, start=100, end=200)
assert history.rows() == [
    ("cpu", 100.0, 0.4),
    ("cpu", 200.0, 0.9),
    ("disk", 200.0, 0.2),
]
```

`VersionQuery` supports these filters and transforms:

- `where(func)` with `func(key, timestamp, value)`, plus `where_key`,
  `where_value`, and `where_timestamp`
- `between(start, end)` and `keys_in(keys)` / `values_in(values)`
- `sort_by_timestamp()`, `sort_by_key()`, and `sort_by_value()`
- `limit(count)` and `offset(count)`
- `rows()`, `keys()`, `values()`, `count()`, `first()`, `fold()`
- `latest_per_key()`, `earliest_per_key()`, and `group_by_key()`
- `to_records()` for dictionaries with `key`, `timestamp`, `datetime`, and `value`
- `to_chronomap()` to materialize the selected rows as a new map
- `sum()`, `mean()`, `min()`, and `max()`

## Archive persistence

The `chronomap.persistence` module writes self-describing archives that preserve
Python key and value types, including TTL deadlines, history length, and the
snapshot time. Two formats are available:

- `"json"` is inspectable and uses a tagged codec for scalars, bytes, dates,
  lists, tuples, sets, and mappings.
- `"pickle"` supports arbitrary Python objects. Only load pickle archives from
  sources you trust, because unpickling can execute code.

### `dump(cm, path, *, format=None, compression=None, indent=2, include_expired=True, atomic=True)`

Writes an archive to disk. The format is inferred from the suffix when omitted:
`.pkl` and `.pickle` select pickle; everything else defaults to JSON. Compression
may be `None`, `"zlib"`, `"gzip"`, `"bz2"`, or `"lzma"`. `atomic=True` writes a
temporary file and replaces the target only after a successful write.

```python
from chronomap import dump

dump(cm, "state.json")
dump(cm, "state.pkl", compression="gzip")
```

Set `include_expired=False` to omit keys whose TTL has already elapsed.

### `dumps(cm, *, format="json", compression=None, indent=2, include_expired=True)`

Returns the archive as `bytes` instead of writing a file.

### `load(path, *, format=None, drop_expired=False, **map_options)` and `loads(data, *, format=None, drop_expired=False, **map_options)`

Read an archive from a path or byte string. The format is detected from the
archive header; pass `format` only to reject an unexpected format. Remaining
keyword arguments are forwarded to the `ChronoMap` constructor, for example
`cache_size=0` or `enable_ttl_cleanup=False`.

```python
from chronomap import load, loads

restored = load("state.json", cache_size=0, enable_ttl_cleanup=False)
same = loads(open("state.json", "rb").read())
```

`drop_expired=True` discards expired keys during loading instead of restoring
their TTLs.

### `inspect(path)`

Reads only the header and row counts, returning an `ArchiveInfo` with `format`,
`format_version`, `compression`, `created_at`, `key_count`, `version_count`,
`max_history`, and `snapshot_time`.

```python
from chronomap import inspect

info = inspect("state.json")
print(info.format, info.key_count, info.version_count)
```

`dump`, `load`, and `inspect` raise `PersistenceError` (or a subclass) for I/O
and archive failures. `UnsupportedFormatError` covers unknown formats,
versions, and compression names; `CorruptArchiveError` covers malformed
payloads; `CodecError` covers values the JSON codec cannot represent.

## AsyncChronoMap

`AsyncChronoMap` is a separate asyncio-native implementation. It uses an
`asyncio.Lock` and must be used from one event loop.

```python
import asyncio
from chronomap import AsyncChronoMap


async def main():
    cm = AsyncChronoMap(max_history=100)
    await cm.put("cpu", 0.4)
    await cm.put("cpu", 0.9)
    assert await cm.get("cpu") == 0.9
    assert await cm.keys() == ["cpu"]


asyncio.run(main())
```

Available methods:

| Method | Behavior |
| --- | --- |
| `await put(key, value, timestamp=None, ttl=None)` | Store a version. |
| `await put_many(items, timestamp=None, ttl=None)` | Store several versions. |
| `await get(key, timestamp=None, default=None, *, strict=False)` | Read a version. |
| `await get_or_set(key, default_factory, ttl=None)` | Read or create a value. |
| `await get_or_default(key, default, ttl=None)` | Plain-value form of `get_or_set()`. |
| `await delete(key)` | Remove a key. |
| `await snapshot()` | Deep-copy the map. |
| `await keys()` | List non-expired keys. |
| `await latest()` | Dict of latest values. |
| `await keys_with_history_count()` | Dict of version counts. |
| `on_change(callback)` | Register a sync or async callback. |
| `subscribe(key, callback)` / `unsubscribe(key, callback)` | Per-key callbacks. |
| `get_stats()` | Return a copy of the counters. |

The async map does not implement time-range queries, diff/merge, or file
persistence. Use the synchronous map for those operations.

## SnapshotContext

`SnapshotContext` is returned by `ChronoMap.snapshot_context()`. It can also
be constructed directly with a map:

```python
from chronomap import ChronoMap, SnapshotContext

cm = ChronoMap()
with SnapshotContext(cm):
    cm.put("key", "value")
```

On normal exit it keeps the changes. On exception it calls `rollback()` with
the snapshot taken at entry.

## Supporting exports

The package also exports small building blocks, the journal primitive, and the
version string.

### `RWLock`

```python
from chronomap import RWLock

lock = RWLock()
lock.acquire_read()
lock.release_read()
lock.acquire_write()
lock.release_write()
```

Allows concurrent readers or one exclusive writer. `ChronoMap` uses it when
`use_rwlock=True`.

### `LRUCache`

```python
from chronomap import LRUCache

cache = LRUCache(capacity=256)
cache.get(("key", None))
cache.put(("key", None), "value")
cache.invalidate("key")
cache.clear()
cache.get_stats()
```

A thread-safe LRU cache keyed by `(store_key, timestamp)`. The public methods
are `get`, `put`, `invalidate`, `clear`, and `get_stats`.

### `Journal`

```python
from chronomap import Journal

with Journal("events.wal", sync=True) as journal:
    sequence = journal.append("event", {"key": "value"})
    assert journal.sequence == sequence
```

`Journal` is the append-only record layer used by `ChronoMap`. It validates
sequence ordering and CRC checksums, truncates a torn final record on reopen,
and exposes `sequence`, `records`, `size`, and `closed` (plus `reset()`,
`advance_to()`, and `clear_records()` for checkpoint/recovery coordination).
`reset()` atomically replaces the journal with a fresh header while retaining
the sequence counter. Most applications should pass `wal_path` to `ChronoMap`
instead of using `Journal` directly. Checkpoint helpers (`write_checkpoint()`
/ `read_checkpoint()`) are internal modules.

### `__version__`

The installed package version as a string.

## Exceptions

All package exceptions derive from `ChronoMapError`, which derives from
`Exception`.

| Exception | Raised for |
| --- | --- |
| `ChronoMapError` | Base class; catch this to handle every package error. |
| `ChronoMapKeyError` | Missing keys with `strict=True`, `__getitem__`, or `__delitem__`. |
| `ChronoMapTypeError` | Unhashable keys, invalid timestamp types, bad callback arguments. |
| `ChronoMapValueError` | Invalid TTLs, non-finite timestamps, bad merge strategies, unknown compression. |
| `ChronoMapMemoryError` | The memory monitor's hard ceiling was exceeded. |
| `QueryError` | A query was composed incorrectly or an aggregate had no rows. |
| `PersistenceError` | Base class for archive read/write failures. |
| `UnsupportedFormatError` | Unknown archive format, version, or compression. |
| `CorruptArchiveError` | Structurally invalid or malformed archive contents. |
| `CodecError` | A value cannot be represented by the selected archive codec. |
| `JournalError` | Base class for WAL open, append, checkpoint, or close failures. |
| `JournalCorruptionError` | A WAL or checkpoint is malformed, out of order, or fails its checksum. |

```python
from chronomap import ChronoMapKeyError

try:
    cm.get("missing", strict=True)
except ChronoMapKeyError:
    pass
```

## CLI

The current CLI has one subcommand, `show`, which loads a saved file and prints
the current key-value state:

```bash
python -m chronomap.cli show state.json
python -m chronomap.cli show state.pkl
```

The CLI accepts both JSON and pickle files written by `save_json()` and
`save_pickle()`. Missing and unreadable files are reported in the terminal.

## Complexity and limits

- `get` and `put` use binary search over a key's version list.
- `query`, `aggregate`, and `count` scan every live key.
- `diff` and `merge` walk both maps.
- WAL appends are O(record size) plus an fsync by default; checkpoints are
  O(total state) and are amortized by the journal size threshold.
- The structure is thread-safe within one process, not process-safe. Use one
  live `ChronoMap` per WAL path.
- The memory ceiling is an approximation intended as a tripwire, not a hard
  allocator guarantee.
