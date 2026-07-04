"""Field-study evidence pack (GA-1): the cross-well view the summit analyst worked from.

Deterministic, read-only summaries: a per-well depth-bin table (the same medians-per-bin
table the summit read to place every zone) and the cross-well distribution of the
engine-detected competent-rock top. Pure facts for the agent's observation surface — no
action, method or interval is ever suggested here.
"""

from __future__ import annotations

from typing import Any

import numpy as np

VERSION = "0.1.0"

_BIN_KEYS = ("RHOB", "GR", "RT", "NEUT", "NPHI")


def well_depth_bins(
    curves: dict[str, np.ndarray],
    depth: np.ndarray,
    bin_m: float = 100.0,
) -> dict[str, Any]:
    """Median of each key curve per depth bin — the well's structure at a glance.

    Args:
        curves: canonical curve arrays.
        depth: depth index (m).
        bin_m: bin height (m).

    Returns:
        ``{bin_m, rows: [{top, <curve>: median…}, …]}`` — a row only where any curve has
        >=10 finite samples in the bin; medians rounded to 2 decimals.
    """
    d = np.asarray(depth, dtype=float)
    if d.size == 0:
        return {"bin_m": bin_m, "rows": []}
    start = float(np.floor(d.min() / bin_m) * bin_m)
    rows: list[dict[str, float]] = []
    lo = start
    while lo < float(d.max()):
        row: dict[str, float] = {"top": lo}
        keep = False
        in_bin = (d >= lo) & (d < lo + bin_m)
        for k in _BIN_KEYS:
            arr = curves.get(k)
            if arr is None:
                continue
            vals = np.asarray(arr, dtype=float)[in_bin]
            vals = vals[np.isfinite(vals)]
            if vals.size >= 10:
                row[k] = round(float(np.median(vals)), 2)
                keep = True
        if keep:
            rows.append(row)
        lo += bin_m
    return {"bin_m": bin_m, "rows": rows}


def competent_top_m(
    rhob: np.ndarray | None,
    depth: np.ndarray,
    thresh: float = 2.35,
    frac: float = 0.75,
    win: int = 40,
) -> float | None:
    """First depth where a rolling window reads sustained consolidated density.

    The engine criterion behind the GR-panel marker: the shallowest depth from which a
    ``win``-sample window has more than ``frac`` of RHOB above ``thresh``. Returns None
    without RHOB or when no window qualifies (a fact, not a judgement).
    """
    if rhob is None:
        return None
    r = np.asarray(rhob, dtype=float)
    d = np.asarray(depth, dtype=float)
    ok = np.isfinite(r) & (r > thresh)
    for i in range(0, max(0, r.size - win), 10):
        if float(np.mean(ok[i : i + win])) > frac:
            return round(float(d[i]), 1)
    return None


def field_tops_summary(tops: list[float | None]) -> dict[str, Any]:
    """Cross-well distribution of the engine-detected competent tops (facts only).

    Returns ``{n_with_top, n_without, p10, p50, p90}`` (percentiles absent when < 3 tops).
    """
    vals = sorted(float(t) for t in tops if t is not None)
    out: dict[str, Any] = {"n_with_top": len(vals), "n_without": len(tops) - len(vals)}
    if len(vals) >= 3:
        arr = np.asarray(vals)
        out["p10"] = round(float(np.percentile(arr, 10)), 1)
        out["p50"] = round(float(np.percentile(arr, 50)), 1)
        out["p90"] = round(float(np.percentile(arr, 90)), 1)
    return out


def agreement_stats(a: np.ndarray, b: np.ndarray) -> dict[str, Any]:
    """Agreement between two per-depth estimates: r, median-absolute-difference, bias.

    The same trio the count-rate-vs-sonic validation gate used. Facts only — whether the
    agreement is acceptable is the analyst's judgement.

    Returns:
        ``{n, r, mad, bias}`` — ``{"n": 0}`` when fewer than 30 finite overlapping samples.
    """
    x = np.asarray(a, dtype=float)
    y = np.asarray(b, dtype=float)
    ok = np.isfinite(x) & np.isfinite(y)
    n = int(ok.sum())
    if n < 30:
        return {"n": n}
    xa, ya = x[ok], y[ok]
    r = float(np.corrcoef(xa, ya)[0, 1]) if float(np.std(xa)) > 0 and float(np.std(ya)) > 0 else 0.0
    return {
        "n": n,
        "r": round(r, 3),
        "mad": round(float(np.median(np.abs(xa - ya))), 4),
        "bias": round(float(np.median(xa - ya)), 4),
    }


def build_field_context(
    this_well_bins: dict[str, Any],
    this_well_top: float | None,
    tops_summary: dict[str, Any],
) -> dict[str, Any]:
    """Assemble the compact field-context block one well's observation carries."""
    return {
        "this_well_depth_bins": this_well_bins,
        "this_well_competent_top_m": this_well_top,
        "field_competent_tops": tops_summary,
        "note": "engine-computed medians and detection facts; interpretation is yours",
    }
