"""End-to-end report generation: deterministic pipeline -> renderer + narrative -> verify.

The structured report (tables, every number) is rendered deterministically from the
ledger by ``report_template``. The LLM contributes only narrative prose, which is then
claim-verified against the ledger — the renderer's numbers cannot hallucinate by design.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.agents.claim_verifier import verify_report
from src.agents.client import ChatFn
from src.agents.report_template import render_well_report
from src.agents.reviewer import review_report
from src.agents.writer import write_narrative
from src.orchestrator.graph import run_pipeline

VERSION = "0.1.0"


def generate_report(
    las_path: str,
    chat: ChatFn,
    region: str = "paleozoic_kansas",
    out_dir: str = "outputs",
    reviewer_chat: ChatFn | None = None,
    max_revisions: int = 1,
) -> dict[str, Any]:
    """Run the full pipeline, render the structured report with LLM narrative, review it
    once (optional), verify the narrative's numbers, and persist artifacts.

    Returns ``{report, ledger, verification, review}``. Writes ``<uwi>_report.md`` and
    records the claim-verifier and adversarial-review results in the ledger.
    """
    ledger = run_pipeline(las_path, region=region, out_dir=out_dir)
    narrative = write_narrative(ledger, chat)
    report_md = render_well_report(ledger, narrative)

    review: dict[str, Any] = {"passed": True, "objections": []}
    if reviewer_chat is not None:
        review = review_report(report_md, ledger, reviewer_chat)
        revisions = 0
        while not review["passed"] and revisions < max_revisions:
            feedback = "\n".join(f"- {o.detail}" for o in review["objections"])
            narrative = write_narrative(ledger, chat, feedback=feedback)
            report_md = render_well_report(ledger, narrative)
            review = review_report(report_md, ledger, reviewer_chat)
            revisions += 1

    # ✅ Claim-verify ONLY the LLM narrative (the renderer's numbers are deterministic)
    narrative_text = "\n".join(narrative.values())
    verification = verify_report(narrative_text, ledger)

    uwi = ledger["run"]["uwi"]
    ledger["run"]["claim_verifier"] = {
        "result": "PASS" if verification["passed"] else "FLAGS",
        "flags": verification["flags"],
    }
    ledger["run"]["adversarial_review"] = {
        "result": "PASS" if review["passed"] else "OBJECTIONS",
        "count": len(review["objections"]),
    }
    # 🔄 Final render so the ledger excerpt and completeness gate reflect verification
    report_md = render_well_report(ledger, narrative)
    Path(out_dir, f"{uwi}_report.md").write_text(report_md)
    return {
        "report": report_md,
        "ledger": ledger,
        "verification": verification,
        "review": review,
    }
