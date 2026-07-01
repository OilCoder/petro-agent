"""Monte Carlo propagation of parameter AND method uncertainty into net pay (P10/P50/P90).

Samples the high-leverage Archie parameters (Rw, m, n, a) from their ranges and recomputes Sw ->
net pay per realization. When ``vsh_alts``/``phie_alts`` are supplied, each realization also draws
one Vsh and one PHIE curve from the vetted METHOD alternatives — so the band reflects structural /
method uncertainty, not only parameter sensitivity (parameter-only bands read overconfident against
independent interpretations; see the VOLVE calibration in debug/).
"""

from __future__ import annotations

from typing import Any

import numpy as np

from src.petrophysics.netpay import apply_cutoffs, compute_net_pay
from src.petrophysics.phie import phi_density, phi_neutron
from src.petrophysics.sw import calc_sw
from src.petrophysics.vsh import vsh_clavier, vsh_linear

VERSION = "0.1.0"

# Default ranges for the uncertain Archie parameters (used when provenance == default).
DEFAULT_RANGES: dict[str, tuple[float, float]] = {
    "Rw": (0.02, 0.06),
    "m": (1.8, 2.5),
    "n": (1.8, 2.2),
    "a": (0.6, 1.0),
}


def build_method_alts(
    curves: dict[str, np.ndarray],
    vsh: np.ndarray,
    phie: np.ndarray,
    gr_min: float,
    gr_max: float,
    rho_ma: float,
    rho_fl: float,
    phie_max: float,
) -> tuple[list[np.ndarray], list[np.ndarray]]:
    """Vetted Vsh/PHIE method alternatives for ``propagate_net_pay``'s structural-uncertainty draw.

    The base curves plus the other vetted methods for each property (Vsh: linear, Clavier; PHIE:
    density-only, neutron-only). Feeding these to the MC widens the band to include method choice.
    """
    vsh_alts = [vsh]
    if "GR" in curves:
        vsh_alts += [
            vsh_linear(curves["GR"], gr_min, gr_max),
            vsh_clavier(curves["GR"], gr_min, gr_max),
        ]
    phie_alts = [phie]
    if "RHOB" in curves:
        phie_alts.append(phi_density(curves["RHOB"], rho_ma, rho_fl, phie_max))
    if "NPHI" in curves:
        phie_alts.append(phi_neutron(curves["NPHI"], phie_max))
    return vsh_alts, phie_alts


def propagate_net_pay(
    vsh: np.ndarray,
    phie: np.ndarray,
    rt: np.ndarray,
    base: dict[str, float],
    cutoffs: dict[str, float],
    step: float,
    ranges: dict[str, tuple[float, float]] | None = None,
    n: int = 500,
    seed: int = 42,
    vsh_alts: list[np.ndarray] | None = None,
    phie_alts: list[np.ndarray] | None = None,
) -> dict[str, Any]:
    """Return the net-pay distribution (P10/P50/P90) over Monte Carlo realizations.

    Args:
        vsh, phie, rt: computed/curve arrays.
        base: base parameter values (a, m, n, Rw, cutoffs already in ``cutoffs``).
        cutoffs: vsh_cutoff, phie_cutoff, sw_cutoff.
        step: depth step (m).
        ranges: per-parameter (lo, hi); defaults to :data:`DEFAULT_RANGES`.
        n: number of realizations.
        seed: RNG seed (logged for reproducibility).
        vsh_alts, phie_alts: optional vetted METHOD alternatives; when given, each realization
            draws one from each so the band captures method (structural) uncertainty too.
    """
    ranges = ranges or DEFAULT_RANGES
    rng = np.random.default_rng(seed)
    vsh_pool = vsh_alts if vsh_alts else [vsh]
    phie_pool = phie_alts if phie_alts else [phie]
    net_pays = np.empty(n, dtype=float)
    for i in range(n):
        a = rng.uniform(*ranges["a"]) if "a" in ranges else base["a"]
        m = rng.uniform(*ranges["m"]) if "m" in ranges else base["m"]
        nn = rng.uniform(*ranges["n"]) if "n" in ranges else base["n"]
        rw = rng.uniform(*ranges["Rw"]) if "Rw" in ranges else base["Rw"]
        v = vsh_pool[int(rng.integers(len(vsh_pool)))]
        p = phie_pool[int(rng.integers(len(phie_pool)))]
        sw = calc_sw(rt, p, a, m, nn, rw)
        flag = apply_cutoffs(
            v, p, sw, cutoffs["vsh_cutoff"], cutoffs["phie_cutoff"], cutoffs["sw_cutoff"]
        )
        net_pays[i] = compute_net_pay(flag, step)
    p10, p50, p90 = (float(x) for x in np.percentile(net_pays, [10, 50, 90]))
    return {
        "net_pay_p10": p10,
        "net_pay_p50": p50,
        "net_pay_p90": p90,
        "net_pay_mean": float(np.mean(net_pays)),
        "method": "monte_carlo",
        "n_realizations": n,
        "seed": seed,
        "methods_sampled": {"vsh": len(vsh_pool), "phie": len(phie_pool)},
        # the per-realization net pays, for the human-only Monte-Carlo distribution figure
        "realizations": [round(float(x), 2) for x in net_pays],
    }


def multi_seed_robustness(
    vsh: np.ndarray,
    phie: np.ndarray,
    rt: np.ndarray,
    base: dict[str, float],
    cutoffs: dict[str, float],
    step: float,
    seeds: tuple[int, ...] = (1, 7, 42, 99),
    n: int = 300,
) -> dict[str, Any]:
    """Robustness check: P50 net pay across multiple seeds should be stable."""
    p50s = [
        propagate_net_pay(vsh, phie, rt, base, cutoffs, step, n=n, seed=s)["net_pay_p50"]
        for s in seeds
    ]
    spread = float(max(p50s) - min(p50s))
    mean = float(np.mean(p50s))
    return {
        "p50_by_seed": p50s,
        "p50_spread": spread,
        "robust": bool(spread <= 0.10 * mean) if mean > 0 else True,
    }
