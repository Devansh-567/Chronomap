"""Core ChronoMap implementation."""

from bisect import bisect_right
from copy import deepcopy
from datetime import datetime
import threading
from typing import Any, Optional, List, Tuple, Dict, Set

class ChronoMap:
    """A thread-safe, time-versioned key-value store."""
    
    def __init__(self):
        self._store: Dict[Any, List[Tuple[float, Any]]] = {}
        self._lock = threading.RLock()
        self._snapshot_time: Optional[float] = None
    
    def _current_time(self) -> float:
        return datetime.utcnow().timestamp()
    
    def put(self, key: Any, value: Any, timestamp: Optional[float] = None) -> None:
        with self._lock:
            timestamp = timestamp or self._current_time()
            if key not in self._store:
                self._store[key] = []
            if self._store[key] and self._store[key][-1][0] > timestamp:
                self._store[key].append((timestamp, value))
                self._store[key].sort(key=lambda x: x[0])
            else:
                self._store[key].append((timestamp, value))
    
    def get(self, key: Any, timestamp: Optional[float] = None) -> Optional[Any]:
        with self._lock:
            if key not in self._store or not self._store[key]:
                return None
            versions = self._store[key]
            timestamp = timestamp or self._current_time()
            times = [entry[0] for entry in versions]
            index = bisect_right(times, timestamp) - 1
            return versions[index][1] if index >= 0 else None
    
    def snapshot(self) -> 'ChronoMap':
        with self._lock:
            snap = ChronoMap()
            snap._store = deepcopy(self._store)
            snap._snapshot_time = self._current_time()
            return snap
    
    def diff(self, other_map: 'ChronoMap') -> Set[Any]:
        with self._lock:
            changed = set()
            all_keys = set(self._store.keys()) | set(other_map._store.keys())
            for key in all_keys:
                current_val = self.get(key)
                snapshot_val = other_map.get(key, other_map.snapshot_time)
                if current_val != snapshot_val:
                    changed.add(key)
            return changed
    
    def latest(self) -> Dict[Any, Any]:
        with self._lock:
            return {key: versions[-1][1] for key, versions in self._store.items() if versions}
    
    def history(self, key: Any) -> List[Tuple[float, Any]]:
        with self._lock:
            return list(self._store.get(key, []))
    
    @property
    def snapshot_time(self) -> Optional[float]:
        return self._snapshot_time
    
    def __repr__(self) -> str:
        return f"ChronoMap(latest={self.latest()})"
    
    def __len__(self) -> int:
        with self._lock:
            return len(self._store)
    
    def __contains__(self, key: Any) -> bool:
        with self._lock:
            return key in self._store and len(self._store[key]) > 0
