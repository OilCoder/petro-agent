"""Compute agent: SELECTS the region/variant/method from the vetted library.

It never computes a number — it parameterizes the deterministic engine. In v1 the
selection is fully determined by the PROV formation tag, so this is deterministic;
the LLM would only narrate the selection rationale, never alter the choice.
"""

from __future__ import annotations

from src.params.config_loader import larionov_variant

VERSION = "0.1.0"

_TERTIARY_REGIONS = {"tertiary"}


def select_method(prov: str, region_hint: str | None = None) -> dict[str, str]:
    """Select the petrophysical method/region from the PROV tag.

    Returns the chosen ``region``, Larionov ``variant``, and a short rationale.
    """
    variant, degraded = larionov_variant(prov)
    if region_hint:
        region = region_hint
    elif (prov or "").strip().lower() in _TERTIARY_REGIONS:
        region = "north_sea_jurassic"
    else:
        region = "paleozoic_kansas"
    rationale = (
        f"PROV='{prov or 'unknown'}' -> Larionov {variant} variant, region {region}"
        + (" (degraded: PROV absent/unrecognised, defaulted)" if degraded else "")
    )
    return {"region": region, "variant": variant, "rationale": rationale}
