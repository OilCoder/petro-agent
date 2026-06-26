"""Tests for v2 per-model evaluation: objective_score, score_report, leaderboard (V2-F)."""

from src.agents.reviewer import score_report
from src.evaluation.leaderboard import build_leaderboard, score_run
from src.evaluation.report_score import objective_score

_GRAPH = {
    "mode": "free",
    "model": "m",
    "nodes": [
        {"id": "obs_1", "type": "observation", "depends_on": [], "payload": {"finding": "x"}},
        {"id": "obs_2", "type": "observation", "depends_on": [], "payload": {"finding": "y"}},
        {
            "id": "dec_1",
            "type": "decision",
            "depends_on": ["obs_1"],
            "payload": {"rationale": "dirty rock so Simandoux", "chosen": "sw_simandoux"},
        },
        {
            "id": "act_1",
            "type": "tool_call",
            "depends_on": ["dec_1"],
            "payload": {"tool": "sw_simandoux", "result_ledger_key": "ledger:sw_simandoux"},
        },
    ],
}
_LEDGER = {
    "run": {
        "methodology_graph": _GRAPH,
        "analyst": {"n_observations_available": 2, "optional_sections": ["shaly_sand_saturation"]},
        "claim_verifier": {"result": "PASS"},
    },
}


def test_objective_score_metrics():
    s = objective_score(_LEDGER)
    assert s["exploration_coverage"] == 1.0  # 2 obs / 2 available
    assert s["methods_selected"] == 1 and s["optional_sections"] == 1
    assert s["decisions_justified"] == 1.0  # 1 of 1 decision has rationale
    assert s["reasoning_depth"] == 3  # obs_1 -> dec_1 -> act_1
    assert s["honesty_ok"] is True and s["invariant_clean"] is True


def test_objective_score_honesty_false_when_abstaining_with_confident_section():
    ledger = {
        "run": {
            "methodology_graph": {"nodes": []},
            "abstain": True,
            "analyst": {"optional_sections": ["shaly_sand_saturation"]},
        },
    }
    assert objective_score(ledger)["honesty_ok"] is False


def test_score_report_parses_and_defaults():
    good = ('{"completeness":4,"method_appropriateness":5,"decision_quality":4,'
            '"honesty":5,"narrative":3,"objections":["x"]}')
    s = score_report("report", _GRAPH, _LEDGER, lambda sy, u: good)
    assert s["completeness"] == 4 and s["objections"] == ["x"]
    # unparseable -> mid defaults (not silently rewarded)
    s2 = score_report("report", _GRAPH, _LEDGER, lambda sy, u: "no json")
    assert s2["completeness"] == 3


def test_leaderboard_ranks_by_objective_anchor():
    def chat(sy, u):
        return ('{"completeness":3,"method_appropriateness":3,"decision_quality":3,'
                '"honesty":3,"narrative":3}')

    strong = score_run(_LEDGER, "r", chat)
    weak_ledger = {
        "run": {
            "methodology_graph": {"nodes": []},
            "analyst": {"n_observations_available": 2, "optional_sections": []},
            "claim_verifier": {"result": "PASS"},
        }
    }
    weak = score_run(weak_ledger, "r", chat)
    board = build_leaderboard({"qwen3": strong, "llama3.1": weak})
    assert board["ranked"][0] == "qwen3"  # more justified decisions + coverage
    assert len(board["rows"]) == 2
