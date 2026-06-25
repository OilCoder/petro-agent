"""QC masking primitives: nulls, spikes, bad-hole, physical range. Each logs ledger edits.

Consolidates the Phase-1 masking functions (the blueprint sketched separate
null_handler/spike/bad_hole/range_check modules; merged here for the autonomous run —
see planning/DECISIONS.md D3). Every function returns ``(masked_or_flags, edits)`` so
the caller records the edits in the ledger.
"""

from __future__ import annotations

import numpy as np

VERSION = "0.1.0"

Edit = dict[str, object]


def mask_nulls(
    curves: dict[str, np.ndarray], sentinel: float = -999.25, tol: float = 1e-3
) -> tuple[dict[str, np.ndarray], list[Edit]]:
    """Mask sentinel nulls to NaN across all curves. lasio usually does this on read;
    this is a defensive pass that also logs the masked count per curve."""
    out: dict[str, np.ndarray] = {}
    edits: list[Edit] = []
    for name, arr in curves.items():
        a = np.asarray(arr, dtype=float).copy()
        hit = np.abs(a - sentinel) < tol
        n = int(np.count_nonzero(hit))
        if n:
            a[hit] = np.nan
            edits.append({"type": "null_mask", "curve": name, "count": n})
        out[name] = a
    return out, edits


def remove_spikes(
    curve: np.ndarray, window: int = 10, k: float = 5.0
) -> tuple[np.ndarray, list[Edit]]:
    """Mask spikes exceeding ``k * IQR`` above the local median in a ``±window`` window.

    Returns the despiked curve (spikes -> NaN) and the list of spike edits.
    """
    a = np.asarray(curve, dtype=float).copy()
    n = a.size
    edits: list[Edit] = []
    if n == 0 or not np.any(np.isfinite(a)):
        return a, edits
    q1, q3 = np.nanpercentile(a, [25, 75])
    iqr = q3 - q1
    if not np.isfinite(iqr) or iqr == 0:
        return a, edits
    for i in range(n):
        lo, hi = max(0, i - window), min(n, i + window + 1)
        local = a[lo:hi]
        med = np.nanmedian(local)
        if np.isfinite(a[i]) and abs(a[i] - med) > k * iqr:
            edits.append({"type": "spike_removal", "index": i, "value": float(a[i])})
            a[i] = np.nan
    return a, edits


def bad_hole_mask(
    cali: np.ndarray | None,
    dcal: np.ndarray | None,
    bit_size: float,
    threshold_in: float = 2.0,
) -> tuple[np.ndarray | None, list[Edit]]:
    """Return a bad-hole boolean mask (True = bad) and edits.

    Preferred: ``|DCAL| > threshold``. Fallback: ``CALI > bit_size + threshold`` (logs a
    degradation). Both absent: returns ``None`` (caller logs a tier downgrade).
    """
    edits: list[Edit] = []
    if dcal is not None:
        mask = np.abs(np.asarray(dcal, dtype=float)) > threshold_in
        return np.nan_to_num(mask, nan=False).astype(bool), edits
    if cali is not None:
        edits.append({"type": "degradation", "detail": "bad_hole_cali_fallback"})
        mask = np.asarray(cali, dtype=float) > (bit_size + threshold_in)
        return np.nan_to_num(mask, nan=False).astype(bool), edits
    edits.append({"type": "degradation", "detail": "bad_hole_unavailable"})
    return None, edits


_RANGES = {
    "GR": (0.0, 300.0),
    "RHOB": (1.0, 3.0),
    "NPHI": (0.0, 1.0),
    "RT": (0.01, 50000.0),
    "CALI": (0.0, 30.0),
}


def range_flags(curves: dict[str, np.ndarray]) -> tuple[dict[str, np.ndarray], list[Edit]]:
    """Flag (WARN, not mask) samples outside physical ranges. Returns per-curve bool flags."""
    flags: dict[str, np.ndarray] = {}
    edits: list[Edit] = []
    for name, (lo, hi) in _RANGES.items():
        if name not in curves:
            continue
        a = np.asarray(curves[name], dtype=float)
        with np.errstate(invalid="ignore"):
            warn = (a < lo) | (a > hi)
        warn &= ~np.isnan(a)
        flags[name] = warn
        n = int(np.count_nonzero(warn))
        if n:
            edits.append({"type": "range_warn", "curve": name, "count": n})
    return flags, edits
