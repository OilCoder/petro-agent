"""Cutoff-driven net-pay aggregation. Frozen, golden-tested.

These are deterministic cutoff/aggregation functions over the three core engine
outputs (Vsh/PHIE/Sw) — NOT new petrophysical equations. They surface the three-tier
net-sand >= net-reservoir >= net-pay hierarchy and net-to-gross.
"""

import numpy as np

VERSION = "0.1.0"


def apply_cutoffs(
    vsh: np.ndarray,
    phie: np.ndarray,
    sw: np.ndarray,
    vsh_cutoff: float,
    phie_cutoff: float,
    sw_cutoff: float,
) -> np.ndarray:
    """Per-depth net-PAY flag: ``Vsh<=vsh_cutoff & PHIE>=phie_cutoff & Sw<=sw_cutoff``.

    Cutoffs are boundary-inclusive. Any NaN (EXCLUDED) sample flags False.
    """
    vsh_a = np.asarray(vsh, dtype=float)
    phie_a = np.asarray(phie, dtype=float)
    sw_a = np.asarray(sw, dtype=float)
    with np.errstate(invalid="ignore"):
        flag = (vsh_a <= vsh_cutoff) & (phie_a >= phie_cutoff) & (sw_a <= sw_cutoff)
    flag &= ~(np.isnan(vsh_a) | np.isnan(phie_a) | np.isnan(sw_a))
    return flag


def _net_sand_flag(vsh: np.ndarray, vsh_cutoff: float) -> np.ndarray:
    vsh_a = np.asarray(vsh, dtype=float)
    with np.errstate(invalid="ignore"):
        flag = vsh_a <= vsh_cutoff
    return flag & ~np.isnan(vsh_a)


def _net_reservoir_flag(
    vsh: np.ndarray, phie: np.ndarray, vsh_cutoff: float, phie_cutoff: float
) -> np.ndarray:
    vsh_a = np.asarray(vsh, dtype=float)
    phie_a = np.asarray(phie, dtype=float)
    with np.errstate(invalid="ignore"):
        flag = (vsh_a <= vsh_cutoff) & (phie_a >= phie_cutoff)
    return flag & ~(np.isnan(vsh_a) | np.isnan(phie_a))


def compute_net_pay(flag: np.ndarray, step: float) -> float:
    """Net-pay thickness = ``sum(flag) * step`` (metres)."""
    return float(np.count_nonzero(np.asarray(flag, dtype=bool)) * step)


def net_sand(vsh: np.ndarray, vsh_cutoff: float, step: float) -> float:
    """Net-sand thickness (Vsh cutoff only), metres."""
    return float(np.count_nonzero(_net_sand_flag(vsh, vsh_cutoff)) * step)


def net_reservoir(
    vsh: np.ndarray,
    phie: np.ndarray,
    vsh_cutoff: float,
    phie_cutoff: float,
    step: float,
) -> float:
    """Net-reservoir thickness (Vsh + PHIE cutoffs), metres."""
    return float(
        np.count_nonzero(_net_reservoir_flag(vsh, phie, vsh_cutoff, phie_cutoff)) * step
    )


def net_to_gross(net_m: float, gross_m: float) -> float:
    """Net-to-gross ratio with a zero-gross guard (returns 0.0 if gross is 0)."""
    if gross_m <= 0.0:
        return 0.0
    return net_m / gross_m
