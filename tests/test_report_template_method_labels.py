"""Regression: §Methodology and §Water saturation label the method actually used.

The renderer hardcoded "Archie" (and Larionov/density-neutron in the methodology
table) even when the agent selected another vetted method — outputs/v5+v6 shipped
Simandoux/Indonesia numbers labeled Archie. Labels must come from the ledger's
method ids; the engine defaults remain the fallback when no agent choice exists.
"""

from src.agents.report_template import _methodology, _sw

_AGENT_LEDGER = {
    "calibration": {"vsh_method": {"value": "vsh_linear", "chosen_by_model": True}},
    "porosity_comparison": {"methods": {}, "selected": "phi_density"},
    "sw_summary": {
        "method": "sw_simandoux",
        "mean_sw": 0.563,
        "a": 1.0,
        "m": 2.0,
        "n": 2.0,
        "rw": 0.04,
    },
}


def test_sw_section_labels_the_selected_method():
    section = _sw(_AGENT_LEDGER)
    assert "Simandoux" in section
    assert "Archie" not in section


def test_methodology_table_reflects_ledger_choices():
    table = _methodology(_AGENT_LEDGER)
    assert "sw_simandoux" in table and "Simandoux 1963" in table
    assert "vsh_linear" in table
    assert "phi_density" in table
    assert "Archie" not in table


def test_defaults_still_render_without_agent_choices():
    table = _methodology({})
    assert "Archie 1942" in table
    assert "Larionov" in table
    section = _sw({"sw_summary": {"method": "sw_archie", "mean_sw": 0.6}})
    assert "Archie" in section
