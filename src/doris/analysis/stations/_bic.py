"""BIC pro lineární modely fitované MNČ."""

from __future__ import annotations
import numpy as np


def bic_from_rss(n: int, rss: float, k: int = 2) -> float:
    """BIC = n·ln(RSS/n) + k·ln(n).

    Parameters
    ----------
    n   : počet datových bodů
    rss : součet čtverců reziduálů (nevážený nebo vážený dle modelu)
    k   : počet parametrů (výchozí 2 = sklon + úsek)
    """
    if n <= k or not np.isfinite(rss):
        return np.inf
    if rss <= 0:
        return -np.inf
    return n * np.log(rss / n) + k * np.log(n)
