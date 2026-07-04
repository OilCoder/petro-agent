"""Golden tests for the invasion-profile EDA scan (CXR-4)."""

import numpy as np

from src.eda.explore import invasion_scan


def test_invasion_fractions_on_synthetic_profile():
    rt = np.array([10.0, 10.0, 10.0, 10.0])
    rxo = np.array([20.0, 15.0, 10.0, 5.0])  # ratios: 2.0, 1.5, 1.0, 0.5
    out = invasion_scan(rt, rxo)
    assert out["n"] == 4
    assert out["frac_invaded"] == 0.5  # 2.0 and 1.5 above 1.2
    assert out["frac_reversed"] == 0.25  # 0.5 below 0.8
    assert out["median_rxo_rt"] == 1.25


def test_invasion_handles_medium_only_and_nan():
    rt = np.array([10.0, np.nan, 5.0])
    rmed = np.array([12.0, 8.0, np.nan])
    out = invasion_scan(rt, rmed=rmed)
    assert out["median_rmed_rt"] == 1.2 and out["n"] == 1


def test_invasion_empty_overlap():
    out = invasion_scan(np.array([np.nan]), np.array([np.nan]))
    assert out == {"n": 0}
