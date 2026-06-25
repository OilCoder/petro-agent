"""Tests for the Phase-4 deterministic orchestrator + circuit breaker."""

import json
import os

import numpy as np

from src.orchestrator.graph import build_graph, run_pipeline
from src.orchestrator.stages import route_after_typify
from src.orchestrator.state import CONVERGED, DID_NOT_CONVERGE
from src.params.config_loader import load_config, resolve_all

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "synthetic_oldrocks.las")


def test_route_circuit_breaker_logic():
    base = {"cb_n": 3}
    assert route_after_typify({**base, "correctable": 0}) == "zonate"  # converged
    assert route_after_typify({**base, "correctable": 2, "iteration": 3}) == "zonate"  # max iters
    assert (
        route_after_typify({**base, "correctable": 2, "iteration": 1, "prev_correctable": 2})
        == "zonate"
    )  # no decrease
    assert (
        route_after_typify({**base, "correctable": 2, "iteration": 0}) == "correct"
    )  # keep correcting


def test_net_pay_plausibility_flags_high_ntg():
    from src.validators.physical import net_pay_plausibility

    # 600 m net pay in a 1000 m well -> NTG 0.6 > 0.5 -> irreducible objection
    objs = net_pay_plausibility(600.0, 1000.0, 0.15)
    assert len(objs) == 1 and objs[0].objection_type == "irreducible"


def test_net_pay_plausibility_flags_high_phie():
    from src.validators.physical import net_pay_plausibility

    objs = net_pay_plausibility(50.0, 1000.0, 0.30)  # avg PHIE 0.30 > 0.25
    assert any("PHIE" in o.detail for o in objs)


def test_net_pay_plausibility_passes_realistic():
    from src.validators.physical import net_pay_plausibility

    assert net_pay_plausibility(40.0, 1000.0, 0.12) == []  # NTG 0.04, PHIE 0.12


def test_tier_downgrade_floors_at_bracketed():
    from src.orchestrator.stages import _downgrade

    assert _downgrade("firm", 1) == "qualified"
    assert _downgrade("firm", 2) == "bracketed"
    assert _downgrade("bracketed", 3) == "bracketed"  # floor


def test_gating_abstains_on_implausible_net_pay():
    from src.orchestrator.stages import gating
    from src.params.schema import ParamValue

    state = {
        "correctable": 0,
        "params": {"a": ParamValue(1.0, "-", "default", "x")},
        "objections": [],
        "net_pay_total_m": 700.0,
        "summary": {"gross_m": 1000.0, "avg_phie": 0.15},
    }
    out = gating(state)  # type: ignore[arg-type]
    assert out["abstain"] is True
    assert any("NTG" in r for r in out["abstain_reasons"])


def test_run_pipeline_emits_ledger(tmp_path):
    ledger = run_pipeline(FIXTURE, out_dir=str(tmp_path))
    assert ledger["run"]["convergence_status"] in (CONVERGED, DID_NOT_CONVERGE)
    assert "config_hash_sha256" in ledger["run"]
    assert "zones" in ledger and "net_pay_total_m" in ledger
    assert "parameters" in ledger and "m" in ledger["parameters"]
    # ledger.json written
    out = tmp_path / f"{ledger['run']['uwi']}_ledger.json"
    assert out.exists()
    assert json.loads(out.read_text())["run"]["uwi"] == ledger["run"]["uwi"]


def test_circuit_breaker_fires_on_persistent_objection(tmp_path):
    n = 20
    # Dirty rock (GR 75 -> vsh > 0.3) so data-driven Rw falls back to the default 0.04;
    # high porosity + low RT then gives Sw<0.4 with RT<5 -> a persistent rt_sw mechanical
    # objection the stub cannot fix, so the circuit breaker fires.
    curves = {
        "GR": np.full(n, 75.0),
        "RHOB": np.full(n, 1.7),
        "NPHI": np.full(n, 0.40),
        "RT": np.full(n, 2.0),
    }
    params = resolve_all(load_config(), "paleozoic_kansas")
    state = {
        "uwi": "NONCONV",
        "out_dir": str(tmp_path),
        "curves": curves,
        "params": params,
        "variant": "old_rocks",
        "depth_m": np.arange(n, dtype=float) * 0.5,
        "step_m": 0.5,
        "qc_edits": [],
        "cb_n": 3,
        "iteration": 0,
    }
    final = build_graph().invoke(state)
    assert final["convergence_status"] == DID_NOT_CONVERGE
