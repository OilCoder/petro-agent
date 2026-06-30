"""Tests for the agentic loop: scripted decisions, recompute, max_steps, default equivalence."""

import json
import os

from src.agents.analyst_loop import run_analyst_loop
from src.orchestrator.graph import run_pipeline

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "synthetic_oldrocks.las")


def _scripted(script):
    it = iter(script)

    def chat(system, user):
        try:
            return json.dumps(next(it))
        except StopIteration:
            return json.dumps({"action": "finish"})

    return chat


def test_loop_recompute_and_chain(tmp_path):
    ledger, ctx = run_pipeline(FIXTURE, out_dir=str(tmp_path), return_ctx=True)
    default_netpay = ledger["net_pay_total_m"]
    script = [
        {"action": "compute_vsh", "method": "vsh_linear"},  # recompute -> invalidates downstream
        {"action": "compute_phie"},
        {"action": "compute_sw"},
        {"action": "apply_cutoffs"},
        {"action": "run_uncertainty"},
        {"action": "permeability", "method": "perm_timur"},
        {"action": "finish"},
    ]
    res = run_analyst_loop(ledger, ctx, "free", _scripted(script), "m")
    al = ledger["run"]["analyst_loop"]
    assert al["finished_by_agent"] is True and al["steps_taken"] == 6
    assert al["recomputes"] >= 1  # recomputed vsh (it was already valid from pass-0)
    assert "perm_timur" in ledger.get("tool_results", {})
    assert res["section_plan"]["sections"][:3] == ["vsh", "porosity", "sw"]
    assert "permeability" in res["section_plan"]["sections"]
    # vsh_linear (overestimates Vsh) changes the net pay vs the default Larionov
    assert ledger["net_pay_total_m"] != default_netpay


def test_loop_recompute_default_method_matches_pipeline(tmp_path):
    # recomputing with the DEFAULT methods reproduces the pipeline net pay (steps share one truth)
    ledger, ctx = run_pipeline(FIXTURE, out_dir=str(tmp_path), return_ctx=True)
    base = ledger["net_pay_total_m"]
    script = [
        {"action": "compute_vsh"},
        {"action": "compute_phie"},
        {"action": "compute_sw"},
        {"action": "apply_cutoffs"},
        {"action": "finish"},
    ]
    run_analyst_loop(ledger, ctx, "free", _scripted(script), "m")
    assert abs(ledger["net_pay_total_m"] - base) < 1e-9


def test_loop_hits_max_steps(tmp_path):
    ledger, ctx = run_pipeline(FIXTURE, out_dir=str(tmp_path), return_ctx=True)
    seq = iter(["compute_vsh", "compute_phie"] * 10)  # alternate so the stall guard never fires
    alternating = lambda s, u: json.dumps({"action": next(seq)})  # noqa: E731
    run_analyst_loop(ledger, ctx, "free", alternating, "m", max_steps=4)
    al = ledger["run"]["analyst_loop"]
    assert al["steps_taken"] == 4 and al["hit_max_steps"] is True


def test_loop_stall_guard_stops_repetition(tmp_path):
    ledger, ctx = run_pipeline(FIXTURE, out_dir=str(tmp_path), return_ctx=True)
    repeat = lambda s, u: json.dumps({"action": "compute_vsh"})  # noqa: E731
    run_analyst_loop(ledger, ctx, "free", repeat, "m", max_steps=20)
    al = ledger["run"]["analyst_loop"]
    assert al["stalled"] is True and al["steps_taken"] < 20


def test_loop_garbage_falls_back_and_finishes(tmp_path):
    ledger, ctx = run_pipeline(FIXTURE, out_dir=str(tmp_path), return_ctx=True)
    run_analyst_loop(ledger, ctx, "free", lambda s, u: "no json", "m", max_steps=8)
    al = ledger["run"]["analyst_loop"]
    # everything is valid from pass-0, so the default fallback finishes immediately
    assert al["finished_by_agent"] is True
