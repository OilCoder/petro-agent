"""Deterministic figure generation for the report.

Matplotlib (Agg) renders the standard petrophysical figures a reviewer expects: composite log,
Pickett, Buckles, Hingle, curve distributions, and the field map. Each function saves a PNG to
``out_dir`` and returns its basename; ``generate_figures`` collects them (plus the validator's
neutron-density crossplot) into the list the report renderer embeds. Figures visualize numbers the
engine already computed — they author none.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from src.petrophysics.netpay import apply_cutoffs  # noqa: E402

VERSION = "0.1.0"


def _safe(uwi: str) -> str:
    """Filesystem-safe UWI (strip commas/slashes/spaces) for figure filenames."""
    return re.sub(r"[^A-Za-z0-9_.-]", "", uwi.replace("/", "_").replace(",", ""))


def composite_log_plot(
    depth: np.ndarray,
    curves: dict[str, np.ndarray],
    vsh: np.ndarray,
    phie: np.ndarray,
    sw: np.ndarray,
    netpay_flag: np.ndarray,
    out_path: str | Path,
) -> str:
    """Render the composite triple-combo log (GR, RT, RHOB/NPHI, PHIE, Sw, net pay).

    Returns the basename of the saved PNG.
    """
    tracks: list[tuple[str, list[tuple[Any, str, str | None]], bool]] = [
        ("GR (API)", [(curves.get("GR"), "k", None)], False),
        ("RT (ohm-m)", [(curves.get("RT"), "tab:red", None)], True),
        ("Vsh / PHIE (v/v)", [(vsh, "tab:brown", "Vsh"), (phie, "tab:blue", "PHIE")], False),
        ("Sw (v/v)", [(sw, "tab:cyan", None)], False),
        ("Net pay", [(netpay_flag.astype(float), "tab:green", None)], False),
    ]
    fig, axes = plt.subplots(1, len(tracks), figsize=(11, 8), sharey=True)
    for ax, (label, series, logx) in zip(axes, tracks, strict=True):
        for arr, color, name in series:
            if arr is not None:
                ax.plot(np.asarray(arr, dtype=float), depth, color=color, lw=0.6, label=name)
        if logx:
            ax.set_xscale("log")
        if any(s[2] for s in series):
            ax.legend(fontsize=6, loc="upper right")
        ax.set_title(label, fontsize=8)
        ax.grid(True, alpha=0.3)
    axes[0].set_ylim(float(np.nanmax(depth)), float(np.nanmin(depth)))
    axes[0].set_ylabel("Depth (m)")
    fig.suptitle("Composite log", fontsize=10)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=90, bbox_inches="tight")
    plt.close(fig)
    return out.name


def pickett_plot(
    rt: np.ndarray,
    phie: np.ndarray,
    a: float,
    m: float,
    rw: float,
    out_path: str | Path,
    n: float = 2.0,
) -> str:
    """Render a Pickett plot (log-log RT vs PHIE) with constant-Sw lines.

    Archie: ``Rt = a*Rw / (PHIE**m * Sw**n)``. Each Sw line is a straight line in
    log-log space; the data scatter is overlaid. Returns the PNG basename.
    """
    r = np.asarray(rt, dtype=float)
    p = np.asarray(phie, dtype=float)
    valid = np.isfinite(r) & np.isfinite(p) & (p > 0) & (r > 0)

    fig, ax = plt.subplots(figsize=(6, 6))
    ax.scatter(r[valid], p[valid], s=5, alpha=0.3, color="k", label="data")
    phi_line = np.array([0.01, 0.5])
    for sw in (1.0, 0.5, 0.25):
        rt_line = a * rw / (phi_line**m * sw**n)
        ax.plot(rt_line, phi_line, lw=1, label=f"Sw={sw:.2f}")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("RT (ohm-m)")
    ax.set_ylabel("PHIE (v/v)")
    ax.set_title(f"Pickett plot (a={a}, m={m}, Rw={rw})")
    ax.legend(fontsize=7)
    ax.grid(True, which="both", alpha=0.3)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=90, bbox_inches="tight")
    plt.close(fig)
    return out.name


def buckles_plot(phie: np.ndarray, sw: np.ndarray, out_path: str | Path) -> str:
    """Render a Buckles plot (PHIE vs Sw) with constant bulk-volume-water (BVW) hyperbolas.

    ``BVW = PHIE * Sw``; each constant-BVW line is ``Sw = BVW / PHIE``. Points on a common
    hyperbola suggest a shared irreducible-water condition. Returns the PNG basename.
    """
    p = np.asarray(phie, dtype=float)
    s = np.asarray(sw, dtype=float)
    valid = np.isfinite(p) & np.isfinite(s) & (p > 0) & (s >= 0)

    fig, ax = plt.subplots(figsize=(6, 6))
    ax.scatter(p[valid], s[valid], s=5, alpha=0.3, color="k", label="data")
    phi_line = np.linspace(0.01, 0.4, 200)
    for bvw in (0.02, 0.05, 0.1):
        ax.plot(phi_line, np.clip(bvw / phi_line, 0.0, 1.0), lw=1, label=f"BVW={bvw:.2f}")
    ax.set_xlim(0.0, 0.4)
    ax.set_ylim(0.0, 1.0)
    ax.set_xlabel("PHIE (v/v)")
    ax.set_ylabel("Sw (v/v)")
    ax.set_title("Buckles plot (constant BVW = PHIE·Sw)")
    ax.legend(fontsize=7)
    ax.grid(True, alpha=0.3)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=90, bbox_inches="tight")
    plt.close(fig)
    return out.name


def hingle_plot(rt: np.ndarray, phie: np.ndarray, m: float, out_path: str | Path) -> str:
    """Render a Hingle plot (PHIE vs RT^(-1/m)) — the linearized RT/porosity crossplot.

    For 100% water ``Rt = a*Rw / PHIE**m`` so ``Rt**(-1/m)`` is linear in PHIE through the
    origin; points off that trend flag possible hydrocarbon. Returns the PNG basename.
    """
    r = np.asarray(rt, dtype=float)
    p = np.asarray(phie, dtype=float)
    valid = np.isfinite(r) & np.isfinite(p) & (r > 0) & (p >= 0)

    fig, ax = plt.subplots(figsize=(6, 6))
    ax.scatter(p[valid], r[valid] ** (-1.0 / m), s=5, alpha=0.3, color="k")
    ax.set_xlabel("PHIE (v/v)")
    ax.set_ylabel(f"RT^(-1/{m:g}) (water line is linear through origin)")
    ax.set_title(f"Hingle plot (m={m:g})")
    ax.grid(True, alpha=0.3)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=90, bbox_inches="tight")
    plt.close(fig)
    return out.name


def distribution_plot(series: dict[str, np.ndarray | None], out_path: str | Path) -> str:
    """Render side-by-side histograms of the given curves/properties (GR, PHIE, Sw, …).

    Skips entries that are ``None`` or all-NaN. Returns the PNG basename.
    """
    items = [(k, np.asarray(v, dtype=float)) for k, v in series.items() if v is not None]
    items = [(k, a) for k, a in items if np.any(np.isfinite(a))]
    n = max(1, len(items))
    fig, axes = plt.subplots(1, n, figsize=(3.2 * n, 3.0))
    axes = np.atleast_1d(axes)
    for ax, (name, arr) in zip(axes, items, strict=False):
        ax.hist(arr[np.isfinite(arr)], bins=30, color="tab:blue", alpha=0.8)
        ax.set_title(name, fontsize=9)
        ax.grid(True, alpha=0.3)
    fig.suptitle("Distributions", fontsize=10)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=90, bbox_inches="tight")
    plt.close(fig)
    return out.name


def tornado_plot(swings: dict[str, float], out_path: str | Path) -> str:
    """Render a sensitivity tornado (net-pay swing per parameter), sorted by magnitude.

    HUMAN-ONLY figure: a numeric bar chart. It is not fed to the vision track (a vision model must
    not read numeric values off a plot). Returns the PNG basename.
    """
    items = sorted(swings.items(), key=lambda kv: abs(kv[1]))
    labels = [k for k, _ in items]
    vals = [abs(float(v)) for _, v in items]

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.barh(labels, vals, color="tab:orange")
    ax.set_xlabel("Net-pay swing (m)")
    ax.set_title("Sensitivity tornado (net-pay swing per parameter)")
    ax.grid(True, axis="x", alpha=0.3)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=90, bbox_inches="tight")
    plt.close(fig)
    return out.name


def mc_distribution_plot(
    realizations: list[float],
    p10: float | None,
    p50: float | None,
    p90: float | None,
    out_path: str | Path,
) -> str:
    """Render the Monte-Carlo net-pay distribution histogram with P10/P50/P90 markers.

    HUMAN-ONLY figure (numeric). Not fed to the vision track. Returns the PNG basename.
    """
    arr = np.asarray(realizations, dtype=float)
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.hist(arr[np.isfinite(arr)], bins=30, color="tab:green", alpha=0.8)
    for x, label in ((p10, "P10"), (p50, "P50"), (p90, "P90")):
        if x is not None:
            ax.axvline(float(x), color="k", ls="--", lw=1)
            ax.text(float(x), ax.get_ylim()[1] * 0.95, label, fontsize=7, ha="center")
    ax.set_xlabel("Net pay (m)")
    ax.set_ylabel("count")
    ax.set_title("Net-pay Monte-Carlo distribution")
    ax.grid(True, alpha=0.3)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=90, bbox_inches="tight")
    plt.close(fig)
    return out.name


def generate_uncertainty_figures(
    ledger: dict[str, Any], out_dir: str | Path
) -> list[dict[str, str]]:
    """Append the HUMAN-ONLY uncertainty figures (tornado + MC distribution) to the ledger.

    Run AFTER the loop (uncertainty is a loop artifact). These are numeric charts and are NOT wired
    into the vision track. Returns the figures added (empty if uncertainty was not computed).
    """
    unc = ledger.get("uncertainty", {})
    if not unc:
        return []
    safe = _safe(ledger.get("run", {}).get("uwi", "well"))
    fig_dir = Path(out_dir) / "figuras"
    added: list[dict[str, str]] = []
    swings = unc.get("sensitivity", {}).get("swings_m")
    if swings:
        name = tornado_plot(swings, fig_dir / f"{safe}_tornado.png")
        added.append({"title": "Sensitivity tornado", "file": f"figuras/{name}"})
    reals = unc.get("realizations")
    if reals:
        name = mc_distribution_plot(
            reals,
            unc.get("net_pay_p10"),
            unc.get("net_pay_p50"),
            unc.get("net_pay_p90"),
            fig_dir / f"{safe}_mc_dist.png",
        )
        added.append({"title": "Net-pay Monte-Carlo distribution", "file": f"figuras/{name}"})
    ledger.setdefault("figures", []).extend(added)
    return added


def field_map_plot(wells: list[dict[str, Any]], out_path: str | Path) -> str | None:
    """Scatter of well positions (header LAT/LON) sized by net pay P50; None if no coordinates.

    The honest field map when header coordinates are present. Returns the PNG basename, or
    None when no well has usable LAT/LON (the caller then omits the map).
    """
    pts = [w for w in wells if w.get("latitude") and w.get("longitude")]
    if not pts:
        return None
    lon = [float(w["longitude"]) for w in pts]
    lat = [float(w["latitude"]) for w in pts]
    sizes = [max(10.0, float(w.get("net_pay_p50") or 0.0) * 5.0) for w in pts]
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.scatter(lon, lat, s=sizes, c="tab:green", alpha=0.6, edgecolors="k")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_title("Field well map (marker ∝ net pay P50)")
    ax.grid(True, alpha=0.3)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=90, bbox_inches="tight")
    plt.close(fig)
    return out.name


def generate_figures(
    uwi: str,
    depth: np.ndarray,
    curves: dict[str, np.ndarray],
    vsh: np.ndarray,
    phie: np.ndarray,
    sw: np.ndarray,
    params: dict[str, Any],
    out_dir: str | Path,
) -> list[dict[str, str]]:
    """Generate the report figures and return ``[{title, file}]`` for the ledger.

    Includes the composite log, the Pickett plot, and the validator's neutron-density
    crossplot when it was produced (same path convention as the harness).
    """
    safe = _safe(uwi)
    out_dir = Path(out_dir)
    fig_dir = out_dir / "figuras"

    def _pv(key: str, default: float) -> float:
        p = params.get(key)
        return float(p.value) if p is not None else default

    netpay_flag = apply_cutoffs(
        vsh, phie, sw, _pv("vsh_cutoff", 0.4), _pv("phie_cutoff", 0.08), _pv("sw_cutoff", 0.6)
    )

    # Figures live under <out_dir>/figuras/; the ledger keeps the relative ref so report
    # links resolve from the report.md at the out_dir root.
    figures: list[dict[str, str]] = []
    composite = composite_log_plot(
        depth, curves, vsh, phie, sw, netpay_flag, fig_dir / f"{safe}_composite.png"
    )
    figures.append({"title": "Composite log", "file": f"figuras/{composite}"})
    if "RT" in curves:
        pickett = pickett_plot(
            curves["RT"],
            phie,
            _pv("a", 1.0),
            _pv("m", 2.0),
            _pv("Rw", 0.04),
            fig_dir / f"{safe}_pickett.png",
            n=_pv("n", 2.0),
        )
        figures.append({"title": "Pickett plot", "file": f"figuras/{pickett}"})
    crossplot = fig_dir / f"{uwi}_crossplot_nd.png"
    if crossplot.exists():
        figures.append({"title": "Neutron-density crossplot", "file": f"figuras/{crossplot.name}"})

    buckles = buckles_plot(phie, sw, fig_dir / f"{safe}_buckles.png")
    figures.append({"title": "Buckles plot", "file": f"figuras/{buckles}"})
    if "RT" in curves:
        hingle = hingle_plot(curves["RT"], phie, _pv("m", 2.0), fig_dir / f"{safe}_hingle.png")
        figures.append({"title": "Hingle plot", "file": f"figuras/{hingle}"})
    dist = distribution_plot(
        {"GR": curves.get("GR"), "PHIE": phie, "Sw": sw}, fig_dir / f"{safe}_distributions.png"
    )
    figures.append({"title": "Distributions", "file": f"figuras/{dist}"})
    return figures
