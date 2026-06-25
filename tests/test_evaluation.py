"""Tests for the Phase-8 VOLVE regression framework and version pinning."""

import numpy as np

from src.evaluation.regression import evaluate_well, mae, run_regression
from src.orchestrator.provenance import pin_versions


def test_mae_nan_aware():
    assert mae(np.array([1.0, np.nan, 3.0]), np.array([1.0, 5.0, 3.5])) == 0.25


def test_evaluate_well_passes_when_close():
    pred = {"PHIE": np.full(10, 0.20), "Vsh": np.full(10, 0.15), "Sw": np.full(10, 0.40)}
    ref = {"PHIE": np.full(10, 0.21), "Vsh": np.full(10, 0.16), "Sw": np.full(10, 0.45)}
    out = evaluate_well(pred, ref, pred_net_pay=10.0, ref_net_pay=11.0)
    assert out["pass"] is True
    assert out["metrics"]["PHIE"]["pass"] is True


def test_evaluate_well_fails_on_large_error():
    pred = {"PHIE": np.full(10, 0.20)}
    ref = {"PHIE": np.full(10, 0.40)}  # MAE 0.20 > 0.03
    out = evaluate_well(pred, ref, pred_net_pay=10.0, ref_net_pay=30.0)
    assert out["pass"] is False


def test_run_regression_overall():
    well = {
        "uwi": "VOLVE-1",
        "pred": {"PHIE": np.full(5, 0.2)},
        "ref": {"PHIE": np.full(5, 0.21)},
        "pred_net_pay": 10.0,
        "ref_net_pay": 11.0,
    }
    out = run_regression([well])
    assert out["n_wells"] == 1 and out["overall_pass"] is True


def test_pin_versions():
    v = pin_versions()
    assert "git_sha" in v
    assert v["libraries"]["numpy"] != "absent"
    assert v["engine_versions"]["calc_vsh"] == "0.1.0"
    assert v["seeds"]["monte_carlo"] == 42
