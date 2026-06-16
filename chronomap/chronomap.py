"""
ChronoMap v2.2.0: Production-grade thread-safe, time-versioned key-value store.

New in v2.2.0:
- Auto-pruning with max_history limits
- LRU cache for read optimization
- Background TTL cleanup thread
- Memory usage monitoring and limits
- Batch operation optimizations
- Enhanced compression with multiple algorithms
- Improved async performance
- Better memory efficiency

Previous features (v2.1.0):
- Read-write locks for better concurrency
- Async support (AsyncChronoMap)
- Query filters and aggregations
- Event hooks (on_change callbacks)
- Time travel with datetime strings
- History garbage collection
- Context manager for snapshots
- Export to Pandas DataFrame
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
import gzip
import bz2
import lzma
import weakref
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, List, Tuple, Dict, Set, Iterator, Union, Callable, Awaitable
from collections.abc import Mapping
from collections import OrderedDict
from functools import wraps
import time as time_module

logger = logging.getLogger(__name__)

ChangeCallback = Callable[[Any, Any, Any, float], Union[Awaitable[None], None]]
KeyChangeCallback = Callable[[Any, Any, float], Union[Awaitable[None], None]]
_CACHE_MISS = object()


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


class ChronoMapMemoryError(ChronoMapError, MemoryError):
    """Raised when memory limit is exceeded."""
    pass


# ============================================================================
# LRU Cache for Read Optimization (NEW in v2.2.0)
# ===========================
# =================================================

class LRUCache:
    """Thread-safe LRU cache for frequently accessed keys."""
    
    def __init__(self, capacity: int = 1000) -> None:
        self.capacity = capacity
        self.cache: OrderedDict = OrderedDict()
        self.lock = threading.Lock()
        self.hits = 0
        self.misses = 0
    
    def get(self, key: Tuple[Any, float], default: Any = None) -> Any:
        """
        Get value from cache.
        
        Example:
            >>> cache = LRUCache(capacity=10)
            >>> cache.put(('mykey', 1.0), 'hello')
            >>> cache.get(('mykey', 1.0))
            'hello'
        """
        with self.lock:
            if key in self.cache:
                self.cache.move_to_end(key)
                self.hits += 1
                return self.cache[key]

            self.misses += 1
            return default
            
    def put(self, key: Tuple[Any, float], value: Any) -> None:
        """
        Put value in cache.
        
        Example:
            >>> cache = LRUCache(capacity=10)
            >>> cache.put(('mykey', 1.0), 'hello')
        """
        with self.lock:
            if key in self.cache:
                self.cache.move_to_end(key)
            self.cache[key] = value
            if len(self.cache) > self.capacity:
                self.cache.popitem(last=False)
    
    def invalidate(self, store_key: Any) -> None:
        """
        Invalidate all cache entries for a store key.
        
        Example:
            >>> cache = LRUCache(capacity=10)
            >>> cache.put(('mykey', 1.0), 'hello')
            >>> cache.invalidate('mykey')
            >>> cache.get(('mykey', 1.0)) is None
            True
        """
        with self.lock:
            keys_to_remove = [k for k in self.cache.keys() if k[0] == store_key]
            for k in keys_to_remove:
                del self.cache[k]
    
    def clear(self) -> None:
        """
        Clear entire cache.
        
        Example:
            >>> cache = LRUCache(capacity=10)
            >>> cache.put(('mykey', 1.0), 'hello')
            >>> cache.clear()
            >>> cache.get(('mykey', 1.0)) is None
            True
        """
        with self.lock:
            self.cache.clear()
            self.hits = 0
            self.misses = 0
    
    def get_stats(self) -> Dict[str, int]:
        """
        Get cache statistics.
        
        Example:
            >>> cache = LRUCache(capacity=10)
            >>> cache.put(('mykey', 1.0), 'hello')
            >>> cache.get(('mykey', 1.0))
            'hello'
            >>> cache.get_stats()
            {'hits': 1, 'misses': 0, 'size': 1, 'capacity': 10, 'hit_rate': 100.0}
        """
        with self.lock:
            total = self.hits + self.misses
            hit_rate = (self.hits / total * 100) if total > 0 else 0
            return {
                'hits': self.hits,
                'misses': self.misses,
                'size': len(self.cache),
                'capacity': self.capacity,
                'hit_rate': round(hit_rate, 2)
            }


# ============================================================================
# Read-Write Lock for Better Concurrency
# ============================================================================

class RWLock:
    """Read-Write lock allowing multiple readers or single writer."""
    
    def __init__(self) -> None:
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
    
    def __init__(self, chronomap: ChronoMap) -> None:
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
# Background TTL Cleanup Thread (NEW in v2.2.0)
# ============================================================================

class TTLCleanupThread:
    """Background thread for automatic TTL cleanup."""
    
    def __init__(self, chronomap_ref: weakref.ref, interval: float = 60.0) -> None:
        self.chronomap_ref = chronomap_ref
        self.interval = interval
        self.thread = None
        self.stop_event = threading.Event()
        self.cleaned_count = 0
    
    def start(self):
        """Start the cleanup thread."""
        if self.thread is not None and self.thread.is_alive():
            return
        
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self.thread.start()
        logger.debug("TTL cleanup thread started")
    
    def stop(self):
        """Stop the cleanup thread."""
        self.stop_event.set()
        if self.thread is not None:
            self.thread.join(timeout=2.0)
        logger.debug("TTL cleanup thread stopped")
    
    def _cleanup_loop(self):
        """Main cleanup loop."""
        while not self.stop_event.is_set():
            try:
                cm = self.chronomap_ref()
                if cm is None:
                    # ChronoMap was garbage collected
                    break
                
                cleaned = cm.clean_expired_keys()
                self.cleaned_count += cleaned
                
                if cleaned > 0:
                    logger.debug(f"Background cleanup removed {cleaned} expired keys")
                
                del cm  # Release reference
                
            except Exception as e:
                logger.error(f"Error in TTL cleanup thread: {e}")
            
            # Wait for next interval or stop event
            self.stop_event.wait(self.interval)


# ============================================================================
# Memory Monitor (NEW in v2.2.0)
# ============================================================================

class MemoryMonitor:
    """Monitor and enforce memory limits."""
    
    def __init__(self, max_memory_mb: Optional[float] = None) -> None:
        self.max_memory_bytes = int(max_memory_mb * 1024 * 1024) if max_memory_mb else None
        self.warning_threshold = 0.8  # Warn at 80%
        self.warned = False
    
    def estimate_size(self, obj: Any) -> int:
        """Estimate memory size of an object."""
        try:
            import sys
            return sys.getsizeof(obj)
        except:
            return 0
    
    def check_memory(self, store: Dict, ttl: Dict) -> None:
        """Check if memory limit is exceeded."""
        if self.max_memory_bytes is None:
            return
        
        # Estimate total size
        total_size = self.estimate_size(store) + self.estimate_size(ttl)
        
        # Check warning threshold
        if not self.warned and total_size > self.max_memory_bytes * self.warning_threshold:
            logger.warning(f"Memory usage at {total_size / 1024 / 1024:.2f}MB "
                         f"({total_size / self.max_memory_bytes * 100:.1f}% of limit)")
            self.warned = True
        
        # Check hard limit
        if total_size > self.max_memory_bytes:
            raise ChronoMapMemoryError(
                f"Memory limit exceeded: {total_size / 1024 / 1024:.2f}MB "
                f"(limit: {self.max_memory_bytes / 1024 / 1024:.2f}MB)"
            )
    
    def reset_warning(self):
        """Reset warning flag."""
        self.warned = False


# ============================================================================
# Main ChronoMap Class (Enhanced v2.2.0)
# ============================================================================

class ChronoMap:
    """
    Production-grade thread-safe, time-versioned key-value store.
    
    New Features in v2.2.0:
    - Auto-pruning with max_history
    - LRU cache for reads
    - Background TTL cleanup
    - Memory limits and monitoring
    - Batch optimizations
    - Enhanced compression
    
    Features from v2.1.0:
    - Read-write locks
    - Event hooks
    - Query filters and aggregations
    - Time travel with datetime strings
    - Context manager support
    - Async support
    """

    def __init__(
        self, 
        debug: bool = False, 
        use_rwlock: bool = True,
        max_history: Optional[int] = None,
        cache_size: int = 1000,
        enable_ttl_cleanup: bool = True,
        ttl_cleanup_interval: float = 60.0,
        max_memory_mb: Optional[float] = None
    ) -> None:
        """
        Initialize a ChronoMap.
        
        Args:
            debug: Enable debug logging if True.
            use_rwlock: Use read-write locks for better concurrency.
            max_history: Maximum versions per key (auto-prune if exceeded).
            cache_size: LRU cache size for read optimization.
            enable_ttl_cleanup: Enable background TTL cleanup thread.
            ttl_cleanup_interval: Seconds between TTL cleanup runs.
            max_memory_mb: Maximum memory usage in MB (None = no limit).
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
        
        # NEW in v2.2.0: Performance features
        self._max_history = max_history
        self._cache = LRUCache(capacity=cache_size) if cache_size > 0 else None
        self._memory_monitor = MemoryMonitor(max_memory_mb)
        
        # TTL cleanup thread
        self._ttl_cleanup_thread = None
        if enable_ttl_cleanup:
            self._ttl_cleanup_thread = TTLCleanupThread(
                weakref.ref(self),
                interval=ttl_cleanup_interval
            )
            self._ttl_cleanup_thread.start()
        
        # Event hooks
        self._change_callbacks: List[Callable] = []
        self._key_subscribers: Dict[Any, List[Callable]] = {}
        
        # Statistics
        self._stats = {
            'reads': 0,
            'writes': 0,
            'deletes': 0,
            'snapshots': 0,
            'auto_prunes': 0,
            'cache_hits': 0,
            'cache_misses': 0
        }

        if debug:
            logger.setLevel(logging.DEBUG)
            if not logger.handlers:
                handler = logging.StreamHandler()
                handler.setFormatter(
                    logging.Formatter("[ChronoMap] %(levelname)s: %(message)s")
                )
                logger.addHandler(handler)

    def __del__(self):
        """Cleanup on deletion."""
        if hasattr(self, '_ttl_cleanup_thread') and self._ttl_cleanup_thread:
            self._ttl_cleanup_thread.stop()

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
            
            # Invalidate cache
            if self._cache:
                self._cache.invalidate(key)
            
            logger.debug("EXPIRED key=%r", key)
            return True
        return False
    
    def _auto_prune(self, key: Any) -> None:
        """Auto-prune history if max_history exceeded."""
        if self._max_history is None:
            return
        
        versions = self._store.get(key, [])
        if len(versions) > self._max_history:
            removed = len(versions) - self._max_history
            self._store[key] = versions[-self._max_history:]
            self._stats['auto_prunes'] += 1
            
            # Invalidate cache
            if self._cache:
                self._cache.invalidate(key)
            
            logger.debug(f"AUTO_PRUNE key={key!r} removed {removed} old versions")
    
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
        """Trigger global change callbacks and subscribers for the changed key."""
        for callback in list(self._change_callbacks):
            try:
                callback(key, old_value, new_value, timestamp)
            except Exception as e:
                logger.error(f"Error in change callback: {e}")
        for callback in list(self._key_subscribers.get(key, [])):
            try:
                callback(old_value, new_value, timestamp)
            except Exception as e:
                logger.error(f"Error in key subscriber callback for {key!r}: {e}")

    def _get_unlocked(
        self,
        key: Any,
        timestamp: Optional[Union[float, str, datetime]] = None,
        default: Any = None,
        *,
        strict: bool = False
    ) -> Any:
        """Internal get that assumes caller already holds a read lock."""
        ts = self._parse_timestamp(timestamp) if timestamp is not None else self._current_time()

        if self._is_expired(key):
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

        return versions[idx][1]
    # ========================================================================
    # Event Hooks
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

    def subscribe(self, key: Any, callback: KeyChangeCallback) -> None:
        """
        Register a callback for changes to one specific key.

        Args:
            key: Key to watch.
            callback: Function(old_value, new_value, timestamp) -> None.

        Example:
            >>> cm.subscribe('app.config', lambda old, new, ts: print(new))
        """
        self._validate_key(key)
        if not callable(callback):
            raise ChronoMapTypeError("Subscriber callback must be callable")

        self._acquire_write()
        try:
            self._key_subscribers.setdefault(key, []).append(callback)
        finally:
            self._release_write()

    def unsubscribe(self, key: Any, callback: KeyChangeCallback) -> bool:
        """
        Remove a key-specific subscriber.

        Returns:
            True if the callback was registered for the key and removed.
        """
        self._validate_key(key)
        self._acquire_write()
        try:
            callbacks = self._key_subscribers.get(key)
            if not callbacks:
                return False
            try:
                callbacks.remove(callback)
            except ValueError:
                return False
            if not callbacks:
                del self._key_subscribers[key]
            return True
        finally:
            self._release_write()
    
    def remove_change_callback(self, callback: Callable) -> bool:
        """Remove a change callback. Returns True if found."""
        try:
            self._change_callbacks.remove(callback)
            return True
        except ValueError:
            return False

    # ========================================================================
    # Core Methods (Optimized in v2.2.0)
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
                times = [v[0] for v in versions]
                idx = bisect.bisect_right(times, ts)
                versions.insert(idx, (ts, value))

            # Set TTL if provided
            if ttl is not None:
                if ttl <= 0:
                    raise ChronoMapValueError(f"TTL must be positive, got {ttl}")
                self._ttl[key] = self._current_time() + ttl

            # Auto-prune if needed
            self._auto_prune(key)
            
            # Invalidate cache
            if self._cache:
                self._cache.invalidate(key)
            
            # Check memory limits
            self._memory_monitor.check_memory(self._store, self._ttl)

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
        Retrieve the value for a key at a given timestamp (with LRU caching).
        
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
        
        # Check expiry FIRST - before cache lookup
        # (We need to do a quick check without lock for expired keys)
        if self._is_expired(key):
            # Invalidate cache for expired key
            if self._cache:
                self._cache.invalidate(key)
            if strict:
                raise ChronoMapKeyError(key)
            return default
        
        # Check cache - use None as cache key when getting latest value
        if self._cache:
            cache_key = (key, None if timestamp is None else ts)
            cached = self._cache.get(cache_key, _CACHE_MISS)
            if cached is not _CACHE_MISS:
                self._stats['cache_hits'] += 1
                self._stats['reads'] += 1
                return cached
            self._stats['cache_misses'] += 1

        self._acquire_read()
        try:
            # Double-check expiry inside lock (in case it just expired)
            if self._is_expired(key):
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
            
            # Update cache - use None for latest value queries
            if self._cache:
                cache_key = (key, None if timestamp is None else ts)
                self._cache.put(cache_key, value)
            
            self._stats['reads'] += 1
            logger.debug("GET key=%r -> %r at ts=%f", key, value, ts)
            return value
        finally:
            self._release_read()

    def get_or_set(
        self,
        key: Any,
        default_factory: Callable[[], Any],
        ttl: Optional[float] = None
    ) -> Any:
        """
        Return the current value for a key, or create and store it if missing.

        The default factory is called only when the key is missing or expired.

        Args:
            key: The key to retrieve or initialize.
            default_factory: Zero-argument callable that produces the value.
            ttl: Optional time-to-live in seconds for newly stored values.

        Returns:
            The existing or newly stored value.

        Example:
            >>> cm = ChronoMap()
            >>> value = cm.get_or_set('config', lambda: load_config())
        """
        self._validate_key(key)
        if not callable(default_factory):
            raise ChronoMapTypeError("default_factory must be callable")
        if ttl is not None and ttl <= 0:
            raise ChronoMapValueError(f"TTL must be positive, got {ttl}")

        ts = self._current_time()
        self._validate_timestamp(ts)

        self._acquire_write()
        try:
            if self._is_expired(key):
                if key in self._store:
                    del self._store[key]
                if key in self._ttl:
                    del self._ttl[key]
                if self._cache:
                    self._cache.invalidate(key)

            versions = self._store.get(key, [])
            if versions:
                self._stats['reads'] += 1
                return versions[-1][1]

            value = default_factory()
            self._store[key] = [(ts, value)]

            if ttl is not None:
                self._ttl[key] = self._current_time() + ttl

            self._auto_prune(key)
            if self._cache:
                self._cache.invalidate(key)
            self._memory_monitor.check_memory(self._store, self._ttl)

            self._stats['writes'] += 1
            logger.debug("GET_OR_SET key=%r value=%r ttl=%s", key, value, ttl)
            self._trigger_change_callbacks(key, None, value, ts)
            return value
        finally:
            self._release_write()

    def get_or_default(
        self,
        key: Any,
        default: Any,
        ttl: Optional[float] = None
    ) -> Any:
        """
        Return the current value for a key, or store a default value if missing.

        If default is callable, it is treated as a zero-argument factory.
        """
        factory = default if callable(default) else lambda: default
        return self.get_or_set(key, factory, ttl=ttl)

    def delete(self, key: Any) -> bool:
        """Delete all history of a key."""
        self._acquire_write()
        try:
            existed = key in self._store
            if existed:
                del self._store[key]
                if key in self._ttl:
                    del self._ttl[key]
                
                # Invalidate cache
                if self._cache:
                    self._cache.invalidate(key)
                
                self._stats['deletes'] += 1
                logger.debug("DELETE key=%r", key)
            return existed
        finally:
            self._release_write()

    # ========================================================================
    # Query & Analytics
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
                value = self._get_unlocked(key, timestamp=ts)
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
                    val = self._get_unlocked(key, timestamp=ts)
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
    # History Management
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
            
            # Invalidate cache
            if self._cache and removed > 0:
                self._cache.invalidate(key)
            
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
    # Batch Operations (Optimized in v2.2.0)
    # ========================================================================

    def put_many(
        self,
        items: Dict[Any, Any],
        timestamp: Optional[Union[float, str, datetime]] = None,
        ttl: Optional[float] = None
    ) -> None:
        """Insert multiple key-value pairs at once (optimized batch operation)."""
        # Acquire lock once for entire batch
        ts = self._parse_timestamp(timestamp) if timestamp is not None else self._current_time()
        self._validate_timestamp(ts)
        
        self._acquire_write()
        try:
            for key, value in items.items():
                self._validate_key(key)
                
                # Get old value for callback
                old_value = None
                if key in self._store and self._store[key]:
                    old_value = self._store[key][-1][1]
                
                if key not in self._store:
                    self._store[key] = []
                versions = self._store[key]
                
                if not versions or ts >= versions[-1][0]:
                    versions.append((ts, value))
                else:
                    times = [v[0] for v in versions]
                    idx = bisect.bisect_right(times, ts)
                    versions.insert(idx, (ts, value))
                
                if ttl is not None:
                    if ttl <= 0:
                        raise ChronoMapValueError(f"TTL must be positive, got {ttl}")
                    self._ttl[key] = self._current_time() + ttl
                
                # Auto-prune
                self._auto_prune(key)
                
                # Invalidate cache
                if self._cache:
                    self._cache.invalidate(key)
                
                # Trigger callbacks
                self._trigger_change_callbacks(key, old_value, value, ts)
            
            # Check memory once after all inserts
            self._memory_monitor.check_memory(self._store, self._ttl)
            
            self._stats['writes'] += len(items)
            logger.debug("PUT_MANY %d items", len(items))
        finally:
            self._release_write()

    def delete_many(self, keys: List[Any]) -> int:
        """Delete multiple keys at once (optimized batch operation)."""
        self._acquire_write()
        try:
            count = 0
            for key in keys:
                if key in self._store:
                    del self._store[key]
                    if key in self._ttl:
                        del self._ttl[key]
                    
                    # Invalidate cache
                    if self._cache:
                        self._cache.invalidate(key)
                    
                    count += 1
                    self._stats['deletes'] += 1
            
            logger.debug("DELETE_MANY %d/%d keys", count, len(keys))
            return count
        finally:
            self._release_write()

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
            # Check expiry - just check, don't clean
            if self._is_expired(key):
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
                if self._get_unlocked(key, timestamp=ts) == value:
                    keys.append(key)
            logger.debug("GET_KEYS_BY_VALUE found %d keys", len(keys))
            return keys
        finally:
            self._release_read()

    # ========================================================================
    # Snapshot, Diff, Rollback
    # ========================================================================

    def snapshot(self) -> ChronoMap:
        """Return a deep-copy snapshot of the current map."""
        self._acquire_read()
        try:
            snap = ChronoMap(
                debug=self._debug, 
                use_rwlock=self._use_rwlock,
                max_history=self._max_history,
                cache_size=0,  # Snapshots don't need cache
                enable_ttl_cleanup=False  # No background thread for snapshots
            )
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
            
            # Clear cache after rollback
            if self._cache:
                self._cache.clear()
            
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
                        # Use internal put logic without re-locking
                        if key not in self._store:
                            self._store[key] = []
                        target_versions = self._store[key]
                        
                        if not target_versions or ts >= target_versions[-1][0]:
                            target_versions.append((ts, val))
                        else:
                            times = [v[0] for v in versions]
                            idx = bisect.bisect_right(times, ts)
                            versions.insert(idx, (ts, value))
                        
                        self._auto_prune(key)
                
                for key, expiry in other._ttl.items():
                    if key not in self._ttl or expiry > self._ttl[key]:
                        self._ttl[key] = expiry
            else:  # overwrite
                for key, versions in other._store.items():
                    self._store[key] = deepcopy(versions)
                for key, expiry in other._ttl.items():
                    self._ttl[key] = expiry
            
            # Clear cache after merge
            if self._cache:
                self._cache.clear()

            logger.debug("MERGE completed with strategy=%s", strategy)
        finally:
            self._release_write()

    # ========================================================================
    # Utilities
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
            # Check expiry - just check, don't clean
            if self._is_expired(key):
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
            
            # Clear cache
            if self._cache:
                self._cache.clear()
            
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
                
                # Invalidate cache
                if self._cache:
                    self._cache.invalidate(key)
                
                count += 1
            
            logger.debug("CLEAN_EXPIRED removed %d keys", count)
            return count
        finally:
            self._release_write()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive operation statistics."""
        stats = self._stats.copy()
        
        # Add cache stats if available
        if self._cache:
            cache_stats = self._cache.get_stats()
            stats.update({
                'cache_hits': cache_stats['hits'],
                'cache_misses': cache_stats['misses'],
                'cache_size': cache_stats['size'],
                'cache_hit_rate': cache_stats['hit_rate']
            })
        
        # Add TTL cleanup stats
        if self._ttl_cleanup_thread:
            stats['ttl_cleanup_count'] = self._ttl_cleanup_thread.cleaned_count
        
        # Add size stats
        stats['total_keys'] = len(self)
        stats['total_versions'] = sum(len(v) for v in self._store.values())
        stats['expired_keys'] = sum(1 for k in self._ttl if self._is_expired(k))
        
        return stats
    
    def reset_stats(self) -> None:
        """Reset operation statistics."""
        self._stats = {
            'reads': 0,
            'writes': 0,
            'deletes': 0,
            'snapshots': 0,
            'auto_prunes': 0,
            'cache_hits': 0,
            'cache_misses': 0
        }
        
        if self._cache:
            self._cache.clear()
        
        if self._ttl_cleanup_thread:
            self._ttl_cleanup_thread.cleaned_count = 0

    # ========================================================================
    # Export
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
            # Check expiry - just check, don't clean
            if self._is_expired(key):
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
    # Persistence (Enhanced with Multiple Compression Algorithms)
    # ========================================================================

    def to_dict(self, compress: Union[bool, str] = False) -> Union[Dict[str, Any], bytes]:
        """
        Serialize to dictionary (compatible with JSON/pickle).
        
        Args:
            compress: Compression method: False, 'zlib', 'gzip', 'bz2', 'lzma'
        
        Returns:
            Dictionary or compressed bytes
        """
        self._acquire_read()
        try:
            data = {
                'store': deepcopy(self._store),
                'ttl': deepcopy(self._ttl),
                'snapshot_time': self._snapshot_time,
                'version': '2.2.0',
                'max_history': self._max_history
            }
            
            if compress:
                import pickle
                pickled = pickle.dumps(data)
                
                if compress == 'zlib' or compress is True:
                    compressed = zlib.compress(pickled, level=6)
                    method = 'zlib'
                elif compress == 'gzip':
                    compressed = gzip.compress(pickled, compresslevel=6)
                    method = 'gzip'
                elif compress == 'bz2':
                    compressed = bz2.compress(pickled, compresslevel=6)
                    method = 'bz2'
                elif compress == 'lzma':
                    compressed = lzma.compress(pickled, preset=6)
                    method = 'lzma'
                else:
                    raise ChronoMapValueError(f"Unknown compression method: {compress}")
                
                logger.debug("COMPRESS (%s): %d -> %d bytes (%.1f%%)", 
                           method, len(pickled), len(compressed), 
                           100 * len(compressed) / len(pickled))
                
                # Prepend compression method marker
                return method.encode() + b'|' + compressed
            
            return data
        finally:
            self._release_read()

    @classmethod
    def from_dict(cls, data: Union[Dict[str, Any], bytes], debug: bool = False, 
                  use_rwlock: bool = True, **kwargs) -> ChronoMap:
        """
        Reconstruct ChronoMap from dictionary or compressed bytes.
        
        Args:
            data: Dictionary from to_dict() or compressed bytes
            debug: Enable debug mode
            use_rwlock: Use read-write locks
            **kwargs: Additional arguments for ChronoMap constructor
        
        Returns:
            New ChronoMap instance
        """
        if isinstance(data, bytes):
            # Auto-detect compression method
            if b'|' in data[:20]:
                method_bytes, compressed = data.split(b'|', 1)
                method = method_bytes.decode()
                
                if method == 'zlib':
                    decompressed = zlib.decompress(compressed)
                elif method == 'gzip':
                    decompressed = gzip.decompress(compressed)
                elif method == 'bz2':
                    decompressed = bz2.decompress(compressed)
                elif method == 'lzma':
                    decompressed = lzma.decompress(compressed)
                else:
                    # Fallback: try all methods
                    try:
                        decompressed = zlib.decompress(data)
                    except:
                        try:
                            decompressed = gzip.decompress(data)
                        except:
                            try:
                                decompressed = bz2.decompress(data)
                            except:
                                decompressed = lzma.decompress(data)
            else:
                # Old format without method marker
                try:
                    decompressed = zlib.decompress(data)
                except:
                    decompressed = data
            
            import pickle
            data = pickle.loads(decompressed)
        
        max_history = data.get('max_history')
        
        instance = cls(
            debug=debug, 
            use_rwlock=use_rwlock,
            max_history=max_history,
            **kwargs
        )
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
            'version': data.get('version', '2.2.0'),
            'max_history': data.get('max_history')
        }
        
        with open(path, 'w') as f:
            json.dump(json_data, f, indent=2)
        logger.debug("SAVE_JSON to %s", file_path)

    @classmethod
    def load_json(cls, file_path: Union[str, Path], debug: bool = False, 
                  use_rwlock: bool = True, **kwargs) -> ChronoMap:
        """Load ChronoMap from JSON file."""
        path = Path(file_path)
        with open(path, 'r') as f:
            json_data = json.load(f)
        
        data = {
            'store': json_data['store'],
            'ttl': json_data['ttl'],
            'snapshot_time': json_data.get('snapshot_time'),
            'version': json_data.get('version', '2.0.0'),
            'max_history': json_data.get('max_history')
        }
        
        logger.debug("LOAD_JSON from %s", file_path)
        return cls.from_dict(data, debug=debug, use_rwlock=use_rwlock, **kwargs)

    def save_pickle(self, file_path: Union[str, Path], compress: Union[bool, str] = False) -> None:
        """
        Save ChronoMap to pickle file.
        
        Args:
            file_path: Path to save pickle file
            compress: Compression method: False, 'zlib', 'gzip', 'bz2', 'lzma'
        """
        path = Path(file_path)
        data = self.to_dict(compress=compress)
        
        with open(path, 'wb') as f:
            if isinstance(data, bytes):
                f.write(data)  # Already compressed
            else:
                pickle.dump(data, f)
        
        logger.debug("SAVE_PICKLE to %s (compressed=%s)", file_path, compress)

    @classmethod
    def load_pickle(cls, file_path: Union[str, Path], debug: bool = False,
                    use_rwlock: bool = True, **kwargs) -> ChronoMap:
        """
        Load ChronoMap from pickle file (auto-detects compression).
        
        Args:
            file_path: Path to pickle file
            debug: Enable debug mode
            use_rwlock: Use read-write locks
            **kwargs: Additional arguments for ChronoMap constructor
        
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
            # It's compressed, let from_dict handle it
            data = data_bytes
        
        logger.debug("LOAD_PICKLE from %s", file_path)
        return cls.from_dict(data, debug=debug, use_rwlock=use_rwlock, **kwargs)


