"""Golden tests for the summit lithology additions: Arps Rw-T, M-N crossplot, Umaa."""

import numpy as np
import pytest

from src.petrophysics.lithology import litho_mn, rw_arps_temperature, umaa_apparent

# ----------------------------------------
# Step 1 — Arps temperature correction of Rw
# ----------------------------------------


def test_rw_arps_analytic_case():
    # T_f = 15 + 27.5 * 1300/1000 = 50.75 C; Rw_f = 0.10 * (15+21.5)/(50.75+21.5)
    res = rw_arps_temperature(0.10, 15.0, 27.5, 1300.0)
    assert res["t_formation_c"] == pytest.approx(50.75, abs=0.01)
    assert res["rw_formation"] == pytest.approx(0.10 * 36.5 / 72.25, abs=1e-4)


def test_rw_arps_monotonic_with_depth():
    shallow = rw_arps_temperature(0.10, 15.0, 27.5, 500.0)["rw_formation"]
    deep = rw_arps_temperature(0.10, 15.0, 27.5, 2000.0)["rw_formation"]
    assert deep < shallow < 0.10  # hotter formation -> lower Rw


def test_rw_arps_zero_gradient_is_identity():
    res = rw_arps_temperature(0.08, 20.0, 0.0, 1500.0)
    assert res["rw_formation"] == pytest.approx(0.08)


def test_rw_arps_rejects_nonpositive_rw():
    with pytest.raises(ValueError):
        rw_arps_temperature(0.0, 15.0, 27.5, 1000.0)


# ----------------------------------------
# Step 2 — M-N lithology crossplot
# ----------------------------------------


def test_litho_mn_pure_calcite_lands_on_calcite():
    # calcite matrix: RHOB 2.71, NPHI 0.00, DT 47.5 -> M≈0.827, N≈0.585
    res = litho_mn(np.array([2.71]), np.array([0.0]), np.array([47.5]))
    assert res["shares"].get("calcite") == 1.0
    assert res["m"][0] == pytest.approx(0.827, abs=0.01)
    assert res["n"][0] == pytest.approx(0.585, abs=0.01)


def test_litho_mn_pure_dolomite_lands_on_dolomite():
    # dolomite matrix: RHOB 2.87, NPHI 0.035, DT 43.5 -> M≈0.778, N≈0.516
    res = litho_mn(np.array([2.87]), np.array([0.035]), np.array([43.5]))
    assert res["shares"].get("dolomite") == 1.0


def test_litho_mn_nan_passthrough_and_bad_denominator():
    res = litho_mn(np.array([np.nan, 1.0]), np.array([0.1, 0.1]), np.array([60.0, 60.0]))
    assert np.isnan(res["m"][0])  # NaN input
    assert np.isnan(res["m"][1])  # RHOB at fluid density -> undefined
    assert res["n_samples"] == 0


# ----------------------------------------
# Step 3 — Umaa apparent matrix
# ----------------------------------------


def test_umaa_pure_calcite_and_quartz():
    # calcite: PEF 5.08 * RHOB 2.71 ≈ 13.77 barns/cc at zero porosity
    cal = umaa_apparent(np.array([5.08]), np.array([2.71]), np.array([0.0]))
    assert cal["shares"].get("calcite") == 1.0
    assert cal["umaa"][0] == pytest.approx(13.77, abs=0.1)
    # quartz: PEF 1.81 * RHOB 2.65 ≈ 4.80
    qtz = umaa_apparent(np.array([1.81]), np.array([2.65]), np.array([0.0]))
    assert qtz["shares"].get("quartz") == 1.0


def test_umaa_porosity_correction_moves_toward_matrix():
    # same tool readings with porosity: Umaa must exceed the raw U (fluid removed)
    porous = umaa_apparent(np.array([4.0]), np.array([2.40]), np.array([0.20]))
    zero = umaa_apparent(np.array([4.0]), np.array([2.40]), np.array([0.0]))
    assert porous["umaa"][0] > zero["umaa"][0]


def test_umaa_nan_passthrough():
    res = umaa_apparent(np.array([np.nan]), np.array([2.7]), np.array([0.1]))
    assert np.isnan(res["umaa"][0]) and res["n_samples"] == 0
