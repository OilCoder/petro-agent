"""Tests for the field rollup: aggregation arithmetic and field report rendering."""

from src.agents.field_report import aggregate_field, render_field_report

_LEDGERS = [
    {
        "run": {"uwi": "W1", "confidence_tier": "bracketed",
                "convergence_status": "CONVERGED", "net_pay_p10_p50_p90": [4.0, 6.0, 9.0]},
        "summary": {"gross_m": 100.0, "ntg": 0.06, "avg_phie": 0.12, "avg_sw": 0.4},
        "net_pay_total_m": 6.0,
    },
    {
        "run": {"uwi": "W2", "confidence_tier": "bracketed",
                "convergence_status": "DID_NOT_CONVERGE", "net_pay_p10_p50_p90": [8.0, 12.0, 18.0]},
        "summary": {"gross_m": 120.0, "ntg": 0.10, "avg_phie": 0.14, "avg_sw": 0.5},
        "net_pay_total_m": 12.0,
    },
]


def test_aggregate_field_sums_percentiles():
    agg = aggregate_field(_LEDGERS)
    field = agg["field"]
    assert field["n_wells"] == 2
    assert field["net_pay_p10"] == 12.0  # 4 + 8
    assert field["net_pay_p50"] == 18.0  # 6 + 12
    assert field["net_pay_p90"] == 27.0  # 9 + 18
    assert field["gross_m"] == 220.0


def test_aggregate_field_per_well_rows():
    agg = aggregate_field(_LEDGERS)
    assert [w["uwi"] for w in agg["wells"]] == ["W1", "W2"]
    assert agg["wells"][1]["net_pay_p50"] == 12.0


def test_render_field_report_structure():
    agg = aggregate_field(_LEDGERS)
    md = render_field_report(agg, {"executive_summary": "Field prose.", "conclusions": "Done."})
    assert "# Field Petrophysical Report — 2 wells" in md
    assert "Field net pay P10/P50/P90 = 12.0 / 18.0 / 27.0 m" in md
    assert "Strongest well:** W2" in md  # higher P50
    assert "Weakest well:** W1" in md
    assert "Field prose." in md


def test_render_field_report_empty():
    agg = aggregate_field([])
    md = render_field_report(agg, {})
    assert "0 wells" in md
