"""Hydrocarbon volumetrics. Frozen, golden-tested.

Deterministic aggregation arithmetic over PHIE and Sw on net-pay depths — not new
petrophysical equations.
"""

import numpy as np

VERSION = "0.1.0"


def bvw(phie: np.ndarray, sw: np.ndarray) -> np.ndarray:
    """Per-depth bulk-volume water = ``PHIE * Sw`` (v/v). NaN propagates."""
    return np.asarray(phie, dtype=float) * np.asarray(sw, dtype=float)


def hcpv(
    phie: np.ndarray,
    sw: np.ndarray,
    flag: np.ndarray,
    step: float,
) -> float:
    """Net hydrocarbon pore thickness over net-pay depths.

    ``HCPV = sum( PHIE * (1 - Sw) * step )`` integrated only where ``flag`` is True.
    NaN samples within the flag are skipped (treated as no contribution).

    Args:
        phie: effective porosity (v/v).
        sw: water saturation (v/v).
        flag: per-depth net-pay boolean flag.
        step: depth sampling interval (m).

    Returns:
        Net hydrocarbon pore thickness (m·v/v).
    """
    phie_a = np.asarray(phie, dtype=float)
    sw_a = np.asarray(sw, dtype=float)
    flag_a = np.asarray(flag, dtype=bool)
    contrib = phie_a * (1.0 - sw_a)
    mask = flag_a & ~np.isnan(contrib)
    return float(np.sum(contrib[mask]) * step)
