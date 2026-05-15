"""Sliding-window jump detection core."""

from __future__ import annotations

import numpy as np
from scipy.stats import ttest_ind


def _sliding_window(
    years: np.ndarray,
    values: np.ndarray,
    window_size: int,
    shift: int,
    threshold_mode: str,
    sigma_mult: float,
    alpha: float,
) -> dict:
    """Compute sliding-window means and detect jumps.

    Returns a dict with keys used by the public wrapper to build
    a :class:`JumpDetectionResult`.
    """
    n = len(values)
    mu1_list: list[float] = []
    mu2_list: list[float] = []
    yrs1: list[float] = []
    yrs2: list[float] = []
    pvalues: list[float | None] = []
    jumps: list[float] = []

    sigma = float(np.std(values))
    heur_thr = sigma_mult * sigma

    for i in range(n - window_size - shift + 1):
        seg1 = values[i : i + window_size]
        seg2 = values[i + shift : i + shift + window_size]
        mu1 = float(seg1.mean())
        mu2 = float(seg2.mean())

        c1 = float(years[i : i + window_size].mean())
        c2 = float(years[i + shift : i + shift + window_size].mean())

        mu1_list.append(mu1)
        mu2_list.append(mu2)
        yrs1.append(c1)
        yrs2.append(c2)

        if threshold_mode == "heuristic":
            detected = abs(mu2 - mu1) > heur_thr
            pvalues.append(None)
        else:  # t_test — Welch two-sample t-test
            _, p = ttest_ind(seg1, seg2, equal_var=False)
            p = float(p)
            pvalues.append(p)
            detected = p < alpha

        if detected:
            jumps.append(0.5 * (c1 + c2))

    # threshold: actual cutoff used — sigma-based for heuristic, alpha for t_test
    threshold = heur_thr if threshold_mode == "heuristic" else alpha

    return {
        "jumps": np.array(jumps),
        "threshold": threshold,
        "sigma": sigma,
        "mu1": np.array(mu1_list),
        "mu2": np.array(mu2_list),
        "years1": np.array(yrs1),
        "years2": np.array(yrs2),
        "pvalues": np.array(pvalues, dtype=object),
    }
