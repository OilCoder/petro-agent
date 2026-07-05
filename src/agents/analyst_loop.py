"""The agentic loop (v2 free mode): observe → decide → compute → observe, step by step.

The orchestrator owns the loop and termination. Each step the agent sees the accumulated state +
the physics-valid actions and picks ONE (or FINISH); the engine computes that one thing; the agent
reacts. The interpretation EMERGES from the agent's decisions — but the LLM never computes a number
(the invariant). Recompute is allowed (downstream is invalidated). A per-step signaled fallback to
the canonical default keeps the loop from hanging.
"""

from __future__ import annotations

import json
import re
from typing import Any

from src.agents.client import ChatFn
from src.agents.loop_actions import (
    PRODUCES,
    available_actions,
    execute_step,
    seed_baseline_sections,
)
from src.agents.methodology_graph import MethodologyGraph
from src.eda.explore import build_eda_digest
from src.orchestrator.finalize import persist_ledger, revalidate_objections
from src.orchestrator.steps import default_vsh_key
from src.validators.physical import cross_tool_consistency

VERSION = "0.1.0"

# Property computed by the agent -> the report section ids it produces (in the analysis body).
_PROP_SECTIONS: dict[str, tuple[str, ...]] = {
    "vsh": ("vsh",),
    "phie": ("porosity",),
    "sw": ("sw",),
    "netpay": ("zonation", "results"),
    "uncertainty": ("uncertainty",),
    "permeability": ("permeability",),
    "rock_quality": ("rock_quality",),
    "electrofacies": ("electrofacies",),
    "lithology": ("lithology",),
    "derived": ("derived_parameters",),
}
# Canonical default order for the per-step fallback (a competent baseline interpretation).
_DEFAULT_ORDER = ("compute_vsh", "compute_phie", "compute_sw", "apply_cutoffs", "run_uncertainty")
# The complete core chain; mid-loop advisory validation fires only once it exists.
_CORE_CHAIN = frozenset({"vsh", "phie", "sw", "netpay"})


def _maybe_revalidate(
    action: str, valid: set[str], ledger: dict[str, Any], ctx: dict[str, Any]
) -> None:
    """Mid-loop advisory validation (R14-G): re-run the deterministic checks the moment the core
    chain is complete after a core-affecting step, so the NEXT observation carries the objections
    (e.g. implausible PHIE). Evidence only — no gate, nothing prescribed; the verdict stays with
    ``finalize_run``."""
    core_touched = action == "set_zone_of_interest" or PRODUCES.get(action) in _CORE_CHAIN
    if core_touched and _CORE_CHAIN <= valid:
        revalidate_objections(ledger, ctx)


# The ledger key each ACTION actually writes (for honest graph provenance). Observations are
# read-only (absent here) so their tool_call node claims NO result_ledger_key — the graph's
# self-check flagged "ledger:<action> not in ledger" because the action name is not a ledger key.
_ACTION_LEDGER_KEY: dict[str, str] = {
    "compute_vsh": "vsh_comparison",
    "compute_phie": "porosity_comparison",
    "compute_sw": "sw_summary",
    "apply_cutoffs": "zones",
    "run_uncertainty": "uncertainty",
    "set_zone_of_interest": "zone_of_interest",
    "permeability": "tool_results",
    "rock_quality": "tool_results",
    "electrofacies": "tool_results",
    "lithology": "tool_results",
    "derived_parameters": "tool_results",
}

_LOOP_SYSTEM = """You are a senior petrophysical ANALYST composing a well report STEP BY STEP.
The engine has computed a CORE interpretation (vsh, phie, sw, net pay, uncertainty) with DEFAULT
methods — treat it as a STARTING POINT, not a finished report. Your job is to compose the most
complete, defensible analysis the DATA justify: choose the methods and optional analyses your own
reading of the data supports, and finish ONLY when the analysis is genuinely complete for this well
— not merely because a baseline exists. Each turn you see the STATE and the VALID ACTIONS; choose
exactly ONE next action:
- OBSERVE the data (depth_quality, distributions, scans, crossplot, examine_figures) to inform your
  judgement; compare_methods, args {"property": "vsh"|"porosity"|"sw"}, returns the engine-computed
  mean of every vetted method for that property — evidence you may read BEFORE choosing a method;
  request_tool, args {"spec": "<computation you lack>"}, records the request for human vetting — it
  executes nothing now; validate_choice, args {"property": "vsh"|"porosity"|"sw"}, returns the
  engine-computed agreement (n, r, MAD, bias) between your chosen result and an independent
  contrast, when one exists; rw_evidence returns an engine-computed SP-derived Rw estimate with
  its declared assumptions, when readable; mhi_scan returns the Rxo/Rt movable-hydrocarbon
  indicator profile, when those curves exist; interval_stats, args {"top": <m>, "bottom": <m>},
  returns curve medians over ANY interval you propose — test a hypothesis before committing;
  objection_profile shows, per depth bin, where your current pay samples and their PHIE live;
  review_attempts, args {"attempt": <n>} or empty, returns the full engine record of your OWN
  prior attempts on this well (complete history, on demand);
- RESTRICT the analysis to a depth interval with set_zone_of_interest, args {"top": <m>,
  "bottom": <m>} (recomputes over that zone) if your reading of the data warrants it;
- RECOMPUTE a core property with a different vetted method (at most once per property) when the
  data justify it;
- ADD an optional analysis (permeability, rock_quality, electrofacies, lithology,
  derived_parameters) that the data support and that adds value to the report;
- pick "finish" ONLY when the analysis is genuinely complete for this well.

Output ONLY a JSON object: {"action": "<id>", "method": "<optional method id>", "args": {}}.
Use an id from VALID ACTIONS only. Do NOT repeat the same action; do NOT recompute a property you
already chose a method for. You never compute a number — the engine does; you decide WHICH method,
WHETHER to restrict the interval, WHICH analyses to include, and in what order. Never write a
number; never invent an id. NEVER add an analysis the data do not support just to lengthen it."""

