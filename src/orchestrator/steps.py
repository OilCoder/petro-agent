"""Discrete petrophysical compute steps — the shared primitives of the pipeline AND the loop.

Each step computes ONE property from the accumulated state using the vetted, golden-tested
functions, and returns ``(array, calibration_fragment)``. ``stages.compute()`` composes them in
the default order, and the agentic loop calls the same steps one at a time — so the guided
pipeline and the free loop share ONE source of truth (no divergence by construction). The agent
selects the method id; the frozen function produces the number (the invariant holds).
"""

from __future__ import annotations

from typing import Any

import numpy as np

from src.petrophysics.lithology import (
    estimate_matrix_density,
    estimate_rw,
    estimate_shale_points,
)
from src.petrophysics.phie import calc_phie, phi_density, phi_neutron
from src.petrophysics.sw import calc_sw, sw_indonesia, sw_simandoux
from src.petrophysics.vsh import (
    OLD_ROCKS,
    TERTIARY,
    calc_vsh,
    vsh_clavier,
    vsh_linear,
    vsh_steiber,
)


def vsh_step(
    curves: dict[str, np.ndarray],
    gr_min: float,
    gr_max: float,
    variant: str,
    method: str | None = None,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Compute Vsh with the selected vetted method (default = the engine's Larionov variant)."""
    gr = curves["GR"]
    if method == "vsh_linear":
        arr = vsh_linear(gr, gr_min, gr_max)
    elif method == "vsh_clavier":
        arr = vsh_clavier(gr, gr_min, gr_max)
    elif method == "vsh_steiber":
        arr = vsh_steiber(gr, gr_min, gr_max)
    elif method == "vsh_larionov_tertiary":
        arr = calc_vsh(gr, gr_min, gr_max, TERTIARY)
    elif method == "vsh_larionov_old":
        arr = calc_vsh(gr, gr_min, gr_max, OLD_ROCKS)
    else:
        arr = calc_vsh(gr, gr_min, gr_max, variant)
    cal = {
        "vsh_method": {
            "value": method or f"vsh_larionov_{variant}",
            "chosen_by_model": bool(method),
        }
    }
    return arr, cal


def phie_step(
    curves: dict[str, np.ndarray], vsh: np.ndarray, p: dict[str, float], method: str | None = None
) -> tuple[np.ndarray, dict[str, Any]]:
    """Compute effective porosity (default = density-neutron, shale-corrected) + calibration."""
    nan = np.full(vsh.size, np.nan)
    rhob, nphi = curves.get("RHOB", nan), curves.get("NPHI", nan)
    rho_ma, ma_dd = estimate_matrix_density(rhob, vsh, default=p["rho_ma"])
    if method == "phi_density":
        arr = phi_density(rhob, rho_ma, p["rho_fl"], p["phie_max"])
        cal = {"rho_ma": {"value": rho_ma, "data_driven": ma_dd, "regional_default": p["rho_ma"]}}
        return arr, cal
    if method == "phi_neutron":
        return phi_neutron(nphi, p["phie_max"]), {}
    phi_sh_d, phi_sh_n, sh_dd = estimate_shale_points(
        rhob, nphi, vsh, rho_ma, p["rho_fl"], p["phi_sh_d"], p["phi_sh_n"]
    )
    arr = calc_phie(
        rhob,
        nphi,
        rho_ma,
        p["rho_fl"],
        p["phie_max"],
        vsh=vsh,
        phi_sh_d=phi_sh_d,
        phi_sh_n=phi_sh_n,
    )
    cal = {
        "rho_ma": {"value": rho_ma, "data_driven": ma_dd, "regional_default": p["rho_ma"]},
        "phi_sh_d": {"value": phi_sh_d, "data_driven": sh_dd, "regional_default": p["phi_sh_d"]},
        "phi_sh_n": {"value": phi_sh_n, "data_driven": sh_dd, "regional_default": p["phi_sh_n"]},
    }
    return arr, cal


def sw_step(
    curves: dict[str, np.ndarray],
    phie: np.ndarray,
    vsh: np.ndarray,
    p: dict[str, float],
    method: str | None = None,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Compute water saturation (default = Archie with data-driven Rw) + calibration."""
    rt = curves["RT"]
    rw, rw_dd = estimate_rw(rt, phie, vsh, p["a"], p["m"], default=p["Rw"])
    if method == "sw_simandoux":
        arr = sw_simandoux(rt, phie, vsh, p["a"], p["m"], p["n"], rw, p.get("rsh", 2.0))
    elif method == "sw_indonesia":
        arr = sw_indonesia(rt, phie, vsh, p["a"], p["m"], p["n"], rw, p.get("rsh", 2.0))
    else:
        arr = calc_sw(rt, phie, p["a"], p["m"], p["n"], rw)
    cal = {"Rw": {"value": rw, "data_driven": rw_dd, "regional_default": p["Rw"]}}
    return arr, cal
