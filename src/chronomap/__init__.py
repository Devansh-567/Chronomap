# Copyright (c) 2026 Devansh Singh, ChronoMap contributors
# SPDX-License-Identifier: MIT


"""ChronoMap: a thread-safe, time-versioned key-value store for Python.

    from chronomap import ChronoMap

    cm = ChronoMap()
    cm['config'] = {'debug': True}
    cm['config'] = {'debug': False}

    cm.history('config')          # every version, in order
    cm.get('config', timestamp=…) # value as of a given time

See the README for the full walkthrough and the docs/ directory for
API reference.
"""

from .asynchronous import AsyncChronoMap
from .core import ChronoMap
from ._cache import LRUCache
from ._lock import RWLock
from ._snapshot import SnapshotContext
from ._version import __version__
from .exceptions import (
    ChronoMapError,
    ChronoMapKeyError,
    ChronoMapMemoryError,
    ChronoMapTypeError,
    ChronoMapValueError,
)

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
    "__version__",
]
