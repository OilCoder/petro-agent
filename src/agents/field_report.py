"""Field-scale rollup (v2-native): cross-well statistics + the analyst's well selection.

Aggregates per-well ledgers into a field chapter with CROSS-WELL statistics (mean/median/range)
— never a summed thickness, which is meaningless as a field headline. The analyst agent selects
its own wells FREELY from a quality-aware inventory (the minimum base of information: % usable
depths, key curves, depth interval) — no fixed anchor. Every number is rendered from the per-well
ledgers by code; the LLM writes prose.
"""

from __future__ import annotations

import json
import re
import statistics
from typing import TYPE_CHECKING, Any

import numpy as np

from src.agents.client import ChatFn
from src.agents.report_template import _fmt
from src.qc.gate import GOOD, qc_gate

if TYPE_CHECKING:
    from src.io.loader import WellData

VERSION = "0.1.0"


# ----------------------------------------
# Step 1 — Analyst well selection (free, from a quality-aware inventory)
# ----------------------------------------

_SELECT_SYSTEM = """You are a petrophysical analyst choosing wells for a FIELD report.
You get the field inventory WITH data quality (% usable depths, key curves present, depth interval).
Select the wells that best serve the analysis: prefer interpretable wells (higher % usable, with
GR/RT/RHOB/NPHI); avoid wells flagged QC-abort/poor.
Output ONLY a JSON object: {"wells": ["<uwi>", ...], "rationale": "<why these, in terms of data
quality; words only, NO numbers>"}.
Use REAL uwis from the list. Never invent a uwi and never write a number."""

_OBJ = re.compile(r"\{.*\}", re.DOTALL)


def well_quality_summary(well: WellData) -> dict[str, Any]:
    """Cheap pre-selection quality signal for one well (no full pipeline).

    Runs the QC gate to get the usable fraction; on QC abort the well is marked not runnable.

    Returns:
        ``{pct_usable, runnable, key_curves, depth_top, depth_bottom}``.
    """
    key = [c for c in ("GR", "RT", "RHOB", "NPHI") if c in well.curves]
    depth = well.depth_m
    top = float(depth[0]) if depth.size else float("nan")
    bottom = float(depth[-1]) if depth.size else float("nan")
    try:
        res = qc_gate(well)
        n = res.quality_map.size
        pct = float(np.count_nonzero(res.quality_map == GOOD) / n) if n else 0.0
        runnable = True
    except ValueError:
        pct, runnable = 0.0, False
    return {
        "pct_usable": pct,
        "runnable": runnable,
        "key_curves": key,
        "depth_top": top,
        "depth_bottom": bottom,
    }


def field_well_inventory(metas: list[dict[str, Any]]) -> str:
    """Compact text inventory of the field's wells for the selection prompt.

    Includes data quality (``% usable``, key curves, depth interval) when a meta carries a
    ``quality`` summary; otherwise falls back to the curve list.
    """
    lines = []
    for m in metas:
        q = m.get("quality")
        if q:
            if q.get("runnable"):
                state = f"{q.get('pct_usable', 0.0):.0%} usable"
            else:
                state = "QC-abort/poor"
            curves = "/".join(q.get("key_curves", [])) or "—"
            lines.append(
                f"{m['uwi']}: {state}, curves={curves}, "
                f"{q.get('depth_top', float('nan')):.0f}-{q.get('depth_bottom', float('nan')):.0f}m"
            )
        else:
            lines.append(f"{m['uwi']}: curves={sorted(m['curves'])}")
    return "FIELD WELLS (with data quality):\n" + "\n".join(lines)


