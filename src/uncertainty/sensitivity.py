"""One-at-a-time sensitivity: which parameter dominates net pay.

This is where automation beats the manual report: if net pay is dominated by a
parameter that is only a regional default, the report must SHOUT it.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from src.petrophysics.netpay import apply_cutoffs, compute_net_pay
from src.petrophysics.sw import calc_sw
from src.uncertainty.montecarlo import DEFAULT_RANGES

VERSION = "0.1.0"


def _net_pay_at(
    vsh: np.ndarray,
    phie: np.ndarray,
    rt: np.ndarray,
    params: dict[str, float],
    cutoffs: dict[str, float],
    step: float,
) -> float:
    sw = calc_sw(rt, phie, params["a"], params["m"], params["n"], params["Rw"])
    flag = apply_cutoffs(
        vsh, phie, sw, cutoffs["vsh_cutoff"], cutoffs["phie_cutoff"], cutoffs["sw_cutoff"]
    )
    return compute_net_pay(flag, step)


def sensitivity_net_pay(
    vsh: np.ndarray,
    phie: np.ndarray,
    rt: np.ndarray,
    base: dict[str, float],
    cutoffs: dict[str, float],
    step: float,
    ranges: dict[str, tuple[float, float]] | None = None,
) -> dict[str, Any]:
    """Rank parameters by the net-pay swing across their range (others held at base)."""
    ranges = ranges or DEFAULT_RANGES
    swings: dict[str, float] = {}
    for key, (lo, hi) in ranges.items():
        np_lo = _net_pay_at(vsh, phie, rt, {**base, key: lo}, cutoffs, step)
        np_hi = _net_pay_at(vsh, phie, rt, {**base, key: hi}, cutoffs, step)
        swings[key] = abs(np_hi - np_lo)
    dominant = max(swings, key=lambda k: swings[k]) if swings else None
    return {
        "swings_m": {k: float(v) for k, v in swings.items()},
        "dominant_parameter": dominant,
        "dominant_swing_m": float(swings[dominant]) if dominant else 0.0,
    }
