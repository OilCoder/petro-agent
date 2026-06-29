"""Golden tests for the deterministic report section renderers (zone merge + sections).

The v1 monolithic assembler was removed in the v1 purge; v2 composes via report_compose.
These tests exercise the shared section helpers directly (the composer reuses them).
"""

from src.agents.report_template import (
    _header,
    _parameters,
    _results,
    _uncertainty,
    merge_zones,
)

_LEDGER = {
    "run": {
        "uwi": "TEST-1",
        "convergence_status": "DID_NOT_CONVERGE",
        "confidence_tier": "bracketed",
        "variant": "old_rocks",
        "variant_degraded": True,
        "config_hash_sha256": "abc123def456",
        "versions": {"git_sha": "deadbeef1234", "engine_versions": {"calc_vsh": "0.1.0"}},
        "net_pay_p10_p50_p90": [10.0, 14.0, 19.0],
    },
    "parameters": {
        "m": {"value": 2.0, "unit": "-", "provenance": "default"},
        "Rw": {"value": 0.04, "unit": "ohm-m", "provenance": "default"},
        "gr_min": {"value": 20.0, "unit": "API", "provenance": "default"},
    },
    "zones": [
        {"top_m": 100.0, "base_m": 101.0, "net_pay_m": 1.0,
         "avg_phie": 0.12, "avg_sw": 0.4, "avg_vsh": 0.1},
        {"top_m": 101.5, "base_m": 102.5, "net_pay_m": 1.0,
         "avg_phie": 0.14, "avg_sw": 0.5, "avg_vsh": 0.2},
        {"top_m": 130.0, "base_m": 131.0, "net_pay_m": 1.0,
         "avg_phie": 0.10, "avg_sw": 0.3, "avg_vsh": 0.1},
    ],
    "summary": {
        "gross_m": 80.0, "net_pay_m": 3.0, "ntg": 0.0375,
        "avg_phie": 0.12, "avg_sw": 0.4, "avg_vsh": 0.13, "n_zones_raw": 3,
    },
    "net_pay_total_m": 3.0,
    "objections": [{"validator_id": "v1", "type": "support", "detail": "test objection"}],
    "edits": [{"type": "unit_conversion"}, {"type": "unit_conversion"}, {"type": "null_mask"}],
    "uncertainty": {
        "n_realizations": 500, "seed": 42,
        "sensitivity": {
            "swings_m": {"Rw": 5.0, "m": 6.0, "n": 1.0},
            "dominant_parameter": "m", "dominant_swing_m": 6.0,
        },
        "high_leverage_warning": {"warn": True, "message": "Net pay dominated by 'm' (default)."},
    },
}


def test_merge_zones_merges_within_tolerance():
    merged = merge_zones(_LEDGER["zones"], gap_tol_m=1.5)
    # First two zones (gap 0.5 m) merge; the third (gap 27.5 m) stays separate.
    assert len(merged) == 2
    assert merged[0]["top_m"] == 100.0 and merged[0]["base_m"] == 102.5
    assert merged[0]["net_pay_m"] == 2.0  # net pay preserved (sum)


def test_merge_zones_weighted_average():
    merged = merge_zones(_LEDGER["zones"], gap_tol_m=1.5)
    # Equal weights (1.0 each) -> simple mean of 0.12 and 0.14.
    assert abs(merged[0]["avg_phie"] - 0.13) < 1e-9


def test_merge_zones_empty():
    assert merge_zones([]) == []


def test_merge_zones_preserves_total_net_pay():
    merged = merge_zones(_LEDGER["zones"], gap_tol_m=1.5)
    assert sum(z["net_pay_m"] for z in merged) == _LEDGER["net_pay_total_m"]


def test_header_surfaces_status():
    assert "DID_NOT_CONVERGE" in _header(_LEDGER["run"])


def test_parameters_renders_frozen_citation():
    assert "Archie" in _parameters(_LEDGER)  # frozen citation for parameter 'm'


def test_results_renders_p50_from_ledger():
    assert "14.0" in _results(_LEDGER)  # net pay P50 rendered from ledger


def test_uncertainty_surfaces_dominant_driver():
    md = _uncertainty(_LEDGER)
    assert "Dominant uncertainty: `m`" in md
    assert "dominated by 'm'" in md  # high-leverage warning surfaced


def test_uncertainty_degrades_when_absent():
    ledger = {k: v for k, v in _LEDGER.items() if k != "uncertainty"}
    assert "not run" in _uncertainty(ledger)
