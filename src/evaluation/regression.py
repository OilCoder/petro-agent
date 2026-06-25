"""VOLVE regression: compare the pipeline's outputs to an accepted interpretation.

This is the framework (metrics + thresholds + runner). The VOLVE LAS + accepted
interpretation are a large, navigation-gated Equinor download — NEEDS-HANDSON to
obtain (see planning/DECISIONS.md / AUTONOMOUS_RUN.md). Once present, point
``run_regression`` at the (predicted, reference) array pairs per well.
"""

from __future__ import annotations

from typing import Any

import numpy as np

VERSION = "0.1.0"

# Pass/fail thresholds (Charter Success criterion 2).
THRESHOLDS: dict[str, float] = {
    "PHIE": 0.03,  # MAE
    "Vsh": 0.10,  # MAE
    "Sw": 0.15,  # MAE
    "net_pay_rel": 0.20,  # relative
}


def mae(pred: np.ndarray, ref: np.ndarray) -> float:
    """NaN-aware mean absolute error over depths where both are finite."""
    p = np.asarray(pred, dtype=float)
    r = np.asarray(ref, dtype=float)
    mask = np.isfinite(p) & np.isfinite(r)
    if not mask.any():
        return float("nan")
    return float(np.mean(np.abs(p[mask] - r[mask])))


def evaluate_well(
    pred: dict[str, np.ndarray],
    ref: dict[str, np.ndarray],
    pred_net_pay: float,
    ref_net_pay: float,
    thresholds: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Evaluate one well against its accepted interpretation."""
    th = thresholds or THRESHOLDS
    metrics: dict[str, Any] = {}
    passed = True
    for curve in ("PHIE", "Vsh", "Sw"):
        if curve in pred and curve in ref:
            m = mae(pred[curve], ref[curve])
            ok = bool(np.isfinite(m) and m < th[curve])
            metrics[curve] = {"mae": m, "threshold": th[curve], "pass": ok}
            passed = passed and ok
    rel = abs(pred_net_pay - ref_net_pay) / ref_net_pay if ref_net_pay > 0 else float("inf")
    np_ok = bool(rel <= th["net_pay_rel"])
    metrics["net_pay"] = {
        "predicted": pred_net_pay,
        "reference": ref_net_pay,
        "rel_error": rel,
        "threshold": th["net_pay_rel"],
        "pass": np_ok,
    }
    passed = passed and np_ok
    return {"metrics": metrics, "pass": passed}


def run_regression(wells: list[dict[str, Any]]) -> dict[str, Any]:
    """Run the regression over a list of per-well dicts (pred/ref/net pay).

    Each well dict: ``{uwi, pred, ref, pred_net_pay, ref_net_pay}``.
    Returns per-well results and an overall pass (all wells must pass).
    """
    results = []
    for w in wells:
        res = evaluate_well(
            w["pred"], w["ref"], w["pred_net_pay"], w["ref_net_pay"]
        )
        results.append({"uwi": w.get("uwi", "?"), **res})
    overall = bool(results) and all(r["pass"] for r in results)
    return {"wells": results, "overall_pass": overall, "n_wells": len(results)}
