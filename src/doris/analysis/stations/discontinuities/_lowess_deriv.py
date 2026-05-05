"""LOWESS smoothing + derivative jump detection core."""

from __future__ import annotations

import numpy as np
from scipy.stats import norm


def _robust_scale(x: np.ndarray) -> float:
    """MAD-based robust standard deviation (same as in original notebook)."""
    med = np.median(x)
    mad = np.median(np.abs(x - med))
    if mad == 0:
        s = float(np.std(x))
        return s if s > 0 else 1.0
    return 1.4826 * float(mad)


def _lowess_derivative(
    years: np.ndarray,
    values: np.ndarray,
    frac: float,
    threshold_mode: str,
    k_sigma: float,
    min_abs: float,
    alpha: float,
) -> dict:
    """LOWESS smooth, compute derivative, detect jumps.

    Returns a dict with keys used by the public wrapper to build
    a :class:`JumpDetectionResult`.

    Threshold modes
    ---------------
    ``"heuristic"``
        ``max(min_abs, k_sigma · σ_slope)`` — identical to original notebook.
    ``"z_test"``
        ``max(min_abs, z_{α/2} · σ_slope)`` where ``z_{α/2}`` is the
        upper critical value of the standard normal at significance level
        *alpha*.  For ``alpha=0.05`` this gives ``z ≈ 1.96``, equivalent to
        ``k ≈ 2`` but with a principled statistical meaning.
    """
    try:
        from statsmodels.nonparametric.smoothers_lowess import lowess as _lowess
    except ImportError as e:
        raise ImportError(
            "statsmodels is required for LOWESS detection. "
            "Install it with:  pip install statsmodels"
        ) from e

    smoothed = _lowess(values, years, frac=frac, return_sorted=False)
    slope = np.diff(smoothed) / np.diff(years)
    t_mid = (years[:-1] + years[1:]) / 2
    sigma_slope = _robust_scale(slope)

    if threshold_mode == "heuristic":
        thr = max(min_abs, k_sigma * sigma_slope)
    else:  # z_test
        z_crit = float(norm.ppf(1.0 - alpha / 2.0))
        thr = max(min_abs, z_crit * sigma_slope)

    deriv_jumps = t_mid[np.abs(slope) > thr]
    jumps = np.unique(np.round(deriv_jumps, 6))

    return {
        "jumps": jumps,
        "threshold": thr,
        "sigma_slope": sigma_slope,
        "smoothed": smoothed,
        "t_mid": t_mid,
        "slope": slope,
    }