# ============================================================================
# Async ChronoMap (Enhanced in v2.2.0)
# ============================================================================

class AsyncChronoMap:
    """
    Async version of ChronoMap for use with asyncio.
    
    Enhanced in v2.2.0 with auto-pruning and better performance.
    
    Example:
        >>> async def main():
        ...     cm = AsyncChronoMap(max_history=1000)
        ...     await cm.put('key', 'value')
        ...     value = await cm.get('key')
        ...     print(value)
    """
    
    def __init__(self, debug: bool = False, max_history: Optional[int] = None) -> None:
        """Initialize AsyncChronoMap."""
        self._store: Dict[Any, List[Tuple[float, Any]]] = {}
        self._ttl: Dict[Any, float] = {}
        self._lock = asyncio.Lock()
        self._snapshot_time: Optional[float] = None
        self._debug = debug
        self._max_history = max_history
        self._change_callbacks: List[Callable] = []
        self._key_subscribers: Dict[Any, List[Callable]] = {}
        self._stats = {
            'reads': 0,
            'writes': 0,
            'deletes': 0,
            'snapshots': 0,
            'auto_prunes': 0
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
    
    def _auto_prune(self, key: Any) -> None:
        """Auto-prune history if max_history exceeded."""
        if self._max_history is None:
            return
        
        versions = self._store.get(key, [])
        if len(versions) > self._max_history:
            removed = len(versions) - self._max_history
            self._store[key] = versions[-self._max_history:]
            self._stats['auto_prunes'] += 1
            logger.debug(f"AUTO_PRUNE key={key!r} removed {removed} old versions")
    
    async def put(
        self,
        key: Any,
        value: Any,
        timestamp: Optional[Union[float, str, datetime]] = None,
        ttl: Optional[float] = None
    ) -> None:
        """Store a key-value pair asynchronously."""
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
                times = [v[0] for v in versions]
                idx = bisect.bisect_right(times, ts)
                versions.insert(idx, (ts, value))
            
            if ttl is not None:
                if ttl <= 0:
                    raise ChronoMapValueError(f"TTL must be positive, got {ttl}")
                self._ttl[key] = self._current_time() + ttl
            
            # Auto-prune
            self._auto_prune(key)
            
            self._stats['writes'] += 1
            
            # Trigger callbacks
            callbacks = list(self._change_callbacks)
            key_callbacks = list(self._key_subscribers.get(key, []))
            for callback in callbacks:
                if asyncio.iscoroutinefunction(callback):
                    await callback(key, old_value, value, ts)
                else:
                    callback(key, old_value, value, ts)
            for callback in key_callbacks:
                if asyncio.iscoroutinefunction(callback):
                    await callback(old_value, value, ts)
                else:
                    callback(old_value, value, ts)

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

    async def get_or_set(
        self,
        key: Any,
        default_factory: Callable[[], Any],
        ttl: Optional[float] = None
    ) -> Any:
        """Return the current value for a key, or create and store it if missing."""
        self._validate_key(key)
        if not callable(default_factory):
            raise ChronoMapTypeError("default_factory must be callable")
        if ttl is not None and ttl <= 0:
            raise ChronoMapValueError(f"TTL must be positive, got {ttl}")

        ts = self._current_time()

        async with self._lock:
            if self._is_expired(key):
                if key in self._store:
                    del self._store[key]
                if key in self._ttl:
                    del self._ttl[key]

            versions = self._store.get(key, [])
            if versions:
                self._stats['reads'] += 1
                return versions[-1][1]

            value = default_factory()
            if asyncio.iscoroutine(value):
                value = await value

            self._store[key] = [(ts, value)]

            if ttl is not None:
                self._ttl[key] = self._current_time() + ttl

            self._auto_prune(key)
            self._stats['writes'] += 1

            callbacks = list(self._change_callbacks)
            key_callbacks = list(self._key_subscribers.get(key, []))
            for callback in callbacks:
                if asyncio.iscoroutinefunction(callback):
                    await callback(key, None, value, ts)
                else:
                    callback(key, None, value, ts)
            for callback in key_callbacks:
                if asyncio.iscoroutinefunction(callback):
                    await callback(None, value, ts)
                else:
                    callback(None, value, ts)

            return value

    async def get_or_default(
        self,
        key: Any,
        default: Any,
        ttl: Optional[float] = None
    ) -> Any:
        """Return the current value for a key, or store a default value if missing."""
        factory = default if callable(default) else lambda: default
        return await self.get_or_set(key, factory, ttl=ttl)
    
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
            snap = AsyncChronoMap(debug=self._debug, max_history=self._max_history)
            snap._store = deepcopy(self._store)
            snap._ttl = deepcopy(self._ttl)
            snap._snapshot_time = self._current_time()
            self._stats['snapshots'] += 1
            return snap
    
    def on_change(self, callback: ChangeCallback) -> None:
        """Register change callback (can be sync or async)."""
        self._change_callbacks.append(callback)

    def subscribe(self, key: Any, callback: KeyChangeCallback) -> None:
        """Register a sync or async callback for one specific key."""
        self._validate_key(key)
        if not callable(callback):
            raise ChronoMapTypeError("Subscriber callback must be callable")
        self._key_subscribers.setdefault(key, []).append(callback)

    def unsubscribe(self, key: Any, callback: KeyChangeCallback) -> bool:
        """Remove a key-specific callback. Returns True if found."""
        self._validate_key(key)
        callbacks = self._key_subscribers.get(key)
        if not callbacks:
            return False
        try:
            callbacks.remove(callback)
        except ValueError:
            return False
        if not callbacks:
            del self._key_subscribers[key]
        return True
    
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

__version__ = "2.2.0"
__all__ = [
    "ChronoMap",
    "AsyncChronoMap",
    "ChronoMapError",
    "ChronoMapKeyError",
    "ChronoMapTypeError",
    "ChronoMapValueError",
    "ChronoMapMemoryError",
    "SnapshotContext",
    "RWLock",
    "LRUCache",
]
