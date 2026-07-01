"""Tests for the V2-C tool dispatcher, keyed claim verifier, and cross-tool consistency.

All deterministic — no model in the loop.
"""

import numpy as np

from src.agents.claim_verifier import verify_keyed
from src.agents.methodology_graph import MethodologyGraph
from src.agents.tool_dispatch import dispatch, validate_plan
from src.validators.physical import cross_tool_consistency

N = 50
CTX = {
    "curves": {
        "GR": np.full(N, 50.0),
        "RT": np.full(N, 10.0),
        "RHOB": np.full(N, 2.5),
        "NPHI": np.full(N, 0.2),
    },
    "phie": np.full(N, 0.2),
    "vsh": np.full(N, 0.3),
    "sw": np.full(N, 0.3),
    "depth_m": np.arange(N, dtype=float) * 0.5,
    "step_m": 0.5,
    "quality_map": np.array(["GOOD"] * N, dtype=object),
}


def test_validate_plan_rejects_unknown_tool():
    issues = validate_plan({"tool_calls": [{"tool": "sw_made_up", "args": {}}]})
    assert any("not a whitelisted id" in i for i in issues)


def test_bad_preset_coerced_to_default_not_rejected():
    # an unknown/placeholder preset must NOT discard the plan — it is coerced to the default
    plan = {"tool_calls": [{"tool": "sw_simandoux", "args": {"electrical_preset": "<preset_id>"}}]}
    assert validate_plan(plan) == []
    ledger: dict = {}
    dispatch(plan, CTX, ledger, MethodologyGraph(mode="free", model="m"))
    assert ledger["tool_results"]["sw_simandoux"]["value"]["preset"] == "carbonate_default"


def test_validate_plan_handles_malformed_tool_without_crashing():
    # a real model returned tool as a dict -> must not raise "unhashable type: dict"
    issues = validate_plan({"tool_calls": [{"tool": {"name": "sw"}, "args": {}}, "notadict"]})
    assert len(issues) == 2 and all("not a" in i or "not an" in i for i in issues)


def test_validate_plan_accepts_good_plan():
    plan = {
        "tool_calls": [{"tool": "sw_simandoux", "args": {"electrical_preset": "carbonate_default"}}]
    }
    assert validate_plan(plan) == []


def test_dispatch_writes_number_hash_and_graph_node():
    plan = {
        "tool_calls": [{"tool": "sw_simandoux", "args": {"electrical_preset": "carbonate_default"}}]
    }
    ledger: dict = {}
    graph = MethodologyGraph(mode="free", model="m")
    written = dispatch(plan, CTX, ledger, graph)
    assert written == ["sw_simandoux"]
    entry = ledger["tool_results"]["sw_simandoux"]
    assert "mean_sw" in entry["value"] and len(entry["result_hash"]) == 16
    # the graph recorded a tool_call node pointing at the ledger key
    act = [n for n in graph.nodes if n.type == "tool_call"][0]
    assert (
        act.payload["result_ledger_key"] == "ledger:tool_results"
    )  # result lives under tool_results


def test_dispatch_runs_eda_tool():
    plan = {"tool_calls": [{"tool": "low_resistivity_scan", "args": {}}]}
    ledger: dict = {}
    dispatch(plan, CTX, ledger, MethodologyGraph(mode="free", model="m"))
    assert "low_resistivity_scan" in ledger["tool_results"]


def test_dispatch_invalid_plan_writes_nothing():
    ledger: dict = {}
    written = dispatch(
        {"tool_calls": [{"tool": "bad", "args": {}}]},
        CTX,
        ledger,
        MethodologyGraph(mode="free", model="m"),
    )
    assert written == [] and "tool_results" not in ledger


def test_dispatch_runs_vsh_method():
    plan = {"tool_calls": [{"tool": "vsh_larionov_old", "args": {}}]}
    ledger: dict = {}
    dispatch(plan, CTX, ledger, MethodologyGraph(mode="free", model="m"))
    val = ledger["tool_results"]["vsh_larionov_old"]["value"]
    assert "mean_vsh" in val and np.isfinite(val["mean_vsh"])


def test_dispatch_runs_vsh_neutron_density():
    # the non-GR clay indicator is now a selectable tool (different signature, special-cased)
    plan = {"tool_calls": [{"tool": "vsh_neutron_density", "args": {}}]}
    ledger: dict = {}
    dispatch(plan, CTX, ledger, MethodologyGraph(mode="free", model="m"))
    val = ledger["tool_results"]["vsh_neutron_density"]["value"]
    assert "mean_vsh" in val and np.isfinite(val["mean_vsh"])


