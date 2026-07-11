"""Exception hierarchy for ChronoMap.

Kept in their own module so other packages (CLI, examples, tests) can
import just the errors without pulling in the whole store implementation.
"""

from __future__ import annotations


class ChronoMapError(Exception):
    """Base class for every error ChronoMap raises."""


class ChronoMapKeyError(ChronoMapError, KeyError):
    """A key was missing and the call was made with strict=True."""


class ChronoMapTypeError(ChronoMapError, TypeError):
    """Something was the wrong type (an unhashable key, a bad timestamp, ...)."""


class ChronoMapValueError(ChronoMapError, ValueError):
    """A value was the right type but not valid (e.g. a negative TTL)."""


class ChronoMapMemoryError(ChronoMapError, MemoryError):
    """Raised when a configured max_memory_mb limit is exceeded."""


__all__ = [
    "ChronoMapError",
    "ChronoMapKeyError",
    "ChronoMapTypeError",
    "ChronoMapValueError",
    "ChronoMapMemoryError",
]
