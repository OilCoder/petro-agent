"""Regression: the orchestrator re-closes the stale core chain before rendering.

When the agent recomputes a core property (e.g. Sw with Simandoux) and finishes
without re-running apply_cutoffs/run_uncertainty, the report used to deliver the
pass-0 (Archie) net pay/zones/MC next to the recomputed Sw — an internally
inconsistent quantitative state (proven on well 15-135-25945, outputs/v6). The
deterministic loop finalizer must re-run the canonical chain with defaults — an
orchestrator decision, never the LLM's.
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


def test_sw_recompute_then_finish_recloses_netpay_and_uncertainty(tmp_path):
    ledger, ctx = run_pipeline(FIXTURE, out_dir=str(tmp_path), return_ctx=True)
    pass0_avg_sw = ledger["summary"]["avg_sw"]
    script = [
        {"action": "compute_sw", "method": "sw_simandoux"},
        {"action": "finish"},  # agent walks away with netpay/uncertainty stale
    ]
    run_analyst_loop(ledger, ctx, "free", _scripted(script), "m")
    al = ledger["run"]["analyst_loop"]
    # ✅ The orchestrator re-closed the chain deterministically (recorded, not silent)
    assert al["reclosed_steps"] == ["apply_cutoffs", "run_uncertainty"]
    # ✅ The delivered pay-zone summary reflects the agent's Sw choice, not the stale pass-0 chain
    assert ledger["summary"]["avg_sw"] != pass0_avg_sw
    # ✅ The re-close is traced in the methodology graph as orchestrator-owned
    rationales = [
        n["payload"].get("rationale", "")
        for n in ledger["run"]["methodology_graph"]["nodes"]
        if n["type"] == "decision"
    ]
    assert any("RECLOSE" in r for r in rationales)


def test_complete_chain_needs_no_reclose(tmp_path):
    ledger, ctx = run_pipeline(FIXTURE, out_dir=str(tmp_path), return_ctx=True)
    script = [
        {"action": "compute_sw", "method": "sw_simandoux"},
        {"action": "apply_cutoffs"},
        {"action": "run_uncertainty"},
        {"action": "finish"},
    ]
    run_analyst_loop(ledger, ctx, "free", _scripted(script), "m")
    assert ledger["run"]["analyst_loop"]["reclosed_steps"] == []
