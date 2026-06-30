"""Build the deterministic LangGraph state machine and the run_pipeline entry point."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from langgraph.graph import END, START, StateGraph

from src.agents.log_plot import generate_figures
from src.gating.rules import high_leverage_flag
from src.io.loader import load_las
from src.orchestrator.provenance import pin_versions
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
from src.uncertainty.montecarlo import propagate_net_pay
from src.uncertainty.sensitivity import sensitivity_net_pay

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
        "typify", route_after_typify, {"correct": "correct", "zonate": "zonate"}
    )
    g.add_edge("correct", "compute")
    # zonate runs before gating so the gate can judge net-pay plausibility
    g.add_edge("zonate", "gating")
    g.add_edge("gating", "emit")
    g.add_edge("emit", END)
    return g.compile()


def run_pipeline(
    las_path: str,
    region: str = "paleozoic_kansas",
    out_dir: str = "outputs",
    config_path: str | None = None,
    uncertainty: bool = True,
    return_ctx: bool = False,
    method_overrides: dict[str, str] | None = None,
) -> Any:
    """Run the full deterministic pipeline on a LAS file and return the ledger dict.

    Load → QC gate → (LangGraph: compute→validate→correct-loop→gating→zonate→emit).
    Emits ``outputs/<uwi>_ledger.json`` and the Phase-3 cross-plot PNG; no prose report.

    With ``return_ctx=True`` returns ``(ledger, ctx)`` where ctx carries the final arrays
    (curves/vsh/phie/sw/depth) for the v2 analyst (backward-compatible; default unchanged).
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
        "raw_mnemonics": well.raw_mnemonics,
        "well_metadata": well.metadata,
        "params": params,
        "variant": variant,
        "variant_degraded": degraded,
        "methods": method_overrides or {},
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
    ledger["run"]["versions"] = pin_versions()
    ledger["run"]["unmapped_curves"] = well.unmapped  # raw curves dropped at load (transparency)

    if uncertainty:
        cal = final.get("calibration", {})
        base = {k: params[k].value for k in ("a", "m", "n", "Rw")}
        if cal.get("Rw", {}).get("data_driven"):
            base["Rw"] = cal["Rw"]["value"]
        cutoffs = {k: params[k].value for k in ("vsh_cutoff", "phie_cutoff", "sw_cutoff")}
        vsh, phie, rt = final["vsh"], final["phie"], final["curves"]["RT"]
        step = float(well.step_m)
        mc = propagate_net_pay(vsh, phie, rt, base, cutoffs, step)
        sens = sensitivity_net_pay(vsh, phie, rt, base, cutoffs, step)
        warn = high_leverage_flag(sens["dominant_parameter"], params)
        ledger["uncertainty"] = {**mc, "sensitivity": sens, "high_leverage_warning": warn}
        ledger["run"]["net_pay_p10_p50_p90"] = [
            mc["net_pay_p10"],
            mc["net_pay_p50"],
            mc["net_pay_p90"],
        ]

    ledger["figures"] = generate_figures(
        ledger["run"]["uwi"],
        well.depth_m,
        final["curves"],
        final["vsh"],
        final["phie"],
        final["sw"],
        params,
        out_dir,
    )
    if return_ctx:
        ctx = {
            "curves": final["curves"],
            "vsh": final["vsh"],
            "phie": final["phie"],
            "sw": final["sw"],
            "depth_m": well.depth_m,
            "step_m": float(well.step_m),
            "quality_map": qc.quality_map,
            "params": params,  # resolved ParamValues, for the agentic loop's recompute steps
            "variant": variant,
        }
        return ledger, ctx
    return ledger
