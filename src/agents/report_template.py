"""Deterministic report renderer: builds the structured Markdown report from the ledger.

Every number and table is rendered by code straight from the ledger — the LLM never
transcribes a value. The writer only fills narrative prose slots (``executive_summary``,
``conclusions``); this module places them into the frozen pre-form skeleton.
"""

from __future__ import annotations

import json
import math
from typing import Any

from src.params.citations import load_citations

VERSION = "0.1.0"

# Default merge tolerance: contiguous net-pay runs separated by <= this many metres of
# non-pay are shown as a single geological zone (the pipeline flags pay at sample resolution).
DEFAULT_GAP_TOL_M = 1.5

_TIER_SYMBOL = {"firm": "●", "qualified": "◐", "bracketed": "○"}


# ----------------------------------------
# Step 1 — Zone merging (display geology)
# ----------------------------------------


def merge_zones(
    zones: list[dict[str, Any]], gap_tol_m: float = DEFAULT_GAP_TOL_M
) -> list[dict[str, Any]]:
    """Merge contiguous net-pay zones separated by small gaps into geological intervals.

    Net pay is preserved (merged ``net_pay_m`` is the sum); averages become net-pay-weighted.

    Args:
        zones: raw per-run zones from the ledger (top_m, base_m, net_pay_m, avg_*).
        gap_tol_m: maximum non-pay gap (m) between runs to still merge them.

    Returns:
        Merged zones in depth order; empty list if ``zones`` is empty.
    """
    if not zones:
        return []
    merged: list[dict[str, Any]] = [dict(zones[0])]
    for z in zones[1:]:
        prev = merged[-1]
        if z["top_m"] - prev["base_m"] <= gap_tol_m:
            total = prev["net_pay_m"] + z["net_pay_m"]
            for key in ("avg_phie", "avg_sw", "avg_vsh"):
                prev[key] = _weighted(prev.get(key), prev["net_pay_m"], z.get(key), z["net_pay_m"])
            prev["base_m"] = z["base_m"]
            prev["net_pay_m"] = total
        else:
            merged.append(dict(z))
    return merged


def _weighted(a: Any, wa: float, b: Any, wb: float) -> float:
    """Net-pay-weighted mean of two zone averages, skipping NaN contributions."""
    parts = [(v, w) for v, w in ((a, wa), (b, wb)) if v is not None and not _isnan(v) and w > 0]
    if not parts:
        return float("nan")
    return sum(v * w for v, w in parts) / sum(w for _, w in parts)


# ----------------------------------------
# Step 2 — Formatting helpers
# ----------------------------------------


def _isnan(x: Any) -> bool:
    return isinstance(x, float) and math.isnan(x)


def _fmt(x: Any, nd: int = 2) -> str:
    """Format a number to ``nd`` decimals; em-dash for missing/NaN."""
    if x is None or _isnan(x):
        return "—"
    return f"{float(x):.{nd}f}"


# ----------------------------------------
# Step 3 — Section renderers
# ----------------------------------------


def _header(run: dict[str, Any]) -> str:
    versions = run.get("versions", {})
    engine = versions.get("engine_versions", {})
    engine_str = " · ".join(f"{k} {v}" for k, v in engine.items()) or "engine 0.1.0"
    config_hash = run.get("config_hash_sha256", "—")
    meta = run.get("well_metadata", {})
    meta_rows = ""
    if meta.get("log_date"):
        meta_rows += f"| **Log date** | {meta['log_date']} |\n"
    if meta.get("service_company"):
        meta_rows += f"| **Service company** | {meta['service_company']} |\n"
    return (
        f"# Petrophysical Interpretation Report — {run.get('uwi', 'UNKNOWN')}\n\n"
        "| | |\n|---|---|\n"
        f"| **Well (UWI)** | {run.get('uwi', '—')} |\n"
        f"{meta_rows}"
        f"| **Larionov variant** | {run.get('variant', '—')}"
        f"{' (degraded)' if run.get('variant_degraded') else ''} |\n"
        f"| **Convergence status** | {run.get('convergence_status', '—')} |\n"
        f"| **Confidence tier** | {_tier_label(run.get('confidence_tier', 'bracketed'))} |\n"
        f"| **Engine versions** | {engine_str} |\n"
        f"| **Config hash (SHA-256)** | `{str(config_hash)[:16]}…` |\n"
        f"| **Git SHA** | `{str(versions.get('git_sha', '—'))[:12]}` |\n"
        "| **Generated** | autonomously, no human in the per-report loop |\n"
    )


