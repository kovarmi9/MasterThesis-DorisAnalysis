from __future__ import annotations

import pandas as pd
from scipy.signal import find_peaks


def select_periodogram_peaks(
    periodogram: pd.DataFrame,
    *,
    value_col: str = "amplitude",
    n_peaks: int = 10,
    distance: int | None = None,
) -> pd.DataFrame:
    """Select the largest local peaks from a periodogram."""
    # sort by period so find_peaks works correctly regardless of input order
    df = periodogram.sort_values("period").reset_index(drop=True)

    # Find local maxima
    peaks, _ = find_peaks(df[value_col].to_numpy(), distance=distance)

    # Sort peaks by amplitude/power
    result = df.iloc[peaks].copy()
    result = result.sort_values(value_col, ascending=False)

    return result.head(n_peaks).reset_index(drop=True)