"""Unified trend-fitting helpers for station time series."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

from ._bic import bic_from_rss
from ._ls import FitResult, fit_ols, fit_wls

__all__ = [
    "SegmentResult",
    "TrendResult",
    "fit_linear_trend",
    "fit_piecewise_trend",
]

BicMetric = Literal["rss", "wrss", "auto"]
_SPLIT_SCORE_TOL = 1e-12


@dataclass
class SegmentResult:
    """One fitted linear segment."""

    segment_id: int
    fit: FitResult

    @property
    def slope(self) -> float:
        return self.fit.slope

    @property
    def intercept(self) -> float:
        return self.fit.intercept

    @property
    def rss(self) -> float:
        return self.fit.rss

    @property
    def wrss(self) -> float:
        return self.fit.wrss

    @property
    def n(self) -> int:
        return self.fit.n

    @property
    def x_min(self) -> float:
        return self.fit.x_min

    @property
    def x_max(self) -> float:
        return self.fit.x_max

    def summary(self) -> dict[str, float | int]:
        return {
            "segment_id": self.segment_id,
            "slope": self.slope,
            "intercept": self.intercept,
            "rss": self.rss,
            "wrss": self.wrss,
            "n": self.n,
            "x_min": self.x_min,
            "x_max": self.x_max,
        }


@dataclass
class TrendResult:
    """Result of a station trend model in an export-friendly shape."""

    model: str
    segments: list[SegmentResult]
    breakpoints: list[float]
    bic: float
    bic_metric: str
    rss: float
    wrss: float
    r2: float
    x: np.ndarray
    y: np.ndarray
    fitted: np.ndarray
    residuals: np.ndarray
    sigma: np.ndarray | None = None
    valid_mask: np.ndarray | None = None
    segment_id: np.ndarray | None = None

    @property
    def fit(self) -> FitResult:
        """Backward-compatible access for one-segment results."""
        if len(self.segments) != 1:
            raise AttributeError("fit is only available for one-segment trends; use segments instead")
        return self.segments[0].fit

    @property
    def n_segments(self) -> int:
        return len(self.segments)

    @property
    def n(self) -> int:
        return int(sum(segment.n for segment in self.segments))

    @property
    def weighted(self) -> bool:
        return any(segment.fit.weighted for segment in self.segments)

    @property
    def slope(self) -> float:
        return self.fit.slope

    @property
    def intercept(self) -> float:
        return self.fit.intercept

    def summary(self) -> dict[str, float | int | str | bool | list[float]]:
        """Return scalar model metadata for tables or logs."""
        data: dict[str, float | int | str | bool | list[float]] = {
            "model": self.model,
            "weighted": self.weighted,
            "n": self.n,
            "n_segments": self.n_segments,
            "k": _k_params(self.n_segments),
            "rss": self.rss,
            "wrss": self.wrss,
            "r2": self.r2,
            "bic": self.bic,
            "bic_metric": self.bic_metric,
            "breakpoints": list(self.breakpoints),
        }

        if self.n_segments == 1:
            data.update(
                {
                    "slope": self.segments[0].slope,
                    "intercept": self.segments[0].intercept,
                    "x_min": self.segments[0].x_min,
                    "x_max": self.segments[0].x_max,
                }
            )

        return data

    def segments_summary(self):
        """Return one row per fitted segment."""
        import pandas as pd

        return pd.DataFrame([segment.summary() for segment in self.segments])

    def to_dataframe(self):
        """Return a pandas DataFrame with raw, fitted and detrended values."""
        import pandas as pd

        data = {
            "x": self.x,
            "y": self.y,
            "fitted": self.fitted,
            "residual": self.residuals,
            "model": self.model,
            "segment_id": self.segment_id,
            "valid": self.valid_mask,
        }

        if self.sigma is not None:
            data["sigma"] = self.sigma

        return pd.DataFrame(data)


def _as_float_array(values, name: str) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    if arr.ndim != 1:
        raise ValueError(f"{name} must be a one-dimensional array")
    return arr


def _resolve_bic_metric(weighted: bool, bic_metric: BicMetric) -> str:
    if bic_metric == "auto":
        return "wrss" if weighted else "rss"
    if bic_metric not in {"rss", "wrss"}:
        raise ValueError("bic_metric must be one of: 'rss', 'wrss', 'auto'")
    if bic_metric == "wrss" and not weighted:
        return "rss"
    return bic_metric


def _valid_mask(x: np.ndarray, y: np.ndarray, sigma: np.ndarray | None) -> np.ndarray:
    mask = np.isfinite(x) & np.isfinite(y)
    if sigma is not None:
        mask &= np.isfinite(sigma) & (sigma > 0)
    return mask


def _fit_segment(x: np.ndarray, y: np.ndarray, sigma: np.ndarray | None) -> FitResult:
    if sigma is None:
        return fit_ols(x, y)
    return fit_wls(x, y, sigma=sigma)


def _rss_for_bic(fit: FitResult, bic_metric: str) -> float:
    return fit.wrss if bic_metric == "wrss" else fit.rss


def _k_params(n_segments: int) -> int:
    return 3 * n_segments - 1


def _candidate_taus(x: np.ndarray, min_points: int, min_years: float) -> np.ndarray:
    unique_x = np.unique(x)
    if unique_x.size < 2:
        return np.array([], dtype=float)

    taus: list[float] = []
    xmin = float(unique_x[0])
    xmax = float(unique_x[-1])

    for tau in unique_x[:-1]:
        left_count = int(np.sum(x <= tau))
        right_count = int(np.sum(x > tau))
        if left_count < min_points or right_count < min_points:
            continue
        if min_years > 0 and (float(tau) - xmin < min_years or xmax - float(tau) < min_years):
            continue
        taus.append(float(tau))

    return np.asarray(taus, dtype=float)


def _best_split(
    x: np.ndarray,
    y: np.ndarray,
    sigma: np.ndarray | None,
    *,
    min_points: int,
    min_years: float,
    bic_metric: str,
) -> dict | None:
    best = None
    best_score = np.inf

    for tau in _candidate_taus(x, min_points=min_points, min_years=min_years):
        left = x <= tau
        right = x > tau
        sigma_left = sigma[left] if sigma is not None else None
        sigma_right = sigma[right] if sigma is not None else None

        fit_left = _fit_segment(x[left], y[left], sigma_left)
        fit_right = _fit_segment(x[right], y[right], sigma_right)
        score = _rss_for_bic(fit_left, bic_metric) + _rss_for_bic(fit_right, bic_metric)

        if score < best_score:
            best_score = score
            best = {
                "tau": float(tau),
                "fit_left": fit_left,
                "fit_right": fit_right,
                "score": float(score),
            }

    return best


def _fit_segments_from_breakpoints(
    x: np.ndarray,
    y: np.ndarray,
    sigma: np.ndarray | None,
    breakpoints: list[float],
) -> list[SegmentResult]:
    segments: list[SegmentResult] = []
    lower = -np.inf

    for segment_id, upper in enumerate([*breakpoints, np.inf]):
        if segment_id == 0:
            mask = x <= upper
        else:
            mask = (x > lower) & (x <= upper)

        if not np.any(mask):
            raise ValueError("empty segment produced while fitting piecewise trend")

        sigma_segment = sigma[mask] if sigma is not None else None
        fit = _fit_segment(x[mask], y[mask], sigma_segment)
        segments.append(SegmentResult(segment_id=segment_id, fit=fit))
        lower = upper

    return segments


def _score_segments(segments: list[SegmentResult], bic_metric: str) -> float:
    return float(sum(_rss_for_bic(segment.fit, bic_metric) for segment in segments))


def _segment_for_values(x: np.ndarray, breakpoints: list[float]) -> np.ndarray:
    if not breakpoints:
        return np.zeros(len(x), dtype=int)
    return np.searchsorted(np.asarray(breakpoints, dtype=float), x, side="left")


def fit_piecewise_trend(
    x,
    y,
    sigma=None,
    *,
    max_segments: int | None = 1,
    force_max_segments: bool = False,
    min_points: int = 10,
    min_years: float = 1.0,
    bic_metric: BicMetric = "auto",
) -> TrendResult:
    """Fit a BIC-selected piecewise linear trend.

    Parameters
    ----------
    x, y:
        One-dimensional arrays with time-like coordinates and observed values.
    sigma:
        Optional uncertainty array. If provided, each segment uses WLS with
        weights ``1 / sigma**2``. Otherwise each segment uses OLS.
    max_segments:
        Maximum allowed number of segments. The default ``1`` returns a single
        linear trend. ``2`` allows one breakpoint but keeps one segment when BIC
        does not improve. ``None`` keeps adding breakpoints greedily until BIC no
        longer improves or the ``min_points``/``min_years`` constraints stop it.
    force_max_segments:
        If ``True`` and ``max_segments`` is an integer, keep the best available
        split until exactly ``max_segments`` is reached or no valid split exists,
        even when BIC would prefer fewer segments. This is useful for exporting
        fixed model variants.
    min_points:
        Minimum number of valid observations required on each side of a split.
    min_years:
        Minimum distance in x-units from a candidate breakpoint to both segment
        edges. Set to ``0`` to disable this guard.
    bic_metric:
        Residual sum used by BIC: ``"rss"``, ``"wrss"`` or ``"auto"``.
    """
    if max_segments is not None and max_segments < 1:
        raise ValueError("max_segments must be >= 1 or None")
    if force_max_segments and max_segments is None:
        raise ValueError("force_max_segments=True requires an integer max_segments")
    if min_points < 2:
        raise ValueError("min_points must be >= 2")
    if min_years < 0:
        raise ValueError("min_years must be >= 0")

    x_arr = _as_float_array(x, "x")
    y_arr = _as_float_array(y, "y")

    if len(x_arr) != len(y_arr):
        raise ValueError("x and y must have the same length")

    sigma_arr = None
    if sigma is not None:
        sigma_arr = _as_float_array(sigma, "sigma")
        if len(sigma_arr) != len(x_arr):
            raise ValueError("sigma must have the same length as x and y")

    mask = _valid_mask(x_arr, y_arr, sigma_arr)
    if int(mask.sum()) < 2:
        raise ValueError("at least two valid points are required to fit a trend")

    x_valid = x_arr[mask]
    y_valid = y_arr[mask]
    sigma_valid = sigma_arr[mask] if sigma_arr is not None else None

    order = np.argsort(x_valid, kind="mergesort")
    x_sorted = x_valid[order]
    y_sorted = y_valid[order]
    sigma_sorted = sigma_valid[order] if sigma_valid is not None else None

    weighted = sigma_sorted is not None
    resolved_metric = _resolve_bic_metric(weighted, bic_metric)

    breakpoints: list[float] = []
    segments = _fit_segments_from_breakpoints(x_sorted, y_sorted, sigma_sorted, breakpoints)
    score = _score_segments(segments, resolved_metric)
    bic = bic_from_rss(n=len(x_sorted), rss=score, k=_k_params(len(segments)))

    while max_segments is None or len(segments) < max_segments:
        best_breakpoints = None
        best_segments = None
        best_score = np.inf
        best_bic = np.inf

        for segment in segments:
            if not force_max_segments and _rss_for_bic(segment.fit, resolved_metric) <= _SPLIT_SCORE_TOL:
                continue

            seg_mask = _segment_for_values(x_sorted, breakpoints) == segment.segment_id
            split = _best_split(
                x_sorted[seg_mask],
                y_sorted[seg_mask],
                sigma_sorted[seg_mask] if sigma_sorted is not None else None,
                min_points=min_points,
                min_years=min_years,
                bic_metric=resolved_metric,
            )
            if split is None:
                continue

            candidate_breakpoints = sorted([*breakpoints, split["tau"]])
            candidate_segments = _fit_segments_from_breakpoints(
                x_sorted,
                y_sorted,
                sigma_sorted,
                candidate_breakpoints,
            )
            candidate_score = _score_segments(candidate_segments, resolved_metric)
            candidate_bic = bic_from_rss(
                n=len(x_sorted),
                rss=candidate_score,
                k=_k_params(len(candidate_segments)),
            )

            if candidate_bic < best_bic:
                best_breakpoints = candidate_breakpoints
                best_segments = candidate_segments
                best_score = candidate_score
                best_bic = candidate_bic

        if best_segments is None or (best_bic >= bic and not force_max_segments):
            break

        breakpoints = best_breakpoints or []
        segments = best_segments
        score = best_score
        bic = best_bic

    if not force_max_segments:
        pruned = True
        while pruned and breakpoints:
            pruned = False
            for breakpoint in list(breakpoints):
                candidate_breakpoints = [value for value in breakpoints if value != breakpoint]
                candidate_segments = _fit_segments_from_breakpoints(
                    x_sorted,
                    y_sorted,
                    sigma_sorted,
                    candidate_breakpoints,
                )
                candidate_score = _score_segments(candidate_segments, resolved_metric)
                candidate_bic = bic_from_rss(
                    n=len(x_sorted),
                    rss=candidate_score,
                    k=_k_params(len(candidate_segments)),
                )
                if candidate_bic <= bic or (candidate_score <= _SPLIT_SCORE_TOL and score <= _SPLIT_SCORE_TOL):
                    breakpoints = candidate_breakpoints
                    segments = candidate_segments
                    score = candidate_score
                    bic = candidate_bic
                    pruned = True
                    break

    fitted = np.full_like(y_arr, np.nan, dtype=float)
    residuals = np.full_like(y_arr, np.nan, dtype=float)
    segment_ids = np.full(len(x_arr), -1, dtype=int)

    finite_x = np.isfinite(x_arr)
    value_segment_ids = _segment_for_values(x_arr[finite_x], breakpoints)
    segment_ids[finite_x] = value_segment_ids

    for segment in segments:
        seg_mask = finite_x & (segment_ids == segment.segment_id)
        fitted[seg_mask] = segment.intercept + segment.slope * x_arr[seg_mask]

    residuals[mask] = y_arr[mask] - fitted[mask]

    rss = float(np.nansum(residuals[mask] ** 2))
    if sigma_arr is not None:
        wrss = float(np.nansum((residuals[mask] / sigma_arr[mask]) ** 2))
    else:
        wrss = rss

    tss = float(np.sum((y_arr[mask] - np.mean(y_arr[mask])) ** 2))
    r2 = 1.0 - rss / tss if tss > 0 else 0.0

    return TrendResult(
        model="piecewise_linear" if len(segments) > 1 else "linear",
        segments=segments,
        breakpoints=breakpoints,
        bic=float(bic),
        bic_metric=resolved_metric,
        rss=rss,
        wrss=wrss,
        r2=float(r2),
        x=x_arr,
        y=y_arr,
        sigma=sigma_arr,
        fitted=fitted,
        residuals=residuals,
        valid_mask=mask,
        segment_id=segment_ids,
    )


def fit_linear_trend(
    x,
    y,
    sigma=None,
    *,
    bic_metric: BicMetric = "auto",
) -> TrendResult:
    """Fit one linear trend and compute fitted values, residuals and BIC."""
    return fit_piecewise_trend(
        x,
        y,
        sigma=sigma,
        max_segments=1,
        min_points=2,
        min_years=0.0,
        bic_metric=bic_metric,
    )
