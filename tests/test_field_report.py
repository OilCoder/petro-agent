"""Tests for the field rollup: cross-well aggregation (no sums) and rendering."""

from src.agents.field_report import aggregate_field, render_field_report

_LEDGERS = [
    {
        "run": {"uwi": "W1", "confidence_tier": "bracketed", "convergence_status": "CONVERGED",
                "abstain": False, "net_pay_p10_p50_p90": [4.0, 6.0, 9.0]},
        "summary": {"gross_m": 100.0, "ntg": 0.06, "avg_phie": 0.12, "avg_sw": 0.4},
        "net_pay_total_m": 6.0, "objections": [],
    },
    {
        "run": {"uwi": "W2", "confidence_tier": "bracketed",
                "convergence_status": "DID_NOT_CONVERGE",
                "abstain": True, "net_pay_p10_p50_p90": [8.0, 12.0, 18.0]},
        "summary": {"gross_m": 120.0, "ntg": 0.10, "avg_phie": 0.14, "avg_sw": 0.5},
        "net_pay_total_m": 12.0, "objections": [{"validator_id": "x"}],
    },
]


def test_aggregate_uses_cross_well_stats_not_sums():
    field = aggregate_field(_LEDGERS)["field"]
    assert field["n_wells"] == 2
    assert field["n_abstaining"] == 1
    # mean of 6 and 12 is 9 — NOT the sum 18
    assert field["net_pay_p50"]["mean"] == 9.0
    assert field["net_pay_p50"]["min"] == 6.0 and field["net_pay_p50"]["max"] == 12.0


def test_aggregate_per_well_rows():
    wells = aggregate_field(_LEDGERS)["wells"]
    assert [w["uwi"] for w in wells] == ["W1", "W2"]
    assert wells[1]["abstain"] is True and wells[1]["n_objections"] == 1


def test_render_field_report_no_summed_headline():
    agg = aggregate_field(_LEDGERS)
    md = render_field_report(agg, {"executive_summary": "Field prose.", "conclusions": "Done."})
    assert "# Field Petrophysical Report — 2 wells" in md
    assert "NOT a sum" in md  # explicit anti-sum framing
    assert "mean 9.0 m" in md  # cross-well mean, not 18
    assert "Per-well inventory" in md
    assert "Best reservoir quality:** W2" in md  # higher NTG
    assert "Field prose." in md


def test_render_field_report_lists_excluded():
    agg = aggregate_field(_LEDGERS)
    md = render_field_report(agg, {}, excluded=[{"path": "bad.las", "error": "wrapped"}])
    assert "bad.las" in md and "wrapped" in md


def test_render_field_report_empty():
    agg = aggregate_field([])
    md = render_field_report(agg, {})
    assert "0 wells" in md
