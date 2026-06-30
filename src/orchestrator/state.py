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
    raw_mnemonics: dict[str, str]
    well_metadata: dict[str, str]
    params: dict[str, Any]  # key -> ParamValue
    variant: str
    variant_degraded: bool
    methods: dict[str, Any]  # agent-selected method ids (e.g. {"vsh": "vsh_clavier"}); optional
    depth_m: Any
    step_m: float
    quality_map: Any
    qc_edits: list[dict[str, Any]]
    cb_n: int

    # computed
    vsh: Any
    phie: Any
    sw: Any
    calibration: dict[str, Any]
    objections: list[Any]
    correctable: int
    prev_correctable: int
    iteration: int
    convergence_status: str
    confidence_tier: str
    abstain: bool
    abstain_reasons: list[str]
    zones: list[dict[str, Any]]
    net_pay_total_m: float
    summary: dict[str, Any]
    ledger: dict[str, Any]
