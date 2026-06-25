"""Golden tests for data-driven matrix density and shale endpoints (PHYS-02)."""

import numpy as np

from src.petrophysics.lithology import estimate_matrix_density, estimate_shale_points

RHO_FL = 1.00


def test_matrix_density_reads_sandstone_from_clean_rock():
    # Clean sandstone matrix ~2.65; high percentile of clean RHOB recovers it.
    rhob = np.full(100, 2.65)
    vsh = np.zeros(100)
    rho_ma, dd = estimate_matrix_density(rhob, vsh, default=2.71)
    assert dd is True
    assert abs(rho_ma - 2.65) < 0.02  # data-driven, not the 2.71 default


def test_matrix_density_falls_back_when_no_clean_rock():
    rhob = np.full(100, 2.50)
    vsh = np.full(100, 0.9)  # all shaly -> no clean samples
    rho_ma, dd = estimate_matrix_density(rhob, vsh, default=2.71)
    assert dd is False and rho_ma == 2.71


def test_matrix_density_clipped_to_window():
    rhob = np.full(100, 3.5)  # implausibly dense (e.g. anhydrite streak)
    vsh = np.zeros(100)
    rho_ma, _ = estimate_matrix_density(rhob, vsh, default=2.71)
    assert rho_ma <= 2.95  # clipped to the plausible ceiling


def test_shale_points_read_from_high_vsh_rock():
    # Shale: RHOB 2.45 -> phi_sh_d=(2.65-2.45)/(2.65-1)=0.121; NPHI median 0.40.
    n = 100
    rhob = np.where(np.arange(n) < 50, 2.45, 2.65)
    nphi = np.where(np.arange(n) < 50, 0.40, 0.10)
    vsh = np.where(np.arange(n) < 50, 0.9, 0.1)
    phi_sh_d, phi_sh_n, dd = estimate_shale_points(rhob, nphi, vsh, 2.65, RHO_FL, 0.10, 0.35)
    assert dd is True
    assert phi_sh_d == np.float64(np.clip((2.65 - 2.45) / (2.65 - 1.0), 0, 1))
    assert phi_sh_n == 0.40


def test_shale_points_fall_back_without_shale():
    n = 100
    rhob, nphi = np.full(n, 2.60), np.full(n, 0.15)
    vsh = np.full(n, 0.2)  # no high-Vsh rock
    phi_sh_d, phi_sh_n, dd = estimate_shale_points(rhob, nphi, vsh, 2.65, RHO_FL, 0.10, 0.35)
    assert dd is False and (phi_sh_d, phi_sh_n) == (0.10, 0.35)


def test_estimate_rw_from_clean_porous_wet_rock():
    from src.petrophysics.lithology import estimate_rw

    n = 50
    rt, phie, vsh = np.full(n, 2.0), np.full(n, 0.2), np.full(n, 0.1)
    rw, dd = estimate_rw(rt, phie, vsh, 1.0, 2.0, default=0.04)
    assert dd is True
    assert rw == np.float64(2.0 * 0.2**2 / 1.0)  # Rwa = RT*PHIE^m/a = 0.08


def test_estimate_rw_falls_back_without_porous_rock():
    from src.petrophysics.lithology import estimate_rw

    n = 50
    rt, phie, vsh = np.full(n, 2.0), np.full(n, 0.02), np.full(n, 0.1)  # PHIE<0.08
    rw, dd = estimate_rw(rt, phie, vsh, 1.0, 2.0, default=0.04)
    assert dd is False and rw == 0.04
