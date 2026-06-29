"""Writer agent: produces ONLY the narrative prose slots of the report.

The deterministic renderer (``report_template``) owns every number and table. The LLM
writes two prose blocks — executive summary and conclusions — from a pre-formatted facts
digest, and is forbidden from introducing any number not already in that digest. This is
the invariant in practice: the model narrates, it does not compute or transcribe values.
"""

from __future__ import annotations

from typing import Any

from src.agents.client import ChatFn

VERSION = "0.1.0"

_SYSTEM = """You are a senior PETROPHYSICIST writing narrative prose for a well-log report.
You interpret ROCK and FLUIDS — shale volume (Vsh), effective porosity (PHIE), water
saturation (Sw), and net-pay zones — NOT software, algorithms, or "data convergence".

ABSOLUTE RULES:
- Write PROSE ONLY. Do NOT output tables, headings, bullet lists, or JSON.
- Use ONLY the numbers in the FACTS block. Never introduce, compute, or re-round a number.
  If you want to cite a value, copy it verbatim from FACTS. The tables are rendered
  separately by code — do not reproduce them.
- Bind tone to the confidence tier: firm = declarative; qualified = hedged; bracketed =
  speak of ranges and name the limitation (parameters are regional DEFAULTS, no core).
- "DID_NOT_CONVERGE" is an INTERNAL QC flag (the validation loop hit a data-limited
  objection); mention it at most as a one-line caveat. Do NOT make the report about it.
- 2 to 4 sentences. Be honest; never assert more certainty than the tier allows.
- You did NOT see any figure, plot, or log image. Never write "as seen in the crossplot",
  "the log shows", or imply visual inspection — your only evidence is the numeric FACTS.
"""


def _facts(ledger: dict[str, Any]) -> str:
    """Build a compact, pre-formatted facts digest (the ONLY numbers the LLM may use)."""
    run = ledger.get("run", {})
    summary = ledger.get("summary", {})
    unc = ledger.get("uncertainty", {})
    sens = unc.get("sensitivity", {})
    warn = unc.get("high_leverage_warning", {})
    p = run.get("net_pay_p10_p50_p90")
    np_str = (
        f"P10/P50/P90 = {p[0]:.1f}/{p[1]:.1f}/{p[2]:.1f} m"
        if p
        else f"{ledger.get('net_pay_total_m', float('nan')):.1f} m"
    )
    lines = [
        f"- Well: {run.get('uwi', '?')}",
        f"- Confidence tier: {run.get('confidence_tier', 'bracketed')}",
        f"- Convergence status: {run.get('convergence_status', '?')}",
        f"- Net pay: {np_str}",
        f"- Gross interval: {summary.get('gross_m', float('nan')):.1f} m, "
        f"net-to-gross {summary.get('ntg', float('nan')):.3f}",
        f"- Net-pay averages: PHIE {summary.get('avg_phie', float('nan')):.3f}, "
        f"Sw {summary.get('avg_sw', float('nan')):.3f}, "
        f"Vsh {summary.get('avg_vsh', float('nan')):.3f}",
        f"- Dominant uncertainty parameter: {sens.get('dominant_parameter', '?')} "
        f"(swing {sens.get('dominant_swing_m', float('nan')):.1f} m)",
        f"- Validator objections: {len(ledger.get('objections', []))}",
    ]
    if warn.get("warn"):
        lines.append(f"- High-leverage warning: {warn.get('message')}")
    if run.get("abstain"):
        lines.append(
            "- ABSTENTION: this run is NOT a confident estimate — "
            + "; ".join(run.get("abstain_reasons", []))
        )
    return "\n".join(lines)


def write_narrative(ledger: dict[str, Any], chat: ChatFn, feedback: str = "") -> dict[str, str]:
    """Generate the executive-summary and conclusions prose blocks via the writer LLM.

    Args:
        ledger: the completed ledger (source of the facts digest).
        chat: the writer chat function.
        feedback: optional reviewer objections to address in the revision.

    Returns:
        ``{"executive_summary": str, "conclusions": str}`` — prose only, no numbers
        beyond the facts digest.
    """
    facts = _facts(ledger)
    fb = f"\n\nA reviewer raised these objections; address EACH:\n{feedback}" if feedback else ""

    exec_user = (
        f"FACTS (the ONLY numbers you may use):\n{facts}\n\n"
        f"Write the EXECUTIVE SUMMARY narrative: the reservoir/pay story in plain "
        f"petrophysical terms (rock, porosity, saturation, net pay), tone bound to the "
        f"confidence tier.{fb}"
    )
    concl_user = (
        f"FACTS (the ONLY numbers you may use):\n{facts}\n\n"
        f"Write the CONCLUSIONS narrative: the key takeaway and the single highest-leverage "
        f"next action to reduce uncertainty, tone bound to the confidence tier.{fb}"
    )
    return {
        "executive_summary": chat(_SYSTEM, exec_user).strip(),
        "conclusions": chat(_SYSTEM, concl_user).strip(),
    }
