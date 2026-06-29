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


# ----------------------------------------
# Shale correction — effective porosity (PHYS-01)
# ----------------------------------------

PHI_SH_D, PHI_SH_N = 0.10, 0.35


def test_phie_effective_less_than_total_in_shaly_rock():
    # Shaly sample: effective PHIE (shale-corrected) must be below total PHIT.
    rhob, nphi, vsh = np.array([2.30]), np.array([0.30]), np.array([0.5])
    phit = calc_phie(rhob, nphi, RHO_MA, RHO_FL)
    phie = calc_phie(rhob, nphi, RHO_MA, RHO_FL, vsh=vsh, phi_sh_d=PHI_SH_D, phi_sh_n=PHI_SH_N)
    assert phie[0] < phit[0]
    # phi_d=0.21212 -> corr 0.16212; phi_n 0.30 -> corr 0.125; PHIE=(0.16212+0.125)/2
    assert phie[0] == pytest.approx(0.14356, abs=1e-3)


def test_phie_goes_to_zero_in_pure_shale():
    # Vsh=1 at the shale points -> effective porosity collapses to zero.
    rhob = np.array([RHO_MA - PHI_SH_D * (RHO_MA - RHO_FL)])  # phi_d == phi_sh_d
    nphi = np.array([PHI_SH_N])
    phie = calc_phie(
        rhob, nphi, RHO_MA, RHO_FL, vsh=np.array([1.0]), phi_sh_d=PHI_SH_D, phi_sh_n=PHI_SH_N
    )
    assert phie[0] == pytest.approx(0.0, abs=1e-9)


def test_phie_clean_sand_unchanged_by_correction():
    # Vsh=0 -> shale correction is a no-op; identical to the total-porosity result.
    rhob, nphi = np.array([2.00]), np.array([0.30])
    phit = calc_phie(rhob, nphi, RHO_MA, RHO_FL)
    phie = calc_phie(
        rhob, nphi, RHO_MA, RHO_FL, vsh=np.array([0.0]), phi_sh_d=PHI_SH_D, phi_sh_n=PHI_SH_N
    )
    assert phie[0] == pytest.approx(phit[0])


def test_phie_effective_decreases_with_vsh():
    # Monotonic: higher shale volume -> lower effective porosity.
    rhob, nphi = np.full(3, 2.30), np.full(3, 0.30)
    phie = calc_phie(
        rhob,
        nphi,
        RHO_MA,
        RHO_FL,
        vsh=np.array([0.0, 0.4, 0.8]),
        phi_sh_d=PHI_SH_D,
        phi_sh_n=PHI_SH_N,
    )
    assert np.all(np.diff(phie) < 0)


def test_phie_effective_nan_passthrough():
    # Shale correction preserves the both-NaN exclusion.
    phie = calc_phie(
        np.array([np.nan]),
        np.array([np.nan]),
        RHO_MA,
        RHO_FL,
        vsh=np.array([0.5]),
        phi_sh_d=PHI_SH_D,
        phi_sh_n=PHI_SH_N,
    )
    assert np.isnan(phie[0])


# --- single-curve porosity (R3) ---
from src.petrophysics.phie import phi_density, phi_neutron  # noqa: E402


def test_phi_density_known_value():
    out = phi_density(np.array([2.5]), 2.65, 1.0)
    assert abs(out[0] - (2.65 - 2.5) / (2.65 - 1.0)) < 1e-9


def test_phi_density_clips_and_nan():
    out = phi_density(np.array([1.0, np.nan]), 2.65, 1.0, phie_max=0.45)
    assert out[0] == 0.45 and np.isnan(out[1])


def test_phi_density_bad_bounds_raises():
    with pytest.raises(ValueError):
        phi_density(np.array([2.5]), 1.0, 1.0)


def test_phi_neutron_passthrough_and_clip():
    out = phi_neutron(np.array([0.2, 0.9, np.nan]), phie_max=0.45)
    assert abs(out[0] - 0.2) < 1e-9 and out[1] == 0.45 and np.isnan(out[2])
