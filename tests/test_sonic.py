"""Golden tests for sonic porosity (Wyllie, Raymer-Hunt-Gardner)."""

import numpy as np
import pytest

from src.petrophysics.sonic import phi_sonic_rhg, phi_sonic_wyllie

DT_MA, DT_FL = 47.5, 189.0  # limestone matrix, fluid


def test_wyllie_known_value():
    # PHI = (DT - DT_ma)/(DT_fl - DT_ma); DT=118.25 -> 70.75/141.5 = 0.5 (phie_max raised)
    phi = phi_sonic_wyllie(np.array([118.25]), DT_MA, DT_FL, phie_max=0.6)
    assert phi[0] == pytest.approx(0.5, abs=1e-3)


def test_wyllie_bounds_and_nan():
    phi = phi_sonic_wyllie(np.array([47.5, 400.0, np.nan]), DT_MA, DT_FL)
    assert phi[0] == 0.0 and phi[1] == 0.45 and np.isnan(phi[2])


def test_wyllie_monotonic_in_dt():
    phi = phi_sonic_wyllie(np.array([60.0, 90.0, 120.0]), DT_MA, DT_FL)
    assert np.all(np.diff(phi) > 0)


def test_wyllie_invalid_raises():
    with pytest.raises(ValueError):
        phi_sonic_wyllie(np.array([100.0]), 189.0, 47.5)


def test_rhg_bounds_and_nan():
    phi = phi_sonic_rhg(np.array([90.0, np.nan, 0.0]), DT_MA)
    assert 0.0 <= phi[0] <= 0.45 and np.isnan(phi[1]) and np.isnan(phi[2])


def test_rhg_monotonic_in_dt():
    phi = phi_sonic_rhg(np.array([60.0, 90.0, 120.0]), DT_MA)
    assert np.all(np.diff(phi) > 0)
