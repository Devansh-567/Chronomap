# ChronoMap

<!-- ChronoMap Logo -->
<p align="center">
  <img src="https://chronomap-logo.netlify.app/logo.png" alt="ChronoMap Logo" width="200">
</p>

[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-102%20passed-brightgreen.svg)](tests/)
[![Open Source Helpers](https://www.codetriage.com/devansh-567/chronomap/badges/users.svg)](https://www.codetriage.com/devansh-567/chronomap)



**ChronoMap** is a thread-safe, time-versioned key-value store for Python that maintains complete history of all changes. Perfect for configuration management, audit trails, time-series data, session stores, and any application requiring historical data tracking with **concurrency, async, and analytics.**

## ✨ Features

- **⏱️ Time-Versioned Storage** - Every value change is timestamped and preserved
- **🔒 Thread-Safe** - All operations are protected with locks for concurrent access
- **🌙 Async Support** – Full AsyncChronoMap for asyncio applications
- **📸 Snapshots & Rollback** - Create snapshots and rollback to any previous state
- **⏰ TTL Support** - Automatic key expiration with time-to-live
- **📊 Query & Analytics** – Filter, aggregate, count, and analyze your data
- **🧹 History Pruning** – Garbage-collect old versions to manage memory
- **📈 Statistics Tracking** – Monitor reads, writes, deletes, and snapshots
- **🔔 Event Hooks** – Register callbacks on every change (on_change)
- **🔄 Batch Operations** - Efficient `put_many()` and `delete_many()` operations
- **🔍 Advanced Queries** - Range queries, find latest keys, search by value
- **🤝 Merge & Diff** - Merge multiple maps and track differences
- **🔄 Context Manager** – Automatic rollback on exception with snapshot_context()
- **💾 Persistence** - Save/load from JSON or Pickle
- **🐼 Pandas Export** – Export full history to DataFrame for analysis
- **🐍 Pythonic API** - Dictionary-like interface with magic methods
- **📝 Comprehensive Testing** - 102 tests with >95% coverage

## 📦 Installation

```bash
pip install chronomap
```
> 💡 Optional: pip install pandas for to_dataframe() support 

## 🚀 Quick Start

```python
from chronomap import ChronoMap

cm = ChronoMap()
cm['user'] = 'alice'
cm['status'] = 'active'
print(cm['user'])

# Query active users
active = cm.query(lambda k, v: v == 'active')

# Track changes
def log_change(key, old, new, ts):
    print(f"{key}: {old} → {new}")
cm.on_change(log_change)

# Prune old history
cm.prune_all_history(keep_last=100)
```

## 📚 Documentation

### Basic Operations

```python
cm.put('key', 'value')
value = cm.get('key')
cm.delete('key')

cm['key'] = 'value'
value = cm['key']
del cm['key']

if 'key' in cm:
    print("Key exists")
value = cm.get('nonexistent', default='default_value')

try:
    value = cm.get('nonexistent', strict=True)
except ChronoMapKeyError:
    print("Key not found")
```
### Time Travel with Datetime
```python
# Use datetime strings or objects
cm.put('event', 'login', timestamp="2025-10-21T12:00:00")
cm.put('event', 'logout', timestamp=datetime(2025, 10, 21, 13, 0, 0))

# Query at specific time
value = cm.get('event', timestamp="2025-10-21T12:30:00")
```

### TTL and Auto-Expiry

```python
cm.put('session_token', 'abc123', ttl=3600)
print(cm.get('session_token'))
removed_count = cm.clean_expired_keys()
print(f"Removed {removed_count} expired keys")
```

### Snapshots and Context Manager

```python
cm['counter'] = 10
with cm.snapshot_context():
    cm['counter'] = 100
    cm['temp'] = 'data'
    raise Exception("Rollback!")  # Auto-rollback on exception

print(cm['counter'])  # 10
print(cm.get('temp'))  # None
```
### Event Hooks
```python
def audit_log(key, old, new, ts):
    print(f"[AUDIT] {key}: {old} → {new} at {ts}")

cm.on_change(audit_log)
cm['config'] = 'new_value'    
```
### Query & Aggregation
``` python
cm.put_many({'score1': 85, 'score2': 92, 'score3': 78})

# Filter
high_scores = cm.query(lambda k, v: isinstance(v, int) and v > 80)

# Aggregate
avg = cm.aggregate(lambda vals: sum(vals) / len(vals))
total = cm.aggregate(sum, keys=['score1', 'score2'])

# Count
active_count = cm.count(lambda k, v: v == 'active')
```

### History Pruning
```python
# Keep only last 10 versions
cm.prune_history('sensor', keep_last=10)

# Remove versions older than date
cm.prune_history('log', older_than="2025-01-01")

# Prune all keys
cm.prune_all_history(keep_last=100)
```
### AsyncChronoMap
```python
import asyncio
from chronomap import AsyncChronoMap

async def main():
    cm = AsyncChronoMap()
    await cm.put('key', 'value')
    value = await cm.get('key')
    snap = await cm.snapshot()
    keys = await cm.keys()
    latest = await cm.latest()

asyncio.run(main())
```
### Pandas Export
```python
# Requires: pip install pandas
df = cm.to_dataframe()
print(df.head())
#   key  value  timestamp            datetime  version
# 0  temp     20      100.0 1970-01-01 00:01:40        0
```

### Compression and Persistence
```python
# Save with compression
cm.save_pickle('state.pkl', compress=True)

# Load automatically detects compression
cm2 = ChronoMap.load_pickle('state.pkl')
```
### Statistics
```python
stats = cm.get_stats()
print(f"Writes: {stats['writes']}, Reads: {stats['reads']}")
cm.reset_stats()
```

### Batch Operations

```python
users = {
    'user:1': {'name': 'Alice', 'role': 'admin'},
    'user:2': {'name': 'Bob', 'role': 'user'},
    'user:3': {'name': 'Charlie', 'role': 'user'}
}
cm.put_many(users)
cm.put_many(users, ttl=3600)
cm.put_many(users, timestamp=1609459200)
deleted_count = cm.delete_many(['user:2', 'user:3'])
print(f"Deleted {deleted_count} keys")
```

### Advanced Queries

```python
cm.put('sensor', 10, timestamp=100)
cm.put('sensor', 15, timestamp=200)
cm.put('sensor', 20, timestamp=300)
readings = cm.get_range('sensor', start_ts=150, end_ts=250)

latest = cm.get_latest_keys(2)
for key, timestamp, value in latest:
    print(f"{key}: {value} (updated at {timestamp})")

cm.put_many({'user1': 'active', 'user2': 'active', 'user3': 'inactive'})
active_users = cm.get_keys_by_value('active')
```

### Merge and Diff

```python
cm1 = ChronoMap()
cm2 = ChronoMap()
cm1.put('shared', 'v1', timestamp=100)
cm2.put('shared', 'v2', timestamp=200)
cm2.put('unique', 'data')
cm1.merge(cm2, strategy='timestamp')
changed_keys = cm1.diff(cm2)
```

### Iteratons and Utilities
```python
for key in cm:
    print(key)

latest = cm.latest()
history = cm.history('key')
print(len(cm))
cm.clear()
```

## 🧪 Testing

```bash
# Run all tests
pytest tests/test_chronomap.py -v

# With coverage
pytest tests/test_chronomap.py --cov=chronomap --cov-report=html

# Run specific test class
pytest tests/test_chronomap.py::TestAsyncChronoMap -v
```

## Test coverage includes:

- ✅ Basic operations (put, get, delete)
- ✅ Batch operations
- ✅ TTL and expiry
- ✅ Advanced queries
- ✅ Snapshots, context manager, rollback
- ✅ Merge and diff
- ✅ Magic methods & iteration
- ✅ Persistence (JSON, Pickle, compression)
- ✅ Thread safety & RWLock
- ✅ AsyncChronoMap
- ✅ Query, aggregation, pruning
- ✅ Event hooks & statistics
- ✅ Pandas export
- ✅ Edge cases & integration scenarios

### Project Structure

```
chronomap/
├── chronomap/
│   ├── __init__.py
│   ├── chronomap.py           # Core implementation
│   ├── cli.py         
│   └── __main__.py            # CLI interface
├── tests/
│   └── test_chronomap.py      # Test suite
├── examples/
│   ├── config_manager.py
│   ├── session_store.py
│   └── metrics_store.py
├── logo/
│   └── logo.png
├── README.md
├── setup.py
├── pyproject.toml
└── LICENSE
```

### Contributing

1. Fork the repository
2. Write tests for your changes
3. Ensure all tests pass (`pytest tests/ -v`)
4. Commit your changes (`git commit -m 'Add amazing feature'`)
5. Push to the branch (`git push origin feature/amazing-feature`)
6. Open a Pull Request

## 📋 Requirements

- Python 3.8+
- No external dependencies for core functionality
- Optional: pandas for to_dataframe()
- Development dependencies: pytest, pytest-cov, pytest-asyncio

## 🗺️ Roadmap

- [ ] Async/await support ✅ (v2.1.0)
- [ ] Read-write locks ✅ (v2.1.0)
- [ ] Query & aggregation ✅ (v2.1.0)
- [ ] History pruning ✅ (v2.1.0)
- [ ] Event hooks ✅ (v2.1.0)
- [ ] Compression ✅ (v2.1.0)
- [ ] Pandas export ✅ (v2.1.0)
- [ ] SQLite backend for persistence
- [ ] Web UI for visualization
- [ ] Export to various formats (CSV, Parquet)
- [ ] Query language for complex searches
- [ ] Integration with popular frameworks (Django, Flask)

## 📈 Changelog

### v2.1.0 (2025)
- Added AsyncChronoMap for asyncio support
- Implemented read-write locks for better concurrency
- Added query filters, aggregations, and counting
- Added event hooks (on_change callbacks)
- Added history pruning (prune_history, prune_all_history)
- Added snapshot context manager (snapshot_context)
- Added operation statistics tracking
- Added compression support (zlib + pickle)
- Added Pandas DataFrame export
- Enhanced datetime string support ("2025-10-21T12:00:00")
- Improved CLI demo and error handling

### v2.0.0 (2025)

- Complete rewrite with enhanced features
- Added TTL/expiry support
- Added batch operations
- Added advanced queries (range, latest keys, search by value)
- Added merge and diff functionality
- Added comprehensive test suite (65 tests)
- Improved thread safety
- Enhanced documentation

### v1.0.0

- Initial release
- Basic time-versioned storage
- Snapshot and rollback
- Persistence support

## 💡 Tips and Best Practices

1. **Use TTL for temporary data** - Session tokens, cache entries, temporary flags
2. **Use snapshot_context()** - Risky operations – Auto-rollback on failure
3. **Prune history regularly** – Prevent memory bloat with prune_all_history()
4. **Use async for I/O-bound apps** – Web servers, data pipelines
5. **Monitor Stats** - Track usage patterns with get_stats()
6. **Enable compression** – For large persistent states
7. **Export to Pandas** – Analyze time-series data with familiar tools
8. **Take snapshots before risky operations** - Database migrations, bulk updates
9. **Use batch operations** - More efficient than individual operations
10. **Clean expired keys regularly** - Call `clean_expired_keys()` during maintenance
11. **Leverage history for auditing** - Track configuration changes, document versions
12. **Use descriptive key naming** - `user:123:profile` is better than `u123p`
13. **Persist regularly** - Save state periodically using `save_json()` or `save_pickle()`
14. **Monitor map size** - Large histories may need archiving or cleanup

## ❓ FAQ

**Q: Is ChronoMap suitable for production use?**  
A: Yes! ChronoMap is thread-safe, well-tested, and used in production environments.

**Q: How much memory does ChronoMap use?**  
A: Memory usage depends on the number of keys and history size. Each value change is stored, so keys with frequent updates will use more memory.

**Q: Can I use ChronoMap as a database?**  
A: ChronoMap is an in-memory store. For persistence, use `save_json()` or `save_pickle()`. For large-scale data, consider a proper database.

**Q: How do I limit history size?**  
A: Currently, you need to manually manage history. Consider periodically archiving old data or implementing custom cleanup logic.

**Q: Is ChronoMap compatible with multiprocessing?**  
A: ChronoMap is thread-safe but not process-safe. For multiprocessing, use separate instances or implement inter-process communication.

**Q: Can I use ChronoMap with Django/Flask?**  
A: Yes! ChronoMap works well as a cache layer or session store in web applications.

**Q:  How do I upgrade from v2.0.0?**    
A: Fully backward-compatible! Just pip install chronomap==2.1.0.

---

## 📄 License

## This project is licensed under the MIT License

Made with 😎 by [Devansh Singh](https://github.com/Devasnh-567)