_LOOP_SYSTEM_AUTHOR = """You are a senior petrophysical ANALYST and the AUTHOR of this well's
interpretation. NO interpretation exists yet — only the measured data (curves, QC, figures). Your
job is to build the complete, defensible analysis the DATA justify, step by step. Each turn you see
the STATE and the VALID ACTIONS (actions unlock as their physical prerequisites are met); choose
exactly ONE next action:
- OBSERVE the data (depth_quality, distributions, scans, crossplot, examine_figures) to inform your
  judgement; compare_methods, args {"property": "vsh"|"porosity"|"sw"}, returns the engine-computed
  mean of every vetted method for that property — evidence you may read BEFORE choosing a method;
  request_tool, args {"spec": "<computation you lack>"}, records the request for human vetting — it
  executes nothing now; validate_choice, args {"property": "vsh"|"porosity"|"sw"}, returns the
  engine-computed agreement (n, r, MAD, bias) between your chosen result and an independent
  contrast, when one exists; rw_evidence returns an engine-computed SP-derived Rw estimate with
  its declared assumptions, when readable; mhi_scan returns the Rxo/Rt movable-hydrocarbon
  indicator profile, when those curves exist; interval_stats, args {"top": <m>, "bottom": <m>},
  returns curve medians over ANY interval you propose — test a hypothesis before committing;
  objection_profile shows, per depth bin, where your current pay samples and their PHIE live;
  review_attempts, args {"attempt": <n>} or empty, returns the full engine record of your OWN
  prior attempts on this well (complete history, on demand);
- DECIDE whether to RESTRICT the analysis to a depth interval with set_zone_of_interest, args
  {"top": <m>, "bottom": <m>}, if your reading of the data warrants it;
- COMPUTE each core property (vsh, phie, sw, cutoffs, uncertainty), choosing its method ONCE — pass
  "method" to select a vetted method, or omit it to accept the engine default;
- ADD an optional analysis (permeability, rock_quality, electrofacies, lithology,
  derived_parameters) that the data support and that adds value to the report;
- pick "finish" ONLY when the analysis is genuinely complete for this well.

Output ONLY a JSON object: {"action": "<id>", "method": "<optional method id>", "args": {}}.
Use an id from VALID ACTIONS only. Do NOT repeat the same action. You never compute a number — the
engine does; you decide WHICH method, WHETHER to restrict the interval, WHICH analyses to include,
and in what order. Never write a number; never invent an id. NEVER add an analysis the data do not
support just to lengthen it."""

_OBJ = re.compile(r"\{.*\}", re.DOTALL)


def parse_action(raw: str, actions: list[str]) -> dict[str, Any] | None:
    """Extract a validated action choice from the model output; None if unusable."""
    if not raw or not raw.strip():
        return None
    m = _OBJ.search(raw)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict) or data.get("action") not in actions:
        return None
    method = data.get("method")
    args = data.get("args")
    return {
        "action": data["action"],
        "method": method if isinstance(method, str) else None,
        "args": args if isinstance(args, dict) else {},
    }


def _initial_valid(ctx: dict[str, Any], ledger: dict[str, Any]) -> set[str]:
    """Properties already valid from pass-0 (the default interpretation the agent observes)."""
    valid: set[str] = set()
    for prop in ("vsh", "phie", "sw"):
        if ctx.get(prop) is not None:
            valid.add(prop)
    if ledger.get("zones") is not None:
        valid.add("netpay")
    if ledger.get("uncertainty"):
        valid.add("uncertainty")
    return valid


def _report_outline(ledger: dict[str, Any], order: list[str]) -> list[str]:
    """A compact, document-like view of the report built SO FAR (one line per section)."""
    cal = ledger.get("calibration", {})
    tr = ledger.get("tool_results", {})
    lines: list[str] = ["[prep + honesty rails are added automatically]"]
    summaries = {
        "vsh": lambda: f"Shale volume: {cal.get('vsh_method', {}).get('value', '?')}",
        "porosity": lambda: (
            f"Porosity: {ledger.get('porosity_comparison', {}).get('selected', '?')}"
        ),
        "sw": lambda: f"Water saturation: {ledger.get('sw_summary', {}).get('method', '?')}",
        "zonation": lambda: f"Zonation: {len(ledger.get('zones', []))} net-pay intervals",
        "results": lambda: f"Results: net pay {ledger.get('net_pay_total_m', '?')} m",
        "uncertainty": lambda: "Uncertainty: Monte Carlo P10/P50/P90",
        "permeability": lambda: f"Permeability: {[k for k in tr if k.startswith('perm_')]}",
        "rock_quality": lambda: "Rock quality (uncalibrated)",
        "electrofacies": lambda: "Electrofacies (k-means)",
        "lithology": lambda: "Lithology",
        "derived_parameters": lambda: "Derived parameters (BVW)",
    }
    for i, sid in enumerate(order, 1):
        fn = summaries.get(sid)
        lines.append(f"{i}. {fn() if fn else sid}")
    if not order:
        lines.append("(no analysis sections built yet)")
    return lines


