"""Pipeline state carried through the LangGraph state machine."""

from __future__ import annotations

from typing import Any, TypedDict

CONVERGED = "CONVERGED"
DID_NOT_CONVERGE = "DID_NOT_CONVERGE"


class PipelineState(TypedDict, total=False):
    """State threaded through the deterministic pipeline nodes."""

    # inputs (set before invoke)
    uwi: str
    out_dir: str
    curves: dict[str, Any]
    params: dict[str, Any]  # key -> ParamValue
    variant: str
    variant_degraded: bool
    depth_m: Any
    step_m: float
    quality_map: Any
    qc_edits: list[dict[str, Any]]
    cb_n: int

    # computed
    vsh: Any
    phie: Any
    sw: Any
    objections: list[Any]
    correctable: int
    prev_correctable: int
    iteration: int
    convergence_status: str
    confidence_tier: str
    zones: list[dict[str, Any]]
    net_pay_total_m: float
    ledger: dict[str, Any]
