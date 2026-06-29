"""Golden tests for net-pay aggregation (apply_cutoffs, net_sand, net_reservoir...)."""

import numpy as np

from src.petrophysics.netpay import (
    apply_cutoffs,
    compute_net_pay,
    net_reservoir,
    net_sand,
    net_to_gross,
)

VSH_C, PHIE_C, SW_C, STEP = 0.40, 0.08, 0.60, 0.5

# index:        0     1     2     3
VSH = np.array([0.10, 0.10, 0.10, 0.50])
PHIE = np.array([0.20, 0.20, 0.05, 0.20])
SW = np.array([0.30, 0.70, 0.30, 0.30])


def test_cutoffs_all_pass():
    flag = apply_cutoffs(VSH[:1], PHIE[:1], SW[:1], VSH_C, PHIE_C, SW_C)
    assert bool(flag[0]) is True


def test_cutoffs_per_cutoff_rejection():
    flag = apply_cutoffs(VSH, PHIE, SW, VSH_C, PHIE_C, SW_C)
    # only index 0 passes all three; 1 fails Sw, 2 fails PHIE, 3 fails Vsh
    assert list(flag) == [True, False, False, False]


def test_cutoffs_nan_excluded():
    flag = apply_cutoffs(np.array([np.nan]), np.array([0.2]), np.array([0.3]), VSH_C, PHIE_C, SW_C)
    assert bool(flag[0]) is False


def test_cutoffs_boundary_inclusive():
    # values exactly at the cutoff must pass (<=, >=)
    flag = apply_cutoffs(
        np.array([VSH_C]), np.array([PHIE_C]), np.array([SW_C]), VSH_C, PHIE_C, SW_C
    )
    assert bool(flag[0]) is True


def test_net_pay_thickness():
    flag = apply_cutoffs(VSH, PHIE, SW, VSH_C, PHIE_C, SW_C)
    assert compute_net_pay(flag, STEP) == 0.5  # 1 sample * 0.5


def test_three_tier_ordering():
    sand = net_sand(VSH, VSH_C, STEP)
    reservoir = net_reservoir(VSH, PHIE, VSH_C, PHIE_C, STEP)
    pay = compute_net_pay(apply_cutoffs(VSH, PHIE, SW, VSH_C, PHIE_C, SW_C), STEP)
    assert sand == 1.5 and reservoir == 1.0 and pay == 0.5
    assert pay <= reservoir <= sand


def test_net_sand_nan_excluded():
    assert net_sand(np.array([np.nan, 0.1]), VSH_C, STEP) == 0.5


def test_net_to_gross_zero_gross_guard():
    assert net_to_gross(0.0, 0.0) == 0.0
    assert net_to_gross(5.0, 10.0) == 0.5
