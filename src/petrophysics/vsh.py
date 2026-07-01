"""Shale volume (Vsh) from gamma ray via the Larionov correction.

Frozen, version-pinned, golden-tested. The old-rocks (pre-Tertiary) variant is the
only one valid for the Kansas/Schaben Paleozoic development data (Charter Invariant 6).
"""

import numpy as np

VERSION = "0.1.0"

OLD_ROCKS = "old_rocks"
TERTIARY = "tertiary"


def calc_vsh(
    gr: np.ndarray,
    gr_min: float,
    gr_max: float,
    variant: str = OLD_ROCKS,
) -> np.ndarray:
    """Compute shale volume from gamma ray.

    Larionov old-rocks: ``Vsh = 0.33 * (2**(2*IGR) - 1)``.
    Larionov Tertiary:  ``Vsh = 0.083 * (2**(3.7*IGR) - 1)``.
    IGR = (GR - gr_min) / (gr_max - gr_min), clipped to [0, 1] so out-of-range GR
    yields Vsh at the physical boundary rather than outside it.

    Args:
        gr: 1-D gamma-ray array (API). NaN entries propagate to NaN.
        gr_min: clean-sand GR baseline (API).
        gr_max: shale GR baseline (API).
        variant: ``"old_rocks"`` (default, Paleozoic) or ``"tertiary"``.

    Returns:
        Vsh array in [0, 1] (NaN where input GR is NaN).

    Raises:
        ValueError: if ``gr_max <= gr_min`` or ``variant`` is unknown.
    """
    if gr_max <= gr_min:
        raise ValueError(f"gr_max ({gr_max}) must exceed gr_min ({gr_min})")
    if variant not in (OLD_ROCKS, TERTIARY):
        raise ValueError(f"unknown Larionov variant: {variant!r}")

    gr_arr = np.asarray(gr, dtype=float)
    igr = np.clip((gr_arr - gr_min) / (gr_max - gr_min), 0.0, 1.0)

    if variant == TERTIARY:
        vsh = 0.083 * (2.0 ** (3.7 * igr) - 1.0)
    else:
        vsh = 0.33 * (2.0 ** (2.0 * igr) - 1.0)

    vsh = np.clip(vsh, 0.0, 1.0)
    vsh[np.isnan(gr_arr)] = np.nan
    return vsh


def vsh_linear(gr: np.ndarray, gr_min: float, gr_max: float) -> np.ndarray:
    """Compute shale volume as the linear gamma-ray index (Vsh = IGR).

    ``IGR = (GR - gr_min) / (gr_max - gr_min)``, clipped to [0, 1]. The conservative
    screening estimate — overestimates Vsh vs Larionov, so it is the cautious choice.

    Args:
        gr: gamma-ray array (API). NaN propagates to NaN.
        gr_min: clean-sand GR baseline (API).
        gr_max: shale GR baseline (API).

    Returns:
        Vsh array in [0, 1] (NaN where GR is NaN).

    Raises:
        ValueError: if ``gr_max <= gr_min``.
    """
    if gr_max <= gr_min:
        raise ValueError(f"gr_max ({gr_max}) must exceed gr_min ({gr_min})")
    gr_arr = np.asarray(gr, dtype=float)
    vsh = np.clip((gr_arr - gr_min) / (gr_max - gr_min), 0.0, 1.0)
    vsh[np.isnan(gr_arr)] = np.nan
    return vsh


