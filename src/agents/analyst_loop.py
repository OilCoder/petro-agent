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

_LOOP_SYSTEM = """You are a senior petrophysical ANALYST refining a well report STEP BY STEP.
A BASELINE interpretation (vsh, phie, sw, net pay, uncertainty) is ALREADY computed with default
methods. Each turn you see the STATE and the VALID ACTIONS; choose exactly ONE next action.

Your job, in order:
0. CHECK the interval first with the "depth_quality" observation. If the top is non-reservoir
   OVERBURDEN (low RHOB / high frac_rhob_below_2 = not consolidated rock), restrict to the reservoir
   with set_zone_of_interest, args {"top": <m>, "bottom": <m>} (recomputes the baseline over that
   zone). Do this BEFORE refining methods.
1. OPTIONALLY recompute a core property with a BETTER method for this rock (e.g. a shaly-sand Sw
   model when Vsh is high) — at most once per property, only when justified by the data.
2. ADD the optional analyses that add value (permeability, rock_quality, electrofacies, lithology,
   derived_parameters).
3. Then pick "finish".

Output ONLY a JSON object: {"action": "<id>", "method": "<optional method id>", "args": {}}.
Use an id from VALID ACTIONS only. Do NOT repeat the same action; do NOT recompute a property you
already chose a method for. Prefer "finish" once your choices are made. You never compute a number —
the engine does; you decide the method and the order. Never write a number; never invent an id."""

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


def _diagnostics(ledger: dict[str, Any]) -> dict[str, Any]:
    """The red-flag signals the analyst must see: validator objections, net-pay summary, status.

    All already computed by pass-0 (validate/zonate/gating) — surfaced, not recomputed.
    """
    run = ledger.get("run", {})
    objs = [
        {
            "validator": o.get("validator_id"),
            "type": o.get("type") or o.get("objection_type"),
            "detail": o.get("detail"),
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
            "type 'irreducible' = a DATA limitation no method/zone can fix — note it and MOVE ON; "
            "'mechanical' = may improve with a better method (try ONCE); 'support' = informational. "
            "Do NOT loop trying to resolve an irreducible objection."
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
    stale = [p for p in ("phie", "sw", "netpay", "uncertainty") if p not in valid]
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
        "computed": computed,
        "stale_or_pending": stale,
        "optionals_not_yet_added": optionals_available,
        "zone_of_interest": ledger.get("zone_of_interest", "full logged interval (not restricted)"),
        "baseline_complete": not stale,
        "report_so_far": _report_outline(ledger, order or []),
        "eda": ledger.get("run", {}).get("eda", {}),
        "hint": "check diagnostics FIRST: if an objection flags an implausible value (e.g. PHIE "
        "too high) or the well did not converge, consider restricting the zone "
        "(set_zone_of_interest) or recomputing a core property with a better method. Then add the "
        "optionals worth adding; finish.",
    }
    return "STATE:\n" + json.dumps(state, indent=1, default=str)[:5200]


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
        default = _DEFAULT_METHOD.get(action) or f"vsh_larionov_{ctx['variant']}"
        chosen = method or default
        current = _current_method(prop, ledger)
        if current is None:
            return False
        # No-op if the same method, OR the property was already refined off its default — the prompt
        # allows refining a core property AT MOST ONCE, so a second refinement is wasted (it also
        # stops capable models from rabbit-holing on a data-driven objection no method can fix).
        return chosen == current or current != default
    return False


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
    obs: str, actions: list[str], valid: set[str], curves: set[str], chats: list[tuple[Any, str]]
) -> tuple[dict[str, Any], int]:
    """Ask the model cascade for the next action; fall back to the canonical default (signaled)."""
    empty = 0
    for c, _mdl in chats:
        if c is None:
            continue
        raw = c(_LOOP_SYSTEM, obs)
        if not raw or not raw.strip():
            empty += 1
            continue
        choice = parse_action(raw, actions)
        if choice is not None:
            return choice, empty
    nxt = _default_next(valid, curves)
    return ({"action": nxt} if nxt else {"action": "finish"}), empty


