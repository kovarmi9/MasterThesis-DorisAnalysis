from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from ..interpolate import interpolate_trajectory_to_reference
from ..track import project_to_rtn

__all__ = [
    "compare_trajectories",
]

log = logging.getLogger(__name__)


# Compare two orbit trajectories
def compare_trajectories(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    *,
    time_col: str = "t_sec",
    degree: int = 11,
    edge_trim: int = 10,
    rtn: bool = True,
    unit: str = "mm",
) -> pd.DataFrame:
    """
    Compare two orbit trajectories by interpolating A onto B's epochs.

    Parameters
    ----------
    df_a : DataFrame
        First trajectory (will be interpolated).
        Must contain: time_col, x, y, z, vx, vy, vz
    df_b : DataFrame
        Second trajectory (reference, defines time grid).
        Must contain: time_col, x, y, z, vx, vy, vz
    time_col : str
        Name of the time column (default: "t_sec")
    degree : int
        Hermite interpolation degree (default: 11, must be odd)
    edge_trim : int
        Number of points to trim from each edge of the
        interpolation interval to avoid boundary effects
    rtn : bool
        If True, decompose differences into RTN frame
    unit : str
        Output unit for differences: "mm" or "m"

    Returns
    -------
    DataFrame with columns:
        t_sec, x_ref, y_ref, z_ref, x_interp, y_interp, z_interp,
        dx, dy, dz, norm,
        [dR, dT, dN if rtn=True]

    Metadata in df.attrs:
        comparison_unit, degree, edge_trim, rtn, n_points,
        max_norm, mean_norm, std_norm
    """
    scale = 1000.0 if unit == "mm" else 1.0
    suffix = "_mm" if unit == "mm" else "_m"

    # Trim reference to stay inside source interval
    t_a = df_a[time_col].values
    t_min = t_a[edge_trim] if edge_trim > 0 else t_a[0]
    t_max = t_a[-edge_trim] if edge_trim > 0 else t_a[-1]

    mask = (df_b[time_col] >= t_min) & (df_b[time_col] <= t_max)
    df_ref = df_b[mask].copy().reset_index(drop=True)

    if len(df_ref) == 0:
        raise ValueError("No reference points inside source interval after trimming")

    log.info("Comparing trajectories: %d reference points, degree=%d", len(df_ref), degree)

    # Interpolate A onto reference epochs
    df_interp = interpolate_trajectory_to_reference(
        df_source=df_a,
        df_reference=df_ref,
        method="hermite",
        degree=degree,
        time_col=time_col,
    )

    # Position differences: ref - interp  (= GOP - SSA_interp)
    # Convention: same sign as Bernese STDDIF
    r_ref = df_ref[["x", "y", "z"]].values
    r_int = df_interp[["x", "y", "z"]].values
    dr = (r_ref - r_int) * scale

    dx = dr[:, 0]
    dy = dr[:, 1]
    dz = dr[:, 2]
    norm = np.sqrt(dx**2 + dy**2 + dz**2)

    # Build result DataFrame
    result = pd.DataFrame({
        time_col: df_ref[time_col].values,
        "x_ref": r_ref[:, 0],
        "y_ref": r_ref[:, 1],
        "z_ref": r_ref[:, 2],
        "x_interp": r_int[:, 0],
        "y_interp": r_int[:, 1],
        "z_interp": r_int[:, 2],
        f"dx{suffix}": dx,
        f"dy{suffix}": dy,
        f"dz{suffix}": dz,
        f"norm{suffix}": norm,
    })

    # RTN decomposition
    if rtn:
        v_ref = df_ref[["vx", "vy", "vz"]].values
        diff_m = (r_ref - r_int)  # differences in meters for RTN, same convention as Bernese STDDIF
        dR, dT, dN = project_to_rtn(diff_m, r_ref, v_ref)

        result[f"dR{suffix}"] = dR * scale
        result[f"dT{suffix}"] = dT * scale
        result[f"dN{suffix}"] = dN * scale

    # Store metadata
    result.attrs["comparison_unit"] = unit
    result.attrs["degree"] = degree
    result.attrs["edge_trim"] = edge_trim
    result.attrs["rtn"] = rtn
    result.attrs["n_points"] = len(result)
    result.attrs["max_norm"] = float(np.max(norm))
    result.attrs["mean_norm"] = float(np.mean(norm))
    result.attrs["median_norm"] = float(np.median(norm))
    result.attrs["std_norm"] = float(np.std(norm))

    if rtn:
        result.attrs["max_dR"] = float(np.max(np.abs(dR * scale)))
        result.attrs["max_dT"] = float(np.max(np.abs(dT * scale)))
        result.attrs["max_dN"] = float(np.max(np.abs(dN * scale)))

    log.info("Comparison done: %d points, max norm=%.4f %s", len(result), result.attrs["max_norm"], unit)

    return result
