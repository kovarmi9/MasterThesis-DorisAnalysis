from __future__ import annotations

import numpy as np

__all__ = [
    "hermite_at_time",
]


def _coerce_inputs(data):
    """
    Supported input formats
    -----------------------
    1) (t, r, v)
       - t: (N,)
       - r: (N,3) or (3,N)
       - v: (N,3) or (3,N)

    2) (t, x, y, z, vx, vy, vz)
       - 7 separate vectors

    3) array (N,7) = [t, x, y, z, vx, vy, vz]

    Returns
    -------
    t : ndarray (N,)
    r : ndarray (N,3)
    v : ndarray (N,3)
    """
    if isinstance(data, (tuple, list)):
        if len(data) == 3:
            t, r, v = data
            t = np.asarray(t, dtype=float).reshape(-1)
            r = np.asarray(r, dtype=float)
            v = np.asarray(v, dtype=float)

            if r.ndim == 2 and r.shape == (3, t.size):
                r = r.T
            if v.ndim == 2 and v.shape == (3, t.size):
                v = v.T

            return t, r, v

        if len(data) == 7:
            t, x, y, z, vx, vy, vz = data
            t = np.asarray(t, dtype=float).reshape(-1)
            x = np.asarray(x, dtype=float).reshape(-1)
            y = np.asarray(y, dtype=float).reshape(-1)
            z = np.asarray(z, dtype=float).reshape(-1)
            vx = np.asarray(vx, dtype=float).reshape(-1)
            vy = np.asarray(vy, dtype=float).reshape(-1)
            vz = np.asarray(vz, dtype=float).reshape(-1)

            r = np.column_stack([x, y, z])
            v = np.column_stack([vx, vy, vz])
            return t, r, v

    arr = np.asarray(data, dtype=float)
    if arr.ndim == 2 and arr.shape[1] == 7:
        t = arr[:, 0]
        r = arr[:, 1:4]
        v = arr[:, 4:7]
        return t, r, v

    raise TypeError(
        "data must be one of: "
        "(t, r, v), (t, x, y, z, vx, vy, vz), "
        "or array (N,7)=[t,x,y,z,vx,vy,vz]."
    )


def _as_query_array(t_query):
    """
    Convert query times to 1D array.

    Returns
    -------
    tq : ndarray (Q,)
    was_scalar : bool
    """
    tq = np.asarray(t_query, dtype=float)
    if tq.ndim == 0:
        return tq.reshape(1), True
    return tq.reshape(-1), False


def _exact_node_index(t_sorted: np.ndarray, q: float, atol: float) -> int | None:
    """
    Return exact node index if q matches t_sorted within tolerance, else None.
    """
    k = int(np.searchsorted(t_sorted, q))

    if k < len(t_sorted) and abs(t_sorted[k] - q) <= atol:
        return k
    if k > 0 and abs(t_sorted[k - 1] - q) <= atol:
        return k - 1

    return None


def _select_nodes(t_sorted: np.ndarray, t_query: float, n_nodes: int) -> np.ndarray:
    """
    Select n_nodes around the interpolation gap given by searchsorted(t, t_query).

    Parameters
    ----------
    t_sorted : ndarray (N,)
        Strictly increasing times.
    t_query : float
        Query time.
    n_nodes : int
        Number of nodes.

    Returns
    -------
    ndarray (n_nodes,)
        Selected node indices.

    Raises
    ------
    ValueError
        If query is too close to edge and enough nodes cannot be selected.
    """
    left_count = n_nodes // 2
    right_count = n_nodes - left_count

    i_gap = int(np.searchsorted(t_sorted, float(t_query)))

    if i_gap - left_count < 0 or i_gap + right_count > len(t_sorted):
        raise ValueError(
            "Query too close to edge for selected degree; not enough nodes on both sides."
        )

    return np.concatenate(
        [
            np.arange(i_gap - left_count, i_gap),
            np.arange(i_gap, i_gap + right_count),
        ]
    )


def lagrange_basis(x_nodes: np.ndarray, x: float) -> np.ndarray:
    """
    Lagrange basis values L_k(x) for all nodes.

    Parameters
    ----------
    x_nodes : ndarray (m,)
    x : float

    Returns
    -------
    L : ndarray (m,)
    """
    x_nodes = np.asarray(x_nodes, dtype=float).reshape(-1)
    m = x_nodes.size
    L = np.ones(m, dtype=float)

    for k in range(m):
        for j in range(m):
            if j == k:
                continue
            L[k] *= (x - x_nodes[j]) / (x_nodes[k] - x_nodes[j])

    return L


def lagrange_basis_deriv_at_nodes(x_nodes: np.ndarray) -> np.ndarray:
    """
    Derivative of Lagrange basis at its own nodes: L'_k(x_k).

    Parameters
    ----------
    x_nodes : ndarray (m,)

    Returns
    -------
    dL : ndarray (m,)
    """
    x_nodes = np.asarray(x_nodes, dtype=float).reshape(-1)
    m = x_nodes.size
    dL = np.zeros(m, dtype=float)

    for k in range(m):
        s = 0.0
        for j in range(m):
            if j == k:
                continue
            s += 1.0 / (x_nodes[k] - x_nodes[j])
        dL[k] = s

    return dL


