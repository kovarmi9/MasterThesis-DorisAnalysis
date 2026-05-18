from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd
from scipy.signal import lombscargle


_PERIODOGRAM_COLUMNS = ["frequency", "period", "amplitude", "power", "phase_rad"]


def compute_periodogram(
    t,
    y=None,
    *,
    method: str = "fft",
    time_col: str | None = None,
    value_cols: str | Sequence[str] | None = None,
    min_period: float | None = None,
    max_period: float | None = None,
    n_frequencies: int = 6000,
) -> pd.DataFrame:
    """Compute a periodogram for one or more time-series columns.

    Parameters
    ----------
    t
        Time values, or a DataFrame when ``time_col`` and ``value_cols`` are used.
    y
        Data values. Can be a 1D array/Series, a 2D array, or omitted when ``t`` is
        a DataFrame.
    method
        ``"fft"`` for regularly sampled data, or ``"lomb_scargle"`` for unevenly
        sampled data.
    time_col, value_cols
        Column names used when ``t`` is a DataFrame.
    min_period, max_period
        Optional period range filter.
    n_frequencies
        Number of tested frequencies. Used only for Lomb-Scargle, ignored for FFT.
    """
    time, values, names = _coerce_periodogram_input(t, y, time_col=time_col, value_cols=value_cols)
    method_key = _normalize_method(method)

    frames = []
    for idx, name in enumerate(names):
        series = values[:, idx]

        if method_key == "fft":
            result = _fft_periodogram_1d(time, series)
        elif method_key == "lomb_scargle":
            result = _lomb_scargle_periodogram_1d(
                time,
                series,
                min_period=min_period,
                max_period=max_period,
                n_frequencies=n_frequencies,
            )
        else:  # pragma: no cover - guarded by _normalize_method
            raise ValueError(f"Unsupported periodogram method: {method!r}")

        frame = _periodogram_dict_to_frame(result)
        frame = _filter_period_range(frame, min_period=min_period, max_period=max_period)

        if len(names) > 1:
            frame.insert(0, "component", name)

        frames.append(frame)

    if not frames:
        return pd.DataFrame(columns=_PERIODOGRAM_COLUMNS)

    return pd.concat(frames, ignore_index=True)


def compute_fft_periodogram(
    t,
    y,
    *,
    min_period: float | None = None,
    max_period: float | None = None,
) -> pd.DataFrame:
    """Compute a one-sided FFT amplitude spectrum.

    This compatibility wrapper delegates to :func:`compute_periodogram`.
    """
    return compute_periodogram(
        t,
        y,
        method="fft",
        min_period=min_period,
        max_period=max_period,
    )


def _normalize_method(method: str) -> str:
    key = method.lower().replace("-", "_")

    if key in {"fft"}:
        return "fft"
    if key in {"lomb", "lomb_scargle", "lombscargle", "ls"}:
        return "lomb_scargle"

    raise ValueError("method must be 'fft' or 'lomb_scargle'")


def _coerce_periodogram_input(t, y=None, *, time_col=None, value_cols=None):
    if isinstance(t, pd.DataFrame):
        if time_col is None:
            raise ValueError("time_col must be provided when t is a DataFrame")

        if value_cols is None:
            raise ValueError("value_cols must be provided when t is a DataFrame")

        value_names = _normalize_value_cols(value_cols)
        time = t[time_col].to_numpy(dtype=float)
        values = t[value_names].to_numpy(dtype=float)

        return time, _ensure_2d_values(values), value_names

    if y is None:
        raise ValueError("y must be provided when t is not a DataFrame")

    time = np.asarray(t, dtype=float)

    if isinstance(y, pd.DataFrame):
        names = list(y.columns)
        values = y.to_numpy(dtype=float)
    elif isinstance(y, pd.Series):
        names = [y.name or "value"]
        values = y.to_numpy(dtype=float)
    else:
        values = np.asarray(y, dtype=float)
        values = _ensure_2d_values(values)
        names = [f"value_{i}" for i in range(values.shape[1])]
        if values.shape[1] == 1:
            names = ["value"]

    values = _ensure_2d_values(values)

    if time.ndim != 1:
        raise ValueError("t must be a 1D array")
    if len(time) != values.shape[0]:
        raise ValueError("t and y must have the same number of rows")

    return time, values, names


def _normalize_value_cols(value_cols: str | Sequence[str]) -> list[str]:
    if isinstance(value_cols, str):
        return [value_cols]

    return list(value_cols)


def _ensure_2d_values(values) -> np.ndarray:
    values = np.asarray(values, dtype=float)

    if values.ndim == 1:
        return values.reshape(-1, 1)
    if values.ndim == 2:
        return values

    raise ValueError("y must be a 1D or 2D array")


