from __future__ import annotations

from typing import Final

import pandas as pd

__all__ = [
    "transform_itrf_to_gcrs",
]
import astropy.units as u
from astropy.time import Time
from astropy.coordinates import ITRS, GCRS


SUPPORTED_INPUT_FRAMES: Final[set[str]] = {"ITRF", "ITRS", "IGS"}
SUPPORTED_TIME_SCALES: Final[set[str]] = {"TAI", "UTC", "GPS"}


def _require_columns(df: pd.DataFrame, columns: list[str]) -> None:
    missing = [col for col in columns if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")


def _detect_time_column(df: pd.DataFrame) -> str:
    time_column = str(df.attrs.get("time_column", "")).strip()
    if time_column and time_column in df.columns:
        return time_column

    candidates = [c for c in df.columns if isinstance(c, str) and c.startswith("MJD_")]
    if len(candidates) == 1:
        return candidates[0]

    raise ValueError(
        "Could not determine time column. "
        "Expected df.attrs['time_column'] or exactly one 'MJD_*' column."
    )


def _detect_time_scale(df: pd.DataFrame, time_column: str) -> str:
    scale = str(df.attrs.get("time_scale", "")).upper().strip()
    if scale in SUPPORTED_TIME_SCALES:
        return scale

    if time_column.startswith("MJD_"):
        guessed = time_column.removeprefix("MJD_").upper()
        if guessed in SUPPORTED_TIME_SCALES:
            return guessed

    raise ValueError(
        "Could not determine time scale. "
        "Expected df.attrs['time_scale'] or time column name like 'MJD_TAI'."
    )

def _detect_coordinate_system(df: pd.DataFrame) -> str:
    frame = str(df.attrs.get("coordinate_system", "")).upper().strip()

    if frame in {"ITRF", "ITRS", "IGS"}:
        return frame

    if "ITRF" in frame:
        return "ITRF"

    raise ValueError(
        f"Unsupported coordinate system: {frame}. "
        "Expected ITRF/ITRS/IGS."
    )

def transform_itrf_to_gcrs(df: pd.DataFrame) -> pd.DataFrame:
    """
    Transform trajectory from ITRF/ITRS to GCRS using Astropy.

    Expected input
    --------------
    DataFrame with columns:
        x, y, z, vx, vy, vz, MJD_<TIME_SCALE>

    Metadata in df.attrs:
        coordinate_system : 'ITRF' or 'ITRS'
        time_scale        : 'TAI', 'UTC', or 'GPS'
        time_column       : e.g. 'MJD_TAI'

    Assumptions
    -----------
    - Position is in meters
    - Velocity is in m/s
    - Time column is MJD in the declared time scale

    Returns
    -------
    pd.DataFrame
        New dataframe with transformed x, y, z, vx, vy, vz.
        Time column is preserved.
        coordinate_system is updated to 'GCRS'.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame")

    _require_columns(df, ["x", "y", "z", "vx", "vy", "vz"])

    input_frame = _detect_coordinate_system(df)
    time_column = _detect_time_column(df)
    time_scale = _detect_time_scale(df, time_column)

    if time_column not in df.columns:
        raise ValueError(f"Time column {time_column!r} not found in dataframe")

    out = df.copy()

    t = Time(
        out[time_column].to_numpy(dtype=float),
        format="mjd",
        scale=time_scale.lower(),
    )

    itrs = ITRS(
        x=out["x"].to_numpy(dtype=float) * u.m,
        y=out["y"].to_numpy(dtype=float) * u.m,
        z=out["z"].to_numpy(dtype=float) * u.m,
        v_x=out["vx"].to_numpy(dtype=float) * (u.m / u.s),
        v_y=out["vy"].to_numpy(dtype=float) * (u.m / u.s),
        v_z=out["vz"].to_numpy(dtype=float) * (u.m / u.s),
        obstime=t,
    )

    gcrs = itrs.transform_to(GCRS(obstime=t))

    r_gcrs = gcrs.cartesian.xyz.to_value(u.m).T
    v_gcrs = gcrs.velocity.d_xyz.to_value(u.m / u.s).T

    out["x"] = r_gcrs[:, 0]
    out["y"] = r_gcrs[:, 1]
    out["z"] = r_gcrs[:, 2]

    out["vx"] = v_gcrs[:, 0]
    out["vy"] = v_gcrs[:, 1]
    out["vz"] = v_gcrs[:, 2]

    attrs = dict(out.attrs)
    attrs["source_coordinate_system"] = input_frame
    attrs["coordinate_system"] = "GCRS"
    attrs["transformation"] = "ITRF/ITRS -> GCRS"
    out.attrs = attrs

    return out