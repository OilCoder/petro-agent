"""Per-model leaderboard (v2): tabulate the objective + qualitative scores side by side.

The objective score (deterministic, unbiased) is the ranking anchor; the same-model
qualitative score is a complementary column, never fused into an opaque composite. "Analyzed
more" is normalized so it is not mistaken for "analyzed better".
"""

from __future__ import annotations

from typing import Any

from src.agents.reviewer import score_report
from src.evaluation.report_score import objective_score

VERSION = "0.1.0"

_QUAL_DIMS = ("completeness", "method_appropriateness", "decision_quality", "honesty", "narrative")


def score_run(ledger: dict[str, Any], report: str, chat: Any) -> dict[str, Any]:
    """Score one run: deterministic objective metrics + same-model qualitative score."""
    graph = ledger.get("run", {}).get("methodology_graph", {})
    objective = objective_score(ledger)
    qualitative = score_report(report, graph, ledger, chat)
    return {"objective": objective, "qualitative": qualitative}


def build_leaderboard(per_model: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Tabulate per-model scores and rank by objective metrics (anchor), not a composite.

    Args:
        per_model: model name -> the ``score_run`` result for that model.

    Returns:
        ``{"rows": [...], "ranked": [model, ...]}`` with objective and qualitative kept
        as separate columns. Ranking: honesty first, then justified decisions, then coverage.
    """
    rows: list[dict[str, Any]] = []
    for model, scored in per_model.items():
        obj = scored["objective"]
        qual = scored["qualitative"]
        rows.append(
            {
                "model": model,
                "honesty_ok": obj["honesty_ok"],
                "invariant_clean": obj["invariant_clean"],
                "exploration_coverage": obj["exploration_coverage"],
                "methods_selected": obj["methods_selected"],
                "optional_sections": obj["optional_sections"],
                "depth_backed": obj["depth_backed"],
                "reasoning_depth": obj["reasoning_depth"],
                "decisions_justified": obj["decisions_justified"],
                "qual_mean": round(sum(qual.get(d, 3) for d in _QUAL_DIMS) / len(_QUAL_DIMS), 2),
            }
        )
    ranked = sorted(
        rows,
        key=lambda r: (
            r["honesty_ok"],
            r["decisions_justified"],
            r["exploration_coverage"],
            r["depth_backed"],
        ),
        reverse=True,
    )
    return {"rows": rows, "ranked": [r["model"] for r in ranked]}
