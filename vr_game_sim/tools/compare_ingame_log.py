"""Utility for comparing rendered in-game log HTML snapshots."""

from __future__ import annotations

import difflib
import sys


def main(left_path: str, right_path: str) -> None:
    with open(left_path, "r", encoding="utf-8") as left_file:
        left_lines = left_file.read().splitlines()
    with open(right_path, "r", encoding="utf-8") as right_file:
        right_lines = right_file.read().splitlines()

    diff = difflib.unified_diff(
        left_lines,
        right_lines,
        fromfile=left_path,
        tofile=right_path,
        lineterm="",
    )
    print("\n".join(diff))


if __name__ == "__main__":  # pragma: no cover - convenience tool
    if len(sys.argv) != 3:
        print("Usage: compare_ingame_log.py our.html golden.html")
        raise SystemExit(1)
    main(sys.argv[1], sys.argv[2])
