from __future__ import annotations

from typing import Iterable

import numpy as np

__all__ = [
    "interpolate_trajectory_to_reference",
    "interpolate_like",
]
import pandas as pd

from .hermite import hermite_at_time


STATE_COLS = ["x", "y", "z", "vx", "vy", "vz"]
DEFAULT_TIME_CANDIDATES = ["t_sec_round", "t_sec", "MJD_TAI", "MJD_GPS"]


def _check_required_columns(df: pd.DataFrame, required: Iterable[str], name: str) -> None:
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise KeyError(f"{name} is missing required columns: {missing}")


def _resolve_time_column(
    df_source: pd.DataFrame,
    df_reference: pd.DataFrame,
    time_col: str | None = None,
) -> str:
    if time_col is not None:
        if time_col not in df_source.columns:
            raise KeyError(f"df_source is missing time column '{time_col}'.")
        if time_col not in df_reference.columns:
            raise KeyError(f"df_reference is missing time column '{time_col}'.")
        return time_col

    for col in DEFAULT_TIME_CANDIDATES:
        if col in df_source.columns and col in df_reference.columns:
            return col

    raise KeyError(
        "No common time column found. Tried: "
        f"{DEFAULT_TIME_CANDIDATES}. Pass time_col explicitly."
    )


def _prepare_source_matrix(
    df_source: pd.DataFrame,
    time_col: str,
) -> tuple[pd.DataFrame, np.ndarray]:
    _check_required_columns(df_source, [time_col, *STATE_COLS], "df_source")

    work = df_source[[time_col, *STATE_COLS]].copy()

    mask = np.isfinite(work[time_col].to_numpy(dtype=float))
    for col in STATE_COLS:
        mask &= np.isfinite(work[col].to_numpy(dtype=float))

    work = work.loc[mask].copy()
    work = work.sort_values(time_col).reset_index(drop=True)

    M = work[[time_col, *STATE_COLS]].to_numpy(dtype=float)
    return work, M


def _prepare_reference(
    df_reference: pd.DataFrame,
    time_col: str,
) -> tuple[pd.DataFrame, np.ndarray]:
    _check_required_columns(df_reference, [time_col], "df_reference")

    ref = df_reference.copy()
    ref = ref.sort_values(time_col).reset_index(drop=True)

    tq = ref[time_col].to_numpy(dtype=float)
    return ref, tq


def interpolate_trajectory_to_reference(
    df_source: pd.DataFrame,
    df_reference: pd.DataFrame,
    method: str = "hermite",
    degree: int = 11,
    *,
    time_col: str | None = None,
    source_window_margin_points: int | None = None,
    preserve_reference_columns: bool = True,
) -> pd.DataFrame:
    """
    Interpolate source trajectory to epochs from reference dataframe.

    Notes
    -----
    Backend uses hermite.hermite_at_time(), which returns POSITION only,
    matching hermite_module6-style API. Therefore vx, vy, vz are set to NaN
    in the output for now.
    """
    del source_window_margin_points  # kept only for API compatibility

    if method != "hermite":
        raise ValueError("Only method='hermite' is supported.")

    resolved_time_col = _resolve_time_column(df_source, df_reference, time_col=time_col)

    src_work, M = _prepare_source_matrix(df_source, resolved_time_col)
    ref_work, tq = _prepare_reference(df_reference, resolved_time_col)

    t_min = float(src_work[resolved_time_col].iloc[0])
    t_max = float(src_work[resolved_time_col].iloc[-1])

    if len(tq) > 0:
        q_min = float(np.nanmin(tq))
        q_max = float(np.nanmax(tq))
        if q_min < t_min or q_max > t_max:
            raise ValueError(
                "Reference times are outside source interpolation interval: "
                f"source=[{t_min}, {t_max}], reference=[{q_min}, {q_max}]"
            )

    r_i = hermite_at_time(
        M,
        tq,
        degree=degree,
        assume_sorted=True,
        drop_nan=True,
    )

    if preserve_reference_columns:
        out = ref_work.copy()
    else:
        out = ref_work[[resolved_time_col]].copy()

    out["x"] = r_i[:, 0]
    out["y"] = r_i[:, 1]
    out["z"] = r_i[:, 2]

    # Backend is intentionally position-only for compatibility with hermite_module6 style
    out["vx"] = np.nan
    out["vy"] = np.nan
    out["vz"] = np.nan

    out.attrs = dict(getattr(df_reference, "attrs", {}))
    out.attrs["interpolation_method"] = "hermite"
    out.attrs["interpolation_degree"] = degree
    out.attrs["interpolation_time_column"] = resolved_time_col
    out.attrs["interpolation_source_rows"] = len(src_work)
    out.attrs["interpolation_reference_rows"] = len(ref_work)

    return out


def interpolate_like(
    df_source: pd.DataFrame,
    df_reference: pd.DataFrame,
    method: str = "hermite",
    degree: int = 11,
    *,
    time_col: str | None = None,
    source_window_margin_points: int | None = None,
    preserve_reference_columns: bool = True,
) -> pd.DataFrame:
    """
    Backward-compatible alias.
    """
    return interpolate_trajectory_to_reference(
        df_source=df_source,
        df_reference=df_reference,
        method=method,
        degree=degree,
        time_col=time_col,
        source_window_margin_points=source_window_margin_points,
        preserve_reference_columns=preserve_reference_columns,
    )