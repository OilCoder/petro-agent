"""Sonic porosity methods (Wyllie time-average, Raymer-Hunt-Gardner).

Vetted alternatives to density/neutron porosity when a sonic (DT) curve is present.
Frozen, version-pinned, golden-tested. Selected by the agent only when DT is available.
"""

import numpy as np

VERSION = "0.1.0"


def phi_sonic_wyllie(
    dt: np.ndarray, dt_matrix: float, dt_fluid: float, phie_max: float = 0.45
) -> np.ndarray:
    """Compute porosity via the Wyllie time-average equation.

    ``PHI = (DT - DT_matrix) / (DT_fluid - DT_matrix)``, clipped to ``[0, phie_max]``.
    Best in consolidated, clean formations.

    Args:
        dt: sonic interval transit time (µs/ft). NaN propagates to NaN.
        dt_matrix: matrix transit time (µs/ft), e.g. 47.5 limestone, 55.5 sandstone.
        dt_fluid: fluid transit time (µs/ft), e.g. 189.
        phie_max: physical-plausibility ceiling (v/v).

    Returns:
        Porosity array in [0, phie_max] (NaN where DT is NaN).

    Raises:
        ValueError: if ``dt_fluid <= dt_matrix``.
    """
    if dt_fluid <= dt_matrix:
        raise ValueError(f"dt_fluid ({dt_fluid}) must exceed dt_matrix ({dt_matrix})")
    dt_arr = np.asarray(dt, dtype=float)
    phi = (dt_arr - dt_matrix) / (dt_fluid - dt_matrix)
    phi = np.clip(phi, 0.0, phie_max)
    phi[np.isnan(dt_arr)] = np.nan
    return phi


def phi_sonic_rhg(
    dt: np.ndarray, dt_matrix: float, c: float = 0.67, phie_max: float = 0.45
) -> np.ndarray:
    """Compute porosity via the Raymer-Hunt-Gardner transform.

    ``PHI = C * (DT - DT_matrix) / DT``, clipped to ``[0, phie_max]``. More accurate than
    Wyllie in unconsolidated or high-porosity rock (``C`` ~ 0.67).

    Args:
        dt: sonic interval transit time (µs/ft). NaN propagates to NaN.
        dt_matrix: matrix transit time (µs/ft).
        c: RHG empirical constant (~0.67).
        phie_max: physical-plausibility ceiling (v/v).

    Returns:
        Porosity array in [0, phie_max] (NaN where DT is NaN).
    """
    dt_arr = np.asarray(dt, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        phi = c * (dt_arr - dt_matrix) / dt_arr
    phi = np.clip(phi, 0.0, phie_max)
    phi[np.isnan(dt_arr) | (dt_arr <= 0.0)] = np.nan
    return phi
