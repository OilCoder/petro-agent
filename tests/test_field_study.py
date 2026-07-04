"""Golden tests for the GA-1 field-study evidence pack."""

import numpy as np

from src.eda.field_study import (
    agreement_stats,
    build_field_context,
    competent_top_m,
    field_tops_summary,
    well_depth_bins,
)


def test_depth_bins_medians_and_row_gating():
    depth = np.linspace(0.0, 199.0, 200)
    curves = {
        "GR": np.concatenate([np.full(100, 40.0), np.full(100, 80.0)]),
        "RHOB": np.full(200, 2.5),
        "RT": np.full(200, np.nan),  # all-NaN -> never a key in any row
    }
    out = well_depth_bins(curves, depth, bin_m=100.0, fine_tail_m=0.0)
    assert len(out["rows"]) == 2
    assert out["rows"][0]["GR"] == 40.0 and out["rows"][1]["GR"] == 80.0
    assert out["rows"][0]["RHOB"] == 2.5
    assert "RT" not in out["rows"][0]


def test_depth_bins_fine_tail_resolution():
    # GB-5: the deepest 500 m bin at 50 m so thin deep contrasts survive the medians
    depth = np.linspace(0.0, 1500.0, 3001)  # 0.5 m step; fine tail starts exactly at 1000
    gr = np.full(3001, 40.0)
    gr[(depth >= 1300) & (depth < 1350)] = 110.0  # thin deep feature, one fine bin wide
    out = well_depth_bins({"GR": gr}, depth)
    fine_rows = [r for r in out["rows"] if r["top"] >= 1000.0]
    coarse_rows = [r for r in out["rows"] if r["top"] < 1000.0]
    # fine tail: 50-m spacing; above: 100-m spacing
    assert all(b["top"] - a["top"] == 50.0 for a, b in zip(fine_rows, fine_rows[1:], strict=False))
    assert all(
        b["top"] - a["top"] == 100.0 for a, b in zip(coarse_rows, coarse_rows[1:], strict=False)
    )
    # the thin feature is visible as its own fine-bin median (not diluted to ~40)
    assert any(r["GR"] > 100.0 for r in fine_rows)


def test_competent_top_detects_the_step():
    depth = np.linspace(0.0, 999.0, 1000)
    rhob = np.where(depth < 600.0, 2.0, 2.6)  # consolidated block from 600 m
    top = competent_top_m(rhob, depth)
    assert top is not None and 590.0 <= top <= 615.0
    assert competent_top_m(None, depth) is None
    assert competent_top_m(np.full(1000, 2.0), depth) is None  # never consolidated


def test_field_tops_summary_percentiles():
    tops = [1000.0, 1050.0, 1100.0, None, 950.0]
    s = field_tops_summary(tops)
    assert s["n_with_top"] == 4 and s["n_without"] == 1
    assert 950.0 <= s["p10"] <= s["p50"] <= s["p90"] <= 1100.0
    assert "p50" not in field_tops_summary([1000.0, None])  # < 3 tops -> no percentiles


def test_observation_surfaces_field_context_and_notes():
    from src.agents.analyst_loop import observation_text

    ledger = {"run": {}, "objections": []}
    fc = build_field_context({"bin_m": 100, "rows": [{"top": 1000, "RHOB": 2.5}]}, 1000.0, {})
    obs = observation_text(ledger, set(), ["finish"], [], None, fc, "my note from well one")
    assert "field_context" in obs and "2.5" in obs
    assert "your_prior_field_notes" in obs and "well one" in obs
    # absent by default (no key noise when not provided)
    obs2 = observation_text(ledger, set(), ["finish"], [], None)
    assert "field_context" not in obs2 and "your_prior_field_notes" not in obs2


def test_agreement_stats_known_offset_and_gating():
    # GA-3 golden: b = a + 0.05 -> perfect correlation, MAD 0.05, bias (median a-b) = -0.05
    a = np.linspace(0.05, 0.25, 50)
    s = agreement_stats(a, a + 0.05)
    assert s["n"] == 50 and s["r"] == 1.0
    assert s["mad"] == 0.05 and s["bias"] == -0.05
    # identical arrays -> zero disagreement
    ident = agreement_stats(a, a.copy())
    assert ident["r"] == 1.0 and ident["mad"] == 0.0 and ident["bias"] == 0.0
    # < 30 finite overlapping samples -> only the honest count
    short = agreement_stats(a[:10], a[:10])
    assert short == {"n": 10}
    # NaNs shrink the overlap, never crash
    b = a.copy()
    b[:25] = np.nan
    assert agreement_stats(a, b) == {"n": 25}
    # zero-variance input -> r reported as 0.0, never NaN
    flat = agreement_stats(np.full(40, 0.1), np.linspace(0.0, 1.0, 40))
    assert flat["r"] == 0.0


def test_well_analysis_digest_is_ledger_facts_only():
    from src.agents.field_report import well_analysis_digest

    ledger = {
        "zone_of_interest": {"top_m": 900.0, "bottom_m": 1382.6},
        "vsh_comparison": {"selected": "vsh_larionov_old", "method_source": "agent"},
        "porosity_comparison": {
            "selected": "phie_density_neutron",
            "method_source": "engine_default",
        },
        "sw_summary": {"method": "sw_simandoux", "method_source": "agent"},
        "run": {"net_pay_p10_p50_p90": [10.0, 22.1, 40.0], "abstain": True},
        "objections": [{"validator_id": "x"}, {"validator_id": "y"}],
    }
    d = well_analysis_digest(ledger)
    assert "zone=900.0-1382.6m" in d
    assert "vsh=vsh_larionov_old[a]" in d and "phie=phie_density_neutron[e]" in d
    assert "netpay_p50=22.1m" in d and "abstain=True" in d and "objections=2" in d
    # unzoned well says so honestly
    assert "zone=none" in well_analysis_digest({"run": {}})


def test_field_context_shape():
    ctx = build_field_context({"bin_m": 100, "rows": []}, 1000.0, {"n_with_top": 1, "n_without": 0})
    assert set(ctx) == {
        "this_well_depth_bins",
        "this_well_competent_top_m",
        "field_competent_tops",
        "note",
    }
