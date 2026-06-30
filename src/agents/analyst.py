"""The analyst agent node (v2): EXPLORE -> DECIDE -> DISPATCH, with signaled fallback.

The one place the LLM gets analytical agency: it reads a COMPACT EDA digest + the available
vetted methods and DECIDES which optional analyses/sections add completeness — emitting a
plan of method/section IDs and rationale, never a number. The deterministic dispatcher runs
the tools. If the model returns empty (the 16GB-VRAM failure mode) or invalid JSON, the
cascade falls back qwen3 -> llama3.1 -> deterministic heuristic, ALWAYS signaled in the
ledger (never silent), so a base-by-failure is never mistaken for a base-by-choice.
"""

from __future__ import annotations

import json
import re
from typing import Any

import numpy as np

from src.agents.client import ChatFn
from src.agents.methodology_graph import MethodologyGraph
from src.agents.report_compose import (
    _FREE_CHOOSABLE,
    OPTIONAL_REQUIRES,
    OPTIONAL_SECTIONS,
    heuristic_section_plan,
)
from src.agents.tool_dispatch import ALLOWED_TOOLS, dispatch, validate_plan
from src.eda.explore import build_eda_digest
from src.petrophysics.phie import porosity_method_comparison
from src.petrophysics.registry import ELECTRICAL_PRESETS, MATRIX_PRESETS
from src.petrophysics.vsh import vsh_method_comparison
from src.validators.physical import cross_tool_consistency

VERSION = "0.1.0"

_SYSTEM = """You are a senior petrophysical ANALYST deciding how to COMPOSE a well report.
From the FACTS (pre-computed observations) and AVAILABLE METHODS, decide which analysis sections
the report should contain and in what order — a real analyst's judgement, not a fixed template.
Data preparation and the honesty rails (parameters, validators, methodology graph, limitations)
are added automatically; you choose the ANALYSIS body.

ABSOLUTE RULES:
- Output ONLY a JSON object with this shape (a concrete example, copy the structure not the
  values):
  {"sections": ["gr_analysis", "lithology", "vsh", "porosity", "sw", "zonation", "results",
                "uncertainty", "shaly_sand_saturation"],
   "tool_calls": [{"tool": "sw_simandoux", "args": {"electrical_preset": "carbonate_default"}}],
   "rationale": "dolomitic shaly section, so include lithology and a shaly-sand saturation"}
- "sections" is your ORDERED choice of analysis sections (from the SECTION CATALOG). Most
  sections need NO tool_call — list them in "sections" only. tool_calls are ONLY for the OPTIONAL
  sections (each needs its backing method id from the catalog), never for regular section ids.
- Use REAL ids only. NEVER copy angle-bracket placeholders like <id> or <preset_id>.
- For sw_* methods set args.electrical_preset; for sonic methods set args.matrix_preset; use one
  of the VALID args listed. If unsure, omit args (a safe default is applied).
- Never write a number — the engine computes; you select and compose.
- Keep the rationale to plain words (no decimals); reference what the data shows, not values."""


def _eda_findings(digest: dict[str, Any]) -> list[tuple[str, str]]:
    """The actionable EDA findings (one observation node each). Deterministic."""
    out: list[tuple[str, str]] = []
    lr = digest.get("low_resistivity", {})
    if lr.get("n_flagged", 0) > 0:
        out.append(("low_resistivity_scan", "low-resistivity intervals present"))
    lit = digest.get("lithology", {})
    if lit.get("nearest"):
        out.append(
            (
                "crossplot_density_neutron",
                f"lithology nearest {lit['nearest']} (from density-neutron numeric crossplot)",
            )
        )
    bh = digest.get("badhole", {})
    if bh.get("DEGRADED", 0) + bh.get("EXCLUDED", 0) > 0:
        out.append(("badhole_summary", "degraded/excluded intervals present"))
    return out or [("eda_digest", "exploration complete")]


def _section_catalog() -> str:
    """The section menu the agent composes from: choosable analysis sections + optional backings."""
    optional = [
        f"{sec} (call one of: {', '.join(tools)})" for sec, tools in OPTIONAL_REQUIRES.items()
    ]
    return (
        "SECTION CATALOG — pick and order any of these in 'sections':\n"
        f"{', '.join(_FREE_CHOOSABLE)}\n\n"
        "Of those, these OPTIONAL sections also need their backing tool in tool_calls (else "
        "dropped):\n- " + "\n- ".join(optional) + "\n\n"
        f"VALID args: electrical_preset ∈ {list(ELECTRICAL_PRESETS)}; "
        f"matrix_preset ∈ {list(MATRIX_PRESETS)}."
    )


def _digest_text(digest: dict[str, Any]) -> str:
    """Compact (<~800 token) text of the digest for the LLM — never the raw curve blob."""
    return "FACTS:\n" + json.dumps(digest, indent=1)[:3000] + "\n\n" + _section_catalog()


_OBJECT = re.compile(r"\{.*\}", re.DOTALL)


def _parse_plan(raw: str) -> dict[str, Any] | None:
    """Tolerant extraction of the plan JSON; None if unparseable or malformed."""
    if not raw or not raw.strip():
        return None
    m = _OBJECT.search(raw)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    data.setdefault("sections", [])
    data.setdefault("optional_sections", [])
    data.setdefault("tool_calls", [])
    data.setdefault("rationale", "")
    if not isinstance(data["tool_calls"], list) or not isinstance(data["optional_sections"], list):
        return None
    if not isinstance(data["sections"], list):
        return None
    # coerce to clean types (a real model may return dicts where strings are expected)
    data["sections"] = [s for s in data["sections"] if isinstance(s, str)]
    data["optional_sections"] = [s for s in data["optional_sections"] if isinstance(s, str)]
    # keep only whitelisted tool_calls — models often list section ids as tools; dropping those
    # (instead of rejecting the whole plan) preserves the agent's real section composition.
    data["tool_calls"] = [
        c for c in data["tool_calls"] if isinstance(c, dict) and c.get("tool") in ALLOWED_TOOLS
    ]
    data["rationale"] = str(data.get("rationale", ""))
    return data


