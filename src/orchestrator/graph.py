"""Build the deterministic LangGraph state machine and the run_pipeline entry point."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from langgraph.graph import END, START, StateGraph

from src.io.loader import load_las
from src.orchestrator.stages import (
    compute,
    correct_stub,
    emit,
    gating,
    route_after_typify,
    typify,
    validate,
    zonate,
)
from src.orchestrator.state import PipelineState
from src.params.config_loader import (
    config_hash,
    larionov_variant,
    load_config,
    resolve_all,
)
from src.qc.gate import qc_gate

VERSION = "0.1.0"


def build_graph() -> Any:
    """Compile the deterministic pipeline graph.

    Stages: compute → validate → typify → [correct]* → gating → zonate → emit.
    """
    g: StateGraph = StateGraph(PipelineState)
    g.add_node("compute", compute)
    g.add_node("validate", validate)
    g.add_node("typify", typify)
    g.add_node("correct", correct_stub)
    g.add_node("gating", gating)
    g.add_node("zonate", zonate)
    g.add_node("emit", emit)

    g.add_edge(START, "compute")
    g.add_edge("compute", "validate")
    g.add_edge("validate", "typify")
    g.add_conditional_edges(
        "typify", route_after_typify, {"correct": "correct", "gating": "gating"}
    )
    g.add_edge("correct", "compute")
    g.add_edge("gating", "zonate")
    g.add_edge("zonate", "emit")
    g.add_edge("emit", END)
    return g.compile()


def run_pipeline(
    las_path: str,
    region: str = "paleozoic_kansas",
    out_dir: str = "outputs",
    config_path: str | None = None,
) -> dict[str, Any]:
    """Run the full deterministic pipeline on a LAS file and return the ledger dict.

    Load → QC gate → (LangGraph: compute→validate→correct-loop→gating→zonate→emit).
    Emits ``outputs/<uwi>_ledger.json`` and the Phase-3 cross-plot PNG; no prose report.
    """
    well = load_las(las_path)
    qc = qc_gate(well)
    config = load_config(config_path) if config_path else load_config()
    params = resolve_all(config, region, well.uwi)
    variant, degraded = larionov_variant(well.prov)

    initial: PipelineState = {
        "uwi": well.uwi or Path(las_path).stem,
        "out_dir": out_dir,
        "curves": qc.curves,
        "params": params,
        "variant": variant,
        "variant_degraded": degraded,
        "depth_m": well.depth_m,
        "step_m": well.step_m,
        "quality_map": qc.quality_map,
        "qc_edits": qc.edits,
        "cb_n": int(params["circuit_breaker_n"].value),
        "iteration": 0,
    }
    final = build_graph().invoke(initial)
    ledger = final["ledger"]
    ledger["run"]["config_hash_sha256"] = config_hash(config_path) if config_path else config_hash()
    return ledger
