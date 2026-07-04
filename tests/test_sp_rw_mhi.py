"""Golden tests: SP->Rw chain (sp_rw) and the movable-hydrocarbon index (sw.mhi)."""

import numpy as np
import pytest

from src.petrophysics.sp_rw import rw_from_ssp, sp_ssp
from src.petrophysics.sw import movable_hydrocarbon_index

# ----------------------------------------
# Step 1 — rw_from_ssp: exact chart-chain cases
# ----------------------------------------


def test_k_constant_and_zero_ssp():
    # T=25C -> 77F -> K = 61 + 0.133*77 = 71.241; SSP=0 -> Rwe = 0.85*Rmf exactly
    out = rw_from_ssp(0.0, 1.0, 25.0)
    assert out["k_mv"] == pytest.approx(71.24, abs=0.01)
    assert out["rwe_ohmm"] == pytest.approx(0.85, abs=1e-4)


def test_high_rwe_branch_known_value():
    # Rwe = 0.2 -> Rw = -(0.58 - 10^(0.69*0.2 - 0.24)) = 0.21075...
    ssp = 0.0
    rmf = 0.2 / 0.85  # makes Rwe exactly 0.2 at SSP=0
    out = rw_from_ssp(ssp, rmf, 25.0)
    assert out["rwe_ohmm"] == pytest.approx(0.2, abs=1e-4)
    assert out["rw_ohmm"] == pytest.approx(-(0.58 - 10 ** (0.69 * 0.2 - 0.24)), abs=1e-4)


def test_low_rwe_branch_known_value():
    # Rwe = 0.05 -> Rw = (77*0.05 + 5) / (146 - 377*0.05) = 8.85/127.15
    rmf = 0.05 / 0.85
    out = rw_from_ssp(0.0, rmf, 25.0)
    assert out["rw_ohmm"] == pytest.approx(8.85 / 127.15, abs=1e-4)


def test_more_negative_ssp_means_saltier_water():
    rws = [rw_from_ssp(s, 0.5, 40.0)["rw_ohmm"] for s in (0.0, -40.0, -80.0, -120.0)]
    assert all(a > b for a, b in zip(rws, rws[1:], strict=False))  # monotonically decreasing
    assert all(r > 0 for r in rws)  # physical


def test_rmf_must_be_positive():
    with pytest.raises(ValueError):
        rw_from_ssp(-50.0, 0.0, 25.0)


# ----------------------------------------
# Step 2 — sp_ssp: baseline drift removal on synthetic
# ----------------------------------------


def _synthetic_sp(n=2000, drift=30.0, deflection=-60.0):
    # alternating shale (600) / clean (400) blocks with a linear baseline drift
    gr = np.where((np.arange(n) // 500) % 2 == 0, 120.0, 20.0)  # shale blocks even
    base_drift = np.linspace(0.0, drift, n)
    sp = base_drift + np.where(gr > 100, 0.0, deflection)
    return sp, gr


def test_ssp_reads_the_deflection_through_drift():
    sp, gr = _synthetic_sp()
    out = sp_ssp(sp, gr, gr_min=10.0, gr_max=130.0)
    # true deflection is -60 mV; drift removed, read within a few mV
    assert out["ssp_mv"] == pytest.approx(-60.0, abs=5.0)


def test_ssp_unreadable_without_populations():
    sp = np.zeros(300)
    gr = np.full(300, 60.0)  # mid-IGR everywhere: neither clean nor shale
    out = sp_ssp(sp, gr, gr_min=10.0, gr_max=130.0)
    assert np.isnan(out["ssp_mv"]) and out["n_clean"] == 0


# ----------------------------------------
# Step 3 — MHI: analytic cases and NaN policy
# ----------------------------------------


def test_mhi_analytic_and_bounds():
    rt = np.array([10.0, 10.0, 10.0])
    rxo = np.array([10.0, 4.9, np.nan])
    # rw/rmf = 1: MHI = sqrt(rxo/rt) -> [1.0, 0.7, nan]
    mhi = movable_hydrocarbon_index(rt, rxo, 0.05, 0.05)
    assert mhi[0] == pytest.approx(1.0)
    assert mhi[1] == pytest.approx(0.7, abs=1e-9)
    assert np.isnan(mhi[2])


def test_mhi_nonpositive_resistivity_is_nan():
    mhi = movable_hydrocarbon_index(np.array([0.0, -1.0]), np.array([1.0, 1.0]), 0.05, 0.5)
    assert np.isnan(mhi).all()


def test_mhi_positive_params_required():
    with pytest.raises(ValueError):
        movable_hydrocarbon_index(np.array([1.0]), np.array([1.0]), 0.0, 0.5)
