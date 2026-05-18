"""High-level loader for STCD station-coordinate time series."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ._regularize import infer_mjd_step, regularize_mjd_grid
from ._stcd_reader import read_stcd_to_dataframe
from ._time_convert import add_time_columns

__all__ = [
    "load_station_dataframe",
]

# Cartesian-component columns not needed for ENU analysis
_XYZ_COLUMNS = ["dX", "dY", "dZ", "sX", "sY", "sZ"]


def _filter_window(
    df: pd.DataFrame,
    start: str | None,
    end: str | None,
) -> pd.DataFrame:
    """Slice *df* to the closed interval [start, end].

    Parameters
    ----------
    start, end:
        ISO date strings (``'YYYY-MM-DD'`` or ``'YYYY-MM-DD HH:MM'``).
        ``None`` means open on that side.
    """
    if "Date" not in df.columns:
        raise ValueError("DataFrame must have a 'Date' column before filtering.")

    dates = pd.to_datetime(df["Date"], errors="coerce")

    mask = pd.Series(True, index=df.index)
    if start is not None:
        mask &= dates >= pd.to_datetime(start)
    if end is not None:
        mask &= dates <= pd.to_datetime(end)

    return df.loc[mask].sort_values("Date").reset_index(drop=True)


def load_station_dataframe(
    path: Path | str,
    *,
    start: str | None = None,
    end: str | None = None,
    fill_gaps: bool = True,
    keep_xyz: bool = False,
) -> pd.DataFrame:
    """Load a STCD file into a ready-to-use pandas DataFrame.

    This is the main entry point for station time-series analysis.  It
    chains the low-level helpers in the correct order:

    1. :func:`read_stcd_to_dataframe` – parse the raw file.
    2. :func:`add_time_columns` – add ``Date`` and ``year``.
    3. :func:`regularize_mjd_grid` – fill gaps with NaN rows (optional).
    4. Window filtering – keep only epochs in ``[start, end]`` (optional).
    5. Drop XYZ columns (optional, default ``True``).

    Parameters
    ----------
    path:
        Path to the STCD file (e.g. ``data/stcd/gop25wd04/gop25wd04.stcd.licb``).
    start:
        Keep only epochs on or after this date.  ISO format:
        ``'YYYY-MM-DD'`` or ``'YYYY-MM-DD HH:MM'``.  ``None`` keeps all.
    end:
        Keep only epochs on or before this date.  Same format.
        ``None`` keeps all.
    fill_gaps:
        If ``True`` (default), regularise the MJD grid so missing epochs
        appear as NaN rows.  The step is inferred automatically.
    keep_xyz:
        If ``True``, retain the Cartesian-component columns
        ``dX, dY, dZ, sX, sY, sZ``.  Default ``False`` drops them because
        the ENU components ``dE, dN, dU, sE, sN, sU`` are used for analysis.

    Returns
    -------
    pd.DataFrame
        Columns (with ``keep_xyz=False``)::

            Date   – datetime
            year   – decimal year (e.g. 2015.017808)
            dE     – East  offset  [mm]
            dN     – North offset  [mm]
            dU     – Up    offset  [mm]
            sE     – East  sigma   [mm]
            sN     – North sigma   [mm]
            sU     – Up    sigma   [mm]

        ``MJD`` is always present as the first column.

        Provenance stored in ``df.attrs``:

        * ``source_file``   – absolute path of the input file
        * ``mjd_column``    – ``"MJD"``
        * ``time_column``   – ``"Date"``
        * ``regularize``    – dict with ``step_days``, ``rows_added``,
          ``inferred_step`` (only when *fill_gaps* is ``True``)
        * ``load_station``  – dict summarising all loader options

    Raises
    ------
    FileNotFoundError
        If *path* does not exist.
    ValueError
        If the file cannot be parsed, or if no rows remain after filtering.

    Examples
    --------
    >>> from doris.analysis.stations.loading import load_station_dataframe
    >>> df = load_station_dataframe(
    ...     "data/stcd/gop25wd04/gop25wd04.stcd.licb",
    ...     start="2015-01-01",
    ...     end="2025-12-31",
    ... )
    >>> df.head()
    """
    path = Path(path)

    # 1. Parse raw STCD file
    df = read_stcd_to_dataframe(path)

    # 2. Add Date and year columns
    df = add_time_columns(df)

    # 3. Regularise MJD grid (fill missing epochs with NaN)
    if fill_gaps:
        df = regularize_mjd_grid(df)

    # 4. Optional time-window filter
    if start is not None or end is not None:
        df = _filter_window(df, start, end)

        if df.empty:
            raise ValueError(
                f"No rows remain after filtering to window "
                f"[{start or '–'}, {end or '–'}] in {path}"
            )

    # 5. Drop XYZ columns unless caller wants them
    if not keep_xyz:
        cols_to_drop = [c for c in _XYZ_COLUMNS if c in df.columns]
        df = df.drop(columns=cols_to_drop)

    # Store loader provenance
    attrs = dict(df.attrs)
    attrs["load_station"] = {
        "path": str(path.resolve()),
        "start": start,
        "end": end,
        "fill_gaps": fill_gaps,
        "keep_xyz": keep_xyz,
        "n_rows": len(df),
    }
    df.attrs = attrs

    return df
