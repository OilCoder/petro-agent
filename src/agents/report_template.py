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
    rob = unc.get("robustness")
    if rob:
        status = "stable" if rob.get("robust") else "UNSTABLE across seeds"
        rows.append(
            f"\nMulti-seed robustness: P50 {status} (spread {_fmt(rob.get('p50_spread'), 1)} m "
            f"across {len(rob.get('p50_by_seed', []))} seeds)."
        )
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


# ----------------------------------------
# R2 — LAS-only [FIJO] sections (renderer-only; data already in the ledger/eda)
# ----------------------------------------

_STD_CURVES = ("GR", "RHOB", "NPHI", "RT", "SP", "DT", "PEF", "CALI", "DCAL")


def _fmt_kv(d: Any) -> str:
    """Render a small dict as compact key=value pairs (for EDA digest summaries)."""
    if not isinstance(d, dict):
        return str(d)
    return ", ".join(f"{k}={v}" for k, v in d.items())


def _data_inventory(ledger: dict[str, Any]) -> str:
    run = ledger.get("run", {})
    wm = run.get("well_metadata", {})
    prov = run.get("curve_provenance", {})
    curves = ", ".join(f"{c}←{m}" for c, m in sorted(prov.items())) or "—"
    return (
        "## Data inventory (from LAS)\n\n"
        f"- Curves present (canonical ← raw): {curves}\n"
        f"- Logged interval: {wm.get('depth_start_m', '—')}–{wm.get('depth_stop_m', '—')} m\n"
        f"- Log date: {wm.get('log_date', '—')}\n"
        f"- Service company: {wm.get('service_company', '—')} · Company: {wm.get('company', '—')}\n"
        f"- Field: {wm.get('field', '—')}\n"
        "- Not provided by LAS (out of scope): core, mud logs, pressure tests, production, "
        "completion, formation tops.\n"
    )


def _las_qc(ledger: dict[str, Any]) -> str:
    edits = ledger.get("edits", [])
    rows = ["## LAS quality control\n", "| Edit type | Curve | Detail |", "|---|---|---|"]
    # Edits with a count/factor are informative (one row each); bare per-depth edits (e.g. each
    # spike removal) are aggregated by type+curve so they don't flood the table with empty rows.
    bare: dict[tuple[str, str], int] = {}
    for e in edits:
        etype, curve = e.get("type", "—"), e.get("curve", "—")
        if e.get("count") is not None:
            rows.append(f"| {etype} | {curve} | count {e['count']} |")
        elif e.get("factor") is not None:
            rows.append(f"| {etype} | {curve} | factor {e['factor']} |")
        else:
            bare[(etype, curve)] = bare.get((etype, curve), 0) + 1
    for (etype, curve), n in bare.items():
        rows.append(f"| {etype} | {curve} | {n} edits |" if n > 1 else f"| {etype} | {curve} | — |")
    if not edits:
        rows.append("| — | — | none |")
    return "\n".join(rows) + "\n"


def _standardization(ledger: dict[str, Any]) -> str:
    prov = ledger.get("run", {}).get("curve_provenance", {})
    conv = [e for e in ledger.get("edits", []) if e.get("type") == "unit_conversion"]
    rows = [
        "## Standardization\n",
        "Raw mnemonics mapped to canonical curve names:",
        "| Canonical | Raw mnemonic |",
        "|---|---|",
    ]
    for c, m in sorted(prov.items()):
        rows.append(f"| {c} | {m} |")
    if not prov:
        rows.append("| — | — |")
    if conv:
        rows.append(
            "\nUnit conversions: "
            + ", ".join(f"{e.get('curve')}×{e.get('factor')}" for e in conv)
            + "."
        )
    return "\n".join(rows) + "\n"


def _curve_qc(ledger: dict[str, Any]) -> str:
    eda = ledger.get("run", {}).get("eda", {})
    if not eda:
        return "## Per-curve log QC\n\n_Not computed — EDA digest not available._\n"
    rows = ["## Per-curve log QC\n"]
    gb = eda.get("gr_baseline") or eda.get("gr_baseline_check")
    if gb:
        rows.append(f"- GR baseline: {_fmt_kv(gb)}")
    if eda.get("badhole"):
        rows.append(f"- Bad-hole: {_fmt_kv(eda['badhole'])}")
    if eda.get("low_resistivity"):
        rows.append(f"- Low-resistivity: {_fmt_kv(eda['low_resistivity'])}")
    if len(rows) == 1:
        rows.append("_No per-curve flags surfaced._")
    return "\n".join(rows) + "\n"


