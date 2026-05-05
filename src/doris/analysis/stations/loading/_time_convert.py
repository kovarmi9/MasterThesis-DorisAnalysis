"""MJD → calendar date and decimal-year conversion for station time series."""

from __future__ import annotations

import calendar
from datetime import datetime, timedelta

import pandas as pd

__all__ = [
    "add_time_columns",
]

# MJD epoch: 1858-11-17 00:00:00 UTC
_MJD_EPOCH = datetime(1858, 11, 17)


def _mjd_to_datetime(mjd: float) -> datetime:
    """Convert a single MJD value to a Python datetime.

    Uses the standard MJD epoch 1858-11-17.  The fractional part of *mjd*
    maps directly to hours/minutes/seconds (e.g. MJD 53704.5 → noon).
    """
    return _MJD_EPOCH + timedelta(days=float(mjd))


def _decimal_year(dt: datetime) -> float:
    """Convert a datetime to a decimal year.

    The fractional part is computed as elapsed seconds divided by the total
    seconds in that calendar year, which correctly handles leap years.

    Example
    -------
    2015-01-07 12:00:00  →  2015.017808…
    """
    y = dt.year
    year_start = datetime(y, 1, 1)
    year_end = datetime(y + 1, 1, 1)
    return y + (dt - year_start).total_seconds() / (year_end - year_start).total_seconds()


def add_time_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Add ``Date`` (datetime) and ``year`` (decimal year) columns to *df*.

    Reads the MJD column identified by ``df.attrs["mjd_column"]`` and appends:

    * ``Date`` – Python datetime corresponding to each MJD value; ``NaT``
      for missing epochs (NaN MJD).
    * ``year`` – Decimal year computed from ``Date``; ``NaN`` for missing
      epochs.

    The columns are inserted directly after ``MJD`` so the time information
    stays together at the left side of the table.

    Parameters
    ----------
    df:
        DataFrame as returned by :func:`read_stcd_to_dataframe`.  Must
        contain the column named in ``df.attrs["mjd_column"]``.

    Returns
    -------
    pd.DataFrame
        Copy of *df* with ``Date`` and ``year`` added.  ``df.attrs`` is
        preserved and extended with ``time_column = "Date"``.
    """
    mjd_col = df.attrs.get("mjd_column", "MJD")

    if mjd_col not in df.columns:
        raise ValueError(
            f"MJD column {mjd_col!r} not found in DataFrame. "
            "Available columns: " + ", ".join(df.columns)
        )

    out = df.copy()

    # MJD → datetime (NaN MJD → NaT)
    out["Date"] = out[mjd_col].apply(
        lambda v: _mjd_to_datetime(v) if pd.notna(v) else pd.NaT
    )

    # datetime → decimal year (NaT → NaN)
    out["year"] = out["Date"].apply(
        lambda v: _decimal_year(v) if pd.notna(v) else float("nan")
    )

    # Move Date and year to just after MJD
    mjd_idx = out.columns.get_loc(mjd_col)
    cols = list(out.columns)
    for extra in ("year", "Date"):
        if extra in cols:
            cols.remove(extra)
    cols.insert(mjd_idx + 1, "Date")
    cols.insert(mjd_idx + 2, "year")
    out = out[cols]

    attrs = dict(out.attrs)
    attrs["time_column"] = "Date"
    out.attrs = attrs

    return out
