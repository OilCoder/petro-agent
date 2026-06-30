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
from src.agents.loop_actions import PRODUCES, available_actions, execute_step
from src.agents.methodology_graph import MethodologyGraph
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
}
# Canonical default order for the per-step fallback (a competent baseline interpretation).
_DEFAULT_ORDER = ("compute_vsh", "compute_phie", "compute_sw", "apply_cutoffs", "run_uncertainty")

_LOOP_SYSTEM = """You are a senior petrophysical ANALYST building a well report STEP BY STEP.
Each turn you see the STATE (what is computed so far) and the VALID ACTIONS. Choose exactly ONE
next action, like a real analyst reacting to the data. You never compute a number — the engine
does; you decide the method and the order.

Output ONLY a JSON object: {"action": "<id>", "method": "<optional method id>",
"args": {<optional>}}. Use an action id from VALID ACTIONS (and a real method id when relevant).
Pick "finish" when the report is complete. You may RECOMPUTE a property with a different method if
the data warrants it (downstream is recomputed). Never write a number; never invent an id."""

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


def observation_text(ledger: dict[str, Any], valid: set[str], actions: list[str]) -> str:
    """Compact STATE digest for the agent (zone/distribution/point on request; never raw arrays)."""
    cal = ledger.get("calibration", {})
    computed = {
        "vsh": {"in": "vsh" in valid, "method": cal.get("vsh_method", {}).get("value")},
        "phie": {"in": "phie" in valid},
        "sw": {"in": "sw" in valid, "mean": ledger.get("sw_summary", {}).get("mean_sw")},
        "netpay": {"in": "netpay" in valid, "net_pay_m": ledger.get("net_pay_total_m")},
        "uncertainty": {"in": "uncertainty" in valid},
    }
    stale = [p for p in ("phie", "sw", "netpay", "uncertainty") if p not in valid]
    state = {
        "computed": computed,
        "stale_or_pending": stale,
        "eda": ledger.get("run", {}).get("eda", {}),
        "valid_actions": actions,
    }
    return "STATE:\n" + json.dumps(state, indent=1, default=str)[:3000]


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
    order: list[str] = []
    steps_taken = recomputes = empty_returns = 0
    finished = False

    chats = [(chat, model), (fallback_chat, fallback_model)]
    for _ in range(max_steps):
        actions = available_actions(valid, curves)
        obs = observation_text(ledger, valid, actions)
        choice, empty = _decide(obs, actions, valid, curves, chats)
        empty_returns += empty
        action = choice["action"]
        if action == "finish":
            finished = True
            break

        graph.add("decision", {"rationale": f"step: {action}", "chosen": action})
        if PRODUCES.get(action) in valid:
            recomputes += 1
        _summary, valid = execute_step(
            action, ctx, ledger, valid, choice.get("method"), choice.get("args")
        )
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
        "hit_max_steps": steps_taken >= max_steps and not finished,
        "recomputes": recomputes,
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
    }
    return [s for s in order if s in opt]