def run_analyst_loop(
    ledger: dict[str, Any],
    ctx: dict[str, Any],
    mode: str,
    chat: ChatFn,
    model: str,
    fallback_chat: ChatFn | None = None,
    fallback_model: str = "",
    max_steps: int = 12,
) -> dict[str, Any]:
    """Run the observe→decide→compute loop; return ``{section_plan, graph, fell_back}``.

    Records ``ledger.run.analyst_loop`` (steps_taken, finished_by_agent, hit_max_steps, recomputes,
    empty_returns) and ``ledger.run.methodology_graph`` (the step-by-step trace).
    """
    graph = MethodologyGraph(mode=mode, model=model)
    curves = set(ctx["curves"])
    valid = _initial_valid(ctx, ledger)
    order = _seed_order(valid)
    # Build the EDA digest the agent reads (the loop path never populated it -> agent was blind).
    ledger.setdefault("run", {})["eda"] = build_eda_digest(ctx)
    # Seed the [FIJO] Vsh/Porosity/Sw section keys from the baseline (render without a recompute).
    seed_baseline_sections(ledger, ctx)
    steps_taken = recomputes = empty_returns = wasted = 0
    finished = False

    chats = [(chat, model), (fallback_chat, fallback_model)]
    recent: list[str] = []
    stalled = False
    last_obs: dict[str, Any] | None = None
    for _ in range(max_steps):
        actions = available_actions(
            valid, curves
        )  # offer everything; no-ops are measured, not hidden
        obs = observation_text(ledger, valid, actions, order, last_obs)
        choice, empty = _decide(obs, actions, valid, curves, chats)
        empty_returns += empty
        action = choice["action"]
        if action == "finish":
            finished = True
            break
        # Orchestrator-owned anti-stall: 3 identical actions in a row = unproductive loop -> stop.
        recent.append(action)
        if len(recent) >= 3 and len(set(recent[-3:])) == 1:
            stalled = True
            break
        # No-op (re-add a done optional / recompute same method): record + skip, keep report clean.
        if _is_noop(action, choice.get("method"), ledger, ctx, valid, choice.get("args")):
            wasted += 1
            graph.add("decision", {"rationale": f"wasted no-op: {action}", "chosen": action})
            # Tell the agent its choice had no effect so it stops repeating it (was looping blind).
            last_obs = {
                "action": action,
                "result": f"NO-OP: '{action}' had no effect — already done, same method, or same "
                "zone. Pick a DIFFERENT action (an optional analysis) or finish.",
            }
            continue

        graph.add("decision", {"rationale": f"step: {action}", "chosen": action})
        if PRODUCES.get(action) in valid:
            recomputes += 1
        _summary, valid = execute_step(
            action, ctx, ledger, valid, choice.get("method"), choice.get("args")
        )
        # Feed an observation's result into the next decision (reads are no longer fire-and-forget).
        last_obs = _obs_result(action, _summary) or last_obs
        graph.add(
            "tool_call",
            {
                "tool": action,
                "args": choice.get("args", {}),
                "result_ledger_key": f"ledger:{action}",
            },
        )
        prop = PRODUCES.get(action)
        if prop:
            for sid in _PROP_SECTIONS.get(prop, ()):
                if sid not in order:
                    order.append(sid)
        steps_taken += 1

    # Finalize: cross-tool consistency of the agent's optional results vs the core (a contradiction
    # becomes a MECHANICAL objection). NOTE: re-running the full validator harness on a recomputed
    # core is a follow-up — the pass-0 objections/tier reflect the default interpretation.
    cross_objs = cross_tool_consistency(ledger)
    if cross_objs:
        ledger.setdefault("objections", []).extend(
            {"validator_id": o.validator_id, "type": o.objection_type, "detail": o.detail}
            for o in cross_objs
        )

    ledger.setdefault("run", {})["analyst_loop"] = {
        "steps_taken": steps_taken,
        "finished_by_agent": finished,
        "hit_max_steps": steps_taken >= max_steps and not finished and not stalled,
        "stalled": stalled,
        "recomputes": recomputes,
        "wasted_steps": wasted,
        "empty_returns": empty_returns,
    }
    ledger["run"]["methodology_graph"] = graph.to_json()
    return {
        "section_plan": {"sections": order, "optional_sections": _optionals_in(order)},
        "graph": graph,
        "fell_back": steps_taken == 0,
    }


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
