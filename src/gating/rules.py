"""Confidence gating rules.

Tier from parameter provenance (firm/qualified/bracketed) + a soft abstention flag:
if net pay is dominated by a regional-default parameter, the report must say so.
Decision (b) — HARD abstention (refuse to emit) — is deferred to a product decision;
v1 emits with a loud warning rather than refusing.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from src.orchestrator.state import CONVERGED, DID_NOT_CONVERGE
from src.validators.objections import IRREDUCIBLE, MECHANICAL

VERSION = "0.1.0"

FIRM, QUALIFIED, BRACKETED = "firm", "qualified", "bracketed"


def confidence_tier(provenances: Iterable[str]) -> str:
    """Worst-case tier across provenances (core=firm, offset=qualified, else bracketed)."""
    provs = set(provenances)
    if "default" in provs:
        return BRACKETED
    if "offset" in provs:
        return QUALIFIED
    if provs == {"core"}:
        return FIRM
    return BRACKETED


_TIER_ORDER = (BRACKETED, QUALIFIED, FIRM)


def _downgrade(tier: str, levels: int) -> str:
    """Lower a confidence tier by ``levels`` steps, floored at 'bracketed'."""
    idx = max(0, _TIER_ORDER.index(tier) - levels)
    return _TIER_ORDER[idx]


def gate_decision(
    objections: list[Any],
    params: dict[str, Any],
    converged: bool,
) -> dict[str, Any]:
    """Tier + abstention verdict from a final objection set (shared by gating and finalize).

    One source of truth for the gate math: base tier from parameter provenances, one downgrade
    per irreducible objection (floored at bracketed), abstain when unresolved MECHANICAL
    objections remain on a non-converged run or when net-pay plausibility objected (identified
    by ``validator_id == "net_pay_plausibility"``). Deterministic — no LLM decides a gate.

    Args:
        objections: final Objection list (attribute access: validator_id/objection_type/detail).
        params: resolved ParamValues (provenance drives the base tier).
        converged: whether the run counts as converged (pass-0: correctable == 0;
            post-loop finalize: no non-irreducible objections remain).

    Returns:
        ``{convergence_status, confidence_tier, abstain, abstain_reasons}``.
    """
    status = CONVERGED if converged else DID_NOT_CONVERGE
    provs = {p.provenance for p in params.values()}
    base_tier = FIRM if "core" in provs else (QUALIFIED if "offset" in provs else BRACKETED)

    n_irreducible = sum(1 for o in objections if o.objection_type == IRREDUCIBLE)
    tier = _downgrade(base_tier, n_irreducible)

    n_mechanical = sum(1 for o in objections if o.objection_type == MECHANICAL)
    abstain_reasons: list[str] = []
    if status == DID_NOT_CONVERGE and n_mechanical > 0:
        abstain_reasons.append(f"{n_mechanical} unresolved MECHANICAL objection(s)")
    abstain_reasons += [o.detail for o in objections if o.validator_id == "net_pay_plausibility"]

    return {
        "convergence_status": status,
        "confidence_tier": tier,
        "abstain": bool(abstain_reasons),
        "abstain_reasons": abstain_reasons,
    }


def high_leverage_flag(dominant_parameter: str | None, params: dict[str, Any]) -> dict[str, Any]:
    """Flag (soft) when the net-pay-dominating parameter is only a regional default.

    Returns ``{warn, parameter, provenance, message}``. Decision (b) hard abstention
    is deferred; this is a loud warning, not a refusal.
    """
    if not dominant_parameter or dominant_parameter not in params:
        return {"warn": False}
    prov = getattr(params[dominant_parameter], "provenance", "default")
    if prov == "default":
        return {
            "warn": True,
            "parameter": dominant_parameter,
            "provenance": prov,
            "message": (
                f"Net pay is dominated by '{dominant_parameter}', which is a regional "
                f"DEFAULT (uncalibrated). This is the single largest uncertainty — the "
                f"result is bracketed, not a confident point estimate."
            ),
        }
    return {"warn": False, "parameter": dominant_parameter, "provenance": prov}
