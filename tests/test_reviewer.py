"""Tests for the Phase-6 adversarial reviewer (LLM mocked)."""

import os

from src.agents.report import generate_report
from src.agents.reviewer import review_report
from src.validators.objections import SUPPORT

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "synthetic_oldrocks.las")
LEDGER = {"run": {"confidence_tier": "bracketed"}}


def test_review_parses_objections():
    def chat(system, user):
        return 'Here are issues: [{"issue": "overclaims net pay", "severity": "high"}]'

    out = review_report("report", LEDGER, chat)
    assert out["passed"] is False
    assert len(out["objections"]) == 1
    assert out["objections"][0].objection_type == SUPPORT


def test_review_passes_on_empty():
    out = review_report("report", LEDGER, lambda s, u: "Looks honest. []")
    assert out["passed"] is True and out["objections"] == []


def test_review_defensive_on_malformed():
    out = review_report("report", LEDGER, lambda s, u: "no json here at all")
    assert out["passed"] is True  # un-parseable -> no objections (fail open, logged raw)


def test_generate_report_with_reviewer(tmp_path):
    writes = {"n": 0}

    def writer(system, user):
        writes["n"] += 1
        return "# Report\nBracketed interval; parameters are regional defaults."

    # reviewer objects once, then passes on the revision
    reviews = {"n": 0}

    def reviewer(system, user):
        reviews["n"] += 1
        return '[{"issue": "add limitation", "severity": "medium"}]' if reviews["n"] == 1 else "[]"

    result = generate_report(
        FIXTURE, writer, out_dir=str(tmp_path), reviewer_chat=reviewer, max_revisions=1
    )
    # write_narrative makes 2 prose-slot calls (exec + conclusions); initial + one revision = 4
    assert writes["n"] == 4
    assert result["ledger"]["run"]["adversarial_review"]["result"] == "PASS"
