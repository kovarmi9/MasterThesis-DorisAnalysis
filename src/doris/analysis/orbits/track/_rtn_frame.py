from __future__ import annotations

import numpy as np

__all__ = [
    "build_rtn_frame",
    "project_to_rtn",
]

_EPS = 1e-15


# Build RTN orthonormal frame from position and velocity
def build_rtn_frame(
    position: np.ndarray,
    velocity: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Build local RTN (Radial-Tangential-Normal) frame.

    Parameters
    ----------
    position : (N, 3) array — satellite position vectors [m]
    velocity : (N, 3) array — satellite velocity vectors [m/s]

    Returns
    -------
    R_hat : (N, 3) — radial unit vectors (Earth center → satellite)
    T_hat : (N, 3) — tangential unit vectors (along-track, in orbital plane)
    N_hat : (N, 3) — normal unit vectors (cross-track, orbital plane normal)
    """
    position = np.asarray(position, dtype=float)
    velocity = np.asarray(velocity, dtype=float)

    if position.ndim == 1:
        position = position[np.newaxis, :]
        velocity = velocity[np.newaxis, :]

    if position.shape != velocity.shape or position.shape[1] != 3:
        raise ValueError("position and velocity must have shape (N, 3)")

    # Radial: r / ||r||
    r_norm = np.linalg.norm(position, axis=1, keepdims=True)
    R_hat = position / np.maximum(r_norm, _EPS)

    # Normal: (r × v) / ||r × v||
    h = np.cross(position, velocity)
    h_norm = np.linalg.norm(h, axis=1, keepdims=True)
    N_hat = h / np.maximum(h_norm, _EPS)

    # Tangential: N × R
    T_hat = np.cross(N_hat, R_hat)

    return R_hat, T_hat, N_hat


# Project XYZ differences into RTN frame
def project_to_rtn(
    diff_xyz: np.ndarray,
    position: np.ndarray,
    velocity: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Project position differences into RTN frame.

    Parameters
    ----------
    diff_xyz : (N, 3) array — position differences in XYZ [m]
    position : (N, 3) array — reference satellite position [m]
    velocity : (N, 3) array — reference satellite velocity [m/s]

    Returns
    -------
    dR : (N,) — radial component [m]
    dT : (N,) — tangential component [m]
    dN : (N,) — normal component [m]
    """
    diff_xyz = np.asarray(diff_xyz, dtype=float)

    R_hat, T_hat, N_hat = build_rtn_frame(position, velocity)

    dR = np.sum(diff_xyz * R_hat, axis=1)
    dT = np.sum(diff_xyz * T_hat, axis=1)
    dN = np.sum(diff_xyz * N_hat, axis=1)

    return dR, dT, dN