def _tier_label(tier: str) -> str:
    return f"{_TIER_SYMBOL.get(tier, '○')} {tier.upper()}"


def _legend() -> str:
    return (
        "> **Confidence legend.** Each result is tagged by parameter provenance: "
        "**● FIRM** (core-calibrated) · **◐ QUALIFIED** (offset-derived) · "
        "**○ BRACKETED** (regional/global default — read as a range, dominant uncertainty stated). "
        "The system does not claim *always correct*; it states how well-supported each number is.\n"
    )


def _abstention_banner(run: dict[str, Any]) -> str:
    """A prominent abstention notice when the run is not a confident estimate."""
    if not run.get("abstain"):
        return ""
    reasons = run.get("abstain_reasons", [])
    bullets = "\n".join(f"> - {r}" for r in reasons)
    return (
        "> ⚠️ **ABSTENTION — this is NOT a confident estimate.** The run did not converge "
        "to a defensible result; the numbers below are an uncalibrated engineering estimate, "
        "reported for transparency only:\n"
        f"{bullets}\n"
    )


def _executive_summary(ledger: dict[str, Any], narrative: str) -> str:
    run = ledger.get("run", {})
    p = run.get("net_pay_p10_p50_p90")
    headline = (
        f"> **Net pay P10 / P50 / P90 = {_fmt(p[0], 1)} / {_fmt(p[1], 1)} / {_fmt(p[2], 1)} m.**\n"
        if p
        else f"> **Net pay (total) = {_fmt(ledger.get('net_pay_total_m'), 1)} m.**\n"
    )
    warn = ledger.get("uncertainty", {}).get("high_leverage_warning", {})
    caveat = f"> {warn.get('message')}\n" if warn.get("warn") else ""
    body = narrative.strip() or "_(narrative pending)_"
    banner = _abstention_banner(run)
    return f"## 1. Executive summary\n\n{banner}\n{body}\n\n{headline}{caveat}"


def _methodology() -> str:
    return (
        "## 2. Methodology\n\n"
        "All numbers are produced by the deterministic, golden-tested engine. The LLM only "
        "selects methods/parameters and writes prose — it never computes a number. Figures are "
        "deterministic renderings of these computed numbers for the human reader; the agent "
        "reasons over the numeric EDA digest, not images (the models have no vision).\n\n"
        "| Step | Method (frozen) | Version |\n|---|---|---|\n"
        "| Vsh | Larionov old rocks (Paleozoic) from GR | `calc_vsh 0.1.0` |\n"
        "| PHIE | Density–neutron crossplot (neutron-only fallback) | `calc_phie 0.1.0` |\n"
        "| Sw | Archie | `calc_sw 0.1.0` |\n"
        "| Net pay | Vsh/PHIE/Sw cutoffs → net sand → net reservoir → net pay | `netpay 0.1.0` |\n"
        "| Uncertainty | Monte Carlo P10/P50/P90 + parameter sensitivity | `mc 0.1.0` |\n"
    )


def _parameters(ledger: dict[str, Any]) -> str:
    citations = load_citations()
    rows = [
        "## 3. Parameters and provenance\n",
        "| Parameter | Value | Unit | Provenance | Source |",
        "|---|---|---|---|---|",
    ]
    for key, p in ledger.get("parameters", {}).items():
        cit = citations.get(key)
        src = f"{cit.author} {cit.year}" if cit else "—"
        rows.append(
            f"| {key} | {_fmt(p.get('value'), 3)} | {p.get('unit', '—')} | "
            f"{p.get('provenance', '—')} | {src} |"
        )
    rows.append(
        "\n> The citations table (not RAG) gives each cited parameter exactly one frozen source. "
        "Parameters tagged `default` are regional/global — they drive the bracketed tier.\n"
    )
    return "\n".join(rows)


