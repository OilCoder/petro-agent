"""Unit tests for the v2 agents (LLM mocked — no model required)."""

from src.agents.claim_verifier import verify_keyed, verify_tone
from src.agents.writer import write_narrative


def test_verify_keyed_passes_on_ledger_numbers():
    ledger = {"run": {"net_pay": 12.5}, "zones": [{"net_pay_m": 8.0}]}
    report = "Net pay is 12.5 m, with a 8.0 m zone."
    assert verify_keyed(report, ledger)["passed"] is True


def test_verify_keyed_flags_hallucination():
    ledger = {"run": {"net_pay": 12.5}}
    report = "Net pay is 12.5 m and Sw is 0.37."  # 0.37 not in ledger
    out = verify_keyed(report, ledger)
    assert out["passed"] is False and 0.37 in out["flags"]


def test_verify_tone_flags_overconfident_bracketed():
    ledger = {"run": {"confidence_tier": "bracketed"}}
    tone_flags = verify_tone("Net pay is high and the reservoir is excellent.", ledger)
    assert tone_flags


def test_verify_tone_passes_with_hedging():
    ledger = {"run": {"confidence_tier": "bracketed"}}
    tone_flags = verify_tone("Net pay is uncertain; parameters are regional defaults.", ledger)
    assert tone_flags == []


def test_writer_returns_prose_slots():
    captured = {}

    def fake_chat(system, user):
        captured["system"] = system
        return "The reservoir interval is bracketed; parameters are regional defaults."

    out = write_narrative({"run": {"confidence_tier": "bracketed"}}, fake_chat)
    assert set(out) == {"executive_summary", "conclusions"}
    assert "PROSE ONLY" in captured["system"]  # narrative-only enforcement
