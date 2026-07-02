"""Author-mode pass-0: run_descriptive_pass produces a descriptive-only skeleton.

The interpretation keys must be ABSENT (not None) so the analyst loop starts from an empty
valid-set and the agent — not the pipeline — authors the interpretation.
"""

import json
import os

from src.agents.analyst_loop import _initial_valid
from src.agents.log_plot import generate_descriptive_figures
from src.orchestrator.graph import run_descriptive_pass

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "synthetic_oldrocks.las")

_INTERPRETATION_KEYS = ("zones", "summary", "net_pay_total_m", "uncertainty", "figures")
_GATE_KEYS = ("convergence_status", "confidence_tier", "abstain", "abstain_reasons")


def test_descriptive_ledger_has_floor_and_no_interpretation(tmp_path):
    ledger, ctx = run_descriptive_pass(FIXTURE, out_dir=str(tmp_path))
    run = ledger["run"]
    assert run["uwi"] and run["curve_provenance"] and run["authoring_mode"] == "agent"
    assert ledger["parameters"] and "edits" in ledger and ledger["objections"] == []
    assert run["config_hash_sha256"] and run["versions"]
    for key in _INTERPRETATION_KEYS:
        assert key not in ledger, f"interpretation key '{key}' must be absent"
    for key in _GATE_KEYS:
        assert key not in run, f"gate key '{key}' must be absent (finalize owns the verdict)"


def test_descriptive_ctx_props_are_none_and_valid_set_empty(tmp_path):
    ledger, ctx = run_descriptive_pass(FIXTURE, out_dir=str(tmp_path))
    assert ctx["vsh"] is None and ctx["phie"] is None and ctx["sw"] is None
    assert ctx["curves"] and ctx["params"] and ctx["out_dir"] == str(tmp_path)
    assert _initial_valid(ctx, ledger) == set()


def test_descriptive_ledger_is_persisted(tmp_path):
    ledger, _ctx = run_descriptive_pass(FIXTURE, out_dir=str(tmp_path))
    path = tmp_path / f"{ledger['run']['uwi']}_ledger.json"
    persisted = json.loads(path.read_text())
    assert persisted["run"]["authoring_mode"] == "agent"
    assert "zones" not in persisted


def test_descriptive_figures_are_raw_only(tmp_path):
    ledger, ctx = run_descriptive_pass(FIXTURE, out_dir=str(tmp_path))
    figs = generate_descriptive_figures(
        ledger["run"]["uwi"], ctx["depth_m"], ctx["curves"], str(tmp_path)
    )
    assert figs and all("_raw_" in f["file"] for f in figs)
    for f in figs:
        assert (tmp_path / f["file"]).exists()