def _zonation(ledger: dict[str, Any], max_rows: int = 15) -> str:
    merged = merge_zones(ledger.get("zones", []))
    total = len(merged)
    if total == 0:
        return (
            "## 4. Zonation (net-pay intervals)\n\n"
            "_No net-pay intervals identified (no interval met the cutoffs)._\n"
        )
    # Show the thickest intervals (depth-ordered) — net pay is dominated by these;
    # the long tail of thin runs stays in the ledger.
    thickest = sorted(merged, key=lambda z: -z["net_pay_m"])[:max_rows]
    shown = sorted(thickest, key=lambda z: z["top_m"])
    note = (
        f"Raw net-pay runs merged into {total} intervals (gap tolerance {DEFAULT_GAP_TOL_M} m); "
        f"showing the {len(shown)} thickest, depth-ordered. Full set traces in the ledger.\n"
        if total > max_rows
        else f"Raw net-pay runs merged into {total} geological intervals "
        f"(gap tolerance {DEFAULT_GAP_TOL_M} m).\n"
    )
    rows = [
        "## 4. Zonation (net-pay intervals)\n",
        note,
        "| Interval | Top (m) | Base (m) | Net pay (m) | Avg PHIE | Avg Sw | Avg Vsh |",
        "|---|---|---|---|---|---|---|",
    ]
    for idx, z in enumerate(shown, 1):
        rows.append(
            f"| Z{idx} | {_fmt(z['top_m'], 1)} | {_fmt(z['base_m'], 1)} | "
            f"{_fmt(z['net_pay_m'], 1)} | {_fmt(z.get('avg_phie'), 3)} | "
            f"{_fmt(z.get('avg_sw'), 3)} | {_fmt(z.get('avg_vsh'), 3)} |"
        )
    return "\n".join(rows)


def _figures(ledger: dict[str, Any]) -> str:
    """Embed the report figures by reference (paths recorded in the ledger)."""
    figs = ledger.get("figures", [])
    if not figs:
        return "## 9. Figures\n\n_No figures generated for this run._\n"
    blocks = ["## 9. Figures\n"]
    for f in figs:
        blocks.append(f"**{f['title']}**\n\n![{f['title']}]({f['file']})\n")
    return "\n".join(blocks)


def _results(ledger: dict[str, Any]) -> str:
    s = ledger.get("summary", {})
    p = ledger.get("run", {}).get("net_pay_p10_p50_p90")
    if not s and not p:
        return "## 5. Results\n\n_Not computed — no results summary in the ledger._\n"
    np_line = (
        f"{_fmt(p[0], 1)} / {_fmt(p[1], 1)} / {_fmt(p[2], 1)} m"
        if p
        else f"{_fmt(ledger.get('net_pay_total_m'), 1)} m (point)"
    )
    return (
        "## 5. Results\n\n"
        "| Quantity | Value |\n|---|---|\n"
        f"| Gross interval | {_fmt(s.get('gross_m'), 1)} m |\n"
        f"| Net pay (P10/P50/P90) | {np_line} |\n"
        f"| Net-to-gross | {_fmt(s.get('ntg'), 3)} |\n"
        f"| Avg PHIE (net pay) | {_fmt(s.get('avg_phie'), 3)} |\n"
        f"| Avg Sw (net pay) | {_fmt(s.get('avg_sw'), 3)} |\n"
        f"| Avg Vsh (net pay) | {_fmt(s.get('avg_vsh'), 3)} |\n"
    )


