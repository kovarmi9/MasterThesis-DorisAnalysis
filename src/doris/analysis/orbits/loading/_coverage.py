from __future__ import annotations

from datetime import timedelta
from pathlib import Path

__all__ = [
    "inspect_orbit_file_coverage",
]


import pandas as pd

from ._filename_parsers import parse_filename_info


def inspect_orbit_file_coverage(paths: list[Path]) -> pd.DataFrame:
    """
    Inspect continuity between adjacent orbit files based on filename coverage.

    Returns a dataframe describing the relation between each adjacent pair.
    Summary counts are stored in ``df.attrs["coverage_summary"]``.
    """
    records: list[dict] = []

    parsed = []
    for path in paths:
        info = parse_filename_info(path)
        if info is None or info.start is None or info.end is None:
            continue
        parsed.append(info)

    parsed.sort(key=lambda item: (item.start, item.end, item.path.name))

    for left, right in zip(parsed, parsed[1:]):
        if right.start > left.end + timedelta(days=1):
            relation = "gap"
            gap_days = (right.start - left.end).days - 1
            overlap_days = 0
        elif right.start == left.end + timedelta(days=1):
            relation = "touching"
            gap_days = 0
            overlap_days = 0
        else:
            relation = "overlap"
            gap_days = 0
            overlap_days = (left.end - right.start).days + 1

        records.append(
            {
                "left_file": str(left.path),
                "right_file": str(right.path),
                "left_start": left.start,
                "left_end": left.end,
                "right_start": right.start,
                "right_end": right.end,
                "relation": relation,
                "gap_days": gap_days,
                "overlap_days": overlap_days,
            }
        )

    result = pd.DataFrame(records)

    if not result.empty:
        summary = {
            "file_count": len(parsed),
            "pair_count": len(result),
            "gap_count": int((result["relation"] == "gap").sum()),
            "touching_count": int((result["relation"] == "touching").sum()),
            "overlap_count": int((result["relation"] == "overlap").sum()),
        }
    else:
        summary = {
            "file_count": len(parsed),
            "pair_count": 0,
            "gap_count": 0,
            "touching_count": 0,
            "overlap_count": 0,
        }

    result.attrs["coverage_summary"] = summary
    return result
