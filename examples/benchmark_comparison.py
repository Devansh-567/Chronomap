"""Compare ChronoMap, dict, and SQLite on common key-value workloads.

Run from the repository root:

    python examples/benchmark_comparison.py

The benchmark intentionally uses only Python's standard library plus ChronoMap
so it can run in a fresh checkout without extra dependencies.
"""

from __future__ import annotations

import argparse
import sqlite3
import statistics
import sys
import time
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from chronomap import ChronoMap  # noqa: E402

Operation = Callable[[], int]
BenchmarkResult = Tuple[str, str, float, int]


def timed(name: str, store_name: str, operation: Operation, repeats: int) -> BenchmarkResult:
    durations: List[float] = []
    total_units = 0
    for _ in range(repeats):
        start = time.perf_counter()
        total_units = operation()
        durations.append(time.perf_counter() - start)
    return name, store_name, statistics.median(durations), total_units


def setup_chronomap(size: int) -> ChronoMap:
    store = ChronoMap(cache_size=max(1, size))
    for index in range(size):
        store.put(f"key-{index}", index, timestamp=float(index))
    return store


def setup_dict(size: int) -> Dict[str, int]:
    return {f"key-{index}": index for index in range(size)}


def setup_sqlite(size: int) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE kv (key TEXT PRIMARY KEY, value INTEGER, ts REAL)")
    conn.executemany(
        "INSERT INTO kv (key, value, ts) VALUES (?, ?, ?)",
        ((f"key-{index}", index, float(index)) for index in range(size)),
    )
    conn.execute("CREATE INDEX idx_kv_ts ON kv(ts)")
    conn.commit()
    return conn


def benchmark_writes(size: int, repeats: int) -> Iterable[BenchmarkResult]:
    def chronomap_write() -> int:
        store = ChronoMap(cache_size=max(1, size))
        for index in range(size):
            store.put(f"key-{index}", index, timestamp=float(index))
        return size

    def dict_write() -> int:
        store: Dict[str, int] = {}
        for index in range(size):
            store[f"key-{index}"] = index
        return size

    def sqlite_write() -> int:
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE kv (key TEXT PRIMARY KEY, value INTEGER, ts REAL)")
        conn.executemany(
            "INSERT INTO kv (key, value, ts) VALUES (?, ?, ?)",
            ((f"key-{index}", index, float(index)) for index in range(size)),
        )
        conn.commit()
        conn.close()
        return size

    yield timed("writes", "ChronoMap", chronomap_write, repeats)
    yield timed("writes", "dict", dict_write, repeats)
    yield timed("writes", "SQLite", sqlite_write, repeats)


def benchmark_cached_reads(size: int, repeats: int) -> Iterable[BenchmarkResult]:
    chrono = setup_chronomap(size)
    plain = setup_dict(size)
    sqlite = setup_sqlite(size)
    key = f"key-{size // 2}"

    def chronomap_read() -> int:
        for _ in range(size):
            chrono.get(key)
        return size

    def dict_read() -> int:
        for _ in range(size):
            _ = plain[key]
        return size

    def sqlite_read() -> int:
        cursor = sqlite.cursor()
        for _ in range(size):
            cursor.execute("SELECT value FROM kv WHERE key = ?", (key,)).fetchone()
        return size

    yield timed("cached reads", "ChronoMap", chronomap_read, repeats)
    yield timed("cached reads", "dict", dict_read, repeats)
    yield timed("cached reads", "SQLite", sqlite_read, repeats)
    sqlite.close()


def benchmark_distinct_reads(size: int, repeats: int) -> Iterable[BenchmarkResult]:
    chrono = setup_chronomap(size)
    plain = setup_dict(size)
    sqlite = setup_sqlite(size)
    keys = [f"key-{index}" for index in range(size)]

    def chronomap_read() -> int:
        for key in keys:
            chrono.get(key)
        return size

    def dict_read() -> int:
        for key in keys:
            _ = plain[key]
        return size

    def sqlite_read() -> int:
        cursor = sqlite.cursor()
        for key in keys:
            cursor.execute("SELECT value FROM kv WHERE key = ?", (key,)).fetchone()
        return size

    yield timed("distinct reads", "ChronoMap", chronomap_read, repeats)
    yield timed("distinct reads", "dict", dict_read, repeats)
    yield timed("distinct reads", "SQLite", sqlite_read, repeats)
    sqlite.close()


def benchmark_range_queries(size: int, ranges: int, repeats: int) -> Iterable[BenchmarkResult]:
    chrono = setup_chronomap(size)
    plain = setup_dict(size)
    sqlite = setup_sqlite(size)
    windows = [(index, index + 10) for index in range(ranges)]

    def chronomap_range() -> int:
        total = 0
        for start, end in windows:
            total += len(chrono.query(lambda _key, value: start <= value < end))
        return total

    def dict_range() -> int:
        total = 0
        for start, end in windows:
            total += sum(1 for value in plain.values() if start <= value < end)
        return total

    def sqlite_range() -> int:
        cursor = sqlite.cursor()
        total = 0
        for start, end in windows:
            row = cursor.execute(
                "SELECT COUNT(*) FROM kv WHERE value >= ? AND value < ?",
                (start, end),
            ).fetchone()
            total += int(row[0])
        return total

    yield timed("range queries", "ChronoMap", chronomap_range, repeats)
    yield timed("range queries", "dict", dict_range, repeats)
    yield timed("range queries", "SQLite", sqlite_range, repeats)
    sqlite.close()


def print_results(results: Iterable[BenchmarkResult]) -> None:
    rows = list(results)
    print(f"{'Operation':<18} {'Store':<10} {'Median ms':>12} {'Ops/sec':>12} {'Units':>10}")
    print("-" * 68)
    for operation, store_name, seconds, units in rows:
        ops_per_second = units / seconds if seconds > 0 else float("inf")
        print(
            f"{operation:<18} {store_name:<10} "
            f"{seconds * 1000:>12.2f} {ops_per_second:>12,.0f} {units:>10,}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark ChronoMap against dict and SQLite.",
    )
    parser.add_argument("--size", type=int, default=10_000, help="write/read operation count")
    parser.add_argument("--ranges", type=int, default=1_000, help="number of range queries")
    parser.add_argument("--repeats", type=int, default=3, help="median repetitions per benchmark")
    args = parser.parse_args()

    if args.size <= 0 or args.ranges <= 0 or args.repeats <= 0:
        raise SystemExit("size, ranges, and repeats must be positive integers")

    results: List[BenchmarkResult] = []
    results.extend(benchmark_writes(args.size, args.repeats))
    results.extend(benchmark_cached_reads(args.size, args.repeats))
    results.extend(benchmark_distinct_reads(args.size, args.repeats))
    results.extend(benchmark_range_queries(args.size, args.ranges, args.repeats))
    print_results(results)


if __name__ == "__main__":
    main()
