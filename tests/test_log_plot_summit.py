"""Render tests for the summit figures: M-N plot and the GR correlation panel."""

import numpy as np

from src.agents.log_plot import gr_correlation_panel, mn_plot
from src.petrophysics.lithology import MN_MATRIX_POINTS


def test_mn_plot_renders(tmp_path):
    rng_m = np.linspace(0.7, 0.9, 50)
    rng_n = np.linspace(0.5, 0.65, 50)
    name = mn_plot(rng_m, rng_n, MN_MATRIX_POINTS, tmp_path / "mn.png")
    assert (tmp_path / name).exists()


def test_gr_panel_renders_with_markers(tmp_path):
    depth = np.linspace(100, 1300, 400)
    wells = [
        {
            "uwi": f"15-135-{i}",
            "depth": depth,
            "gr": 60 + 30 * np.sin(depth / (50 + i * 7)),
            "marker_m": 1000.0 + i * 20,
        }
        for i in range(5)
    ]
    name = gr_correlation_panel(wells, tmp_path / "panel.png")
    assert name and (tmp_path / name).exists()


def test_gr_panel_needs_two_wells(tmp_path):
    only = [{"uwi": "x", "depth": np.arange(10.0), "gr": np.arange(10.0)}]
    assert gr_correlation_panel(only, tmp_path / "nope.png") is None
