"""Plan-driven report composition + the two modes (v2).

Builds the report from a ``section_plan`` instead of a fixed template: mandatory sections
always appear; optional sections appear only when the plan (agent or heuristic) selects
them and the data supports them. Reuses the FROZEN v1 section renderers (v1 stays intact;
this composer re-numbers by plan order). The mode is set by the invoker, never the LLM:
guided = mandatory gates + ABSTENTION_SAFE restriction; free = advisory gates + mandatory
methodology-graph section. ``graph.validate()`` is a MECHANICAL gate (blocks guided, warns free).
"""

from __future__ import annotations

import re
from typing import Any

from src.agents import report_template as v1
from src.agents.claim_verifier import verify_keyed, verify_tone
from src.agents.methodology_graph import MethodologyGraph

VERSION = "0.1.0"

GUIDED, FREE = "guided", "free"

# GUIDED mode: the full mandatory floor (numbered, in order) — the comparable baseline.
_MANDATORY_BODY = [
    "executive_summary",
    "data_inventory",
    "las_qc",
    "standardization",
    "curve_qc",
    "data_prep",
    "intervals",
    "methodology",
    "gr_analysis",
    "resistivity_analysis",
    "caliper_quality",
    "lithology",
    "vsh",
    "porosity",
    "sw",
    "parameters",
    "rw",
    "cutoffs",
    "zonation",
    "results",
    "uncertainty",
    "data_quality",
    "figures",
    "recommendations",
    "limitations",
    "conclusions",
]
# Optional sections the plan may insert (after results). Vetted, closed set.
OPTIONAL_SECTIONS = (
    "shaly_sand_saturation",
    "sonic_porosity",
    "permeability",
    "rock_quality",
    "electrofacies",
    "derived_parameters",
)
# Each optional section is backed by a named tool result; the section is emitted ONLY when that
# result exists, so "section present ⇒ a real tool number backs it" always holds (no theater).
OPTIONAL_REQUIRES: dict[str, tuple[str, ...]] = {
    "shaly_sand_saturation": ("sw_simandoux",),
    "sonic_porosity": ("phi_sonic_wyllie", "phi_sonic_rhg"),
    "permeability": ("perm_timur", "perm_coates"),
    "rock_quality": ("rqi", "fzi", "winland_r35"),
    "electrofacies": ("electrofacies",),
    "derived_parameters": ("bvw",),
}
# Optional sections allowed when the run abstains (diagnostic only — never confident analysis).
ABSTENTION_SAFE: tuple[str, ...] = ()

# FREE mode: only data preparation + the honesty rails are forced; the agent decides the analysis.
# Forced head (data prep foundation + the headline) and trailing rails (provenance, validators +
# claim verifier, methodology graph, limitations, conclusions). Everything else is the agent's.
_FREE_HEAD = [
    "executive_summary",
    "data_inventory",
    "las_qc",
    "standardization",
    "curve_qc",
    "data_prep",
    "intervals",
    "methodology",
]
_FREE_TAIL = [
    "parameters",
    "cutoffs",
    "data_quality",
    "__methodology_graph__",
    "recommendations",
    "limitations",
    "conclusions",
]
# Analysis sections the agent may choose (and order) in FREE mode — including the optional ones.
_FREE_CHOOSABLE: tuple[str, ...] = (
    "gr_analysis",
    "resistivity_analysis",
    "caliper_quality",
    "lithology",
    "vsh",
    "porosity",
    "sw",
    "rw",
    "zonation",
    "results",
    "uncertainty",
    "figures",
) + OPTIONAL_SECTIONS


def _strip_number(block: str) -> str:
    return re.sub(r"^(#+ )\d+\.\s*", r"\1", block, flags=re.MULTILINE)


def _optional_supported(section_id: str, ledger: dict[str, Any]) -> bool:
    """True only when a backing tool result exists for the optional section."""
    results = ledger.get("tool_results", {})
    return any(k in results for k in OPTIONAL_REQUIRES.get(section_id, ()))


def _shaly_sand(ledger: dict[str, Any]) -> str:
    sw = ledger.get("tool_results", {}).get("sw_simandoux", {}).get("value", {})
    return f"## Shaly-sand saturation\n\nMean Sw (Simandoux): {sw.get('mean_sw', '—')}.\n"


