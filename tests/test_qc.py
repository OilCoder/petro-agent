"""Tests for the Phase-1 QC gate: unit detection, masking, quality map, abort."""

import numpy as np
import pytest

from src.io.loader import WellData
from src.qc.gate import DEGRADED, EXCLUDED, GOOD, detect_units, qc_gate
from src.qc.masks import bad_hole_mask, mask_nulls, remove_spikes


def _well(curves, n=20):
    depth = np.arange(n, dtype=float) * 0.5 + 1000.0
    return WellData("x", "W1", "uwi", "paleozoic", depth, 0.5, curves)


def _clean_curves(n=20):
    return {
        "GR": np.linspace(20, 80, n),
        "RHOB": np.full(n, 2.35),
        "NPHI": np.full(n, 0.20),
        "RT": np.full(n, 10.0),
    }


def test_detect_units_nphi_percent():
    out, edits = detect_units({"NPHI": np.array([18.0, 22.0])})
    assert out["NPHI"][0] == pytest.approx(0.18)
    assert any(e["type"] == "unit_conversion" for e in edits)


def test_detect_units_rhob_kgm3():
    out, _ = detect_units({"RHOB": np.array([2400.0, 2500.0])})
    assert out["RHOB"][0] == pytest.approx(2.40)


def test_detect_units_ambiguous_raises():
    with pytest.raises(ValueError):
        detect_units({"NPHI": np.array([0.5, 1.5])})


def test_mask_nulls():
    out, edits = mask_nulls({"GR": np.array([20.0, -999.25, 40.0])})
    assert np.isnan(out["GR"][1]) and edits[0]["count"] == 1


def test_remove_spikes():
    arr = np.array([20.0, 21.0, 20.5, 999.0, 21.0, 20.0, 20.5, 21.0, 20.0, 20.5])
    out, edits = remove_spikes(arr)
    assert np.isnan(out[3]) and len(edits) == 1


def test_bad_hole_dcal_preferred():
    mask, _ = bad_hole_mask(None, np.array([0.5, 3.0, 1.0]), 8.5)
    assert list(mask) == [False, True, False]


def test_bad_hole_cali_fallback():
    mask, edits = bad_hole_mask(np.array([8.6, 12.0]), None, 8.5)
    assert list(mask) == [False, True]
    assert any(e["detail"] == "bad_hole_cali_fallback" for e in edits)


def test_bad_hole_both_absent():
    mask, edits = bad_hole_mask(None, None, 8.5)
    assert mask is None and edits[0]["detail"] == "bad_hole_unavailable"


def test_quality_map_tiers():
    curves = _clean_curves()
    curves["GR"][0:2] = np.nan  # EXCLUDED (no GR)
    curves["RHOB"][5:7] = np.nan  # DEGRADED (one porosity missing)
    result = qc_gate(_well(curves))
    assert result.quality_map[0] == EXCLUDED
    assert result.quality_map[5] == DEGRADED
    assert result.quality_map[10] == GOOD


def test_qc_abort_threshold():
    curves = _clean_curves()
    curves["GR"][:] = np.nan  # everything excluded
    with pytest.raises(ValueError):
        qc_gate(_well(curves))


def test_hard_range_mask_masks_infinite_rt():
    from src.qc.masks import hard_range_mask

    curves = {"RT": np.array([10.0, 1e10, 50.0, -5.0])}
    out, edits = hard_range_mask(curves)
    assert np.isnan(out["RT"][1])  # 1e10 sentinel-like -> masked
    assert np.isnan(out["RT"][3])  # negative resistivity -> masked
    assert out["RT"][0] == 10.0 and out["RT"][2] == 50.0  # valid kept
    assert any(e["type"] == "hard_range_mask" and e["curve"] == "RT" for e in edits)
