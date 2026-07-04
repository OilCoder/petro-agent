"""Tests for the agentic loop action frontier (physics prereqs + recompute invalidation)."""

import numpy as np

from src.agents.loop_actions import (
    available_actions,
    depth_quality_profile,
    invalidate_downstream,
    observe,
    seed_baseline_sections,
)
from src.params.schema import ParamValue

_FULL = {"GR", "RHOB", "NPHI", "RT"}


def _pv(v: float) -> ParamValue:
    return ParamValue(v, "-", "default", "x")


def _cmp_ctx() -> dict:
    n = 30
    return {
        "curves": {
            "GR": np.linspace(20.0, 100.0, n),
            "RHOB": np.linspace(2.2, 2.6, n),
            "NPHI": np.linspace(0.30, 0.05, n),
            "RT": np.linspace(2.0, 80.0, n),
        },
        "params": {
            "gr_min": _pv(20.0),
            "gr_max": _pv(120.0),
            "rho_fl": _pv(1.0),
            "rho_ma": _pv(2.65),
            "phie_max": _pv(0.45),
            "phi_sh_d": _pv(0.10),
            "phi_sh_n": _pv(0.35),
            "a": _pv(1.0),
            "m": _pv(2.0),
            "n": _pv(2.0),
            "Rw": _pv(0.04),
        },
        "variant": "old_rocks",
        "vsh": np.linspace(0.1, 0.6, n),
        "phie": np.linspace(0.05, 0.2, n),
    }


def test_seed_vsh_selected_matches_a_real_method_key():
    # the [FIJO] Vsh section's "Selected" ✓ was empty in free mode: the fallback built
    # "vsh_larionov_old_rocks" but the method key is "vsh_larionov_old" -> no match
    def _pv(v: float) -> ParamValue:
        return ParamValue(v, "-", "default", "x")

    ctx = {
        "curves": {"GR": np.linspace(20.0, 100.0, 30)},  # no RHOB/NPHI -> GR methods only
        "params": {
            "gr_min": _pv(20.0),
            "gr_max": _pv(120.0),
            "rho_fl": _pv(1.0),
            "rho_ma": _pv(2.65),
            "phie_max": _pv(0.45),
            "phi_sh_d": _pv(0.10),
            "phi_sh_n": _pv(0.35),
            "a": _pv(1.0),
            "m": _pv(2.0),
            "n": _pv(2.0),
            "Rw": _pv(0.04),
        },
        "variant": "old_rocks",
    }
    ledger: dict = {}
    seed_baseline_sections(ledger, ctx)
    cmp = ledger["vsh_comparison"]
    assert cmp["selected"] == "vsh_larionov_old"
    assert cmp["selected"] in cmp["methods"]  # so the report actually marks a ✓


def test_physics_prereqs_gate_the_chain():
    # nothing computed yet: only Vsh (and curve-only actions) + finish
    acts = available_actions(set(), _FULL)
    assert "compute_vsh" in acts
    assert "compute_phie" not in acts  # needs vsh
    assert "compute_sw" not in acts  # needs phie
    assert "finish" in acts


def test_phie_unlocks_after_vsh_sw_after_phie():
    assert "compute_phie" in available_actions({"vsh"}, _FULL)
    assert "compute_sw" not in available_actions({"vsh"}, _FULL)
    assert "compute_sw" in available_actions({"vsh", "phie"}, _FULL)
    assert "apply_cutoffs" in available_actions({"vsh", "phie", "sw"}, _FULL)


def test_optionals_need_phie_and_sw():
    assert "permeability" not in available_actions({"vsh", "phie"}, _FULL)
    assert "permeability" in available_actions({"vsh", "phie", "sw"}, _FULL)


def test_missing_curve_blocks_action():
    no_rt = {"GR", "RHOB", "NPHI"}
    assert "compute_sw" not in available_actions({"vsh", "phie"}, no_rt)  # sw needs RT
    assert "low_res_scan" not in available_actions({"vsh", "phie"}, no_rt)


