"""End-to-end report generation: deterministic pipeline -> writer -> claim verifier."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.agents.claim_verifier import verify_report
from src.agents.client import ChatFn
from src.agents.writer import write_report
from src.orchestrator.graph import run_pipeline

VERSION = "0.1.0"


def generate_report(
    las_path: str,
    chat: ChatFn,
    region: str = "paleozoic_kansas",
    out_dir: str = "outputs",
) -> dict[str, Any]:
    """Run the full pipeline, write the prose report, verify claims, persist artifacts.

    Returns ``{report, ledger, verification}``. Writes ``<uwi>_report.md`` and updates
    the ledger's ``run.claim_verifier`` result.
    """
    ledger = run_pipeline(las_path, region=region, out_dir=out_dir)
    report_md = write_report(ledger, chat)
    verification = verify_report(report_md, ledger)

    uwi = ledger["run"]["uwi"]
    ledger["run"]["claim_verifier"] = {
        "result": "PASS" if verification["passed"] else "FLAGS",
        "flags": verification["flags"],
    }
    Path(out_dir, f"{uwi}_report.md").write_text(report_md)
    return {"report": report_md, "ledger": ledger, "verification": verification}
