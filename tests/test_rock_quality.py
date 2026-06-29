"""Golden tests for rock-quality indices (uncalibrated): RQI, FZI, Winland R35."""

import numpy as np

from src.petrophysics.rock_quality import fzi, rqi, winland_r35


def test_rqi_nonneg_increases_with_k():
    out = rqi(np.array([1.0, 10.0, 100.0]), np.array([0.2, 0.2, 0.2]))
    assert np.all(out >= 0.0) and out[0] < out[1] < out[2]


def test_rqi_nan_passthrough():
    assert np.isnan(rqi(np.array([np.nan]), np.array([0.2]))[0])


def test_fzi_nonneg_and_nan():
    out = fzi(np.array([10.0, np.nan]), np.array([0.2, 0.2]))
    assert out[0] >= 0.0 and np.isnan(out[1])


def test_winland_r35_increases_with_k():
    out = winland_r35(np.array([1.0, 100.0]), np.array([0.2, 0.2]))
    assert np.all(out >= 0.0) and out[0] < out[1]


def test_winland_r35_nan_passthrough():
    assert np.isnan(winland_r35(np.array([np.nan]), np.array([0.2]))[0])