# What each validator's objection is COMPUTED FROM (factual scope, per id — never a fix
# suggestion). A generic legend once claimed "no method/zone can fix" for ALL irreducible
# objections; that is true for raw-data checks but FALSE for interval-scoped ones, and a
# false universal is disinformation, not honesty.
_OBJECTION_SCOPE: dict[str, str] = {
    "net_pay_plausibility": (
        "computed from the net-pay summary over the CURRENT analysis interval "
        "(full logged interval unless restricted)"
    ),
    "rt_sw_consistency": "computed sample-by-sample from raw RT vs the computed Sw",
    "model_mismatch_nd": "computed from raw RHOB/NPHI character (data quality)",
    "vsh_phie_anticorrelation": "computed from the correlation of the computed Vsh vs PHIE",
    "vsh_bounds": "computed from the computed Vsh against its physical bounds",
    "phie_bounds": "computed from the computed PHIE against its physical bounds",
    "sw_bounds": "computed from the computed Sw against its physical bounds",
    "cross_tool_consistency": "computed by cross-checking optional tool results vs the core",
}


def _diagnostics(ledger: dict[str, Any]) -> dict[str, Any]:
    """The red-flag signals the analyst must see: validator objections, net-pay summary, status.

    Surfaced from the current ledger, not recomputed (pass-0's gate in baseline mode; absent
    until the chain exists in author mode — ``finalize_run`` writes the final verdict).
    """
    run = ledger.get("run", {})
    objs = [
        {
            "validator": o.get("validator_id"),
            "type": o.get("type") or o.get("objection_type"),
            "detail": o.get("detail"),
            "computed_from": _OBJECTION_SCOPE.get(o.get("validator_id", ""), "see validator"),
        }
        for o in ledger.get("objections", [])
    ][:6]
    s = ledger.get("summary", {})
    summary = {
        k: s[k] for k in ("gross_m", "ntg", "avg_phie", "avg_sw", "avg_vsh") if s.get(k) is not None
    }
    return {
        "objections": objs or "none",
        "objections_legend": (
            "type 'irreducible' = cannot be fixed by choosing a different METHOD — note it and "
            "MOVE ON rather than looping; what each objection DEPENDS ON is stated in its "
            "computed_from. 'mechanical' = may improve with a better method (try ONCE); "
            "'support' = info."
        ),
        "net_pay_summary": summary or "not computed yet",
        "convergence": {
            "status": run.get("convergence_status"),
            "abstain": run.get("abstain"),
            "reasons": run.get("abstain_reasons", []),
        },
    }


def observation_text(
    ledger: dict[str, Any],
    valid: set[str],
    actions: list[str],
    order: list[str] | None = None,
    last_obs: dict[str, Any] | None = None,
    field_context: dict[str, Any] | None = None,
    case_file: str | None = None,
    regional_brief: str | None = None,
    journal: list[dict[str, Any]] | None = None,
    prior_attempt: str | None = None,
) -> str:
    """STATE digest + the report-in-progress (so the agent sees the document it is building).

    The agent reasons over summarized data (zone/distribution/point on request; never raw arrays)
    AND a compact outline of the sections built so far — concrete grounding for what to add or
    refine and when to finish. ``last_obs`` carries the result of the observation the agent just
    requested, so a read (e.g. depth_quality) feeds the next decision instead of being discarded.
    """
    cal = ledger.get("calibration", {})
    computed = {
        "vsh": {"in": "vsh" in valid, "method": cal.get("vsh_method", {}).get("value")},
        "phie": {"in": "phie" in valid},
        "sw": {"in": "sw" in valid, "mean": ledger.get("sw_summary", {}).get("mean_sw")},
        "netpay": {"in": "netpay" in valid, "net_pay_m": ledger.get("net_pay_total_m")},
        "uncertainty": {"in": "uncertainty" in valid},
    }
    stale = [p for p in ("vsh", "phie", "sw", "netpay", "uncertainty") if p not in valid]
    done_tools = set(ledger.get("tool_results", {}))
    optionals_available = [
        a
        for a in (
            "permeability",
            "rock_quality",
            "electrofacies",
            "lithology",
            "derived_parameters",
        )
        if a in actions and not (done_tools & _OPTIONAL_TOOLS.get(a, set()))
    ]
    # Order matters: critical fields FIRST so the 5200-char cap only ever trims the verbose tail
    # (report_so_far, eda) — never valid_actions or the diagnostics the agent decides on.
    state = {
        "valid_actions": actions,
        "diagnostics": _diagnostics(ledger),
        "last_observation": last_obs or "none yet (call an observation to inspect the data)",
        # GC-3: the agent's own PRIOR attempt on this well (decisions + measured outcome) —
        # consequence as evidence, never direction; what to change is the agent's call.
        **({"your_prior_attempt_on_this_well": prior_attempt[:1200]} if prior_attempt else {}),
        # GB-1: every read already executed this well (repeating one is a measured no-op)
        **({"observations_so_far": journal} if journal else {}),
        "computed": computed,
        "stale_or_pending": stale,
        # factual affordance: what each still-available optional COMPUTES (never a nudge to add it)
        "optionals_not_yet_added": {a: _OPTIONAL_DESC.get(a, a) for a in optionals_available},
        "zone_of_interest": ledger.get("zone_of_interest", "full logged interval (not restricted)"),
        "baseline_complete": not stale,
        # GA-1: the field-study evidence pack (engine medians/tops facts; interpretation is the
        # agent's). GA-4: the agent's own notes from prior wells in this batch.
        **({"field_context": field_context} if field_context else {}),
        **({"your_prior_field_notes": case_file[-2500:]} if case_file else {}),
        # GA-5: cited background DATA (author mode only); facts with source class, never a nudge.
        **({"regional_reference": regional_brief[:1800]} if regional_brief else {}),
        "report_so_far": _report_outline(ledger, order or []),
        "eda": ledger.get("run", {}).get("eda", {}),
        "hint": "A MECHANICAL objection MIGHT improve with a different vetted method (try at most "
        "once). An IRREDUCIBLE objection cannot be fixed by another METHOD — do NOT retry methods "
        "for it; what it depends on is in its computed_from. Optional analyses do not need "
        "convergence. Pick 'finish' when your choices are made.",
    }
    return "STATE:\n" + json.dumps(state, indent=1, default=str)[:6500]


