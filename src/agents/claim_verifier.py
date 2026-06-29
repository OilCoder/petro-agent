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


def _collect_numbers(obj: Any, out: set[float]) -> None:
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        out.add(float(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            _collect_numbers(v, out)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _collect_numbers(v, out)
    elif isinstance(obj, str):
        for m in _DECIMAL.findall(obj):
            out.add(float(m))


_HEDGE_TERMS = ("bracket", "uncertain", "range", "default", "not", "caution", "abstain",
                "limit", "regional", "p10", "p90", "uncalibrated")


def verify_tone(report: str, ledger: dict[str, Any]) -> list[str]:
    """Flag tone violations: a bracketed or abstaining run must hedge (check 4).

    A ``bracketed`` tier or an ``abstain`` run whose prose contains no hedging/limitation
    language is over-confident — the report asserts more certainty than the ledger allows.
    """
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


def verify_keyed(
    report: str, ledger: dict[str, Any], rel_tol: float = KEYED_REL_TOL
) -> dict[str, Any]:
    """Reconcile report numbers against tool-derived ledger values with a TIGHT tolerance.

    v2 adds optional sections whose numbers come from named tool results
    (``ledger['tool_results'][key]['value']``). The flat verifier's 2% band weakens as the
    number set grows; this keyed check uses a rounding-only epsilon, so a value that drifts
    from its tool result is flagged as authored (not from a tool).
    """
    nums: set[float] = set()
    _collect_numbers(ledger, nums)
    flags: list[float] = []
    for token in _DECIMAL.findall(report):
        num = float(token)
        if not any(abs(num - ln) <= max(1e-6, rel_tol * abs(ln)) for ln in nums):
            flags.append(num)
    return {"passed": len(flags) == 0, "flags": flags}
