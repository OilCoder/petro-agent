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
    assert route_after_typify({**base, "correctable": 0}) == "gating"  # converged
    assert route_after_typify({**base, "correctable": 2, "iteration": 3}) == "gating"  # max iters
    assert (
        route_after_typify({**base, "correctable": 2, "iteration": 1, "prev_correctable": 2})
        == "gating"
    )  # no decrease
    assert (
        route_after_typify({**base, "correctable": 2, "iteration": 0}) == "correct"
    )  # keep correcting


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
    # high porosity + low RT -> Sw<0.4 with RT<5 -> rt_sw mechanical objection the stub can't fix
    curves = {
        "GR": np.full(n, 40.0),
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
