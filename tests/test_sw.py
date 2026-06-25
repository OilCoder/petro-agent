"""Golden tests for calc_sw (Archie water saturation).

NOTE: two monotonicity directions here were CORRECTED relative to blueprint 05's
test descriptions, which had the Archie physics inverted. See planning/DECISIONS.md
(2026-06-25). Archie: Sw = ((a*Rw)/(Rt*PHIE**m))**(1/n) ∝ PHIE**(-m/n):
  - Sw DECREASES as PHIE increases (blueprint said "increases" — wrong).
  - Sw INCREASES as m increases (for PHIE < 1) (blueprint said "lowers" — wrong).
"""

import numpy as np
import pytest

from src.petrophysics.sw import calc_sw

A, M, N, RW = 1.0, 2.0, 2.0, 0.05


def test_sw_bounds():
    rt = np.linspace(0.5, 200.0, 80)
    phie = np.full(80, 0.2)
    sw = calc_sw(rt, phie, A, M, N, RW)
    assert np.all((sw >= 0.0) & (sw <= 1.0))


def test_sw_water_zone():
    # Sw = 1 when (a*Rw)/(Rt*PHIE**m) = 1 -> Rt = a*Rw/PHIE**m = 0.05/0.04 = 1.25
    sw = calc_sw(np.array([1.25]), np.array([0.2]), A, M, N, RW)
    assert sw[0] == pytest.approx(1.0, abs=1e-6)


def test_sw_known_numeric():
    # Rt=10, PHIE=0.2: Sw = (0.05/(10*0.04))**0.5 = (0.125)**0.5 = 0.353553
    sw = calc_sw(np.array([10.0]), np.array([0.2]), A, M, N, RW)
    assert sw[0] == pytest.approx(0.353553, abs=1e-5)


def test_sw_monotonicity_rt():
    rt = np.array([2.0, 10.0, 50.0])
    sw = calc_sw(rt, np.full(3, 0.2), A, M, N, RW)
    assert np.all(np.diff(sw) <= 1e-12)  # higher Rt -> lower Sw


def test_sw_monotonicity_phie():
    # CORRECTED vs blueprint: Sw DECREASES as PHIE increases (Archie).
    phie = np.array([0.1, 0.2, 0.3])
    sw = calc_sw(np.full(3, 10.0), phie, A, M, N, RW)
    assert np.all(np.diff(sw) <= 1e-12)


def test_sw_m_sensitivity():
    # CORRECTED vs blueprint: higher m -> higher Sw (PHIE < 1).
    sw_low_m = calc_sw(np.array([10.0]), np.array([0.2]), A, 1.5, N, RW)[0]
    sw_high_m = calc_sw(np.array([10.0]), np.array([0.2]), A, 2.5, N, RW)[0]
    assert sw_high_m > sw_low_m


def test_sw_zero_phie_guard():
    sw = calc_sw(np.array([10.0]), np.array([0.0]), A, M, N, RW)
    assert np.isnan(sw[0])


def test_sw_nan_passthrough():
    sw = calc_sw(np.array([np.nan, 10.0]), np.array([0.2, np.nan]), A, M, N, RW)
    assert np.isnan(sw[0]) and np.isnan(sw[1])
