"""Per-model report scorer (same-model self-evaluation, v2).

Scores a report's ANALYTICAL QUALITY — method choice, decision quality, honesty,
narrative — NOT its numbers (those are computed deterministically and checked by the
claim verifier). Scoring is done by the SAME model that may have written the report:
the goal is to compare which model produces better reports, so the score is per-model
metadata, not a cross-family adversarial gate. It is advisory and never blocks a gate.
"""

from __future__ import annotations

import json
import re
from typing import Any

from src.agents.client import ChatFn

VERSION = "0.1.0"

_SCORE_SYSTEM = """You are scoring a petrophysical report's ANALYTICAL QUALITY (not its numbers,
which are computed deterministically). You are the SAME model that may have written it — this is a
per-model self-evaluation, so be calibrated, not generous. Score each 1-5 and list objections.

Return ONLY a JSON object:
{"completeness":1-5,"method_appropriateness":1-5,"decision_quality":1-5,"honesty":1-5,
 "narrative":1-5,"objections":["..."]}
The 1-5 scores are metadata about the model, never numbers of the report."""


def score_report(
    report: str, methodology_graph: dict[str, Any], ledger: dict[str, Any], chat: ChatFn
) -> dict[str, Any]:
    """Same-model qualitative score of the report (advisory — never blocks a gate).

    Returns the 1-5 dimensions + objections. Defaults to mid-scores on unparseable output so a
    model that cannot self-evaluate is not silently rewarded. Numbers here are evaluation
    metadata, outside the claim_verifier's scope.
    """
    user = (
        f"Methodology graph: {json.dumps(methodology_graph)[:2000]}\n\n"
        f"Report:\n```markdown\n{report[:8000]}\n```\n\nReturn the JSON score now."
    )
    raw = chat(_SCORE_SYSTEM, user)
    dims = ("completeness", "method_appropriateness", "decision_quality", "honesty", "narrative")
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    parsed: Any = {}
    if m:
        try:
            parsed = json.loads(m.group(0))
        except (ValueError, TypeError):
            parsed = {}
    if not isinstance(parsed, dict):
        parsed = {}
    score = {d: int(parsed[d]) if isinstance(parsed.get(d), (int, float)) else 3 for d in dims}
    raw_objs = parsed.get("objections", [])
    objections = [str(o) for o in raw_objs] if isinstance(raw_objs, list) else []
    return {**score, "objections": objections, "raw": raw}
