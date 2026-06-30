"""Tests for the v2-native field rollup: selection, cross-well aggregation (no sums), render."""

import numpy as np

from src.agents.field_report import (
    aggregate_field,
    field_well_inventory,
    render_field_report,
    select_field_wells,
    select_wells,
    well_quality_summary,
    write_field_narrative,
)
from src.io.loader import WellData

_METAS = [
    {
        "uwi": "A",
        "curves": ["GR", "RHOB", "NPHI", "RT", "DT"],
        "quality": {
            "runnable": True,
            "pct_usable": 0.9,
            "key_curves": ["GR", "RT", "RHOB", "NPHI"],
            "depth_top": 1000.0,
            "depth_bottom": 1200.0,
        },
    },
    {
        "uwi": "B",
        "curves": ["GR", "RHOB", "NPHI", "RT"],
        "quality": {
            "runnable": True,
            "pct_usable": 0.5,
            "key_curves": ["GR", "RT", "RHOB", "NPHI"],
            "depth_top": 1000.0,
            "depth_bottom": 1100.0,
        },
    },
    {
        "uwi": "C",
        "curves": ["GR", "RT"],
        "quality": {
            "runnable": False,
            "pct_usable": 0.0,
            "key_curves": ["GR", "RT"],
            "depth_top": 1000.0,
            "depth_bottom": 1050.0,
        },
    },
    {
        "uwi": "D",
        "curves": ["GR", "RHOB", "NPHI", "RT"],
        "quality": {
            "runnable": True,
            "pct_usable": 0.7,
            "key_curves": ["GR", "RT", "RHOB", "NPHI"],
            "depth_top": 1000.0,
            "depth_bottom": 1150.0,
        },
    },
]


def test_select_field_wells_model_choice():
    chat = lambda s, u: '{"wells": ["B", "D"], "rationale": "fuller suites"}'  # noqa: E731
    out = select_field_wells(_METAS, chat=chat, max_wells=4)
    assert out["fell_back"] is False
    assert out["selected"] == ["B", "D"]


def test_select_field_wells_falls_back_to_best_quality():
    chat = lambda s, u: "no json here"  # noqa: E731
    out = select_field_wells(_METAS, chat=chat, max_wells=2)
    assert out["fell_back"] is True
    # ranked by runnable then pct_usable: A (0.9), D (0.7)
    assert out["selected"] == ["A", "D"]


def test_select_field_wells_drops_unknown():
    chat = lambda s, u: '{"wells": ["A", "ZZ", "C"]}'  # noqa: E731
    out = select_field_wells(_METAS, chat=chat, max_wells=4)
    assert out["selected"] == ["A", "C"]  # unknown ZZ dropped, free selection (C allowed)


def test_field_well_inventory_shows_quality():
    inv = field_well_inventory(_METAS)
    assert "90% usable" in inv and "QC-abort/poor" in inv and "GR/RT/RHOB/NPHI" in inv


def test_well_quality_summary_runnable_and_abort():
    n = 20
    depth = np.arange(n, dtype=float) * 0.5 + 1000.0
    good = WellData(
        "x",
        "W",
        "uwi",
        "paleozoic",
        depth,
        0.5,
        {
            "GR": np.linspace(20, 80, n),
            "RHOB": np.full(n, 2.35),
            "NPHI": np.full(n, 0.20),
            "RT": np.full(n, 10.0),
        },
    )
    q = well_quality_summary(good)
    assert q["runnable"] is True and q["pct_usable"] > 0.9
    assert q["key_curves"] == ["GR", "RT", "RHOB", "NPHI"]

    bad = WellData("x", "W", "uwi", "paleozoic", depth, 0.5, {"GR": np.full(n, np.nan)})
    qb = well_quality_summary(bad)
    assert qb["runnable"] is False and qb["pct_usable"] == 0.0


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


def test_select_wells_caps_and_orders():
    sel = select_wells(["W1", "W2", "W3", "W4"], model_choice=["W3", "W4", "W2"], max_wells=2)
    assert sel["selected"] == ["W3", "W4"]  # capped at max_wells=2, in choice order


def test_select_wells_drops_unknown_and_dupes():
    sel = select_wells(["W1", "W2"], model_choice=["W1", "ZZ", "W1", "W2"], max_wells=4)
    assert sel["selected"] == ["W1", "W2"]  # unknown ZZ + duplicate W1 dropped


def test_aggregate_is_cross_well_not_summed():
    field = aggregate_field(_LEDGERS)["field"]
    assert field["n_wells"] == 2 and field["n_abstaining"] == 1
    assert field["net_pay_p50"]["mean"] == 9.0  # (6+12)/2, NOT 18 (sum)
    assert field["net_pay_p50"]["min"] == 6.0 and field["net_pay_p50"]["max"] == 12.0


def test_render_field_report_no_summed_headline():
    md = render_field_report(
        aggregate_field(_LEDGERS),
        {"executive_summary": "Field prose.", "conclusions": "Done."},
        selection={"selected": ["W1", "W2"]},
    )
    assert "NOT a sum" in md and "quality-aware" in md and "W1" in md and "W2" in md
