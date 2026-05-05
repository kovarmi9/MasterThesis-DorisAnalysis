"""Parser for plaintext STCD station-coordinate files."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

__all__ = [
    "read_stcd_to_dataframe",
]

# Fixed column order as produced by the GOP analysis centre
_STCD_COLUMNS = [
    "MJD",
    "dX", "dY", "dZ",
    "sX", "sY", "sZ",
    "dE", "dN", "dU",
    "sE", "sN", "sU",
]


def _find_data_start(path: Path) -> int:
    """Return the line index of the first numeric data row.

    Data lines are identified by leading whitespace followed by a digit,
    which is the format written by the GOP DORIS processing software.
    """
    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
        for i, line in enumerate(fh):
            stripped = line.lstrip()
            if stripped and stripped[0].isdigit():
                return i
    raise ValueError(
        f"No numeric data rows found in STCD file: {path}\n"
        "Expected lines starting with a digit after optional whitespace."
    )


def read_stcd_to_dataframe(path: Path | str) -> pd.DataFrame:
    """Read a single STCD file and return its contents as a pandas DataFrame.

    The STCD format is a plain-text, whitespace-delimited table produced by
    the GOP DORIS analysis centre.  A variable-length text header precedes the
    numeric table; this function locates the first numeric row automatically
    and reads the rest as the data block.

    Parameters
    ----------
    path:
        Path to the STCD file (e.g. ``gop25wd04.stcd.licb``).

    Returns
    -------
    pd.DataFrame
        Raw 13-column DataFrame with columns::

            MJD, dX, dY, dZ, sX, sY, sZ, dE, dN, dU, sE, sN, sU

        Provenance is stored in ``df.attrs``:

        * ``source_file`` – absolute path of the input file
        * ``mjd_column``  – name of the time column (``"MJD"``)

    Raises
    ------
    FileNotFoundError
        If *path* does not exist.
    ValueError
        If the file contains no parsable numeric rows, or if the number of
        columns on the first data line does not match the expected 13.
    """
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"STCD file does not exist: {path}")
    if not path.is_file():
        raise ValueError(f"Path is not a file: {path}")

    skiprows = _find_data_start(path)

    df = pd.read_csv(
        path,
        sep=r"\s+",
        header=None,
        skiprows=skiprows,
        names=_STCD_COLUMNS,
    )

    if df.empty:
        raise ValueError(f"No data rows parsed from STCD file: {path}")

    if len(df.columns) != len(_STCD_COLUMNS):
        raise ValueError(
            f"Expected {len(_STCD_COLUMNS)} columns, "
            f"got {len(df.columns)} in {path}"
        )

    # Convert all columns to numeric, coercing any stray text to NaN
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.sort_values("MJD").reset_index(drop=True)

    df.attrs["source_file"] = str(path.resolve())
    df.attrs["mjd_column"] = "MJD"

    return df
