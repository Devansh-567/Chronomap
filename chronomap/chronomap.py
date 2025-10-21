"""
ChronoMap v2.1.0: Enhanced thread-safe, time-versioned key-value store.

New in v2.1.0:
- Read-write locks for better concurrency
- Async support (AsyncChronoMap)
- Query filters and aggregations
- Event hooks (on_change callbacks)
- Time travel with datetime strings
- History garbage collection
- Context manager for snapshots
- Export to Pandas DataFrame
- Compression support
- Performance benchmarking utilities
"""

from __future__ import annotations
import asyncio
import bisect
import json
import logging
import pickle
import threading
import math
import zlib
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, List, Tuple, Dict, Set, Iterator, Union, Callable
from collections.abc import Mapping

logger = logging.getLogger(__name__)


# ============================================================================
# Custom Exceptions
# ============================================================================

class ChronoMapError(Exception):
    """Base exception for ChronoMap errors."""
    pass


class ChronoMapKeyError(ChronoMapError, KeyError):
    """Raised when a key is not found in strict mode."""
    pass


class ChronoMapTypeError(ChronoMapError, TypeError):
    """Raised when an invalid type is provided."""
    pass


class ChronoMapValueError(ChronoMapError, ValueError):
    """Raised when an invalid value is provided."""
    pass


# ============================================================================
# Read-Write Lock for Better Concurrency
# ============================================================================

class RWLock:
    """Read-Write lock allowing multiple readers or single writer."""
    
    def __init__(self):
        self._readers = 0
        self._writers = 0
        self._read_ready = threading.Condition(threading.RLock())
        self._write_ready = threading.Condition(threading.RLock())
    
    def acquire_read(self):
        """Acquire read lock."""
        self._read_ready.acquire()
        try:
            while self._writers > 0:
                self._read_ready.wait()
            self._readers += 1
        finally:
            self._read_ready.release()
    
    def release_read(self):
        """Release read lock."""
        self._read_ready.acquire()
        try:
            self._readers -= 1
            if self._readers == 0:
                self._read_ready.notifyAll()
        finally:
            self._read_ready.release()
    
    def acquire_write(self):
        """Acquire write lock."""
        self._write_ready.acquire()
        self._writers += 1
        self._write_ready.release()
        
        self._read_ready.acquire()
        while self._readers > 0:
            self._read_ready.wait()
    
    def release_write(self):
        """Release write lock."""
        self._writers -= 1
        self._read_ready.notifyAll()
        self._read_ready.release()
        
        self._write_ready.acquire()
        self._write_ready.notifyAll()
        self._write_ready.release()


# ============================================================================
# Snapshot Context Manager
# ============================================================================

class SnapshotContext:
    """Context manager for automatic rollback on exception."""
    
    def __init__(self, chronomap: ChronoMap):
        self.chronomap = chronomap
        self.snapshot = None
    
    def __enter__(self) -> ChronoMap:
        self.snapshot = self.chronomap.snapshot()
        return self.chronomap
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            # Rollback on exception
            self.chronomap.rollback(self.snapshot)
        return False


# ============================================================================
# Main ChronoMap Class (Enhanced)
# ============================================================================

