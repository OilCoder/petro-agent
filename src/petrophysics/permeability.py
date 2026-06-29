"""Log-based permeability estimators (UNCALIBRATED — no core).

Timur (1968) and Coates (1981) transforms from porosity and irreducible water saturation.
Frozen, version-pinned, golden-tested for physical behavior (monotonicity, bounds, NaN
passthrough). These are screening estimates: without core calibration the absolute value is
indicative only — the report must always state the uncalibrated caveat. The agent selects the
method; it never authors the number.
"""

import numpy as np

VERSION = "0.1.0"


def perm_timur(phie: np.ndarray, swirr: np.ndarray) -> np.ndarray:
    """Timur 1968 permeability (mD) from porosity and irreducible water saturation.

    ``k = 0.136 * (PHIE*100)**4.4 / (Swirr*100)**2`` (porosity/saturation as fractions).
    Increases with porosity, decreases with Swirr. Uncalibrated screening estimate.

    Args:
        phie: effective porosity (v/v). NaN propagates to NaN.
        swirr: irreducible water saturation proxy (v/v); clipped away from 0.

    Returns:
        Permeability array (mD), >= 0 (NaN where inputs are NaN).
    """
    phi = np.asarray(phie, dtype=float)
    swi = np.clip(np.asarray(swirr, dtype=float), 1e-3, 1.0)
    k = 0.136 * (phi * 100.0) ** 4.4 / (swi * 100.0) ** 2
    k = np.where(k < 0.0, 0.0, k)
    k[np.isnan(phi) | np.isnan(swirr)] = np.nan
    return k


def perm_coates(phie: np.ndarray, swirr: np.ndarray) -> np.ndarray:
    """Coates 1981 permeability (mD) from porosity and irreducible water saturation.

    ``k = (10 * PHIE**2 * (1 - Swirr) / Swirr)**2`` (porosity/saturation as fractions).
    Increases with porosity and with the free-fluid fraction (1 - Swirr). Uncalibrated.

    Args:
        phie: effective porosity (v/v). NaN propagates to NaN.
        swirr: irreducible water saturation proxy (v/v); clipped away from 0.

    Returns:
        Permeability array (mD), >= 0 (NaN where inputs are NaN).
    """
    phi = np.asarray(phie, dtype=float)
    swi = np.clip(np.asarray(swirr, dtype=float), 1e-3, 1.0)
    k = (10.0 * phi**2 * (1.0 - swi) / swi) ** 2
    k = np.where(k < 0.0, 0.0, k)
    k[np.isnan(phi) | np.isnan(swirr)] = np.nan
    return k
