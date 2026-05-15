from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd
from scipy.signal import find_peaks

from .periodogram import compute_periodogram


def estimate_periodogram_threshold(
    t,
    y=None,
    *,
    method: str = "fft",
    time_col: str | None = None,
    value_cols: str | Sequence[str] | None = None,
    value_col: str = "amplitude",
    false_alarm_level: float = 0.95,
    n_permutations: int = 200,
    min_period: float | None = None,
    max_period: float | None = None,
    n_frequencies: int = 6000,
    random_state: int | None = None,
) -> float:
    """Estimate a periodogram threshold by random permutation of observations.

    The returned value is the selected quantile of the maximum periodogram value
    obtained from permuted data. It is a simple false-alarm threshold for a
    shuffle-based null model.
    """
    if not 0.0 < false_alarm_level < 1.0:
        raise ValueError("false_alarm_level must be between 0 and 1")
    if n_permutations < 1:
        raise ValueError("n_permutations must be at least 1")

    time, values = _coerce_threshold_input(t, y, time_col=time_col, value_cols=value_cols)

    # validate value_col once before running permutations
    test_pgram = compute_periodogram(
        time, values, method=method,
        min_period=min_period, max_period=max_period, n_frequencies=n_frequencies,
    )
    if value_col not in test_pgram:
        raise KeyError(f"Periodogram does not contain column {value_col!r}")

    rng = np.random.default_rng(random_state)
    maxima = [test_pgram[value_col].max()]

    for _ in range(n_permutations - 1):
        shuffled = values.copy()
        for col in range(shuffled.shape[1]):
            shuffled[:, col] = rng.permutation(shuffled[:, col])

        periodogram = compute_periodogram(
            time,
            shuffled,
            method=method,
            min_period=min_period,
            max_period=max_period,
            n_frequencies=n_frequencies,
        )

        maxima.append(periodogram[value_col].max())

    return float(np.quantile(np.asarray(maxima, dtype=float), false_alarm_level))


def find_significant_peaks(
    periodogram: pd.DataFrame,
    *,
    threshold: float,
    value_col: str = "amplitude",
    n_peaks: int = 10,
) -> pd.DataFrame:
    """Find local periodogram peaks above a threshold."""
    if value_col not in periodogram:
        raise KeyError(f"Periodogram does not contain column {value_col!r}")

    if "component" in periodogram.columns:
        parts = [
            _find_significant_peaks_1d(group, threshold=threshold, value_col=value_col, n_peaks=n_peaks)
            for _, group in periodogram.groupby("component", sort=False)
        ]
        parts = [part for part in parts if not part.empty]
        if not parts:
            return periodogram.iloc[0:0].copy()
        return pd.concat(parts, ignore_index=True)

    return _find_significant_peaks_1d(
        periodogram,
        threshold=threshold,
        value_col=value_col,
        n_peaks=n_peaks,
    )


def _coerce_threshold_input(t, y=None, *, time_col=None, value_cols=None):
    if isinstance(t, pd.DataFrame):
        if time_col is None:
            raise ValueError("time_col must be provided when t is a DataFrame")
        if value_cols is None:
            raise ValueError("value_cols must be provided when t is a DataFrame")

        value_cols = [value_cols] if isinstance(value_cols, str) else list(value_cols)
        time = t[time_col].to_numpy(dtype=float)
        values = t[value_cols].to_numpy(dtype=float)
        return time, _ensure_2d(values)

    if y is None:
        raise ValueError("y must be provided when t is not a DataFrame")

    time = np.asarray(t, dtype=float)
    values = _ensure_2d(np.asarray(y, dtype=float))

    if time.ndim != 1:
        raise ValueError("t must be a 1D array")
    if len(time) != values.shape[0]:
        raise ValueError("t and y must have the same number of rows")

    return time, values


def _ensure_2d(values):
    values = np.asarray(values, dtype=float)
    if values.ndim == 1:
        return values.reshape(-1, 1)
    if values.ndim == 2:
        return values
    raise ValueError("y must be a 1D or 2D array")


def _find_significant_peaks_1d(periodogram, *, threshold, value_col, n_peaks):
    df = periodogram.sort_values("period").reset_index(drop=True)
    peak_idx, _ = find_peaks(df[value_col].to_numpy())
    peaks = df.iloc[peak_idx].copy()
    peaks = peaks[peaks[value_col] >= threshold]

    # assumes period is in decimal years
    if "period_days" not in peaks.columns and "period" in peaks.columns:
        peaks["period_days"] = peaks["period"] * 365.25

    return peaks.sort_values(value_col, ascending=False).head(n_peaks).reset_index(drop=True)
