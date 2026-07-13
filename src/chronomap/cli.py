"""Command-line interface for ChronoMap.

Right now this only supports inspecting a saved .json/.pkl file:

    python -m chronomap.cli show path/to/state.json

It's deliberately small. If you need put/get/history from the shell,
that's a good first PR — see CONTRIBUTING.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from .core import ChronoMap


class Colors:
    """ANSI color codes for terminal output."""

    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    END = "\033[0m"


def colorize(text: str, color: str) -> str:
    """Wrap `text` in an ANSI color code, resetting at the end."""
    return f"{color}{text}{Colors.END}"


def format_timestamp(ts: float) -> str:
    """Format a Unix timestamp as a local `YYYY-MM-DD HH:MM:SS` string."""
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def parse_value(raw: str) -> Any:
    """Best-effort parse of a CLI string argument into a Python value.

    Tries int, then float, then JSON (which also covers dicts, lists,
    true/false/null), and falls back to the original string if nothing
    else matches.
    """
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        pass
    return raw


def load_and_display(path: str) -> None:
    """Load a ChronoMap from a .json or .pkl file and print its current state."""
    file_path = Path(path)

    if not file_path.exists():
        print(colorize(f"File not found: {path}", Colors.RED))
        return

    suffix = file_path.suffix.lower()
    try:
        if suffix == ".json":
            cm = ChronoMap.load_json(file_path)
        elif suffix in (".pkl", ".pickle"):
            cm = ChronoMap.load_pickle(file_path)
        else:
            print(colorize(f"Unsupported file type: {suffix}", Colors.RED))
            return
    except Exception as exc:  # noqa: BLE001 - CLI boundary, want to report any failure
        print(colorize(f"Error loading file: {exc}", Colors.RED))
        return

    print(colorize(f"Loaded ChronoMap from {path}", Colors.GREEN))
    latest = cm.latest()
    print(f"Keys: {len(latest)}")
    for key, value in latest.items():
        print(f"{key}: {value}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="chronomap",
        description="Inspect ChronoMap save files from the command line.",
    )
    subparsers = parser.add_subparsers(dest="command")

    show_parser = subparsers.add_parser(
        "show", help="Load a .json/.pkl file and print its current key-value state."
    )
    show_parser.add_argument("path", help="Path to a file written by save_json() or save_pickle()")

    args = parser.parse_args(argv)

    if args.command == "show":
        load_and_display(args.path)
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":  # pragma: no cover - trivial entrypoint, not worth a subprocess test
    sys.exit(main())
