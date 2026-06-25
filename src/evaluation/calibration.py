"""Reliability diagram + Expected Calibration Error (ECE) infrastructure.

The numeric ECE pass/fail threshold is DEFERRED to Phase 7 exit (set as a logged
manifest decision once measured on VOLVE) — this module provides the measurement,
not the threshold.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

VERSION = "0.1.0"


def reliability_bins(
    confidences: np.ndarray, correct: np.ndarray, n_bins: int = 10
) -> dict[str, np.ndarray]:
    """Bin predictions by confidence and return per-bin mean confidence and accuracy."""
    conf = np.asarray(confidences, dtype=float)
    corr = np.asarray(correct, dtype=float)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    idx = np.clip(np.digitize(conf, edges[1:-1]), 0, n_bins - 1)
    mean_conf = np.full(n_bins, np.nan)
    acc = np.full(n_bins, np.nan)
    count = np.zeros(n_bins)
    for b in range(n_bins):
        sel = idx == b
        count[b] = sel.sum()
        if count[b]:
            mean_conf[b] = conf[sel].mean()
            acc[b] = corr[sel].mean()
    return {"mean_conf": mean_conf, "accuracy": acc, "count": count}


def expected_calibration_error(
    confidences: np.ndarray, correct: np.ndarray, n_bins: int = 10
) -> float:
    """ECE = sum over bins of (bin weight) * |accuracy - mean confidence|."""
    bins = reliability_bins(confidences, correct, n_bins)
    total = float(bins["count"].sum())
    if total == 0:
        return 0.0
    ece = 0.0
    for b in range(n_bins):
        if bins["count"][b]:
            ece += (bins["count"][b] / total) * abs(bins["accuracy"][b] - bins["mean_conf"][b])
    return float(ece)


def reliability_diagram(
    confidences: np.ndarray, correct: np.ndarray, out_path: str | Path, n_bins: int = 10
) -> float:
    """Write a reliability-diagram PNG and return the ECE."""
    bins = reliability_bins(confidences, correct, n_bins)
    ece = expected_calibration_error(confidences, correct, n_bins)
    fig, ax = plt.subplots(figsize=(4.5, 4.5))
    ax.plot([0, 1], [0, 1], "k--", lw=1, label="perfect")
    valid = ~np.isnan(bins["mean_conf"])
    ax.plot(bins["mean_conf"][valid], bins["accuracy"][valid], "o-", label="model")
    ax.set_xlabel("confidence")
    ax.set_ylabel("accuracy")
    ax.set_title(f"Reliability diagram (ECE={ece:.3f})")
    ax.legend(fontsize=8)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=90, bbox_inches="tight")
    plt.close(fig)
    return ece