# Factual one-liners: WHAT each optional computes + its inputs (an affordance, not a nudge).
_OPTIONAL_DESC: dict[str, str] = {
    "permeability": "Timur/Coates permeability from PHIE+Sw (uncalibrated screen, no core)",
    "rock_quality": "RQI/FZI/Winland rock-quality indices from PHIE+permeability",
    "electrofacies": "unsupervised k-means facies from GR/RHOB/NPHI",
    "lithology": "density-neutron crossplot matrix point-shares",
    "derived_parameters": "bulk-volume water (BVW = PHIE*Sw)",
}

_OPTIONAL_TOOLS: dict[str, set[str]] = {
    "permeability": {"perm_timur", "perm_coates"},
    "rock_quality": {"rqi", "fzi", "winland_r35"},
    "electrofacies": {"electrofacies"},
    "lithology": {"litho_nd_crossplot"},
    "derived_parameters": {"bvw"},
}


def _seed_order(valid: set[str]) -> list[str]:
    """Seed the section order with the baseline sections (the report the agent starts to refine)."""
    order: list[str] = []
    for prop in ("vsh", "phie", "sw", "netpay", "uncertainty"):
        if prop in valid:
            order.extend(s for s in _PROP_SECTIONS.get(prop, ()) if s not in order)
    return order


def _done_optionals(ledger: dict[str, Any]) -> frozenset[str]:
    """Optional actions whose tool result already exists."""
    done = set(ledger.get("tool_results", {}))
    return frozenset(a for a, tools in _OPTIONAL_TOOLS.items() if done & tools)


_DEFAULT_METHOD = {"compute_phie": "phie_density_neutron", "compute_sw": "sw_archie"}


def _current_method(prop: str, ledger: dict[str, Any]) -> Any:
    if prop == "vsh":
        return ledger.get("calibration", {}).get("vsh_method", {}).get("value")
    if prop == "phie":
        return ledger.get("porosity_comparison", {}).get("selected")
    if prop == "sw":
        return ledger.get("sw_summary", {}).get("method")
    return None


def _is_noop(
    action: str,
    method: str | None,
    ledger: dict[str, Any],
    ctx: dict[str, Any],
    valid: set[str],
    args: dict[str, Any] | None = None,
) -> bool:
    """A no-op: re-add a done optional, recompute a VALID core property with the SAME method, or
    re-restrict to the SAME zone of interest.

    Offered (not hidden) so the model's choice is measured; the loop skips + counts them as wasted
    steps — a competence signal, not scaffolding that does the model's thinking. A STALE property
    (invalidated by an upstream recompute) is never a no-op — it must be recomputed.
    """
    if action in _OPTIONAL_TOOLS and action in _done_optionals(ledger):
        return True
    if action == "set_zone_of_interest":
        zoi, a = ctx.get("zoi"), args or {}
        if zoi is not None and a.get("top") is not None and a.get("bottom") is not None:
            # re-restricting to the same interval just recomputes the same baseline -> wasted
            return abs(float(a["top"]) - zoi[0]) < 1.0 and abs(float(a["bottom"]) - zoi[1]) < 1.0
        return False
    if action in ("compute_vsh", "compute_phie", "compute_sw"):
        prop = PRODUCES[action]
        if prop not in valid:  # stale -> recomputing it is necessary, not wasted
            return False
        default = _DEFAULT_METHOD.get(action) or default_vsh_key(ctx["variant"])
        chosen = method or default
        current = _current_method(prop, ledger)
        if current is None:
            return False
        # No-op if the same method, OR the property was already refined off its default — the prompt
        # allows refining a core property AT MOST ONCE, so a second refinement is wasted (it also
        # stops capable models from rabbit-holing on a data-driven objection no method can fix).
        return chosen == current or current != default
    return False


def _obs_key(action: str, choice: dict[str, Any]) -> str:
    args = json.dumps(choice.get("args") or {}, sort_keys=True, default=str)
    return f"{action}|{args}|{choice.get('method') or ''}"


def _journal_add(
    journal: dict[str, dict[str, Any]],
    epoch: int,
    action: str,
    choice: dict[str, Any],
    summary: dict[str, Any],
) -> None:
    """Record an executed read in the within-well journal (GB-1). Compact: one line per read."""
    journal[_obs_key(action, choice)] = {
        "epoch": epoch,
        "action": action,
        "args": choice.get("args") or {},
        "summary": json.dumps(summary, default=str)[:220],
    }


