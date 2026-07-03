"""Hydrocarbon volumetrics. Frozen, golden-tested.

Deterministic aggregation arithmetic over PHIE and Sw on net-pay depths — not new
petrophysical equations.
"""

import numpy as np

VERSION = "0.1.0"


def bvw(phie: np.ndarray, sw: np.ndarray) -> np.ndarray:
    """Per-depth bulk-volume water = ``PHIE * Sw`` (v/v). NaN propagates."""
    return np.asarray(phie, dtype=float) * np.asarray(sw, dtype=float)


def phi_h(phie: np.ndarray, flag: np.ndarray, step: float) -> float:
    """Porosity-thickness (Phi·H) over net-pay depths.

    ``Phi_H = sum( PHIE * step )`` integrated only where ``flag`` is True. NaN samples
    within the flag are skipped (no contribution).

    Args:
        phie: effective porosity (v/v).
        flag: per-depth net-pay boolean flag.
        step: depth sampling interval (m).

    Returns:
        Porosity-thickness (m·v/v).
    """
    phie_a = np.asarray(phie, dtype=float)
    mask = np.asarray(flag, dtype=bool) & ~np.isnan(phie_a)
    return float(np.sum(phie_a[mask]) * step)


def swirr_buckles(
    phie: np.ndarray,
    sw: np.ndarray,
    flag: np.ndarray,
    pct: float = 10.0,
) -> dict[str, float]:
    """Estimate irreducible water saturation via a constant-BVW (Buckles) fit on net pay.

    In rock at irreducible conditions ``PHIE * Sw`` clusters on a constant (the Buckles
    number). The estimator takes the ``pct``-th percentile of BVW over the net-pay flag —
    a low percentile isolates the samples closest to irreducible — and derives the mean
    irreducible saturation as ``buckles / mean(PHIE_pay)``.

    Args:
        phie: effective porosity (v/v).
        sw: water saturation (v/v).
        flag: per-depth net-pay boolean flag.
        pct: percentile of pay BVW taken as the Buckles constant (low = closest to Swirr).

    Returns:
        ``{buckles, swirr_mean, n_pay}`` — NaN buckles/swirr when no finite pay samples.
    """
    phie_a = np.asarray(phie, dtype=float)
    sw_a = np.asarray(sw, dtype=float)
    pay = np.asarray(flag, dtype=bool)
    b = phie_a * sw_a
    finite = pay & np.isfinite(b) & np.isfinite(phie_a) & (phie_a > 0.0)
    n = int(np.count_nonzero(finite))
    if n == 0:
        return {"buckles": float("nan"), "swirr_mean": float("nan"), "n_pay": 0}
    buckles = float(np.percentile(b[finite], pct))
    swirr = float(np.clip(buckles / float(np.mean(phie_a[finite])), 0.0, 1.0))
    return {"buckles": round(buckles, 4), "swirr_mean": round(swirr, 4), "n_pay": n}


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
