# Examples

These examples show how ChronoMap can be used in real-world scenarios.  
Each file is self-contained and runnable on its own.

---

## Running an Example

```bash
# Install ChronoMap first if you haven't
pip install -e ".[pandas]"

# Run any example
python examples/cache_manager.py
python examples/config_version_control.py
python examples/feature_flag.py
python examples/metrics_collector.py
python examples/session_manager.py
```

---

## What Each Example Covers

### `cache_manager.py`
Builds a smart caching layer on top of ChronoMap.

- Cache-aside pattern (`get_or_compute`)
- TTL-based automatic expiration
- Cache warmup / preloading
- Selective cache invalidation
- Cache hit rate monitoring

**Key ChronoMap features used:** `put()` with TTL, `get()`, `delete()`, `query()`, `get_stats()`

---

### `config_version_control.py`
Uses ChronoMap as a configuration management system with version control.

- Storing and updating application config
- Creating snapshots before deployments
- Instant rollback when something breaks
- Safe bulk updates with `snapshot_context()`
- Temporary feature flags with TTL
- Querying config by prefix or value type

**Key ChronoMap features used:** `snapshot()`, `rollback()`, `snapshot_context()`, `on_change()`, `query()`, `put_many()`

---

### `feature_flag.py`
A feature flag manager with A/B testing and gradual rollouts.

- Enabling flags for specific users or groups
- Gradual rollout (10% → 50% → 100%)
- Consistent A/B testing (same user always gets same result)
- Emergency kill switch to instantly disable a feature
- Full history of every flag change

**Key ChronoMap features used:** `put()`, `get()`, `history()`, `snapshot()`, `rollback()`, `query()`

---

### `metrics_collector.py`
Collects and analyzes system metrics over time, similar to lightweight Prometheus.

- Recording metrics with explicit timestamps
- Statistical analysis (mean, median, percentiles)
- Time-range queries (last N seconds)
- Real-time alerting when thresholds are crossed
- Anomaly detection using standard deviation
- Exporting data for visualization

**Key ChronoMap features used:** `put()` with timestamps, `get_range()`, `history()`, `on_change()`, `aggregate()`, `to_dataframe()`

---

### `session_manager.py`
A session storage system with automatic expiration and security monitoring.

- Creating sessions with TTL auto-expiry
- Validating sessions and refreshing TTL on activity
- Detecting multiple concurrent sessions per user
- Complete session audit trail
- Background cleanup of expired sessions

**Key ChronoMap features used:** `put()` with TTL, `get()`, `delete()`, `query()`, `history()`, `on_change()`, background TTL cleanup

---

## Want to Add an Example?

If you have a use case that isn't covered here, contributions are welcome!  
Check the [Contributing Guide](../CONTRIBUTING.md) to get started.

Good candidates for new examples:
- Job queue / task scheduling
- Rate limiter
- Leaderboard with score history
- Inventory tracking with stock history
