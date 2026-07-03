"""Author mode (R14): the agent authors the interpretation from a descriptive-only pass-0.

Scripted chats (no LLM): a capable script authors the full chain with explicit methods; a
garbage model exercises the deterministic safety net (per-step default + post-loop re-close).
"""

import json
import os

from src.agents import analyst_loop
from src.agents.analyst_loop import run_analyst_loop
from src.agents.report_compose import compose_report
from src.evaluation.report_score import completeness_breakdown
from src.orchestrator.finalize import finalize_run
from src.orchestrator.graph import run_descriptive_pass

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "synthetic_oldrocks.las")


def _scripted(script):
    it = iter(script)

    def chat(system, user):
        if "SKEPTICAL" in system:  # R13 skeptic pass -> no objections (do not eat the script)
            return json.dumps({"objections": []})
        try:
            return json.dumps(next(it))
        except StopIteration:
            return json.dumps({"action": "finish"})

    return chat


_AUTHOR_SCRIPT = [
    {"action": "compute_vsh", "method": "vsh_linear"},
    {"action": "compute_phie", "method": "phi_density"},
    {"action": "compute_sw", "method": "sw_simandoux"},
    {"action": "apply_cutoffs"},
    {"action": "run_uncertainty"},
    {"action": "finish"},
]


def test_author_scripted_run_authors_the_full_chain(tmp_path):
    ledger, ctx = run_descriptive_pass(FIXTURE, out_dir=str(tmp_path))
    res = run_analyst_loop(
        ledger, ctx, "free", _scripted(_AUTHOR_SCRIPT), "fake", max_steps=16, author=True
    )
    assert res["fell_back"] is False
    # the chain exists and was authored: every core method carries agent provenance
    assert ledger["vsh_comparison"]["method_source"] == "agent"
    assert ledger["porosity_comparison"]["method_source"] == "agent"
    assert ledger["sw_summary"]["method_source"] == "agent"
    assert ledger["zones"] is not None and "uncertainty" in ledger
    assert ledger["run"]["analyst_loop"]["author_mode"] is True
    br = completeness_breakdown(ledger, res["section_plan"])
    assert br["authored_core"] == 3
    assert br["core_methods_defaulted"] == []


def test_author_garbage_model_closes_deterministically(tmp_path):
    ledger, ctx = run_descriptive_pass(FIXTURE, out_dir=str(tmp_path))

    def garbage(system, user):
        return "zzz not json"

    res = run_analyst_loop(ledger, ctx, "free", garbage, "fake", max_steps=16, author=True)
    loop = ledger["run"]["analyst_loop"]
    # every executed step was the deterministic default -> honest fell_back, chain still complete
    assert res["fell_back"] is True
    assert loop["default_steps"] > 0
    assert ledger.get("zones") is not None and ledger.get("net_pay_total_m") is not None
    assert ledger["sw_summary"]["method_source"] == "engine_default"
    # finalize gates the closed chain and the report composes end-to-end
    finalize_run(ledger, ctx)
    assert ledger["run"]["convergence_status"] in ("CONVERGED", "DID_NOT_CONVERGE")
    md = compose_report(ledger, res["section_plan"], "free", res["graph"], {})
    assert "Water saturation" in md


def test_author_skips_baseline_seeding(monkeypatch, tmp_path):
    calls = {"n": 0}

    def spy(ledger, ctx):
        calls["n"] += 1

    monkeypatch.setattr(analyst_loop, "seed_baseline_sections", spy)
    ledger, ctx = run_descriptive_pass(FIXTURE, out_dir=str(tmp_path))
    run_analyst_loop(ledger, ctx, "free", _scripted([]), "fake", max_steps=2, author=True)
    assert calls["n"] == 0  # author mode: seeding would fabricate labels for unmade choices

    ledger2, ctx2 = run_descriptive_pass(FIXTURE, out_dir=str(tmp_path))
    run_analyst_loop(ledger2, ctx2, "free", _scripted([]), "fake", max_steps=2)
    assert calls["n"] == 1  # baseline mode keeps the seeding


def test_author_midloop_validation_surfaces_objections_before_finish(tmp_path):
    # R14-G: once the chain closes, the NEXT observation must carry the validator objections —
    # in v8 the agent authored blind (objections only existed after finalize) and never zoned.
    ledger, ctx = run_descriptive_pass(FIXTURE, out_dir=str(tmp_path))
    seen: list[str] = []
    it = iter(_AUTHOR_SCRIPT)

    def chat(system, user):
        if "SKEPTICAL" in system:
            return json.dumps({"objections": []})
        seen.append(user)
        try:
            return json.dumps(next(it))
        except StopIteration:
            return json.dumps({"action": "finish"})

    run_analyst_loop(ledger, ctx, "free", chat, "fake", max_steps=16, author=True)
    # the fixture's default chain yields a net_pay_plausibility objection: it must be in the
    # ledger BEFORE finalize, and visible in an observation AFTER apply_cutoffs closed the chain
    assert any(o["validator_id"] == "net_pay_plausibility" for o in ledger["objections"])
    post_chain_obs = seen[4:]  # observations after the 4th step (apply_cutoffs) executed
    assert any("net_pay_plausibility" in obs for obs in post_chain_obs)


def test_objection_scope_is_typed_per_validator():
    # A false universal ("no method/zone can fix") misinformed the agent for interval-scoped
    # checks. Each objection must state what it is computed from, truthfully per validator.
    from src.agents.analyst_loop import _diagnostics

    ledger = {
        "objections": [
            {"validator_id": "net_pay_plausibility", "type": "irreducible", "detail": "x"},
            {"validator_id": "model_mismatch_nd", "type": "irreducible", "detail": "y"},
        ],
        "run": {},
    }
    objs = _diagnostics(ledger)["objections"]
    assert "CURRENT analysis interval" in objs[0]["computed_from"]  # interval-scoped: says so
    assert "raw RHOB/NPHI" in objs[1]["computed_from"]  # data-quality: says so
    legend = _diagnostics(ledger)["objections_legend"]
    assert "zone" not in legend  # the false universal is gone


def test_author_compare_methods_feeds_the_next_decision(tmp_path):
    ledger, ctx = run_descriptive_pass(FIXTURE, out_dir=str(tmp_path))
    script = [
        {"action": "compare_methods", "args": {"property": "vsh"}},
        {"action": "compute_vsh", "method": "vsh_clavier"},
        {"action": "finish"},
    ]
    res = run_analyst_loop(
        ledger, ctx, "free", _scripted(script), "fake", max_steps=16, author=True
    )
    assert ledger["vsh_comparison"]["selected"] == "vsh_clavier"
    # the observation was executed read-only (no ledger key, no valid-set change before compute)
    assert res["fell_back"] is False
