"""Lithology model-mismatch detection via the neutron-density cross-plot.

Emits a cross-plot PNG and flags when the data signature contradicts the assumed
matrix density. The M-N cross-plot is DEFERRED for v1 (gated on DT/PEF presence —
unification decision); v1 relies on the neutron-density cross-plot only.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from src.validators.objections import MECHANICAL, Objection  # noqa: E402

VERSION = "0.1.0"

# Matrix densities (g/cc) for the reference lithology lines.
_MATRIX = {"sandstone": 2.65, "limestone": 2.71, "dolomite": 2.87}


def neutron_density_crossplot(
    rhob: np.ndarray,
    nphi: np.ndarray,
    out_path: str | Path,
    rho_ma: float = 2.71,
    tol: float = 0.05,
) -> list[Objection]:
    """Generate the ND cross-plot PNG and flag matrix-density model mismatch.

    Heuristic: in low-porosity rock (NPHI < 0.05) bulk density approaches the matrix
    density. If the median RHOB there deviates from the assumed ``rho_ma`` by more than
    ``tol``, raise a mechanical objection (wrong matrix → wrong PHIE).
    """
    r = np.asarray(rhob, dtype=float)
    p = np.asarray(nphi, dtype=float)

    fig, ax = plt.subplots(figsize=(5, 5))
    valid = np.isfinite(r) & np.isfinite(p)
    ax.scatter(p[valid], r[valid], s=6, alpha=0.4, label="data")
    for name, rma in _MATRIX.items():
        ax.plot([0, 0.45], [rma, 1.0], lw=1, label=name)
    ax.set_xlabel("NPHI (v/v)")
    ax.set_ylabel("RHOB (g/cc)")
    ax.set_ylim(3.0, 1.0)
    ax.set_xlim(-0.05, 0.5)
    ax.legend(fontsize=7)
    ax.set_title("Neutron-density cross-plot")
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=90, bbox_inches="tight")
    plt.close(fig)

    low_phi = valid & (p < 0.05)
    if np.count_nonzero(low_phi) >= 5:
        med = float(np.median(r[low_phi]))
        if abs(med - rho_ma) > tol:
            nearest = min(_MATRIX, key=lambda k: abs(_MATRIX[k] - med))
            return [
                Objection(
                    "model_mismatch_nd",
                    MECHANICAL,
                    f"low-porosity RHOB median {med:.2f} ~ {nearest} ({_MATRIX[nearest]}), "
                    f"not assumed rho_ma {rho_ma:.2f}",
                )
            ]
    return []
