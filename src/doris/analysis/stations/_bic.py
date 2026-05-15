"""BIC for linear models fitted by least squares."""

from __future__ import annotations
import numpy as np


def bic_from_rss(n: int, rss: float, k: int = 2) -> float:
    """BIC = n·ln(RSS/n) + k·ln(n).

    Parameters
    ----------
    n   : number of data points
    rss : residual sum of squares (unweighted or weighted depending on model)
    k   : number of parameters (default 2 = slope + intercept)
    """
    if n <= k or not np.isfinite(rss):
        return np.inf
    if rss <= 0:
        return -np.inf
    return n * np.log(rss / n) + k * np.log(n)
