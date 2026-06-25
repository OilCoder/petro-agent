"""Golden tests for calc_vsh (Larionov old-rocks Vsh)."""

import numpy as np
import pytest

from src.petrophysics.vsh import OLD_ROCKS, TERTIARY, calc_vsh

GR = np.array([0.0, 25.0, 50.0, 75.0, 100.0, 150.0, 200.0])
GR_MIN, GR_MAX = 10.0, 150.0


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
