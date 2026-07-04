"""SP-derived formation-water resistivity (SSP -> Rwe -> Rw, Bateman-Konen).

Vetted alternative source of Rw when the LAS carries an SP curve and the header carries
RMF + a measured temperature: shale-baseline drift is removed with a rolling median, the
static SP is read as a robust percentile of the clean-interval deflection, and the
classic chart chain (K constant, Rmfe = 0.85 * Rmf, Rwe from SSP, Rwe -> Rw) yields an
Rw candidate with declared provenance. Evidence for the analyst — never auto-applied.
Frozen, version-pinned, golden-tested.
"""

from __future__ import annotations

import numpy as np

VERSION = "0.1.0"

# Chart-chain constants (declared, not tunable at runtime).
_RMFE_FACTOR = 0.85  # Rmf -> Rmfe approximation for predominantly NaCl muds
_CLEAN_IGR = 0.3  # IGR below which a sample counts as clean
_SHALE_IGR = 0.6  # IGR above which a sample anchors the shale baseline
_MIN_SAMPLES = 50  # minimum clean/shale samples for a readable SSP


def sp_ssp(
    sp: np.ndarray,
    gr: np.ndarray,
    gr_min: float,
    gr_max: float,
    win: int = 201,
) -> dict[str, float]:
    """Read the static SP (mV) from a drift-corrected SP curve.

    The shale baseline is the rolling median of SP over shale samples (IGR > 0.6),
    linearly interpolated across the well — this removes baseline drift. SSP is the P5
    of ``(SP - baseline)`` over clean samples (IGR < 0.3): the sustained negative
    deflection, robust to spikes.

    Args:
        sp: spontaneous potential (mV). NaN allowed.
        gr: gamma ray (API), same grid.
        gr_min: clean-sand GR baseline (API).
        gr_max: shale GR baseline (API).
        win: rolling-median window in samples (odd).

    Returns:
        ``{ssp_mv, n_clean, n_shale}`` — ``ssp_mv`` NaN when either population is
        thinner than 50 samples (an unreadable SP is a fact, not an error).
    """
    sp_arr = np.asarray(sp, dtype=float)
    gr_arr = np.asarray(gr, dtype=float)
    igr = np.clip((gr_arr - gr_min) / max(gr_max - gr_min, 1e-9), 0.0, 1.0)
    ok = np.isfinite(sp_arr) & np.isfinite(gr_arr)
    shale = ok & (igr > _SHALE_IGR)
    clean = ok & (igr < _CLEAN_IGR)
    n_clean, n_shale = int(clean.sum()), int(shale.sum())
    if n_clean < _MIN_SAMPLES or n_shale < _MIN_SAMPLES:
        return {"ssp_mv": float("nan"), "n_clean": n_clean, "n_shale": n_shale}

    # 🔄 drift-corrected shale baseline: rolling median over shale samples, interpolated
    idx = np.arange(sp_arr.size)
    half = max(win // 2, 1)
    shale_idx = idx[shale]
    baseline_pts = np.array(
        [
            np.nanmedian(sp_arr[shale][(shale_idx >= i - half) & (shale_idx <= i + half)])
            for i in shale_idx
        ]
    )
    baseline = np.interp(idx, shale_idx, baseline_pts)
    ssp = float(np.percentile(sp_arr[clean] - baseline[clean], 5))
    return {"ssp_mv": round(ssp, 1), "n_clean": n_clean, "n_shale": n_shale}


def rw_from_ssp(ssp_mv: float, rmf_ohmm: float, temp_c: float) -> dict[str, float]:
    """Formation-water resistivity from static SP via the Bateman-Konen chain.

    ``K = 61 + 0.133 * T(degF)``; ``Rmfe = 0.85 * Rmf``; ``Rwe = Rmfe * 10^(SSP/K)``;
    then Rwe -> Rw with the standard chart fit: for ``Rwe > 0.12``,
    ``Rw = -(0.58 - 10^(0.69*Rwe - 0.24))``; otherwise
    ``Rw = (77*Rwe + 5) / (146 - 377*Rwe)``. All resistivities at the given temperature.

    Args:
        ssp_mv: static SP (mV, negative when Rmf > Rw).
        rmf_ohmm: mud-filtrate resistivity at ``temp_c`` (ohm-m).
        temp_c: formation temperature (Celsius).

    Returns:
        ``{rw_ohmm, rwe_ohmm, k_mv}``.

    Raises:
        ValueError: if ``rmf_ohmm`` is not positive.
    """
    if rmf_ohmm <= 0.0:
        raise ValueError(f"rmf_ohmm must be positive, got {rmf_ohmm}")
    t_f = temp_c * 9.0 / 5.0 + 32.0
    k = 61.0 + 0.133 * t_f
    rwe = _RMFE_FACTOR * rmf_ohmm * 10.0 ** (float(ssp_mv) / k)
    if rwe > 0.12:
        rw = -(0.58 - 10.0 ** (0.69 * rwe - 0.24))
    else:
        rw = (77.0 * rwe + 5.0) / (146.0 - 377.0 * rwe)
    return {"rw_ohmm": round(float(rw), 5), "rwe_ohmm": round(float(rwe), 5), "k_mv": round(k, 2)}