def _journal_view(journal: dict[str, dict[str, Any]], limit: int = 12) -> list[dict[str, Any]]:
    """The journal as the agent sees it: newest-last, capped, without epochs."""
    entries = list(journal.values())[-limit:]
    return [
        {
            "action": e["action"],
            **({"args": e["args"]} if e["args"] else {}),
            "summary": e["summary"],
        }
        for e in entries
    ]


def _track_read(
    journal: dict[str, dict[str, Any]],
    epoch: int,
    action: str,
    choice: dict[str, Any],
    summary: dict[str, Any],
) -> int:
    """Journal a read; a state-changing action instead bumps the epoch (old reads re-readable)."""
    if PRODUCES.get(action) is None and action != "set_zone_of_interest":
        _journal_add(journal, epoch, action, choice, summary)
        return epoch
    return epoch + 1


def _skip_reason(
    action: str,
    choice: dict[str, Any],
    ledger: dict[str, Any],
    ctx: dict[str, Any],
    valid: set[str],
    journal: dict[str, dict[str, Any]],
    epoch: int,
) -> dict[str, Any] | None:
    """A no-op verdict for this choice: compute no-op, or a same-epoch REPEAT of a read (GB-1).

    Repeats were the dominant v11 waste (~80% of observations): with only ``last_observation``
    in view the models re-bought evidence they already owned. The journal makes the read visible
    and the repeat a measured no-op — after a state-changing action the same read is valid again.
    """
    if _is_noop(action, choice.get("method"), ledger, ctx, valid, choice.get("args")):
        return {
            "repeat": False,
            "obs": {
                "action": action,
                "result": f"NO-OP: '{action}' had no effect — already done, same method, or same "
                "zone. Pick a DIFFERENT action (an optional analysis) or finish.",
            },
        }
    if PRODUCES.get(action) is not None or action == "set_zone_of_interest":
        return None
    ent = journal.get(_obs_key(action, choice))
    if ent is None or ent["epoch"] != epoch:
        return None
    return {
        "repeat": True,
        "obs": {
            "action": action,
            "result": "NO-OP repeat: you already own this read — its summary is in "
            "observations_so_far. Pick a DIFFERENT action or finish.",
            "cached_summary": ent["summary"],
        },
    }


def _obs_result(action: str, summary: dict[str, Any]) -> dict[str, Any] | None:
    """The result to surface next turn if ``action`` was a read-only observation, else None."""
    if action not in PRODUCES and action != "set_zone_of_interest":
        return {"action": action, "result": summary}
    return None


def _default_next(valid: set[str], curves: set[str]) -> str | None:
    """The per-step fallback: the next canonical action whose prereqs are met, else finish."""
    acts = available_actions(valid, curves)
    for a in _DEFAULT_ORDER:
        if a in acts and PRODUCES[a] not in valid:
            return a
    return "finish" if "finish" in acts else None


def _decide(
    obs: str,
    actions: list[str],
    valid: set[str],
    curves: set[str],
    chats: list[tuple[Any, str]],
    system: str = _LOOP_SYSTEM,
) -> tuple[dict[str, Any], int, bool]:
    """Ask the model cascade for the next action; fall back to the canonical default (signaled).

    Returns ``(choice, empty_returns, from_default)`` — ``from_default`` is True when the model gave
    nothing usable and the deterministic canonical step was substituted, so the caller can keep a
    base-by-fallback step distinct from a step the agent actually chose.
    """
    empty = 0
    for c, _mdl in chats:
        if c is None:
            continue
        raw = c(system, obs)
        if not raw or not raw.strip():
            empty += 1
            continue
        choice = parse_action(raw, actions)
        if choice is not None:
            return choice, empty, False
    nxt = _default_next(valid, curves)
    return ({"action": nxt} if nxt else {"action": "finish"}), empty, True


def _record_step(graph: MethodologyGraph, action: str, from_default: bool) -> None:
    """Add the decision node, labeling a deterministic-default step apart from an agent step."""
    tag = "DETERMINISTIC DEFAULT (model empty)" if from_default else "step"
    graph.add("decision", {"rationale": f"{tag}: {action}", "chosen": action})


def _extend_order(order: list[str], action: str) -> None:
    """Append (in order, no duplicates) the report section ids the action's property produces."""
    prop = PRODUCES.get(action)
    if not prop:
        return
    for sid in _PROP_SECTIONS.get(prop, ()):
        if sid not in order:
            order.append(sid)


def _is_stalled(recent: list[str]) -> bool:
    """Anti-stall signal: the last 3 chosen actions are identical (an unproductive loop)."""
    return len(recent) >= 3 and len(set(recent[-3:])) == 1


def _completeness_critique(ledger: dict[str, Any], actions: list[str]) -> dict[str, Any] | None:
    """A NEUTRAL completeness surface shown ONCE when the agent tries to finish.

    States, factually, which applicable optional analyses are not yet added and which core
    properties still use the DEFAULT method — so the agent reconsiders whether the report is
    genuinely complete. It never says WHICH to add or which method to use (that is the analyst's).
    Returns None when nothing applicable is left undone.
    """
    done = set(ledger.get("tool_results", {}))
    unadded = [
        a
        for a in (
            "permeability",
            "rock_quality",
            "electrofacies",
            "lithology",
            "derived_parameters",
        )
        if a in actions and not (done & _OPTIONAL_TOOLS.get(a, set()))
    ]
    default_core = []
    if not ledger.get("calibration", {}).get("vsh_method", {}).get("chosen_by_model"):
        default_core.append("vsh")
    if ledger.get("porosity_comparison", {}).get("method_source") != "agent":
        default_core.append("phie")
    if ledger.get("sw_summary", {}).get("method_source") != "agent":
        default_core.append("sw")
    if not unadded and not default_core:
        return None
    return {
        "action": "completeness_check",
        "note": "Before finishing — a factual completeness check (NOT a directive): applicable "
        f"analyses not yet added: {unadded or 'none'}; core properties still on the DEFAULT "
        f"method: {default_core or 'none'}. Decide whether the analysis is genuinely complete "
        "for this well — add what the DATA support, or finish.",
    }


