"""Field rollup: aggregate per-well ledgers into a field-scale report.

Reports a per-well inventory and CROSS-WELL statistics (mean/median/range) — never a
summed thickness, which is meaningless as a field headline. Every number is rendered
from the per-well ledgers by code; the LLM writes only prose. Field volume, if ever
reported, is a net rock volume (area x thickness), not a sum of per-well net pay.
"""

from __future__ import annotations

import statistics
from pathlib import Path
from typing import Any

from src.agents.client import ChatFn
from src.agents.log_plot import net_pay_bar
from src.agents.report_template import _fmt
from src.agents.writer import _SYSTEM
from src.orchestrator.graph import run_pipeline

VERSION = "0.1.0"


# ----------------------------------------
# Step 1 — Aggregate per-well ledgers (cross-well stats, never sums)
# ----------------------------------------


def aggregate_field(ledgers: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate per-well ledgers into per-well rows and cross-well field statistics."""
    wells: list[dict[str, Any]] = []
    for lg in ledgers:
        run = lg.get("run", {})
        s = lg.get("summary", {})
        p = run.get("net_pay_p10_p50_p90") or [lg.get("net_pay_total_m")] * 3
        wells.append(
            {
                "uwi": run.get("uwi", "?"),
                "tier": run.get("confidence_tier", "?"),
                "status": run.get("convergence_status", "?"),
                "abstain": bool(run.get("abstain", False)),
                "log_date": run.get("well_metadata", {}).get("log_date", "—"),
                "gross_m": s.get("gross_m"),
                "ntg": s.get("ntg"),
                "net_pay_p10": p[0],
                "net_pay_p50": p[1],
                "net_pay_p90": p[2],
                "avg_phie": s.get("avg_phie"),
                "avg_sw": s.get("avg_sw"),
                "n_objections": len(lg.get("objections", [])),
                "git_sha": run.get("versions", {}).get("git_sha", "—"),
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
# Step 2 — Render the field report
# ----------------------------------------


def _inventory_table(wells: list[dict[str, Any]]) -> str:
    rows = [
        "| Well | Log date | Status | Tier | Net pay P50 (m) | NTG | Avg PHIE | Avg Sw | Obj |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for w in wells:
        flag = " ⚠️" if w["abstain"] else ""
        rows.append(
            f"| {w['uwi']}{flag} | {w['log_date']} | {w['status']} | {w['tier']} | "
            f"{_fmt(w['net_pay_p50'], 1)} | {_fmt(w['ntg'], 3)} | {_fmt(w['avg_phie'], 3)} | "
            f"{_fmt(w['avg_sw'], 3)} | {w['n_objections']} |"
        )
    return "\n".join(rows)


def render_field_report(
    agg: dict[str, Any],
    narrative: dict[str, str] | None = None,
    figures: list[dict[str, str]] | None = None,
    excluded: list[dict[str, str]] | None = None,
    metadata: dict[str, Any] | None = None,
) -> str:
    """Render the field-scale Markdown report from the aggregate and optional prose."""
    narrative = narrative or {}
    figures = figures or []
    excluded = excluded or []
    metadata = metadata or {}
    wells = agg["wells"]
    field = agg["field"]
    np50 = field["net_pay_p50"]

    best_reservoir = max(wells, key=lambda w: w["ntg"] or 0.0) if wells else None
    best_data = min(wells, key=lambda w: (w["abstain"], w["n_objections"])) if wells else None

    fig_block = (
        "\n".join(f"**{f['title']}**\n\n![{f['title']}]({f['file']})\n" for f in figures)
        or "_No field figures generated._"
    )
    excl_block = (
        "\n".join(f"- `{e['path']}` — {e['error']}" for e in excluded) if excluded else "None."
    )

    return (
        f"# Field Petrophysical Report — {field['n_wells']} wells\n\n"
        "| | |\n|---|---|\n"
        f"| **Field** | {metadata.get('field', '—')} |\n"
        f"| **Wells loaded / excluded** | {field['n_wells']} / {len(excluded)} |\n"
        f"| **Wells abstaining** | {field['n_abstaining']} of {field['n_wells']} |\n"
        f"| **Engine / pipeline** | {metadata.get('versions', '—')} |\n\n"
        f"{narrative.get('executive_summary', '_(narrative pending)_').strip()}\n\n"
        "> **Cross-well net pay P50** (NOT a sum — wells are not stacked): "
        f"mean {_fmt(np50['mean'], 1)} m, median {_fmt(np50['median'], 1)} m, "
        f"range {_fmt(np50['min'], 1)}–{_fmt(np50['max'], 1)} m across {field['n_wells']} wells. "
        f"NTG mean {_fmt(field['ntg']['mean'], 3)}.\n\n"
        "---\n\n## Per-well inventory\n\n"
        f"{_inventory_table(wells)}\n\n"
        f"- **Best reservoir quality:** {best_reservoir['uwi'] if best_reservoir else '—'} "
        f"(NTG {_fmt(best_reservoir['ntg'], 3) if best_reservoir else '—'})\n"
        f"- **Best data quality:** {best_data['uwi'] if best_data else '—'} "
        f"({'abstains' if best_data and best_data['abstain'] else 'cleanest'}, "
        f"{best_data['n_objections'] if best_data else '—'} objections)\n\n"
        "---\n\n## Figures\n\n"
        f"{fig_block}\n\n"
        "---\n\n## Excluded files\n\n"
        f"{excl_block}\n\n"
        "---\n\n## Conclusions\n\n"
        f"{narrative.get('conclusions', '_(narrative pending)_').strip()}\n"
    )


# ----------------------------------------
# Step 3 — Field narrative (prose only)
# ----------------------------------------


def write_field_narrative(agg: dict[str, Any], chat: ChatFn) -> dict[str, str]:
    """Generate field-level executive-summary and conclusions prose from the aggregate."""
    field = agg["field"]
    np50 = field["net_pay_p50"]
    facts = (
        f"- Wells: {field['n_wells']} ({field['n_abstaining']} abstaining)\n"
        f"- Cross-well net pay P50 (NOT summed): mean {np50['mean']:.1f} m, "
        f"median {np50['median']:.1f} m, range {np50['min']:.1f}-{np50['max']:.1f} m\n"
        f"- NTG mean {field['ntg']['mean']:.3f}, avg PHIE mean {field['avg_phie']['mean']:.3f}"
    )
    exec_user = (
        f"FACTS (the ONLY numbers you may use):\n{facts}\n\n"
        "Write the FIELD EXECUTIVE SUMMARY narrative (rock/pay story across the wells); "
        "treat net pay as a per-well distribution, never a stacked total."
    )
    concl_user = (
        f"FACTS (the ONLY numbers you may use):\n{facts}\n\n"
        "Write the FIELD CONCLUSIONS narrative (key takeaway + highest-leverage next action)."
    )
    return {
        "executive_summary": chat(_SYSTEM, exec_user).strip(),
        "conclusions": chat(_SYSTEM, concl_user).strip(),
    }


# ----------------------------------------
# Step 4 — End-to-end field report
# ----------------------------------------


def generate_field_report(
    las_paths: list[str],
    chat: ChatFn | None = None,
    region: str = "paleozoic_kansas",
    out_dir: str = "outputs",
) -> dict[str, Any]:
    """Run the pipeline on each well, aggregate, render the field report.

    Load failures are recorded as excluded files (honest N_loaded/N_excluded) rather than
    crashing the field run. Writes ``<out_dir>/field_report.md``.
    """
    ledgers: list[dict[str, Any]] = []
    excluded: list[dict[str, str]] = []
    for p in las_paths:
        try:
            ledgers.append(run_pipeline(p, region=region, out_dir=out_dir))
        except Exception as exc:  # noqa: BLE001 - record, do not abort the field run
            excluded.append({"path": p, "error": str(exc)[:120]})

    agg = aggregate_field(ledgers)
    narrative = write_field_narrative(agg, chat) if chat is not None and agg["wells"] else {}
    figures: list[dict[str, str]] = []
    if agg["wells"]:
        net_pay_png = net_pay_bar(agg["wells"], Path(out_dir) / "figuras" / "field_net_pay.png")
        figures.append(
            {
                "title": "Field net pay by well",
                "file": f"figuras/{net_pay_png}",
            }
        )
    metadata = {
        "field": ledgers[0]["run"].get("well_metadata", {}).get("field", "—") if ledgers else "—",
        "versions": "engine 0.1.0 · pipeline 0.1.0",
    }
    report_md = render_field_report(agg, narrative, figures, excluded, metadata)
    Path(out_dir, "field_report.md").write_text(report_md)
    return {"report": report_md, "aggregate": agg, "ledgers": ledgers, "excluded": excluded}
