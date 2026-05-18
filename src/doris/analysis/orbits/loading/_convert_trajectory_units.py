from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
from astropy.time import Time

__all__ = [
    "convert_trajectory_units",
]

_SECONDS_PER_DAY = 86400.0
_MJD_EPOCH = datetime(1858, 11, 17, tzinfo=timezone.utc)
_GPS_MINUS_TAI_SECONDS = -19.0  # GPS = TAI - 19 s


# ============================================================
# Low-level time helpers
# ============================================================

def _mjd_to_datetime_utc_like(mjd: float) -> datetime:
    return _MJD_EPOCH + timedelta(days=float(mjd))


def _mjd_utc_to_mjd_tai(mjd_utc: float) -> float:
    return Time(mjd_utc, format="mjd", scale="utc").tai.mjd


def _mjd_tai_to_mjd_utc(mjd_tai: float) -> float:
    return Time(mjd_tai, format="mjd", scale="tai").utc.mjd


def _convert_mjd_between_scales(
    mjd: pd.Series,
    source_scale: str,
    target_scale: str,
) -> pd.Series:
    source = source_scale.upper()
    target = target_scale.upper()

    if source == target:
        return mjd.astype(float).copy()

    values = mjd.astype(float).to_numpy(copy=True)

    if source == "TAI" and target == "GPS":
        return pd.Series(values + _GPS_MINUS_TAI_SECONDS / _SECONDS_PER_DAY, index=mjd.index)

    if source == "GPS" and target == "TAI":
        return pd.Series(values - _GPS_MINUS_TAI_SECONDS / _SECONDS_PER_DAY, index=mjd.index)

    if source == "UTC" and target == "TAI":
        converted = np.array(
            [_mjd_utc_to_mjd_tai(v) if np.isfinite(v) else np.nan for v in values],
            dtype=float,
        )
        return pd.Series(converted, index=mjd.index)

    if source == "TAI" and target == "UTC":
        converted = np.array(
            [_mjd_tai_to_mjd_utc(v) if np.isfinite(v) else np.nan for v in values],
            dtype=float,
        )
        return pd.Series(converted, index=mjd.index)

    if source == "GPS" and target == "UTC":
        tai = _convert_mjd_between_scales(mjd, "GPS", "TAI")
        return _convert_mjd_between_scales(tai, "TAI", "UTC")

    if source == "UTC" and target == "GPS":
        tai = _convert_mjd_between_scales(mjd, "UTC", "TAI")
        return _convert_mjd_between_scales(tai, "TAI", "GPS")

    raise ValueError(f"Unsupported time-scale conversion: {source!r} -> {target!r}")


def _mjd_series_to_datetime_series(mjd: pd.Series) -> pd.Series:
    dts = [_mjd_to_datetime_utc_like(v).replace(tzinfo=None) if pd.notna(v) else pd.NaT for v in mjd.to_numpy()]
    return pd.to_datetime(dts)


# ============================================================
# Metadata helpers
# ============================================================

def _detect_time_scale(df: pd.DataFrame) -> str:
    time_scale = str(df.attrs.get("time_scale", "")).upper().strip()
    if time_scale in {"UTC", "TAI", "GPS"}:
        return time_scale

    time_column = str(df.attrs.get("time_column", "")).strip()
    if time_column.startswith("MJD_"):
        guessed = time_column.removeprefix("MJD_").upper()
        if guessed in {"UTC", "TAI", "GPS"}:
            return guessed

    for col in df.columns:
        if isinstance(col, str) and col.startswith("MJD_"):
            guessed = col.removeprefix("MJD_").upper()
            if guessed in {"UTC", "TAI", "GPS"}:
                return guessed

    raise ValueError("Could not determine source time scale from df.attrs or columns.")


def _detect_time_column(df: pd.DataFrame, source_scale: str) -> str:
    time_column = str(df.attrs.get("time_column", "")).strip()
    expected = f"MJD_{source_scale}"

    if time_column and time_column in df.columns:
        return time_column
    if expected in df.columns:
        return expected

    candidates = [c for c in df.columns if isinstance(c, str) and c.startswith("MJD_")]
    if len(candidates) == 1:
        return candidates[0]

    raise ValueError("Could not determine source time column.")


# ============================================================
# Public function
# ============================================================

def convert_trajectory_units(
    df: pd.DataFrame,
    *,
    target_time_scale: str = "TAI",
    add_epoch: bool = False,
) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame")

    target = target_time_scale.upper().strip()
    if target not in {"TAI", "UTC", "GPS"}:
        raise ValueError(f"Unsupported target_time_scale: {target_time_scale!r}")

    out = df.copy()

    source_scale = _detect_time_scale(out)
    source_time_column = _detect_time_column(out, source_scale)
    target_time_column = f"MJD_{target}"

    position_unit = str(out.attrs.get("position_unit", "m")).strip().lower()
    velocity_unit = str(out.attrs.get("velocity_unit", "m/s")).strip().lower()

    if position_unit == "km":
        factor = 1000.0
    elif position_unit == "m":
        factor = 1.0
    else:
        raise ValueError(f"Unsupported position unit: {position_unit!r}")

    for col in ("x", "y", "z"):
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce") * factor

    if velocity_unit == "dm/s":
        factor = 0.1
    elif velocity_unit == "km/s":
        factor = 1000.0
    elif velocity_unit == "m/s":
        factor = 1.0
    else:
        raise ValueError(f"Unsupported velocity unit: {velocity_unit!r}")

    for col in ("vx", "vy", "vz"):
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce") * factor

    if source_time_column not in out.columns:
        raise ValueError(f"Source time column {source_time_column!r} not found in dataframe")

    source_time_idx = out.columns.get_loc(source_time_column)
    source_time = pd.to_numeric(out[source_time_column], errors="coerce")

    if source_scale == target:
        converted_time = source_time
    else:
        converted_time = _convert_mjd_between_scales(
            source_time,
            source_scale=source_scale,
            target_scale=target,
        )

    out = out.drop(columns=[source_time_column])
    out.insert(source_time_idx, target_time_column, converted_time)

    other_mjd_columns = [
        c for c in out.columns
        if isinstance(c, str) and c.startswith("MJD_") and c != target_time_column
    ]
    if other_mjd_columns:
        out = out.drop(columns=other_mjd_columns, errors="ignore")

    epoch_column = f"epoch_{target}"
    if add_epoch:
        out[epoch_column] = _mjd_series_to_datetime_series(out[target_time_column])
    else:
        epoch_cols = [
            c for c in out.columns
            if isinstance(c, str) and c.startswith("epoch_")
        ]
        if epoch_cols:
            out = out.drop(columns=epoch_cols, errors="ignore")

    attrs = dict(out.attrs)
    attrs["source_time_scale"] = source_scale
    attrs["source_time_column"] = source_time_column
    attrs["time_scale"] = target
    attrs["time_column"] = target_time_column
    attrs["position_unit"] = "m"
    attrs["velocity_unit"] = "m/s"
    attrs["epoch_column"] = epoch_column if add_epoch else None
    attrs["normalized"] = True
    out.attrs = attrs

    sort_cols = [target_time_column]
    if "satellite" in out.columns:
        sort_cols.append("satellite")

    out = out.sort_values(sort_cols).reset_index(drop=True)
    out.attrs = attrs

    return out