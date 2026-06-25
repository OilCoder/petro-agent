"""Writer agent: produces the prose report from the ledger, tone bound by confidence.

Hard rule in the system prompt: use ONLY the numbers present in the ledger; never
compute or invent a number. Tone is bound to ``confidence_tier``.
"""

from __future__ import annotations

import json
from typing import Any

from src.agents.client import ChatFn

VERSION = "0.1.0"

_SYSTEM = """You are a petrophysical report writer producing a defensible WELL-LOG
INTERPRETATION report (shale volume Vsh, effective porosity PHIE, water saturation Sw,
net pay, zones). This is petroleum petrophysics, NOT software/optimization. The ledger's
"convergence_status" refers to the interpretation pipeline's validation loop terminating
(CONVERGED = all objections resolved; DID_NOT_CONVERGE = the circuit breaker stopped a
loop that could not resolve a data-limited objection) — it is NOT an optimizer.

ABSOLUTE RULES:
- Use ONLY the numbers present in the provided ledger JSON. Never compute, derive, round
  differently, or invent any number. If a value is not in the ledger, do not state it.
- Bind your TONE to the ledger's confidence_tier:
  * "firm"      -> declarative, confident statements.
  * "qualified" -> hedged statements ("approximately", "consistent with").
  * "bracketed" -> explicitly state the value as uncertain, give the range if present,
                   and name the limitation (e.g. parameters are regional defaults, no core).
- Be honest about limitations. Never assert more certainty than the tier allows.

Output a Markdown report with these sections:
# Petrophysical Report — <well>
## Executive summary
## Parameters and provenance
## Zonation and net pay
## Conclusions
## Limitations and confidence statement
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
        f"Convergence: {run.get('convergence_status', 'unknown')}. "
        f"Write the report now, binding tone to the confidence tier.{fb}"
    )
    return chat(_SYSTEM, user)
