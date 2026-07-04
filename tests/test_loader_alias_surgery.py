"""Regressions for the CXR-3 alias surgery: RHOC and GRD were mismapped; new canonicals load.

RHOC is the density CORRECTION (~0.1 g/cc), not bulk density — mapping it to RHOB corrupted
the 2 wells that carry RHOC without RHOB. GRD in this dataset is a guard-log RESISTIVITY
(ohm-m), not gamma — mapping it to GR made gamma≡resistivity in 2 wells.
"""

from src.io.loader import _match


def test_rhoc_is_density_correction_not_bulk_density():
    canon, _rank = _match("RHOC")
    assert canon == "DRHO"


def test_grd_is_guard_resistivity_not_gamma():
    canon, _rank = _match("GRD")
    assert canon == "RT"


def test_vintage_and_invasion_canonicals_resolve():
    assert _match("NEUT")[0] == "NEUT"
    assert _match("LL")[0] == "RT"
    assert _match("RILM")[0] == "RMED"
    assert _match("RLL3")[0] == "RXO"
    assert _match("MLL")[0] == "RXO"
    assert _match("CNDL")[0] == "NPHI_DOL"
    assert _match("DPOR")[0] == "PHID_SVC"
    assert _match("SON")[0] == "DT"


def test_rt_rank_prefers_deep_over_vintage():
    # RILD (deep induction) must outrank RES/LL/GRD fallbacks when several coexist
    assert _match("RILD")[1] < _match("RES")[1] < _match("GRD")[1]
