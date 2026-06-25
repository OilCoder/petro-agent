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


def verify_report(
    report: str, ledger: dict[str, Any], rel_tol: float = 0.02, abs_tol: float = 0.01
) -> dict[str, Any]:
    """Flag every decimal in the report that no ledger value supports (within tolerance)."""
    ledger_nums: set[float] = set()
    _collect_numbers(ledger, ledger_nums)

    flags: list[float] = []
    for token in _DECIMAL.findall(report):
        num = float(token)
        if not any(abs(num - ln) <= max(abs_tol, rel_tol * abs(ln)) for ln in ledger_nums):
            flags.append(num)
    return {"passed": len(flags) == 0, "flags": flags}
