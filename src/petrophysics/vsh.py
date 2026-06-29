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


def vsh_method_comparison(gr: np.ndarray, gr_min: float, gr_max: float) -> dict[str, float]:
    """Mean Vsh from every GR-only method, for the multi-method comparison section.

    Deterministic aggregation (not a new formula) — runs the vetted Vsh methods on the same
    GR and returns each one's mean, so the report can show how the estimate varies by method.

    Args:
        gr: gamma-ray array (API).
        gr_min: clean-sand GR baseline (API).
        gr_max: shale GR baseline (API).

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
    out: dict[str, float] = {}
    for key, arr in methods.items():
        finite = arr[np.isfinite(arr)]
        out[key] = round(float(np.mean(finite)), 4) if finite.size else float("nan")
    return out
