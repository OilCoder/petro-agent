"""Regression: the agent's method choices survive into the persisted artifacts.

The v6 audit had to reverse-engineer WHICH Sw model the agent picked because
(1) methodology-graph tool_call nodes recorded only args, not the method id, and
(2) <uwi>_ledger.json was the pass-0 snapshot — the loop's mutations (sw_summary,
vsh_comparison, run.analyst_loop, run.methodology_graph) were never re-persisted.
"""

import json
import os

from src.agents.analyst_loop import run_analyst_loop
from src.orchestrator.graph import run_pipeline

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "synthetic_oldrocks.las")


def _scripted(script):
    it = iter(script)

    def chat(system, user):
        if "SKEPTICAL" in system:  # R13 skeptic pass -> no objections (do not eat script)
            return json.dumps({"objections": []})
        try:
            return json.dumps(next(it))
        except StopIteration:
            return json.dumps({"action": "finish"})

    return chat


def test_persisted_ledger_records_the_agent_choices(tmp_path):
    ledger, ctx = run_pipeline(FIXTURE, out_dir=str(tmp_path), return_ctx=True)
    script = [{"action": "compute_sw", "method": "sw_simandoux"}, {"action": "finish"}]
    run_analyst_loop(ledger, ctx, "free", _scripted(script), "m")

    path = tmp_path / f"{ledger['run']['uwi']}_ledger.json"
    saved = json.loads(path.read_text())
    # ✅ The interpretive-choice keys survive persistence (auditable without rerunning)
    assert saved["sw_summary"]["method"] == "sw_simandoux"
    assert saved["sw_summary"]["method_source"] == "agent"
    assert "vsh_comparison" in saved and "porosity_comparison" in saved
    assert saved["run"]["analyst_loop"]["reclosed_steps"] == ["apply_cutoffs", "run_uncertainty"]

    # ✅ The graph's tool_call node names the vetted method the agent picked
    calls = [
        n["payload"]
        for n in saved["run"]["methodology_graph"]["nodes"]
        if n["type"] == "tool_call" and n["payload"].get("tool") == "compute_sw"
    ]
    assert calls and calls[0].get("method") == "sw_simandoux"
