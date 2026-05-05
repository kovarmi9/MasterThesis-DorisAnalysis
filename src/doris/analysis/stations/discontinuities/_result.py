"""Result container for jump/discontinuity detection."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class JumpDetectionResult:
    """Holds the output of a jump-detection run.

    Attributes
    ----------
    jumps : np.ndarray
        Detected jump epochs in decimal years.
    method : str
        ``"sliding_window"`` or ``"lowess_derivative"``.
    threshold : float | None
        Numeric cutoff applied: ``k·σ`` for heuristic mode, critical slope
        (``z_{α/2}·σ_slope``, floored by *min_abs*) for ``"z_test"``, or
        *alpha* for ``"t_test"``.
    threshold_mode : str
        One of ``"heuristic"``, ``"t_test"``, ``"z_test"``.
    alpha : float | None
        Significance level used for statistical tests; ``None`` in heuristic
        mode.
    extras : dict
        Method-specific intermediate results needed for plotting.

        Sliding-window keys: ``mu1``, ``mu2``, ``years1``, ``years2``,
        ``sigma``, ``pvalues``, ``window_size``, ``shift``.

        LOWESS-derivative keys: ``smoothed``, ``t_mid``, ``slope``,
        ``sigma_slope``, ``frac``, ``min_abs``.
    """

    jumps: np.ndarray
    method: str
    threshold: float | None
    threshold_mode: str
    alpha: float | None
    extras: dict = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.jumps)

    def __repr__(self) -> str:
        return (
            f"JumpDetectionResult(method={self.method!r}, "
            f"n_jumps={len(self.jumps)}, "
            f"threshold_mode={self.threshold_mode!r}, "
            f"threshold={self.threshold})"
        )