def test_dispatch_runs_vsh_multimineral():
    plan = {"tool_calls": [{"tool": "vsh_multimineral", "args": {}}]}
    ledger: dict = {}
    dispatch(plan, CTX, ledger, MethodologyGraph(mode="free", model="m"))
    val = ledger["tool_results"]["vsh_multimineral"]["value"]
    assert "mean_vsh" in val and np.isfinite(val["mean_vsh"])


def test_dispatch_runs_porosity_density_neutron():
    plan = {"tool_calls": [{"tool": "phie_density_neutron", "args": {}}]}
    ledger: dict = {}
    dispatch(plan, CTX, ledger, MethodologyGraph(mode="free", model="m"))
    val = ledger["tool_results"]["phie_density_neutron"]["value"]
    assert "mean_phi" in val and np.isfinite(val["mean_phi"])


def test_dispatch_runs_sonic_with_matrix_preset():
    ctx = {**CTX, "curves": {**CTX["curves"], "DT": np.full(N, 80.0)}}
    plan = {"tool_calls": [{"tool": "phi_sonic_wyllie", "args": {"matrix_preset": "sandstone"}}]}
    ledger: dict = {}
    dispatch(plan, ctx, ledger, MethodologyGraph(mode="free", model="m"))
    val = ledger["tool_results"]["phi_sonic_wyllie"]["value"]
    assert "mean_phi" in val and np.isfinite(val["mean_phi"]) and val["preset"] == "sandstone"


def test_dispatch_runs_lithology_method():
    plan = {"tool_calls": [{"tool": "litho_nd_crossplot", "args": {}}]}
    ledger: dict = {}
    dispatch(plan, CTX, ledger, MethodologyGraph(mode="free", model="m"))
    assert "nearest_litho" in ledger["tool_results"]["litho_nd_crossplot"]["value"]


def test_dispatch_runs_permeability_uncalibrated():
    plan = {"tool_calls": [{"tool": "perm_timur", "args": {}}]}
    ledger: dict = {}
    dispatch(plan, CTX, ledger, MethodologyGraph(mode="free", model="m"))
    val = ledger["tool_results"]["perm_timur"]["value"]
    assert "mean_k_md" in val and val["calibrated"] is False


def test_dispatch_runs_rock_quality():
    plan = {"tool_calls": [{"tool": "rqi", "args": {}}]}
    ledger: dict = {}
    dispatch(plan, CTX, ledger, MethodologyGraph(mode="free", model="m"))
    val = ledger["tool_results"]["rqi"]["value"]
    assert "mean_value" in val and val["calibrated"] is False


def test_dispatch_runs_electrofacies():
    plan = {"tool_calls": [{"tool": "electrofacies", "args": {"n_facies": 3}}]}
    ledger: dict = {}
    dispatch(plan, CTX, ledger, MethodologyGraph(mode="free", model="m"))
    val = ledger["tool_results"]["electrofacies"]["value"]
    assert "n_facies" in val and "sizes" in val


def test_bad_matrix_preset_coerced_not_rejected():
    ctx = {**CTX, "curves": {**CTX["curves"], "DT": np.full(N, 80.0)}}
    plan = {"tool_calls": [{"tool": "phi_sonic_wyllie", "args": {"matrix_preset": "ghost"}}]}
    assert validate_plan(plan) == []
    ledger: dict = {}
    dispatch(plan, ctx, ledger, MethodologyGraph(mode="free", model="m"))
    assert "mean_phi" in ledger["tool_results"]["phi_sonic_wyllie"]["value"]


def test_verify_keyed_flags_19pct_off_number():
    # flat verifier (2%) passes a 1.9%-off number; the keyed (0.5%) flags it
    ledger = {"tool_results": {"sw_simandoux": {"value": {"mean_sw": 0.300}, "result_hash": "x"}}}
    report = "Average Sw is 0.306."  # 2.0% above 0.300
    assert verify_keyed(report, ledger)["passed"] is False


def test_verify_keyed_passes_exact():
    ledger = {"tool_results": {"sw_simandoux": {"value": {"mean_sw": 0.300}, "result_hash": "x"}}}
    assert verify_keyed("Average Sw is 0.300.", ledger)["passed"] is True


def test_cross_tool_consistency_flags_contradiction():
    ledger = {
        "summary": {"avg_sw": 0.30},
        "tool_results": {"sw_indonesia": {"value": {"mean_sw": 0.80}, "result_hash": "x"}},
    }
    objs = cross_tool_consistency(ledger)
    assert len(objs) == 1 and objs[0].objection_type == "mechanical"


def test_cross_tool_consistency_passes_when_consistent():
    ledger = {
        "summary": {"avg_sw": 0.30},
        "tool_results": {"sw_simandoux": {"value": {"mean_sw": 0.31}, "result_hash": "x"}},
    }
    assert cross_tool_consistency(ledger) == []