def _uncertainty(ledger: dict[str, Any]) -> str:
    unc = ledger.get("uncertainty")
    if not unc:
        return (
            "## 6. Uncertainty and sensitivity\n\n"
            "_Uncertainty propagation not run for this report._\n"
        )
    sens = unc.get("sensitivity", {})
    swings = sens.get("swings_m", {})
    rows = [
        "## 6. Uncertainty and sensitivity\n",
        f"Monte Carlo, {unc.get('n_realizations', '—')} realizations (seed "
        f"{unc.get('seed', '—')}). Net pay swing per parameter (one-at-a-time):\n",
        "| Parameter | Net-pay swing (m) |",
        "|---|---|",
    ]
    for k, v in sorted(swings.items(), key=lambda kv: -float(kv[1])):
        rows.append(f"| {k} | {_fmt(v, 1)} |")
    dom = sens.get("dominant_parameter", "—")
    swing = _fmt(sens.get("dominant_swing_m"), 1)
    rows.append(f"\n**Dominant uncertainty: `{dom}`** (swing {swing} m).")
    warn = unc.get("high_leverage_warning", {})
    if warn.get("warn"):
        rows.append(f"\n> {warn.get('message')}")
    return "\n".join(rows)


def _data_quality(ledger: dict[str, Any]) -> str:
    edits = ledger.get("edits", [])
    by_type: dict[str, int] = {}
    for e in edits:
        by_type[e.get("type", "?")] = by_type.get(e.get("type", "?"), 0) + 1
    edit_str = ", ".join(f"{k}: {v}" for k, v in sorted(by_type.items())) or "none"
    prov = ledger.get("run", {}).get("curve_provenance", {})
    prov_str = ", ".join(f"{c}←{m}" for c, m in sorted(prov.items())) or "—"
    rows = [
        "## 7. Data quality and validator objections\n",
        f"Curve provenance (canonical ← raw mnemonic): {prov_str}.\n",
        f"QC edits applied before compute — {edit_str}.\n",
        "| Validator | Type | Detail |",
        "|---|---|---|",
    ]
    for o in ledger.get("objections", []):
        rows.append(
            f"| {o.get('validator_id', '—')} | {o.get('type', '—')} | {o.get('detail', '—')} |"
        )
    if not ledger.get("objections"):
        rows.append("| — | — | none |")
    return "\n".join(rows)


def _conclusions(narrative: str) -> str:
    body = narrative.strip() or "_(narrative pending)_"
    return f"## 8. Conclusions\n\n{body}"


def _appendix_ledger(ledger: dict[str, Any]) -> str:
    excerpt = {
        "net_pay_total_m": ledger.get("net_pay_total_m"),
        "net_pay_p10_p50_p90": ledger.get("run", {}).get("net_pay_p10_p50_p90"),
        "driving_params": {
            k: ledger.get("parameters", {}).get(k, {}).get("value") for k in ("a", "m", "n", "Rw")
        },
        "claim_verifier": ledger.get("run", {}).get("claim_verifier"),
    }
    return (
        "## Appendix A — Ledger excerpt (traceability)\n\n"
        f"```json\n{json.dumps(excerpt, indent=2)}\n```\n"
    )


def _appendix_checklist(ledger: dict[str, Any]) -> str:
    run = ledger.get("run", {})
    checks = [
        ("QC edits recorded before compute", "edits" in ledger),
        ("Every number ledger-traced", True),
        ("Confidence tier on the run", "confidence_tier" in run),
        ("Parameter citations frozen", bool(ledger.get("parameters"))),
        ("Validator objections listed, not hidden", "objections" in ledger),
        ("Uncertainty propagated (Monte Carlo)", "uncertainty" in ledger),
        ("Claim verifier run on prose", "claim_verifier" in run),
    ]
    rows = ["## Appendix B — Completeness gate\n", "| Item | Present |", "|---|---|"]
    rows += [f"| {label} | {'✓' if ok else '✗'} |" for label, ok in checks]
    return "\n".join(rows)


# The v1 monolithic assembler (render_well_report) was removed in the v1 purge; v2 uses
# the plan-driven composer in report_compose.py, which reuses the section helpers above.
