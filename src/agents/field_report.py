"""Field rollup: run the pipeline over several wells and render a field-scale report.

Per-well ledgers come from the deterministic pipeline; this module aggregates them to
field net pay and renders the per-well results table + field rollup. As in the well
report, every number is rendered from the ledgers by code; the LLM writes only prose.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.agents.client import ChatFn
from src.agents.report_template import _fmt
from src.agents.writer import _SYSTEM
from src.orchestrator.graph import run_pipeline

VERSION = "0.1.0"


# ----------------------------------------
# Step 1 — Aggregate per-well ledgers
# ----------------------------------------


def aggregate_field(ledgers: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate per-well ledgers into per-well rows and field totals.

    Field P10/P50/P90 net pay are the per-well percentile sums (comonotonic assumption,
    stated in the report — a conservative field range, not independent-error addition).
    """
    wells: list[dict[str, Any]] = []
    for lg in ledgers:
        run = lg.get("run", {})
        s = lg.get("summary", {})
        p = run.get("net_pay_p10_p50_p90") or [lg.get("net_pay_total_m")] * 3
        wells.append({
            "uwi": run.get("uwi", "?"),
            "tier": run.get("confidence_tier", "?"),
            "status": run.get("convergence_status", "?"),
            "gross_m": s.get("gross_m"),
            "ntg": s.get("ntg"),
            "net_pay_p10": p[0],
            "net_pay_p50": p[1],
            "net_pay_p90": p[2],
            "avg_phie": s.get("avg_phie"),
            "avg_sw": s.get("avg_sw"),
        })

    def fsum(key: str) -> float:
        return float(sum(w[key] for w in wells if w.get(key) is not None))

    field = {
        "n_wells": len(wells),
        "gross_m": fsum("gross_m"),
        "net_pay_p10": fsum("net_pay_p10"),
        "net_pay_p50": fsum("net_pay_p50"),
        "net_pay_p90": fsum("net_pay_p90"),
    }
    return {"wells": wells, "field": field}


# ----------------------------------------
# Step 2 — Render the field report
# ----------------------------------------


def render_field_report(agg: dict[str, Any], narrative: dict[str, str] | None = None) -> str:
    """Render the field-scale Markdown report from the aggregate and optional prose."""
    narrative = narrative or {}
    wells = agg["wells"]
    field = agg["field"]
    best = max(wells, key=lambda w: w["net_pay_p50"]) if wells else None
    weakest = min(wells, key=lambda w: w["net_pay_p50"]) if wells else None

    rows = [
        "| Well | Status | Tier | Gross (m) | Net pay P10/P50/P90 (m) | NTG | Avg PHIE | Avg Sw |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for w in wells:
        np_cell = (
            f"{_fmt(w['net_pay_p10'], 1)}/{_fmt(w['net_pay_p50'], 1)}/{_fmt(w['net_pay_p90'], 1)}"
        )
        rows.append(
            f"| {w['uwi']} | {w['status']} | {w['tier']} | {_fmt(w['gross_m'], 1)} | "
            f"{np_cell} | "
            f"{_fmt(w['ntg'], 3)} | {_fmt(w['avg_phie'], 3)} | {_fmt(w['avg_sw'], 3)} |"
        )
    table = "\n".join(rows)

    return (
        f"# Field Petrophysical Report — {field['n_wells']} wells\n\n"
        f"{narrative.get('executive_summary', '_(narrative pending)_').strip()}\n\n"
        f"> **Field net pay P10/P50/P90 = {_fmt(field['net_pay_p10'], 1)} / "
        f"{_fmt(field['net_pay_p50'], 1)} / {_fmt(field['net_pay_p90'], 1)} m** across "
        f"{field['n_wells']} wells (per-well percentile sums, comonotonic — conservative).\n\n"
        "---\n\n## Per-well results\n\n"
        f"{table}\n\n"
        f"- **Strongest well:** {best['uwi'] if best else '—'} "
        f"(net pay P50 {_fmt(best['net_pay_p50'], 1) if best else '—'} m)\n"
        f"- **Weakest well:** {weakest['uwi'] if weakest else '—'} "
        f"(net pay P50 {_fmt(weakest['net_pay_p50'], 1) if weakest else '—'} m)\n\n"
        "---\n\n## Conclusions\n\n"
        f"{narrative.get('conclusions', '_(narrative pending)_').strip()}\n"
    )


# ----------------------------------------
# Step 3 — Field narrative (prose only)
# ----------------------------------------


def write_field_narrative(agg: dict[str, Any], chat: ChatFn) -> dict[str, str]:
    """Generate field-level executive-summary and conclusions prose from the aggregate."""
    field = agg["field"]
    facts = (
        f"- Wells: {field['n_wells']}\n"
        f"- Field net pay P10/P50/P90 = {field['net_pay_p10']:.1f}/"
        f"{field['net_pay_p50']:.1f}/{field['net_pay_p90']:.1f} m\n"
        f"- Field gross interval: {field['gross_m']:.1f} m"
    )
    exec_user = (
        f"FACTS (the ONLY numbers you may use):\n{facts}\n\n"
        "Write the FIELD EXECUTIVE SUMMARY narrative (rock/pay story across the wells)."
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
    """Run the pipeline on each well, aggregate, and render the field report.

    Args:
        las_paths: LAS files for the wells in the field.
        chat: optional writer chat for the field narrative; rendered without prose if None.
        region: regional defaults key.
        out_dir: output directory for ledgers and the field report.

    Returns:
        ``{report, aggregate, ledgers}``. Writes ``<out_dir>/field_report.md``.
    """
    ledgers = [run_pipeline(p, region=region, out_dir=out_dir) for p in las_paths]
    agg = aggregate_field(ledgers)
    narrative = write_field_narrative(agg, chat) if chat is not None else {}
    report_md = render_field_report(agg, narrative)
    Path(out_dir, "field_report.md").write_text(report_md)
    return {"report": report_md, "aggregate": agg, "ledgers": ledgers}
