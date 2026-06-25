"""Fixed validator harness: runs the full suite, returns a typed objection list.

The orchestrator (Phase 4) calls this; the agents never choose which checks fire.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from src.validators.model_mismatch import neutron_density_crossplot
from src.validators.objections import Objection
from src.validators.physical import (
    rt_sw_consistency,
    validate_bounds,
    vsh_phie_anticorrelation,
)

VERSION = "0.1.0"


def run_validators(
    vsh: np.ndarray,
    phie: np.ndarray,
    sw: np.ndarray,
    curves: dict[str, np.ndarray],
    phie_max: float = 0.45,
    rho_ma: float = 2.71,
    rt_floor: float = 5.0,
    out_dir: str | Path = "outputs",
    uwi: str = "well",
) -> list[Objection]:
    """Run the complete fixed validator suite and collect all objections."""
    objections: list[Objection] = []
    objections += validate_bounds(vsh, phie, sw, phie_max)
    objections += vsh_phie_anticorrelation(vsh, phie)
    if "RT" in curves:
        objections += rt_sw_consistency(curves["RT"], sw, rt_floor=rt_floor)
    if "RHOB" in curves and "NPHI" in curves:
        png = Path(out_dir) / f"{uwi}_crossplot_nd.png"
        objections += neutron_density_crossplot(
            curves["RHOB"], curves["NPHI"], png, rho_ma=rho_ma
        )
    return objections
