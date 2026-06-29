"""Tests for the plan-driven composer and the two modes (V2-D)."""

from src.agents.methodology_graph import MethodologyGraph
from src.agents.report_compose import (
    FREE,
    GUIDED,
    compose_report,
    heuristic_section_plan,
)

LEDGER = {
    "run": {"uwi": "TEST-1", "confidence_tier": "bracketed", "convergence_status": "CONVERGED"},
    "parameters": {"m": {"value": 2.0, "unit": "-", "provenance": "default"}},
    "zones": [
        {
            "top_m": 100.0,
            "base_m": 101.0,
            "net_pay_m": 1.0,
            "avg_phie": 0.12,
            "avg_sw": 0.4,
            "avg_vsh": 0.1,
        }
    ],
    "summary": {
        "gross_m": 80.0,
        "net_pay_m": 1.0,
        "ntg": 0.0125,
        "avg_phie": 0.12,
        "avg_sw": 0.4,
        "avg_vsh": 0.1,
        "n_zones_raw": 1,
    },
    "net_pay_total_m": 1.0,
    "objections": [],
    "edits": [],
    "tool_results": {"sw_simandoux": {"value": {"mean_sw": 0.35}, "result_hash": "x"}},
}


def _valid_graph(mode: str = FREE) -> MethodologyGraph:
    g = MethodologyGraph(mode=mode, model="m")
    g.add("decision", {"rationale": "dirty rock so Simandoux", "chosen": "sw_simandoux"})
    return g


def test_guided_includes_all_mandatory_sections():
    md = compose_report(LEDGER, {"optional_sections": []}, GUIDED, _valid_graph(GUIDED))
    for title in ("Executive summary", "Methodology", "Zonation", "Results", "Conclusions"):
        assert title in md


def test_free_has_mandatory_methodology_graph_section():
    md = compose_report(LEDGER, {"optional_sections": []}, FREE, _valid_graph())
    assert "Methodology (decision graph)" in md and "flowchart TD" in md


def test_guided_omits_methodology_graph_section():
    md = compose_report(LEDGER, {"optional_sections": []}, GUIDED, _valid_graph(GUIDED))
    assert "decision graph" not in md


def test_heuristic_plan_adds_shaly_sand():
    plan = heuristic_section_plan(LEDGER)
    assert "shaly_sand_saturation" in plan["optional_sections"]
    md = compose_report(LEDGER, plan, FREE, _valid_graph())
    assert "Shaly-sand saturation" in md and "0.35" in md


def test_optional_inserted_after_results():
    md = compose_report(
        LEDGER, {"optional_sections": ["shaly_sand_saturation"]}, FREE, _valid_graph()
    )
    assert (
        md.index("Results")
        < md.index("Shaly-sand saturation")
        < md.index("Uncertainty and sensitivity")
    )


def test_numbering_is_sequential():
    import re

    md = compose_report(LEDGER, {"optional_sections": []}, GUIDED, _valid_graph(GUIDED))
    assert "## 1. Executive summary" in md
    nums = [int(n) for n in re.findall(r"^## (\d+)\. ", md, flags=re.MULTILINE)]
    assert nums == list(range(1, len(nums) + 1))  # 1..N, no gaps


def test_r2_mandatory_sections_present():
    md = compose_report(LEDGER, {"optional_sections": []}, FREE, _valid_graph())
    for title in (
        "Data inventory",
        "LAS quality control",
        "Standardization",
        "Interval definition",
        "Gamma-ray analysis",
        "Water resistivity (Rw)",
        "Limitations",
    ):
        assert title in md


def test_r2_sections_degrade_when_data_absent():
    md = compose_report(LEDGER, {"optional_sections": []}, FREE, _valid_graph())
    assert "Not computed — no resistivity" in md  # no RT in curve_provenance
    assert "needs the RHOB+NPHI" in md  # lithology, no EDA digest


def test_invalid_graph_blocks_in_guided():
    g = MethodologyGraph(mode=GUIDED, model="m")
    g.add("decision", {"rationale": "Sw is 0.33 here"})  # numeric literal -> invalid
    md = compose_report(LEDGER, {"optional_sections": []}, GUIDED, g)
    assert "BLOCKED (guided): methodology graph invalid" in md


def test_invalid_graph_only_warns_in_free():
    g = MethodologyGraph(mode=FREE, model="m")
    g.add("decision", {"rationale": "Sw is 0.33 here"})  # numeric literal -> invalid
    md = compose_report(LEDGER, {"optional_sections": []}, FREE, g)
    assert "methodology graph warnings" in md and "BLOCKED" not in md


def test_claim_verifier_stamped_and_gate_passes():
    ledger = {**LEDGER, "run": dict(LEDGER["run"])}
    md = compose_report(ledger, {"optional_sections": []}, FREE, _valid_graph())
    assert ledger["run"]["claim_verifier"]["result"] == "PASS"
    assert "Claim verifier run on prose | ✓" in md  # Appendix B now satisfied


def test_claim_verifier_flags_untraceable_number():
    ledger = {**LEDGER, "run": dict(LEDGER["run"])}
    narrative = {"executive_summary": "Net pay is 999.9 m.", "conclusions": ""}
    md = compose_report(ledger, {"optional_sections": []}, FREE, _valid_graph(), narrative)
    assert ledger["run"]["claim_verifier"]["result"] == "FLAGS"
    assert 999.9 in ledger["run"]["claim_verifier"]["flags"]
    assert "claim verifier FLAGS" in md


def test_sonic_section_requires_tool_result():
    # selected but no backing tool result -> section is NOT emitted (no theater)
    md = compose_report(LEDGER, {"optional_sections": ["sonic_porosity"]}, FREE, _valid_graph())
    assert "Sonic porosity" not in md
    # with a real tool result -> section renders the number
    ledger = {
        **LEDGER,
        "run": dict(LEDGER["run"]),
        "tool_results": {
            **LEDGER["tool_results"],
            "phi_sonic_wyllie": {"value": {"mean_phi": 0.18}, "result_hash": "y"},
        },
    }
    md2 = compose_report(ledger, {"optional_sections": ["sonic_porosity"]}, FREE, _valid_graph())
    assert "Sonic porosity" in md2 and "0.18" in md2
