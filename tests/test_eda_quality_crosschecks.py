"""Golden tests for CXR-5: service-porosity cross-check, microlog scan, DRHO badhole."""

import numpy as np

from src.eda.explore import microlog_scan, service_porosity_summary


def test_service_porosity_percent_normalized():
    curves = {"PHID_SVC": np.full(50, 25.0), "NPHI_DOL": np.full(50, 0.18)}
    out = service_porosity_summary(curves)
    assert out["phid_svc_mean"] == 0.25  # PU% -> fraction
    assert out["nphi_dol_mean"] == 0.18  # already fraction, untouched


def test_service_porosity_skips_thin_curves():
    assert service_porosity_summary({"PHID_SVC": np.full(5, 20.0)}) == {}


def test_microlog_separation_fractions():
    mnor = np.array([6.0, 5.0, 4.0, np.nan])
    minv = np.array([5.0, 5.5, 3.0, 1.0])
    out = microlog_scan(mnor, minv)
    assert out["n"] == 3
    assert out["frac_permeable"] == round(2 / 3, 3)  # separations +1, -0.5, +1


def test_microlog_absent_curves():
    assert microlog_scan(None, np.array([1.0])) == {"n": 0}


def test_drho_badhole_masks_rhob():
    from src.io.loader import WellData
    from src.qc.gate import qc_gate

    n = 200
    depth = np.linspace(1000.0, 1100.0, n)
    rhob = np.full(n, 2.5)
    drho = np.zeros(n)
    drho[:20] = 0.4  # unreliable compensation at the top
    well = WellData(
        source_path="synthetic",
        well_name="w",
        uwi="w",
        prov="old_rocks",
        depth_m=depth,
        step_m=0.5,
        curves={
            "GR": np.full(n, 50.0),
            "RHOB": rhob,
            "NPHI": np.full(n, 0.15),
            "RT": np.full(n, 10.0),
            "DRHO": drho,
        },
    )
    res = qc_gate(well)
    assert np.all(np.isnan(res.curves["RHOB"][:20]))  # masked where |DRHO| > 0.25
    assert np.all(np.isfinite(res.curves["RHOB"][25:]))
    assert any("drho" in str(e.get("detail", "")) for e in res.edits)
