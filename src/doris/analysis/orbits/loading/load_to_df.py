from __future__ import annotations

from collections.abc import Iterator
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from ._continuity import inspect_orbit_time_series
from ._convert_trajectory_units import convert_trajectory_units
from ._coverage import inspect_orbit_file_coverage
from ._deduplicate import deduplicate_orbit_epochs
from ._orbit_file_selection import select_orbit_files_for_period
from ._sp3_reader import read_sp3_files_to_dataframe

__all__ = [
    "load_orbit_dataframe",
    "load_orbit_day",
    "iter_orbit_days",
]

_MJD_EPOCH = datetime(1858, 11, 17, tzinfo=timezone.utc)


def _date_to_mjd_utc(d: date) -> float:
    """Convert date to MJD"""
    dt = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    return (dt - _MJD_EPOCH).total_seconds() / 86400.0


def load_orbit_dataframe(
    source: Path,
    start: date,
    end: date,
    *,
    recursive: bool = True,
    dedup_keep: str = "first",
    compute_statistics: bool = False,
    normalize: bool = True,
    target_time_scale: str = "TAI",
    add_epoch: bool = True,
    inspect_coverage: bool = True,
    inspect_continuity: bool = True,
    expected_step_seconds: int | float = 60,
) -> pd.DataFrame:
    """
    Load orbit data for a time range into one DataFrame.
    """

    # select files
    paths = select_orbit_files_for_period(
        source,
        start=start,
        end=end,
        recursive=recursive,
    )

    if not paths:
        raise ValueError(f"No orbit files for {start} -> {end} in {source}")

    # optional: check file coverage
    coverage_summary = None
    if inspect_coverage:
        coverage_summary = inspect_orbit_file_coverage(paths).attrs.get("coverage_summary")

    # read + clean data
    df = read_sp3_files_to_dataframe(paths)
    df = deduplicate_orbit_epochs(
        df,
        keep=dedup_keep,
        compute_statistics=compute_statistics,
    )

    # optional: normalize units and time
    if normalize:
        df = convert_trajectory_units(
            df,
            target_time_scale=target_time_scale,
            add_epoch=add_epoch,
        )

    # optional: check time gaps
    time_series_summary = None
    if inspect_continuity:
        time_series_summary = inspect_orbit_time_series(
            df,
            expected_step_seconds=expected_step_seconds,
        ).attrs.get("time_series_summary")

    # store metadata
    attrs = dict(df.attrs)
    attrs["load_to_df"] = {
        "source_root": str(source),
        "requested_start": start.isoformat(),
        "requested_end": end.isoformat(),
        "recursive": recursive,
        "selected_file_count": len(paths),
        "dedup_keep": dedup_keep,
        "compute_statistics": compute_statistics,
        "normalize": normalize,
        "target_time_scale": target_time_scale if normalize else None,
        "add_epoch": add_epoch if normalize else False,
        "coverage_summary": coverage_summary,
        "time_series_summary": time_series_summary,
    }
    df.attrs = attrs

    return df


def load_orbit_day(
    source: Path,
    day: date,
    *,
    window: float = 0.0,
    recursive: bool = True,
    dedup_keep: str = "first",
    normalize: bool = True,
    target_time_scale: str = "TAI",
    add_epoch: bool = False,
    inspect_coverage: bool = False,
    inspect_continuity: bool = False,
) -> pd.DataFrame:
    """
    Load data for one day and cut to time window.
    """

    # select files for this day
    paths = select_orbit_files_for_period(
        source,
        start=day,
        end=day,
        recursive=recursive,
    )

    if not paths:
        raise ValueError(f"No orbit files for {day} in {source}")

    coverage_summary = None
    if inspect_coverage:
        coverage_summary = inspect_orbit_file_coverage(paths).attrs.get("coverage_summary")

    # read + clean
    df = read_sp3_files_to_dataframe(paths)
    df = deduplicate_orbit_epochs(df, keep=dedup_keep, compute_statistics=False)

    if normalize:
        df = convert_trajectory_units(
            df,
            target_time_scale=target_time_scale,
            add_epoch=add_epoch,
        )

    time_series_summary = None
    if inspect_continuity:
        time_series_summary = inspect_orbit_time_series(df).attrs.get("time_series_summary")

    # trim to time window
    time_col = df.attrs.get("time_column", f"MJD_{target_time_scale.upper()}")

    if time_col in df.columns:
        t_start = _date_to_mjd_utc(day) - window
        t_end = _date_to_mjd_utc(day + timedelta(days=1)) + window

        mask = (df[time_col] >= t_start) & (df[time_col] < t_end)
        df = df[mask].reset_index(drop=True)

    # store metadata
    attrs = dict(df.attrs)
    attrs["load_to_df"] = {
        "source_root": str(source),
        "requested_day": day.isoformat(),
        "window_mjd_days": window,
        "recursive": recursive,
        "selected_file_count": len(paths),
        "dedup_keep": dedup_keep,
        "normalize": normalize,
        "target_time_scale": target_time_scale if normalize else None,
        "add_epoch": add_epoch if normalize else False,
        "coverage_summary": coverage_summary,
        "time_series_summary": time_series_summary,
    }
    df.attrs = attrs

    return df


def iter_orbit_days(
    source: Path,
    start: date,
    end: date,
    *,
    skip_missing: bool = True,  # if False, raise error on missing day
    **kwargs,
) -> Iterator[tuple[date, pd.DataFrame]]:
    """
    Loop over days and return (day, DataFrame).
    """

    current = start

    while current <= end:
        try:
            df = load_orbit_day(source, current, **kwargs)
            yield current, df
        except ValueError:
            if not skip_missing:
                raise

        current += timedelta(days=1)