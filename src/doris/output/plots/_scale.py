"""Axis scale helpers used by exported Matplotlib plots."""

from __future__ import annotations

from typing import Dict, Sequence, Tuple

import numpy as np
import pandas as pd
from matplotlib.ticker import FormatStrFormatter, MultipleLocator


def _nice_step(x: float) -> float:
    """Return a pleasant tick step close to ``x``."""
    if x <= 0 or not np.isfinite(x):
        return 1.0

    power = np.floor(np.log10(x))
    base = x / 10**power

    if base <= 1:
        nice = 1.0
    elif base <= 2:
        nice = 2.0
    elif base <= 2.5:
        nice = 2.5
    elif base <= 5:
        nice = 5.0
    else:
        nice = 10.0

    return float(nice * 10**power)


def _series_min_max(
    y: np.ndarray,
    robust: bool = False,
    q_low: float = 1.0,
    q_high: float = 99.0,
) -> Tuple[float, float]:
    """Return finite min/max values for a 1D array."""
    values = np.asarray(y, dtype=float)
    values = values[np.isfinite(values)]

    if values.size == 0:
        return np.nan, np.nan

    if robust:
        lo, hi = np.percentile(values, [q_low, q_high])
        return float(lo), float(hi)

    return float(np.min(values)), float(np.max(values))


def _infer_x_from_axes(ax) -> np.ndarray:
    """Collect finite X data from all lines in one Matplotlib axis."""
    x_parts = []

    for line in ax.get_lines():
        x_data = np.asarray(line.get_xdata(orig=False), dtype=float)
        if x_data.size:
            x_parts.append(x_data)

    if not x_parts:
        return np.array([], dtype=float)

    x = np.concatenate(x_parts)
    return x[np.isfinite(x)]


def uniform_y_scale_policy(
    axes,
    df: pd.DataFrame,
    components: Sequence[str],
    tick_step: float | None = None,
    target_ticks: int = 6,
    tightness: str = "tight",
    min_ticks: int = 3,
    robust: bool = True,
    q_low: float = 1.0,
    q_high: float = 99.0,
) -> Tuple[float, float]:
    """Apply a shared Y tick step and window height to multiple subplots."""
    spans = []
    y_stats: Dict[str, Dict[str, float | bool]] = {}

    for comp in components:
        y = pd.to_numeric(df[comp], errors="coerce").to_numpy()
        y_min, y_max = _series_min_max(y, robust=robust, q_low=q_low, q_high=q_high)

        if not np.isfinite(y_min) or not np.isfinite(y_max):
            y_stats[comp] = {"ok": False, "y_mid": 0.0, "span": 0.0}
            continue

        span = float(y_max - y_min)
        midpoint = float(0.5 * (y_min + y_max))
        spans.append(span)
        y_stats[comp] = {"ok": True, "y_mid": midpoint, "span": span}

    max_span = max(spans) if spans else 1.0

    if tick_step is None:
        rough_step = max_span / max(int(target_ticks), 1)
        tick_step = _nice_step(rough_step)

    pad_by_tightness = {"tight": 0.5, "medium": 1.0, "loose": 2.0}
    pad_ticks_total = float(pad_by_tightness.get(tightness, 0.5))

    needed_ticks_for_span = int(np.ceil(max_span / tick_step))
    total_ticks = int(
        max(np.ceil(needed_ticks_for_span + pad_ticks_total), int(min_ticks))
    )
    common_window = float(total_ticks * tick_step)

    for ax, comp in zip(np.atleast_1d(axes), components):
        stats = y_stats.get(comp, {"ok": False, "y_mid": 0.0})
        midpoint = float(stats.get("y_mid", 0.0))
        half_window = 0.5 * common_window

        y_lo = np.floor((midpoint - half_window) / tick_step) * tick_step
        y_hi = y_lo + total_ticks * tick_step

        if (y_hi - y_lo) / tick_step < float(min_ticks):
            centered_midpoint = 0.5 * (y_lo + y_hi)
            y_lo = centered_midpoint - 0.5 * min_ticks * tick_step
            y_hi = centered_midpoint + 0.5 * min_ticks * tick_step

        ax.set_ylim(y_lo, y_hi)
        ax.yaxis.set_major_locator(MultipleLocator(tick_step))

    return float(tick_step), float(common_window)


def set_unit_ticks(
    axes,
    step: float = 1.0,
    snap: bool = True,
    integer_labels: bool = True,
    minor: float | None = None,
    x_values: pd.Series | np.ndarray | None = None,
) -> None:
    """Set a uniform X tick spacing for all given Matplotlib axes."""
    for ax in np.atleast_1d(axes):
        if x_values is None:
            x = _infer_x_from_axes(ax)
        else:
            x = pd.to_numeric(np.asarray(x_values), errors="coerce")
            x = x[np.isfinite(x)]

        if x.size == 0:
            ax.xaxis.set_major_locator(MultipleLocator(step))
            if integer_labels:
                ax.xaxis.set_major_formatter(FormatStrFormatter("%.0f"))
            if minor is not None:
                ax.xaxis.set_minor_locator(MultipleLocator(minor))
            continue

        x_min = float(np.min(x))
        x_max = float(np.max(x))

        if snap:
            x_lo = np.floor(x_min / step) * step
            x_hi = np.ceil(x_max / step) * step
        else:
            x_lo, x_hi = x_min, x_max

        ax.set_xlim(x_lo, x_hi)
        ax.xaxis.set_major_locator(MultipleLocator(step))

        if integer_labels:
            ax.xaxis.set_major_formatter(FormatStrFormatter("%.0f"))
        if minor is not None:
            ax.xaxis.set_minor_locator(MultipleLocator(minor))