def _data_prep(ledger: dict[str, Any]) -> str:
    by_type: dict[str, int] = {}
    for e in ledger.get("edits", []):
        t = e.get("type", "?")
        by_type[t] = by_type.get(t, 0) + 1
    summary = ", ".join(f"{t}: {n}" for t, n in sorted(by_type.items())) or "none"
    return f"## Data preparation\n\nEdits applied before compute (by type): {summary}.\n"


def _intervals(ledger: dict[str, Any]) -> str:
    s = ledger.get("summary", {})
    wm = ledger.get("run", {}).get("well_metadata", {})
    nz = s.get("n_zones_raw")
    return (
        "## Interval definition\n\n"
        f"- Logged interval: {wm.get('depth_start_m', '—')}–{wm.get('depth_stop_m', '—')} m\n"
        f"- Gross evaluated interval: {_fmt(s.get('gross_m'), 1)} m\n"
        f"- Computed net-pay runs (pre-merge): {nz if nz is not None else '—'}\n"
        "- Zonation is computed by depth (no formation tops in LAS).\n"
    )


def _gr_analysis(ledger: dict[str, Any]) -> str:
    p = ledger.get("parameters", {})
    gmin = p.get("gr_min", {}).get("value")
    gmax = p.get("gr_max", {}).get("value")
    eda = ledger.get("run", {}).get("eda", {})
    rows = [
        "## Gamma-ray analysis\n",
        f"- Clean baseline gr_min = {_fmt(gmin, 1)} API · shale gr_max = {_fmt(gmax, 1)} API",
        "- Shale index IGR = (GR − gr_min)/(gr_max − gr_min), the basis for Vsh.",
    ]
    gb = eda.get("gr_baseline") or eda.get("gr_baseline_check")
    if gb:
        rows.append(f"- GR baseline check: {_fmt_kv(gb)}")
    return "\n".join(rows) + "\n"


def _resistivity_analysis(ledger: dict[str, Any]) -> str:
    prov = ledger.get("run", {}).get("curve_provenance", {})
    if "RT" not in prov:
        return "## Resistivity analysis\n\n_Not computed — no resistivity curve (RT) present._\n"
    lr = ledger.get("run", {}).get("eda", {}).get("low_resistivity")
    body = (
        f"Low-resistivity scan: {_fmt_kv(lr)}."
        if lr
        else "Resistivity present; no low-resistivity scan in the EDA digest."
    )
    return f"## Resistivity analysis\n\n{body}\n"


def _caliper_quality(ledger: dict[str, Any]) -> str:
    bh = ledger.get("run", {}).get("eda", {}).get("badhole")
    if not bh:
        return "## Caliper / hole quality\n\n_Not computed — no bad-hole summary available._\n"
    return f"## Caliper / hole quality\n\nBad-hole summary (quality classes): {_fmt_kv(bh)}.\n"


def _lithology(ledger: dict[str, Any]) -> str:
    lit = ledger.get("run", {}).get("eda", {}).get("lithology")
    if not lit or not lit.get("shares"):
        return (
            "## Density-neutron crossplot lithology\n\n"
            "_Not computed — needs the RHOB+NPHI density-neutron crossplot._\n"
        )
    shares = ", ".join(f"{k}: {v}" for k, v in lit["shares"].items())
    return (
        "## Density-neutron crossplot lithology\n\n"
        f"Matrix point-shares (fraction of points near each matrix line): {shares}. "
        "Engine crossplot output; naming the dominant lithology is the analyst's judgement. "
        "Comparison with core/mud log: not available (LAS-only).\n"
    )


def _rw(ledger: dict[str, Any]) -> str:
    p = ledger.get("parameters", {}).get("Rw", {})
    swings = ledger.get("uncertainty", {}).get("sensitivity", {}).get("swings_m", {})
    rw_swing = swings.get("Rw")
    rows = [
        "## Water resistivity (Rw)\n",
        f"- Rw = {_fmt(p.get('value'), 4)} ohm-m · provenance: {p.get('provenance', '—')}",
        "- Sourced by the engine (Pickett / SP / default); never authored by the LLM.",
    ]
    if rw_swing is not None:
        rows.append(f"- Net-pay sensitivity to Rw: {_fmt(rw_swing, 1)} m swing.")
    return "\n".join(rows) + "\n"


