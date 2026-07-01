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
    _run_derived_method,
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
from src.uncertainty.montecarlo import build_method_alts, multi_seed_robustness, propagate_net_pay
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
    "derived_parameters": "derived",
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
    "derived_parameters": (("phie", "sw"), ()),
}

# Dependency graph (property -> the properties it directly depends on), for recompute invalidation.
DEPENDENCIES: dict[str, tuple[str, ...]] = {
    "phie": ("vsh",),
    "sw": ("phie",),
    "netpay": ("sw",),
    "uncertainty": ("netpay",),
    "permeability": ("phie", "sw"),
    "rock_quality": ("phie", "sw"),
    "derived": ("phie", "sw"),
}

# Observation actions (read-only): the property/curve they need to be meaningful.
_OBSERVE_NEEDS: dict[str, tuple[str, ...]] = {
    "zone_stats": ("netpay",),
    "depth_quality": ("__curves__:RHOB",),  # RHOB-by-depth profile to spot overburden/bad data
    "percentiles": (),  # target chosen at call time (a present curve or computed property)
    "value_at": (),
    "extremes": (),
    "histogram": (),
    "crossplot": ("__curves__:RHOB,NPHI",),
    "low_res_scan": ("__curves__:RT",),
}


def available_actions(valid: set[str], curves: set[str], vision: bool = False) -> list[str]:
    """Return the action ids valid right now (compute + observation + FINISH).

    Only PHYSICS gates the frontier (PHIE needs Vsh, …). Already-done optionals and same-method
    recomputes are STILL offered — picking one is a no-op the loop records as a wasted step (a
    measured competence signal), rather than hidden (which would mask the model's judgement).

    Args:
        valid: properties already computed AND not stale (e.g. {"vsh", "phie"}).
        curves: canonical curves present in the well.
        vision: offer ``examine_figures`` (a vision-capable model + figures present).

    Returns:
        List of available action ids; always includes ``finish``.
    """
    actions: list[str] = []
    for action, (deps, need_curves) in _REQUIRES.items():
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
    if vision:  # cloud ceiling track: read the figures qualitatively
        actions.append("examine_figures")
    # Zone-of-interest selection is always physics-valid (you can always restrict the interval).
    actions.append("set_zone_of_interest")
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


def _vsh_cmp(ctx: dict[str, Any], gmin: float, gmax: float) -> dict[str, float]:
    """Multi-method Vsh means for §13, including the non-GR neutron-density when RHOB+NPHI exist."""
    curves, pf = ctx["curves"], _pf(ctx)
    return vsh_method_comparison(
        curves["GR"],
        gmin,
        gmax,
        nphi=curves.get("NPHI"),
        rhob=curves.get("RHOB"),
        rho_ma=pf["rho_ma"],
        rho_fl=pf["rho_fl"],
        phi_sh_n=pf["phi_sh_n"],
        phi_sh_d=pf["phi_sh_d"],
    )


