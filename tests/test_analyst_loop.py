"""Tests for the agentic loop: scripted decisions, recompute, max_steps, default equivalence."""

import json
import os

import numpy as np

from src.agents.analyst_loop import run_analyst_loop
from src.agents.report_compose import compose_report
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
    # four distinct PRODUCTIVE optional actions (no no-ops, no 3-in-a-row stall)
    seq = iter(["permeability", "rock_quality", "electrofacies", "lithology"] * 3)
    productive = lambda s, u: json.dumps({"action": next(seq)})  # noqa: E731
    run_analyst_loop(ledger, ctx, "free", productive, "m", max_steps=4)
    al = ledger["run"]["analyst_loop"]
    assert al["steps_taken"] == 4 and al["hit_max_steps"] is True


def test_loop_measures_noop_as_wasted(tmp_path):
    ledger, ctx = run_pipeline(FIXTURE, out_dir=str(tmp_path), return_ctx=True)
    # add permeability, then try to add it AGAIN (a no-op) -> measured as wasted, not re-executed
    script = [
        {"action": "permeability", "method": "perm_timur"},
        {"action": "permeability", "method": "perm_timur"},
        {"action": "finish"},
    ]
    run_analyst_loop(ledger, ctx, "free", _scripted(script), "m")
    al = ledger["run"]["analyst_loop"]
    assert al["wasted_steps"] == 1 and al["steps_taken"] == 1


def test_loop_derived_parameters_optional_renders(tmp_path):
    ledger, ctx = run_pipeline(FIXTURE, out_dir=str(tmp_path), return_ctx=True)
    # the agent can now select the [MODELO] derived-parameters section (bvw)
    script = [{"action": "derived_parameters", "method": "bvw"}, {"action": "finish"}]
    res = run_analyst_loop(ledger, ctx, "free", _scripted(script), "m")
    assert "bvw" in ledger.get("tool_results", {})  # the vetted tool ran (no theater)
    assert "derived_parameters" in res["section_plan"]["sections"]
    md = compose_report(
        ledger,
        res["section_plan"],
        "free",
        res["graph"],
        {"executive_summary": "x", "conclusions": "y"},
    )
    assert "Bulk-volume water" in md  # the section renders with a real value


def test_loop_floor_sections_render_without_recompute(tmp_path):
    ledger, ctx = run_pipeline(FIXTURE, out_dir=str(tmp_path), return_ctx=True)
    # agent finishes immediately (no recompute) — the [FIJO] Vsh/Porosity/Sw floor must still render
    res = run_analyst_loop(ledger, ctx, "free", _scripted([{"action": "finish"}]), "m")
    assert "vsh_comparison" in ledger and "porosity_comparison" in ledger and "sw_summary" in ledger
    md = compose_report(
        ledger,
        res["section_plan"],
        "free",
        res["graph"],
        {"executive_summary": "x", "conclusions": "y"},
    )
    assert "Not computed — no GR curve" not in md  # the floor sections render from the baseline
    assert "Not computed — no RHOB/NPHI curve" not in md


def test_loop_surfaces_diagnostics_and_populates_eda(tmp_path):
    from src.agents.analyst_loop import observation_text
    from src.agents.loop_actions import available_actions

    ledger, ctx = run_pipeline(FIXTURE, out_dir=str(tmp_path), return_ctx=True)
    run_analyst_loop(ledger, ctx, "free", _scripted([{"action": "finish"}]), "m")
    # the loop path now builds the EDA digest (it used to leave the agent's "eda" empty)
    eda = ledger["run"]["eda"]
    assert eda.get("curves_present") and "curve_inventory" in eda and "depth_coverage" in eda
    # observation_text surfaces the diagnostics, and valid_actions comes before the verbose tail
    valid = {"vsh", "phie", "sw", "netpay"}
    obs = observation_text(ledger, valid, available_actions(valid, set(ctx["curves"])), ["vsh"])
    assert "diagnostics" in obs and "net_pay_summary" in obs and "convergence" in obs
    assert obs.index("valid_actions") < obs.index("report_so_far")  # critical field not truncated


