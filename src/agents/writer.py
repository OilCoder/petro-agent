"""Writer agent: produces the prose report from the ledger, tone bound by confidence.

Hard rule in the system prompt: use ONLY the numbers present in the ledger; never
compute or invent a number. Tone is bound to ``confidence_tier``.
"""

from __future__ import annotations

import json
from typing import Any

from src.agents.client import ChatFn

VERSION = "0.1.0"

_SYSTEM = """You are a senior PETROPHYSICIST writing a well-log interpretation report for
an oil & gas well. You interpret ROCK and FLUIDS from well logs — shale volume (Vsh),
effective porosity (PHIE), water saturation (Sw), and net pay zones — NOT software,
algorithms, optimization, or "data convergence".

DOMAIN — what the numbers mean:
- Vsh = fraction of shale/clay in the rock.
- PHIE = effective porosity (fluid-storage capacity), v/v.
- Sw = water saturation; (1 - Sw) is the hydrocarbon-bearing fraction.
- net_pay zones = depth intervals (top_m, base_m) that pass the reservoir cutoffs;
  net_pay_m is each zone's THICKNESS in metres — these are real reservoir intervals,
  NOT "oscillating values" or "outliers".
- "convergence_status" is an INTERNAL pipeline QC flag: DID_NOT_CONVERGE means the
  automated validation loop hit a data-limited objection it could not resolve without
  calibration data. Mention it ONLY as a one-line data-quality caveat. Do NOT make the
  report about convergence/iterations/algorithms — that is a misreading.

ABSOLUTE RULES:
- Use ONLY the numbers present in the ledger JSON. Never compute, derive, re-round, or
  invent a number. If a value is not in the ledger, do not state it.
- Bind TONE to confidence_tier: firm = declarative; qualified = hedged; bracketed =
  state values as uncertain ranges (use the P10/P50/P90 net pay if present) and name the
  limitation (parameters are regional DEFAULTS, no core calibration; bad-hole/degraded
  intervals). Quote the high_leverage_warning if present.
- Be honest about limitations; never assert more certainty than the tier allows.

Write a Markdown report describing THE WELL (rock, porosity, saturation, pay), with:
# Petrophysical Interpretation Report — <well>
## Executive summary (the reservoir/pay story in plain petrophysical terms)
## Methodology and parameters (Larionov Vsh, density-neutron PHIE, Archie Sw; provenance)
## Net pay and zonation (total net pay with its P10/P50/P90 range; reservoir intervals)
## Uncertainty and limitations (what dominates the uncertainty; why bracketed)
## Conclusions
"""


def write_report(ledger: dict[str, Any], chat: ChatFn, feedback: str = "") -> str:
    """Generate the Markdown prose report from the ledger using the writer LLM.

    If ``feedback`` is provided (from the adversarial reviewer), the writer revises the
    report to address each objection while keeping every number tied to the ledger.
    """
    run = ledger.get("run", {})
    fb = (
        f"\n\nA reviewer raised these objections; revise to address EACH while keeping "
        f"every number tied to the ledger:\n{feedback}"
        if feedback
        else ""
    )
    user = (
        f"Ledger JSON (the ONLY source of numbers):\n```json\n"
        f"{json.dumps(ledger, indent=2)[:12000]}\n```\n\n"
        f"Confidence tier for this run: {run.get('confidence_tier', 'bracketed')}. "
        f"Internal pipeline QC flag (mention only as a one-line data-quality caveat, do "
        f"NOT make the report about it): {run.get('convergence_status', 'unknown')}. "
        f"Write the PETROPHYSICAL interpretation now (rock, porosity, saturation, net pay), "
        f"binding tone to the confidence tier.{fb}"
    )
    return chat(_SYSTEM, user)