_SKEPTIC_SYSTEM = """You are a SKEPTICAL senior petrophysicist reviewing another analyst's
IN-PROGRESS choices on a well, BEFORE the report is finalized. You see the analyst's key CHOICES
(methods picked, interval restricted or not, optional analyses added or omitted) and qualitative
evidence (validator objections, curves present, confidence tier). Try to REFUTE those choices:
where does the DATA fail to justify a method chosen, an interval kept or restricted, or an analysis
included or left out?

Rules: QUESTION, do NOT prescribe — ask "is X justified by the data?", never "use method Y" or
"conclude Z". Never mention or invent a number (numbers are computed and checked elsewhere). If the
choices are well justified by the evidence, return no objections.

Return ONLY a JSON object: {"objections": ["...", "..."]}  (empty list if the choices hold up)."""


def _choices_digest(ledger: dict[str, Any]) -> dict[str, Any]:
    """Qualitative summary of the analyst's decisions (method ids, zone, optionals) — no numbers."""
    cal = ledger.get("calibration", {})
    return {
        "vsh_method": cal.get("vsh_method", {}).get("value"),
        "phie_method": ledger.get("porosity_comparison", {}).get("selected"),
        "sw_method": ledger.get("sw_summary", {}).get("method"),
        "zone": ledger.get("zone_of_interest") or "full logged interval (not restricted)",
        "optional_analyses_added": sorted(ledger.get("tool_results", {})),
    }


def _skeptic_evidence(ledger: dict[str, Any]) -> dict[str, Any]:
    """Qualitative evidence the skeptic grounds objections in (validator flags, curves, tier)."""
    objs = [
        o.get("detail") or o.get("type") or o.get("objection_type")
        for o in ledger.get("objections", [])
    ]
    run = ledger.get("run", {})
    return {
        "validator_objections": objs[:6] or "none",
        "curves_present": run.get("eda", {}).get("curves_present"),
        "confidence_tier": run.get("confidence_tier"),
    }


def _parse_objections(raw: str) -> list[str] | None:
    """Extract the skeptic's objection list from model output; None if unusable."""
    if not raw or not raw.strip():
        return None
    m = _OBJ.search(raw)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except (ValueError, TypeError):
        return None
    obj = data.get("objections") if isinstance(data, dict) else None
    return [str(x) for x in obj][:6] if isinstance(obj, list) else None


def _skeptic_pass(ledger: dict[str, Any], chats: list[Any]) -> list[str] | None:
    """Same-model one-shot adversarial pass over the analyst's CHOICES (never the numbers).

    The analyst's OWN model plays skeptic and tries to refute its choices, grounded in qualitative
    evidence. Returns a non-empty objection list, or None (no objections / no usable model). It
    questions, never prescribes; the orchestrator still owns the loop (the LLM decides no gate).
    """
    user = (
        "Analyst choices:\n"
        + json.dumps(_choices_digest(ledger), default=str)[:1500]
        + "\n\nEvidence:\n"
        + json.dumps(_skeptic_evidence(ledger), default=str)[:2000]
    )
    for chat, _model in chats:
        if chat is None:
            continue
        try:
            obj = _parse_objections(chat(_SKEPTIC_SYSTEM, user))
        except Exception:
            continue
        if obj is not None:
            return obj or None
    return None


def _finish_review(
    ledger: dict[str, Any], actions: list[str], chats: list[Any]
) -> dict[str, Any] | None:
    """One-shot pre-finish review = neutral completeness surface + same-model skeptic objections.

    Returns a combined observation the analyst reconsiders once, or None when nothing is worth it.
    """
    comp = _completeness_critique(ledger, actions)
    objs = _skeptic_pass(ledger, chats)
    if comp is None and objs is None:
        return None
    review: dict[str, Any] = {"action": "finish_review"}
    if comp is not None:
        review["completeness"] = comp["note"]
    if objs is not None:
        review["skeptic_objections"] = objs
    review["decide"] = (
        "A skeptic questioned your CHOICES and a completeness check ran. Address what the DATA "
        "support (revise a choice, add a backed analysis, or restrict the interval), or finish."
    )
    return review


def _record_tool_call(
    graph: MethodologyGraph, action: str, args: dict[str, Any], method: str | None = None
) -> None:
    """Add the tool_call node, pointing result_ledger_key at the REAL ledger key it wrote.

    ``method`` is the vetted method id the agent selected — recorded so the trace shows WHICH
    method was picked, not just that the action ran (the v6 audit had to reverse-engineer it).
    Observations are read-only and write nothing, so their node claims no key (the graph's
    self-check flagged ``ledger:<action> not in ledger`` because the action name is never a key).
    """
    payload: dict[str, Any] = {"tool": action, "args": args}
    if method:
        payload["method"] = method
    key = _ACTION_LEDGER_KEY.get(action)
    if key:
        payload["result_ledger_key"] = f"ledger:{key}"
    graph.add("tool_call", payload)


