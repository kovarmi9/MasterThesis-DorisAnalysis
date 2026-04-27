import numpy as np
import pandas as pd

__all__ = [
    "orbit_diff_stats",
    "orbit_diff_summary",
]


def orbit_diff_stats(diff_df: pd.DataFrame) -> dict[str, float]:
    """
    Compute basic stats for R, T, N
    """

    dR = diff_df["dR_m"].to_numpy()
    dT = diff_df["dT_m"].to_numpy()
    dN = diff_df["dN_m"].to_numpy()

    def compute_stats(x):
        mean = float(np.mean(x))
        rms  = float(np.sqrt(np.mean(x**2)))
        rms0 = float(np.sqrt(np.mean((x - mean)**2)))
        return mean, rms, rms0
    
    r_mean, r_rms, r_rms0 = compute_stats(dR)
    t_mean, t_rms, t_rms0 = compute_stats(dT)
    n_mean, n_rms, n_rms0 = compute_stats(dN)

    return {
        "R_mean": r_mean,
        "T_mean": t_mean,
        "N_mean": n_mean,
        "R_rms":  r_rms,
        "T_rms":  t_rms,
        "N_rms":  n_rms,
        "R_rms0": r_rms0,
        "T_rms0": t_rms0,
        "N_rms0": n_rms0,
    }


def orbit_diff_summary(results: dict) -> pd.DataFrame:
    """
    Build simple table: one row per day.
    """

    rows = []

    for day, diff in sorted(results.items()):
        stats = orbit_diff_stats(diff)

        row = {"day": day}
        row.update(stats)

        rows.append(row)

    return pd.DataFrame(rows)