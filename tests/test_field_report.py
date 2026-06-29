"""Tests for the v2-native field rollup: selection, cross-well aggregation (no sums), render."""

from src.agents.field_report import (
    aggregate_field,
    render_field_report,
    select_field_wells,
    select_wells,
    write_field_narrative,
)

_METAS = [
    {"uwi": "A", "curves": ["GR", "RHOB", "NPHI", "RT", "DT"]},
    {"uwi": "B", "curves": ["GR", "RHOB", "NPHI", "RT"]},
    {"uwi": "C", "curves": ["GR", "RT"]},
    {"uwi": "D", "curves": ["GR", "RHOB", "NPHI", "RT"]},
]


def test_select_field_wells_model_choice():
    chat = lambda s, u: '{"wells": ["B", "D"], "rationale": "fuller suites"}'  # noqa: E731
    out = select_field_wells(_METAS, anchor="A", chat=chat, n_free=2)
    assert out["fell_back"] is False
    assert out["selected"] == ["A", "B", "D"] and out["anchor"] == "A"


def test_select_field_wells_falls_back_on_garbage():
    chat = lambda s, u: "no json here"  # noqa: E731
    out = select_field_wells(_METAS, anchor="A", chat=chat, n_free=2)
    assert out["fell_back"] is True
    assert out["anchor"] == "A" and len(out["free"]) == 2 and "A" not in out["free"]


def test_select_field_wells_drops_anchor_and_unknown():
    chat = lambda s, u: '{"wells": ["A", "ZZ", "C"]}'  # noqa: E731
    out = select_field_wells(_METAS, anchor="A", chat=chat, n_free=2)
    assert out["free"] == ["C"]  # anchor + unknown dropped


def test_write_field_narrative_prose_only():
    captured = {}

    def fake_chat(system, user):
        captured["system"] = system
        return "Field prose with honest uncertainty."

    agg = {
        "field": {
            "n_wells": 3,
            "n_abstaining": 2,
            "net_pay_p50": {"mean": 157.4, "min": 82.5, "max": 202.2},
            "ntg": {"mean": 0.129},
        }
    }
    out = write_field_narrative(agg, fake_chat)
    assert set(out) == {"executive_summary", "conclusions"}
    assert "PROSE ONLY" in captured["system"] and "never sum" in captured["system"].lower()


_LEDGERS = [
    {
        "run": {
            "uwi": "W1",
            "confidence_tier": "qualified",
            "convergence_status": "CONVERGED",
            "abstain": False,
            "net_pay_p10_p50_p90": [4.0, 6.0, 9.0],
            "well_metadata": {"latitude": "38.1", "longitude": "-99.6"},
        },
        "summary": {"ntg": 0.2, "avg_phie": 0.18, "avg_sw": 0.4},
        "objections": [],
    },
    {
        "run": {
            "uwi": "W2",
            "confidence_tier": "bracketed",
            "convergence_status": "DID_NOT_CONVERGE",
            "abstain": True,
            "net_pay_p10_p50_p90": [8.0, 12.0, 18.0],
            "well_metadata": {},
        },
        "summary": {"ntg": 0.3, "avg_phie": 0.22, "avg_sw": 0.5},
        "objections": [{"validator_id": "x", "type": "mechanical", "detail": "y"}],
    },
]


def test_select_wells_anchor_plus_two_free():
    sel = select_wells(["W1", "W2", "W3", "W4"], anchor="W1", model_choice=["W3", "W4", "W2"])
    assert sel["anchor"] == "W1"
    assert sel["free"] == ["W3", "W4"]  # excludes anchor, capped at n_free=2
    assert sel["selected"] == ["W1", "W3", "W4"]


def test_select_wells_drops_unknown_and_anchor_dupes():
    sel = select_wells(["W1", "W2"], anchor="W1", model_choice=["W1", "ZZ", "W2"], n_free=2)
    assert sel["free"] == ["W2"]


def test_aggregate_is_cross_well_not_summed():
    field = aggregate_field(_LEDGERS)["field"]
    assert field["n_wells"] == 2 and field["n_abstaining"] == 1
    assert field["net_pay_p50"]["mean"] == 9.0  # (6+12)/2, NOT 18 (sum)
    assert field["net_pay_p50"]["min"] == 6.0 and field["net_pay_p50"]["max"] == 12.0


def test_render_field_report_no_summed_headline():
    md = render_field_report(
        aggregate_field(_LEDGERS),
        {"executive_summary": "Field prose.", "conclusions": "Done."},
        selection={"anchor": "W1", "free": ["W2"]},
    )
    assert "NOT a sum" in md and "anchor `W1`" in md and "W2" in md