def _record_method_comparisons(ledger: dict[str, Any], ctx: dict[str, Any]) -> None:
    """Stamp the deterministic FIXED-floor comparisons (Vsh §13, porosity §14, Sw §16).

    The selected method is the engine's; the LLM authors none of these numbers.
    """
    curves = ctx["curves"]
    params = ledger.get("parameters", {})

    def _pv(key: str, default: float) -> float:
        return params.get(key, {}).get("value", default)

    gr = curves.get("GR")
    if gr is not None:
        variant = ledger["run"].get("variant", "old_rocks")
        selected = "vsh_larionov_tertiary" if variant == "tertiary" else "vsh_larionov_old"
        ledger["vsh_comparison"] = {
            "methods": vsh_method_comparison(gr, _pv("gr_min", 20.0), _pv("gr_max", 120.0)),
            "selected": selected,
        }

    rhob, nphi = curves.get("RHOB"), curves.get("NPHI")
    if rhob is not None or nphi is not None:
        pmethods = porosity_method_comparison(
            rhob,
            nphi,
            _pv("rho_ma", 2.71),
            _pv("rho_fl", 1.0),
            _pv("phie_max", 0.45),
            vsh=ctx.get("vsh"),
            phi_sh_d=_pv("phi_sh_d", 0.0),
            phi_sh_n=_pv("phi_sh_n", 0.0),
        )
        sel = (
            "phie_density_neutron"
            if "phie_density_neutron" in pmethods
            else next(iter(pmethods), "—")
        )
        ledger["porosity_comparison"] = {"methods": pmethods, "selected": sel}

    sw = ctx.get("sw")
    if sw is not None:
        finite = np.asarray(sw, dtype=float)
        mean_sw = round(float(np.nanmean(finite)), 4) if np.any(np.isfinite(finite)) else None
        ledger["sw_summary"] = {
            "method": "sw_archie",
            "mean_sw": mean_sw,
            "a": _pv("a", float("nan")),
            "m": _pv("m", float("nan")),
            "n": _pv("n", float("nan")),
            "rw": _pv("Rw", float("nan")),
        }


def run_analyst(
    ledger: dict[str, Any],
    ctx: dict[str, Any],
    mode: str,
    chat: ChatFn,
    model: str,
    fallback_chat: ChatFn | None = None,
    fallback_model: str = "",
) -> dict[str, Any]:
    """Run EXPLORE -> DECIDE -> DISPATCH and return ``{section_plan, graph, fell_back}``.

    Records ``ledger['run']['analyst']`` (model_used, empty_returns, fell_back_to_deterministic)
    and ``ledger['run']['methodology_graph']``. The cascade is always signaled.
    """
    graph = MethodologyGraph(mode=mode, model=model)
    digest = build_eda_digest(ctx)
    ledger.setdefault("run", {})["eda"] = digest
    _record_method_comparisons(ledger, ctx)

    # one observation node per surfaced EDA finding (makes exploration_coverage meaningful)
    for tool, finding in _eda_findings(digest):
        graph.add(
            "observation", {"tool": tool, "finding": finding, "source_ledger_key": "ledger:eda"}
        )

    plan: dict[str, Any] | None = None
    used = ""
    empty_returns = 0
    for c, mdl in ((chat, model), (fallback_chat, fallback_model)):
        if c is None:
            continue
        raw = c(_SYSTEM, _digest_text(digest))
        if not raw or not raw.strip():
            empty_returns += 1
            continue
        candidate = _parse_plan(raw)
        if candidate is not None and not validate_plan({"tool_calls": candidate["tool_calls"]}):
            plan, used = candidate, mdl
            break

    fell_back = plan is None
    if plan is None:
        plan = heuristic_section_plan(ledger)
        plan["tool_calls"] = []
        plan["rationale"] = "deterministic heuristic (analyst unavailable)"
        used = "deterministic"

    graph.add(
        "decision",
        {
            "rationale": str(plan.get("rationale", "")),
            "chosen": ",".join(c.get("tool", "") for c in plan["tool_calls"]),
        },
    )
    dispatch({"tool_calls": plan["tool_calls"]}, ctx, ledger, graph)

    # Cross-tool consistency: a dispatched tool result that contradicts the core calibration
    # becomes a MECHANICAL objection (a contradiction, not a silent dual number).
    cross_objs = cross_tool_consistency(ledger)
    if cross_objs:
        ledger.setdefault("objections", []).extend(
            {"validator_id": o.validator_id, "type": o.objection_type, "detail": o.detail}
            for o in cross_objs
        )

    sections = list(plan.get("sections", []))
    optional = [s for s in sections if s in OPTIONAL_SECTIONS]
    optional += [s for s in plan.get("optional_sections", []) if s not in optional]
    ledger["run"]["analyst"] = {
        "model_used": used,
        "empty_returns": empty_returns,
        "fell_back_to_deterministic": fell_back,
        "sections": sections,
        "optional_sections": optional,
        "n_observations_available": len(_eda_findings(digest)),
    }
    ledger["run"]["methodology_graph"] = graph.to_json()
    return {
        "section_plan": {"sections": sections, "optional_sections": optional},
        "graph": graph,
        "fell_back": fell_back,
    }
