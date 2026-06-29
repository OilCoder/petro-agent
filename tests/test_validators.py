"""Tests for the Phase-3 independent validator harness."""

import numpy as np
import pytest

from src.validators.harness import run_validators
from src.validators.model_mismatch import neutron_density_crossplot
from src.validators.objections import IRREDUCIBLE, MECHANICAL, SUPPORT, Objection
from src.validators.physical import (
    rt_sw_consistency,
    validate_bounds,
    vsh_phie_anticorrelation,
)


def test_objection_type_validation():
    assert Objection("x", MECHANICAL, "d").objection_type == MECHANICAL
    assert SUPPORT and IRREDUCIBLE  # constants exist
    with pytest.raises(ValueError):
        Objection("x", "bogus", "d")


def test_bounds_clean():
    objs = validate_bounds(np.array([0.1, 0.2]), np.array([0.1, 0.2]), np.array([0.3, 0.4]))
    assert objs == []


def test_bounds_violation_is_mechanical():
    objs = validate_bounds(np.array([1.5]), np.array([0.1]), np.array([0.3]))
    assert len(objs) == 1 and objs[0].objection_type == MECHANICAL


def test_vsh_phie_anticorrelation_flags_positive_corr():
    # strongly positively correlated Vsh & PHIE -> support objection
    vsh = np.linspace(0.1, 0.5, 25)
    phie = np.linspace(0.05, 0.25, 25)
    objs = vsh_phie_anticorrelation(vsh, phie)
    assert len(objs) == 1 and objs[0].objection_type == SUPPORT


def test_vsh_phie_ok_when_anticorrelated():
    vsh = np.linspace(0.1, 0.5, 25)
    phie = np.linspace(0.25, 0.05, 25)  # decreasing -> negative correlation
    assert vsh_phie_anticorrelation(vsh, phie) == []


def test_rt_sw_consistency_flags():
    objs = rt_sw_consistency(np.array([2.0]), np.array([0.2]), rt_floor=5.0)
    assert len(objs) == 1 and objs[0].objection_type == MECHANICAL


def test_crossplot_png_and_mismatch(tmp_path):
    # low-porosity RHOB ~2.65 (sandstone) but assumed limestone 2.71 -> mismatch
    rhob = np.concatenate([np.full(10, 2.65), np.full(10, 2.30)])
    nphi = np.concatenate([np.full(10, 0.02), np.full(10, 0.25)])
    out = tmp_path / "xplot.png"
    objs = neutron_density_crossplot(rhob, nphi, out, rho_ma=2.71)
    assert out.exists()
    assert len(objs) == 1 and "model_mismatch" in objs[0].validator_id


def test_harness_runs(tmp_path):
    n = 30
    curves = {
        "RT": np.full(n, 10.0),
        "RHOB": np.full(n, 2.68),
        "NPHI": np.linspace(0.02, 0.2, n),
    }
    objs = run_validators(
        np.full(n, 0.2),
        np.full(n, 0.15),
        np.full(n, 0.35),
        curves,
        out_dir=str(tmp_path),
        uwi="TEST",
    )
    assert isinstance(objs, list)
    assert (tmp_path / "figuras" / "TEST_crossplot_nd.png").exists()
