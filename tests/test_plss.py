"""Golden tests for the PLSS grid → lat/lon converter (bounding-box anchors, not points)."""

from src.io.plss import plss_to_latlon


def test_plss_ness_county_anchor():
    # Schaben field headers read like "Sec29 T19S R21W" — must land inside Ness County's
    # public bounding box (approx 38.2–38.7 N, -100.25–-99.55 W).
    res = plss_to_latlon("29", "19S", "21W")
    assert res is not None
    assert 38.2 < res["latitude"] < 38.7
    assert -100.25 < res["longitude"] < -99.55
    assert res["precision_km"] == 1.6


def test_plss_grid_monotonicity():
    # more townships south -> lower latitude; more ranges west -> lower longitude
    a = plss_to_latlon(1, "10S", "20W")
    b = plss_to_latlon(1, "20S", "20W")
    c = plss_to_latlon(1, "10S", "30W")
    assert b["latitude"] < a["latitude"]
    assert c["longitude"] < a["longitude"]
    assert abs(abs(a["latitude"] - b["latitude"]) - 10 * 6 / 69.05) < 1e-4


def test_plss_section_boustrophedon():
    # section 1 is the NE corner, section 6 the NW corner (same row) -> same lat, lon6 < lon1;
    # section 36 is the SE corner -> lower lat than section 1
    s1 = plss_to_latlon(1, "19S", "21W")
    s6 = plss_to_latlon(6, "19S", "21W")
    s36 = plss_to_latlon(36, "19S", "21W")
    assert abs(s1["latitude"] - s6["latitude"]) < 1e-9
    assert s6["longitude"] < s1["longitude"]
    assert s36["latitude"] < s1["latitude"]


def test_plss_rejects_garbage_and_out_of_scope():
    assert plss_to_latlon("", "19S", "21W") is None
    assert plss_to_latlon("40", "19S", "21W") is None  # section > 36
    assert plss_to_latlon("29", "19N", "21W") is None  # north reference out of scope
    assert plss_to_latlon("29", "19S", "21E") is None  # east reference out of scope
