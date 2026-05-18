from __future__ import annotations

import pandas as pd

__all__ = [
    "inspect_orbit_time_series",
]


def _mjd_to_datetime(series: pd.Series) -> pd.Series:
    datetimes = pd.to_datetime(series + 2400000.5, unit="D", origin="julian")
    return datetimes.dt.round("1s")


def inspect_orbit_time_series(
    df: pd.DataFrame,
    *,
    expected_step_seconds: int | float = 60,
) -> pd.DataFrame:
    """
    Inspect continuity of an orbit dataframe based on its time column.

    Returns a dataframe of problematic steps. Summary is stored in
    ``result.attrs["time_series_summary"]``.
    """
    time_column = df.attrs.get("time_column")
    if not time_column:
        raise ValueError("DataFrame attrs must contain 'time_column'.")

    if time_column not in df.columns:
        raise ValueError(f"Time column {time_column!r} not found in dataframe.")

    if df.empty:
        result = pd.DataFrame(
            columns=["time_prev", "time_next", "step_seconds", "issue_type"]
        )
        result.attrs["time_series_summary"] = {
            "row_count": 0,
            "expected_step_seconds": expected_step_seconds,
            "min_step_seconds": None,
            "max_step_seconds": None,
            "duplicate_count": 0,
            "gap_count": 0,
            "irregular_count": 0,
            "is_regular": True,
        }
        return result

    times = _mjd_to_datetime(pd.to_numeric(df[time_column], errors="coerce"))
    times = times.sort_values().reset_index(drop=True)

    previous = times.shift(1)
    step_seconds = times.diff().dt.total_seconds()

    issues = pd.DataFrame(
        {
            "time_prev": previous,
            "time_next": times,
            "step_seconds": step_seconds,
        }
    ).dropna()

    def classify(step: float) -> str | None:
        if step == expected_step_seconds:
            return None
        if step == 0:
            return "duplicate"
        if step > expected_step_seconds:
            return "gap"
        return "irregular"

    issues["issue_type"] = issues["step_seconds"].map(classify)
    issues = issues[issues["issue_type"].notna()].reset_index(drop=True)

    all_steps = step_seconds.dropna()
    summary = {
        "row_count": len(df),
        "expected_step_seconds": expected_step_seconds,
        "min_step_seconds": float(all_steps.min()) if not all_steps.empty else None,
        "max_step_seconds": float(all_steps.max()) if not all_steps.empty else None,
        "duplicate_count": int((issues["issue_type"] == "duplicate").sum()) if not issues.empty else 0,
        "gap_count": int((issues["issue_type"] == "gap").sum()) if not issues.empty else 0,
        "irregular_count": int((issues["issue_type"] == "irregular").sum()) if not issues.empty else 0,
        "is_regular": bool(issues.empty),
    }

    issues.attrs["time_series_summary"] = summary
    return issues
