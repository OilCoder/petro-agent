"""Smoke tests for figure generation (composite log, Pickett plot, collection)."""

import numpy as np

from src.agents.log_plot import _safe, composite_log_plot, generate_figures, pickett_plot
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
    assert "Composite log" in titles and "Pickett plot" in titles
    for f in figs:
        assert (tmp_path / f["file"]).exists()
