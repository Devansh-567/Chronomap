# Copyright (c) 2026 Devansh Singh, ChronoMap contributors
# SPDX-License-Identifier: MIT


"""Crash-safe write-ahead journal and checkpoint helpers.

The journal is a sequence of length-prefixed, CRC-checked pickle records.
A torn record at the end of the file is discarded during recovery; a complete
record with a bad checksum is treated as corruption. Records carry a
monotonically increasing sequence number so a checkpoint can safely coexist
with the tail of an older journal after a crash.

Pickle can execute code while loading. Journals and checkpoints are trusted
local state files, not a format for untrusted input.
"""

from __future__ import annotations

import os
import pickle
import struct
import tempfile
import threading
import zlib
from pathlib import Path
from typing import IO, Any, Dict, List, Optional, Tuple, Union

from .exceptions import ChronoMapError

MAGIC = b"CMWAL1\n"
CHECKPOINT_MAGIC = b"CMCHK1\n"
MAX_RECORD_BYTES = 1 << 30
_FRAME = struct.Struct(">II")

PathLike = Union[str, os.PathLike]


class JournalError(ChronoMapError):
    """Base class for journal read/write failures."""


class JournalCorruptionError(JournalError):
    """The journal or checkpoint is malformed or fails its checksum."""


def _fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(str(path), os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError:
        pass


def write_checkpoint(path: PathLike, state: Dict[str, Any]) -> None:
    """Atomically write a checkpoint state dictionary."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=destination.name + ".",
        suffix=".tmp",
        dir=str(destination.parent),
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(CHECKPOINT_MAGIC)
            pickle.dump(state, handle, protocol=4)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, destination)
        _fsync_directory(destination.parent)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise


def read_checkpoint(path: PathLike) -> Dict[str, Any]:
    """Read a checkpoint written by :func:`write_checkpoint`."""
    raw = Path(path).read_bytes()
    if not raw.startswith(CHECKPOINT_MAGIC):
        raise JournalCorruptionError("Checkpoint header is missing or invalid")
    try:
        state = pickle.loads(raw[len(CHECKPOINT_MAGIC) :])
    except Exception as exc:
        raise JournalCorruptionError("Could not decode checkpoint payload") from exc
    if not isinstance(state, dict):
        raise JournalCorruptionError("Checkpoint payload must be a mapping")
    return state


class Journal:
    """Append-only, checksummed journal."""

    def __init__(self, path: PathLike, *, sync: bool = True) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._sync = sync
        self._lock = threading.RLock()
        self._closed = False
        self._sequence = 0
        self._records: List[Tuple[int, str, Dict[str, Any]]] = []
        self._file: Optional[IO[bytes]] = None
        self._open()

    @property
    def sequence(self) -> int:
        return self._sequence

    @property
    def records(self) -> Tuple[Tuple[int, str, Dict[str, Any]], ...]:
        """Records loaded during the last open, in sequence order."""
        return tuple(self._records)

    @property
    def size(self) -> int:
        try:
            return self.path.stat().st_size
        except OSError:
            return 0

    def _open(self) -> None:
        created = not self.path.exists() or self.path.stat().st_size == 0
        if created:
            with open(self.path, "wb") as writer:
                writer.write(MAGIC)
                writer.flush()
                os.fsync(writer.fileno())
            _fsync_directory(self.path.parent)
        handle = open(self.path, "r+b")
        try:
            header = handle.read(len(MAGIC))
            if header != MAGIC:
                raise JournalCorruptionError("Journal header is missing or invalid")
            valid_end = len(MAGIC)
            last_sequence = 0
            while True:
                record_start = handle.tell()
                frame = handle.read(_FRAME.size)
                if not frame:
                    break
                if len(frame) < _FRAME.size:
                    break
                length, checksum = _FRAME.unpack(frame)
                if length <= 0 or length > MAX_RECORD_BYTES:
                    raise JournalCorruptionError(f"Invalid journal record length: {length}")
                payload = handle.read(length)
                if len(payload) < length:
                    break
                if zlib.crc32(payload) & 0xFFFFFFFF != checksum:
                    raise JournalCorruptionError(f"Journal checksum failed at offset {record_start}")
                try:
                    record = pickle.loads(payload)
                except Exception as exc:
                    raise JournalCorruptionError(
                        f"Could not decode journal record at offset {record_start}"
                    ) from exc
                if (
                    not isinstance(record, tuple)
                    or len(record) != 3
                    or isinstance(record[0], bool)
                    or not isinstance(record[0], int)
                    or not isinstance(record[1], str)
                    or not isinstance(record[2], dict)
                ):
                    raise JournalCorruptionError(f"Invalid journal record at offset {record_start}")
                sequence, operation, data = record
                if sequence <= last_sequence:
                    raise JournalCorruptionError("Journal sequence numbers are not increasing")
                self._records.append((sequence, operation, data))
                last_sequence = sequence
                valid_end = handle.tell()

            size = handle.seek(0, os.SEEK_END)
            if size > valid_end:
                handle.truncate(valid_end)
            handle.seek(0, os.SEEK_END)
            self._sequence = last_sequence
            self._file = handle
        except BaseException:
            handle.close()
            raise

    def advance_to(self, sequence: int) -> None:
        """Ensure future records use sequence numbers above ``sequence``."""
        with self._lock:
            self._sequence = max(self._sequence, sequence)

    def clear_records(self) -> None:
        """Release records loaded during the last open."""
        with self._lock:
            self._records.clear()

    def append(self, operation: str, data: Dict[str, Any]) -> int:
        if not isinstance(operation, str) or not operation:
            raise JournalError("Journal operations must be non-empty strings")
        if not isinstance(data, dict):
            raise JournalError("Journal record data must be a mapping")
        with self._lock:
            if self._closed or self._file is None:
                raise JournalError("Journal is closed")
            sequence = self._sequence + 1
            try:
                payload = pickle.dumps((sequence, operation, data), protocol=4)
            except Exception as exc:
                raise JournalError(f"Could not encode journal record: {exc}") from exc
            if len(payload) > MAX_RECORD_BYTES:
                raise JournalError("Journal record is too large")
            frame = _FRAME.pack(len(payload), zlib.crc32(payload) & 0xFFFFFFFF)
            handle = self._file
            record_start = handle.seek(0, os.SEEK_END)
            try:
                handle.write(frame)
                handle.write(payload)
                handle.flush()
                if self._sync:
                    os.fsync(handle.fileno())
            except BaseException:
                handle.truncate(record_start)
                handle.seek(0, os.SEEK_END)
                raise
            self._sequence = sequence
            return sequence

    def reset(self) -> None:
        """Discard all journal records while retaining the sequence counter."""
        with self._lock:
            if self._closed or self._file is None:
                raise JournalError("Journal is closed")
            handle = self._file
            handle.seek(0)
            handle.truncate()
            handle.write(MAGIC)
            handle.flush()
            if self._sync:
                os.fsync(handle.fileno())
            self._records.clear()

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            if self._file is not None:
                self._file.close()
                self._file = None

    def __enter__(self) -> "Journal":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()


__all__ = [
    "CHECKPOINT_MAGIC",
    "MAGIC",
    "Journal",
    "JournalCorruptionError",
    "JournalError",
    "read_checkpoint",
    "write_checkpoint",
]
