"""Golden tests for the deterministic EDA tools (V2-B)."""

import numpy as np

from src.eda.explore import (
    badhole_summary,
    crossplot_density_neutron,
    curve_inventory,
    depth_coverage,
    gr_baseline_check,
    histogram_stats,
    low_resistivity_scan,
)

DEPTH = np.arange(0.0, 50.0, 0.5)  # 100 samples, step 0.5


def test_curve_inventory_reports_validity():
    gr = np.full(100, 50.0)
    gr[:10] = np.nan
    inv = curve_inventory({"GR": gr}, DEPTH)
    assert inv["GR"]["pct_valid"] == 0.9
    assert inv["GR"]["min"] == 50.0 and inv["GR"]["max"] == 50.0


def test_depth_coverage_detects_gap():
    d = np.concatenate([np.arange(0, 10, 0.5), np.arange(20, 30, 0.5)])  # one big gap
    cov = depth_coverage({}, d, 0.5)
    assert cov["n_gaps"] == 1 and cov["gross_m"] == 29.5


def test_histogram_stats_percentiles():
    h = histogram_stats(np.arange(0.0, 101.0))
    assert h["p50"] == 50.0 and h["n"] == 101


def test_histogram_stats_empty():
    h = histogram_stats(np.full(10, np.nan))
    assert h["n"] == 0 and h["p50"] is None


def test_crossplot_nd_nearest_lithology():
    # RHOB ~ limestone matrix line at low NPHI -> nearest limestone
    nphi = np.full(50, 0.05)
    rhob = 2.71 - nphi * (2.71 - 1.0)  # exact limestone line
    cp = crossplot_density_neutron(rhob, nphi, line_tol=0.05)
    assert cp["nearest"] == "limestone" and cp["shares"]["limestone"] == 1.0


def test_low_resistivity_scan_flags_interval():
    rt = np.full(100, 50.0)
    rt[40:50] = 2.0  # low-resistivity zone
    # neutral RT-percentile scan: no porosity cross (no pay-screen interpretation)
    scan = low_resistivity_scan(rt, DEPTH, rt_low_pctile=10)
    assert scan["n_flagged"] >= 5 and scan["intervals"]


def test_gr_baseline_check():
    gr = np.linspace(20.0, 120.0, 100)
    b = gr_baseline_check(gr)
    # neutral percentiles, no clean/shale label
    assert b["gr_p5"] < 30 and b["gr_p95"] > 110


def test_badhole_summary_fractions():
    q = np.array(["GOOD"] * 80 + ["DEGRADED"] * 15 + ["EXCLUDED"] * 5, dtype=object)
    s = badhole_summary(q)
    assert s["GOOD"] == 0.8 and s["DEGRADED"] == 0.15 and s["EXCLUDED"] == 0.05