def _sonic_porosity(ledger: dict[str, Any]) -> str:
    results = ledger.get("tool_results", {})
    for key in ("phi_sonic_wyllie", "phi_sonic_rhg"):
        val = results.get(key, {}).get("value", {})
        if val:
            return (
                f"## Sonic porosity\n\nMean sonic porosity ({key}): {val.get('mean_phi', '—')}.\n"
            )
    return "## Sonic porosity\n\n_Not computed — no sonic-porosity tool result._\n"


def _render_known(section_id: str, ledger: dict[str, Any], narrative: dict[str, str]) -> str:
    """Render a v1 section (number-stripped) or a v2 optional section."""
    renderers = {
        "executive_summary": lambda: v1._executive_summary(
            ledger, narrative.get("executive_summary", "")
        ),
        "methodology": v1._methodology,
        "parameters": lambda: v1._parameters(ledger),
        "zonation": lambda: v1._zonation(ledger),
        "results": lambda: v1._results(ledger),
        "uncertainty": lambda: v1._uncertainty(ledger),
        "data_quality": lambda: v1._data_quality(ledger),
        "figures": lambda: v1._figures(ledger),
        "conclusions": lambda: v1._conclusions(narrative.get("conclusions", "")),
        # R2 — LAS-only [FIJO] renderer sections
        "data_inventory": lambda: v1._data_inventory(ledger),
        "las_qc": lambda: v1._las_qc(ledger),
        "standardization": lambda: v1._standardization(ledger),
        "curve_qc": lambda: v1._curve_qc(ledger),
        "data_prep": lambda: v1._data_prep(ledger),
        "intervals": lambda: v1._intervals(ledger),
        "gr_analysis": lambda: v1._gr_analysis(ledger),
        "resistivity_analysis": lambda: v1._resistivity_analysis(ledger),
        "caliper_quality": lambda: v1._caliper_quality(ledger),
        "lithology": lambda: v1._lithology(ledger),
        "vsh": lambda: v1._vsh(ledger),
        "porosity": lambda: v1._porosity(ledger),
        "sw": lambda: v1._sw(ledger),
        "rw": lambda: v1._rw(ledger),
        "cutoffs": lambda: v1._cutoffs(ledger),
        "recommendations": lambda: v1._recommendations(ledger),
        "limitations": lambda: v1._limitations(ledger),
        "shaly_sand_saturation": lambda: _shaly_sand(ledger),
        "sonic_porosity": lambda: _sonic_porosity(ledger),
        "permeability": lambda: v1._permeability_section(ledger),
        "rock_quality": lambda: v1._rock_quality_section(ledger),
        "electrofacies": lambda: v1._electrofacies_section(ledger),
        "derived_parameters": lambda: v1._derived_parameters_section(ledger),
    }
    if section_id not in renderers:
        raise KeyError(section_id)
    return _strip_number(renderers[section_id]())


def _methodology_section(graph: MethodologyGraph) -> str:
    return f"## Methodology (decision graph)\n\n{graph.to_mermaid()}\n"


def heuristic_section_plan(ledger: dict[str, Any]) -> dict[str, Any]:
    """Deterministic section plan (the V2-D stand-in for the LLM agent).

    Picks optional sections from what the data shows: shaly-sand saturation when a
    Simandoux tool result exists; sonic porosity when DT is present.
    """
    optional: list[str] = []
    if "sw_simandoux" in ledger.get("tool_results", {}):
        optional.append("shaly_sand_saturation")
    if "DT" in ledger.get("run", {}).get("curve_provenance", {}):
        optional.append("sonic_porosity")
    # the fallback yields a COMPLETE analysis body (so a model-unavailable run is still useful);
    # only a real model's choice produces a tailored, possibly-thinner report.
    core = [s for s in _FREE_CHOOSABLE if s not in OPTIONAL_SECTIONS]
    return {"sections": core + optional, "optional_sections": optional}