def _persist_ledger(ledger: dict[str, Any], out_dir: str | None) -> None:
    """Overwrite ``<out_dir>/<uwi>_ledger.json`` with the post-loop ledger.

    Pass-0's ``emit`` writes a pre-loop snapshot; without this re-write the agent's
    interpretive choices (sw_summary, vsh/porosity comparisons, run.analyst_loop,
    run.methodology_graph) would be unauditable from the persisted artifact.
    Delegates to the orchestrator's ``persist_ledger`` (single serializer).
    """
    persist_ledger(ledger, out_dir)


def _prepare_loop(ledger: dict[str, Any], ctx: dict[str, Any], author: bool) -> str:
    """Pre-loop setup: EDA digest + (baseline mode only) section seeding; returns the system prompt.

    Author mode skips ``seed_baseline_sections`` — seeding would fabricate "selected" labels for
    choices nobody made — and frames the agent as the AUTHOR of the interpretation.
    """
    # Build the EDA digest the agent reads (the loop path never populated it -> agent was blind).
    ledger.setdefault("run", {})["eda"] = build_eda_digest(ctx)
    if author:
        return _LOOP_SYSTEM_AUTHOR
    # Seed the [FIJO] Vsh/Porosity/Sw section keys from the baseline (render without a recompute).
    seed_baseline_sections(ledger, ctx)
    return _LOOP_SYSTEM


def run_analyst_loop(
    ledger: dict[str, Any],
    ctx: dict[str, Any],
    mode: str,
    chat: ChatFn,
    model: str,
    fallback_chat: ChatFn | None = None,
    fallback_model: str = "",
    max_steps: int = 12,
    author: bool = False,
    field_context: dict[str, Any] | None = None,
    case_file: str | None = None,
    regional_brief: str | None = None,
    prior_attempt: str | None = None,
) -> dict[str, Any]:
    """Run the observe→decide→compute loop; return ``{section_plan, graph, fell_back}``.

    Records ``ledger.run.analyst_loop`` (steps_taken, finished_by_agent, hit_max_steps, recomputes,
    empty_returns) and ``ledger.run.methodology_graph`` (the step-by-step trace).

    With ``author=True`` (R14: the descriptive pass-0 computed no interpretation) the agent is
    framed as the AUTHOR of the interpretation and the baseline section seeding is skipped —
    seeding would fabricate "selected" labels for choices nobody made. The deterministic per-step
    fallback and the post-loop re-close are unchanged (they close the chain for weak models).
    """
    graph = MethodologyGraph(mode=mode, model=model)
    curves = set(ctx["curves"])
    valid = _initial_valid(ctx, ledger)
    order = _seed_order(valid)
    system = _prepare_loop(ledger, ctx, author)
    steps_taken = recomputes = empty_returns = wasted = observation_steps = 0
    agent_steps = default_steps = repeated_observations = 0
    journal: dict[str, dict[str, Any]] = {}
    epoch = 0
    # Vision track: offer examine_figures only when a vision chat + figures are wired into ctx.
    vision_on = bool(ctx.get("vision_chat") and ctx.get("figure_paths"))
    finished = False

    chats = [(chat, model), (fallback_chat, fallback_model)]
    recent: list[str] = []
    stalled = False
    reviewed = False
    last_obs: dict[str, Any] | None = None
    for _ in range(max_steps):
        actions = available_actions(
            valid, curves, vision=vision_on
        )  # offer everything; no-ops are measured, not hidden
        obs = observation_text(
            ledger,
            valid,
            actions,
            order,
            last_obs,
            field_context,
            case_file,
            regional_brief if author else None,  # GA-5: background data is an author-mode input
            _journal_view(journal),
            prior_attempt,
        )
        choice, empty, from_default = _decide(obs, actions, valid, curves, chats, system)
        empty_returns += empty
        action = choice["action"]
        if action == "finish":
            # One-shot pre-finish review: neutral completeness surface + same-model skeptic (R13).
            review = None if reviewed else _finish_review(ledger, actions, chats)
            reviewed = True
            if review is not None:
                last_obs = review
                continue
            finished = True
            break
        # Orchestrator-owned anti-stall: 3 identical actions in a row = unproductive loop -> stop.
        recent.append(action)
        if _is_stalled(recent):
            stalled = True
            break
        # No-op (compute repeat) or same-epoch observation repeat (GB-1): record + skip.
        skip = _skip_reason(action, choice, ledger, ctx, valid, journal, epoch)
        if skip is not None:
            wasted += 1
            repeated_observations += int(skip["repeat"])
            graph.add("decision", {"rationale": f"wasted no-op: {action}", "chosen": action})
            last_obs = skip["obs"]
            continue

        default_steps += int(from_default)
        agent_steps += int(not from_default)
        _record_step(graph, action, from_default)
        if PRODUCES.get(action) in valid:
            recomputes += 1
        _summary, valid = execute_step(
            action, ctx, ledger, valid, choice.get("method"), choice.get("args")
        )
        # Feed an observation's result into the next decision (reads are no longer fire-and-forget).
        last_obs = _obs_result(action, _summary) or last_obs
        epoch = _track_read(journal, epoch, action, choice, _summary)
        _record_tool_call(graph, action, choice.get("args", {}), choice.get("method"))
        _extend_order(order, action)
        steps_taken += 1
        # read-only step counter (GA-2: commitment is measured, not assumed)
        observation_steps += int(PRODUCES.get(action) is None and action != "set_zone_of_interest")
        _maybe_revalidate(action, valid, ledger, ctx)

    # ----------------------------------------
    # Step — Deterministic re-close of the stale core chain
    # ----------------------------------------
    # A core recompute (the agent's method choice) invalidates its downstream; if the loop ends
    # before the agent re-runs the chain, the report would render pass-0 numbers next to the
    # recomputed property (internally inconsistent). The ORCHESTRATOR re-closes with canonical
    # defaults so the agent's upstream choice propagates — no LLM decides anything here. One pass
    # over _DEFAULT_ORDER suffices: it is topological (vsh -> phie -> sw -> cutoffs -> uncertainty).
    reclosed: list[str] = []
    for stale_action in _DEFAULT_ORDER:
        if PRODUCES[stale_action] in valid or stale_action not in available_actions(valid, curves):
            continue
        graph.add(
            "decision",
            {
                "rationale": f"DETERMINISTIC RECLOSE (stale chain): {stale_action}",
                "chosen": stale_action,
            },
        )
        _summary, valid = execute_step(stale_action, ctx, ledger, valid, None, None)
        _record_tool_call(graph, stale_action, {})
        reclosed.append(stale_action)

    # Finalize: cross-tool consistency of the agent's optional results vs the core (a contradiction
    # becomes a MECHANICAL objection). NOTE: re-running the full validator harness on a recomputed
    # core is a follow-up — the pass-0 objections/tier reflect the default interpretation.
    cross_objs = cross_tool_consistency(ledger)
    if cross_objs:
        ledger.setdefault("objections", []).extend(
            {"validator_id": o.validator_id, "type": o.objection_type, "detail": o.detail}
            for o in cross_objs
        )

    field_notes = _write_field_notes(ledger, chats, author)
    ledger.setdefault("run", {})["analyst_loop"] = {
        "steps_taken": steps_taken,
        "agent_steps": agent_steps,
        "default_steps": default_steps,
        "finished_by_agent": finished,
        "hit_max_steps": steps_taken >= max_steps and not finished and not stalled,
        "stalled": stalled,
        "recomputes": recomputes,
        "wasted_steps": wasted,
        "empty_returns": empty_returns,
        "reclosed_steps": reclosed,
        "vision_enabled": vision_on,
        "author_mode": author,
        "observation_steps": observation_steps,
        "repeated_observations": repeated_observations,
        "field_notes": field_notes,
    }
    ledger["run"]["methodology_graph"] = graph.to_json()
    # Re-persist: pass-0's emit wrote a pre-loop snapshot; the agent's choices must be auditable.
    _persist_ledger(ledger, ctx.get("out_dir"))
    return {
        "section_plan": {"sections": order, "optional_sections": _optionals_in(order)},
        "graph": graph,
        # fell_back means the agent contributed NO decision of its own (every executed step was the
        # deterministic default) — a 100%-default run must not read as the agent's analysis.
        "fell_back": agent_steps == 0,
        "field_notes": field_notes,
    }