def _exec_vsh(ctx, ledger, method, args, valid):  # noqa: ANN001
    p = ctx["params"]
    gmin, gmax = float(p["gr_min"].value), float(p["gr_max"].value)
    vsh, cal = vsh_step(ctx["curves"], gmin, gmax, ctx["variant"], method, pf=_pf(ctx))
    ctx["vsh"] = vsh
    ledger.setdefault("calibration", {}).update(cal)
    ledger["vsh_comparison"] = {
        "methods": _vsh_cmp(ctx, gmin, gmax),
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
    ledger["porosity_comparison"] = {
        "methods": pm,
        "selected": method or "phie_density_neutron",
        "method_source": "agent" if method else "engine_default",
    }
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
        "method_source": "agent" if method else "engine_default",
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
    p = ctx["params"]
    cutoffs = {k: float(p[k].value) for k in ("vsh_cutoff", "phie_cutoff", "sw_cutoff")}
    rt, step = ctx["curves"]["RT"], ctx["step_m"]
    # net-pay MC now includes METHOD uncertainty (vetted Vsh/PHIE alternatives), not only parameters
    vsh_alts, phie_alts = build_method_alts(
        ctx["curves"],
        ctx["vsh"],
        ctx["phie"],
        float(p["gr_min"].value),
        float(p["gr_max"].value),
        pf["rho_ma"],
        pf["rho_fl"],
        pf["phie_max"],
        pf["phi_sh_d"],
        pf["phi_sh_n"],
    )
    mc = propagate_net_pay(
        ctx["vsh"], ctx["phie"], rt, base, cutoffs, step, vsh_alts=vsh_alts, phie_alts=phie_alts
    )
    sens = sensitivity_net_pay(ctx["vsh"], ctx["phie"], rt, base, cutoffs, step)
    warn = high_leverage_flag(sens["dominant_parameter"], ctx["params"])
    rob = multi_seed_robustness(ctx["vsh"], ctx["phie"], rt, base, cutoffs, step, n=200)
    ledger["uncertainty"] = {
        **mc,
        "sensitivity": sens,
        "high_leverage_warning": warn,
        "robustness": rob,
    }
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
    "derived_parameters": _run_derived_method,
}
_OPTIONAL_DEFAULT_TOOL = {
    "permeability": "perm_timur",
    "rock_quality": "rqi",
    "electrofacies": "electrofacies",
    "lithology": "litho_nd_crossplot",
    "derived_parameters": "bvw",
}


def _exec_optional(action, ctx, ledger, method, args, valid):  # noqa: ANN001
    requested = method
    tool = method or _OPTIONAL_DEFAULT_TOOL[action]
    coerced = False
    try:
        result = _OPTIONAL_RUNNERS[action](tool, ctx, args)
    except KeyError:  # hallucinated/unknown method -> coerce to the action's default
        tool = _OPTIONAL_DEFAULT_TOOL[action]
        result = _OPTIONAL_RUNNERS[action](tool, ctx, args)
        coerced = True
    entry = {"value": result, "result_hash": _hash(result)}
    # Signal base-by-default apart from base-by-choice: record when the engine picked the method
    # (agent gave none) or had to coerce a hallucinated one, so it never reads as the agent's pick.
    if requested is None or coerced:
        entry["method_source"] = "engine_default"
        entry["requested_method"] = requested
        ledger.setdefault("run", {}).setdefault("method_coerced", []).append(
            {"action": action, "requested": requested, "used": tool}
        )
    ledger.setdefault("tool_results", {})[tool] = entry
    nv = set(valid)
    nv.add(action)
    return {"property": action, "tool": tool, "result": result}, nv


def depth_quality_profile(curves: dict[str, Any], depth: Any, n_bins: int = 8) -> dict[str, Any]:
    """Binned RHOB-by-depth summary the agent may read (read-only, no interpretation).

    Returns per-bin depth range + median RHOB + fraction below 2.0 g/cc. Summarized, never the raw
    array. The numbers are surfaced as facts; what they imply about the interval is the analyst's.
    """
    depth_arr = np.asarray(depth, dtype=float)
    n = depth_arr.size
    rhob = np.asarray(curves.get("RHOB", np.full(n, np.nan)), dtype=float)
    edges = np.linspace(float(depth_arr.min()), float(depth_arr.max()), n_bins + 1)
    bins = []
    for i in range(n_bins):
        lo, hi = edges[i], edges[i + 1]
        sel = (depth_arr >= lo) & (depth_arr <= hi)
        rf = rhob[sel]
        rf = rf[np.isfinite(rf)]
        bins.append(
            {
                "top_m": round(float(lo), 0),
                "bottom_m": round(float(hi), 0),
                "rhob_p50": round(float(np.median(rf)), 3) if rf.size else None,
                "frac_rhob_below_2": round(float(np.mean(rf < 2.0)), 2) if rf.size else None,
            }
        )
    return {
        "bins": bins,
        "note": "rhob_p50 = median RHOB (g/cc) per depth bin; frac_rhob_below_2 = fraction of "
        "samples with RHOB < 2.0 g/cc in the bin.",
    }


