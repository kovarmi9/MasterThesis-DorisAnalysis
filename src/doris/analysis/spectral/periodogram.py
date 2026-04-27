from __future__ import annotations

import numpy as np
import pandas as pd


def compute_periodogram(
    t,
    y,
    *,
    method: str = "fft",
    min_period: float | None = None,
    max_period: float | None = None,
) -> pd.DataFrame:
    """Compute periodogram. Currently only FFT is implemented."""
    if method.lower() != "fft":
        raise NotImplementedError("Only FFT periodogram is implemented.")

    return compute_fft_periodogram(t, y, min_period=min_period, max_period=max_period)


def compute_fft_periodogram(
    t,
    y,
    *,
    min_period: float | None = None,
    max_period: float | None = None,
) -> pd.DataFrame:
    """Compute simple one-sided FFT amplitude spectrum."""
    t = np.asarray(t, dtype=float)
    y = np.asarray(y, dtype=float)

    # Drop missing values
    mask = np.isfinite(t) & np.isfinite(y)
    t = t[mask]
    y = y[mask]

    # Sort by time
    order = np.argsort(t)
    t = t[order]
    y = y[order]

    if len(y) < 2:
        return pd.DataFrame(columns=["frequency", "period", "amplitude", "power", "phase_rad"])

    # Remove mean
    y = y - np.mean(y)

    # Use median sampling interval
    n = len(y)
    dt = np.median(np.diff(t))

    if not np.isfinite(dt) or dt <= 0:
        return pd.DataFrame(columns=["frequency", "period", "amplitude", "power", "phase_rad"])

    # FFT
    fft_values = np.fft.rfft(y)
    frequencies = np.fft.rfftfreq(n, d=dt)

    # Amplitude spectrum
    amplitude = np.abs(fft_values) / n
    if n % 2 == 0 and len(amplitude) > 2:
        amplitude[1:-1] *= 2.0
    elif len(amplitude) > 1:
        amplitude[1:] *= 2.0

    # Periods
    period = np.full_like(frequencies, np.inf)
    period[1:] = 1.0 / frequencies[1:]

    result = pd.DataFrame({
        "frequency": frequencies,
        "period": period,
        "amplitude": amplitude,
        "power": amplitude**2,
        "phase_rad": np.angle(fft_values),
    })

    # Remove zero frequency
    result = result[np.isfinite(result["period"])]

    # Optional period range
    if min_period is not None:
        result = result[result["period"] >= min_period]
    if max_period is not None:
        result = result[result["period"] <= max_period]

    return result.sort_values("period").reset_index(drop=True)