class ChronoMap:
    """
    Enhanced thread-safe, time-versioned key-value store.
    
    New Features in v2.1.0:
    - Better concurrency with read-write locks
    - Event hooks for change tracking
    - Query filters and aggregations
    - Time travel with datetime strings
    - History garbage collection
    - Context manager support
    - Compression
    """

    def __init__(self, debug: bool = False, use_rwlock: bool = True):
        """
        Initialize a ChronoMap.
        
        Args:
            debug: Enable debug logging if True.
            use_rwlock: Use read-write locks for better concurrency.
        """
        self._store: Dict[Any, List[Tuple[float, Any]]] = {}
        self._ttl: Dict[Any, float] = {}
        
        # Locking strategy
        if use_rwlock:
            self._lock = RWLock()
            self._use_rwlock = True
        else:
            self._lock = threading.RLock()
            self._use_rwlock = False
        
        self._snapshot_time: Optional[float] = None
        self._debug = debug
        
        # Event hooks (NEW in v2.1.0)
        self._change_callbacks: List[Callable] = []
        
        # Statistics (NEW in v2.1.0)
        self._stats = {
            'reads': 0,
            'writes': 0,
            'deletes': 0,
            'snapshots': 0
        }

        if debug:
            logger.setLevel(logging.DEBUG)
            if not logger.handlers:
                handler = logging.StreamHandler()
                handler.setFormatter(
                    logging.Formatter("[ChronoMap] %(levelname)s: %(message)s")
                )
                logger.addHandler(handler)

    def _current_time(self) -> float:
        """Get current UTC timestamp."""
        return datetime.utcnow().timestamp()
    
    def _parse_timestamp(self, timestamp: Union[float, str, datetime]) -> float:
        """Parse timestamp from various formats."""
        if isinstance(timestamp, str):
            # Parse ISO format datetime string
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                return dt.timestamp()
            except ValueError:
                raise ChronoMapValueError(f"Invalid datetime string: {timestamp}")
        elif isinstance(timestamp, datetime):
            return timestamp.timestamp()
        elif isinstance(timestamp, (int, float)):
            return float(timestamp)
        else:
            raise ChronoMapTypeError(f"Invalid timestamp type: {type(timestamp)}")

    def _validate_key(self, key: Any) -> None:
        """Validate that key is hashable."""
        try:
            hash(key)
        except TypeError:
            raise ChronoMapTypeError(f"Key must be hashable, got {type(key).__name__}")

    def _validate_timestamp(self, timestamp: float) -> None:
        """Validate that timestamp is a finite number."""
        if not isinstance(timestamp, (int, float)):
            raise ChronoMapTypeError(f"Timestamp must be numeric, got {type(timestamp).__name__}")
        if not math.isfinite(timestamp):
            raise ChronoMapValueError(f"Timestamp must be finite, got {timestamp}")

    def _is_expired(self, key: Any) -> bool:
        """Check if a key has expired."""
        if key not in self._ttl:
            return False
        return self._current_time() >= self._ttl[key]

    def _clean_expired(self, key: Any) -> bool:
        """Remove expired key. Returns True if key was expired and removed."""
        if self._is_expired(key):
            if key in self._store:
                del self._store[key]
            del self._ttl[key]
            logger.debug("EXPIRED key=%r", key)
            return True
        return False
    
    def _acquire_read(self):
        """Acquire read lock."""
        if self._use_rwlock:
            self._lock.acquire_read()
        else:
            self._lock.acquire()
    
    def _release_read(self):
        """Release read lock."""
        if self._use_rwlock:
            self._lock.release_read()
        else:
            self._lock.release()
    
    def _acquire_write(self):
        """Acquire write lock."""
        if self._use_rwlock:
            self._lock.acquire_write()
        else:
            self._lock.acquire()
    
    def _release_write(self):
        """Release write lock."""
        if self._use_rwlock:
            self._lock.release_write()
        else:
            self._lock.release()
    
    def _trigger_change_callbacks(self, key: Any, old_value: Any, new_value: Any, timestamp: float):
        """Trigger all registered change callbacks."""
        for callback in self._change_callbacks:
            try:
                callback(key, old_value, new_value, timestamp)
            except Exception as e:
                logger.error(f"Error in change callback: {e}")

    # ========================================================================
    # Event Hooks (NEW in v2.1.0)
    # ========================================================================
    
    def on_change(self, callback: Callable[[Any, Any, Any, float], None]) -> None:
        """
        Register a callback to be called on every change.
        
        Args:
            callback: Function(key, old_value, new_value, timestamp) -> None
        
        Example:
            >>> cm.on_change(lambda k, o, n, t: print(f"{k}: {o} -> {n}"))
        """
        self._change_callbacks.append(callback)
    
    def remove_change_callback(self, callback: Callable) -> bool:
        """Remove a change callback. Returns True if found."""
        try:
            self._change_callbacks.remove(callback)
            return True
        except ValueError:
            return False

    # ========================================================================
    # Core Methods (Enhanced)
    # ========================================================================

    def put(
        self,
        key: Any,
        value: Any,
        timestamp: Optional[Union[float, str, datetime]] = None,
        ttl: Optional[float] = None
    ) -> None:
        """
        Insert a key-value pair at the given timestamp (or now).
        
        Args:
            key: The key to store (must be hashable).
            value: The value to store.
            timestamp: Optional timestamp (float, datetime string, or datetime object).
            ttl: Optional time-to-live in seconds.
        
        Example:
            >>> cm.put('temp', 20.5)
            >>> cm.put('temp', 21.0, timestamp="2025-10-21T12:00:00")
        """
        self._validate_key(key)
        ts = self._parse_timestamp(timestamp) if timestamp is not None else self._current_time()
        self._validate_timestamp(ts)

        self._acquire_write()
        try:
            # Get old value for callback
            old_value = None
            if key in self._store and self._store[key]:
                old_value = self._store[key][-1][1]
            
            if key not in self._store:
                self._store[key] = []
            versions = self._store[key]

            # Insert maintaining sorted order
            if not versions or ts >= versions[-1][0]:
                versions.append((ts, value))
            else:
                bisect.insort(versions, (ts, value), key=lambda x: x[0])

            # Set TTL if provided
            if ttl is not None:
                if ttl <= 0:
                    raise ChronoMapValueError(f"TTL must be positive, got {ttl}")
                self._ttl[key] = self._current_time() + ttl

            self._stats['writes'] += 1
            logger.debug("PUT key=%r value=%r at ts=%f ttl=%s", key, value, ts, ttl)
            
            # Trigger callbacks
            self._trigger_change_callbacks(key, old_value, value, ts)
        finally:
            self._release_write()

    def get(
        self,
        key: Any,
        timestamp: Optional[Union[float, str, datetime]] = None,
        default: Any = None,
        *,
        strict: bool = False
    ) -> Any:
        """
        Retrieve the value for a key at a given timestamp.
        
        Args:
            key: The key to retrieve.
            timestamp: Optional timestamp (float, datetime string, or datetime object).
            default: Default value if key not found (when strict=False).
            strict: Raise KeyError if key not found when True.
            
        Returns:
            The value at the specified timestamp.
        """
        ts = self._parse_timestamp(timestamp) if timestamp is not None else self._current_time()
        self._validate_timestamp(ts)

        self._acquire_read()
        try:
            # Check expiry
            if self._clean_expired(key):
                if strict:
                    raise ChronoMapKeyError(key)
                return default

            versions = self._store.get(key, [])
            if not versions:
                if strict:
                    raise ChronoMapKeyError(key)
                return default

            times = [v[0] for v in versions]
            idx = bisect.bisect_right(times, ts) - 1
            if idx < 0:
                if strict:
                    raise ChronoMapKeyError(key)
                return default

            value = versions[idx][1]
            self._stats['reads'] += 1
            logger.debug("GET key=%r -> %r at ts=%f", key, value, ts)
            return value
        finally:
            self._release_read()

    def delete(self, key: Any) -> bool:
        """Delete all history of a key."""
        self._acquire_write()
        try:
            existed = key in self._store
            if existed:
                del self._store[key]
                if key in self._ttl:
                    del self._ttl[key]
                self._stats['deletes'] += 1
                logger.debug("DELETE key=%r", key)
            return existed
        finally:
            self._release_write()

    # ========================================================================
    # Query & Analytics (NEW in v2.1.0)
    # ========================================================================
    
    def query(
        self,
        predicate: Callable[[Any, Any], bool],
        timestamp: Optional[Union[float, str, datetime]] = None
    ) -> Dict[Any, Any]:
        """
        Filter keys based on a predicate function.
        
        Args:
            predicate: Function(key, value) -> bool
            timestamp: Optional timestamp for evaluation
        
        Returns:
            Dictionary of matching key-value pairs
        
        Example:
            >>> cm.query(lambda k, v: isinstance(v, int) and v > 100)
        """
        ts = self._parse_timestamp(timestamp) if timestamp is not None else self._current_time()
        
        self._acquire_read()
        try:
            result = {}
            for key in self._store:
                if self._is_expired(key):
                    continue
                value = self.get(key, timestamp=ts)
                if value is not None and predicate(key, value):
                    result[key] = value
            return result
        finally:
            self._release_read()
    
    def aggregate(
        self,
        func: Callable[[List[Any]], Any],
        keys: Optional[List[Any]] = None,
        timestamp: Optional[Union[float, str, datetime]] = None
    ) -> Any:
        """
        Apply aggregation function to values.
        
        Args:
            func: Aggregation function (e.g., sum, max, len)
            keys: Optional list of keys (defaults to all keys)
            timestamp: Optional timestamp for evaluation
        
        Returns:
            Aggregated result
        
        Example:
            >>> cm.aggregate(sum, keys=['score1', 'score2', 'score3'])
            >>> cm.aggregate(lambda vals: sum(vals) / len(vals))  # average
        """
        ts = self._parse_timestamp(timestamp) if timestamp is not None else self._current_time()
        
        self._acquire_read()
        try:
            target_keys = keys if keys is not None else list(self._store.keys())
            values = []
            
            for key in target_keys:
                if not self._is_expired(key):
                    val = self.get(key, timestamp=ts)
                    if val is not None:
                        values.append(val)
            
            return func(values) if values else None
        finally:
            self._release_read()
    
    def count(
        self,
        predicate: Optional[Callable[[Any, Any], bool]] = None,
        timestamp: Optional[Union[float, str, datetime]] = None
    ) -> int:
        """
        Count keys matching optional predicate.
        
        Example:
            >>> cm.count()  # Count all keys
            >>> cm.count(lambda k, v: v > 100)  # Count where value > 100
        """
        if predicate is None:
            return len(self)
        
        return len(self.query(predicate, timestamp))

    # ========================================================================
    # History Management (Enhanced in v2.1.0)
    # ========================================================================
    
    def prune_history(
        self,
        key: Any,
        keep_last: Optional[int] = None,
        older_than: Optional[Union[float, str, datetime]] = None
    ) -> int:
        """
        Remove old history entries for a key.
        
        Args:
            key: The key to prune
            keep_last: Keep only the last N versions
            older_than: Remove versions older than this timestamp
        
        Returns:
            Number of versions removed
        
        Example:
            >>> cm.prune_history('sensor', keep_last=100)
            >>> cm.prune_history('sensor', older_than="2025-01-01")
        """
        self._acquire_write()
        try:
            if key not in self._store:
                return 0
            
            versions = self._store[key]
            original_count = len(versions)
            
            if keep_last is not None:
                versions[:] = versions[-keep_last:]
            
            if older_than is not None:
                cutoff_ts = self._parse_timestamp(older_than)
                versions[:] = [(ts, val) for ts, val in versions if ts >= cutoff_ts]
            
            removed = original_count - len(versions)
            logger.debug("PRUNE key=%r removed %d versions", key, removed)
            return removed
        finally:
            self._release_write()
    
    def prune_all_history(
        self,
        keep_last: Optional[int] = None,
        older_than: Optional[Union[float, str, datetime]] = None
    ) -> int:
        """
        Prune history for all keys.
        
        Returns:
            Total number of versions removed
        """
        total_removed = 0
        for key in list(self.keys()):
            total_removed += self.prune_history(key, keep_last, older_than)
        return total_removed

    # ========================================================================
    # Batch Operations
    # ========================================================================

    def put_many(
        self,
        items: Dict[Any, Any],
        timestamp: Optional[Union[float, str, datetime]] = None,
        ttl: Optional[float] = None
    ) -> None:
        """Insert multiple key-value pairs at once."""
        for key, value in items.items():
            self.put(key, value, timestamp=timestamp, ttl=ttl)
        logger.debug("PUT_MANY %d items", len(items))

    def delete_many(self, keys: List[Any]) -> int:
        """Delete multiple keys at once."""
        count = 0
        for key in keys:
            if self.delete(key):
                count += 1
        logger.debug("DELETE_MANY %d/%d keys", count, len(keys))
        return count

    # ========================================================================
    # Advanced Queries
    # ========================================================================

    def get_range(
        self,
        key: Any,
        start_ts: Optional[Union[float, str, datetime]] = None,
        end_ts: Optional[Union[float, str, datetime]] = None
    ) -> List[Tuple[float, Any]]:
        """Get all values for a key within a time range."""
        self._acquire_read()
        try:
            if self._clean_expired(key):
                return []

            versions = self._store.get(key, [])
            if not versions:
                return []

            start = self._parse_timestamp(start_ts) if start_ts is not None else float('-inf')
            end = self._parse_timestamp(end_ts) if end_ts is not None else self._current_time()

            result = [(ts, val) for ts, val in versions if start <= ts <= end]
            logger.debug("GET_RANGE key=%r found %d entries", key, len(result))
            return result
        finally:
            self._release_read()

    def get_latest_keys(self, n: int) -> List[Tuple[Any, float, Any]]:
        """Get the n most recently updated keys."""
        self._acquire_read()
        try:
            latest_items = []
            for key, versions in self._store.items():
                if self._is_expired(key):
                    continue
                if versions:
                    ts, val = versions[-1]
                    latest_items.append((key, ts, val))

            latest_items.sort(key=lambda x: x[1], reverse=True)
            result = latest_items[:n]
            logger.debug("GET_LATEST_KEYS returning %d keys", len(result))
            return result
        finally:
            self._release_read()

    def get_keys_by_value(self, value: Any, timestamp: Optional[Union[float, str, datetime]] = None) -> List[Any]:
        """Get all keys that have a specific value at the given timestamp."""
        ts = self._parse_timestamp(timestamp) if timestamp is not None else self._current_time()
        self._acquire_read()
        try:
            keys = []
            for key in self._store:
                if self._is_expired(key):
                    continue
                if self.get(key, timestamp=ts) == value:
                    keys.append(key)
            logger.debug("GET_KEYS_BY_VALUE found %d keys", len(keys))
            return keys
        finally:
            self._release_read()

    # ========================================================================
    # Snapshot, Diff, Rollback (Enhanced)
    # ========================================================================

    def snapshot(self) -> ChronoMap:
        """Return a deep-copy snapshot of the current map."""
        self._acquire_read()
        try:
            snap = ChronoMap(debug=self._debug, use_rwlock=self._use_rwlock)
            snap._store = deepcopy(self._store)
            snap._ttl = deepcopy(self._ttl)
            snap._snapshot_time = self._current_time()
            self._stats['snapshots'] += 1
            logger.debug("SNAPSHOT created at ts=%f", snap._snapshot_time)
            return snap
        finally:
            self._release_read()
    
    def snapshot_context(self) -> SnapshotContext:
        """
        Return a context manager for automatic rollback on exception.
        
        Example:
            >>> with cm.snapshot_context():
            ...     cm['temp'] = 42
            ...     raise Exception()  # Auto-rollback
        """
        return SnapshotContext(self)

    def rollback(self, snapshot: ChronoMap) -> None:
        """Rollback the map to a previous snapshot."""
        if not isinstance(snapshot, ChronoMap):
            raise ChronoMapTypeError("Expected ChronoMap instance for rollback.")
        
        self._acquire_write()
        try:
            self._store = deepcopy(snapshot._store)
            self._ttl = deepcopy(snapshot._ttl)
            logger.debug("ROLLBACK to snapshot at ts=%s", snapshot._snapshot_time)
        finally:
            self._release_write()

    def diff(self, other: ChronoMap) -> Set[Any]:
        """Return keys with differing latest values compared to another map."""
        if not isinstance(other, ChronoMap):
            raise ChronoMapTypeError("Expected ChronoMap instance for diff.")
        
        self._acquire_read()
        try:
            changed = set()
            all_keys = set(self._store) | set(other._store)
            for key in all_keys:
                if self._is_expired(key) or other._is_expired(key):
                    if self._is_expired(key) != other._is_expired(key):
                        changed.add(key)
                    continue
                if self.get(key) != other.get(key):
                    changed.add(key)
            logger.debug("DIFF found %d keys", len(changed))
            return changed
        finally:
            self._release_read()

    def diff_detailed(self, other: ChronoMap) -> List[Tuple[Any, Any, Any]]:
        """Return (key, old_value, new_value) for changed keys."""
        if not isinstance(other, ChronoMap):
            raise ChronoMapTypeError("Expected ChronoMap instance for diff_detailed.")
        
        self._acquire_read()
        try:
            changes = []
            all_keys = set(self._store) | set(other._store)
            for key in all_keys:
                if self._is_expired(key) or other._is_expired(key):
                    continue
                old_val = other.get(key)
                new_val = self.get(key)
                if old_val != new_val:
                    changes.append((key, old_val, new_val))
            return changes
        finally:
            self._release_read()

    # ========================================================================
    # Merge
    # ========================================================================

    def merge(self, other: ChronoMap, strategy: str = 'timestamp') -> None:
        """Merge another ChronoMap into this one."""
        if not isinstance(other, ChronoMap):
            raise ChronoMapTypeError("Expected ChronoMap instance for merge.")
        
        if strategy not in ('timestamp', 'overwrite'):
            raise ChronoMapValueError(f"Invalid merge strategy: {strategy}")

        self._acquire_write()
        try:
            if strategy == 'timestamp':
                for key, versions in other._store.items():
                    for ts, val in versions:
                        self.put(key, val, timestamp=ts)
                for key, expiry in other._ttl.items():
                    if key not in self._ttl or expiry > self._ttl[key]:
                        self._ttl[key] = expiry
            else:  # overwrite
                for key, versions in other._store.items():
                    self._store[key] = deepcopy(versions)
                for key, expiry in other._ttl.items():
                    self._ttl[key] = expiry

            logger.debug("MERGE completed with strategy=%s", strategy)
        finally:
            self._release_write()

    # ========================================================================
    # Utilities (Enhanced)
    # ========================================================================

    def latest(self) -> Dict[Any, Any]:
        """Get a dictionary of all keys with their latest values."""
        self._acquire_read()
        try:
            result = {}
            for k, v in self._store.items():
                if self._is_expired(k):
                    continue
                if v:
                    result[k] = v[-1][1]
            return result
        finally:
            self._release_read()

    def history(self, key: Any) -> List[Tuple[float, Any]]:
        """Get the complete history of a key."""
        self._acquire_read()
        try:
            if self._clean_expired(key):
                return []
            return list(self._store.get(key, []))
        finally:
            self._release_read()

    def clear(self) -> None:
        """Clear all data from the map."""
        self._acquire_write()
        try:
            self._store.clear()
            self._ttl.clear()
            logger.debug("CLEAR all data")
        finally:
            self._release_write()

    def clean_expired_keys(self) -> int:
        """Manually clean all expired keys."""
        self._acquire_write()
        try:
            count = 0
            expired_keys = []
            for key in list(self._ttl.keys()):
                if self._is_expired(key):
                    expired_keys.append(key)
            
            for key in expired_keys:
                if key in self._store:
                    del self._store[key]
                del self._ttl[key]
                count += 1
            
            logger.debug("CLEAN_EXPIRED removed %d keys", count)
            return count
        finally:
            self._release_write()
    
    def get_stats(self) -> Dict[str, int]:
        """Get operation statistics."""
        return self._stats.copy()
    
    def reset_stats(self) -> None:
        """Reset operation statistics."""
        self._stats = {
            'reads': 0,
            'writes': 0,
            'deletes': 0,
            'snapshots': 0
        }

    # ========================================================================
    # Export (NEW in v2.1.0)
    # ========================================================================
    
    def to_dataframe(self):
        """
        Export to Pandas DataFrame (requires pandas).
        
        Returns:
            DataFrame with columns: key, value, timestamp, version
        
        Example:
            >>> df = cm.to_dataframe()
            >>> df.groupby('key')['value'].mean()
        """
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("pandas is required for to_dataframe(). Install with: pip install pandas")
        
        self._acquire_read()
        try:
            rows = []
            for key, versions in self._store.items():
                if self._is_expired(key):
                    continue
                for version_idx, (ts, val) in enumerate(versions):
                    rows.append({
                        'key': key,
                        'value': val,
                        'timestamp': ts,
                        'datetime': datetime.fromtimestamp(ts),
                        'version': version_idx
                    })
            
            return pd.DataFrame(rows)
        finally:
            self._release_read()

    # ========================================================================
    # Pythonic Container Methods
    # ========================================================================

    def keys(self) -> Iterator[Any]:
        """Iterate over all keys (non-expired)."""
        self._acquire_read()
        try:
            keys_list = [key for key in self._store.keys() if not self._is_expired(key)]
        finally:
            self._release_read()
        
        for key in keys_list:
            yield key

    def values(self) -> Iterator[Any]:
        """Iterate over all latest values (non-expired)."""
        self._acquire_read()
        try:
            values_list = []
            for key, v in self._store.items():
                if not self._is_expired(key) and v:
                    values_list.append(v[-1][1])
        finally:
            self._release_read()
        
        for value in values_list:
            yield value

    def items(self) -> Iterator[Tuple[Any, Any]]:
        """Iterate over all (key, latest_value) pairs (non-expired)."""
        self._acquire_read()
        try:
            items_list = []
            for k, v in self._store.items():
                if not self._is_expired(k) and v:
                    items_list.append((k, v[-1][1]))
        finally:
            self._release_read()
        
        for item in items_list:
            yield item

    def iter_history(self, key: Any) -> Iterator[Tuple[float, Any]]:
        """Iterate over the history of a key."""
        self._acquire_read()
        try:
            if self._clean_expired(key):
                versions = []
            else:
                versions = list(self._store.get(key, []))
        finally:
            self._release_read()
        
        for ts, val in versions:
            yield (ts, val)

    def __iter__(self) -> Iterator[Any]:
        """Iterate over keys."""
        return self.keys()

    def __len__(self) -> int:
        """Return number of keys (non-expired)."""
        self._acquire_read()
        try:
            expired = []
            for key in self._store:
                if self._is_expired(key):
                    expired.append(key)
            return len(self._store) - len(expired)
        finally:
            self._release_read()

    def __contains__(self, key: Any) -> bool:
        """Check if key exists (and is not expired)."""
        self._acquire_read()
        try:
            if key not in self._store:
                return False
            if self._is_expired(key):
                return False
            return len(self._store.get(key, [])) > 0
        finally:
            self._release_read()

    def __getitem__(self, key: Any) -> Any:
        """Get latest value for key. Raises KeyError if not found."""
        return self.get(key, strict=True)

    def __setitem__(self, key: Any, value: Any) -> None:
        """Set value for key at current timestamp."""
        self.put(key, value)

    def __delitem__(self, key: Any) -> None:
        """Delete key. Raises KeyError if not found."""
        if not self.delete(key):
            raise ChronoMapKeyError(key)

    def __eq__(self, other: Any) -> bool:
        """Check equality based on latest values."""
        if not isinstance(other, ChronoMap):
            return False
        return self.latest() == other.latest()

    def __bool__(self) -> bool:
        """Return True if map has keys."""
        return len(self) > 0

    def __repr__(self) -> str:
        """String representation showing latest values."""
        self._acquire_read()
        try:
            non_expired_keys = [k for k in self._store.keys() if not self._is_expired(k)]
            return f"ChronoMap(keys={non_expired_keys[:10]}{'...' if len(non_expired_keys) > 10 else ''})"
        finally:
            self._release_read()

    @property
    def snapshot_time(self) -> Optional[float]:
        """Get the snapshot creation time (if this is a snapshot)."""
        return self._snapshot_time

    # ========================================================================
    # Persistence (Enhanced with Compression)
    # ========================================================================

    def to_dict(self, compress: bool = False) -> Union[Dict[str, Any], bytes]:
        """
        Serialize to dictionary (compatible with JSON/pickle).
        
        Args:
            compress: If True, return compressed bytes instead of dict
        
        Returns:
            Dictionary or compressed bytes
        """
        self._acquire_read()
        try:
            data = {
                'store': deepcopy(self._store),
                'ttl': deepcopy(self._ttl),
                'snapshot_time': self._snapshot_time,
                'version': '2.1.0'
            }
            
            if compress:
                import pickle
                pickled = pickle.dumps(data)
                compressed = zlib.compress(pickled, level=6)
                logger.debug("COMPRESS: %d -> %d bytes (%.1f%%)", 
                           len(pickled), len(compressed), 
                           100 * len(compressed) / len(pickled))
                return compressed
            
            return data
        finally:
            self._release_read()

    @classmethod
    def from_dict(cls, data: Union[Dict[str, Any], bytes], debug: bool = False, 
                  use_rwlock: bool = True) -> ChronoMap:
        """
        Reconstruct ChronoMap from dictionary or compressed bytes.
        
        Args:
            data: Dictionary from to_dict() or compressed bytes
            debug: Enable debug mode
            use_rwlock: Use read-write locks
        
        Returns:
            New ChronoMap instance
        """
        if isinstance(data, bytes):
            # Decompress
            decompressed = zlib.decompress(data)
            import pickle
            data = pickle.loads(decompressed)
        
        instance = cls(debug=debug, use_rwlock=use_rwlock)
        instance._store = deepcopy(data.get('store', {}))
        instance._ttl = deepcopy(data.get('ttl', {}))
        instance._snapshot_time = data.get('snapshot_time')
        return instance

    def save_json(self, file_path: Union[str, Path]) -> None:
        """Save ChronoMap to JSON file."""
        path = Path(file_path)
        data = self.to_dict()
        
        json_data = {
            'store': {str(k): v for k, v in data['store'].items()},
            'ttl': {str(k): v for k, v in data['ttl'].items()},
            'snapshot_time': data['snapshot_time'],
            'version': data.get('version', '2.0.0')
        }
        
        with open(path, 'w') as f:
            json.dump(json_data, f, indent=2)
        logger.debug("SAVE_JSON to %s", file_path)

    @classmethod
    def load_json(cls, file_path: Union[str, Path], debug: bool = False, 
                  use_rwlock: bool = True) -> ChronoMap:
        """Load ChronoMap from JSON file."""
        path = Path(file_path)
        with open(path, 'r') as f:
            json_data = json.load(f)
        
        data = {
            'store': json_data['store'],
            'ttl': json_data['ttl'],
            'snapshot_time': json_data.get('snapshot_time'),
            'version': json_data.get('version', '2.0.0')
        }
        
        logger.debug("LOAD_JSON from %s", file_path)
        return cls.from_dict(data, debug=debug, use_rwlock=use_rwlock)

    def save_pickle(self, file_path: Union[str, Path], compress: bool = False) -> None:
        """
        Save ChronoMap to pickle file.
        
        Args:
            file_path: Path to save pickle file
            compress: Compress the data with zlib
        """
        path = Path(file_path)
        data = self.to_dict(compress=compress)
        
        with open(path, 'wb') as f:
            if compress:
                f.write(data)  # Already compressed bytes
            else:
                pickle.dump(data, f)
        
        logger.debug("SAVE_PICKLE to %s (compressed=%s)", file_path, compress)

    @classmethod
    def load_pickle(cls, file_path: Union[str, Path], debug: bool = False,
                    use_rwlock: bool = True) -> ChronoMap:
        """
        Load ChronoMap from pickle file.
        
        Args:
            file_path: Path to pickle file
            debug: Enable debug mode
            use_rwlock: Use read-write locks
        
        Returns:
            New ChronoMap instance
        """
        path = Path(file_path)
        with open(path, 'rb') as f:
            data_bytes = f.read()
        
        # Try to detect if it's compressed
        try:
            data = pickle.loads(data_bytes)
        except:
            # Try decompression
            data = zlib.decompress(data_bytes)
            data = pickle.loads(data)
        
        logger.debug("LOAD_PICKLE from %s", file_path)
        return cls.from_dict(data, debug=debug, use_rwlock=use_rwlock)