def _exec_zone_of_interest(ctx, ledger, method, args, valid):  # noqa: ANN001
    """Restrict the analysis to a depth interval, then recompute the baseline over it.

    The agent chose the interval (analyst judgement); the engine masks curves outside it to NaN and
    deterministically recomputes vsh→phie→sw→net pay→uncertainty over the zone (the LLM computes
    nothing). Everything is invalidated then rebuilt, so all sections reflect the restricted rock.
    """
    depth = np.asarray(ctx["depth_m"], dtype=float)
    ctx.setdefault(
        "curves_full", {k: np.asarray(v, dtype=float).copy() for k, v in ctx["curves"].items()}
    )
    lo = float(args.get("top", depth.min()))
    hi = float(args.get("bottom", depth.max()))
    if lo > hi:
        lo, hi = hi, lo
    lo, hi = max(lo, float(depth.min())), min(hi, float(depth.max()))
    mask = (depth >= lo) & (depth <= hi)
    ctx["curves"] = {k: np.where(mask, v, np.nan) for k, v in ctx["curves_full"].items()}
    ctx["zoi"] = (lo, hi)
    ledger["zone_of_interest"] = {
        "top_m": round(lo, 1),
        "bottom_m": round(hi, 1),
        "n_samples": int(mask.sum()),
    }
    nv: set[str] = set()
    for runner in (_exec_vsh, _exec_phie, _exec_sw, _exec_cutoffs, _exec_uncertainty):
        _s, nv = runner(ctx, ledger, None, {}, nv)
    return {
        "property": "zone_of_interest",
        "top_m": round(lo, 1),
        "bottom_m": round(hi, 1),
        "n_samples": int(mask.sum()),
    }, nv


def seed_baseline_sections(ledger: dict[str, Any], ctx: dict[str, Any]) -> None:
    """Populate the [FIJO] Vsh/Porosity/Sw section keys from the pass-0 baseline.

    Those floor sections only got set when the agent RECOMPUTED a property (via _exec_*), so in free
    mode they rendered "Not computed" if the agent left the baseline as-is. Seed them from the
    baseline ctx (idempotent: only fills a key when absent, so a later agent recompute overrides).
    """
    curves = ctx["curves"]
    cal = ledger.setdefault("calibration", {})
    p = ctx["params"]
    if "GR" in curves and "vsh_comparison" not in ledger:
        gmin, gmax = float(p["gr_min"].value), float(p["gr_max"].value)
        # the registry key is vsh_larionov_old / _tertiary (NOT _old_rocks) — match it so the
        # report's [FIJO] Vsh section marks the selected method (was empty in free mode)
        default_sel = (
            "vsh_larionov_tertiary" if ctx["variant"] == "tertiary" else "vsh_larionov_old"
        )
        ledger["vsh_comparison"] = {
            "methods": _vsh_cmp(ctx, gmin, gmax),
            "selected": cal.get("vsh_method", {}).get("value", default_sel),
        }
    if {"RHOB", "NPHI"} <= set(curves) and "porosity_comparison" not in ledger:
        pf = _pf(ctx)
        ledger["porosity_comparison"] = {
            "methods": porosity_method_comparison(
                curves.get("RHOB"),
                curves.get("NPHI"),
                pf["rho_ma"],
                pf["rho_fl"],
                pf["phie_max"],
                vsh=ctx.get("vsh"),
                phi_sh_d=pf["phi_sh_d"],
                phi_sh_n=pf["phi_sh_n"],
            ),
            "selected": "phie_density_neutron",
        }
    if ctx.get("sw") is not None and "sw_summary" not in ledger:
        pf = _pf(ctx)
        ledger["sw_summary"] = {
            "method": "sw_archie",
            "mean_sw": _mean(ctx["sw"]),
            "a": pf["a"],
            "m": pf["m"],
            "n": pf["n"],
            "rw": cal.get("Rw", {}).get("value", pf["Rw"]),
        }


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
    if action == "set_zone_of_interest":
        return _exec_zone_of_interest(ctx, ledger, method, args, valid)
    if action in _COMPUTE_RUNNERS:
        return _COMPUTE_RUNNERS[action](ctx, ledger, method, args, valid)
    if action in _OPTIONAL_RUNNERS:
        return _exec_optional(action, ctx, ledger, method, args, valid)
    return observe(action, ctx, ledger, method, args), set(valid)


