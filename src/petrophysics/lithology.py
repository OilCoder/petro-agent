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


# Plausible formation-water resistivity window (ohm-m) for the Rwa estimate.
RW_FLOOR, RW_CEIL = 0.01, 0.5

# Arps' constant for resistivity-temperature conversion in Celsius (6.77 in Fahrenheit).
_ARPS_C = 21.5


def rw_arps_temperature(
    rw_surface: float,
    t_surface_c: float,
    gradient_c_km: float,
    depth_m: float,
) -> dict[str, float]:
    """Correct a surface-conditions Rw to formation temperature via Arps' equation.

    ``Rw_f = Rw_s * (T_s + 21.5) / (T_f + 21.5)`` with temperatures in Celsius and the
    formation temperature from a linear geothermal gradient:
    ``T_f = T_s + gradient * depth/1000``. Salinity is assumed constant (Arps).

    Args:
        rw_surface: water resistivity at surface temperature (ohm-m).
        t_surface_c: mean surface temperature (Celsius).
        gradient_c_km: geothermal gradient (Celsius per km).
        depth_m: formation depth (m).

    Returns:
        ``{rw_formation, t_formation_c}``.

    Raises:
        ValueError: If ``rw_surface`` is not positive.
    """
    if rw_surface <= 0.0:
        raise ValueError(f"rw_surface must be positive, got {rw_surface}")
    t_f = t_surface_c + gradient_c_km * depth_m / 1000.0
    rw_f = rw_surface * (t_surface_c + _ARPS_C) / (t_f + _ARPS_C)
    return {"rw_formation": round(float(rw_f), 5), "t_formation_c": round(float(t_f), 2)}


# M-N crossplot fluid points (fresh mud): DT_fl (µs/ft), RHOB_fl (g/cc), NPHI_fl (v/v).
_MN_FLUID = {"dt_fl": 189.0, "rho_fl": 1.0, "nphi_fl": 1.0}
# Reference M-N matrix points (fresh mud, standard chart values).
MN_MATRIX_POINTS = {
    "quartz": {"m": 0.81, "n": 0.63},
    "calcite": {"m": 0.83, "n": 0.59},
    "dolomite": {"m": 0.78, "n": 0.52},
}


def litho_mn(
    rhob: np.ndarray,
    nphi: np.ndarray,
    dt: np.ndarray,
    dt_fl: float = 189.0,
    rho_fl: float = 1.0,
    nphi_fl: float = 1.0,
) -> dict[str, object]:
    """Compute M-N lithology values and nearest-matrix point shares (porosity-independent).

    ``M = 0.01 * (DT_fl - DT) / (RHOB - RHO_fl)`` and ``N = (NPHI_fl - NPHI) / (RHOB -
    RHO_fl)`` collapse porosity so points cluster by mineralogy; each sample is assigned
    to the nearest reference matrix point (quartz/calcite/dolomite).

    Args:
        rhob: bulk density (g/cc). nphi: neutron porosity (v/v). dt: sonic slowness (µs/ft).
        dt_fl: fluid slowness (µs/ft). rho_fl: fluid density (g/cc). nphi_fl: fluid neutron.

    Returns:
        ``{m, n, shares, n_samples}`` — M/N arrays (NaN where undefined) and the fraction
        of classified samples nearest each matrix point.
    """
    rhob_a = np.asarray(rhob, dtype=float)
    nphi_a = np.asarray(nphi, dtype=float)
    dt_a = np.asarray(dt, dtype=float)
    denom = rhob_a - rho_fl
    with np.errstate(divide="ignore", invalid="ignore"):
        m_val = 0.01 * (dt_fl - dt_a) / denom
        n_val = (nphi_fl - nphi_a) / denom
    bad = ~np.isfinite(m_val) | ~np.isfinite(n_val) | (denom <= 0.05)
    m_val[bad] = np.nan
    n_val[bad] = np.nan

    ok = np.isfinite(m_val) & np.isfinite(n_val)
    shares: dict[str, float] = {}
    n_ok = int(np.count_nonzero(ok))
    if n_ok:
        names = list(MN_MATRIX_POINTS)
        dists = np.stack(
            [
                (m_val[ok] - MN_MATRIX_POINTS[k]["m"]) ** 2
                + (n_val[ok] - MN_MATRIX_POINTS[k]["n"]) ** 2
                for k in names
            ]
        )
        nearest = np.argmin(dists, axis=0)
        shares = {k: round(float(np.mean(nearest == i)), 3) for i, k in enumerate(names)}
    return {"m": m_val, "n": n_val, "shares": shares, "n_samples": n_ok}


