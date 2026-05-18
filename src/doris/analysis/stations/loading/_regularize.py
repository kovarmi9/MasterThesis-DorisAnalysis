"""MJD grid regularisation for station time series.

Detects the dominant sampling interval and fills missing epochs with NaN rows
so the resulting time series has a perfectly uniform step.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = [
    "infer_mjd_step",
    "regularize_mjd_grid",
]


def infer_mjd_step(df: pd.DataFrame) -> int:
    """Return the most frequent integer MJD step (in days).

    Computes consecutive differences between sorted, unique MJD values,
    rounds each to the nearest integer, and returns the smallest integer
    that occurs most frequently.  This handles minor floating-point jitter
    around the true step (e.g. 6.9999… vs 7.0001…).

    Parameters
    ----------
    df:
        DataFrame containing an ``"MJD"`` column (or the column named in
        ``df.attrs["mjd_column"]``).

    Returns
    -------
    int
        Dominant step in days (e.g. ``7`` for weekly data).

    Raises
    ------
    ValueError
        If fewer than two valid MJD values are present, or if no positive
        differences are found.
    """
    mjd_col = df.attrs.get("mjd_column", "MJD")
    s = pd.to_numeric(df[mjd_col], errors="coerce").dropna().to_numpy()

    if s.size < 2:
        raise ValueError(
            "Need at least two valid MJD values to infer the sampling step; "
            f"found {s.size}."
        )

    s = np.sort(np.unique(s))
    diffs = np.diff(s)
    diffs = diffs[diffs > 0]

    if diffs.size == 0:
        raise ValueError("No positive MJD differences found; all epochs are identical.")

    steps = np.rint(diffs).astype(int)
    vals, counts = np.unique(steps, return_counts=True)
    max_count = counts.max()

    # Among all steps tied for the highest frequency, choose the smallest
    return int(vals[counts == max_count].min())


def regularize_mjd_grid(
    df: pd.DataFrame,
    step: int | None = None,
) -> pd.DataFrame:
    """Fill gaps in the MJD grid with NaN rows.

    Builds a regular MJD sequence from the first to the last observed epoch
    using *step* days and reindexes *df* against it.  Missing epochs appear
    as rows of NaN in all data columns (``Date`` and ``year`` included if
    present).

    Parameters
    ----------
    df:
        DataFrame with an ``"MJD"`` column (after :func:`add_time_columns`
        it also has ``"Date"`` and ``"year"``).
    step:
        Sampling interval in days.  If ``None``, inferred automatically via
        :func:`infer_mjd_step`.

    Returns
    -------
    pd.DataFrame
        Regularised copy of *df*.  ``df.attrs`` is preserved and extended
        with::

            regularize = {
                "step_days": <int>,
                "rows_added": <int>,
                "inferred_step": <bool>,
            }

    Raises
    ------
    ValueError
        If *step* is not a positive integer.
    """
    mjd_col = df.attrs.get("mjd_column", "MJD")

    inferred = step is None
    if inferred:
        step = infer_mjd_step(df)

    if step <= 0:
        raise ValueError(f"`step` must be a positive integer; got {step}.")

    s = pd.to_numeric(df[mjd_col], errors="coerce").dropna().to_numpy()
    s = np.sort(np.unique(s))

    start, end = s[0], s[-1]
    n_steps = int(round((end - start) / step)) + 1
    grid = start + step * np.arange(n_steps, dtype=float)

    # Reindex: missing MJD epochs become NaN rows
    out = df.copy().set_index(mjd_col).reindex(grid)
    out.index.name = mjd_col
    out = out.reset_index()

    rows_added = int(len(grid) - len(s))

    # Re-fill Date and year for the newly inserted rows (MJD is now set)
    if "Date" in out.columns:
        from ._time_convert import _mjd_to_datetime, _decimal_year

        mask_new = out["Date"].isna() & out[mjd_col].notna()
        out.loc[mask_new, "Date"] = out.loc[mask_new, mjd_col].apply(_mjd_to_datetime)
        out.loc[mask_new, "year"] = out.loc[mask_new, "Date"].apply(_decimal_year)

    attrs = dict(out.attrs)
    attrs["regularize"] = {
        "step_days": int(step),
        "rows_added": rows_added,
        "inferred_step": inferred,
    }
    out.attrs = attrs

    return out
