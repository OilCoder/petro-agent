"""Golden tests for the summit volumetrics additions: phi_h and swirr_buckles."""

import numpy as np
import pytest

from src.petrophysics.volumetrics import phi_h, swirr_buckles


def test_phi_h_known_sum():
    phie = np.array([0.10, 0.20, 0.30, 0.40])
    flag = np.array([True, True, False, True])
    # 0.10 + 0.20 + 0.40 = 0.70, step 0.5 -> 0.35 m
    assert phi_h(phie, flag, 0.5) == pytest.approx(0.35)


def test_phi_h_nan_skipped_and_empty_flag_zero():
    phie = np.array([0.10, np.nan, 0.30])
    assert phi_h(phie, np.array([True, True, False]), 1.0) == pytest.approx(0.10)
    assert phi_h(phie, np.zeros(3, dtype=bool), 1.0) == 0.0


def test_swirr_buckles_recovers_constant_bvw():
    # rock exactly at irreducible: PHIE*Sw constant = 0.045 everywhere
    phie = np.array([0.09, 0.15, 0.30, 0.10])
    sw = 0.045 / phie
    res = swirr_buckles(phie, sw, np.ones(4, dtype=bool))
    assert res["buckles"] == pytest.approx(0.045, abs=1e-4)
    assert res["swirr_mean"] == pytest.approx(0.045 / phie.mean(), abs=1e-3)
    assert res["n_pay"] == 4


def test_swirr_buckles_low_percentile_isolates_irreducible():
    # half the pay is wet (BVW high); the P10 must sit near the irreducible cluster
    phie = np.full(10, 0.2)
    sw = np.array([0.3] * 5 + [1.0] * 5)  # BVW: 0.06 (irreducible) vs 0.2 (wet)
    res = swirr_buckles(phie, sw, np.ones(10, dtype=bool))
    assert res["buckles"] == pytest.approx(0.06, abs=1e-6)


def test_swirr_buckles_empty_and_nan():
    nan3 = np.full(3, np.nan)
    res = swirr_buckles(nan3, nan3, np.ones(3, dtype=bool))
    assert res["n_pay"] == 0 and np.isnan(res["buckles"]) and np.isnan(res["swirr_mean"])
    res2 = swirr_buckles(np.array([0.2]), np.array([0.5]), np.array([False]))
    assert res2["n_pay"] == 0


def test_swirr_bounded_zero_one():
    phie = np.array([0.05, 0.06])
    sw = np.array([1.0, 1.0])  # fully wet -> swirr estimate must stay <= 1
    res = swirr_buckles(phie, sw, np.ones(2, dtype=bool))
    assert 0.0 <= res["swirr_mean"] <= 1.0
