"""Deterministic exploratory data analysis (EDA) tools for the v2 analyst agent.

Read-only functions that turn raw curve arrays into STRUCTURED observations (numbers and
flags) the agent reasons over — the agent observes, it never computes by hand. Every
function returns a JSON-serializable dict (no raw arrays), so it can be pre-computed,
fed to the LLM as a compact digest, and recorded in the ledger. Interpretive thresholds
(``line_tol``, ``rt_low_pctile``, percentiles) are CITED parameters, not hidden choices.
"""

from __future__ import annotations

from typing import Any

import numpy as np

VERSION = "0.1.0"

# Reference matrix densities for the N-D lithology screen (g/cc).
_MATRIX = {"sandstone": 2.65, "limestone": 2.71, "dolomite": 2.87}


def _finite(a: np.ndarray) -> np.ndarray:
    a = np.asarray(a, dtype=float)
    return a[np.isfinite(a)]


def curve_inventory(curves: dict[str, np.ndarray], depth_m: np.ndarray) -> dict[str, Any]:
    """Report which curves exist, their valid fraction, and value range."""
    n = int(np.asarray(depth_m).size)
    out: dict[str, Any] = {}
    for name, arr in curves.items():
        f = _finite(arr)
        out[name] = {
            "present": True,
            "pct_valid": round(float(f.size) / n, 3) if n else 0.0,
            "min": round(float(f.min()), 3) if f.size else None,
            "max": round(float(f.max()), 3) if f.size else None,
        }
    return out


def depth_coverage(
    curves: dict[str, np.ndarray], depth_m: np.ndarray, step_m: float
) -> dict[str, Any]:
    """Report logged interval, sample count, and the count of internal gaps."""
    d = np.asarray(depth_m, dtype=float)
    if d.size < 2:
        return {"top": None, "base": None, "gross_m": 0.0, "n_samples": int(d.size), "n_gaps": 0}
    diffs = np.diff(d)
    n_gaps = int(np.count_nonzero(diffs > 1.5 * step_m))
    return {
        "top": round(float(d[0]), 2),
        "base": round(float(d[-1]), 2),
        "gross_m": round(float(d[-1] - d[0]), 2),
        "n_samples": int(d.size),
        "n_gaps": n_gaps,
    }


def histogram_stats(curve: np.ndarray, bins: int = 20) -> dict[str, Any]:
    """Robust distribution summary (p5/p50/p95, mode bin, skew flag). No raw array out."""
    f = _finite(curve)
    if f.size == 0:
        return {
            "n": 0,
            "p5": None,
            "p50": None,
            "p95": None,
            "mode_bin": None,
            "right_skewed": None,
        }
    p5, p50, p95 = (float(x) for x in np.percentile(f, [5, 50, 95]))
    counts, edges = np.histogram(f, bins=bins)
    mode_i = int(np.argmax(counts))
    return {
        "n": int(f.size),
        "p5": round(p5, 3),
        "p50": round(p50, 3),
        "p95": round(p95, 3),
        "mode_bin": [round(float(edges[mode_i]), 3), round(float(edges[mode_i + 1]), 3)],
        "right_skewed": bool(float(f.mean()) > p50),
    }


def crossplot_density_neutron(
    rhob: np.ndarray, nphi: np.ndarray, line_tol: float = 0.05
) -> dict[str, Any]:
    """Screen the N-D crossplot: nearest-lithology share and a gas-effect flag.

    ``line_tol`` is a CITED tolerance (g/cc) for "near" a matrix line.
    """
    r, p = np.asarray(rhob, dtype=float), np.asarray(nphi, dtype=float)
    valid = np.isfinite(r) & np.isfinite(p)
    if int(valid.sum()) == 0:
        return {"n": 0, "nearest": None, "shares": {}, "gas_effect_flag": False}
    rv, pv = r[valid], p[valid]
    # share of points near each matrix line in (NPHI, RHOB) space
    shares: dict[str, float] = {}
    for name, rma in _MATRIX.items():
        rho_line = rma - pv * (rma - 1.0)  # matrix line in (NPHI, RHOB)
        shares[name] = round(float(np.mean(np.abs(rv - rho_line) <= line_tol)), 3)
    nearest = max(shares, key=lambda k: shares[k])
    # gas effect: neutron reads low while density reads low (cross-over) in clean rock
    gas = bool(np.mean((pv < 0.10) & (rv < 2.4)) > 0.05)
    return {"n": int(valid.sum()), "nearest": nearest, "shares": shares, "gas_effect_flag": gas}


def low_resistivity_scan(
    rt: np.ndarray, depth_m: np.ndarray, phie: np.ndarray, rt_low_pctile: int = 10
) -> dict[str, Any]:
    """Flag intervals where RT is low (percentile-based, CITED) but PHIE is decent.

    Returns the count and the depth spans — a hint the agent may use to add a saturation
    analysis (e.g. select Simandoux/Pickett). It computes nothing the report trusts.
    """
    rt_a, d, phi = (np.asarray(x, dtype=float) for x in (rt, depth_m, phie))
    valid = np.isfinite(rt_a) & np.isfinite(phi) & (rt_a > 0)
    if int(valid.sum()) < 10:
        return {"rt_threshold": None, "n_flagged": 0, "intervals": []}
    thr = float(np.percentile(rt_a[valid], rt_low_pctile))
    flag = valid & (rt_a <= thr) & (phi > 0.08)
    intervals: list[list[float]] = []
    idx = np.where(flag)[0]
    if idx.size:
        start = idx[0]
        for k in range(1, idx.size + 1):
            if k == idx.size or idx[k] != idx[k - 1] + 1:
                intervals.append([round(float(d[start]), 1), round(float(d[idx[k - 1]]), 1)])
                if k < idx.size:
                    start = idx[k]
    return {
        "rt_threshold": round(thr, 2),
        "n_flagged": int(flag.sum()),
        "intervals": intervals[:10],
    }


def gr_baseline_check(gr: np.ndarray) -> dict[str, Any]:
    """Report the clean/shale GR endpoints actually present (p5/p95)."""
    f = _finite(gr)
    if f.size == 0:
        return {"gr_clean_p5": None, "gr_shale_p95": None}
    p5, p95 = (float(x) for x in np.percentile(f, [5, 95]))
    return {"gr_clean_p5": round(p5, 1), "gr_shale_p95": round(p95, 1)}


def badhole_summary(quality_map: np.ndarray) -> dict[str, Any]:
    """Fraction of depth in GOOD / DEGRADED / EXCLUDED from the QC quality map."""
    q = np.asarray(quality_map, dtype=object)
    n = int(q.size)
    if n == 0:
        return {"GOOD": 0.0, "DEGRADED": 0.0, "EXCLUDED": 0.0}
    return {
        tier: round(float(np.count_nonzero(q == tier)) / n, 3)
        for tier in ("GOOD", "DEGRADED", "EXCLUDED")
    }
