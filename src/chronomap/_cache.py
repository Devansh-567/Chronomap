"""Small thread-safe LRU cache used internally by ChronoMap for reads.

This isn't meant to be a general-purpose cache — it's shaped specifically
around ChronoMap's cache key of (store_key, timestamp_or_None).
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from typing import Any, Dict, Tuple


class LRUCache:
    """Thread-safe LRU cache for frequently accessed keys."""

    def __init__(self, capacity: int = 1000) -> None:
        self.capacity = capacity
        self.cache: "OrderedDict[Tuple[Any, Any], Any]" = OrderedDict()
        self.lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def get(self, key: Tuple[Any, float], default: Any = None) -> Any:
        with self.lock:
            if key in self.cache:
                self.cache.move_to_end(key)
                self.hits += 1
                return self.cache[key]
            self.misses += 1
            return default

    def put(self, key: Tuple[Any, float], value: Any) -> None:
        with self.lock:
            if key in self.cache:
                self.cache.move_to_end(key)
            self.cache[key] = value
            if len(self.cache) > self.capacity:
                self.cache.popitem(last=False)

    def invalidate(self, store_key: Any) -> None:
        """Drop every cached entry belonging to a given store key."""
        with self.lock:
            stale = [k for k in self.cache if k[0] == store_key]
            for k in stale:
                del self.cache[k]

    def clear(self) -> None:
        with self.lock:
            self.cache.clear()
            self.hits = 0
            self.misses = 0

    def get_stats(self) -> Dict[str, Any]:
        with self.lock:
            total = self.hits + self.misses
            hit_rate = (self.hits / total * 100) if total else 0.0
            return {
                "hits": self.hits,
                "misses": self.misses,
                "size": len(self.cache),
                "capacity": self.capacity,
                "hit_rate": round(hit_rate, 2),
            }


__all__ = ["LRUCache"]
