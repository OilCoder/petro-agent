"""Effective porosity (PHIE) from the density-neutron crossplot.

Frozen, version-pinned, golden-tested. Degrades to single-curve porosity (density-only
or neutron-only) when one input is masked, so single-porosity wells (the 61 vintage
Schaben DEGRADE wells) still produce PHIE — the degradation is logged by the caller.
"""

import numpy as np

VERSION = "0.1.0"


def calc_phie(
    rhob: np.ndarray,
    nphi: np.ndarray,
    rho_ma: float,
    rho_fl: float,
    phie_max: float = 0.45,
) -> np.ndarray:
    """Compute effective porosity from bulk density and neutron porosity.

    ``phi_D = (rho_ma - rhob) / (rho_ma - rho_fl)``, ``PHIE = (phi_D + nphi) / 2``.
    Fallbacks: NaN ``nphi`` (density present) -> ``phi_D``; NaN ``rhob`` (neutron
    present) -> ``nphi``; both NaN -> NaN. Output clipped to ``[0, phie_max]``.

    Args:
        rhob: bulk density array (g/cc). NaN = masked.
        nphi: neutron porosity array (v/v). NaN = masked.
        rho_ma: matrix density (g/cc), e.g. 2.71 limestone.
        rho_fl: fluid density (g/cc), e.g. 1.00.
        phie_max: physical-plausibility ceiling (v/v).

    Returns:
        PHIE array in [0, phie_max] (NaN where both inputs are masked).

    Raises:
        ValueError: if ``rho_ma <= rho_fl``.
    """
    if rho_ma <= rho_fl:
        raise ValueError(f"rho_ma ({rho_ma}) must exceed rho_fl ({rho_fl})")

    rhob_arr = np.asarray(rhob, dtype=float)
    nphi_arr = np.asarray(nphi, dtype=float)

    phi_d = (rho_ma - rhob_arr) / (rho_ma - rho_fl)
    phie = (phi_d + nphi_arr) / 2.0

    # Substep — single-curve fallbacks
    density_only = np.isnan(nphi_arr) & ~np.isnan(rhob_arr)
    neutron_only = np.isnan(rhob_arr) & ~np.isnan(nphi_arr)
    phie[density_only] = phi_d[density_only]
    phie[neutron_only] = nphi_arr[neutron_only]
    phie[np.isnan(rhob_arr) & np.isnan(nphi_arr)] = np.nan

    return np.clip(phie, 0.0, phie_max)
