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


def _undefined_mask(rt: np.ndarray, phie: np.ndarray) -> np.ndarray:
    return np.isnan(rt) | np.isnan(phie) | (phie <= 0.0) | (rt <= 0.0)


def sw_simandoux(
    rt: np.ndarray,
    phie: np.ndarray,
    vsh: np.ndarray,
    a: float,
    m: float,
    n: float,
    rw: float,
    rsh: float,
) -> np.ndarray:
    """Compute water saturation via the Simandoux shaly-sand model (n=2 closed form).

    Solves ``1/Rt = PHIE**m * Sw**2 / (a*Rw) + Vsh*Sw/Rsh`` for Sw::

        Sw = (a*Rw)/(2*PHIE**m) * ( sqrt( (Vsh/Rsh)**2 + 4*PHIE**m/(a*Rw*Rt) ) - Vsh/Rsh )

    Reduces to Archie when ``Vsh -> 0``. ``n`` is accepted for registry-uniform signatures
    but the closed form is for n=2 (standard Simandoux). Clipped to [0, 1]; NaN where PHIE
    or Rt are NaN/<= 0.

    Args:
        rt: true resistivity (ohm·m). phie: effective porosity (v/v). vsh: shale volume (v/v).
        a, m, n: Archie factors (n=2 assumed by the closed form). rw: water resistivity (ohm·m).
        rsh: shale resistivity (ohm·m).

    Returns:
        Sw array in [0, 1] (NaN for undefined samples).
    """
    rt_arr = np.asarray(rt, dtype=float)
    phie_arr = np.asarray(phie, dtype=float)
    vsh_arr = np.clip(np.asarray(vsh, dtype=float), 0.0, 1.0)
    x = vsh_arr / rsh
    with np.errstate(divide="ignore", invalid="ignore"):
        term = x**2 + (4.0 * phie_arr**m) / (a * rw * rt_arr)
        sw = (a * rw) / (2.0 * phie_arr**m) * (np.sqrt(term) - x)
    sw = np.clip(sw, 0.0, 1.0)
    sw[_undefined_mask(rt_arr, phie_arr)] = np.nan
    return sw


def sw_indonesia(
    rt: np.ndarray,
    phie: np.ndarray,
    vsh: np.ndarray,
    a: float,
    m: float,
    n: float,
    rw: float,
    rsh: float,
) -> np.ndarray:
    """Compute water saturation via the Indonesia (Poupon-Leveaux) shaly-sand model.

    ``1/sqrt(Rt) = [ Vsh**(1-Vsh/2)/sqrt(Rsh) + PHIE**(m/2)/sqrt(a*Rw) ] * Sw**(n/2)``::

        Sw = ( (1/sqrt(Rt)) / denom ) ** (2/n)

    Designed for high-Vsh rock. Reduces toward Archie when ``Vsh -> 0``. Clipped to [0, 1];
    NaN where PHIE or Rt are NaN/<= 0.

    Args:
        rt, phie, vsh: arrays. a, m, n: Archie factors. rw, rsh: water/shale resistivity (ohm·m).

    Returns:
        Sw array in [0, 1] (NaN for undefined samples).
    """
    rt_arr = np.asarray(rt, dtype=float)
    phie_arr = np.asarray(phie, dtype=float)
    vsh_arr = np.clip(np.asarray(vsh, dtype=float), 0.0, 1.0)
    with np.errstate(divide="ignore", invalid="ignore"):
        shale_term = vsh_arr ** (1.0 - vsh_arr / 2.0) / np.sqrt(rsh)
        sand_term = phie_arr ** (m / 2.0) / np.sqrt(a * rw)
        sw = ((1.0 / np.sqrt(rt_arr)) / (shale_term + sand_term)) ** (2.0 / n)
    sw = np.clip(sw, 0.0, 1.0)
    sw[_undefined_mask(rt_arr, phie_arr)] = np.nan
    return sw