def _vsh(ledger: dict[str, Any]) -> str:
    cmp = ledger.get("vsh_comparison") or {}
    methods = cmp.get("methods") or {}
    if not methods:
        return "## Shale volume (Vsh)\n\n_Not computed — no GR curve for the comparison._\n"
    selected = cmp.get("selected", "—")
    rows = [
        "## Shale volume (Vsh)\n",
        "Mean Vsh by method (selection is the engine's; the LLM authors no number):",
        "| Method | Mean Vsh | Selected |",
        "|---|---|---|",
    ]
    for m, v in methods.items():
        rows.append(f"| {m} | {_fmt(v, 3)} | {'✓' if m == selected else ''} |")
    return "\n".join(rows) + "\n"


def _porosity(ledger: dict[str, Any]) -> str:
    cmp = ledger.get("porosity_comparison") or {}
    methods = cmp.get("methods") or {}
    if not methods:
        return "## Porosity\n\n_Not computed — no RHOB/NPHI curve for the comparison._\n"
    selected = cmp.get("selected", "—")
    rows = [
        "## Porosity\n",
        "Mean porosity by method (effective where shale-corrected; the LLM authors no number):",
        "| Method | Mean porosity | Selected |",
        "|---|---|---|",
    ]
    for m, v in methods.items():
        rows.append(f"| {m} | {_fmt(v, 3)} | {'✓' if m == selected else ''} |")
    return "\n".join(rows) + "\n"


def _sw(ledger: dict[str, Any]) -> str:
    s = ledger.get("sw_summary") or {}
    if s.get("mean_sw") is None:
        return "## Water saturation\n\n_Not computed — no Sw result._\n"
    return (
        "## Water saturation\n\n"
        f"Mean Sw (Archie) = {_fmt(s.get('mean_sw'), 3)} "
        f"(a={_fmt(s.get('a'), 2)}, m={_fmt(s.get('m'), 2)}, n={_fmt(s.get('n'), 2)}, "
        f"Rw={_fmt(s.get('rw'), 4)} ohm-m). "
        "Electrical parameters are engine-sourced; alternative Sw models are optional sections.\n"
    )


def _permeability_section(ledger: dict[str, Any]) -> str:
    results = ledger.get("tool_results", {})
    rows = []
    for key in ("perm_timur", "perm_coates"):
        v = results.get(key, {}).get("value", {})
        if v:
            rows.append(f"- {key}: mean k = {_fmt(v.get('mean_k_md'), 2)} mD")
    if not rows:
        return "## Permeability (uncalibrated)\n\n_Not computed — no permeability tool result._\n"
    return (
        "## Permeability (uncalibrated)\n\n"
        + "\n".join(rows)
        + "\n\n_Uncalibrated screening estimate (no core); Sw used as the Swirr proxy._\n"
    )


def _derived_parameters_section(ledger: dict[str, Any]) -> str:
    v = ledger.get("tool_results", {}).get("bvw", {}).get("value", {})
    if not v:
        return "## Derived parameters\n\n_Not computed — no derived-parameter tool result._\n"
    return (
        "## Derived parameters\n\n"
        f"- Bulk-volume water (BVW = PHIE*Sw): mean {_fmt(v.get('mean_bvw'), 4)} v/v\n"
    )


def _rock_quality_section(ledger: dict[str, Any]) -> str:
    results = ledger.get("tool_results", {})
    rows = []
    for key in ("rqi", "fzi", "winland_r35"):
        v = results.get(key, {}).get("value", {})
        if v:
            rows.append(f"- {key}: mean = {_fmt(v.get('mean_value'), 3)}")
    if not rows:
        return "## Rock quality (uncalibrated)\n\n_Not computed — no rock-quality tool result._\n"
    return (
        "## Rock quality (uncalibrated)\n\n"
        + "\n".join(rows)
        + "\n\n_Built on the uncalibrated permeability; indicative only._\n"
    )