# Vision guardrail: a vision-capable model may READ figures qualitatively, never numbers off a plot.
_VISION_GUARDRAIL = (
    "You may LOOK at petrophysical log figures (composite log, Pickett plot, density-neutron "
    "crossplot). Report ONLY qualitative patterns that inform WHICH method or interval to choose: "
    "lithology trend, curve character, log quality/washouts, hydrocarbon cross-over shape, "
    "zonation boundaries. NEVER read, estimate, or state any NUMERIC value from a plot "
    "(no Rw, no porosity, no saturation) — the engine owns every number. Two or three sentences, "
    "qualitative only."
)


def _examine_figures(ctx: dict[str, Any]) -> dict[str, Any]:
    """Vision observation: a vision-capable model reads the figures QUALITATIVELY (never numbers).

    Offered only when ``ctx`` carries a ``vision_chat`` and ``figure_paths`` (the cloud ceiling
    track). The reading feeds the next decision as an observation; it authors no number.
    """
    vchat = ctx.get("vision_chat")
    paths = ctx.get("figure_paths") or []
    if vchat is None or not paths:
        return {"action": "examine_figures", "note": "no vision backend or figures available"}
    reading = vchat(
        _VISION_GUARDRAIL, "Describe these well-log figures qualitatively.", list(paths)
    )
    return {"action": "examine_figures", "qualitative_reading": str(reading).strip()}


def observe(
    action: str, ctx: dict[str, Any], ledger: dict[str, Any], target=None, args=None
) -> dict[str, Any]:  # noqa: ANN001
    """Read-only observation: zone summary / distribution / point value (never the raw array)."""
    args = args or {}
    tgt = target or args.get("target")
    if action == "zone_stats":
        zones = ledger.get("zones", [])[:15]
        return {"n_zones": len(ledger.get("zones", [])), "zones": zones}
    if action == "examine_figures":
        return _examine_figures(ctx)
    if action == "depth_quality":
        return depth_quality_profile(ctx.get("curves_full", ctx["curves"]), ctx["depth_m"])
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
    return _observe_eda(action, ctx, tgt)


def _observe_eda(action: str, ctx: dict[str, Any], tgt: Any) -> dict[str, Any]:
    """EDA curve observations (histogram / density-neutron crossplot / low-resistivity scan)."""
    if action == "histogram":
        return (
            explore.histogram_stats(ctx["curves"][tgt])
            if tgt in ctx["curves"]
            else {"note": "no curve"}
        )
    if action == "crossplot":
        return explore.crossplot_density_neutron(ctx["curves"]["RHOB"], ctx["curves"]["NPHI"])
    if action == "low_res_scan":
        return explore.low_resistivity_scan(ctx["curves"]["RT"], ctx["depth_m"])
    return {"note": f"unknown observation {action}"}


def _resolve_target(tgt, ctx):  # noqa: ANN001
    """Resolve a target name to an array: a present curve or a computed property (vsh/phie/sw)."""
    if tgt in ("vsh", "phie", "sw"):
        return ctx.get(tgt)
    if tgt in ctx["curves"]:
        return np.asarray(ctx["curves"][tgt], dtype=float)
    return None