def test_zone_stats_needs_netpay():
    assert "zone_stats" not in available_actions({"vsh", "phie", "sw"}, _FULL)
    assert "zone_stats" in available_actions({"vsh", "phie", "sw", "netpay"}, _FULL)


def test_zone_of_interest_and_depth_quality_available():
    acts = available_actions(set(), _FULL)
    assert "set_zone_of_interest" in acts  # always physics-valid (restrict the interval)
    assert "depth_quality" in acts  # RHOB present
    # depth_quality needs RHOB; set_zone_of_interest is always offered
    no_rhob = {"GR", "RT"}
    assert "depth_quality" not in available_actions(set(), no_rhob)
    assert "set_zone_of_interest" in available_actions(set(), no_rhob)


def test_depth_quality_profile_flags_overburden():
    depth = np.arange(100, dtype=float)
    rhob = np.where(depth < 50, 1.8, 2.5)  # low-density top (overburden), real rock below
    prof = depth_quality_profile({"RHOB": rhob}, depth, n_bins=4)
    top, bottom = prof["bins"][0], prof["bins"][-1]
    assert top["rhob_p50"] < 2.0 and top["frac_rhob_below_2"] == 1.0
    assert bottom["rhob_p50"] > 2.4 and bottom["frac_rhob_below_2"] == 0.0


def test_compare_methods_is_always_offered():
    assert "compare_methods" in available_actions(set(), _FULL)
    assert "compare_methods" in available_actions(set(), {"GR"})  # runner reports unmet prereqs


def test_compare_methods_returns_engine_means_per_property():
    ctx = _cmp_ctx()
    vsh_obs = observe("compare_methods", ctx, {}, args={"property": "vsh"})
    assert "vsh_larionov_old" in vsh_obs["methods"]
    por_obs = observe("compare_methods", ctx, {}, args={"property": "porosity"})
    assert "phie_density_neutron" in por_obs["methods"]
    sw_obs = observe("compare_methods", ctx, {}, args={"property": "sw"})
    assert {"sw_archie", "sw_simandoux", "sw_indonesia"} <= set(sw_obs["methods"])


def test_compare_methods_sw_needs_phie_first():
    ctx = _cmp_ctx()
    ctx["phie"] = None
    sw_obs = observe("compare_methods", ctx, {}, args={"property": "sw"})
    assert "methods" not in sw_obs and "prerequisites not met" in sw_obs["note"]


def test_compare_methods_unknown_property_notes():
    obs = observe("compare_methods", _cmp_ctx(), {}, args={"property": "bogus"})
    assert "unknown property" in obs["note"]


def test_request_tool_records_and_never_executes():
    ledger: dict = {}
    out = observe("request_tool", _cmp_ctx(), ledger, args={"spec": "Rxo/RT moveable-oil ratio"})
    assert "recorded" in out["note"]
    assert ledger["run"]["tool_requests"] == ["Rxo/RT moveable-oil ratio"]
    empty = observe("request_tool", _cmp_ctx(), {}, args={})
    assert "needs args" in empty["note"]


def test_vintage_neut_unlocks_phie_without_density():
    # class-B wells (GR+NEUT+RT, no RHOB/NPHI) must still walk the chain (CXR-6)
    vintage = {"GR", "NEUT", "RT"}
    assert "compute_phie" not in available_actions(set(), vintage)  # still needs vsh first
    assert "compute_phie" in available_actions({"vsh"}, vintage)
    assert "electrofacies" not in available_actions({"vsh"}, vintage)  # needs RHOB/NPHI


def test_recompute_invalidates_transitive_dependents():
    valid = {"vsh", "phie", "sw", "netpay", "uncertainty", "permeability"}
    after = invalidate_downstream(valid, "vsh")
    assert after == {"vsh"}  # everything downstream of vsh is stale
    # recomputing sw invalidates only its dependents, not vsh/phie
    after_sw = invalidate_downstream(valid, "sw")
    assert "vsh" in after_sw and "phie" in after_sw and "sw" in after_sw
    assert "netpay" not in after_sw and "uncertainty" not in after_sw
