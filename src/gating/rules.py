"""Confidence gating rules.

Tier from parameter provenance (firm/qualified/bracketed) + a soft abstention flag:
if net pay is dominated by a regional-default parameter, the report must say so.
Decision (b) — HARD abstention (refuse to emit) — is deferred to a product decision;
v1 emits with a loud warning rather than refusing.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

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
