"""Public API for station time-series jump/discontinuity detection."""

from __future__ import annotations

from typing import Literal

import numpy as np

from ._lowess_deriv import _lowess_derivative
from ._result import JumpDetectionResult
from ._sliding_window import _sliding_window

__all__ = [
    "detect_jumps_sliding_window",
    "detect_jumps_lowess",
]

ThresholdMode = Literal["heuristic", "t_test", "z_test"]


def detect_jumps_sliding_window(
    years: np.ndarray,
    values: np.ndarray,
    *,
    window_size: int = 40,
    shift: int = 40,
    threshold_mode: ThresholdMode = "heuristic",
    sigma_mult: float = 1.0,
    alpha: float = 0.05,
) -> JumpDetectionResult:
    """Detect jumps using two adjacent sliding windows.

    For each position, two windows of length *window_size* separated by
    *shift* samples are compared.  A jump is flagged when the windows differ
    significantly.

    Parameters
    ----------
    years : array-like
        Decimal-year epochs (e.g. ``df["year"].values``).
    values : array-like
        Time-series values at the corresponding epochs (e.g. aperiodic
        residuals in mm).  NaN values should be replaced before calling
        (e.g. ``fillna(0)``).
    window_size : int
        Length *W* of each window in samples.  Default ``40``.
    shift : int
        Offset *s* between the two windows in samples.  Default ``40``.
    threshold_mode : {"heuristic", "t_test"}
        How to decide whether two windows differ:

        * ``"heuristic"`` – flag when ``|μ₂ − μ₁| > sigma_mult · σ`` where
          *σ* is the global standard deviation.  Default; identical to the
          original notebook.
        * ``"t_test"`` – Welch two-sample t-test (unequal variances);
          flag when ``p < alpha``.

    sigma_mult : float
        Multiplier for the heuristic threshold.  Used only when
        *threshold_mode* is ``"heuristic"``.  Default ``1.0``.
    alpha : float
        Significance level for the t-test.  Used only when
        *threshold_mode* is ``"t_test"``.  Default ``0.05``.

    Returns
    -------
    JumpDetectionResult
        ``result.jumps`` – array of detected jump epochs in decimal years.
        ``result.extras`` contains the per-step window means and center
        epochs needed to reproduce the sliding-window plot.

    Examples
    --------
    >>> from doris.analysis.stations.discontinuities import detect_jumps_sliding_window
    >>> result = detect_jumps_sliding_window(df["year"].values,
    ...                                      df["aper_dU"].fillna(0).values)
    >>> print(result.jumps)
    """
    years = np.asarray(years, dtype=float)
    values = np.asarray(values, dtype=float)

    r = _sliding_window(years, values, window_size, shift, threshold_mode,
                        sigma_mult, alpha)

    return JumpDetectionResult(
        jumps=r["jumps"],
        method="sliding_window",
        threshold=r["threshold"],
        threshold_mode=threshold_mode,
        alpha=alpha if threshold_mode != "heuristic" else None,
        extras={
            "mu1": r["mu1"],
            "mu2": r["mu2"],
            "years1": r["years1"],
            "years2": r["years2"],
            "sigma": r["sigma"],
            "pvalues": r["pvalues"],
            "window_size": window_size,
            "shift": shift,
        },
    )


def detect_jumps_lowess(
    years: np.ndarray,
    values: np.ndarray,
    *,
    frac: float = 0.2,
    threshold_mode: ThresholdMode = "heuristic",
    k_sigma: float = 2.0,
    min_abs: float = 3.0,
    alpha: float = 0.05,
) -> JumpDetectionResult:
    """Detect jumps via LOWESS smoothing and derivative analysis.

    The series is smoothed with LOWESS, then the finite-difference derivative
    is computed.  Epochs where the absolute derivative exceeds a threshold are
    flagged as jump candidates.

    Parameters
    ----------
    years : array-like
        Decimal-year epochs.
    values : array-like
        Time-series values.  NaN should be filled before calling.
    frac : float
        LOWESS smoothing span as a fraction of the data length.  Smaller
        values preserve more detail.  Default ``0.2``.
    threshold_mode : {"heuristic", "z_test"}
        How to set the derivative threshold:

        * ``"heuristic"`` – ``max(min_abs, k_sigma · σ_slope)`` where
          *σ_slope* is a robust (MAD-based) estimate.  Default; identical to
          the original notebook.
        * ``"z_test"`` – ``max(min_abs, z_{α/2} · σ_slope)`` where
          ``z_{α/2} = norm.ppf(1 - alpha/2)`` is the upper critical value of
          the standard normal.  At ``alpha=0.05`` this gives ``z ≈ 1.96``
          (equivalent to ``k ≈ 2``) but with a principled statistical meaning.

    k_sigma : float
        Multiplier for the heuristic threshold.  Used only when
        *threshold_mode* is ``"heuristic"``.  Default ``2.0``.
    min_abs : float
        Hard lower bound on the threshold in the same units as *values* per
        year (e.g. mm/yr).  Prevents over-detection when the series is very
        smooth.  Default ``3.0``.
    alpha : float
        Significance level for the z-test.  Used only when
        *threshold_mode* is ``"z_test"``.  Default ``0.05``.

    Returns
    -------
    JumpDetectionResult
        ``result.jumps`` – unique detected jump epochs in decimal years.
        ``result.extras`` contains the smoothed curve, derivative, and
        midpoint times needed to reproduce the LOWESS plot.

    Examples
    --------
    >>> from doris.analysis.stations.discontinuities import detect_jumps_lowess
    >>> result = detect_jumps_lowess(df["year"].values,
    ...                              df["aper_dU"].fillna(0).values,
    ...                              threshold_mode="z_test", alpha=0.05)
    >>> print(result.jumps)
    """
    years = np.asarray(years, dtype=float)
    values = np.asarray(values, dtype=float)

    r = _lowess_derivative(years, values, frac, threshold_mode, k_sigma,
                           min_abs, alpha)

    return JumpDetectionResult(
        jumps=r["jumps"],
        method="lowess_derivative",
        threshold=r["threshold"],
        threshold_mode=threshold_mode,
        alpha=alpha if threshold_mode != "heuristic" else None,
        extras={
            "smoothed": r["smoothed"],
            "t_mid": r["t_mid"],
            "slope": r["slope"],
            "sigma_slope": r["sigma_slope"],
            "frac": frac,
            "min_abs": min_abs,
        },
    )
