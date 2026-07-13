# Copyright (c) 2026 Devansh Singh, ChronoMap contributors
# SPDX-License-Identifier: MIT


"""Background daemon thread that periodically clears expired keys.

Holds a weakref to the owning ChronoMap so it never keeps the map alive
just because the cleanup thread is still running.
"""

from __future__ import annotations

import logging
import threading
import weakref

logger = logging.getLogger(__name__)


class TTLCleanupThread:
    """Runs `chronomap.clean_expired_keys()` on an interval, in the background."""

    def __init__(self, chronomap_ref: "weakref.ref", interval: float = 60.0) -> None:
        self.chronomap_ref = chronomap_ref
        self.interval = interval
        self.thread: threading.Thread | None = None
        self.stop_event = threading.Event()
        self.cleaned_count = 0

    def start(self) -> None:
        if self.thread is not None and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self.thread.start()
        logger.debug("TTL cleanup thread started")

    def stop(self) -> None:
        self.stop_event.set()
        # __del__ on the owning ChronoMap can run *on this background thread*:
        # _cleanup_loop briefly holds the only strong reference to the map
        # (via chronomap_ref()), so if the main thread drops its reference
        # at just the wrong moment, `del cm` below is what takes the
        # refcount to zero — on this thread. That triggers ChronoMap.__del__,
        # which calls stop(), which would otherwise try to join() the
        # thread it's currently running on and raise RuntimeError. Skip the
        # join in that case; the loop is already exiting on its own since
        # stop_event is set.
        if self.thread is not None and self.thread is not threading.current_thread():
            self.thread.join(timeout=2.0)
        logger.debug("TTL cleanup thread stopped")

    def _cleanup_loop(self) -> None:
        while not self.stop_event.is_set():
            try:
                cm = self.chronomap_ref()
                if cm is None:
                    break  # owning ChronoMap was garbage collected

                cleaned = cm.clean_expired_keys()
                self.cleaned_count += cleaned
                if cleaned:
                    logger.debug("Background cleanup removed %d expired keys", cleaned)

                del cm
            except Exception:
                logger.exception("Error in TTL cleanup thread")

            self.stop_event.wait(self.interval)


__all__ = ["TTLCleanupThread"]
