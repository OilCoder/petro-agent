"""Golden tests for calc_vsh (Larionov old-rocks Vsh)."""

import numpy as np
import pytest

from src.petrophysics.vsh import (
    OLD_ROCKS,
    TERTIARY,
    calc_vsh,
    vsh_multimineral,
    vsh_neutron_density,
)

GR = np.array([0.0, 25.0, 50.0, 75.0, 100.0, 150.0, 200.0])
GR_MIN, GR_MAX = 10.0, 150.0

# neutron-density Vsh reference points (rho_ma=2.65, rho_fl=1.0; shale @ NPHI=0.42, phi_D=0.10)
_RHO_MA, _RHO_FL, _PSHN, _PSHD = 2.65, 1.0, 0.42, 0.10


def test_vsh_nd_clean_rock_is_zero():
    # clean rock: NPHI == phi_D -> zero separation -> Vsh 0
    rhob = np.array([2.65])  # phi_D = 0
    nphi = np.array([0.0])
    vsh = vsh_neutron_density(nphi, rhob, _RHO_MA, _RHO_FL, _PSHN, _PSHD)
    assert vsh[0] == pytest.approx(0.0)


def test_vsh_nd_shale_point_is_one():
    # at the shale point (NPHI=phi_sh_n, phi_D=phi_sh_d) the separation equals the denominator -> 1
    rhob = np.array([2.65 - _PSHD * (2.65 - 1.0)])  # phi_D = 0.10
    nphi = np.array([_PSHN])
    vsh = vsh_neutron_density(nphi, rhob, _RHO_MA, _RHO_FL, _PSHN, _PSHD)
    assert vsh[0] == pytest.approx(1.0)


def test_vsh_nd_bounds_and_nan_passthrough():
    rhob = np.array([2.2, 2.65, 2.85, np.nan])
    nphi = np.array([0.5, 0.05, 0.0, 0.2])
    vsh = vsh_neutron_density(nphi, rhob, _RHO_MA, _RHO_FL, _PSHN, _PSHD)
    finite = vsh[np.isfinite(vsh)]
    assert np.all((finite >= 0.0) & (finite <= 1.0))
    assert np.isnan(vsh[-1])  # NaN density -> NaN Vsh


def test_vsh_nd_zero_shale_separation_is_nan():
    vsh = vsh_neutron_density(np.array([0.3]), np.array([2.4]), _RHO_MA, _RHO_FL, 0.30, 0.30)
    assert np.isnan(vsh[0])


# multi-mineral endpoints: matrix (2.65, -0.02), clay (2.75, 0.30), fluid (1.0, 1.0)
def test_vsh_multimineral_pure_endpoints():
    # pure matrix -> Vsh 0 ; pure clay -> Vsh 1 ; pure water -> Vsh 0 (all porosity)
    rhob = np.array([2.65, 2.75, 1.00])
    nphi = np.array([-0.02, 0.30, 1.00])
    vsh = vsh_multimineral(rhob, nphi)
    assert vsh[0] == pytest.approx(0.0, abs=1e-6)
    assert vsh[1] == pytest.approx(1.0, abs=1e-6)
    assert vsh[2] == pytest.approx(0.0, abs=1e-6)


def test_vsh_multimineral_fifty_fifty_and_bounds():
    # 50/50 clay-matrix at zero porosity -> Vsh ~0.5
    rhob = np.array([(2.65 + 2.75) / 2])
    nphi = np.array([(-0.02 + 0.30) / 2])
    assert vsh_multimineral(rhob, nphi)[0] == pytest.approx(0.5, abs=1e-6)
    # bounds + NaN passthrough
    vsh = vsh_multimineral(np.array([2.2, 3.0, np.nan]), np.array([0.5, -0.1, 0.2]))
    finite = vsh[np.isfinite(vsh)]
    assert np.all((finite >= 0.0) & (finite <= 1.0)) and np.isnan(vsh[-1])


def test_vsh_bounds_old_rocks():
    gr = np.linspace(0, 300, 100)
    vsh = calc_vsh(gr, GR_MIN, GR_MAX)
    assert np.all((vsh >= 0.0) & (vsh <= 1.0))


def test_vsh_clean_sand():
    assert calc_vsh(np.array([GR_MIN]), GR_MIN, GR_MAX)[0] == pytest.approx(0.0)


def test_vsh_pure_shale():
    # IGR=1 -> 0.33*(2**2 - 1) = 0.99 (not clipped)
    assert calc_vsh(np.array([GR_MAX]), GR_MIN, GR_MAX)[0] == pytest.approx(0.99)


def test_vsh_midpoint():
    mid = (GR_MIN + GR_MAX) / 2.0
    # IGR=0.5 -> 0.33*(2**1 - 1) = 0.33
    assert calc_vsh(np.array([mid]), GR_MIN, GR_MAX)[0] == pytest.approx(0.33)


