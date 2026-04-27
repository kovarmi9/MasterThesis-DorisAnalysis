from __future__ import annotations

from datetime import date
from pathlib import Path

from ._filename_parsers import FilenameInfo, parse_filename_info

__all__ = [
    "select_orbit_files_for_period",
    "select_file_for_day",
]


def select_orbit_files_for_period(
    root: Path,
    start: date,
    end: date,
    *,
    recursive: bool = False,
) -> list[Path]:
    """
    Select all orbit files whose coverage overlaps the requested period [start, end].
    """

    if end < start:
        raise ValueError("End date must not be earlier than start date")

    if not root.exists():
        raise FileNotFoundError(f"Directory does not exist: {root}")

    if not root.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {root}")

    selected: list[Path] = []

    iterator = root.rglob("*") if recursive else root.iterdir()

    for path in iterator:
        if not path.is_file():
            continue

        info = parse_filename_info(path)
        if info is None:
            continue

        if info.start is None or info.end is None:
            continue

        # overlap test for intervals [info.start, info.end] and [start, end]
        if info.end >= start and info.start <= end:
            selected.append(path)

    return sorted(selected)


def select_file_for_day(
    root: Path,
    day: date,
    *,
    recursive: bool = True,
) -> FilenameInfo | None:
    """
    Return one best file covering the given day.
    """

    if not root.exists():
        raise FileNotFoundError(f"Directory does not exist: {root}")

    if not root.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {root}")

    iterator = root.rglob("*") if recursive else root.iterdir()

    candidates: list[FilenameInfo] = []

    for path in iterator:
        if not path.is_file():
            continue

        info = parse_filename_info(path)
        if info is None:
            continue

        if info.start is None or info.end is None:
            continue

        # inclusive coverage of the day
        if info.start <= day <= info.end:
            candidates.append(info)

    if not candidates:
        return None

    # choose the file with the widest/most useful coverage
    best = candidates[0]
    for c in candidates[1:]:
        left_span_best = (day - best.start).days
        right_span_best = (best.end - day).days
        left_span_c = (day - c.start).days
        right_span_c = (c.end - day).days

        # prefer file that gives more room around the target day
        if min(left_span_c, right_span_c) > min(left_span_best, right_span_best):
            best = c
        elif min(left_span_c, right_span_c) == min(left_span_best, right_span_best):
            if (c.end - c.start).days > (best.end - best.start).days:
                best = c

    return best