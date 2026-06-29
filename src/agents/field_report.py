"""Field-scale rollup (v2-native): cross-well statistics + the experiment's well selection.

Aggregates per-well ledgers into a field chapter with CROSS-WELL statistics (mean/median/range)
— never a summed thickness, which is meaningless as a field headline. The experiment selects
1 fixed anchor well (all models analyze it → comparability) + N model-chosen wells (depth/
creativity). Every number is rendered from the per-well ledgers by code; the LLM writes prose.
"""

from __future__ import annotations

import statistics
from typing import Any

from src.agents.report_template import _fmt

VERSION = "0.1.0"


# ----------------------------------------
# Step 1 — Experiment well selection (1 fixed anchor + N model-chosen)
# ----------------------------------------


def select_wells(
    all_uwis: list[str], anchor: str, model_choice: list[str], n_free: int = 2
) -> dict[str, Any]:
    """Pick the field subset: the fixed anchor plus up to ``n_free`` model-chosen wells.

    Args:
        all_uwis: every available well UWI.
        anchor: the fixed anchor well (analyzed by all models for comparability).
        model_choice: the wells the model proposed (in priority order).
        n_free: how many model-chosen wells to keep beyond the anchor.

    Returns:
        ``{anchor, free, selected}`` — free excludes the anchor and unknown UWIs.
    """
    valid = set(all_uwis)
    free: list[str] = []
    for uwi in model_choice:
        if uwi in valid and uwi != anchor and uwi not in free:
            free.append(uwi)
        if len(free) >= n_free:
            break
    selected = ([anchor] if anchor in valid else []) + free
    return {"anchor": anchor, "free": free, "selected": selected}


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
# Step 3 — Render the field chapter
# ----------------------------------------


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
        rows.append(
            f"| {w['uwi']}{flag} | {w['status']} | {w['tier']} | {_fmt(w['net_pay_p50'], 1)} | "
            f"{_fmt(w['ntg'], 3)} | {_fmt(w['avg_phie'], 3)} | {_fmt(w['avg_sw'], 3)} | "
            f"{w['n_objections']} |"
        )
    fig_block = "\n".join(f"**{f['title']}**\n\n![{f['title']}]({f['file']})\n" for f in figures)
    sel_line = ""
    if selection:
        sel_line = (
            f"Selection: anchor `{selection.get('anchor', '—')}` (fixed) + "
            f"model-chosen {selection.get('free', [])}.\n\n"
        )

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
        f"- **Best reservoir quality:** {best['uwi'] if best else '—'} "
        f"(NTG {_fmt(best['ntg'], 3) if best else '—'})\n\n"
        "---\n\n## Figures\n\n"
        f"{fig_block or '_No field figures generated._'}\n\n"
        "---\n\n## Conclusions\n\n"
        f"{narrative.get('conclusions', '_(narrative pending)_').strip()}\n"
    )
