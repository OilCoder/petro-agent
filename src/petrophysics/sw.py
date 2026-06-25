"""Water saturation (Sw) via the Archie equation.

Frozen, version-pinned, golden-tested.
"""

import numpy as np

VERSION = "0.1.0"


def calc_sw(
    rt: np.ndarray,
    phie: np.ndarray,
    a: float,
    m: float,
    n: float,
    rw: float,
) -> np.ndarray:
    """Compute water saturation via Archie.

    ``Sw = ((a * Rw) / (Rt * PHIE**m)) ** (1/n)``, clipped to [0, 1].
    Returns NaN where ``PHIE`` is NaN or <= 0, or where ``Rt`` is NaN or <= 0
    (a zero-porosity or undefined-resistivity sample has no defined saturation).

    Args:
        rt: true resistivity array (ohm·m, linear).
        phie: effective porosity array (v/v).
        a: tortuosity factor.
        m: cementation exponent.
        n: saturation exponent.
        rw: formation water resistivity (ohm·m).

    Returns:
        Sw array in [0, 1] (NaN for undefined samples).
    """
    rt_arr = np.asarray(rt, dtype=float)
    phie_arr = np.asarray(phie, dtype=float)

    with np.errstate(divide="ignore", invalid="ignore"):
        sw = ((a * rw) / (rt_arr * phie_arr**m)) ** (1.0 / n)

    sw = np.clip(sw, 0.0, 1.0)
    undefined = (
        np.isnan(rt_arr) | np.isnan(phie_arr) | (phie_arr <= 0.0) | (rt_arr <= 0.0)
    )
    sw[undefined] = np.nan
    return sw