def vsh_clavier(gr: np.ndarray, gr_min: float, gr_max: float) -> np.ndarray:
    """Compute shale volume via the Clavier 1971 non-linear correction.

    ``Vsh = 1.7 - sqrt(3.38 - (IGR + 0.7)**2)``, IGR clipped to [0, 1] and Vsh to [0, 1].
    A non-linear alternative to Larionov; less aggressive than the linear index.

    Args:
        gr: gamma-ray array (API). NaN propagates to NaN.
        gr_min: clean-sand GR baseline (API).
        gr_max: shale GR baseline (API).

    Returns:
        Vsh array in [0, 1] (NaN where GR is NaN).

    Raises:
        ValueError: if ``gr_max <= gr_min``.
    """
    if gr_max <= gr_min:
        raise ValueError(f"gr_max ({gr_max}) must exceed gr_min ({gr_min})")
    gr_arr = np.asarray(gr, dtype=float)
    igr = np.clip((gr_arr - gr_min) / (gr_max - gr_min), 0.0, 1.0)
    vsh = 1.7 - np.sqrt(np.clip(3.38 - (igr + 0.7) ** 2, 0.0, None))
    vsh = np.clip(vsh, 0.0, 1.0)
    vsh[np.isnan(gr_arr)] = np.nan
    return vsh


def vsh_steiber(gr: np.ndarray, gr_min: float, gr_max: float) -> np.ndarray:
    """Compute shale volume via the Steiber 1970 non-linear correction.

    ``Vsh = IGR / (3 - 2*IGR)``, IGR clipped to [0, 1] and Vsh to [0, 1].
    A non-linear alternative that reads below the linear index in mid-range.

    Args:
        gr: gamma-ray array (API). NaN propagates to NaN.
        gr_min: clean-sand GR baseline (API).
        gr_max: shale GR baseline (API).

    Returns:
        Vsh array in [0, 1] (NaN where GR is NaN).

    Raises:
        ValueError: if ``gr_max <= gr_min``.
    """
    if gr_max <= gr_min:
        raise ValueError(f"gr_max ({gr_max}) must exceed gr_min ({gr_min})")
    gr_arr = np.asarray(gr, dtype=float)
    igr = np.clip((gr_arr - gr_min) / (gr_max - gr_min), 0.0, 1.0)
    vsh = igr / (3.0 - 2.0 * igr)
    vsh = np.clip(vsh, 0.0, 1.0)
    vsh[np.isnan(gr_arr)] = np.nan
    return vsh


def vsh_neutron_density(
    nphi: np.ndarray,
    rhob: np.ndarray,
    rho_ma: float,
    rho_fl: float,
    phi_sh_n: float,
    phi_sh_d: float,
) -> np.ndarray:
    """Shale volume from the neutron-density separation (a NON-GR clay indicator).

    ``phi_D = (rho_ma - rhob) / (rho_ma - rho_fl)``; clay widens the ``(NPHI - phi_D)`` separation,
    so normalizing by the shale-point separation ``(phi_sh_n - phi_sh_d)`` estimates Vsh in [0, 1].
    Complements the GR-Larionov family so the uncertainty band spans more of the method space.

    Args:
        nphi: neutron porosity (v/v). NaN propagates.
        rhob: bulk density (g/cc). NaN propagates.
        rho_ma: matrix density (g/cc).
        rho_fl: fluid density (g/cc).
        phi_sh_n: neutron porosity at the 100%-shale point (v/v).
        phi_sh_d: apparent density porosity at the 100%-shale point (v/v).

    Returns:
        Vsh in [0, 1]; all-NaN when the shale separation ``(phi_sh_n - phi_sh_d)`` is ~0.
    """
    nphi = np.asarray(nphi, dtype=float)
    rhob = np.asarray(rhob, dtype=float)
    denom = phi_sh_n - phi_sh_d
    if abs(denom) < 1e-6:
        return np.full_like(nphi, np.nan)
    phi_d = (rho_ma - rhob) / (rho_ma - rho_fl)
    return np.clip((nphi - phi_d) / denom, 0.0, 1.0)


