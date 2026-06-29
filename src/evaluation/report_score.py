"""Deterministic objective score for a v2 report (the unbiased half of evaluation).

Computed by code from the methodology graph + ledger — comparable across models without
the self-indulgence bias of an LLM judging itself. Measures ANALYSIS and COMPOSITION
(exploration coverage, methods used, reasoning depth, justification, honesty), never the
arithmetic correctness of the numbers (the dispatcher guarantees that).
"""

from __future__ import annotations

from typing import Any

from src.agents.report_compose import OPTIONAL_REQUIRES
from src.petrophysics.registry import METHOD_REGISTRY

VERSION = "0.1.0"


def _longest_path(nodes: list[dict[str, Any]]) -> int:
    """Longest directed chain over all node types (reasoning depth)."""
    deps = {n["id"]: list(n.get("depends_on", [])) for n in nodes}
    memo: dict[str, int] = {}

    def depth(nid: str) -> int:
        if nid in memo:
            return memo[nid]
        parents = deps.get(nid, [])
        memo[nid] = 1 + max((depth(p) for p in parents), default=0)
        return memo[nid]

    return max((depth(n["id"]) for n in nodes), default=0)


def objective_score(ledger: dict[str, Any]) -> dict[str, Any]:
    """Return the deterministic objective score for a report's methodology graph + ledger."""
    run = ledger.get("run", {})
    graph = run.get("methodology_graph", {})
    nodes = graph.get("nodes", [])
    observations = [n for n in nodes if n["type"] == "observation"]
    decisions = [n for n in nodes if n["type"] == "decision"]
    tool_calls = [n for n in nodes if n["type"] == "tool_call"]

    analyst = run.get("analyst", {})
    available = max(1, int(analyst.get("n_observations_available", len(observations))))
    methods = [n for n in tool_calls if n["payload"].get("tool") in METHOD_REGISTRY]
    justified = [d for d in decisions if str(d["payload"].get("rationale", "")).strip()]

    # Depth = MODELO sections actually backed by a real tool result (not just requested).
    tool_results = ledger.get("tool_results", {})
    depth_backed = sum(
        1 for tools in OPTIONAL_REQUIRES.values() if any(t in tool_results for t in tools)
    )

    return {
        "exploration_coverage": round(len(observations) / available, 3),
        "methods_selected": len(methods),
        "optional_sections": len(analyst.get("optional_sections", [])),
        "depth_backed": depth_backed,
        "reasoning_depth": _longest_path(nodes),
        "decisions_justified": round(len(justified) / len(decisions), 3) if decisions else 0.0,
        "honesty_ok": _honesty_ok(ledger),
        "invariant_clean": run.get("claim_verifier", {}).get("result", "PASS") == "PASS",
    }


# Optional sections that present a confident result (must not surround an abstaining core).
_CONFIDENT_OPTIONAL = {"shaly_sand_saturation", "sonic_porosity"}


def _honesty_ok(ledger: dict[str, Any]) -> bool:
    """False if a run that abstains is dressed up with confident analysis sections.

    Computed in BOTH modes (free does not block abstention, so the honesty check must run
    regardless): an abstaining core surrounded by confident optional sections is dishonest
    composition even when the gate did not block it.
    """
    run = ledger.get("run", {})
    if not run.get("abstain"):
        return True
    optional = run.get("analyst", {}).get("optional_sections", [])
    confident = {s for s in optional if isinstance(s, str)} & _CONFIDENT_OPTIONAL
    return not confident
