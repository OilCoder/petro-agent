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

from src.petrophysics.registry import available_methods

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
    """Compute the N-D crossplot per-matrix point-shares (and the nearest matrix line).

    ``line_tol`` is a CITED tolerance (g/cc) for "near" a matrix line. ``nearest`` is exposed
    ONLY for the agent-invoked lithology tool; ``build_eda_digest`` surfaces the shares alone
    (the neutral fact), never the nearest label — naming the dominant lithology is the analyst's.
    """
    r, p = np.asarray(rhob, dtype=float), np.asarray(nphi, dtype=float)
    valid = np.isfinite(r) & np.isfinite(p)
    if int(valid.sum()) == 0:
        return {"n": 0, "nearest": None, "shares": {}}
    rv, pv = r[valid], p[valid]
    # share of points near each matrix line in (NPHI, RHOB) space
    shares: dict[str, float] = {}
    for name, rma in _MATRIX.items():
        rho_line = rma - pv * (rma - 1.0)  # matrix line in (NPHI, RHOB)
        shares[name] = round(float(np.mean(np.abs(rv - rho_line) <= line_tol)), 3)
    nearest = max(shares, key=lambda k: shares[k])
    return {"n": int(valid.sum()), "nearest": nearest, "shares": shares}


def low_resistivity_scan(
    rt: np.ndarray, depth_m: np.ndarray, rt_low_pctile: int = 10
) -> dict[str, Any]:
    """Report depth spans where RT sits in its lowest percentile band (percentile-based, CITED).

    A neutral resistivity observation: the count and the depth spans below the RT percentile
    threshold. No porosity cross, no interpretation, no method suggestion — it computes nothing
    the report trusts, and it does not identify pay (that is the analyst's call).
    """
    rt_a, d = (np.asarray(x, dtype=float) for x in (rt, depth_m))
    valid = np.isfinite(rt_a) & (rt_a > 0)
    if int(valid.sum()) < 10:
        return {"rt_threshold": None, "n_flagged": 0, "intervals": []}
    thr = float(np.percentile(rt_a[valid], rt_low_pctile))
    flag = valid & (rt_a <= thr)
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
    """Report the GR p5/p95 endpoints present (neutral percentiles, no clean/shale label)."""
    f = _finite(gr)
    if f.size == 0:
        return {"gr_p5": None, "gr_p95": None}
    p5, p95 = (float(x) for x in np.percentile(f, [5, 95]))
    return {"gr_p5": round(p5, 1), "gr_p95": round(p95, 1)}


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


def invasion_scan(
    rt: np.ndarray,
    rxo: np.ndarray | None = None,
    rmed: np.ndarray | None = None,
) -> dict[str, Any]:
    """Summarize the invasion profile from multi-depth resistivities (raw-curve facts only).

    In water-based mud, a shallow reading above the deep one (``Rxo/RT > 1``) marks invaded —
    hence permeable — rock. Returns fractions and median ratios; never a permeability number.

    Args:
        rt: deep resistivity (ohm-m).
        rxo: shallow/flushed-zone resistivity (ohm-m), optional.
        rmed: medium resistivity (ohm-m), optional.

    Returns:
        ``{n, frac_invaded, frac_reversed, median_rxo_rt, median_rmed_rt}`` — ratio keys only
        where the corresponding curve overlaps; ``{"n": 0}`` when nothing overlaps.
    """
    rt_a = np.asarray(rt, dtype=float)
    out: dict[str, Any] = {"n": 0}
    if rxo is not None:
        rxo_a = np.asarray(rxo, dtype=float)
        ok = np.isfinite(rt_a) & np.isfinite(rxo_a) & (rt_a > 0) & (rxo_a > 0)
        n = int(ok.sum())
        out["n"] = n
        if n:
            ratio = rxo_a[ok] / rt_a[ok]
            out["frac_invaded"] = round(float(np.mean(ratio > 1.2)), 3)
            out["frac_reversed"] = round(float(np.mean(ratio < 0.8)), 3)
            out["median_rxo_rt"] = round(float(np.median(ratio)), 3)
    if rmed is not None:
        rmed_a = np.asarray(rmed, dtype=float)
        ok_m = np.isfinite(rt_a) & np.isfinite(rmed_a) & (rt_a > 0) & (rmed_a > 0)
        if int(ok_m.sum()):
            out["median_rmed_rt"] = round(float(np.median(rmed_a[ok_m] / rt_a[ok_m])), 3)
            out["n"] = max(out["n"], int(ok_m.sum()))
    return out


