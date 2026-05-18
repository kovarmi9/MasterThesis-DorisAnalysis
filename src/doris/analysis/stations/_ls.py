"""Weighted and unweighted ordinary least-squares line fitting."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class FitResult:
    slope: float
    intercept: float
    rss: float      # sum of squared residuals (always unweighted)
    wrss: float     # weighted RSS: sum(w_i * e_i^2); equals rss when unweighted
    n: int
    x_min: float
    x_max: float
    r2: float
    weighted: bool


def fit_ols(x: np.ndarray, y: np.ndarray) -> FitResult:
    """Unweighted OLS line fit, NaN values are silently dropped."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    mask = np.isfinite(x) & np.isfinite(y)
    xm, ym = x[mask], y[mask]
    n = len(xm)

    slope, intercept = np.polyfit(xm, ym, 1)
    e = ym - (intercept + slope * xm)
    rss = float(np.sum(e**2))
    tss = float(np.sum((ym - ym.mean()) ** 2))
    r2 = 1.0 - rss / tss if tss > 0 else 0.0

    return FitResult(
        slope=float(slope),
        intercept=float(intercept),
        rss=rss,
        wrss=rss,
        n=n,
        x_min=float(xm.min()),
        x_max=float(xm.max()),
        r2=r2,
        weighted=False,
    )


def fit_wls(
    x: np.ndarray, y: np.ndarray, sigma: np.ndarray
) -> FitResult:
    """Weighted OLS line fit (weights w_i = 1/sigma_i^2), NaN/non-positive sigma dropped."""
    x, y, sigma = (np.asarray(a, float) for a in (x, y, sigma))
    mask = np.isfinite(x) & np.isfinite(y) & np.isfinite(sigma) & (sigma > 0)
    xm, ym, sm = x[mask], y[mask], sigma[mask]
    n = len(xm)

    w = 1.0 / sm**2
    sqrt_w = np.sqrt(w)

    # Pre-multiply design matrix and rhs by sqrt(w) → standard lstsq solves WLS
    A = np.column_stack([sqrt_w, sqrt_w * xm])
    b = sqrt_w * ym
    (intercept, slope), *_ = np.linalg.lstsq(A, b, rcond=None)

    e = ym - (intercept + slope * xm)
    rss = float(np.sum(e**2))
    wrss = float(np.sum(w * e**2))
    tss = float(np.sum((ym - ym.mean()) ** 2))
    r2 = 1.0 - rss / tss if tss > 0 else 0.0

    return FitResult(
        slope=float(slope),
        intercept=float(intercept),
        rss=rss,
        wrss=wrss,
        n=n,
        x_min=float(xm.min()),
        x_max=float(xm.max()),
        r2=r2,
        weighted=True,
    )
