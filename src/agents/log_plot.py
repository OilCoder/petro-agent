"""Deterministic figure generation for the report (composite log + Pickett plot).

Matplotlib (Agg) renders the standard petrophysical figures a reviewer expects. Each
function saves a PNG to ``out_dir`` and returns its basename; ``generate_figures``
collects them (plus the validator's neutron-density crossplot) into the list the report
renderer embeds. Figures visualize numbers the engine already computed — they author none.
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
    return figures