def _free_body(section_plan: dict[str, Any], ledger: dict[str, Any]) -> list[str]:
    """FREE mode: forced prep head + the agent's chosen analysis sections + forced honesty rails.

    The agent's ``sections`` (ordered) drive the body; optional sections survive only when a
    backing tool result exists (no theater). Picking nothing yields a minimal but honest report.
    """
    raw = list(section_plan.get("sections", []))
    raw += [s for s in section_plan.get("optional_sections", []) if s not in raw]
    seen: set[str] = set()
    chosen: list[str] = []
    for s in raw:
        if s not in _FREE_CHOOSABLE or s in seen:
            continue
        if s in OPTIONAL_SECTIONS and not _optional_supported(s, ledger):
            continue
        seen.add(s)
        chosen.append(s)
    return _FREE_HEAD + chosen + _FREE_TAIL


def _ordered_body(section_plan: dict[str, Any], mode: str, ledger: dict[str, Any]) -> list[str]:
    if mode == FREE:
        return _free_body(section_plan, ledger)
    # GUIDED: the full mandatory floor (comparable baseline), optionals inserted after results.
    abstain = bool(ledger.get("run", {}).get("abstain"))
    requested = [s for s in section_plan.get("optional_sections", []) if s in OPTIONAL_SECTIONS]
    requested = [s for s in requested if _optional_supported(s, ledger)]
    if abstain:
        requested = [s for s in requested if s in ABSTENTION_SAFE]
    ids: list[str] = []
    for sid in _MANDATORY_BODY:
        ids.append(sid)
        if sid == "results":
            ids.extend(requested)
    return ids


def compose_report(
    ledger: dict[str, Any],
    section_plan: dict[str, Any],
    mode: str,
    graph: MethodologyGraph,
    narrative: dict[str, str] | None = None,
) -> str:
    """Assemble the plan-driven report. ``mode`` is GUIDED or FREE (set by the invoker)."""
    narrative = narrative or {"executive_summary": "", "conclusions": ""}
    graph_issues = graph.validate(ledger)

    preamble = [v1._header(ledger.get("run", {})), v1._legend()]
    if mode == GUIDED and graph_issues:
        preamble.append(
            "> ⚠️ **BLOCKED (guided): methodology graph invalid** — " + "; ".join(graph_issues[:3])
        )
    elif graph_issues:  # free mode: advisory
        preamble.append("> ⚠️ methodology graph warnings: " + "; ".join(graph_issues[:3]))

    body_blocks: list[str] = []
    n = 0
    for sid in _ordered_body(section_plan, mode, ledger):
        n += 1
        block = (
            _methodology_section(graph)
            if sid == "__methodology_graph__"
            else _render_known(sid, ledger, narrative)
        )
        body_blocks.append(re.sub(r"^## ", f"## {n}. ", block, count=1))

    # Claim verification (deterministic): reconcile numbers in the LLM-authored PROSE against the
    # ledger (tight, keyed) + check tone. Only the narrative can hallucinate a number — the tables
    # are rendered deterministically from the ledger (correct by construction, only display-
    # rounded), so verifying them would flag rounding, not lies. Stamped on the ledger for the
    # completeness gate; a FLAGS result is surfaced in the preamble, never hidden.
    prose = (
        narrative.get("executive_summary", "") + "\n" + narrative.get("conclusions", "")
    ).strip()
    keyed = verify_keyed(prose, ledger)
    tone_flags = verify_tone(prose, ledger)
    passed = keyed["passed"] and not tone_flags
    ledger.setdefault("run", {})["claim_verifier"] = {
        "result": "PASS" if passed else "FLAGS",
        "flags": keyed["flags"],
        "tone_flags": tone_flags,
    }
    if not passed:
        detail = []
        if keyed["flags"]:
            detail.append(f"{len(keyed['flags'])} number(s) not traceable to the ledger")
        if tone_flags:
            detail.append("tone (overconfident for tier)")
        preamble.append("> ⚠️ **claim verifier FLAGS:** " + "; ".join(detail))

    appendix = [
        _strip_number(v1._appendix_ledger(ledger)),
        _strip_number(v1._appendix_checklist(ledger)),
    ]
    return "\n\n---\n\n".join(preamble + body_blocks + appendix) + "\n"
