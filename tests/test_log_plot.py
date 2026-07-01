"""Smoke tests for figure generation (composite log, Pickett plot, collection)."""

import numpy as np

from src.agents.log_plot import (
    _safe,
    buckles_plot,
    composite_log_plot,
    distribution_plot,
    generate_figures,
    generate_uncertainty_figures,
    hingle_plot,
    mc_distribution_plot,
    pickett_plot,
    tornado_plot,
)
from src.params.schema import ParamValue

DEPTH = np.linspace(100.0, 200.0, 50)
GR = np.linspace(20.0, 100.0, 50)
RT = np.linspace(2.0, 50.0, 50)
VSH = np.linspace(0.0, 0.5, 50)
PHIE = np.linspace(0.05, 0.3, 50)
SW = np.linspace(0.2, 0.9, 50)
CURVES = {"GR": GR, "RT": RT, "RHOB": np.full(50, 2.5), "NPHI": np.full(50, 0.2)}


def test_safe_strips_commas_and_slashes():
    assert _safe("15-135-24,974-00/00") == "15-135-24974-00_00"


def test_composite_log_plot_writes_png(tmp_path):
    flag = (PHIE > 0.1).astype(float)
    name = composite_log_plot(DEPTH, CURVES, VSH, PHIE, SW, flag, tmp_path / "comp.png")
    assert name == "comp.png"
    assert (tmp_path / "comp.png").exists() and (tmp_path / "comp.png").stat().st_size > 0


def test_pickett_plot_writes_png(tmp_path):
    name = pickett_plot(RT, PHIE, 1.0, 2.0, 0.04, tmp_path / "pick.png")
    assert name == "pick.png"
    assert (tmp_path / "pick.png").exists()


def test_buckles_plot_writes_png(tmp_path):
    name = buckles_plot(PHIE, SW, tmp_path / "buckles.png")
    assert name == "buckles.png"
    assert (tmp_path / "buckles.png").exists() and (tmp_path / "buckles.png").stat().st_size > 0


def test_hingle_plot_writes_png(tmp_path):
    name = hingle_plot(RT, PHIE, 2.0, tmp_path / "hingle.png")
    assert name == "hingle.png"
    assert (tmp_path / "hingle.png").exists()


def test_distribution_plot_writes_png_and_skips_none(tmp_path):
    name = distribution_plot({"GR": GR, "PHIE": PHIE, "Sw": SW, "DT": None}, tmp_path / "dist.png")
    assert name == "dist.png"
    assert (tmp_path / "dist.png").exists() and (tmp_path / "dist.png").stat().st_size > 0


def test_tornado_plot_writes_png(tmp_path):
    name = tornado_plot({"Rw": 125.4, "m": 101.3, "a": 64.2, "n": 38.9}, tmp_path / "tornado.png")
    assert name == "tornado.png" and (tmp_path / "tornado.png").exists()


def test_mc_distribution_plot_writes_png(tmp_path):
    reals = list(np.linspace(80.0, 260.0, 200))
    name = mc_distribution_plot(reals, 100.0, 180.0, 240.0, tmp_path / "mc.png")
    assert name == "mc.png" and (tmp_path / "mc.png").exists()


def test_generate_uncertainty_figures_appends_human_only(tmp_path):
    ledger = {
        "run": {"uwi": "15-135-25990-00-00"},
        "uncertainty": {
            "sensitivity": {"swings_m": {"Rw": 125.4, "m": 101.3}},
            "realizations": [100.0, 150.0, 200.0, 180.0, 160.0],
            "net_pay_p10": 120.0,
            "net_pay_p50": 170.0,
            "net_pay_p90": 210.0,
        },
        "figures": [],
    }
    added = generate_uncertainty_figures(ledger, tmp_path)
    assert {f["title"] for f in added} == {
        "Sensitivity tornado",
        "Net-pay Monte-Carlo distribution",
    }
    assert len(ledger["figures"]) == 2
    for f in added:
        assert (tmp_path / f["file"]).exists()


def test_generate_uncertainty_figures_empty_without_uncertainty(tmp_path):
    assert generate_uncertainty_figures({"run": {"uwi": "x"}}, tmp_path) == []


def test_generate_figures_collects_composite_and_pickett(tmp_path):
    params = {
        "vsh_cutoff": ParamValue(0.35, "v/v", "default", "x"),
        "phie_cutoff": ParamValue(0.10, "v/v", "default", "x"),
        "sw_cutoff": ParamValue(0.50, "v/v", "default", "x"),
        "a": ParamValue(1.0, "-", "default", "x"),
        "m": ParamValue(2.0, "-", "default", "x"),
        "n": ParamValue(2.0, "-", "default", "x"),
        "Rw": ParamValue(0.04, "ohm-m", "default", "x"),
    }
    figs = generate_figures("15-135-24,974-00-00", DEPTH, CURVES, VSH, PHIE, SW, params, tmp_path)
    titles = {f["title"] for f in figs}
    assert {
        "Composite log",
        "Pickett plot",
        "Buckles plot",
        "Hingle plot",
        "Distributions",
    } <= titles
    for f in figs:
        assert (tmp_path / f["file"]).exists()
