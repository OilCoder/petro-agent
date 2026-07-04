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


def test_observation_steps_and_evidence_efficiency_measured(tmp_path):
    # GA-2: commitment is a score — observations counted, efficiency = choices/observations
    ledger, ctx = run_descriptive_pass(FIXTURE, out_dir=str(tmp_path))
    script = [
        {"action": "compare_methods", "args": {"property": "vsh"}},
        {"action": "compute_vsh", "method": "vsh_linear"},
        {"action": "compare_methods", "args": {"property": "porosity"}},
        {"action": "compute_phie", "method": "phi_density"},
        {"action": "compute_sw", "method": "sw_simandoux"},
        {"action": "apply_cutoffs"},
        {"action": "run_uncertainty"},
        {"action": "finish"},
    ]
    res = run_analyst_loop(
        ledger, ctx, "free", _scripted(script), "fake", max_steps=16, author=True
    )
    loop = ledger["run"]["analyst_loop"]
    assert loop["observation_steps"] == 2  # the two compare_methods reads in the script
    br = completeness_breakdown(ledger, res["section_plan"])
    assert br["observation_steps"] == 2
    assert br["evidence_efficiency"] == round(br["interpretive_choices"] / 2, 3)


def test_field_notes_written_scrubbed_and_carried_to_next_well(tmp_path):
    # GA-4: at author finish the agent writes ONE qualitative note; every digit is scrubbed
    # mechanically; the next well reads it via case_file -> your_prior_field_notes.
    ledger, ctx = run_descriptive_pass(FIXTURE, out_dir=str(tmp_path))
    it = iter(_AUTHOR_SCRIPT)

    def chat(system, user):
        if "SKEPTICAL" in system:
            return json.dumps({"objections": []})
        if "field notebook" in system:
            return "Chose Simandoux over Archie; porosity near 0.25 looked optimistic up top."
        try:
            return json.dumps(next(it))
        except StopIteration:
            return json.dumps({"action": "finish"})

    res = run_analyst_loop(ledger, ctx, "free", chat, "fake", max_steps=16, author=True)
    notes = res["field_notes"]
    assert notes == ledger["run"]["analyst_loop"]["field_notes"]
    assert "Simandoux" in notes
    assert "0.25" not in notes and "[n]" in notes  # unledgered number never propagates
    # non-author runs write no notes
    ledger2, ctx2 = run_descriptive_pass(FIXTURE, out_dir=str(tmp_path))
    res2 = run_analyst_loop(ledger2, ctx2, "free", _scripted([]), "fake", max_steps=2)
    assert res2["field_notes"] is None
    # the next well sees the carried notes in its observations
    ledger3, ctx3 = run_descriptive_pass(FIXTURE, out_dir=str(tmp_path))
    seen: list[str] = []

    def spy_chat(system, user):
        if "SKEPTICAL" in system:
            return json.dumps({"objections": []})
        seen.append(user)
        return json.dumps({"action": "finish"})

    run_analyst_loop(
        ledger3, ctx3, "free", spy_chat, "fake", max_steps=4, author=True, case_file=notes
    )
    assert any("your_prior_field_notes" in obs and "Simandoux" in obs for obs in seen)


def test_regional_brief_surfaces_only_in_author_mode(tmp_path):
    # GA-5: the brief is background DATA for the author; baseline mode never sees it
    from src.params.config_loader import load_regional_brief

    brief = load_regional_brief()

    def spy(seen):
        def chat(system, user):
            if "SKEPTICAL" in system:
                return json.dumps({"objections": []})
            seen.append(user)
            return json.dumps({"action": "finish"})

        return chat

    ledger, ctx = run_descriptive_pass(FIXTURE, out_dir=str(tmp_path))
    author_seen: list[str] = []
    run_analyst_loop(
        ledger,
        ctx,
        "free",
        spy(author_seen),
        "fake",
        max_steps=4,
        author=True,
        regional_brief=brief,
    )
    assert any("regional_reference" in obs and "Schaben" in obs for obs in author_seen)

    ledger2, ctx2 = run_descriptive_pass(FIXTURE, out_dir=str(tmp_path))
    base_seen: list[str] = []
    run_analyst_loop(
        ledger2, ctx2, "free", spy(base_seen), "fake", max_steps=4, regional_brief=brief
    )
    assert not any("regional_reference" in obs for obs in base_seen)


