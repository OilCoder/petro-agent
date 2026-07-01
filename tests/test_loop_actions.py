"""Tests for the agentic loop action frontier (physics prereqs + recompute invalidation)."""

import numpy as np

from src.agents.loop_actions import (
    available_actions,
    depth_quality_profile,
    invalidate_downstream,
    seed_baseline_sections,
)
from src.params.schema import ParamValue

_FULL = {"GR", "RHOB", "NPHI", "RT"}


def test_seed_vsh_selected_matches_a_real_method_key():
    # the [FIJO] Vsh section's "Selected" ✓ was empty in free mode: the fallback built
    # "vsh_larionov_old_rocks" but the method key is "vsh_larionov_old" -> no match
    ctx = {
        "curves": {"GR": np.linspace(20.0, 100.0, 30)},
        "params": {
            "gr_min": ParamValue(20.0, "API", "default", "x"),
            "gr_max": ParamValue(120.0, "API", "default", "x"),
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


def test_recompute_invalidates_transitive_dependents():
    valid = {"vsh", "phie", "sw", "netpay", "uncertainty", "permeability"}
    after = invalidate_downstream(valid, "vsh")
    assert after == {"vsh"}  # everything downstream of vsh is stale
    # recomputing sw invalidates only its dependents, not vsh/phie
    after_sw = invalidate_downstream(valid, "sw")
    assert "vsh" in after_sw and "phie" in after_sw and "sw" in after_sw
    assert "netpay" not in after_sw and "uncertainty" not in after_sw
