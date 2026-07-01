"""Monte Carlo propagation of parameter uncertainty into net pay (P10/P50/P90).

Samples the high-leverage Archie parameters (Rw, m, n, a) from their ranges and
recomputes Sw -> net pay per realization. Vsh/PHIE do not depend on these, so the
uncertainty enters through Sw (the design's "most-leverage, least-computable" error).
"""

from __future__ import annotations

from typing import Any

import numpy as np

from src.petrophysics.netpay import apply_cutoffs, compute_net_pay
from src.petrophysics.sw import calc_sw

VERSION = "0.1.0"

# Default ranges for the uncertain Archie parameters (used when provenance == default).
DEFAULT_RANGES: dict[str, tuple[float, float]] = {
    "Rw": (0.02, 0.06),
    "m": (1.8, 2.5),
    "n": (1.8, 2.2),
    "a": (0.6, 1.0),
}


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
    """
    ranges = ranges or DEFAULT_RANGES
    rng = np.random.default_rng(seed)
    net_pays = np.empty(n, dtype=float)
    for i in range(n):
        a = rng.uniform(*ranges["a"]) if "a" in ranges else base["a"]
        m = rng.uniform(*ranges["m"]) if "m" in ranges else base["m"]
        nn = rng.uniform(*ranges["n"]) if "n" in ranges else base["n"]
        rw = rng.uniform(*ranges["Rw"]) if "Rw" in ranges else base["Rw"]
        sw = calc_sw(rt, phie, a, m, nn, rw)
        flag = apply_cutoffs(
            vsh, phie, sw, cutoffs["vsh_cutoff"], cutoffs["phie_cutoff"], cutoffs["sw_cutoff"]
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
