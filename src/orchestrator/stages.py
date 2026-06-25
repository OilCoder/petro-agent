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
from src.petrophysics.netpay import apply_cutoffs
from src.petrophysics.phie import calc_phie
from src.petrophysics.sw import calc_sw
from src.petrophysics.vsh import calc_vsh
from src.validators.harness import run_validators
from src.validators.objections import IRREDUCIBLE

VERSION = "0.1.0"


def _pv(state: PipelineState, key: str) -> float:
    return float(state["params"][key].value)


def compute(state: PipelineState) -> dict[str, Any]:
    """Run the three core deterministic computations."""
    curves = state["curves"]
    n = state["depth_m"].size
    nan = np.full(n, np.nan)
    vsh = calc_vsh(curves["GR"], _pv(state, "gr_min"), _pv(state, "gr_max"), state["variant"])
    phie = calc_phie(
        curves.get("RHOB", nan), curves.get("NPHI", nan),
        _pv(state, "rho_ma"), _pv(state, "rho_fl"), _pv(state, "phie_max"),
    )
    sw = calc_sw(
        curves["RT"], phie, _pv(state, "a"), _pv(state, "m"), _pv(state, "n"), _pv(state, "Rw")
    )
    return {"vsh": vsh, "phie": phie, "sw": sw}


def validate(state: PipelineState) -> dict[str, Any]:
    """Run the fixed validator harness."""
    objs = run_validators(
        state["vsh"], state["phie"], state["sw"], state["curves"],
        phie_max=_pv(state, "phie_max"), rho_ma=_pv(state, "rho_ma"),
        rt_floor=_pv(state, "rt_hydrocarbon_floor"),
        out_dir=state["out_dir"], uwi=state["uwi"],
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
    """Loop routing / circuit breaker. Returns 'correct' or 'gating'."""
    c = state["correctable"]
    if c == 0:
        return "gating"  # converged: nothing correctable left
    if state.get("iteration", 0) >= state["cb_n"]:
        return "gating"  # circuit breaker: max iterations
    prev = state.get("prev_correctable")
    if prev is not None and c >= prev:
        return "gating"  # circuit breaker: correctable count did not decrease
    return "correct"


def gating(state: PipelineState) -> dict[str, Any]:
    """Set convergence status and a coarse confidence tier."""
    status = CONVERGED if state["correctable"] == 0 else DID_NOT_CONVERGE
    provs = {p.provenance for p in state["params"].values()}
    tier = "firm" if "core" in provs else ("qualified" if "offset" in provs else "bracketed")
    return {"convergence_status": status, "confidence_tier": tier}


def zonate(state: PipelineState) -> dict[str, Any]:
    """Delineate contiguous net-pay zones and their thickness."""
    flag = apply_cutoffs(
        state["vsh"], state["phie"], state["sw"],
        _pv(state, "vsh_cutoff"), _pv(state, "phie_cutoff"), _pv(state, "sw_cutoff"),
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
            zones.append({
                "top_m": float(depth[i]),
                "base_m": float(depth[j - 1]),
                "net_pay_m": float((j - i) * step),
            })
            i = j
        else:
            i += 1
    total = float(sum(z["net_pay_m"] for z in zones))
    return {"zones": zones, "net_pay_total_m": total}


def emit(state: PipelineState) -> dict[str, Any]:
    """Assemble and write the ledger JSON (no prose report — that is Phase 5)."""
    ledger = {
        "run": {
            "uwi": state["uwi"],
            "convergence_status": state["convergence_status"],
            "confidence_tier": state["confidence_tier"],
            "variant": state["variant"],
            "variant_degraded": state.get("variant_degraded", False),
        },
        "parameters": {
            k: {"value": p.value, "unit": p.unit, "provenance": p.provenance}
            for k, p in state["params"].items()
        },
        "zones": state["zones"],
        "net_pay_total_m": state["net_pay_total_m"],
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
