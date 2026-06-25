"""LAS loader: read a LAS 2.0 file into a typed well structure.

Resolves curve mnemonics to canonical names, normalizes depth to metres, and
extracts the curves the engine consumes. Heavy QC (spike/bad-hole/quality map) is
Phase 1; this is the Phase-0 intake. The mnemonic alias map is embedded here for
Phase 0 and moves to ``src/params/mnemonic_aliases.json`` in Phase 2.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import lasio
import numpy as np

VERSION = "0.1.0"

FEET_TO_M = 0.3048

# Canonical curve -> accepted aliases (case-insensitive). Phase-0 embedded map.
ALIASES: dict[str, list[str]] = {
    "GR": ["GR", "GRD", "GRGC", "GR_EDTC", "SGR", "CGR", "GAMMA"],
    "RHOB": ["RHOB", "RHOZ", "DEN", "RHOG", "DENS", "ZDEN", "RHOC"],
    "NPHI": ["NPHI", "NPOR", "TNPH", "CN", "PHIN", "CNLS", "CNPOR", "NPRL"],
    "RT": ["RT", "ILD", "RDEEP", "AT90", "RD", "LLD", "RILD", "RES", "RESD"],
    "CALI": ["CALI", "CAL", "C1", "CALP"],
    "DCAL": ["DCAL", "CALX", "CALY", "HDCAL"],
    "DT": ["DT", "AC", "SONIC", "DTC"],
    "PEF": ["PEF", "PE"],
}

# Phase 2: prefer the versioned alias table in src/params; fall back to the map above.
try:
    from src.params.config_loader import load_aliases as _load_aliases

    ALIASES = _load_aliases()
except Exception:  # noqa: BLE001 - keep the embedded fallback if the JSON is unavailable
    pass


@dataclass
class WellData:
    """Typed result of loading a LAS file."""

    source_path: str
    well_name: str
    uwi: str
    prov: str
    depth_m: np.ndarray
    step_m: float
    curves: dict[str, np.ndarray]  # canonical name -> array
    raw_mnemonics: dict[str, str] = field(default_factory=dict)  # canonical -> raw


def _canonical(mnemonic: str) -> str | None:
    upper = mnemonic.upper().split(":")[0].split("[")[0].strip()
    for canon, aliases in ALIASES.items():
        if upper in aliases:
            return canon
    return None


def _header(las: lasio.LASFile, key: str, default: str = "") -> str:
    try:
        if key in las.well:
            value = las.well[key].value
            return str(value).strip() if value is not None else default
    except (KeyError, AttributeError):
        pass
    return default


def load_las(path: str) -> WellData:
    """Load a LAS file into a :class:`WellData` structure.

    Args:
        path: filesystem path to a LAS 2.0 file.

    Returns:
        A :class:`WellData` with canonical curves and depth in metres.

    Raises:
        ValueError: if depth is non-monotonic or fewer than 10 samples.
    """
    las = lasio.read(path, ignore_header_errors=True)

    # ----------------------------------------
    # Step 1 — depth index, normalized to metres
    # ----------------------------------------
    depth = np.asarray(las.index, dtype=float)
    depth_unit = (las.curves[0].unit or "").upper() if len(las.curves) else ""
    if depth_unit in ("FT", "F", "FEET"):
        depth = depth * FEET_TO_M

    if depth.size < 10:
        raise ValueError(f"{path}: fewer than 10 depth samples ({depth.size})")
    if not np.all(np.diff(depth) > 0):
        raise ValueError(f"{path}: depth is not monotonically increasing")
    step = float(np.median(np.diff(depth)))

    # ----------------------------------------
    # Step 2 — resolve canonical curves (first alias match wins)
    # ----------------------------------------
    curves: dict[str, np.ndarray] = {}
    raw: dict[str, str] = {}
    for curve in las.curves:
        canon = _canonical(curve.mnemonic)
        if canon and canon not in curves:
            curves[canon] = np.asarray(curve.data, dtype=float)
            raw[canon] = curve.mnemonic

    # ----------------------------------------
    # Step 3 — well metadata
    # ----------------------------------------
    prov = _header(las, "PROV", default="unknown") or "unknown"

    return WellData(
        source_path=path,
        well_name=_header(las, "WELL", default="UNKNOWN"),
        uwi=_header(las, "UWI") or _header(las, "API", default="UNKNOWN"),
        prov=prov,
        depth_m=depth,
        step_m=step,
        curves=curves,
        raw_mnemonics=raw,
    )