# Umaa matrix points (barns/cc): standard chart values for the apparent-matrix crossplot.
UMAA_MATRIX_POINTS = {"quartz": 4.8, "calcite": 13.8, "dolomite": 9.0}
_U_FLUID = 0.5  # fresh-water fluid volumetric cross-section (barns/cc)


def umaa_apparent(
    pef: np.ndarray,
    rhob: np.ndarray,
    phit: np.ndarray,
) -> dict[str, object]:
    """Compute apparent matrix volumetric cross-section (Umaa) and matrix point shares.

    ``U = PEF * rho_e`` with ``rho_e ≈ RHOB`` (electron-density approximation), then
    ``Umaa = (U - PHIT * U_fl) / (1 - PHIT)``. Each sample is assigned to the nearest
    reference matrix (quartz 4.8, calcite 13.8, dolomite 9.0 barns/cc).

    Args:
        pef: photoelectric factor (barns/electron).
        rhob: bulk density (g/cc).
        phit: total porosity estimate (v/v) — neutron-density porosity is acceptable.

    Returns:
        ``{umaa, shares, n_samples}`` — Umaa array (NaN where undefined) and nearest-point
        shares over classified samples.
    """
    pef_a = np.asarray(pef, dtype=float)
    rhob_a = np.asarray(rhob, dtype=float)
    phit_a = np.clip(np.asarray(phit, dtype=float), 0.0, 0.6)
    with np.errstate(divide="ignore", invalid="ignore"):
        u = pef_a * rhob_a
        umaa = (u - phit_a * _U_FLUID) / (1.0 - phit_a)
    umaa[~np.isfinite(umaa)] = np.nan

    ok = np.isfinite(umaa)
    shares: dict[str, float] = {}
    n_ok = int(np.count_nonzero(ok))
    if n_ok:
        names = list(UMAA_MATRIX_POINTS)
        dists = np.stack([np.abs(umaa[ok] - UMAA_MATRIX_POINTS[k]) for k in names])
        nearest = np.argmin(dists, axis=0)
        shares = {k: round(float(np.mean(nearest == i)), 3) for i, k in enumerate(names)}
    return {"umaa": umaa, "shares": shares, "n_samples": n_ok}


def estimate_rw(
    rt: np.ndarray,
    phie: np.ndarray,
    vsh: np.ndarray,
    a: float,
    m: float,
    default: float,
) -> tuple[float, bool]:
    """Estimate Rw from the apparent water resistivity in clean, porous, wet rock.

    Archie at Sw=1 gives ``Rwa = RT * PHIE**m / a``. In a water zone Sw≈1 so Rwa≈Rw;
    the low percentile of Rwa over clean porous rock approximates Rw (the wettest, most
    conductive intervals). This replaces the flat regional default — the dominant net-pay
    uncertainty — with a data-driven value.

    Args:
        rt: deep resistivity (ohm-m).
        phie: effective porosity (v/v).
        vsh: shale volume (v/v).
        a: Archie tortuosity factor.
        m: Archie cementation exponent.
        default: regional fallback Rw when too few clean porous samples.

    Returns:
        ``(rw, data_driven)`` with rw clipped to the plausible window.
    """
    rt_arr = np.asarray(rt, dtype=float)
    phie_arr = np.asarray(phie, dtype=float)
    vsh_arr = np.asarray(vsh, dtype=float)
    clean_porous = (
        (vsh_arr < 0.3)
        & (phie_arr > 0.08)
        & np.isfinite(rt_arr)
        & np.isfinite(phie_arr)
        & (rt_arr > 0)
    )
    if int(clean_porous.sum()) < MIN_SAMPLES:
        return default, False
    rwa = rt_arr[clean_porous] * phie_arr[clean_porous] ** m / a  # Archie Sw=1: Rwa
    rw = float(np.percentile(rwa, 10))
    return float(np.clip(rw, RW_FLOOR, RW_CEIL)), True