def select_field_wells(
    metas: list[dict[str, Any]],
    chat: ChatFn,
    max_wells: int = 4,
) -> dict[str, Any]:
    """Let the analyst freely pick the wells that serve the analysis (1..``max_wells``).

    No fixed anchor. Falls back deterministically (top wells by % usable) if the model returns
    no usable choice — always signaled via ``fell_back``.

    Returns:
        ``{selected, fell_back, rationale}``.
    """
    all_uwis = [m["uwi"] for m in metas]
    user = field_well_inventory(metas) + (
        f"\n\nSelect 1 to {max_wells} wells that serve the analysis."
    )
    raw = chat(_SELECT_SYSTEM, user)
    m = _OBJ.search(raw or "")
    choice: list[str] = []
    rationale = ""
    if m:
        try:
            data = json.loads(m.group(0))
            choice = [u for u in data.get("wells", []) if isinstance(u, str)]
            rationale = str(data.get("rationale", ""))
        except (ValueError, TypeError):
            choice = []
    sel = select_wells(all_uwis, choice, max_wells)
    fell_back = not sel["selected"]
    if fell_back:
        ranked = sorted(
            metas,
            key=lambda mm: (
                mm.get("quality", {}).get("runnable", False),
                mm.get("quality", {}).get("pct_usable", 0.0),
            ),
            reverse=True,
        )
        sel = {"selected": [mm["uwi"] for mm in ranked[:max_wells]]}
        rationale = "deterministic fallback (model selection unavailable): top wells by % usable"
    return {**sel, "fell_back": fell_back, "rationale": rationale}


def select_wells(
    all_uwis: list[str], model_choice: list[str], max_wells: int = 4
) -> dict[str, Any]:
    """Pick the field subset: up to ``max_wells`` valid, de-duplicated model-chosen wells.

    Args:
        all_uwis: every available well UWI.
        model_choice: the wells the model proposed (in priority order).
        max_wells: cap on how many wells to keep.

    Returns:
        ``{selected}`` — valid, de-duplicated, capped; unknown UWIs dropped.
    """
    valid = set(all_uwis)
    selected: list[str] = []
    for uwi in model_choice:
        if uwi in valid and uwi not in selected:
            selected.append(uwi)
        if len(selected) >= max_wells:
            break
    return {"selected": selected}


# ----------------------------------------
# Step 2 — Cross-well aggregation (never sums)
# ----------------------------------------


