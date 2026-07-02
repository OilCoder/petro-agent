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


def finalize_run(ledger: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    """Re-validate and gate the FINAL chain, regenerate figures, persist. Deterministic.

    Rebuilds ``ledger["objections"]`` from scratch (validator harness + net-pay plausibility on
    the FINAL summary + cross-tool consistency) so a second call is idempotent, then writes the
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
    # Step 2 — Validator harness on the FINAL arrays (zone-masked curves if a zone was set)
    # ----------------------------------------
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
        out_dir=out_dir or "outputs",
        uwi=run.get("uwi", "well"),
    )

    # ----------------------------------------
    # Step 3 — Plausibility on the FINAL summary + cross-tool consistency (rebuilt, not appended)
    # ----------------------------------------
    summary = ledger.get("summary", {})
    objections += net_pay_plausibility(
        float(ledger.get("net_pay_total_m", 0.0)),
        float(summary.get("gross_m", 0.0)),
        float(summary.get("avg_phie", float("nan"))),
    )
    objections += cross_tool_consistency(ledger)
    ledger["objections"] = _serialize(objections)

    # ----------------------------------------
    # Step 4 — Gate verdict on the final objection set (shared gate math)
    # ----------------------------------------
    converged = not any(o.objection_type != IRREDUCIBLE for o in objections)
    run.update(gate_decision(objections, params, converged))

    # ----------------------------------------
    # Step 5 — Figures from the FINAL arrays (+ human-only uncertainty charts)
    # ----------------------------------------
    if out_dir:
        ledger["figures"] = generate_figures(
            run.get("uwi", "well"),
            ctx["depth_m"],
            ctx["curves"],
            ctx["vsh"],
            ctx["phie"],
            ctx["sw"],
            params,
            out_dir,
        )
        generate_uncertainty_figures(ledger, out_dir)

    # ----------------------------------------
    # Step 6 — Persist the finalized ledger (the artifact must tell the whole story)
    # ----------------------------------------
    persist_ledger(ledger, out_dir)
    return ledger
