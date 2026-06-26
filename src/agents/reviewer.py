"""Adversarial reviewer agent (second model family, llama3.1:8b — decision (a)).

Rewarded for finding faults. It judges argumentation quality (support objections):
does the report assert more than the ledger justifies? It does NOT re-judge physical
validity — that is the deterministic validator harness (Phase 3). Decorrelation comes
from a different model family than the Qwen writer.
"""

from __future__ import annotations

import json
import re
from typing import Any

from src.agents.client import ChatFn
from src.validators.objections import SUPPORT, Objection

VERSION = "0.1.0"

_SYSTEM = """You are an ADVERSARIAL petrophysics reviewer from a DIFFERENT model family
than the writer. You are rewarded for finding faults, not for agreeing. Read the
interpretation report and its ledger (the only source of truth for numbers).

Flag any sentence that:
(a) asserts more certainty than the ledger's confidence_tier allows
    (firm=declarative ok; qualified=must hedge; bracketed=must state range + limitation),
(b) states a number that is not in the ledger,
(c) is not justified by the ledger evidence,
(d) omits a material limitation (e.g. parameters are regional defaults, no core; bad hole).

Return ONLY a JSON array; each element {"issue": "<short>", "severity": "high|medium|low"}.
If the report is fully honest and justified, return [].
"""

_ARRAY = re.compile(r"\[.*\]", re.DOTALL)


def _parse_objections(raw: str) -> list[dict[str, str]]:
    m = _ARRAY.search(raw)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
    except (ValueError, TypeError):
        return []
    out: list[dict[str, str]] = []
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and item.get("issue"):
                out.append(
                    {
                        "issue": str(item["issue"]),
                        "severity": str(item.get("severity", "medium")),
                    }
                )
    return out


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


def review_report(report: str, ledger: dict[str, Any], chat: ChatFn) -> dict[str, Any]:
    """Adversarially review the report; return objections (support type) + raw output."""
    user = (
        f"Ledger JSON:\n```json\n{json.dumps(ledger, indent=2)[:8000]}\n```\n\n"
        f"Report:\n```markdown\n{report[:8000]}\n```\n\n"
        "Return the JSON array of objections now."
    )
    raw = chat(_SYSTEM, user)
    parsed = _parse_objections(raw)
    objections = [
        Objection("adversarial_reviewer", SUPPORT, f"{o['issue']} ({o['severity']})")
        for o in parsed
    ]
    return {"passed": len(objections) == 0, "objections": objections, "raw": raw}
