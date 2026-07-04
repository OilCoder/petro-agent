"""LAS loader: read a LAS 2.0 file into a typed well structure.

Resolves curve mnemonics to canonical names, normalizes depth to metres, and
extracts the curves the engine consumes. Heavy QC (spike/bad-hole/quality map) is
Phase 1; this is the Phase-0 intake. The mnemonic alias map is embedded here for
Phase 0 and moves to ``src/params/mnemonic_aliases.json`` in Phase 2.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import lasio
import numpy as np

VERSION = "0.1.0"

FEET_TO_M = 0.3048
INCH_TO_M = 0.0254

# Canonical curve -> accepted aliases (case-insensitive). Phase-0 embedded map.
ALIASES: dict[str, list[str]] = {
    "GR": ["GR", "GRGC", "GR_EDTC", "SGR", "CGR", "GAMMA", "GCGR", "GRSG"],
    "RHOB": ["RHOB", "RHOZ", "DEN", "RHOG", "DENS", "ZDEN"],
    "NPHI": ["NPHI", "NPOR", "TNPH", "CN", "PHIN", "CNLS", "CNPOR", "NPRL"],
    "NPHI_DOL": ["CNDL"],
    "NPHI_SS": ["CNSS"],
    "PHID_SVC": ["DPOR", "DPHI"],
    "NEUT": ["NEUT", "NEU"],
    "RT": [
        "RT",
        "ILD",
        "LLD",
        "AT90",
        "RDEEP",
        "RILD",
        "RESD",
        "RD",
        "RES",
        "LL",
        "GUARD",
        "GRD",
        "SGRD",
        "LGRD",
    ],
    "RXO": ["RXO", "RLL3", "LL8", "SFL", "SFLU", "LLS", "MLL"],
    "RMED": ["RILM", "ILM", "RMED"],
    "MNOR": ["MNOR"],
    "MINV": ["MINV"],
    "CALI": ["CALI", "CAL", "C1", "CALP"],
    "DCAL": ["DCAL", "CALX", "CALY", "HDCAL"],
    "DRHO": ["RHOC", "DRHO", "ZCOR"],
    "DT": ["DT", "AC", "SONIC", "DTC", "SON", "DTC1"],
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
    metadata: dict[str, str] = field(default_factory=dict)  # well/tool provenance
    unmapped: list[str] = field(default_factory=list)  # raw mnemonics dropped (no canonical alias)
    acquisition: dict[str, object] = field(default_factory=dict)  # header params (BHT/RMF/PLSS…)


def _match(mnemonic: str) -> tuple[str, int] | None:
    """Map a raw mnemonic to ``(canonical, rank)`` where lower rank = preferred alias.

    The alias-list order encodes preference — for RT the deepest-DOI mnemonics come
    first — so resolution picks the best curve by rank, not by file order.
    """
    upper = mnemonic.upper().split(":")[0].split("[")[0].strip()
    for canon, aliases in ALIASES.items():
        if upper in aliases:
            return canon, aliases.index(upper)
    return None


def _header(las: lasio.LASFile, key: str, default: str = "") -> str:
    try:
        if key in las.well:
            value = las.well[key].value
            return str(value).strip() if value is not None else default
    except (KeyError, AttributeError):
        pass
    return default


# Acquisition header params worth carrying to the ledger: mud/temperature/elevation numerics
# and location/date text. Read from BOTH ~Parameter and ~Well blocks (vendors vary).
_ACQ_NUMERIC = ("BHT", "RM", "RMF", "RMC", "RMB", "MFT", "EMT", "MCST", "EKB", "EGL", "EDF")
_ACQ_TEXT = ("DATE", "DFT", "SECT", "TOWN", "RANG", "LOC", "COUN")


def _param_lookup(las: lasio.LASFile, key: str) -> tuple[object, str] | None:
    """Find a header item by mnemonic in ~Parameter then ~Well; None when absent/empty."""
    for block in (las.params, las.well):
        try:
            if key in block:
                item = block[key]
                if item.value not in (None, ""):
                    return item.value, str(item.unit or "").strip()
        except (KeyError, AttributeError):
            continue
    return None


def _acquisition(las: lasio.LASFile) -> dict[str, object]:
    """Extract acquisition header params (numeric parsed, unit kept) from ~Parameter/~Well."""
    out: dict[str, object] = {}
    for key in _ACQ_NUMERIC:
        hit = _param_lookup(las, key)
        if hit is None:
            continue
        raw, unit = hit
        cleaned = re.sub(r"[^\d.+-]", "", str(raw))  # "2306'" -> "2306"; "110 DEGF" -> "110"
        try:
            out[key] = {"value": float(cleaned), "unit": unit}
        except (TypeError, ValueError):
            out[key] = {"value": str(raw).strip(), "unit": unit}
    for key in _ACQ_TEXT:
        hit = _param_lookup(las, key)
        if hit is not None:
            out[key] = str(hit[0]).strip()
    return out


def _normalize_depth(depth: np.ndarray, unit: str) -> tuple[np.ndarray, bool]:
    """Depth to metres, flipped if logged deepest-first. Returns ``(depth, was_reversed)``.

    Handles FT/IN/0.1-IN units, and reverses a fully DECREASING index (a valid but deepest-first
    log) so the pipeline always sees a monotonically increasing depth — the caller flips the curves.
    """
    if unit in ("FT", "F", "FEET"):
        depth = depth * FEET_TO_M
    elif unit in ("IN", "INCH", "INCHES"):
        depth = depth * INCH_TO_M
    elif unit in ("0.1 IN", "0.1IN"):  # tenths of an inch (seen in some vendor exports)
        depth = depth * 0.1 * INCH_TO_M
    reversed_depth = depth.size >= 2 and bool(np.all(np.diff(depth) < 0))
    return (depth[::-1] if reversed_depth else depth), reversed_depth


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
    depth_unit = (las.curves[0].unit or "").upper().strip() if len(las.curves) else ""
    depth, reversed_depth = _normalize_depth(depth, depth_unit)

    if depth.size < 10:
        raise ValueError(f"{path}: fewer than 10 depth samples ({depth.size})")
    if not np.all(np.diff(depth) > 0):
        raise ValueError(f"{path}: depth is not monotonically increasing")
    step = float(np.median(np.diff(depth)))

    # ----------------------------------------
    # Step 2 — resolve canonical curves (best alias rank wins, not file order)
    # ----------------------------------------
    # For RT the deepest-DOI mnemonic must win even if a shallow one appears first.
    _DEPTH_MNEMONICS = {"DEPT", "DEPTH", "MD", "TVD", "TVDSS"}
    candidates: dict[str, list[tuple[int, str, np.ndarray]]] = {}
    unmapped: list[str] = []
    for curve in las.curves:
        m = _match(curve.mnemonic)
        if m:
            canon, rank = m
            arr = np.asarray(curve.data, dtype=float)
            if reversed_depth:  # keep curves aligned with the flipped depth index
                arr = arr[::-1]
            candidates.setdefault(canon, []).append((rank, curve.mnemonic, arr))
        elif curve.mnemonic.upper().split(":")[0].strip() not in _DEPTH_MNEMONICS:
            unmapped.append(
                curve.mnemonic
            )  # dropped: no canonical alias (transparency, not a filter)
    curves: dict[str, np.ndarray] = {}
    raw: dict[str, str] = {}
    for canon, cands in candidates.items():
        cands.sort(key=lambda c: c[0])  # lowest rank = most-preferred alias
        _, mnemonic, arr = cands[0]
        curves[canon] = arr
        raw[canon] = mnemonic

    # ----------------------------------------
    # Step 3 — well + tool metadata (provenance)
    # ----------------------------------------
    prov = _header(las, "PROV", default="unknown") or "unknown"
    metadata = {
        "log_date": _header(las, "DATE"),
        "service_company": _header(las, "SRVC"),
        "company": _header(las, "COMP"),
        "field": _header(las, "FLD"),
        "depth_start_m": f"{float(depth[0]):.2f}",
        "depth_stop_m": f"{float(depth[-1]):.2f}",
        "latitude": _header(las, "LAT"),
        "longitude": _header(las, "LON"),
    }

    return WellData(
        source_path=path,
        well_name=_header(las, "WELL", default="UNKNOWN"),
        uwi=_header(las, "UWI") or _header(las, "API", default="UNKNOWN"),
        prov=prov,
        depth_m=depth,
        step_m=step,
        curves=curves,
        raw_mnemonics=raw,
        metadata={k: v for k, v in metadata.items() if v},
        unmapped=unmapped,
        acquisition=_acquisition(las),
    )
