"""Golden tests for hydrocarbon volumetrics (hcpv, bvw)."""

import numpy as np
import pytest

from src.petrophysics.volumetrics import bvw, hcpv

STEP = 0.5


def test_bvw_analytic():
    out = bvw(np.array([0.2, 0.1]), np.array([0.5, 0.4]))
    assert np.allclose(out, [0.10, 0.04])


def test_bvw_nan_passthrough():
    out = bvw(np.array([0.2, np.nan]), np.array([0.5, 0.4]))
    assert out[0] == 0.10 and np.isnan(out[1])


def test_bvw_bounds():
    phie = np.linspace(0, 0.4, 20)
    sw = np.linspace(0, 1, 20)
    out = bvw(phie, sw)
    assert np.all((out >= 0.0) & (out <= 1.0))


def test_hcpv_analytic():
    # one flagged depth: PHIE=0.2, Sw=0.3 -> 0.2*(1-0.3)*0.5 = 0.07
    phie = np.array([0.20, 0.20])
    sw = np.array([0.30, 0.70])
    flag = np.array([True, False])
    assert hcpv(phie, sw, flag, STEP) == pytest.approx(0.07)


def test_hcpv_net_pay_only():
    # un-flagged depths must not contribute
    phie = np.array([0.3, 0.3])
    sw = np.array([0.2, 0.2])
    assert hcpv(phie, sw, np.array([False, False]), STEP) == 0.0


def test_hcpv_zero_thickness_guard():
    assert hcpv(np.array([]), np.array([]), np.array([], dtype=bool), STEP) == 0.0


def test_hcpv_nan_skipped():
    phie = np.array([0.2, np.nan])
    sw = np.array([0.3, 0.3])
    flag = np.array([True, True])
    # second sample is NaN -> skipped; only first contributes 0.07
    assert hcpv(phie, sw, flag, STEP) == pytest.approx(0.07)