def test_vsh_monotonicity():
    vsh = calc_vsh(np.sort(GR), GR_MIN, GR_MAX)
    assert np.all(np.diff(vsh) >= -1e-12)


def test_vsh_nan_passthrough():
    gr = np.array([20.0, np.nan, 80.0])
    vsh = calc_vsh(gr, GR_MIN, GR_MAX)
    assert np.isnan(vsh[1]) and not np.isnan(vsh[0]) and not np.isnan(vsh[2])


def test_vsh_tertiary_differs():
    old = calc_vsh(GR, GR_MIN, GR_MAX, variant=OLD_ROCKS)
    ter = calc_vsh(GR, GR_MIN, GR_MAX, variant=TERTIARY)
    # interior point must differ between variants
    assert not np.isclose(old[3], ter[3])


def test_vsh_dimensional():
    # Output stays in [0,1] regardless of GR scale (any monotonic scaling).
    vsh = calc_vsh(GR * 1000.0, GR_MIN * 1000.0, GR_MAX * 1000.0)
    assert np.all((vsh >= 0.0) & (vsh <= 1.0))


def test_vsh_invalid_baseline_raises():
    with pytest.raises(ValueError):
        calc_vsh(GR, 150.0, 10.0)


# ----------------------------------------
# Linear IGR method (V2-A)
# ----------------------------------------

from src.petrophysics.vsh import vsh_linear  # noqa: E402


def test_vsh_linear_equals_igr():
    gr = np.array([20.0, 70.0, 120.0])  # gr_min=20, gr_max=120 -> IGR 0, 0.5, 1.0
    v = vsh_linear(gr, 20.0, 120.0)
    assert np.allclose(v, [0.0, 0.5, 1.0])


def test_vsh_linear_clips_and_nan():
    v = vsh_linear(np.array([10.0, 200.0, np.nan]), 20.0, 120.0)
    assert v[0] == 0.0 and v[1] == 1.0 and np.isnan(v[2])


def test_vsh_linear_overestimates_vs_larionov():
    gr = np.array([70.0])  # midpoint
    assert vsh_linear(gr, 20.0, 120.0)[0] > calc_vsh(gr, 20.0, 120.0)[0]


def test_vsh_linear_invalid_baseline_raises():
    with pytest.raises(ValueError):
        vsh_linear(GR, 150.0, 10.0)


# --- Clavier / Steiber (non-linear, R3) ---
from src.petrophysics.vsh import vsh_clavier, vsh_steiber  # noqa: E402


def test_vsh_clavier_endpoints():
    out = vsh_clavier(np.array([20.0, 120.0]), 20.0, 120.0)
    assert abs(out[0]) < 1e-9 and abs(out[1] - 1.0) < 1e-9


def test_vsh_steiber_endpoints():
    out = vsh_steiber(np.array([20.0, 120.0]), 20.0, 120.0)
    assert abs(out[0]) < 1e-9 and abs(out[1] - 1.0) < 1e-9


def test_vsh_clavier_bounds_and_monotonic():
    gr = np.linspace(20.0, 120.0, 11)
    out = vsh_clavier(gr, 20.0, 120.0)
    assert np.all((out >= 0.0) & (out <= 1.0))
    assert np.all(np.diff(out) >= -1e-12)


def test_vsh_steiber_below_linear_midrange():
    # Steiber reads below the linear index at mid-range (IGR=0.5 -> 0.5/2 = 0.25)
    out = vsh_steiber(np.array([70.0]), 20.0, 120.0)
    assert abs(out[0] - 0.25) < 1e-9


def test_vsh_nonlinear_nan_passthrough():
    assert np.isnan(vsh_clavier(np.array([np.nan]), 20.0, 120.0)[0])
    assert np.isnan(vsh_steiber(np.array([np.nan]), 20.0, 120.0)[0])


def test_vsh_nonlinear_bad_bounds_raise():
    with pytest.raises(ValueError):
        vsh_clavier(np.array([50.0]), 100.0, 100.0)
    with pytest.raises(ValueError):
        vsh_steiber(np.array([50.0]), 100.0, 100.0)


def test_vsh_method_comparison_keys_and_clean_zero():
    from src.petrophysics.vsh import vsh_method_comparison

    cmp = vsh_method_comparison(np.array([20.0, 20.0]), 20.0, 120.0)
    assert set(cmp) == {
        "vsh_larionov_old",
        "vsh_larionov_tertiary",
        "vsh_linear",
        "vsh_clavier",
        "vsh_steiber",
    }
    assert all(abs(v) < 1e-9 for v in cmp.values())  # all methods read 0 in clean sand