def test_zone_restriction_measures_gross_over_the_analyzed_window(tmp_path):
    # v11 investigation bug: a restricted run rendered the FULL logged gross, diluting NTG and
    # contradicting the analysis performed. Gross/NTG must measure the analyzed window, and §7
    # must declare the restriction.
    ledger, ctx = run_descriptive_pass(FIXTURE, out_dir=str(tmp_path))
    script = [
        {"action": "set_zone_of_interest", "args": {"top": 1500.0, "bottom": 1520.0}},
        {"action": "finish"},
    ]
    res = run_analyst_loop(
        ledger, ctx, "free", _scripted(script), "fake", max_steps=16, author=True
    )
    s = ledger["summary"]
    zoi = ledger["zone_of_interest"]
    span = zoi["bottom_m"] - zoi["top_m"]
    assert abs(s["gross_m"] - span) < 1.0  # window, not the logged interval
    assert abs(s["ntg"] - ledger["net_pay_total_m"] / s["gross_m"]) < 1e-9
    md = compose_report(ledger, res["section_plan"], "free", res["graph"], {})
    assert "Analysis window (analyst-restricted)" in md
    # unrestricted runs keep the logged-interval gross and show no window line
    ledger2, ctx2 = run_descriptive_pass(FIXTURE, out_dir=str(tmp_path))
    res2 = run_analyst_loop(
        ledger2, ctx2, "free", _scripted(_AUTHOR_SCRIPT), "fake", max_steps=16, author=True
    )
    md2 = compose_report(ledger2, res2["section_plan"], "free", res2["graph"], {})
    assert "Analysis window" not in md2


def test_mc_ranges_override_narrows_band_and_records_provenance(tmp_path):
    # Summit v3: an analyst-declared Rw band (SP evidence) parameterizes the MC — never new math.
    ledger, ctx = run_descriptive_pass(FIXTURE, out_dir=str(tmp_path))
    run_analyst_loop(
        ledger, ctx, "free", _scripted(_AUTHOR_SCRIPT), "fake", max_steps=16, author=True
    )
    assert "ranges_provenance" not in ledger["uncertainty"]

    ledger2, ctx2 = run_descriptive_pass(FIXTURE, out_dir=str(tmp_path))
    ctx2["mc_ranges_override"] = {
        "ranges": {"Rw": (0.041, 0.054)},
        "provenance": "SP-evidence field band (offset-median RMF), summit v3",
    }
    run_analyst_loop(
        ledger2, ctx2, "free", _scripted(_AUTHOR_SCRIPT), "fake", max_steps=16, author=True
    )
    unc = ledger2["uncertainty"]
    assert unc["ranges_provenance"].startswith("SP-evidence")
    assert unc["ranges_override"]["Rw"] == (0.041, 0.054)
    # the override took effect: the distribution differs from the default-ranges run
    assert (unc["net_pay_p10"], unc["net_pay_p50"], unc["net_pay_p90"]) != (
        ledger["uncertainty"]["net_pay_p10"],
        ledger["uncertainty"]["net_pay_p50"],
        ledger["uncertainty"]["net_pay_p90"],
    )


def test_observation_journal_blocks_repeats_and_surfaces_history(tmp_path):
    # GB-1: ~80% of v11 observations were repeats (single last_obs slot = amnesia). A repeated
    # read in the same epoch is a measured no-op with the cached summary; the journal is visible;
    # a state-changing action re-opens the read (results may legitimately change).
    ledger, ctx = run_descriptive_pass(FIXTURE, out_dir=str(tmp_path))
    seen: list[str] = []
    script = [
        {"action": "compare_methods", "args": {"property": "vsh"}},
        {"action": "compare_methods", "args": {"property": "vsh"}},  # repeat -> no-op
        {"action": "compute_vsh", "method": "vsh_linear"},  # state change -> epoch bump
        {"action": "compare_methods", "args": {"property": "vsh"}},  # re-read OK now
        {"action": "compute_phie"},
        {"action": "compute_sw"},
        {"action": "apply_cutoffs"},
        {"action": "run_uncertainty"},
        {"action": "finish"},
    ]
    it = iter(script)

    def chat(system, user):
        if "SKEPTICAL" in system:
            return json.dumps({"objections": []})
        if "field notebook" in system:
            return "note"
        seen.append(user)
        try:
            return json.dumps(next(it))
        except StopIteration:
            return json.dumps({"action": "finish"})

    run_analyst_loop(ledger, ctx, "free", chat, "fake", max_steps=20, author=True)
    loop = ledger["run"]["analyst_loop"]
    assert loop["repeated_observations"] == 1  # only the same-epoch repeat
    assert loop["wasted_steps"] >= 1
    # post-epoch re-read executed: two real compare_methods reads counted
    assert loop["observation_steps"] == 2
    # the journal is visible to the agent and the repeat reply carries the cached summary
    assert any("observations_so_far" in obs for obs in seen)
    assert any("NO-OP repeat" in obs and "cached_summary" in obs for obs in seen)


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
