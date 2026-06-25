"""Physical-bounds and cross-curve consistency validators (deterministic)."""

from __future__ import annotations

import numpy as np

from src.validators.objections import IRREDUCIBLE, MECHANICAL, SUPPORT, Objection

VERSION = "0.1.0"


def net_pay_plausibility(
    net_pay_m: float,
    gross_m: float,
    avg_phie: float,
    ntg_max: float = 0.5,
    phie_plausible_max: float = 0.25,
) -> list[Objection]:
    """Flag physically implausible net-pay results (terminal, data-limited check).

    A net-to-gross above ``ntg_max`` or a net-pay average porosity above
    ``phie_plausible_max`` is not credible for a tight Mississippian carbonate and
    signals uncalibrated cutoffs/Rw. Typed ``irreducible`` — it cannot be resolved
    without calibration data, so it degrades confidence rather than looping.

    Args:
        net_pay_m: total net-pay thickness (m).
        gross_m: gross logged interval (m).
        avg_phie: mean effective porosity over the net-pay interval (v/v).
        ntg_max: maximum plausible net-to-gross.
        phie_plausible_max: maximum plausible net-pay average porosity.

    Returns:
        A list of irreducible objections (empty if the result is plausible).
    """
    objs: list[Objection] = []
    ntg = net_pay_m / gross_m if gross_m > 0 else 0.0
    if ntg > ntg_max:
        objs.append(Objection(
            "net_pay_plausibility", IRREDUCIBLE,
            f"NTG {ntg:.2f} > {ntg_max} — implausibly high for tight carbonate "
            f"(uncalibrated cutoffs/Rw)",
        ))
    if np.isfinite(avg_phie) and avg_phie > phie_plausible_max:
        objs.append(Objection(
            "net_pay_plausibility", IRREDUCIBLE,
            f"net-pay avg PHIE {avg_phie:.2f} > {phie_plausible_max} — implausibly high "
            f"for carbonate",
        ))
    return objs


def validate_bounds(
    vsh: np.ndarray, phie: np.ndarray, sw: np.ndarray, phie_max: float = 0.45
) -> list[Objection]:
    """Flag any non-NaN sample outside physical bounds (mechanical objections)."""
    objs: list[Objection] = []
    checks = [
        ("vsh_bounds", vsh, 0.0, 1.0),
        ("phie_bounds", phie, 0.0, phie_max),
        ("sw_bounds", sw, 0.0, 1.0),
    ]
    for vid, arr, lo, hi in checks:
        a = np.asarray(arr, dtype=float)
        with np.errstate(invalid="ignore"):
            bad = (a < lo) | (a > hi)
        bad &= ~np.isnan(a)
        n = int(np.count_nonzero(bad))
        if n:
            objs.append(
                Objection(vid, MECHANICAL, f"{n} samples outside [{lo}, {hi}]")
            )
    return objs


def vsh_phie_anticorrelation(
    vsh: np.ndarray, phie: np.ndarray, window: int = 20, threshold: float = 0.3
) -> list[Objection]:
    """Flag windows where Vsh and PHIE are strongly *positively* correlated.

    Shale volume and porosity should not co-increase without explanation. A Pearson
    correlation > ``threshold`` in any ``±window`` block raises a support objection.
    """
    v = np.asarray(vsh, dtype=float)
    p = np.asarray(phie, dtype=float)
    n = v.size
    worst = -1.0
    for i in range(0, n, window):
        vv, pp = v[i : i + window], p[i : i + window]
        mask = np.isfinite(vv) & np.isfinite(pp)
        if mask.sum() < 3:
            continue
        if np.std(vv[mask]) == 0 or np.std(pp[mask]) == 0:
            continue
        r = float(np.corrcoef(vv[mask], pp[mask])[0, 1])
        worst = max(worst, r)
    if worst > threshold:
        return [
            Objection(
                "vsh_phie_anticorrelation",
                SUPPORT,
                f"Vsh-PHIE Pearson {worst:.2f} > {threshold} (dirty rock + high porosity)",
            )
        ]
    return []


def rt_sw_consistency(
    rt: np.ndarray, sw: np.ndarray, sw_threshold: float = 0.4, rt_floor: float = 5.0
) -> list[Objection]:
    """Flag depths where computed Sw < threshold but RT < floor (implausible: low Sw, low RT)."""
    r = np.asarray(rt, dtype=float)
    s = np.asarray(sw, dtype=float)
    with np.errstate(invalid="ignore"):
        bad = (s < sw_threshold) & (r < rt_floor)
    bad &= ~(np.isnan(r) | np.isnan(s))
    n = int(np.count_nonzero(bad))
    if n:
        return [
            Objection(
                "rt_sw_consistency",
                MECHANICAL,
                f"{n} depths with Sw<{sw_threshold} but RT<{rt_floor} ohm-m",
            )
        ]
    return []
