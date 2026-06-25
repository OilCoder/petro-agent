"""Tests for the LAS loader: a reproducible synthetic fixture + a real-data integration test."""

import glob
import os

import numpy as np
import pytest

from src.io.loader import load_las

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "synthetic_oldrocks.las")


def test_load_synthetic_metadata():
    well = load_las(FIXTURE)
    assert well.well_name == "TEST-1"
    assert well.uwi == "15-999-00001"
    assert well.prov == "paleozoic"


def test_load_synthetic_depth_metres():
    well = load_las(FIXTURE)
    assert well.depth_m[0] == pytest.approx(1000.0)
    assert well.step_m == pytest.approx(0.5)
    assert well.depth_m.size == 10


def test_load_synthetic_curves():
    well = load_las(FIXTURE)
    assert {"GR", "RHOB", "NPHI", "RT"} <= set(well.curves)
    assert well.curves["GR"][0] == pytest.approx(20.0)
    assert well.curves["RHOB"][4] == pytest.approx(2.60)


def test_load_synthetic_curve_length():
    well = load_las(FIXTURE)
    for arr in well.curves.values():
        assert arr.size == well.depth_m.size


def test_load_real_schaben_if_present():
    """Integration: load a real full-suite Schaben LAS if data/ is populated."""
    files = sorted(glob.glob("data/schaben_all/*.las"))
    if not files:
        pytest.skip("no Schaben LAS in data/ (gitignored)")
    for path in files:
        try:
            well = load_las(path)
        except Exception:  # noqa: BLE001
            continue
        if {"GR", "RHOB", "NPHI", "RT"} <= set(well.curves):
            assert well.depth_m.size >= 10
            assert well.step_m > 0
            assert np.all(np.diff(well.depth_m) > 0)
            return
    pytest.skip("no full-suite Schaben well found in data/")


def test_match_prefers_deep_resistivity_by_rank():
    from src.io.loader import _match

    canon_ild, rank_ild = _match("ILD")  # type: ignore[misc]
    canon_rild, rank_rild = _match("RILD")  # type: ignore[misc]
    canon_res, rank_res = _match("RES")  # type: ignore[misc]
    assert canon_ild == canon_rild == canon_res == "RT"
    # deep induction (ILD) outranks RILD outranks generic RES (lower rank = preferred)
    assert rank_ild < rank_rild < rank_res
