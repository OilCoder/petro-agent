"""Deterministic pipeline stage functions (LangGraph nodes) + loop routing.

Phase 4: the ``correct`` node is a deterministic STUB (a no-op) — the real
LLM-driven correction is Phase 5. With the stub, a well carrying correctable
objections cannot reduce them, so the circuit breaker fires (DID_NOT_CONVERGE),
exactly exercising the termination logic.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from src.orchestrator.state import CONVERGED, DID_NOT_CONVERGE, PipelineState
from src.petrophysics.lithology import (
    estimate_matrix_density,
    estimate_rw,
    estimate_shale_points,
)
from src.petrophysics.netpay import apply_cutoffs
from src.petrophysics.phie import calc_phie
from src.petrophysics.sw import calc_sw
from src.petrophysics.vsh import (
    OLD_ROCKS,
    TERTIARY,
    calc_vsh,
    vsh_clavier,
    vsh_linear,
    vsh_steiber,
)
from src.validators.harness import run_validators
from src.validators.objections import IRREDUCIBLE, MECHANICAL
from src.validators.physical import net_pay_plausibility

VERSION = "0.1.0"


def _pv(state: PipelineState, key: str) -> float:
    return float(state["params"][key].value)


def _safe_mean(values: Any) -> float:
    """Mean over finite samples; NaN if the slice is empty or all-NaN."""
    arr = np.asarray(values, dtype=float)
    if arr.size == 0 or bool(np.all(np.isnan(arr))):
        return float("nan")
    return float(np.nanmean(arr))


def _vsh_by_method(
    method_id: str | None, gr: np.ndarray, gr_min: float, gr_max: float, variant: str
) -> np.ndarray:
    """Compute Vsh with the agent-selected method id (vetted functions only), default = variant.

    The LLM selects the ID; the number comes from the frozen function. Unknown/absent → the
    engine's Larionov variant (the safe default), so a missing choice never breaks the chain.
    """
    if method_id == "vsh_linear":
        return vsh_linear(gr, gr_min, gr_max)
    if method_id == "vsh_clavier":
        return vsh_clavier(gr, gr_min, gr_max)
    if method_id == "vsh_steiber":
        return vsh_steiber(gr, gr_min, gr_max)
    if method_id == "vsh_larionov_tertiary":
        return calc_vsh(gr, gr_min, gr_max, TERTIARY)
    if method_id == "vsh_larionov_old":
        return calc_vsh(gr, gr_min, gr_max, OLD_ROCKS)
    return calc_vsh(gr, gr_min, gr_max, variant)


def compute(state: PipelineState) -> dict[str, Any]:
    """Run the three core deterministic computations with data-driven lithology.

    Matrix density and the shale endpoints are derived from the curves (deterministic
    parameter selection) so PHIE is effective porosity of the rock actually logged; the
    regional defaults are the fallback when there is too little clean/shale rock.
    """
    curves = state["curves"]
    n = state["depth_m"].size
    nan = np.full(n, np.nan)
    rhob, nphi = curves.get("RHOB", nan), curves.get("NPHI", nan)
    rho_fl = _pv(state, "rho_fl")

    vsh = _vsh_by_method(
        state.get("methods", {}).get("vsh"),
        curves["GR"],
        _pv(state, "gr_min"),
        _pv(state, "gr_max"),
        state["variant"],
    )

    # Substep — deterministic parameter selection from the data (replaces dead compute agent)
    rho_ma, ma_dd = estimate_matrix_density(rhob, vsh, default=_pv(state, "rho_ma"))
    phi_sh_d, phi_sh_n, sh_dd = estimate_shale_points(
        rhob,
        nphi,
        vsh,
        rho_ma,
        rho_fl,
        _pv(state, "phi_sh_d"),
        _pv(state, "phi_sh_n"),
    )

    phie = calc_phie(
        rhob,
        nphi,
        rho_ma,
        rho_fl,
        _pv(state, "phie_max"),
        vsh=vsh,
        phi_sh_d=phi_sh_d,
        phi_sh_n=phi_sh_n,
    )
    a, m, n = _pv(state, "a"), _pv(state, "m"), _pv(state, "n")
    rw, rw_dd = estimate_rw(curves["RT"], phie, vsh, a, m, default=_pv(state, "Rw"))
    sw = calc_sw(curves["RT"], phie, a, m, n, rw)
    calibration = {
        "rho_ma": {"value": rho_ma, "data_driven": ma_dd, "regional_default": _pv(state, "rho_ma")},
        "phi_sh_d": {
            "value": phi_sh_d,
            "data_driven": sh_dd,
            "regional_default": _pv(state, "phi_sh_d"),
        },
        "phi_sh_n": {
            "value": phi_sh_n,
            "data_driven": sh_dd,
            "regional_default": _pv(state, "phi_sh_n"),
        },
        "Rw": {"value": rw, "data_driven": rw_dd, "regional_default": _pv(state, "Rw")},
        "vsh_method": {
            "value": state.get("methods", {}).get("vsh") or f"vsh_larionov_{state['variant']}",
            "chosen_by_model": bool(state.get("methods", {}).get("vsh")),
        },
    }
    return {"vsh": vsh, "phie": phie, "sw": sw, "calibration": calibration}


def validate(state: PipelineState) -> dict[str, Any]:
    """Run the fixed validator harness."""
    rho_ma_used = state.get("calibration", {}).get("rho_ma", {}).get("value", _pv(state, "rho_ma"))
    objs = run_validators(
        state["vsh"],
        state["phie"],
        state["sw"],
        state["curves"],
        phie_max=_pv(state, "phie_max"),
        rho_ma=rho_ma_used,
        rt_floor=_pv(state, "rt_hydrocarbon_floor"),
        out_dir=state["out_dir"],
        uwi=state["uwi"],
    )
    return {"objections": objs}


def typify(state: PipelineState) -> dict[str, Any]:
    """Count correctable objections (mechanical + support; irreducible excluded)."""
    correctable = sum(1 for o in state["objections"] if o.objection_type != IRREDUCIBLE)
    return {"correctable": correctable}


def correct_stub(state: PipelineState) -> dict[str, Any]:
    """Phase-4 deterministic stub: records the attempt, does not fix (LLM = Phase 5)."""
    return {
        "iteration": state.get("iteration", 0) + 1,
        "prev_correctable": state["correctable"],
    }


def route_after_typify(state: PipelineState) -> str:
    """Loop routing / circuit breaker. Returns 'correct' or 'zonate'."""
    c = state["correctable"]
    if c == 0:
        return "zonate"  # converged: nothing correctable left
    if state.get("iteration", 0) >= state["cb_n"]:
        return "zonate"  # circuit breaker: max iterations
    prev = state.get("prev_correctable")
    if prev is not None and c >= prev:
        return "zonate"  # circuit breaker: correctable count did not decrease
    return "correct"


_TIER_ORDER = ("bracketed", "qualified", "firm")


def _downgrade(tier: str, levels: int) -> str:
    """Lower a confidence tier by ``levels`` steps, floored at 'bracketed'."""
    idx = max(0, _TIER_ORDER.index(tier) - levels)
    return _TIER_ORDER[idx]


def gating(state: PipelineState) -> dict[str, Any]:
    """Set convergence status, confidence tier, and the emission/abstention gate.

    Runs after ``zonate`` so it can judge net-pay plausibility. The tier is downgraded
    one step per irreducible objection (floored at bracketed); the run abstains when
    unresolved MECHANICAL objections remain or the net pay is physically implausible —
    the report then states an explicit abstention rather than a confident estimate.
    """
    status = CONVERGED if state["correctable"] == 0 else DID_NOT_CONVERGE
    provs = {p.provenance for p in state["params"].values()}
    base_tier = "firm" if "core" in provs else ("qualified" if "offset" in provs else "bracketed")

    summary = state.get("summary", {})
    plausibility = net_pay_plausibility(
        state.get("net_pay_total_m", 0.0),
        float(summary.get("gross_m", 0.0)),
        float(summary.get("avg_phie", float("nan"))),
    )
    objections = list(state.get("objections", [])) + plausibility

    n_irreducible = sum(1 for o in objections if o.objection_type == IRREDUCIBLE)
    tier = _downgrade(base_tier, n_irreducible)

    n_mechanical = sum(1 for o in objections if o.objection_type == MECHANICAL)
    abstain_reasons: list[str] = []
    if status == DID_NOT_CONVERGE and n_mechanical > 0:
        abstain_reasons.append(f"{n_mechanical} unresolved MECHANICAL objection(s)")
    abstain_reasons += [o.detail for o in plausibility]

    return {
        "convergence_status": status,
        "confidence_tier": tier,
        "objections": objections,
        "abstain": bool(abstain_reasons),
        "abstain_reasons": abstain_reasons,
    }


def zonate(state: PipelineState) -> dict[str, Any]:
    """Delineate contiguous net-pay zones, their thickness, and per-zone averages."""
    vsh, phie, sw = state["vsh"], state["phie"], state["sw"]
    flag = apply_cutoffs(
        vsh,
        phie,
        sw,
        _pv(state, "vsh_cutoff"),
        _pv(state, "phie_cutoff"),
        _pv(state, "sw_cutoff"),
    )
    depth = state["depth_m"]
    step = state["step_m"]
    zones: list[dict[str, Any]] = []
    i = 0
    n = flag.size
    while i < n:
        if flag[i]:
            j = i
            while j < n and flag[j]:
                j += 1
            zones.append(
                {
                    "top_m": float(depth[i]),
                    "base_m": float(depth[j - 1]),
                    "net_pay_m": float((j - i) * step),
                    "avg_phie": _safe_mean(phie[i:j]),
                    "avg_sw": _safe_mean(sw[i:j]),
                    "avg_vsh": _safe_mean(vsh[i:j]),
                }
            )
            i = j
        else:
            i += 1
    total = float(sum(z["net_pay_m"] for z in zones))
    summary = _well_summary(flag, depth, vsh, phie, sw, total, len(zones))
    return {"zones": zones, "net_pay_total_m": total, "summary": summary}


def _well_summary(
    flag: Any,
    depth: Any,
    vsh: Any,
    phie: Any,
    sw: Any,
    net_pay_total_m: float,
    n_zones_raw: int,
) -> dict[str, Any]:
    """Well-level aggregates over the net-pay interval (deterministic, ledger-bound)."""
    gross_m = float(depth[-1] - depth[0]) if np.asarray(depth).size > 1 else 0.0
    pay = np.asarray(flag, dtype=bool)
    return {
        "gross_m": gross_m,
        "net_pay_m": net_pay_total_m,
        "ntg": float(net_pay_total_m / gross_m) if gross_m > 0 else 0.0,
        "avg_phie": _safe_mean(np.asarray(phie)[pay]),
        "avg_sw": _safe_mean(np.asarray(sw)[pay]),
        "avg_vsh": _safe_mean(np.asarray(vsh)[pay]),
        "n_zones_raw": n_zones_raw,
    }


def _emit_parameters(state: PipelineState) -> dict[str, Any]:
    """Build the ledger parameter block, reflecting data-driven calibration overrides."""
    calibration = state.get("calibration", {})
    params: dict[str, Any] = {}
    for k, p in state["params"].items():
        cal = calibration.get(k)
        if cal and cal.get("data_driven"):
            params[k] = {"value": cal["value"], "unit": p.unit, "provenance": "data_driven"}
        else:
            params[k] = {"value": p.value, "unit": p.unit, "provenance": p.provenance}
    return params


def emit(state: PipelineState) -> dict[str, Any]:
    """Assemble and write the ledger JSON (no prose report — that is Phase 5)."""
    ledger = {
        "run": {
            "uwi": state["uwi"],
            "convergence_status": state["convergence_status"],
            "confidence_tier": state["confidence_tier"],
            "variant": state["variant"],
            "variant_degraded": state.get("variant_degraded", False),
            "abstain": state.get("abstain", False),
            "abstain_reasons": state.get("abstain_reasons", []),
            "curve_provenance": state.get("raw_mnemonics", {}),
            "well_metadata": state.get("well_metadata", {}),
            "environmental_corrections": "none_applied",
        },
        "parameters": _emit_parameters(state),
        "zones": state["zones"],
        "net_pay_total_m": state["net_pay_total_m"],
        "summary": state.get("summary", {}),
        "calibration": state.get("calibration", {}),
        "objections": [
            {"validator_id": o.validator_id, "type": o.objection_type, "detail": o.detail}
            for o in state["objections"]
        ],
        "edits": state.get("qc_edits", []),
    }
    out = Path(state["out_dir"]) / f"{state['uwi']}_ledger.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(ledger, indent=2))
    return {"ledger": ledger}
