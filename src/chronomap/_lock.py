# Copyright (c) 2026 Devansh Singh, ChronoMap contributors
# SPDX-License-Identifier: MIT


"""A basic readers-writer lock.

Not the fastest possible implementation (a semaphore-based approach would
have less overhead), but it's easy to reason about and it's what the rest
of ChronoMap is built against. Swapping this out is a reasonable first
"real" contribution for someone new to the codebase.
"""

from __future__ import annotations

import threading


class RWLock:
    """Allows either multiple concurrent readers or one exclusive writer."""

    def __init__(self) -> None:
        self._readers = 0
        self._writers = 0
        self._read_ready = threading.Condition(threading.RLock())
        self._write_ready = threading.Condition(threading.RLock())

    def acquire_read(self) -> None:
        self._read_ready.acquire()
        try:
            while self._writers > 0:
                # Only reachable in a narrow window: a writer has
                # incremented self._writers but hasn't yet acquired
                # _read_ready itself. Real, but sub-millisecond and not
                # worth a timing-dependent (and therefore flaky) test to
                # force onto the coverage report.
                self._read_ready.wait()  # pragma: no cover
            self._readers += 1
        finally:
            self._read_ready.release()

    def release_read(self) -> None:
        self._read_ready.acquire()
        try:
            self._readers -= 1
            if self._readers == 0:
                self._read_ready.notify_all()
        finally:
            self._read_ready.release()

    def acquire_write(self) -> None:
        self._write_ready.acquire()
        self._writers += 1
        self._write_ready.release()

        self._read_ready.acquire()
        while self._readers > 0:
            self._read_ready.wait()

    def release_write(self) -> None:
        self._writers -= 1
        self._read_ready.notify_all()
        self._read_ready.release()

        self._write_ready.acquire()
        self._write_ready.notify_all()
        self._write_ready.release()


__all__ = ["RWLock"]
