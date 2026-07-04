"""PLSS (Public Land Survey System) grid → approximate lat/lon. Deterministic, golden-tested.

Kansas wells carry Section/Township/Range in their LAS headers instead of coordinates. This
module converts that grid reference to an APPROXIMATE point (section center) on the idealized
PLSS grid anchored at the Kansas baseline (40°N) and the 6th Principal Meridian (~97.37°W).
Declared precision: ±1 section (~±1.6 km) plus real-grid irregularities — good for a field
distribution map, never for exact well location. The map must carry this caveat.
"""

from __future__ import annotations

import math
import re

VERSION = "0.1.0"

# Kansas PLSS anchors: baseline latitude (state north border) and the 6th Principal Meridian.
KS_BASELINE_LAT = 40.0
SIXTH_PM_LON = -97.3667
MILES_PER_DEG_LAT = 69.05
MILES_PER_DEG_LON_EQ = 69.17  # scaled by cos(lat)
TOWNSHIP_MILES = 6.0

# Section numbering is boustrophedon starting at the NE corner: row 0 (north) runs E→W
# (sec 1 = NE corner = easternmost column 0), row 1 runs W→E, … Column index grows WESTWARD.
_SECTION_ROW_COL: dict[int, tuple[int, int]] = {}
for _row in range(6):
    cols = range(6) if _row % 2 == 0 else range(5, -1, -1)
    for _i, _col in enumerate(cols):
        _SECTION_ROW_COL[_row * 6 + _i + 1] = (_row, _col)


def _parse_int(token: str | int | float) -> int | None:
    m = re.search(r"\d+", str(token))
    return int(m.group(0)) if m else None


def plss_to_latlon(
    section: str | int,
    township: str | int,
    range_: str | int,
) -> dict[str, float] | None:
    """Convert a Kansas PLSS reference (section, township-S, range-W) to section-center lat/lon.

    Idealized grid: township rows count SOUTH from the 40°N baseline, range columns count WEST
    from the 6th Principal Meridian; each township is 6×6 miles of 36 sections numbered
    boustrophedon from the NE corner. Longitude miles are scaled by cos(latitude).

    Args:
        section: 1–36 (accepts "29", "Sec29", 29.0).
        township: south township number (accepts "19S", "19", 19).
        range_: west range number (accepts "21W", "21", 21).

    Returns:
        ``{latitude, longitude, precision_km}`` or None when any token is unparseable/out of
        range (northern/eastern-reference Kansas wells are out of this converter's scope).
    """
    sec = _parse_int(section)
    twn = _parse_int(township)
    rng = _parse_int(range_)
    if sec is None or twn is None or rng is None:
        return None
    if not (1 <= sec <= 36) or not (1 <= twn <= 35) or not (1 <= rng <= 43):
        return None
    if "N" in str(township).upper() or "E" in str(range_).upper():
        return None  # Kansas S/W convention only — other quadrants are out of scope

    row, col = _SECTION_ROW_COL[sec]
    lat = KS_BASELINE_LAT - ((twn - 1) + (row + 0.5) / 6.0) * (TOWNSHIP_MILES / MILES_PER_DEG_LAT)
    lon_miles_per_deg = MILES_PER_DEG_LON_EQ * math.cos(math.radians(lat))
    lon = SIXTH_PM_LON - ((rng - 1) + (col + 0.5) / 6.0) * (TOWNSHIP_MILES / lon_miles_per_deg)
    return {"latitude": round(lat, 5), "longitude": round(lon, 5), "precision_km": 1.6}
