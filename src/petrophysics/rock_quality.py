"""Rock-quality indices derived from porosity and permeability (UNCALIBRATED).

RQI / FZI (Amaefule 1993) and Winland R35 — flow-unit and pore-throat indicators built on a
log-based permeability, so they inherit its uncalibrated caveat. Frozen, golden-tested for
physical behavior. The agent selects; the engine computes.
"""

import numpy as np

VERSION = "0.1.0"


def rqi(k: np.ndarray, phie: np.ndarray) -> np.ndarray:
    """Reservoir Quality Index (µm): ``RQI = 0.0314 * sqrt(k / PHIE)`` (k in mD, PHIE v/v).

    Args:
        k: permeability (mD). NaN propagates to NaN.
        phie: effective porosity (v/v); clipped away from 0.

    Returns:
        RQI array (µm), >= 0 (NaN where inputs are NaN).
    """
    k_arr = np.asarray(k, dtype=float)
    phi = np.clip(np.asarray(phie, dtype=float), 1e-6, 1.0)
    out = 0.0314 * np.sqrt(np.clip(k_arr / phi, 0.0, None))
    out[np.isnan(k_arr) | np.isnan(phie)] = np.nan
    return out


def fzi(k: np.ndarray, phie: np.ndarray) -> np.ndarray:
    """Flow Zone Indicator (µm): ``FZI = RQI / phiz``, ``phiz = PHIE / (1 - PHIE)``.

    Args:
        k: permeability (mD). NaN propagates to NaN.
        phie: effective porosity (v/v); clipped to (0, 1).

    Returns:
        FZI array (µm), >= 0 (NaN where inputs are NaN).
    """
    phi = np.clip(np.asarray(phie, dtype=float), 1e-6, 1.0 - 1e-6)
    phiz = phi / (1.0 - phi)
    out = rqi(k, phie) / phiz
    return out


def winland_r35(k: np.ndarray, phie: np.ndarray) -> np.ndarray:
    """Winland R35 pore-throat radius (µm).

    ``log10(R35) = 0.732 + 0.588*log10(k) - 0.864*log10(PHIE%)`` (k in mD, PHIE in %).

    Args:
        k: permeability (mD); clipped away from 0. NaN propagates to NaN.
        phie: effective porosity (v/v); clipped away from 0.

    Returns:
        R35 array (µm), >= 0 (NaN where inputs are NaN).
    """
    k_arr = np.asarray(k, dtype=float)
    phi = np.asarray(phie, dtype=float)
    k_c = np.clip(k_arr, 1e-6, None)
    phi_c = np.clip(phi, 1e-6, 1.0)
    log_r35 = 0.732 + 0.588 * np.log10(k_c) - 0.864 * np.log10(phi_c * 100.0)
    out = 10.0**log_r35
    out[np.isnan(k_arr) | np.isnan(phi)] = np.nan
    return out
