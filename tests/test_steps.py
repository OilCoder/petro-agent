"""Tests for the discrete compute steps (shared by the pipeline and the agentic loop)."""

import numpy as np

from src.orchestrator.steps import phie_step, sw_step, vsh_step

N = 40
CURVES = {
    "GR": np.linspace(20.0, 120.0, N),
    "RHOB": np.full(N, 2.5),
    "NPHI": np.full(N, 0.2),
    "RT": np.full(N, 10.0),
}
P = {
    "rho_fl": 1.0,
    "rho_ma": 2.71,
    "phie_max": 0.45,
    "phi_sh_d": 0.1,
    "phi_sh_n": 0.3,
    "a": 1.0,
    "m": 2.0,
    "n": 2.0,
    "Rw": 0.04,
}


def _in_bounds(arr, lo, hi):
    finite = arr[np.isfinite(arr)]
    return bool(np.all((finite >= lo) & (finite <= hi)))


def test_default_chain_is_finite_and_in_bounds():
    vsh, vcal = vsh_step(CURVES, 20.0, 120.0, "old_rocks")
    phie, _ = phie_step(CURVES, vsh, P)
    sw, _ = sw_step(CURVES, phie, vsh, P)
    assert _in_bounds(vsh, 0.0, 1.0)
    assert _in_bounds(phie, 0.0, P["phie_max"])
    assert _in_bounds(sw, 0.0, 1.0)
    assert vcal["vsh_method"]["chosen_by_model"] is False


def test_vsh_method_choice_is_traced_and_changes_result():
    default, _ = vsh_step(CURVES, 20.0, 120.0, "old_rocks")
    linear, cal = vsh_step(CURVES, 20.0, 120.0, "old_rocks", "vsh_linear")
    assert cal["vsh_method"]["value"] == "vsh_linear" and cal["vsh_method"]["chosen_by_model"]
    assert float(np.nanmean(linear)) != float(np.nanmean(default))  # the choice has consequences


def test_agent_can_select_non_gr_neutron_density_vsh():
    # the non-GR method is now selectable (was engine-internal); needs pf for its params
    default, _ = vsh_step(CURVES, 20.0, 120.0, "old_rocks")
    nd, cal = vsh_step(CURVES, 20.0, 120.0, "old_rocks", "vsh_neutron_density", pf=P)
    assert (
        cal["vsh_method"]["value"] == "vsh_neutron_density" and cal["vsh_method"]["chosen_by_model"]
    )
    assert _in_bounds(nd, 0.0, 1.0)
    assert float(np.nanmean(nd)) != float(
        np.nanmean(default)
    )  # a genuinely different (non-GR) read


def test_sw_method_choice_changes_result():
    vsh, _ = vsh_step(CURVES, 20.0, 120.0, "old_rocks")
    phie, _ = phie_step(CURVES, vsh, P)
    archie, _ = sw_step(CURVES, phie, vsh, P)
    simandoux, _ = sw_step(CURVES, phie, vsh, P, "sw_simandoux")
    assert float(np.nanmean(archie)) != float(np.nanmean(simandoux))