# GA-4 writer contract: the agent's OWN words, qualitative only. Numbers are scrubbed
# mechanically afterwards — the ledger holds the numbers; notes hold the judgement.
_NOTES_SYSTEM = """You are the same analyst closing your field notebook for this well. Write a
SHORT field note (max 120 words, plain text) that you — on the NEXT well of this field — will read
before starting. QUALITATIVE only: what you chose and why, what surprised you, what you would
watch for next time. HEDGE anything uncertain (this is one well, not the field). Write NO numbers
— any digit you write will be removed. Do not tell your future self what to decide; record what
you saw and judged here."""

_DIGITS = re.compile(r"\d+(?:\.\d+)?")


def _write_field_notes(
    ledger: dict[str, Any], chats: list[tuple[ChatFn | None, str]], author: bool
) -> str | None:
    """One-shot field note at author finish (GA-4): the agent's own qualitative words.

    The engine hands only ledger-derived facts as context; the reply is mechanically scrubbed of
    every number (notes feed the NEXT wells' observations, and an unledgered number must never
    propagate). Returns None outside author mode or when no chat backend answers.
    """
    if not author:
        return None
    summary = {
        "vsh_method": ledger.get("vsh_comparison", {}).get("selected"),
        "phie_method": ledger.get("porosity_comparison", {}).get("selected"),
        "sw_method": ledger.get("sw_summary", {}).get("method"),
        "zone_of_interest_set": ledger.get("zone_of_interest") is not None,
        "n_zones": len(ledger.get("zones") or []),
        "objections": [o.get("validator_id") for o in ledger.get("objections", [])][:6],
        "optional_analyses": sorted((ledger.get("tool_results") or {}).keys()),
    }
    for fn, _model in chats:
        if fn is None:
            continue
        try:
            raw = str(fn(_NOTES_SYSTEM, json.dumps(summary))).strip()
        except Exception:  # noqa: BLE001 — notes are best-effort; the run must not die here
            continue
        if raw:
            return _DIGITS.sub("[n]", raw)[:900]
    return None


def _optionals_in(order: list[str]) -> list[str]:
    opt = {
        "shaly_sand_saturation",
        "sonic_porosity",
        "permeability",
        "rock_quality",
        "electrofacies",
        "derived_parameters",
    }
    return [s for s in order if s in opt]
