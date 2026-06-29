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
    vsh: np.ndarray | None = None,
    phi_sh_d: float = 0.0,
    phi_sh_n: float = 0.0,
) -> np.ndarray:
    """Compute EFFECTIVE porosity from bulk density and neutron porosity.

    ``phi_D = (rho_ma - rhob) / (rho_ma - rho_fl)``. When ``vsh`` is supplied, each
    curve is shale-corrected with its shale-point reading before averaging
    (effective, not total, porosity)::

        phi_D_corr = phi_D - vsh * phi_sh_d
        phi_N_corr = nphi  - vsh * phi_sh_n
        PHIE = (phi_D_corr + phi_N_corr) / 2

    This subtracts clay-bound water so PHIE < PHIT in shaly rock and PHIE -> 0 as
    Vsh -> 1 (when the shale points equal the shale readings). With ``vsh=None`` the
    correction is skipped (total porosity) — backward-compatible.
    Fallbacks: NaN ``nphi`` (density present) -> ``phi_D_corr``; NaN ``rhob`` (neutron
    present) -> ``phi_N_corr``; both NaN -> NaN. Output clipped to ``[0, phie_max]``.

    Args:
        rhob: bulk density array (g/cc). NaN = masked.
        nphi: neutron porosity array (v/v). NaN = masked.
        rho_ma: matrix density (g/cc), e.g. 2.71 limestone.
        rho_fl: fluid density (g/cc), e.g. 1.00.
        phie_max: physical-plausibility ceiling (v/v).
        vsh: shale volume array (v/v) for the shale correction; None -> no correction.
        phi_sh_d: apparent density porosity in 100% shale (v/v).
        phi_sh_n: apparent neutron porosity in 100% shale (v/v).

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
    phi_n = nphi_arr

    # Substep — shale correction (effective porosity) when Vsh is provided
    if vsh is not None:
        vsh_arr = np.clip(np.asarray(vsh, dtype=float), 0.0, 1.0)
        phi_d = phi_d - vsh_arr * phi_sh_d
        phi_n = phi_n - vsh_arr * phi_sh_n

    phie = (phi_d + phi_n) / 2.0

    # Substep — single-curve fallbacks (use the shale-corrected curves)
    density_only = np.isnan(nphi_arr) & ~np.isnan(rhob_arr)
    neutron_only = np.isnan(rhob_arr) & ~np.isnan(nphi_arr)
    phie[density_only] = phi_d[density_only]
    phie[neutron_only] = phi_n[neutron_only]
    phie[np.isnan(rhob_arr) & np.isnan(nphi_arr)] = np.nan

    return np.clip(phie, 0.0, phie_max)


def phi_density(
    rhob: np.ndarray, rho_ma: float, rho_fl: float, phie_max: float = 0.45
) -> np.ndarray:
    """Compute density porosity from bulk density (single-curve, total porosity).

    ``phi_D = (rho_ma - rhob) / (rho_ma - rho_fl)``, clipped to ``[0, phie_max]``.

    Args:
        rhob: bulk density array (g/cc). NaN propagates to NaN.
        rho_ma: matrix density (g/cc).
        rho_fl: fluid density (g/cc).
        phie_max: physical-plausibility ceiling (v/v).

    Returns:
        Density porosity in [0, phie_max] (NaN where RHOB is NaN).

    Raises:
        ValueError: if ``rho_fl >= rho_ma``.
    """
    if rho_fl >= rho_ma:
        raise ValueError(f"rho_fl ({rho_fl}) must be below rho_ma ({rho_ma})")
    rhob_arr = np.asarray(rhob, dtype=float)
    phi = np.clip((rho_ma - rhob_arr) / (rho_ma - rho_fl), 0.0, phie_max)
    phi[np.isnan(rhob_arr)] = np.nan
    return phi


def phi_neutron(nphi: np.ndarray, phie_max: float = 0.45) -> np.ndarray:
    """Return neutron porosity (already in porosity units), clipped to ``[0, phie_max]``.

    Args:
        nphi: neutron porosity array (v/v). NaN propagates to NaN.
        phie_max: physical-plausibility ceiling (v/v).

    Returns:
        Neutron porosity in [0, phie_max] (NaN where NPHI is NaN).
    """
    nphi_arr = np.asarray(nphi, dtype=float)
    phi = np.clip(nphi_arr, 0.0, phie_max)
    phi[np.isnan(nphi_arr)] = np.nan
    return phi
