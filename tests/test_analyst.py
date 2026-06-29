"""Tests for the analyst node + signaled fallback cascade (V2-E). Fake chats, no model."""

import numpy as np

from src.agents.analyst import _parse_plan, build_eda_digest, run_analyst

N = 50
CTX = {
    "curves": {
        "GR": np.full(N, 50.0),
        "RT": np.full(N, 10.0),
        "RHOB": np.full(N, 2.5),
        "NPHI": np.full(N, 0.2),
    },
    "phie": np.full(N, 0.2),
    "vsh": np.full(N, 0.3),
    "depth_m": np.arange(N, dtype=float) * 0.5,
    "step_m": 0.5,
    "quality_map": np.array(["GOOD"] * N, dtype=object),
}

_GOOD_PLAN = (
    '{"optional_sections": ["shaly_sand_saturation"], '
    '"tool_calls": [{"tool": "sw_simandoux", "args": {"electrical_preset": "carbonate_default"}}], '
    '"rationale": "dirty rock so a shaly-sand model is warranted"}'
)


def test_build_eda_digest_is_compact_and_structured():
    d = build_eda_digest(CTX)
    assert "available_methods" in d and "lithology" in d and "low_resistivity" in d
    assert isinstance(d["curves_present"], list)


def test_parse_plan_tolerant():
    assert _parse_plan("here is the plan: " + _GOOD_PLAN)["optional_sections"] == [
        "shaly_sand_saturation"
    ]
    assert _parse_plan("no json") is None
    assert _parse_plan("") is None


def test_analyst_uses_primary_model_plan():
    ledger: dict = {}
    out = run_analyst(ledger, CTX, "free", lambda s, u: _GOOD_PLAN, "qwen3:30b-a3b")
    assert out["fell_back"] is False
    assert ledger["run"]["analyst"]["model_used"] == "qwen3:30b-a3b"
    assert "sw_simandoux" in ledger["tool_results"]  # dispatched
    assert ledger["run"]["methodology_graph"]["mode"] == "free"


def test_analyst_falls_back_to_second_model_on_empty():
    ledger: dict = {}
    out = run_analyst(
        ledger,
        CTX,
        "free",
        lambda s, u: "",
        "qwen3:30b-a3b",
        fallback_chat=lambda s, u: _GOOD_PLAN,
        fallback_model="llama3.1:8b",
    )
    assert out["fell_back"] is False
    assert ledger["run"]["analyst"]["model_used"] == "llama3.1:8b"
    assert ledger["run"]["analyst"]["empty_returns"] == 1


def test_analyst_signaled_deterministic_fallback_when_all_fail():
    ledger = {"run": {}, "tool_results": {"sw_simandoux": {"value": {"mean_sw": 0.3}}}}
    out = run_analyst(
        ledger,
        CTX,
        "free",
        lambda s, u: "",
        "qwen3:30b-a3b",
        fallback_chat=lambda s, u: "garbage no json",
        fallback_model="llama3.1:8b",
    )
    assert out["fell_back"] is True
    a = ledger["run"]["analyst"]
    assert a["fell_back_to_deterministic"] is True and a["model_used"] == "deterministic"
    assert a["empty_returns"] == 1  # qwen empty; llama produced (invalid) text


def test_analyst_rejects_out_of_whitelist_tool():
    bad = (
        '{"optional_sections": [], '
        '"tool_calls": [{"tool": "sw_invented", "args": {}}], "rationale": "x"}'
    )
    ledger: dict = {}
    out = run_analyst(ledger, CTX, "guided", lambda s, u: bad, "m")
    # invalid plan -> falls back; nothing from the bad tool dispatched
    assert out["fell_back"] is True and "sw_invented" not in ledger.get("tool_results", {})
