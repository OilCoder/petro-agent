"""Deterministic objective score for a v2 report (the unbiased half of evaluation).

Computed by code from the methodology graph + ledger — comparable across models without
the self-indulgence bias of an LLM judging itself. Measures ANALYSIS and COMPOSITION
(exploration coverage, methods used, reasoning depth, justification, honesty), never the
arithmetic correctness of the numbers (the dispatcher guarantees that).
"""

from __future__ import annotations

from typing import Any

from src.agents.report_compose import OPTIONAL_REQUIRES, OPTIONAL_SECTIONS, free_floor_ids
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

    # Agentic-loop signals (how the model worked step by step), present only in loop runs.
    loop = run.get("analyst_loop", {})

    return {
        "exploration_coverage": round(len(observations) / available, 3),
        "methods_selected": len(methods),
        "optional_sections": len(analyst.get("optional_sections", [])),
        "depth_backed": depth_backed,
        "loop_steps": loop.get("steps_taken", 0),
        "loop_recomputes": loop.get("recomputes", 0),
        "loop_wasted": loop.get("wasted_steps", 0),
        "loop_finished_by_agent": loop.get("finished_by_agent", False),
        "reasoning_depth": _longest_path(nodes),
        "decisions_justified": round(len(justified) / len(decisions), 3) if decisions else 0.0,
        "honesty_ok": _honesty_ok(ledger),
        "invariant_clean": run.get("claim_verifier", {}).get("result", "PASS") == "PASS",
    }


def completeness_breakdown(ledger: dict[str, Any], section_plan: dict[str, Any]) -> dict[str, Any]:
    """Split report completeness into two owners so a section count is never mistaken for skill.

    - ``floor`` = the deterministic sections the CODE guarantees (head + forced [FIJO] descriptive +
      baseline core + rails). Present regardless of the agent; this should stay ~complete.
    - ``interpretive`` = what the AGENT actually added beyond the floor: [MODELO] optional sections
      it chose, core methods it changed off the engine default, and whether it restricted the zone.
      This is the real skill signal; a weak agent scores ~0 here and that is the honest reading.
    """
    run = ledger.get("run", {})
    floor = free_floor_ids(ledger)
    chosen_optionals = [
        s for s in section_plan.get("optional_sections", []) if s in OPTIONAL_SECTIONS
    ]
    core_methods_agent_chosen = sum(
        1
        for key in ("porosity_comparison", "sw_summary")
        if ledger.get(key, {}).get("method_source") == "agent"
    )
    zone_restricted = ledger.get("zone_of_interest") is not None
    loop = run.get("analyst_loop", {})
    interpretive_choices = (
        len(chosen_optionals) + core_methods_agent_chosen + (1 if zone_restricted else 0)
    )
    return {
        "floor_sections": len(floor),
        "floor_ids": floor,
        "interpretive_choices": interpretive_choices,
        "modelo_optionals_chosen": chosen_optionals,
        "core_methods_agent_chosen": core_methods_agent_chosen,
        "zone_restricted": zone_restricted,
        "agent_steps": loop.get("agent_steps", 0),
        "default_steps": loop.get("default_steps", 0),
        "wasted_steps": loop.get("wasted_steps", 0),
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
