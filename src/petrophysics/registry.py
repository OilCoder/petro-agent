"""Method registry: the closed, vetted menu the agent selects from (v2).

The frontier of agency. Each entry maps a method ID to its function, the property it
computes, the curves it requires, and its citation/version. ``available_methods`` reports
which IDs are applicable given the present curves. The agent picks IDs from here and never
invokes anything outside it; electrical params (a, m, n, Rw, Rsh) come only from vetted
presets, never the LLM. Deferred methods (Waxman-Smits, MID) are NOT registered until they
have data + golden tests.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from src.petrophysics import electrofacies, permeability, rock_quality, sonic, sw, volumetrics, vsh
from src.petrophysics.phie import calc_phie, phi_density, phi_neutron
from src.validators.model_mismatch import neutron_density_crossplot

VERSION = "0.1.0"


@dataclass(frozen=True)
class MethodSpec:
    """A vetted method the agent may select."""

    id: str
    property: str  # "vsh" | "porosity" | "sw" | "lithology"
    fn: Callable[..., Any]
    required_curves: tuple[str, ...]
    citation: str
    version: str = "0.1.0"
    fixed_kwargs: dict[str, Any] = field(default_factory=dict)


METHOD_REGISTRY: dict[str, MethodSpec] = {
    "vsh_larionov_old": MethodSpec(
        "vsh_larionov_old",
        "vsh",
        vsh.calc_vsh,
        ("GR",),
        "Larionov 1969 (old rocks)",
        fixed_kwargs={"variant": vsh.OLD_ROCKS},
    ),
    "vsh_larionov_tertiary": MethodSpec(
        "vsh_larionov_tertiary",
        "vsh",
        vsh.calc_vsh,
        ("GR",),
        "Larionov 1969 (Tertiary)",
        fixed_kwargs={"variant": vsh.TERTIARY},
    ),
    "vsh_linear": MethodSpec(
        "vsh_linear", "vsh", vsh.vsh_linear, ("GR",), "Linear gamma-ray index (IGR)"
    ),
    "vsh_clavier": MethodSpec(
        "vsh_clavier", "vsh", vsh.vsh_clavier, ("GR",), "Clavier 1971 (non-linear)"
    ),
    "vsh_steiber": MethodSpec(
        "vsh_steiber", "vsh", vsh.vsh_steiber, ("GR",), "Steiber 1970 (non-linear)"
    ),
    "vsh_neutron_density": MethodSpec(
        "vsh_neutron_density",
        "vsh",
        vsh.vsh_neutron_density,
        ("RHOB", "NPHI"),
        "Neutron-density separation (non-GR clay indicator)",
    ),
    "vsh_multimineral": MethodSpec(
        "vsh_multimineral",
        "vsh",
        vsh.vsh_multimineral,
        ("RHOB", "NPHI"),
        "2-mineral volumetric solve (matrix+clay+porosity from RHOB+NPHI)",
    ),
    "phie_density_neutron": MethodSpec(
        "phie_density_neutron",
        "porosity",
        calc_phie,
        ("RHOB", "NPHI"),
        "Density-neutron crossplot, shale-corrected",
    ),
    "phi_density": MethodSpec(
        "phi_density", "porosity", phi_density, ("RHOB",), "Density porosity (single-curve)"
    ),
    "phi_neutron": MethodSpec(
        "phi_neutron", "porosity", phi_neutron, ("NPHI",), "Neutron porosity (single-curve)"
    ),
    "phi_sonic_wyllie": MethodSpec(
        "phi_sonic_wyllie", "porosity", sonic.phi_sonic_wyllie, ("DT",), "Wyllie 1956 time-average"
    ),
    "phi_sonic_rhg": MethodSpec(
        "phi_sonic_rhg", "porosity", sonic.phi_sonic_rhg, ("DT",), "Raymer-Hunt-Gardner 1980"
    ),
    "sw_archie": MethodSpec("sw_archie", "sw", sw.calc_sw, ("RT",), "Archie 1942"),
    "sw_simandoux": MethodSpec(
        "sw_simandoux", "sw", sw.sw_simandoux, ("RT",), "Simandoux 1963 (shaly sand)"
    ),
    "sw_indonesia": MethodSpec(
        "sw_indonesia", "sw", sw.sw_indonesia, ("RT",), "Poupon-Leveaux 1971 (Indonesia)"
    ),
    "litho_nd_crossplot": MethodSpec(
        "litho_nd_crossplot",
        "lithology",
        neutron_density_crossplot,
        ("RHOB", "NPHI"),
        "Neutron-density lithology crossplot",
    ),
    # MODELO depth methods (uncalibrated; selected by the model, computed by the engine)
    "perm_timur": MethodSpec(
        "perm_timur",
        "permeability",
        permeability.perm_timur,
        ("RT", "RHOB", "NPHI"),
        "Timur 1968 (uncalibrated)",
    ),
    "perm_coates": MethodSpec(
        "perm_coates",
        "permeability",
        permeability.perm_coates,
        ("RT", "RHOB", "NPHI"),
        "Coates 1981 (uncalibrated)",
    ),
    "rqi": MethodSpec(
        "rqi", "rock_quality", rock_quality.rqi, ("RT", "RHOB", "NPHI"), "Amaefule 1993 RQI"
    ),
    "fzi": MethodSpec(
        "fzi", "rock_quality", rock_quality.fzi, ("RT", "RHOB", "NPHI"), "Amaefule 1993 FZI"
    ),
    "winland_r35": MethodSpec(
        "winland_r35",
        "rock_quality",
        rock_quality.winland_r35,
        ("RT", "RHOB", "NPHI"),
        "Winland R35",
    ),
    "electrofacies": MethodSpec(
        "electrofacies",
        "facies",
        electrofacies.electrofacies_summary,
        ("GR", "RHOB", "NPHI"),
        "Unsupervised k-means electrofacies (no core labels)",
    ),
    "bvw": MethodSpec(
        "bvw",
        "derived",
        volumetrics.bvw,
        ("RHOB", "NPHI", "RT"),
        "Bulk-volume water = PHIE*Sw (Asquith 1985)",
    ),
}


# Vetted electrical-parameter presets (a, m, n, Rw, Rsh) — supplied by ID, never by the LLM.
ELECTRICAL_PRESETS: dict[str, dict[str, float]] = {
    "carbonate_default": {"a": 1.0, "m": 2.0, "n": 2.0, "rw": 0.04, "rsh": 2.0},
    "sandstone_default": {"a": 0.62, "m": 2.15, "n": 2.0, "rw": 0.04, "rsh": 4.0},
}

# Vetted sonic matrix/fluid transit-time presets (µs/ft) — supplied by ID, never by the LLM.
MATRIX_PRESETS: dict[str, dict[str, float]] = {
    "limestone": {"dt_matrix": 47.5, "dt_fluid": 189.0},
    "sandstone": {"dt_matrix": 55.5, "dt_fluid": 189.0},
    "dolomite": {"dt_matrix": 43.5, "dt_fluid": 189.0},
}

# Vetted net-pay cutoff presets — supplied by ID, never by the LLM.
CUTOFF_PRESETS: dict[str, dict[str, float]] = {
    "carbonate_conservative": {"vsh_cutoff": 0.35, "phie_cutoff": 0.10, "sw_cutoff": 0.50},
    "sandstone_standard": {"vsh_cutoff": 0.40, "phie_cutoff": 0.08, "sw_cutoff": 0.60},
}


def available_methods(curves: dict[str, Any]) -> dict[str, list[str]]:
    """Return applicable method IDs per property given the present (canonical) curves.

    A method is applicable iff all its required curves are present. The agent selects only
    from this result; an ID not returned here is out of scope (rejected by the dispatcher).
    """
    present = set(curves)
    out: dict[str, list[str]] = {}
    for spec in METHOD_REGISTRY.values():
        if set(spec.required_curves) <= present:
            out.setdefault(spec.property, []).append(spec.id)
    return out
