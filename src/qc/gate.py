"""The deterministic QC gate: orchestrates masking + builds the per-depth quality map.

No computation is reachable without ``qc_gate`` producing the quality map first
(Phase-1 invariant). Quality tiers: GOOD | DEGRADED | EXCLUDED.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from src.io.loader import WellData
from src.qc.masks import (
    Edit,
    bad_hole_mask,
    hard_range_mask,
    mask_nulls,
    range_flags,
    remove_spikes,
)

VERSION = "0.1.0"

GOOD, DEGRADED, EXCLUDED = "GOOD", "DEGRADED", "EXCLUDED"
ABORT_THRESHOLD = 0.80
SPIKE_CURVES = ("GR", "RHOB", "NPHI", "RT")
# Mechanical floor: RHOB below this (g/cc) is non-physical for rock matrix (even ~40% porosity gives
# ~2.0) — a sensor error / washout. We flag those depths DEGRADED (a quality signal); we do NOT mask
# the value or decide it is non-reservoir — that interpretive call belongs to the agent.
RHOB_MIN_PLAUSIBLE = 1.5


@dataclass
class QCResult:
    """Output of the QC gate."""

    curves: dict[str, np.ndarray]  # masked
    quality_map: np.ndarray  # dtype object: GOOD/DEGRADED/EXCLUDED per depth
    edits: list[Edit] = field(default_factory=list)


def detect_units(
    curves: dict[str, np.ndarray],
) -> tuple[dict[str, np.ndarray], list[Edit]]:
    """Auto-convert unambiguous unit variants (NPHI %->v/v, RHOB kg/m3->g/cc).

    Raises ValueError on an ambiguous NPHI range (1.0–2.0) requiring manual confirmation.
    """
    out = {k: np.asarray(v, dtype=float).copy() for k, v in curves.items()}
    edits: list[Edit] = []
    if "NPHI" in out:
        mx = np.nanmax(out["NPHI"]) if np.any(np.isfinite(out["NPHI"])) else 0.0
        if mx > 2.0:
            out["NPHI"] = out["NPHI"] / 100.0
            edits.append({"type": "unit_conversion", "curve": "NPHI", "factor": 0.01})
        elif 1.0 < mx <= 2.0:
            raise ValueError(f"NPHI max {mx:.2f} ambiguous (1.0–2.0); confirm units")
    if "RHOB" in out:
        mx = np.nanmax(out["RHOB"]) if np.any(np.isfinite(out["RHOB"])) else 0.0
        if mx > 10.0:
            out["RHOB"] = out["RHOB"] / 1000.0
            edits.append({"type": "unit_conversion", "curve": "RHOB", "factor": 0.001})
    return out, edits


def _build_quality_map(
    curves: dict[str, np.ndarray], n: int, bad_hole: np.ndarray | None
) -> np.ndarray:
    qmap = np.full(n, GOOD, dtype=object)
    gr = curves.get("GR")
    rt = curves.get("RT")
    rhob = curves.get("RHOB")
    nphi = curves.get("NPHI")

    gr_bad = np.isnan(gr) if gr is not None else np.ones(n, bool)
    rt_bad = np.isnan(rt) if rt is not None else np.ones(n, bool)
    rhob_bad = np.isnan(rhob) if rhob is not None else np.ones(n, bool)
    nphi_bad = np.isnan(nphi) if nphi is not None else np.ones(n, bool)
    # Mechanical floor (objective): RHOB present but non-physically low -> the depth is DEGRADED
    # quality. The value is kept (the agent still sees and judges it); we only flag, never decide.
    rhob_low = (
        (~rhob_bad) & (np.asarray(rhob, dtype=float) < RHOB_MIN_PLAUSIBLE)
        if rhob is not None
        else np.zeros(n, bool)
    )

    excluded = gr_bad | rt_bad  # need GR and RT to compute anything
    degraded = (~excluded) & (rhob_bad | nphi_bad | rhob_low)
    if bad_hole is not None:
        degraded = degraded | ((~excluded) & bad_hole)

    qmap[degraded] = DEGRADED
    qmap[excluded] = EXCLUDED
    return qmap


def qc_gate(well: WellData, bit_size: float = 8.5) -> QCResult:
    """Run the full QC gate on a loaded well.

    Order: unit detection -> null mask -> spike removal -> bad-hole mask ->
    quality map. Aborts if > 80% of depths are EXCLUDED or DEGRADED.

    Raises:
        ValueError: ambiguous units, or > 80% unusable data.
    """
    edits: list[Edit] = []
    curves, e = detect_units(well.curves)
    edits += e
    curves, e = mask_nulls(curves)
    edits += e
    curves, e = hard_range_mask(curves)
    edits += e

    for name in SPIKE_CURVES:
        if name in curves:
            curves[name], e = remove_spikes(curves[name])
            edits += e

    bad_hole, e = bad_hole_mask(curves.get("CALI"), curves.get("DCAL"), bit_size)
    edits += e
    if bad_hole is not None:
        for name in ("RHOB", "NPHI"):
            if name in curves:
                curves[name] = curves[name].copy()
                curves[name][bad_hole] = np.nan

    _, e = range_flags(curves)
    edits += e

    n = well.depth_m.size
    qmap = _build_quality_map(curves, n, bad_hole)

    bad_frac = np.count_nonzero(qmap != GOOD) / n if n else 1.0
    if bad_frac > ABORT_THRESHOLD:
        raise ValueError(f"QC abort: {bad_frac:.0%} of depths unusable (> 80%)")

    return QCResult(curves=curves, quality_map=qmap, edits=edits)
