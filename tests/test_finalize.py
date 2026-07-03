"""finalize_run: the gate verdict must describe the FINAL chain, not pass-0's snapshot.

Regression for the stale-banner finding (v7 read-through): after the loop recomputes the
chain, the abstention banner cited pass-0 numbers (avg PHIE 0.31) while §18 showed the
post-reclose value (0.291). finalize_run rebuilds objections + verdict from the ledger and
ctx as they stand at the END.
"""

import os

from src.orchestrator.finalize import finalize_run
from src.orchestrator.graph import run_pipeline

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "synthetic_oldrocks.las")


def _pipeline(tmp_path):
    return run_pipeline(FIXTURE, out_dir=str(tmp_path), return_ctx=True)


def test_finalize_writes_verdict_keys_and_persists(tmp_path):
    ledger, ctx = _pipeline(tmp_path)
    finalize_run(ledger, ctx)
    run = ledger["run"]
    assert run["convergence_status"] in ("CONVERGED", "DID_NOT_CONVERGE")
    assert run["confidence_tier"] in ("firm", "qualified", "bracketed")
    assert isinstance(run["abstain"], bool) and isinstance(run["abstain_reasons"], list)
    assert (tmp_path / f"{run['uwi']}_ledger.json").exists()


def test_finalize_banner_cites_the_final_chain_not_pass0(tmp_path):
    # Simulate a post-loop rechain: the FINAL summary differs from what pass-0 gated on.
    ledger, ctx = _pipeline(tmp_path)
    ledger["summary"] = dict(ledger.get("summary", {}))
    ledger["summary"]["avg_phie"] = 0.30  # implausible (> 0.25) — must appear in the reasons
    ledger["summary"]["gross_m"] = 1000.0
    ledger["net_pay_total_m"] = 100.0  # NTG 0.10, plausible — isolates the PHIE reason
    finalize_run(ledger, ctx)
    reasons = ledger["run"]["abstain_reasons"]
    assert ledger["run"]["abstain"] is True
    assert any("0.30" in r for r in reasons), reasons  # the FINAL number, not pass-0's


def test_finalize_is_idempotent(tmp_path):
    ledger, ctx = _pipeline(tmp_path)
    finalize_run(ledger, ctx)
    first = [o["detail"] for o in ledger["objections"]]
    finalize_run(ledger, ctx)
    assert [o["detail"] for o in ledger["objections"]] == first  # rebuilt, never duplicated


def test_finalize_incomplete_chain_abstains_honestly(tmp_path):
    ledger, ctx = _pipeline(tmp_path)
    ctx["sw"] = None  # a chain even the re-close could not finish (missing curve scenario)
    finalize_run(ledger, ctx)
    run = ledger["run"]
    assert run["abstain"] is True
    assert run["confidence_tier"] == "bracketed"
    assert any("incomplete" in r for r in run["abstain_reasons"])


def test_finalize_regenerates_figures_from_final_arrays(tmp_path):
    ledger, ctx = _pipeline(tmp_path)
    ledger["figures"] = []  # wipe pass-0's list; finalize must rebuild from ctx arrays
    finalize_run(ledger, ctx)
    assert ledger["figures"], "figures must be regenerated"
    first = tmp_path / ledger["figures"][0]["file"]
    assert first.exists()
