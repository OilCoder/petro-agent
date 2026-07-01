"""Completeness two-cube metric + anti-filler / anti-interpretation guard on renderers.

Enforces the two-owner rule: the descriptive floor is the code's (complete, no filler) and the
interpretive body is the agent's (a measured contribution). A [FIJO] section must carry
well-specific data or a truthful absence marker — never generic prose to inflate the chapter
count, and never a code-authored interpretation (that belongs to the analyst).
"""

from src.agents import report_template as rt
from src.evaluation.report_score import completeness_breakdown

# ----------------------------------------
# Change 2 — completeness split into floor (code) vs interpretive contribution (agent)
# ----------------------------------------


def test_completeness_separates_floor_from_agent_contribution():
    ledger = {
        "run": {
            "curve_provenance": {"GR": {}, "RT": {}, "RHOB": {}, "NPHI": {}},  # no CALI
            "analyst_loop": {"agent_steps": 1, "default_steps": 0, "wasted_steps": 2},
        },
        "figures": ["composite"],
        "porosity_comparison": {"method_source": "agent"},
        "sw_summary": {"method_source": "engine_default"},
        "zone_of_interest": None,
    }
    plan = {"sections": ["vsh", "porosity"], "optional_sections": ["permeability"]}
    br = completeness_breakdown(ledger, plan)

    # floor is code-guaranteed and curve-gated: gr/resistivity/lithology present, caliper absent
    assert "gr_analysis" in br["floor_ids"] and "vsh" in br["floor_ids"]
    assert "caliper_quality" not in br["floor_ids"]  # no CALI curve
    assert br["floor_sections"] >= 20

    # interpretive contribution = chosen [MODELO] optionals + agent core-method changes + zone
    assert br["modelo_optionals_chosen"] == ["permeability"]
    assert br["core_methods_agent_chosen"] == 1  # porosity agent-chosen; sw was engine_default
    assert br["zone_restricted"] is False
    assert br["interpretive_choices"] == 2  # 1 optional + 1 core method + 0 zone


def test_completeness_zero_agent_contribution_reads_honestly():
    # a run where the agent added nothing beyond the floor must score 0 interpretive choices
    ledger = {"run": {"curve_provenance": {"GR": {}}, "analyst_loop": {"agent_steps": 0}}}
    plan = {"sections": [], "optional_sections": []}
    br = completeness_breakdown(ledger, plan)
    assert br["interpretive_choices"] == 0
    assert br["floor_sections"] > 0  # the floor still stands (code's job)


# ----------------------------------------
# Change 3 — anti-filler / anti-interpretation guard
# ----------------------------------------

# Renderers that must degrade to a truthful "not computed" marker when their data is absent.
_ABSENCE_RENDERERS = [
    rt._resistivity_analysis,
    rt._caliper_quality,
    rt._lithology,
    rt._permeability_section,
    rt._derived_parameters_section,
    rt._rock_quality_section,
    rt._electrofacies_section,
]

# Interpretive/generic phrases the CODE must never author (they are the analyst's, or are filler).
_BANNED = (
    "suggests",
    "indicates",
    "recommend",
    "acquire",
    "good reservoir",
    "poor reservoir",
    "dolomitic",
    "overburden",
    "not reservoir",
    "buckles",
    "consolidated rock",
    "prospective",
    "pay zone",
)


def test_fijo_renderers_degrade_to_honest_absence():
    for fn in _ABSENCE_RENDERERS:
        out = fn({}).lower()
        assert "not computed" in out, f"{fn.__name__} did not state absence honestly: {out!r}"


def test_renderers_never_author_interpretation_or_filler():
    extra = [rt._recommendations, rt._limitations, rt._gr_analysis]
    for fn in _ABSENCE_RENDERERS + extra:
        out = fn({}).lower()
        for phrase in _BANNED:
            assert phrase not in out, f"{fn.__name__} authored banned phrase {phrase!r}: {out!r}"


def test_lithology_reports_shares_not_a_named_conclusion():
    ledger = {"run": {"eda": {"lithology": {"shares": {"sandstone": 0.1, "limestone": 0.2}}}}}
    out = rt._lithology(ledger).lower()
    # it must surface the numeric shares and defer the naming to the analyst, not conclude
    assert "analyst" in out and "0.2" in out
    for phrase in _BANNED:
        assert phrase not in out


def test_derived_parameters_has_no_interpretive_note():
    ledger = {"tool_results": {"bvw": {"value": {"mean_bvw": 0.08}}}}
    out = rt._derived_parameters_section(ledger).lower()
    assert "bulk-volume water" in out and "buckles" not in out and "suggests" not in out