def aggregate_field(ledgers: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate per-well ledgers into per-well rows and cross-well field statistics."""
    wells: list[dict[str, Any]] = []
    for lg in ledgers:
        run = lg.get("run", {})
        s = lg.get("summary", {})
        p = run.get("net_pay_p10_p50_p90") or [lg.get("net_pay_total_m")] * 3
        wm = run.get("well_metadata", {})
        wells.append(
            {
                "uwi": run.get("uwi", "?"),
                "tier": run.get("confidence_tier", "?"),
                "status": run.get("convergence_status", "?"),
                "abstain": bool(run.get("abstain", False)),
                "net_pay_p50": p[1],
                "ntg": s.get("ntg"),
                "avg_phie": s.get("avg_phie"),
                "avg_sw": s.get("avg_sw"),
                "n_objections": len(lg.get("objections", [])),
                "latitude": wm.get("latitude"),
                "longitude": wm.get("longitude"),
            }
        )

    def _stats(key: str) -> dict[str, float]:
        vals = [w[key] for w in wells if w.get(key) is not None]
        if not vals:
            return {
                "mean": float("nan"),
                "median": float("nan"),
                "min": float("nan"),
                "max": float("nan"),
            }
        return {
            "mean": statistics.fmean(vals),
            "median": statistics.median(vals),
            "min": min(vals),
            "max": max(vals),
        }

    field = {
        "n_wells": len(wells),
        "n_abstaining": sum(1 for w in wells if w["abstain"]),
        "net_pay_p50": _stats("net_pay_p50"),
        "ntg": _stats("ntg"),
        "avg_phie": _stats("avg_phie"),
    }
    return {"wells": wells, "field": field}


# ----------------------------------------
# Step 2b — Field narrative (prose only; numbers come from the aggregate)
# ----------------------------------------

_NARR_SYSTEM = """You are a senior petrophysicist writing FIELD-level narrative for a multi-well
report. PROSE ONLY — no tables, headings, or JSON. Use ONLY the numbers in the FACTS; never sum
per-well net pay into a field total (wells are not stacked). 2-3 sentences, honest about
uncertainty when wells abstain."""


def write_field_narrative(agg: dict[str, Any], chat: ChatFn) -> dict[str, str]:
    """Generate field executive-summary and conclusions prose from the aggregate (prose only)."""
    f = agg["field"]
    np50 = f["net_pay_p50"]
    facts = (
        f"FACTS (the only numbers you may use): wells {f['n_wells']} "
        f"({f['n_abstaining']} abstaining); cross-well net pay P50 mean {np50['mean']:.1f} m, "
        f"range {np50['min']:.1f}-{np50['max']:.1f} m (NOT a sum); NTG mean {f['ntg']['mean']:.3f}."
    )
    exec_msg = facts + "\n\nWrite the FIELD executive summary (rock/pay story across the wells)."
    concl_msg = facts + "\n\nWrite the FIELD conclusions (key takeaway + highest-leverage action)."
    return {
        "executive_summary": chat(_NARR_SYSTEM, exec_msg).strip(),
        "conclusions": chat(_NARR_SYSTEM, concl_msg).strip(),
    }


# ----------------------------------------
# Step 3 — Render the field chapter
# ----------------------------------------


def well_report_filename(uwi: str) -> str:
    """The per-well report filename the field chapter links to (kept in sync with the writer)."""
    return "report_" + uwi.replace(",", "").replace(" ", "") + ".md"


def render_field_report(
    agg: dict[str, Any],
    narrative: dict[str, str] | None = None,
    selection: dict[str, Any] | None = None,
    figures: list[dict[str, str]] | None = None,
) -> str:
    """Render the field-scale Markdown chapter from the aggregate and optional prose."""
    narrative = narrative or {}
    figures = figures or []
    wells = agg["wells"]
    field = agg["field"]
    np50 = field["net_pay_p50"]

    best = max(wells, key=lambda w: w["ntg"] or 0.0) if wells else None
    rows = [
        "| Well | Status | Tier | Net pay P50 (m) | NTG | Avg PHIE | Avg Sw | Obj |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for w in wells:
        flag = " ⚠️" if w["abstain"] else ""
        link = f"[{w['uwi']}]({well_report_filename(w['uwi'])})"
        rows.append(
            f"| {link}{flag} | {w['status']} | {w['tier']} | {_fmt(w['net_pay_p50'], 1)} | "
            f"{_fmt(w['ntg'], 3)} | {_fmt(w['avg_phie'], 3)} | {_fmt(w['avg_sw'], 3)} | "
            f"{w['n_objections']} |"
        )
    fig_block = "\n".join(f"**{f['title']}**\n\n![{f['title']}]({f['file']})\n" for f in figures)
    sel_line = ""
    if selection:
        wells = selection.get("selected", [])
        rat = selection.get("rationale", "")
        if selection.get("fell_back"):
            # base-by-fallback must NOT read as the agent's free choice on the report surface
            sel_line = (
                f"Selection (DETERMINISTIC FALLBACK — model selection unavailable): {wells}. "
                f"{rat}\n\n"
            )
        else:
            sel_line = f"Selection (agent-chosen): {wells}." + (f" {rat}\n\n" if rat else "\n\n")

    return (
        f"# Field Report — {field['n_wells']} wells\n\n"
        f"{sel_line}"
        f"{narrative.get('executive_summary', '_(narrative pending)_').strip()}\n\n"
        "> **Cross-well net pay P50** (NOT a sum — wells are not stacked): "
        f"mean {_fmt(np50['mean'], 1)} m, median {_fmt(np50['median'], 1)} m, "
        f"range {_fmt(np50['min'], 1)}–{_fmt(np50['max'], 1)} m across {field['n_wells']} wells. "
        f"NTG mean {_fmt(field['ntg']['mean'], 3)}.\n\n"
        "---\n\n## Per-well inventory\n\n"
        f"{chr(10).join(rows)}\n\n"
        f"- **Highest net-to-gross:** {best['uwi'] if best else '—'} "
        f"(NTG {_fmt(best['ntg'], 3) if best else '—'}) — a ranking fact, not a judgement\n\n"
        "---\n\n## Figures\n\n"
        f"{fig_block or '_No field figures generated._'}\n\n"
        "---\n\n## Conclusions\n\n"
        f"{narrative.get('conclusions', '_(narrative pending)_').strip()}\n"
    )
