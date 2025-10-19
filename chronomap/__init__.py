"""
ChronoMap - A time-versioned dictionary implementation for Python.

ChronoMap provides a thread-safe, time-versioned key-value store that maintains
a complete history of all changes, enabling temporal queries and snapshots.
"""

from .chronomap import ChronoMap

__version__ = "0.1.0"
__all__ = ["ChronoMap"]