def hermite_interpolate(
    x_nodes: np.ndarray,
    y_nodes: np.ndarray,
    dy_nodes: np.ndarray,
    x: float,
) -> np.ndarray:
    """
    Classical Hermite interpolation using values and first derivatives.

    Parameters
    ----------
    x_nodes : ndarray (m,)
    y_nodes : ndarray (m,3)
    dy_nodes : ndarray (m,3)
    x : float

    Returns
    -------
    y : ndarray (3,)
        Interpolated position.
    """
    x_nodes = np.asarray(x_nodes, dtype=float).reshape(-1)
    y_nodes = np.asarray(y_nodes, dtype=float)
    dy_nodes = np.asarray(dy_nodes, dtype=float)

    m = x_nodes.size
    if y_nodes.shape != (m, 3) or dy_nodes.shape != (m, 3):
        raise ValueError("Expected shapes x_nodes(m,), y_nodes(m,3), dy_nodes(m,3).")

    L = lagrange_basis(x_nodes, float(x))
    dL = lagrange_basis_deriv_at_nodes(x_nodes)

    y = np.zeros(3, dtype=float)

    for k in range(m):
        dx = float(x) - x_nodes[k]
        L2 = L[k] * L[k]
        H = (1.0 - 2.0 * dx * dL[k]) * L2
        Hhat = dx * L2
        y += H * y_nodes[k] + Hhat * dy_nodes[k]

    return y


def hermite_at_time(
    data,
    t_query,
    *,
    degree: int = 11,
    drop_nan: bool = True,
    assume_sorted: bool = False,
    return_idx: bool = False,
    atol: float = 1e-12,
):
    """
    Universal Hermite interpolation for trajectory position from (t, r, v).

    This function is intentionally API-compatible with hermite_module6 style:
    it returns interpolated POSITION only.

    Parameters
    ----------
    data
        One of:
        - (t, r, v)
        - (t, x, y, z, vx, vy, vz)
        - array (N,7) = [t,x,y,z,vx,vy,vz]

    t_query : float or array-like
        Query time(s).

    degree : int, default=11
        Hermite polynomial degree. Must be odd.
        Number of nodes = (degree + 1) // 2.

    drop_nan : bool, default=True
        Drop rows containing NaNs before interpolation.

    assume_sorted : bool, default=False
        If False, inputs are sorted by time.

    return_idx : bool, default=False
        If True, also return indices of interpolation nodes.

    atol : float, default=1e-12
        Tolerance for exact node match.

    Returns
    -------
    If t_query is scalar:
        r_hat : ndarray (3,)
        optionally idx_nodes : ndarray (n_nodes,)

    If t_query is array-like length Q:
        r_hat : ndarray (Q,3)
        optionally idx_nodes : ndarray (Q,n_nodes)
    """
    if degree % 2 == 0:
        raise ValueError("degree must be odd (3,5,7,9,11,...).")

    n_nodes = (degree + 1) // 2

    t, r, v = _coerce_inputs(data)

    t = np.asarray(t, dtype=float).reshape(-1)
    r = np.asarray(r, dtype=float)
    v = np.asarray(v, dtype=float)

    if r.ndim == 2 and r.shape == (3, t.size):
        r = r.T
    if v.ndim == 2 and v.shape == (3, t.size):
        v = v.T

    if r.shape != (t.size, 3) or v.shape != (t.size, 3):
        raise ValueError("After coercion, shapes must be t(N,), r(N,3), v(N,3).")

    if drop_nan:
        mask = np.isfinite(t) & np.isfinite(r).all(axis=1) & np.isfinite(v).all(axis=1)
        t = t[mask]
        r = r[mask]
        v = v[mask]

    if t.size < n_nodes:
        raise ValueError(
            f"Not enough points for degree={degree}: need {n_nodes} nodes, got {t.size}."
        )

    if not assume_sorted:
        order = np.argsort(t)
        t = t[order]
        r = r[order]
        v = v[order]

    if np.any(np.diff(t) <= 0):
        raise ValueError("Times must be strictly increasing and without duplicates.")

    tq, was_scalar = _as_query_array(t_query)

    r_out = np.zeros((tq.size, 3), dtype=float)
    idx_out = np.zeros((tq.size, n_nodes), dtype=int) if return_idx else None

    for i, q in enumerate(tq):
        j_exact = _exact_node_index(t, float(q), float(atol))
        if j_exact is not None:
            r_out[i] = r[j_exact]
            if return_idx:
                idx_out[i] = _select_nodes(t, float(q), n_nodes)
            continue

        idx = _select_nodes(t, float(q), n_nodes)
        r_hat = hermite_interpolate(t[idx], r[idx], v[idx], float(q))

        r_out[i] = r_hat
        if return_idx:
            idx_out[i] = idx

    if was_scalar:
        if return_idx:
            return r_out[0], idx_out[0]
        return r_out[0]

    if return_idx:
        return r_out, idx_out
    return r_out