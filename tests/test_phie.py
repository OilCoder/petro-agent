"""Golden tests for calc_phie (density-neutron effective porosity)."""

import numpy as np
import pytest

from src.petrophysics.phie import calc_phie

RHO_MA, RHO_FL = 2.65, 1.00


def test_phie_bounds():
    rhob = np.linspace(1.5, 2.65, 50)
    nphi = np.linspace(0.0, 0.5, 50)
    phie = calc_phie(rhob, nphi, RHO_MA, RHO_FL)
    assert np.all((phie >= 0.0) & (phie <= 0.45))


def test_phie_zero_porosity():
    phie = calc_phie(np.array([RHO_MA]), np.array([0.0]), RHO_MA, RHO_FL)
    assert phie[0] == pytest.approx(0.0)


def test_phie_known_sandstone():
    # phi_D = (2.65-2.00)/(2.65-1.00) = 0.3939; PHIE = (0.3939+0.30)/2 = 0.3470
    phie = calc_phie(np.array([2.00]), np.array([0.30]), RHO_MA, RHO_FL)
    assert phie[0] == pytest.approx(0.3470, abs=1e-3)


def test_phie_monotonicity_rhob():
    rhob = np.array([2.0, 2.2, 2.4])
    phie = calc_phie(rhob, np.full(3, 0.2), RHO_MA, RHO_FL)
    assert np.all(np.diff(phie) <= 1e-12)  # denser rock -> less porosity


def test_phie_monotonicity_nphi():
    nphi = np.array([0.1, 0.2, 0.3])
    phie = calc_phie(np.full(3, 2.3), nphi, RHO_MA, RHO_FL)
    assert np.all(np.diff(phie) >= -1e-12)  # more neutron porosity -> more PHIE


def test_phie_nan_rhob_fallback():
    # density masked -> neutron-only path returns nphi
    phie = calc_phie(np.array([np.nan]), np.array([0.22]), RHO_MA, RHO_FL)
    assert phie[0] == pytest.approx(0.22)


def test_phie_nan_nphi_fallback():
    # neutron masked -> density-only path returns phi_D
    phie = calc_phie(np.array([2.00]), np.array([np.nan]), RHO_MA, RHO_FL)
    assert phie[0] == pytest.approx(0.3939, abs=1e-3)


def test_phie_both_nan():
    phie = calc_phie(np.array([np.nan]), np.array([np.nan]), RHO_MA, RHO_FL)
    assert np.isnan(phie[0])


def test_phie_units_guard():
    with pytest.raises(ValueError):
        calc_phie(np.array([2.0]), np.array([0.2]), 1.0, 1.0)