def service_porosity_summary(curves: dict[str, Any]) -> dict[str, float]:
    """Mean of the service-company porosity curves (fractions), for the §14 cross-check.

    PHID_SVC/NPHI_DOL/NPHI_SS arrive in PU (%) on most vintages — a median above 1.5 marks
    percent units and is divided by 100. Evidence for the report; never a substitute for the
    engine's computed porosity.
    """
    out: dict[str, float] = {}
    for name in ("PHID_SVC", "NPHI_DOL", "NPHI_SS"):
        arr = curves.get(name)
        if arr is None:
            continue
        a = np.asarray(arr, dtype=float)
        finite = a[np.isfinite(a)]
        if finite.size < 20:
            continue
        if float(np.median(finite)) > 1.5:  # percent units
            finite = finite / 100.0
        out[name.lower() + "_mean"] = round(float(np.mean(finite)), 4)
    return out


def microlog_scan(mnor: np.ndarray | None, minv: np.ndarray | None) -> dict[str, Any]:
    """Microlog separation summary: positive MNOR-MINV separation marks mudcake (permeable).

    Returns ``{n, frac_permeable, median_separation}`` or ``{"n": 0}`` without overlap.
    Raw-curve facts; the permeability CALL stays with the analyst.
    """
    if mnor is None or minv is None:
        return {"n": 0}
    a = np.asarray(mnor, dtype=float)
    b = np.asarray(minv, dtype=float)
    ok = np.isfinite(a) & np.isfinite(b)
    n = int(ok.sum())
    if not n:
        return {"n": 0}
    sep = a[ok] - b[ok]
    return {
        "n": n,
        "frac_permeable": round(float(np.mean(sep > 0.0)), 3),
        "median_separation": round(float(np.median(sep)), 3),
    }


def build_eda_digest(ctx: dict[str, Any]) -> dict[str, Any]:
    """Pre-compute the compact EDA observations the agent reads (it observes, never computes).

    Summarized data only (per-curve stats, coverage, GR baseline, badhole, litho/low-res screens) —
    never the raw arrays. Used by both the single-shot path and the agentic loop.
    """
    curves = ctx["curves"]
    depth = ctx["depth_m"]
    digest: dict[str, Any] = {
        "curves_present": sorted(curves),
        "curve_inventory": curve_inventory(curves, depth),
        "depth_coverage": depth_coverage(curves, depth, ctx.get("step_m", 0.5)),
        "badhole": badhole_summary(ctx["quality_map"]),
        "available_methods": available_methods(curves),
    }
    if "GR" in curves:
        digest["gr_baseline"] = gr_baseline_check(curves["GR"])
    if "RT" in curves:
        digest["low_resistivity"] = low_resistivity_scan(curves["RT"], depth)
    if "RT" in curves and ("RXO" in curves or "RMED" in curves):
        digest["invasion"] = invasion_scan(curves["RT"], curves.get("RXO"), curves.get("RMED"))
    svc = service_porosity_summary(curves)
    if svc:
        digest["service_porosity"] = svc
    ml = microlog_scan(curves.get("MNOR"), curves.get("MINV"))
    if ml.get("n"):
        digest["microlog"] = ml
    if "RHOB" in curves and "NPHI" in curves:
        cp = crossplot_density_neutron(curves["RHOB"], curves["NPHI"])
        # surface the neutral point-shares only — never the 'nearest' label (that is the analyst's)
        digest["lithology"] = {"n": cp["n"], "shares": cp["shares"]}
    return digest
