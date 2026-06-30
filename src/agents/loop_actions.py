"""Action frontier for the agentic loop: physics-valid next steps + recompute invalidation.

The orchestrator owns WHICH actions are valid at each step (the agent only picks one). Physics is
not a choice: ``available_actions`` enforces the dependency chain (PHIE needs Vsh, Sw needs PHIE,
…). Recompute is allowed — when a property is (re)computed, ``invalidate_downstream`` marks its
dependents stale so they must be recomputed for their sections to stay consistent.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from src.agents.tool_dispatch import (
    _hash,
    _run_facies_method,
    _run_lithology_method,
    _run_permeability_method,
    _run_rock_quality_method,
)
from src.eda import explore
from src.gating.rules import high_leverage_flag
from src.orchestrator.stages import zonate
from src.orchestrator.steps import phie_step, sw_step, vsh_step
from src.petrophysics.phie import porosity_method_comparison
from src.petrophysics.vsh import vsh_method_comparison
from src.uncertainty.montecarlo import propagate_net_pay
from src.uncertainty.sensitivity import sensitivity_net_pay

# Property produced by each compute action.
PRODUCES: dict[str, str] = {
    "compute_vsh": "vsh",
    "compute_phie": "phie",
    "compute_sw": "sw",
    "apply_cutoffs": "netpay",
    "run_uncertainty": "uncertainty",
    "permeability": "permeability",
    "rock_quality": "rock_quality",
    "electrofacies": "electrofacies",
    "lithology": "lithology",
}

# Compute action -> (prerequisite properties that must be VALID, required curves present).
_REQUIRES: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "compute_vsh": ((), ("GR",)),
    "compute_phie": (("vsh",), ("RHOB", "NPHI")),
    "compute_sw": (("phie",), ("RT",)),
    "apply_cutoffs": (("sw",), ()),
    "run_uncertainty": (("netpay",), ()),
    "permeability": (("phie", "sw"), ()),
    "rock_quality": (("phie", "sw"), ()),
    "electrofacies": ((), ("GR", "RHOB", "NPHI")),
    "lithology": ((), ("RHOB", "NPHI")),
}

# Dependency graph (property -> the properties it directly depends on), for recompute invalidation.
DEPENDENCIES: dict[str, tuple[str, ...]] = {
    "phie": ("vsh",),
    "sw": ("phie",),
    "netpay": ("sw",),
    "uncertainty": ("netpay",),
    "permeability": ("phie", "sw"),
    "rock_quality": ("phie", "sw"),
}

# Observation actions (read-only): the property/curve they need to be meaningful.
_OBSERVE_NEEDS: dict[str, tuple[str, ...]] = {
    "zone_stats": ("netpay",),
    "percentiles": (),  # target chosen at call time (a present curve or computed property)
    "value_at": (),
    "extremes": (),
    "histogram": (),
    "crossplot": ("__curves__:RHOB,NPHI",),
    "low_res_scan": ("__curves__:RT",),
}


_OPTIONAL_ACTIONS = ("permeability", "rock_quality", "electrofacies", "lithology")


def available_actions(
    valid: set[str], curves: set[str], done_optionals: frozenset[str] = frozenset()
) -> list[str]:
    """Return the action ids valid right now (compute + observation + FINISH).

    Args:
        valid: properties already computed AND not stale (e.g. {"vsh", "phie"}).
        curves: canonical curves present in the well.
        done_optionals: optional actions already added (excluded — adding them again is a no-op;
            only core properties are meaningfully recomputable).

    Returns:
        Sorted-by-category list of available action ids; always includes ``finish``.
    """
    actions: list[str] = []
    for action, (deps, need_curves) in _REQUIRES.items():
        if action in done_optionals:
            continue
        if all(d in valid for d in deps) and all(c in curves for c in need_curves):
            actions.append(action)
    # observation actions
    for obs, needs in _OBSERVE_NEEDS.items():
        ok = True
        for need in needs:
            if need.startswith("__curves__:"):
                ok = ok and all(c in curves for c in need.split(":", 1)[1].split(","))
            else:
                ok = ok and need in valid
        if ok:
            actions.append(obs)
    actions.append("finish")
    return actions


def invalidate_downstream(valid: set[str], prop: str) -> set[str]:
    """Return ``valid`` with every (transitive) dependent of ``prop`` removed (recompute staleness).

    Recomputing ``prop`` makes everything that depends on it stale until recomputed. The recomputed
    property itself stays valid; its transitive dependents drop out.
    """
    stale: set[str] = set()
    frontier = [prop]
    while frontier:
        cur = frontier.pop()
        for dependent, deps in DEPENDENCIES.items():
            if cur in deps and dependent not in stale:
                stale.add(dependent)
                frontier.append(dependent)
    return set(valid) - stale


# ----------------------------------------
# Execution — each step runs ONE vetted primitive and updates ctx/ledger (the LLM computes nothing)
# ----------------------------------------

_LOOP_PARAM_KEYS = ("rho_fl", "rho_ma", "phie_max", "phi_sh_d", "phi_sh_n", "a", "m", "n", "Rw")


def _pf(ctx: dict[str, Any]) -> dict[str, float]:
    p = ctx["params"]
    return {k: float(p[k].value) for k in _LOOP_PARAM_KEYS}


def _mean(arr: Any) -> float:
    a = np.asarray(arr, dtype=float)
    return round(float(np.nanmean(a)), 4) if np.any(np.isfinite(a)) else float("nan")


def _exec_vsh(ctx, ledger, method, args, valid):  # noqa: ANN001
    p = ctx["params"]
    gmin, gmax = float(p["gr_min"].value), float(p["gr_max"].value)
    vsh, cal = vsh_step(ctx["curves"], gmin, gmax, ctx["variant"], method)
    ctx["vsh"] = vsh
    ledger.setdefault("calibration", {}).update(cal)
    ledger["vsh_comparison"] = {
        "methods": vsh_method_comparison(ctx["curves"]["GR"], gmin, gmax),
        "selected": cal["vsh_method"]["value"],
    }
    nv = invalidate_downstream(valid, "vsh")
    nv.add("vsh")
    return {"property": "vsh", "method": cal["vsh_method"]["value"], "mean_vsh": _mean(vsh)}, nv


def _exec_phie(ctx, ledger, method, args, valid):  # noqa: ANN001
    phie, cal = phie_step(ctx["curves"], ctx["vsh"], _pf(ctx), method)
    ctx["phie"] = phie
    ledger.setdefault("calibration", {}).update(cal)
    pm = porosity_method_comparison(
        ctx["curves"].get("RHOB"),
        ctx["curves"].get("NPHI"),
        _pf(ctx)["rho_ma"],
        _pf(ctx)["rho_fl"],
        _pf(ctx)["phie_max"],
        vsh=ctx["vsh"],
        phi_sh_d=_pf(ctx)["phi_sh_d"],
        phi_sh_n=_pf(ctx)["phi_sh_n"],
    )
    ledger["porosity_comparison"] = {"methods": pm, "selected": method or "phie_density_neutron"}
    nv = invalidate_downstream(valid, "phie")
    nv.add("phie")
    return {
        "property": "phie",
        "method": method or "phie_density_neutron",
        "mean_phie": _mean(phie),
    }, nv


def _exec_sw(ctx, ledger, method, args, valid):  # noqa: ANN001
    sw, cal = sw_step(ctx["curves"], ctx["phie"], ctx["vsh"], _pf(ctx), method)
    ctx["sw"] = sw
    ledger.setdefault("calibration", {}).update(cal)
    pf = _pf(ctx)
    ledger["sw_summary"] = {
        "method": method or "sw_archie",
        "mean_sw": _mean(sw),
        "a": pf["a"],
        "m": pf["m"],
        "n": pf["n"],
        "rw": cal["Rw"]["value"],
    }
    nv = invalidate_downstream(valid, "sw")
    nv.add("sw")
    return {"property": "sw", "method": method or "sw_archie", "mean_sw": _mean(sw)}, nv


def _exec_cutoffs(ctx, ledger, method, args, valid):  # noqa: ANN001
    state = {
        "vsh": ctx["vsh"],
        "phie": ctx["phie"],
        "sw": ctx["sw"],
        "depth_m": ctx["depth_m"],
        "step_m": ctx["step_m"],
        "params": ctx["params"],
    }
    z = zonate(state)
    ledger.update(z)
    nv = invalidate_downstream(valid, "netpay")
    nv.add("netpay")
    return {"property": "netpay", "net_pay_m": z["net_pay_total_m"], "n_zones": len(z["zones"])}, nv


def _exec_uncertainty(ctx, ledger, method, args, valid):  # noqa: ANN001
    pf = _pf(ctx)
    base = {k: pf[k] for k in ("a", "m", "n", "Rw")}
    cal = ledger.get("calibration", {})
    if cal.get("Rw", {}).get("data_driven"):
        base["Rw"] = cal["Rw"]["value"]
    cutoffs = {k: float(ctx["params"][k].value) for k in ("vsh_cutoff", "phie_cutoff", "sw_cutoff")}
    rt, step = ctx["curves"]["RT"], ctx["step_m"]
    mc = propagate_net_pay(ctx["vsh"], ctx["phie"], rt, base, cutoffs, step)
    sens = sensitivity_net_pay(ctx["vsh"], ctx["phie"], rt, base, cutoffs, step)
    warn = high_leverage_flag(sens["dominant_parameter"], ctx["params"])
    ledger["uncertainty"] = {**mc, "sensitivity": sens, "high_leverage_warning": warn}
    ledger["run"]["net_pay_p10_p50_p90"] = [mc["net_pay_p10"], mc["net_pay_p50"], mc["net_pay_p90"]]
    nv = set(valid)
    nv.add("uncertainty")
    return {
        "property": "uncertainty",
        "p50": mc["net_pay_p50"],
        "dominant": sens["dominant_parameter"],
    }, nv


_OPTIONAL_RUNNERS = {
    "permeability": _run_permeability_method,
    "rock_quality": _run_rock_quality_method,
    "electrofacies": _run_facies_method,
    "lithology": _run_lithology_method,
}
_OPTIONAL_DEFAULT_TOOL = {
    "permeability": "perm_timur",
    "rock_quality": "rqi",
    "electrofacies": "electrofacies",
    "lithology": "litho_nd_crossplot",
}


def _exec_optional(action, ctx, ledger, method, args, valid):  # noqa: ANN001
    tool = method or _OPTIONAL_DEFAULT_TOOL[action]
    result = _OPTIONAL_RUNNERS[action](tool, ctx, args)
    ledger.setdefault("tool_results", {})[tool] = {"value": result, "result_hash": _hash(result)}
    nv = set(valid)
    nv.add(action)
    return {"property": action, "tool": tool, "result": result}, nv


_COMPUTE_RUNNERS = {
    "compute_vsh": _exec_vsh,
    "compute_phie": _exec_phie,
    "compute_sw": _exec_sw,
    "apply_cutoffs": _exec_cutoffs,
    "run_uncertainty": _exec_uncertainty,
}


def execute_step(
    action: str,
    ctx: dict[str, Any],
    ledger: dict[str, Any],
    valid: set[str],
    method=None,
    args=None,
) -> tuple[dict[str, Any], set[str]]:
    """Execute ONE action (compute/observe), updating ctx+ledger, and return (summary, new_valid).

    Compute actions run a vetted primitive and update the valid-property set (with recompute
    invalidation). Observation actions are read-only and return summarized data (zone/distribution/
    point) — never raw arrays — leaving ``valid`` unchanged.
    """
    args = args or {}
    if action in _COMPUTE_RUNNERS:
        return _COMPUTE_RUNNERS[action](ctx, ledger, method, args, valid)
    if action in _OPTIONAL_RUNNERS:
        return _exec_optional(action, ctx, ledger, method, args, valid)
    return observe(action, ctx, ledger, method, args), set(valid)


def observe(
    action: str, ctx: dict[str, Any], ledger: dict[str, Any], target=None, args=None
) -> dict[str, Any]:  # noqa: ANN001
    """Read-only observation: zone summary / distribution / point value (never the raw array)."""
    args = args or {}
    tgt = target or args.get("target")
    if action == "zone_stats":
        zones = ledger.get("zones", [])[:15]
        return {"n_zones": len(ledger.get("zones", [])), "zones": zones}
    arr = _resolve_target(tgt, ctx)
    if action == "percentiles":
        finite = arr[np.isfinite(arr)] if arr is not None else np.array([])
        if finite.size == 0:
            return {"target": tgt, "note": "no finite data"}
        return {
            "target": tgt,
            "p10": round(float(np.percentile(finite, 10)), 4),
            "p50": round(float(np.percentile(finite, 50)), 4),
            "p90": round(float(np.percentile(finite, 90)), 4),
        }
    if action == "value_at":
        depth = float(args.get("depth", ctx["depth_m"][0]))
        idx = int(np.argmin(np.abs(ctx["depth_m"] - depth)))
        return {
            "target": tgt,
            "depth": round(float(ctx["depth_m"][idx]), 2),
            "value": (
                round(float(arr[idx]), 4) if arr is not None and np.isfinite(arr[idx]) else None
            ),
        }
    if action == "extremes":
        finite = arr[np.isfinite(arr)] if arr is not None else np.array([])
        if finite.size == 0:
            return {"target": tgt, "note": "no finite data"}
        return {
            "target": tgt,
            "min": round(float(finite.min()), 4),
            "max": round(float(finite.max()), 4),
        }
    if action == "histogram":
        return (
            explore.histogram_stats(ctx["curves"][tgt])
            if tgt in ctx["curves"]
            else {"note": "no curve"}
        )
    if action == "crossplot":
        return explore.crossplot_density_neutron(ctx["curves"]["RHOB"], ctx["curves"]["NPHI"])
    if action == "low_res_scan":
        return explore.low_resistivity_scan(ctx["curves"]["RT"], ctx["depth_m"], ctx["phie"])
    return {"note": f"unknown observation {action}"}


def _resolve_target(tgt, ctx):  # noqa: ANN001
    """Resolve a target name to an array: a present curve or a computed property (vsh/phie/sw)."""
    if tgt in ("vsh", "phie", "sw"):
        return ctx.get(tgt)
    if tgt in ctx["curves"]:
        return np.asarray(ctx["curves"][tgt], dtype=float)
    return None
