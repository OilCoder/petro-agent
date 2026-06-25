"""Unit tests for the Phase-5 agents (LLM mocked — no model required)."""

import os

from src.agents.claim_verifier import verify_report
from src.agents.compute_agent import select_method
from src.agents.report import generate_report
from src.agents.writer import write_report

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "synthetic_oldrocks.las")


def test_select_method_paleozoic():
    sel = select_method("paleozoic")
    assert sel["region"] == "paleozoic_kansas" and sel["variant"] == "old_rocks"


def test_select_method_tertiary():
    sel = select_method("tertiary")
    assert sel["region"] == "north_sea_jurassic" and sel["variant"] == "tertiary"


def test_select_method_unknown_degrades():
    sel = select_method("")
    assert sel["variant"] == "old_rocks" and "degraded" in sel["rationale"]


def test_claim_verifier_passes_on_ledger_numbers():
    ledger = {"run": {"net_pay": 12.5}, "zones": [{"net_pay_m": 8.0}]}
    report = "Net pay is 12.5 m, with a 8.0 m zone."
    assert verify_report(report, ledger)["passed"] is True


def test_claim_verifier_flags_hallucination():
    ledger = {"run": {"net_pay": 12.5}}
    report = "Net pay is 12.5 m and Sw is 0.37."  # 0.37 not in ledger
    out = verify_report(report, ledger)
    assert out["passed"] is False and 0.37 in out["flags"]


def test_writer_uses_injected_chat():
    captured = {}

    def fake_chat(system, user):
        captured["system"] = system
        return "# Petrophysical Report\nNet pay 1.5 m."

    out = write_report({"run": {"confidence_tier": "bracketed"}}, fake_chat)
    assert "Petrophysical Report" in out
    assert "ONLY the numbers" in captured["system"]  # the no-compute rule is enforced


def test_generate_report_integration_mock(tmp_path):
    def fake_chat(system, user):
        return "# Petrophysical Report\nThe interval is bracketed; parameters are defaults."

    result = generate_report(FIXTURE, fake_chat, out_dir=str(tmp_path))
    assert "report" in result and "ledger" in result
    assert result["ledger"]["run"]["claim_verifier"]["result"] in ("PASS", "FLAGS")
    uwi = result["ledger"]["run"]["uwi"]
    assert (tmp_path / f"{uwi}_report.md").exists()