# ============================================================================
# Async ChronoMap (NEW in v2.1.0)
# ============================================================================

class AsyncChronoMap:
    """
    Async version of ChronoMap for use with asyncio.
    
    Example:
        >>> async def main():
        ...     cm = AsyncChronoMap()
        ...     await cm.put('key', 'value')
        ...     value = await cm.get('key')
        ...     print(value)
    """
    
    def __init__(self, debug: bool = False):
        """Initialize AsyncChronoMap."""
        self._store: Dict[Any, List[Tuple[float, Any]]] = {}
        self._ttl: Dict[Any, float] = {}
        self._lock = asyncio.Lock()
        self._snapshot_time: Optional[float] = None
        self._debug = debug
        self._change_callbacks: List[Callable] = []
        self._stats = {
            'reads': 0,
            'writes': 0,
            'deletes': 0,
            'snapshots': 0
        }
        
        if debug:
            logger.setLevel(logging.DEBUG)
    
    def _current_time(self) -> float:
        """Get current UTC timestamp."""
        return datetime.utcnow().timestamp()
    
    def _parse_timestamp(self, timestamp: Union[float, str, datetime]) -> float:
        """Parse timestamp from various formats."""
        if isinstance(timestamp, str):
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                return dt.timestamp()
            except ValueError:
                raise ChronoMapValueError(f"Invalid datetime string: {timestamp}")
        elif isinstance(timestamp, datetime):
            return timestamp.timestamp()
        elif isinstance(timestamp, (int, float)):
            return float(timestamp)
        else:
            raise ChronoMapTypeError(f"Invalid timestamp type: {type(timestamp)}")
    
    def _validate_key(self, key: Any) -> None:
        """Validate that key is hashable."""
        try:
            hash(key)
        except TypeError:
            raise ChronoMapTypeError(f"Key must be hashable, got {type(key).__name__}")
    
    def _is_expired(self, key: Any) -> bool:
        """Check if a key has expired."""
        if key not in self._ttl:
            return False
        return self._current_time() >= self._ttl[key]
    
    async def put(
        self,
        key: Any,
        value: Any,
        timestamp: Optional[Union[float, str, datetime]] = None,
        ttl: Optional[float] = None
    ) -> None:
        self._validate_key(key)
        ts = self._parse_timestamp(timestamp) if timestamp is not None else self._current_time()
        
        async with self._lock:
            old_value = None
            if key in self._store and self._store[key]:
                old_value = self._store[key][-1][1]
            
            if key not in self._store:
                self._store[key] = []
            versions = self._store[key]
            
            if not versions or ts >= versions[-1][0]:
                versions.append((ts, value))
            else:
                bisect.insort(versions, (ts, value), key=lambda x: x[0])
            
            if ttl is not None:
                if ttl <= 0:
                    raise ChronoMapValueError(f"TTL must be positive, got {ttl}")
                self._ttl[key] = self._current_time() + ttl
            
            self._stats['writes'] += 1
            
            # Trigger callbacks
            for callback in self._change_callbacks:
                if asyncio.iscoroutinefunction(callback):
                    await callback(key, old_value, value, ts)
                else:
                    callback(key, old_value, value, ts)

    async def put_many(
        self,
        items: Dict[Any, Any],
        timestamp: Optional[Union[float, str, datetime]] = None,
        ttl: Optional[float] = None
    ) -> None:
        """Insert multiple key-value pairs asynchronously."""
        for key, value in items.items():
            await self.put(key, value, timestamp=timestamp, ttl=ttl)

    async def get(
        self,
        key: Any,
        timestamp: Optional[Union[float, str, datetime]] = None,
        default: Any = None,
        *,
        strict: bool = False
    ) -> Any:
        """Retrieve a value asynchronously."""
        ts = self._parse_timestamp(timestamp) if timestamp is not None else self._current_time()
        
        async with self._lock:
            if self._is_expired(key):
                if key in self._store:
                    del self._store[key]
                if key in self._ttl:
                    del self._ttl[key]
                if strict:
                    raise ChronoMapKeyError(key)
                return default
            
            versions = self._store.get(key, [])
            if not versions:
                if strict:
                    raise ChronoMapKeyError(key)
                return default
            
            times = [v[0] for v in versions]
            idx = bisect.bisect_right(times, ts) - 1
            if idx < 0:
                if strict:
                    raise ChronoMapKeyError(key)
                return default
            
            self._stats['reads'] += 1
            return versions[idx][1]
    
    async def delete(self, key: Any) -> bool:
        """Delete a key asynchronously."""
        async with self._lock:
            existed = key in self._store
            if existed:
                del self._store[key]
                if key in self._ttl:
                    del self._ttl[key]
                self._stats['deletes'] += 1
            return existed
    
    async def snapshot(self) -> AsyncChronoMap:
        """Create a snapshot asynchronously."""
        async with self._lock:
            snap = AsyncChronoMap(debug=self._debug)
            snap._store = deepcopy(self._store)
            snap._ttl = deepcopy(self._ttl)
            snap._snapshot_time = self._current_time()
            self._stats['snapshots'] += 1
            return snap
    
    def on_change(self, callback: Callable) -> None:
        """Register change callback (can be sync or async)."""
        self._change_callbacks.append(callback)
    
    async def keys(self) -> List[Any]:
        """Get all keys asynchronously."""
        async with self._lock:
            return [k for k in self._store.keys() if not self._is_expired(k)]
    
    async def latest(self) -> Dict[Any, Any]:
        """Get latest values asynchronously."""
        async with self._lock:
            result = {}
            for k, v in self._store.items():
                if self._is_expired(k):
                    continue
                if v:
                    result[k] = v[-1][1]
            return result
    
    def get_stats(self) -> Dict[str, int]:
        """Get operation statistics."""
        return self._stats.copy()


# ============================================================================ 
# Version Info
# ============================================================================

__version__ = "2.1.0"
__all__ = [
    "ChronoMap",
    "AsyncChronoMap",
    "ChronoMapError",
    "ChronoMapKeyError",
    "ChronoMapTypeError",
    "ChronoMapValueError",
    "SnapshotContext",
    "RWLock",
]
