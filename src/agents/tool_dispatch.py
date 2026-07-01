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
from src.petrophysics import permeability
from src.petrophysics.registry import (
    ELECTRICAL_PRESETS,
    MATRIX_PRESETS,
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
    """Return issues with a plan (empty = valid). Rejects only unknown/malformed tool ids;
    preset args are coerced to a vetted default at dispatch, never rejected here."""
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
    # Note: preset args are NOT rejected here — an unknown/placeholder preset is coerced to the
    # vetted default at dispatch time, so one sloppy arg never discards an otherwise good plan.
    return issues


def _run_sw_method(method_id: str, ctx: dict[str, Any], args: dict[str, Any]) -> dict[str, Any]:
    spec = METHOD_REGISTRY[method_id]
    # Unknown/absent/placeholder preset → vetted default (robust to sloppy LLM args), SIGNALED:
    # preset_defaulted tells the report a base-by-default apart from a base the agent chose.
    requested = args.get("electrical_preset")
    preset_defaulted = requested not in ELECTRICAL_PRESETS
    eff_preset = "carbonate_default" if preset_defaulted else str(requested)
    preset = ELECTRICAL_PRESETS[eff_preset]
    rt, phie, vsh = ctx["curves"]["RT"], ctx["phie"], ctx["vsh"]
    if method_id == "sw_archie":
        arr = spec.fn(rt, phie, preset["a"], preset["m"], preset["n"], preset["rw"])
    else:
        arr = spec.fn(
            rt, phie, vsh, preset["a"], preset["m"], preset["n"], preset["rw"], preset["rsh"]
        )
    finite = np.asarray(arr, dtype=float)
    mean = float(np.nanmean(finite)) if np.any(np.isfinite(finite)) else float("nan")
    return {
        "mean_sw": round(mean, 4),
        "method": method_id,
        "preset": eff_preset,
        "preset_defaulted": preset_defaulted,
    }


def _mean(arr: Any) -> float:
    finite = np.asarray(arr, dtype=float)
    return round(float(np.nanmean(finite)), 4) if np.any(np.isfinite(finite)) else float("nan")


def _pv(ledger: dict[str, Any], key: str, default: float) -> float:
    """Read a parameter value from the ledger (the engine's data-driven/default value)."""
    p = ledger.get("parameters", {}).get(key)
    if isinstance(p, dict) and "value" in p:
        return float(p["value"])
    return default


def _run_vsh_method(
    method_id: str, ctx: dict[str, Any], ledger: dict[str, Any], args: dict[str, Any]
) -> dict[str, Any]:
    spec = METHOD_REGISTRY[method_id]
    curves = ctx["curves"]
    rho_ma, rho_fl = _pv(ledger, "rho_ma", 2.71), _pv(ledger, "rho_fl", 1.0)
    if method_id == "vsh_neutron_density":  # non-GR clay indicator: different signature
        arr = spec.fn(
            curves["NPHI"], curves["RHOB"], rho_ma, rho_fl,
            _pv(ledger, "phi_sh_n", 0.35), _pv(ledger, "phi_sh_d", 0.10),
        )
    elif method_id == "vsh_multimineral":  # 2-mineral volumetric solve
        arr = spec.fn(curves["RHOB"], curves["NPHI"], rho_ma, rho_fl)
    else:
        gmin, gmax = _pv(ledger, "gr_min", 20.0), _pv(ledger, "gr_max", 120.0)
        arr = spec.fn(curves["GR"], gmin, gmax, **spec.fixed_kwargs)
    return {"mean_vsh": _mean(arr), "method": method_id}


def _run_porosity_method(
    method_id: str, ctx: dict[str, Any], ledger: dict[str, Any], args: dict[str, Any]
) -> dict[str, Any]:
    spec = METHOD_REGISTRY[method_id]
    curves = ctx["curves"]
    phie_max = _pv(ledger, "phie_max", 0.45)
    eff_preset: str | None = None
    preset_defaulted = False
    if method_id == "phie_density_neutron":
        arr = spec.fn(
            curves["RHOB"],
            curves["NPHI"],
            _pv(ledger, "rho_ma", 2.71),
            _pv(ledger, "rho_fl", 1.0),
            phie_max=phie_max,
            vsh=ctx.get("vsh"),
            phi_sh_d=_pv(ledger, "phi_sh_d", 0.0),
            phi_sh_n=_pv(ledger, "phi_sh_n", 0.0),
        )
    elif method_id == "phi_density":
        arr = spec.fn(
            curves["RHOB"], _pv(ledger, "rho_ma", 2.71), _pv(ledger, "rho_fl", 1.0), phie_max
        )
    elif method_id == "phi_neutron":
        arr = spec.fn(curves["NPHI"], phie_max)
    else:  # sonic preset: matrix/fluid transit times, vetted (default SIGNALED), never the LLM
        requested = args.get("matrix_preset")
        preset_defaulted = requested not in MATRIX_PRESETS
        matrix_key = "limestone" if preset_defaulted else str(requested)
        eff_preset = matrix_key
        preset = MATRIX_PRESETS[matrix_key]
        if method_id == "phi_sonic_wyllie":
            arr = spec.fn(curves["DT"], preset["dt_matrix"], preset["dt_fluid"], phie_max)
        else:  # phi_sonic_rhg(dt, dt_matrix, c=0.67, phie_max)
            arr = spec.fn(curves["DT"], preset["dt_matrix"], phie_max=phie_max)
    return {
        "mean_phi": _mean(arr),
        "method": method_id,
        "preset": eff_preset,
        "preset_defaulted": preset_defaulted,
    }


def _run_permeability_method(
    method_id: str, ctx: dict[str, Any], args: dict[str, Any]
) -> dict[str, Any]:
    # Sw is used as the irreducible-Sw proxy (no core); the result carries the uncalibrated flag.
    spec = METHOD_REGISTRY[method_id]
    arr = spec.fn(ctx["phie"], ctx["sw"])
    return {"mean_k_md": _mean(arr), "method": method_id, "calibrated": False}


def _run_rock_quality_method(
    method_id: str, ctx: dict[str, Any], args: dict[str, Any]
) -> dict[str, Any]:
    # Built on an uncalibrated Timur permeability, so it inherits the uncalibrated flag.
    spec = METHOD_REGISTRY[method_id]
    k = permeability.perm_timur(ctx["phie"], ctx["sw"])
    arr = spec.fn(k, ctx["phie"])
    return {"mean_value": _mean(arr), "index": method_id, "calibrated": False}


def _run_facies_method(method_id: str, ctx: dict[str, Any], args: dict[str, Any]) -> dict[str, Any]:
    curves = ctx["curves"]
    cols = []
    for name in ("GR", "RHOB", "NPHI"):
        if name in curves:
            cols.append(np.asarray(curves[name], dtype=float))
    if "RT" in curves:
        cols.append(np.log10(np.clip(np.asarray(curves["RT"], dtype=float), 1e-6, None)))
    feats = np.column_stack(cols)
    n_facies = int(args.get("n_facies", 4))
    summary = METHOD_REGISTRY[method_id].fn(feats, n_facies=n_facies)
    return {**summary, "method": method_id}


def _run_lithology_method(
    method_id: str, ctx: dict[str, Any], args: dict[str, Any]
) -> dict[str, Any]:
    # Numeric value from the golden-tested EDA crossplot (the registry fn is the figure/validator
    # twin); the agent's lithology call yields the nearest-lithology call, not a fabricated number.
    cp = explore.crossplot_density_neutron(ctx["curves"]["RHOB"], ctx["curves"]["NPHI"])
    return {"nearest_litho": cp.get("nearest"), "method": method_id}


def _run_derived_method(
    method_id: str, ctx: dict[str, Any], args: dict[str, Any]
) -> dict[str, Any]:
    # Derived volumetrics over the computed PHIE/Sw (deterministic arithmetic, not a new equation).
    spec = METHOD_REGISTRY[method_id]
    arr = spec.fn(ctx["phie"], ctx["sw"])
    return {"mean_bvw": _mean(arr), "method": method_id}


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
        return explore.low_resistivity_scan(curves["RT"], ctx["depth_m"])
    if tool == "gr_baseline_check":
        return explore.gr_baseline_check(curves["GR"])
    if tool == "badhole_summary":
        return explore.badhole_summary(ctx["quality_map"])
    raise KeyError(tool)


def _execute(
    tool: str, ctx: dict[str, Any], ledger: dict[str, Any], args: dict[str, Any]
) -> dict[str, Any] | None:
    """Run one whitelisted tool, routing by registry property. None = not executable."""
    spec = METHOD_REGISTRY.get(tool)
    if spec is None:
        return _run_eda(tool, ctx, args) if tool in _EDA_TOOLS else None
    runners = {
        "sw": lambda: _run_sw_method(tool, ctx, args),
        "vsh": lambda: _run_vsh_method(tool, ctx, ledger, args),
        "porosity": lambda: _run_porosity_method(tool, ctx, ledger, args),
        "lithology": lambda: _run_lithology_method(tool, ctx, args),
        "permeability": lambda: _run_permeability_method(tool, ctx, args),
        "rock_quality": lambda: _run_rock_quality_method(tool, ctx, args),
        "facies": lambda: _run_facies_method(tool, ctx, args),
        "derived": lambda: _run_derived_method(tool, ctx, args),
    }
    runner = runners.get(spec.property)
    return runner() if runner else None


def dispatch(
    plan: dict[str, Any], ctx: dict[str, Any], ledger: dict[str, Any], graph: MethodologyGraph
) -> list[str]:
    """Execute a validated plan: run each tool, write result+hash to the ledger, log graph nodes.

    Returns the list of ledger keys written. Invalid plans write nothing (caller treats the
    validate_plan issues as a MECHANICAL gate). The LLM produced no number here.
    """
    if validate_plan(plan):
        return []
    ledger.setdefault("tool_results", {})
    written: list[str] = []
    for call in plan["tool_calls"]:
        tool = call["tool"]
        args = call.get("args", {}) if isinstance(call.get("args"), dict) else {}
        result = _execute(tool, ctx, ledger, args)
        if result is None:
            # Not executable: record the skip so a selected tool is signaled, never dropped.
            ledger.setdefault("run", {}).setdefault("tools_not_executed", []).append(tool)
            continue
        result_hash = _hash(result)
        ledger["tool_results"][tool] = {"value": result, "result_hash": result_hash}
        graph.add(
            "tool_call",
            {
                "tool": tool,
                "args": args,
                "result_ledger_key": "ledger:tool_results",  # result lives under tool_results[tool]
                "result_hash": result_hash,
            },
        )
        written.append(tool)
    return written
