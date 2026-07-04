"""Golden tests for the vintage count-rate neutron transform (CXR-3)."""

import numpy as np
import pytest

from src.petrophysics.phie import phi_neutron_countrate


def test_countrate_exact_at_anchors():
    phi = phi_neutron_countrate(np.array([2000.0, 500.0]), n_dense=2000.0, n_shale=500.0)
    assert phi[0] == pytest.approx(0.02, abs=1e-6)  # dense anchor
    assert phi[1] == pytest.approx(0.30, abs=1e-6)  # shale anchor


def test_countrate_monotonic_decreasing_in_counts():
    counts = np.linspace(500.0, 2000.0, 50)
    phi = phi_neutron_countrate(counts, 2000.0, 500.0)
    assert np.all(np.diff(phi) <= 1e-12)  # more counts -> less porosity


def test_countrate_clipped_and_nan_passthrough():
    phi = phi_neutron_countrate(np.array([100.0, np.nan, 5000.0]), 2000.0, 500.0)
    assert phi[0] <= 0.45 and np.isnan(phi[1]) and phi[2] >= 0.0


def test_countrate_rejects_degenerate_anchors():
    with pytest.raises(ValueError):
        phi_neutron_countrate(np.array([1.0]), 1000.0, 1000.0)
    with pytest.raises(ValueError):
        phi_neutron_countrate(np.array([1.0]), 2000.0, 500.0, phi_dense=0.0)


def test_phie_step_countrate_dispatch_with_engine_anchors():
    from src.orchestrator.steps import phie_step

    n = 300
    gr = np.concatenate([np.full(100, 100.0), np.full(200, 40.0)])  # shaly top, clean below
    neut = np.concatenate([np.full(100, 600.0), np.linspace(900.0, 2000.0, 200)])
    curves = {"GR": gr, "NEUT": neut}
    p = {"rho_ma": 2.71, "rho_fl": 1.0, "phie_max": 0.45, "phi_sh_d": 0.1, "phi_sh_n": 0.35}
    arr, cal = phie_step(curves, np.zeros(n), p, method="phi_neutron_countrate")
    anchors = cal["countrate_anchors"]["value"]
    assert anchors["n_shale"] < anchors["n_dense"]
    finite = arr[np.isfinite(arr)]
    assert finite.size == n and finite.min() >= 0.0 and finite.max() <= 0.45
    # dense (high-count) samples must read lower porosity than the shaly low-count top
    assert np.mean(arr[200:]) < np.mean(arr[:100])
