"""Data-driven matrix density and shale endpoints (deterministic, golden-tested).

The regional defaults assume a fixed limestone matrix (2.71) and guessed shale
porosities. On real Schaben data the matrix reads sandstone (~2.63-2.65) and the shale
points vary per well. These estimators derive both from the QC'd curves so PHIE is
parameterized to the rock actually logged — replacing the never-wired LLM compute agent
with deterministic code (the invariant: the engine selects parameters, it never guesses).
"""

from __future__ import annotations

import numpy as np

VERSION = "0.1.0"

# Clean rock = low shale volume; shale = high shale volume. Endpoints are read in each band.
VSH_CLEAN_MAX = 0.25
VSH_SHALE_MIN = 0.75
MIN_SAMPLES = 20
# Plausible matrix-density window (sandstone ~2.65 to dolomite ~2.87); guards dense streaks.
RHO_MA_FLOOR, RHO_MA_CEIL = 2.55, 2.95


def estimate_matrix_density(
    rhob: np.ndarray, vsh: np.ndarray, default: float
) -> tuple[float, bool]:
    """Estimate matrix density from bulk density in clean, low-porosity rock.

    Matrix density is the RHOB reading at zero porosity. In clean rock (low Vsh) the
    densest readings approach the matrix, so the high percentile of clean RHOB is a
    robust proxy, clipped to a plausible window.

    Args:
        rhob: bulk density array (g/cc); NaN = masked.
        vsh: shale volume array (v/v).
        default: regional fallback matrix density when too few clean samples.

    Returns:
        ``(rho_ma, data_driven)`` — the estimate and whether the data drove it.
    """
    rhob_arr = np.asarray(rhob, dtype=float)
    vsh_arr = np.asarray(vsh, dtype=float)
    clean = (vsh_arr <= VSH_CLEAN_MAX) & ~np.isnan(rhob_arr)
    if int(clean.sum()) < MIN_SAMPLES:
        return default, False
    rho_ma = float(np.percentile(rhob_arr[clean], 90))
    return float(np.clip(rho_ma, RHO_MA_FLOOR, RHO_MA_CEIL)), True


def estimate_shale_points(
    rhob: np.ndarray,
    nphi: np.ndarray,
    vsh: np.ndarray,
    rho_ma: float,
    rho_fl: float,
    default_phi_sh_d: float,
    default_phi_sh_n: float,
) -> tuple[float, float, bool]:
    """Estimate the apparent density/neutron porosity in 100% shale from high-Vsh rock.

    The shale points anchor the effective-porosity correction so PHIE -> 0 in pure shale.
    They are read as the median curve response where Vsh is high.

    Args:
        rhob: bulk density array (g/cc).
        nphi: neutron porosity array (v/v).
        vsh: shale volume array (v/v).
        rho_ma: matrix density used to convert shale RHOB to apparent density porosity.
        rho_fl: fluid density (g/cc).
        default_phi_sh_d: regional fallback density shale point.
        default_phi_sh_n: regional fallback neutron shale point.

    Returns:
        ``(phi_sh_d, phi_sh_n, data_driven)`` clipped to [0, 1].
    """
    rhob_arr = np.asarray(rhob, dtype=float)
    nphi_arr = np.asarray(nphi, dtype=float)
    vsh_arr = np.asarray(vsh, dtype=float)
    shale = vsh_arr >= VSH_SHALE_MIN

    shale_d = shale & ~np.isnan(rhob_arr)
    shale_n = shale & ~np.isnan(nphi_arr)
    if int(shale_d.sum()) < MIN_SAMPLES or int(shale_n.sum()) < MIN_SAMPLES:
        return default_phi_sh_d, default_phi_sh_n, False

    rhob_sh = float(np.median(rhob_arr[shale_d]))
    phi_sh_d = (rho_ma - rhob_sh) / (rho_ma - rho_fl)
    phi_sh_n = float(np.median(nphi_arr[shale_n]))
    return float(np.clip(phi_sh_d, 0.0, 1.0)), float(np.clip(phi_sh_n, 0.0, 1.0)), True
