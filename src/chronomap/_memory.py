# Copyright (c) 2026 Devansh Singh, ChronoMap contributors
# SPDX-License-Identifier: MIT


"""Optional memory-usage guardrail.

This is a rough estimate (sys.getsizeof on the top-level containers), not
a real memory profiler. It's good enough to catch "someone forgot to set
max_history and now there are 2GB of stale versions in RAM," which is the
actual failure mode this was written to catch.
"""

from __future__ import annotations

import logging
import sys
from typing import Any, Dict, Optional

from .exceptions import ChronoMapMemoryError

logger = logging.getLogger(__name__)


class MemoryMonitor:
    """Tracks approximate memory usage and enforces an optional hard limit."""

    def __init__(self, max_memory_mb: Optional[float] = None) -> None:
        self.max_memory_bytes = int(max_memory_mb * 1024 * 1024) if max_memory_mb else None
        self.warning_threshold = 0.8
        self.warned = False

    @staticmethod
    def estimate_size(obj: Any) -> int:
        try:
            return sys.getsizeof(obj)
        except TypeError:
            return 0

    def check_memory(self, store: Dict, ttl: Dict) -> None:
        if self.max_memory_bytes is None:
            return

        total_size = self.estimate_size(store) + self.estimate_size(ttl)

        if not self.warned and total_size > self.max_memory_bytes * self.warning_threshold:
            logger.warning(
                "Memory usage at %.2fMB (%.1f%% of limit)",
                total_size / 1024 / 1024,
                total_size / self.max_memory_bytes * 100,
            )
            self.warned = True

        if total_size > self.max_memory_bytes:
            raise ChronoMapMemoryError(
                f"Memory limit exceeded: {total_size / 1024 / 1024:.2f}MB "
                f"(limit: {self.max_memory_bytes / 1024 / 1024:.2f}MB)"
            )

    def reset_warning(self) -> None:
        self.warned = False


__all__ = ["MemoryMonitor"]
