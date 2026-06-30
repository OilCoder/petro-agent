"""Tests for the agentic loop action frontier (physics prereqs + recompute invalidation)."""

from src.agents.loop_actions import available_actions, invalidate_downstream

_FULL = {"GR", "RHOB", "NPHI", "RT"}


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


def test_recompute_invalidates_transitive_dependents():
    valid = {"vsh", "phie", "sw", "netpay", "uncertainty", "permeability"}
    after = invalidate_downstream(valid, "vsh")
    assert after == {"vsh"}  # everything downstream of vsh is stale
    # recomputing sw invalidates only its dependents, not vsh/phie
    after_sw = invalidate_downstream(valid, "sw")
    assert "vsh" in after_sw and "phie" in after_sw and "sw" in after_sw
    assert "netpay" not in after_sw and "uncertainty" not in after_sw
