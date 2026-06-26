"""The analyst agent node (v2): EXPLORE -> DECIDE -> DISPATCH, with signaled fallback.

The one place the LLM gets analytical agency: it reads a COMPACT EDA digest + the available
vetted methods and DECIDES which optional analyses/sections add completeness — emitting a
plan of method/section IDs and rationale, never a number. The deterministic dispatcher runs
the tools. If the model returns empty (the 16GB-VRAM failure mode) or invalid JSON, the
cascade falls back qwen3 -> llama3.1 -> deterministic heuristic, ALWAYS signaled in the
ledger (never silent), so a base-by-failure is never mistaken for a base-by-choice.
"""

from __future__ import annotations

import json
import re
from typing import Any

from src.agents.client import ChatFn
from src.agents.methodology_graph import MethodologyGraph
from src.agents.report_compose import heuristic_section_plan
from src.agents.tool_dispatch import dispatch, validate_plan
from src.eda import explore
from src.petrophysics.registry import available_methods

VERSION = "0.1.0"

_SYSTEM = """You are a senior petrophysical ANALYST choosing how to complete a well report.
From the FACTS (pre-computed observations) and AVAILABLE METHODS, decide which optional
analyses add completeness.

ABSOLUTE RULES:
- Output ONLY a JSON object: {"optional_sections": [...], "tool_calls": [{"tool": "<id>",
  "args": {"electrical_preset": "<preset_id>"}}], "rationale": "<why, NO numbers>"}.
- Choose method IDs ONLY from AVAILABLE METHODS and section IDs from the catalog. Never
  invent an ID. Never write a number — the engine computes; you select.
- Keep the rationale to plain words (no decimals); reference what the data shows, not values."""


def build_eda_digest(ctx: dict[str, Any]) -> dict[str, Any]:
    """Pre-compute the compact EDA observations (the agent observes, never computes)."""
    curves = ctx["curves"]
    digest: dict[str, Any] = {
        "curves_present": sorted(curves),
        "available_methods": available_methods(curves),
        "badhole": explore.badhole_summary(ctx["quality_map"]),
    }
    if "RT" in curves and "phie" in ctx:
        digest["low_resistivity"] = explore.low_resistivity_scan(
            curves["RT"], ctx["depth_m"], ctx["phie"]
        )
    if "RHOB" in curves and "NPHI" in curves:
        digest["lithology"] = explore.crossplot_density_neutron(curves["RHOB"], curves["NPHI"])
    return digest


def _digest_text(digest: dict[str, Any]) -> str:
    """Compact (<~800 token) text of the digest for the LLM — never the raw curve blob."""
    return "FACTS:\n" + json.dumps(digest, indent=1)[:3000]


_OBJECT = re.compile(r"\{.*\}", re.DOTALL)


def _parse_plan(raw: str) -> dict[str, Any] | None:
    """Tolerant extraction of the plan JSON; None if unparseable or malformed."""
    if not raw or not raw.strip():
        return None
    m = _OBJECT.search(raw)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    data.setdefault("optional_sections", [])
    data.setdefault("tool_calls", [])
    data.setdefault("rationale", "")
    if not isinstance(data["tool_calls"], list) or not isinstance(data["optional_sections"], list):
        return None
    return data


def run_analyst(
    ledger: dict[str, Any],
    ctx: dict[str, Any],
    mode: str,
    chat: ChatFn,
    model: str,
    fallback_chat: ChatFn | None = None,
    fallback_model: str = "",
) -> dict[str, Any]:
    """Run EXPLORE -> DECIDE -> DISPATCH and return ``{section_plan, graph, fell_back}``.

    Records ``ledger['run']['analyst']`` (model_used, empty_returns, fell_back_to_deterministic)
    and ``ledger['run']['methodology_graph']``. The cascade is always signaled.
    """
    graph = MethodologyGraph(mode=mode, model=model)
    digest = build_eda_digest(ctx)
    graph.add(
        "observation",
        {
            "tool": "eda_digest",
            "finding": "exploration complete",
            "source_ledger_key": "ledger:eda",
        },
    )
    ledger.setdefault("run", {})["eda"] = digest

    plan: dict[str, Any] | None = None
    used = ""
    empty_returns = 0
    for c, mdl in ((chat, model), (fallback_chat, fallback_model)):
        if c is None:
            continue
        raw = c(_SYSTEM, _digest_text(digest))
        if not raw or not raw.strip():
            empty_returns += 1
            continue
        candidate = _parse_plan(raw)
        if candidate is not None and not validate_plan({"tool_calls": candidate["tool_calls"]}):
            plan, used = candidate, mdl
            break

    fell_back = plan is None
    if plan is None:
        plan = heuristic_section_plan(ledger)
        plan["tool_calls"] = []
        plan["rationale"] = "deterministic heuristic (analyst unavailable)"
        used = "deterministic"

    graph.add(
        "decision",
        {
            "rationale": str(plan.get("rationale", "")),
            "chosen": ",".join(c.get("tool", "") for c in plan["tool_calls"]),
        },
    )
    dispatch({"tool_calls": plan["tool_calls"]}, ctx, ledger, graph)

    ledger["run"]["analyst"] = {
        "model_used": used,
        "empty_returns": empty_returns,
        "fell_back_to_deterministic": fell_back,
    }
    ledger["run"]["methodology_graph"] = graph.to_json()
    return {
        "section_plan": {"optional_sections": plan.get("optional_sections", [])},
        "graph": graph,
        "fell_back": fell_back,
    }
