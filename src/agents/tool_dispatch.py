"""Deterministic tool dispatcher (v2): the orchestrator executes, the LLM never computes.

The agent emits a plan of tool-calls (IDs + args); this module validates each against the
frozen whitelist (the method registry + EDA tools), executes the deterministic function,
writes the result under a NAMED ledger key with a result_hash, and records a tool_call node
in the methodology graph. The number and its hash come from code — the LLM only chose the
ID and (vetted-preset) args. Electrical/cutoff numbers come from presets, never the plan.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import numpy as np

from src.agents.methodology_graph import MethodologyGraph
from src.eda import explore
from src.petrophysics.registry import (
    ELECTRICAL_PRESETS,
    METHOD_REGISTRY,
)

VERSION = "0.1.0"

# EDA tools the agent may invoke (read-only observations).
_EDA_TOOLS = {
    "curve_inventory",
    "depth_coverage",
    "histogram_stats",
    "crossplot_density_neutron",
    "low_resistivity_scan",
    "gr_baseline_check",
    "badhole_summary",
}
ALLOWED_TOOLS: set[str] = set(METHOD_REGISTRY) | _EDA_TOOLS


def _hash(result: Any) -> str:
    return hashlib.sha256(json.dumps(result, sort_keys=True, default=str).encode()).hexdigest()[:16]


def validate_plan(plan: dict[str, Any]) -> list[str]:
    """Return issues with a plan (empty = valid). Rejects unknown tools and bad preset args."""
    issues: list[str] = []
    calls = plan.get("tool_calls")
    if not isinstance(calls, list):
        return ["plan.tool_calls must be a list"]
    for i, call in enumerate(calls):
        if not isinstance(call, dict):
            issues.append(f"call {i}: not an object")
            continue
        tool = call.get("tool")
        if not isinstance(tool, str) or tool not in ALLOWED_TOOLS:
            issues.append(f"call {i}: tool {tool!r} not a whitelisted id")
            continue
        args = call.get("args", {})
        preset = args.get("electrical_preset") if isinstance(args, dict) else None
        if tool in METHOD_REGISTRY and METHOD_REGISTRY[tool].property == "sw":
            if preset is not None and preset not in ELECTRICAL_PRESETS:
                issues.append(f"call {i}: unknown electrical_preset {preset!r}")
    return issues


def _run_sw_method(method_id: str, ctx: dict[str, Any], args: dict[str, Any]) -> dict[str, Any]:
    spec = METHOD_REGISTRY[method_id]
    preset = ELECTRICAL_PRESETS[args.get("electrical_preset", "carbonate_default")]
    rt, phie, vsh = ctx["curves"]["RT"], ctx["phie"], ctx["vsh"]
    if method_id == "sw_archie":
        arr = spec.fn(rt, phie, preset["a"], preset["m"], preset["n"], preset["rw"])
    else:
        arr = spec.fn(
            rt, phie, vsh, preset["a"], preset["m"], preset["n"], preset["rw"], preset["rsh"]
        )
    finite = np.asarray(arr, dtype=float)
    mean = float(np.nanmean(finite)) if np.any(np.isfinite(finite)) else float("nan")
    return {"mean_sw": round(mean, 4), "method": method_id, "preset": args.get("electrical_preset")}


def _run_eda(tool: str, ctx: dict[str, Any], args: dict[str, Any]) -> dict[str, Any]:
    curves = ctx["curves"]
    if tool == "curve_inventory":
        return explore.curve_inventory(curves, ctx["depth_m"])
    if tool == "depth_coverage":
        return explore.depth_coverage(curves, ctx["depth_m"], ctx.get("step_m", 0.5))
    if tool == "histogram_stats":
        return explore.histogram_stats(curves[args["curve"]])
    if tool == "crossplot_density_neutron":
        return explore.crossplot_density_neutron(curves["RHOB"], curves["NPHI"])
    if tool == "low_resistivity_scan":
        return explore.low_resistivity_scan(curves["RT"], ctx["depth_m"], ctx["phie"])
    if tool == "gr_baseline_check":
        return explore.gr_baseline_check(curves["GR"])
    if tool == "badhole_summary":
        return explore.badhole_summary(ctx["quality_map"])
    raise KeyError(tool)


def dispatch(
    plan: dict[str, Any], ctx: dict[str, Any], ledger: dict[str, Any], graph: MethodologyGraph
) -> list[str]:
    """Execute a validated plan: run each tool, write result+hash to the ledger, log graph nodes.

    Returns the list of ledger keys written. Invalid plans write nothing (caller treats the
    validate_plan issues as a MECHANICAL gate). The LLM produced no number here.
    """
    issues = validate_plan(plan)
    if issues:
        return []
    ledger.setdefault("tool_results", {})
    written: list[str] = []
    for call in plan["tool_calls"]:
        tool, args = call["tool"], call.get("args", {})
        if tool in METHOD_REGISTRY and METHOD_REGISTRY[tool].property == "sw":
            result = _run_sw_method(tool, ctx, args)
        elif tool in _EDA_TOOLS:
            result = _run_eda(tool, ctx, args)
        else:
            # Non-sw/eda families are not executed yet (DV2-7): record the skip so a selected
            # tool that produced no result is signaled in the ledger, never silently dropped.
            ledger.setdefault("run", {}).setdefault("tools_not_executed", []).append(tool)
            continue
        key = tool
        result_hash = _hash(result)
        ledger["tool_results"][key] = {"value": result, "result_hash": result_hash}
        graph.add(
            "tool_call",
            {
                "tool": tool,
                "args": args,
                "result_ledger_key": f"ledger:{key}",
                "result_hash": result_hash,
            },
        )
        written.append(key)
    return written
