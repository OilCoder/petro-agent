"""Golden tests for log-based permeability (uncalibrated): Timur, Coates."""

import numpy as np

from src.petrophysics.permeability import perm_coates, perm_timur


def test_timur_nonneg_and_nan():
    out = perm_timur(np.array([0.2, np.nan]), np.array([0.3, 0.3]))
    assert out[0] >= 0.0 and np.isnan(out[1])


def test_timur_increases_with_porosity():
    out = perm_timur(np.array([0.1, 0.2, 0.3]), np.array([0.3, 0.3, 0.3]))
    assert out[0] < out[1] < out[2]


def test_timur_decreases_with_swirr():
    out = perm_timur(np.array([0.2, 0.2]), np.array([0.2, 0.6]))
    assert out[0] > out[1]


def test_coates_nonneg_and_free_fluid_effect():
    out = perm_coates(np.array([0.2, 0.2]), np.array([0.2, 0.6]))
    assert np.all(out >= 0.0) and out[0] > out[1]  # more free fluid -> higher k


def test_coates_nan_passthrough():
    assert np.isnan(perm_coates(np.array([np.nan]), np.array([0.3]))[0])