def _clean_sort_series(t, y):
    t = np.asarray(t, dtype=float)
    y = np.asarray(y, dtype=float)

    mask = np.isfinite(t) & np.isfinite(y)
    t = t[mask]
    y = y[mask]

    order = np.argsort(t)
    return t[order], y[order]


def _empty_periodogram_dict():
    return {
        "frequency": np.array([], dtype=float),
        "period": np.array([], dtype=float),
        "amplitude": np.array([], dtype=float),
        "power": np.array([], dtype=float),
        "phase_rad": np.array([], dtype=float),
    }


def _fft_periodogram_1d(t, y):
    """One-sided FFT amplitude spectrum for a single series."""
    t, y = _clean_sort_series(t, y)

    if len(y) < 2:
        return _empty_periodogram_dict()

    y = y - np.mean(y)
    n = len(y)
    dt = np.median(np.diff(t))

    if not np.isfinite(dt) or dt <= 0:
        return _empty_periodogram_dict()

    fft_values = np.fft.rfft(y)
    frequency = np.fft.rfftfreq(n, d=dt)

    # scale to one-sided amplitude
    amplitude = np.abs(fft_values) / n
    if n % 2 == 0 and len(amplitude) > 2:
        amplitude[1:-1] *= 2.0
    elif len(amplitude) > 1:
        amplitude[1:] *= 2.0

    # skip DC (frequency=0, period=inf)
    period = np.full_like(frequency, np.inf)
    period[1:] = 1.0 / frequency[1:]

    nonzero = np.isfinite(period)
    return {
        "frequency": frequency[nonzero],
        "period": period[nonzero],
        "amplitude": amplitude[nonzero],
        "power": amplitude[nonzero] ** 2,
        "phase_rad": np.angle(fft_values)[nonzero],
    }


def _lomb_scargle_periodogram_1d(
    t,
    y,
    *,
    min_period: float | None = None,
    max_period: float | None = None,
    n_frequencies: int = 6000,
):
    """Lomb-Scargle periodogram for a single series (works on unevenly sampled data)."""
    t, y = _clean_sort_series(t, y)

    if len(y) < 3:
        return _empty_periodogram_dict()

    y = y - np.mean(y)

    min_period, max_period = _resolve_lomb_period_range(t, min_period=min_period, max_period=max_period)
    frequency = np.linspace(1.0 / max_period, 1.0 / min_period, n_frequencies)
    angular_frequency = 2.0 * np.pi * frequency

    power = lombscargle(t, y, angular_frequency, precenter=False, normalize=True)
    amplitude, phase_rad = _sinusoid_amplitude_phase(t, y, angular_frequency)

    return {
        "frequency": frequency,
        "period": 1.0 / frequency,
        "amplitude": amplitude,
        "power": power,
        "phase_rad": phase_rad,
    }


def _resolve_lomb_period_range(t, *, min_period, max_period):
    if len(t) < 3:
        return 1.0, 1.0

    diffs = np.diff(np.sort(t))
    diffs = diffs[np.isfinite(diffs) & (diffs > 0)]
    baseline = np.max(t) - np.min(t)

    if min_period is None:
        if len(diffs) == 0:
            min_period = baseline / 100.0
        else:
            min_period = 2.0 * np.median(diffs)

    if max_period is None:
        max_period = baseline

    if not np.isfinite(min_period) or min_period <= 0:
        raise ValueError("min_period must be positive")
    if not np.isfinite(max_period) or max_period <= 0:
        raise ValueError("max_period must be positive")
    if min_period >= max_period:
        raise ValueError("min_period must be smaller than max_period")

    return float(min_period), float(max_period)


def _sinusoid_amplitude_phase(t, y, angular_frequency):
    phase = np.outer(t, angular_frequency)
    sin_matrix = np.sin(phase)
    cos_matrix = np.cos(phase)

    ss = np.sum(sin_matrix * sin_matrix, axis=0)
    cc = np.sum(cos_matrix * cos_matrix, axis=0)
    sc = np.sum(sin_matrix * cos_matrix, axis=0)
    sy = sin_matrix.T @ y
    cy = cos_matrix.T @ y

    det = ss * cc - sc**2
    sin_coef = np.divide(sy * cc - cy * sc, det, out=np.zeros_like(det), where=det != 0)
    cos_coef = np.divide(cy * ss - sy * sc, det, out=np.zeros_like(det), where=det != 0)

    return np.hypot(sin_coef, cos_coef), np.arctan2(cos_coef, sin_coef)


def _periodogram_dict_to_frame(result: dict[str, np.ndarray]) -> pd.DataFrame:
    frame = pd.DataFrame({column: result[column] for column in _PERIODOGRAM_COLUMNS})
    return frame.sort_values("period").reset_index(drop=True)


def _filter_period_range(frame, *, min_period, max_period):
    if min_period is not None:
        frame = frame[frame["period"] >= min_period]
    if max_period is not None:
        frame = frame[frame["period"] <= max_period]

    return frame.reset_index(drop=True)
