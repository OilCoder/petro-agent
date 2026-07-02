"""Deterministic post-loop finalize: re-validate + gate the FINAL chain, then persist.

The analyst loop may recompute core properties (method choices, zone restriction); pass-0's
objections/tier/abstention then describe a chain that no longer exists. ``finalize_run`` is the
orchestrator's closing move — called by the driver AFTER ``run_analyst_loop`` — so the persisted
verdict (and the report's abstention banner) always cites the numbers the report actually shows.
In author mode it is the ONLY gate (pass-0 computed no interpretation). No LLM decides anything.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.agents.log_plot import generate_figures, generate_uncertainty_figures
from src.gating.rules import gate_decision
from src.validators.harness import run_validators
from src.validators.objections import IRREDUCIBLE, Objection
from src.validators.physical import cross_tool_consistency, net_pay_plausibility

VERSION = "0.1.0"


def _json_fallback(o: Any) -> Any:
    """Serialize numpy scalars/arrays the loop may have left in the ledger; str() as last resort."""
    if hasattr(o, "item"):
        return o.item()
    if hasattr(o, "tolist"):
        return o.tolist()
    return str(o)


def persist_ledger(ledger: dict[str, Any], out_dir: str | None) -> None:
    """Write the ledger JSON to ``<out_dir>/<uwi>_ledger.json`` (numpy-safe)."""
    if not out_dir:
        return
    uwi = ledger.get("run", {}).get("uwi", "well")
    path = Path(out_dir) / f"{uwi}_ledger.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ledger, indent=2, default=_json_fallback))


def _serialize(objs: list[Objection]) -> list[dict[str, str]]:
    return [
        {"validator_id": o.validator_id, "type": o.objection_type, "detail": o.detail} for o in objs
    ]


def revalidate_objections(ledger: dict[str, Any], ctx: dict[str, Any]) -> list[Objection]:
    """Re-run the deterministic checks on the CURRENT chain and REBUILD ``ledger["objections"]``.

    Validator harness on the ctx arrays (zone-masked if a zone was set) + net-pay plausibility on
    the current summary + cross-tool consistency. Rebuilt from scratch (idempotent). Shared by the
    analyst loop (mid-loop advisory surface — the agent decides WITH the objections in view) and
    ``finalize_run`` (the gate). Evidence only: no verdict is written here.
    """
    run = ledger.get("run", {})
    params = ctx["params"]
    rho_ma_used = (
        ledger.get("calibration", {}).get("rho_ma", {}).get("value", float(params["rho_ma"].value))
    )
    objections = run_validators(
        ctx["vsh"],
        ctx["phie"],
        ctx["sw"],
        ctx["curves"],
        phie_max=float(params["phie_max"].value),
        rho_ma=rho_ma_used,
        rt_floor=float(params["rt_hydrocarbon_floor"].value),
        out_dir=ctx.get("out_dir") or "outputs",
        uwi=run.get("uwi", "well"),
    )
    summary = ledger.get("summary", {})
    objections += net_pay_plausibility(
        float(ledger.get("net_pay_total_m", 0.0)),
        float(summary.get("gross_m", 0.0)),
        float(summary.get("avg_phie", float("nan"))),
    )
    objections += cross_tool_consistency(ledger)
    ledger["objections"] = _serialize(objections)
    return objections


def finalize_run(ledger: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    """Re-validate and gate the FINAL chain, regenerate figures, persist. Deterministic.

    Rebuilds ``ledger["objections"]`` via ``revalidate_objections`` (idempotent), then writes the
    gate verdict (``run.convergence_status/confidence_tier/abstain/abstain_reasons``) via the same
    ``gate_decision`` the pass-0 gate uses. Post-loop there is no correction loop, so ``converged``
    means "no non-irreducible objection remains".

    Returns the mutated ledger.
    """
    run = ledger.setdefault("run", {})
    out_dir = ctx.get("out_dir")

    # ----------------------------------------
    # Step 1 — Incomplete-chain guard (missing required curves defeat even the re-close)
    # ----------------------------------------
    if ctx.get("vsh") is None or ctx.get("phie") is None or ctx.get("sw") is None:
        run["convergence_status"] = "DID_NOT_CONVERGE"
        run["confidence_tier"] = "bracketed"
        run["abstain"] = True
        run["abstain_reasons"] = ["core interpretation incomplete (missing required curves)"]
        persist_ledger(ledger, out_dir)
        return ledger

    # ----------------------------------------
    # Step 2 — Rebuild objections from the FINAL chain (harness + plausibility + cross-tool)
    # ----------------------------------------
    objections = revalidate_objections(ledger, ctx)

    # ----------------------------------------
    # Step 3 — Gate verdict on the final objection set (shared gate math)
    # ----------------------------------------
    converged = not any(o.objection_type != IRREDUCIBLE for o in objections)
    run.update(gate_decision(objections, ctx["params"], converged))

    # ----------------------------------------
    # Step 4 — Figures from the FINAL arrays (+ human-only uncertainty charts)
    # ----------------------------------------
    if out_dir:
        ledger["figures"] = generate_figures(
            run.get("uwi", "well"),
            ctx["depth_m"],
            ctx["curves"],
            ctx["vsh"],
            ctx["phie"],
            ctx["sw"],
            ctx["params"],
            out_dir,
        )
        generate_uncertainty_figures(ledger, out_dir)

    # ----------------------------------------
    # Step 5 — Persist the finalized ledger (the artifact must tell the whole story)
    # ----------------------------------------
    persist_ledger(ledger, out_dir)
    return ledger