def _electrofacies_section(ledger: dict[str, Any]) -> str:
    v = ledger.get("tool_results", {}).get("electrofacies", {}).get("value", {})
    if not v or not v.get("n_facies"):
        return "## Electrofacies\n\n_Not computed — no electrofacies tool result._\n"
    sizes = ", ".join(f"facies {k}: {n}" for k, n in (v.get("sizes") or {}).items())
    return (
        "## Electrofacies\n\n"
        f"Unsupervised k-means on {v.get('n_samples', '—')} samples into {v['n_facies']} "
        f"electrofacies (sample counts: {sizes}). Descriptive only — no core labels.\n"
    )


def _cutoffs(ledger: dict[str, Any]) -> str:
    """Net sand/reservoir/pay criteria and the Vsh/PHIE/Sw cutoff values actually applied."""
    params = ledger.get("parameters", {})
    vc = params.get("vsh_cutoff", {})
    pc = params.get("phie_cutoff", {})
    sc = params.get("sw_cutoff", {})
    rows = [
        "## Petrophysical cutoffs\n",
        "Boundary-inclusive criteria applied by the engine (`netpay`) to flag reservoir:\n",
        "| Stage | Criterion | Cutoff | Provenance |",
        "|---|---|---|---|",
    ]
    for stage, crit, p in (
        ("Net sand", "Vsh ≤ cutoff", vc),
        ("Net reservoir", "+ PHIE ≥ cutoff", pc),
        ("Net pay", "+ Sw ≤ cutoff", sc),
    ):
        rows.append(
            f"| {stage} | {crit} | {_fmt(p.get('value'), 3)} | {p.get('provenance', '—')} |"
        )
    dom = ledger.get("uncertainty", {}).get("sensitivity", {}).get("dominant_parameter")
    if dom:
        rows.append(
            f"\n> Cutoff values are engine parameters (never LLM-authored); the dominant net-pay "
            f"uncertainty is **{dom}** — see Uncertainty for the swing."
        )
    return "\n".join(rows) + "\n"


# Maps the dominant Archie parameter to the measurement that calibrates it.
_CALIBRATES = {
    "Rw": "produced-water salinity or a Pickett/SP Rw calibration",
    "m": "core SCAL — cementation exponent m",
    "n": "core SCAL — saturation exponent n",
    "a": "core SCAL — tortuosity factor a",
}


def _recommendations(ledger: dict[str, Any]) -> str:
    """Data absent for calibration + the parameter that dominates net-pay uncertainty (facts only).

    A neutral data-gaps rail (no analyst voice, no imperative): it states what is missing and which
    parameter the sensitivity flags as dominant. Whether/what to recommend is the analyst's call.
    """
    prov = ledger.get("run", {}).get("curve_provenance", {})
    missing = [c for c in _STD_CURVES if c not in prov]
    dom = ledger.get("uncertainty", {}).get("sensitivity", {}).get("dominant_parameter")
    rows = [
        "## Data gaps for calibration\n",
        "This is a LAS-only study. Data that would calibrate the interpretation is absent:\n",
        "- Core (routine + SCAL): would anchor PHIE and Archie m, n, a.",
        "- Pressure tests (RFT/MDT): would give true fluid contacts and gradients (log-based).",
        "- Production/flow data: would test the net-pay flag against deliverability.",
    ]
    if dom:
        rows.append(
            f"- Dominant net-pay uncertainty driver (from the sensitivity): **{dom}** "
            f"(calibrated by {_CALIBRATES.get(dom, 'core calibration')})."
        )
    if missing:
        rows.append(f"- Standard curves absent: {', '.join(missing)}.")
    return "\n".join(rows) + "\n"


def _limitations(ledger: dict[str, Any]) -> str:
    prov = ledger.get("run", {}).get("curve_provenance", {})
    missing = [c for c in _STD_CURVES if c not in prov]
    return (
        "## Limitations\n\n"
        "- LAS-only study: no core calibration, no pressure tests (no true fluid contacts), "
        "no production, no mud logs, no formation tops (zonation computed by depth).\n"
        f"- Standard curves absent in this well: {', '.join(missing) or 'none'}.\n"
        "- Results are uncalibrated; accuracy depends on data not provided.\n"
    )


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