def vsh_multimineral(
    rhob: np.ndarray,
    nphi: np.ndarray,
    rho_ma: float = 2.65,
    rho_fl: float = 1.0,
    rho_clay: float = 2.75,
    nphi_ma: float = -0.02,
    nphi_clay: float = 0.30,
    nphi_fl: float = 1.0,
) -> np.ndarray:
    """Vsh from a 2-mineral (matrix + clay) volumetric solve on RHOB and NPHI.

    Jointly inverts the density and neutron responses for the volume fractions of matrix, clay and
    porosity (fluid), subject to closure ``V_ma + V_clay + PHI = 1`` — a light multi-mineral model
    that uses BOTH logs at once, capturing clay differently than any single GR/N-D indicator.
    ``Vsh = V_clay``, clipped to [0, 1].

    Args:
        rhob, nphi: bulk density (g/cc) and neutron porosity (v/v). NaN propagates.
        rho_ma, rho_fl, rho_clay: matrix, fluid, clay densities (g/cc).
        nphi_ma, nphi_clay, nphi_fl: neutron responses of matrix, clay, fluid (v/v).

    Returns:
        Vsh in [0, 1] (= clay volume fraction); NaN where a response matrix is singular or inputs
        are NaN.
    """
    a = np.array(
        [[rho_ma, rho_clay, rho_fl], [nphi_ma, nphi_clay, nphi_fl], [1.0, 1.0, 1.0]], dtype=float
    )
    rhob = np.asarray(rhob, dtype=float)
    try:
        a_inv = np.linalg.inv(a)
    except np.linalg.LinAlgError:
        return np.full(rhob.shape, np.nan)
    nphi = np.asarray(nphi, dtype=float)
    v_clay = (a_inv @ np.vstack([rhob, nphi, np.ones_like(rhob)]))[1]  # [V_ma, V_clay, PHI]
    return np.clip(v_clay, 0.0, 1.0)


def vsh_method_comparison(
    gr: np.ndarray,
    gr_min: float,
    gr_max: float,
    nphi: np.ndarray | None = None,
    rhob: np.ndarray | None = None,
    rho_ma: float | None = None,
    rho_fl: float | None = None,
    phi_sh_n: float | None = None,
    phi_sh_d: float | None = None,
) -> dict[str, float]:
    """Mean Vsh from every vetted method, for the multi-method comparison section.

    Deterministic aggregation (not a new formula) — runs the vetted Vsh methods on the same data
    and returns each one's mean, so the report shows how the estimate varies by method. When the
    neutron-density inputs are supplied, the NON-GR ``vsh_neutron_density`` is included too.

    Args:
        gr: gamma-ray array (API).
        gr_min: clean-sand GR baseline (API).
        gr_max: shale GR baseline (API).
        nphi, rhob, rho_ma, rho_fl, phi_sh_n, phi_sh_d: optional; when all present, add the
            neutron-density Vsh method.

    Returns:
        ``{method_id: mean_vsh}`` (NaN where a method yields no finite value).
    """
    methods = {
        "vsh_larionov_old": calc_vsh(gr, gr_min, gr_max, OLD_ROCKS),
        "vsh_larionov_tertiary": calc_vsh(gr, gr_min, gr_max, TERTIARY),
        "vsh_linear": vsh_linear(gr, gr_min, gr_max),
        "vsh_clavier": vsh_clavier(gr, gr_min, gr_max),
        "vsh_steiber": vsh_steiber(gr, gr_min, gr_max),
    }
    if (
        nphi is not None
        and rhob is not None
        and rho_ma is not None
        and rho_fl is not None
        and phi_sh_n is not None
        and phi_sh_d is not None
    ):
        methods["vsh_neutron_density"] = vsh_neutron_density(
            nphi, rhob, rho_ma, rho_fl, phi_sh_n, phi_sh_d
        )
        methods["vsh_multimineral"] = vsh_multimineral(rhob, nphi, rho_ma, rho_fl)
    out: dict[str, float] = {}
    for key, arr in methods.items():
        finite = arr[np.isfinite(arr)]
        out[key] = round(float(np.mean(finite)), 4) if finite.size else float("nan")
    return out