def test_loop_set_zone_of_interest_restricts_and_recomputes(tmp_path):
    ledger, ctx = run_pipeline(FIXTURE, out_dir=str(tmp_path), return_ctx=True)
    default_netpay = ledger["net_pay_total_m"]
    depth = np.asarray(ctx["depth_m"], dtype=float)
    top = float(depth[depth.size // 2])  # restrict to the bottom half
    bottom = float(depth[-1])
    script = [
        {"action": "set_zone_of_interest", "args": {"top": top, "bottom": bottom}},
        {"action": "finish"},
    ]
    run_analyst_loop(ledger, ctx, "free", _scripted(script), "m")
    zoi = ledger["zone_of_interest"]
    assert zoi["top_m"] == round(top, 1) and zoi["bottom_m"] == round(bottom, 1)
    # curves above the zone are masked to NaN; the zone keeps real data
    rhob = np.asarray(ctx["curves"]["RHOB"], dtype=float)
    assert np.all(np.isnan(rhob[depth < top]))
    assert np.any(np.isfinite(rhob[depth >= top]))
    # the baseline was recomputed over the smaller interval -> less net pay
    assert ledger["net_pay_total_m"] < default_netpay
    al = ledger["run"]["analyst_loop"]
    assert al["steps_taken"] == 1 and al["finished_by_agent"] is True


def test_loop_optional_bad_method_coerced_not_crash(tmp_path):
    ledger, ctx = run_pipeline(FIXTURE, out_dir=str(tmp_path), return_ctx=True)
    # a hallucinated optional method must coerce to the default, not crash with KeyError
    script = [
        {"action": "permeability", "method": "tiksgaard"},
        {"action": "finish"},
    ]
    run_analyst_loop(ledger, ctx, "free", _scripted(script), "m")
    assert "perm_timur" in ledger.get("tool_results", {})  # coerced to the default tool
    assert ledger["run"]["analyst_loop"]["steps_taken"] == 1


def test_loop_second_refinement_of_property_is_wasted(tmp_path):
    ledger, ctx = run_pipeline(FIXTURE, out_dir=str(tmp_path), return_ctx=True)
    # refining Sw once is allowed; a second compute_sw (any method) is wasted (prompt: at most once)
    script = [
        {"action": "compute_sw", "method": "sw_simandoux"},  # first refinement -> executes
        {"action": "compute_sw", "method": "sw_indonesia"},  # second -> wasted (already refined)
        {"action": "finish"},
    ]
    run_analyst_loop(ledger, ctx, "free", _scripted(script), "m")
    al = ledger["run"]["analyst_loop"]
    assert al["wasted_steps"] == 1 and al["steps_taken"] == 1


def test_loop_rezone_same_interval_is_wasted(tmp_path):
    ledger, ctx = run_pipeline(FIXTURE, out_dir=str(tmp_path), return_ctx=True)
    depth = np.asarray(ctx["depth_m"], dtype=float)
    top, bottom = float(depth[depth.size // 2]), float(depth[-1])
    script = [
        {"action": "set_zone_of_interest", "args": {"top": top, "bottom": bottom}},
        {"action": "set_zone_of_interest", "args": {"top": top, "bottom": bottom}},  # same zone
        {"action": "finish"},
    ]
    run_analyst_loop(ledger, ctx, "free", _scripted(script), "m")
    al = ledger["run"]["analyst_loop"]
    assert al["wasted_steps"] == 1 and al["steps_taken"] == 1  # the re-zone is a no-op


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


def test_loop_self_critique_fires_once_before_finish(tmp_path):
    # R12-B: on 'finish', a NEUTRAL completeness surface is shown once, letting the agent reconsider
    ledger, ctx = run_pipeline(FIXTURE, out_dir=str(tmp_path), return_ctx=True)
    seen: list[str] = []
    script = iter(
        [
            {"action": "finish"},  # first finish -> triggers the completeness critique
            {"action": "permeability", "method": "perm_timur"},  # agent reconsiders, adds analysis
            {"action": "finish"},  # finishes for real (critique does not fire again)
        ]
    )

    def chat(system, user):
        seen.append(user)
        try:
            return json.dumps(next(script))
        except StopIteration:
            return json.dumps({"action": "finish"})

    run_analyst_loop(ledger, ctx, "free", chat, "m")
    al = ledger["run"]["analyst_loop"]
    # the neutral completeness surface reached the agent, who then reconsidered before finishing
    assert any("completeness check" in u for u in seen)
    assert al["finished_by_agent"] is True and al["steps_taken"] == 1
    assert "perm_timur" in ledger.get("tool_results", {})  # the reconsideration added a real tool


def test_completeness_critique_flags_undone_work():
    from src.agents.analyst_loop import _completeness_critique

    crit = _completeness_critique(
        {"calibration": {}, "tool_results": {}}, ["permeability", "finish"]
    )
    assert crit is not None and "permeability" in crit["note"] and "vsh" in crit["note"]


def test_completeness_critique_none_when_complete():
    from src.agents.analyst_loop import _completeness_critique

    ledger = {
        "tool_results": {
            "perm_timur": {},
            "rqi": {},
            "electrofacies": {},
            "litho_nd_crossplot": {},
            "bvw": {},
        },
        "calibration": {"vsh_method": {"chosen_by_model": True}},
        "porosity_comparison": {"method_source": "agent"},
        "sw_summary": {"method_source": "agent"},
    }
    actions = ["permeability", "rock_quality", "electrofacies", "lithology", "derived_parameters"]
    assert _completeness_critique(ledger, actions) is None  # nothing applicable left undone


def test_loop_output_composes_a_report(tmp_path):
    ledger, ctx = run_pipeline(FIXTURE, out_dir=str(tmp_path), return_ctx=True)
    script = [
        {"action": "compute_sw", "method": "sw_simandoux"},
        {"action": "permeability", "method": "perm_timur"},
        {"action": "finish"},
    ]
    res = run_analyst_loop(ledger, ctx, "free", _scripted(script), "m")
    md = compose_report(
        ledger,
        res["section_plan"],
        "free",
        res["graph"],
        {"executive_summary": "Bracketed; defaults.", "conclusions": "Calibrate Rw."},
    )
    assert "Water saturation" in md  # the Sw section the agent built (Simandoux)
    assert "Permeability (uncalibrated)" in md  # the optional the agent added
    assert "Methodology (decision graph)" in md  # the step-by-step trace
    assert "Limitations" in md and "Parameters and provenance" in md  # forced rails always present
