"""Claim verifier: deterministic reconciliation of report numbers against the ledger.

No sentence may assert a number the ledger does not support. This is deterministic
(not an LLM opinion) — every decimal in the report must match a ledger value within
tolerance, else it is flagged as a potential hallucination.
"""

from __future__ import annotations

import re
from typing import Any

VERSION = "0.1.0"

_DECIMAL = re.compile(r"(?<![\w.])(\d+\.\d+)")


# Renderer print formats: every ledger number may legitimately appear rounded to these.
_RENDER_DECIMALS = (1, 2, 3, 4)


def _collect_numbers(obj: Any, out: set[float]) -> None:
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        v = float(obj)
        out.add(v)
        # the PRINTED forms of a ledger value are ledger-derived, not authored
        for nd in _RENDER_DECIMALS:
            out.add(round(v, nd))
    elif isinstance(obj, dict):
        for v in obj.values():
            _collect_numbers(v, out)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _collect_numbers(v, out)
    elif isinstance(obj, str):
        for m in _DECIMAL.findall(obj):
            out.add(float(m))


_HEDGE_TERMS = (
    "bracket",
    "uncertain",
    "range",
    "default",
    "not",
    "caution",
    "abstain",
    "limit",
    "regional",
    "p10",
    "p90",
    "uncalibrated",
)


def verify_tone(report: str, ledger: dict[str, Any]) -> list[str]:
    """Flag tone violations: a bracketed or abstaining run must hedge (check 4).

    A ``bracketed`` tier or an ``abstain`` run whose prose contains no hedging/limitation
    language is over-confident — the report asserts more certainty than the ledger allows.
    """
    if not report.strip():
        return []  # absent prose is not overconfident prose
    run = ledger.get("run", {})
    bracketed = run.get("confidence_tier") == "bracketed" or run.get("abstain")
    if not bracketed:
        return []
    low = report.lower()
    if not any(term in low for term in _HEDGE_TERMS):
        return ["bracketed/abstaining run but the prose states no range or limitation"]
    return []


# Rounding-only epsilon for the keyed reconciliation (the DV2-2 tolerance). Tighter than the
# flat verifier's 2% so a value that drifts from its tool result (e.g. 1.9% off) is caught.
KEYED_REL_TOL = 0.005
# Algorithm constants renderers state in prose (numbers from vetted CODE, not from the LLM).
RENDER_CONSTANTS: tuple[float, ...] = ()


def _tol(ln: float, rel_tol: float) -> float:
    return max(1e-6, rel_tol * abs(ln))


def verify_keyed(
    report: str,
    ledger: dict[str, Any],
    rel_tol: float = KEYED_REL_TOL,
    extra_allowed: tuple[float, ...] = RENDER_CONSTANTS,
) -> dict[str, Any]:
    """Reconcile report numbers against tool-derived ledger values with a TIGHT tolerance.

    v2 adds optional sections whose numbers come from named tool results
    (``ledger['tool_results'][key]['value']``). The number pool holds each ledger value AND
    its printed forms (rounded to the renderer formats) — an honest 1-decimal render of a
    ledger float (1.8 for 1.8288) matches exactly, while an authored value that matches no
    printed form is flagged. ``extra_allowed`` admits DECLARED algorithm constants renderers
    state in prose (e.g. the zone-merge gap tolerance).
    """
    nums: set[float] = set()
    _collect_numbers(ledger, nums)
    nums.update(float(c) for c in extra_allowed)
    flags: list[float] = []
    for token in _DECIMAL.findall(report):
        num = float(token)
        if not any(abs(num - ln) <= _tol(ln, rel_tol) for ln in nums):
            flags.append(num)
    return {"passed": len(flags) == 0, "flags": flags}
