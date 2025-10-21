"""
ChronoMap package initialization.
"""

__version__ = "2.1.0"

from .chronomap import (
    ChronoMap,
    AsyncChronoMap,
    ChronoMapError,
    ChronoMapKeyError,
    ChronoMapTypeError,
    ChronoMapValueError,
    SnapshotContext,
    RWLock,
)