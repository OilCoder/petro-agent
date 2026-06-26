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
