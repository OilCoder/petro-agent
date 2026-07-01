"""Tests for Phase-7 uncertainty (Monte Carlo, sensitivity), gating, and calibration."""

import os

import numpy as np

from src.evaluation.calibration import expected_calibration_error, reliability_diagram
from src.gating.rules import BRACKETED, FIRM, QUALIFIED, confidence_tier, high_leverage_flag
from src.orchestrator.graph import run_pipeline
from src.params.schema import ParamValue
from src.uncertainty.montecarlo import (
    build_method_alts,
    multi_seed_robustness,
    propagate_net_pay,
)
from src.uncertainty.sensitivity import sensitivity_net_pay

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "synthetic_oldrocks.las")

# arrays with real net pay: low Vsh, decent PHIE, varying RT
N = 40
VSH = np.full(N, 0.15)
PHIE = np.full(N, 0.20)
RT = np.linspace(2.0, 60.0, N)
BASE = {"a": 1.0, "m": 2.0, "n": 2.0, "Rw": 0.04}
CUTOFFS = {"vsh_cutoff": 0.40, "phie_cutoff": 0.08, "sw_cutoff": 0.60}
STEP = 0.5


def test_montecarlo_percentile_ordering():
    mc = propagate_net_pay(VSH, PHIE, RT, BASE, CUTOFFS, STEP, n=200, seed=42)
    assert mc["net_pay_p10"] <= mc["net_pay_p50"] <= mc["net_pay_p90"]
    assert mc["method"] == "monte_carlo" and mc["seed"] == 42
    # realizations exposed for the human-only MC distribution figure
    assert len(mc["realizations"]) == 200


def test_montecarlo_reproducible():
    a = propagate_net_pay(VSH, PHIE, RT, BASE, CUTOFFS, STEP, n=100, seed=7)
    b = propagate_net_pay(VSH, PHIE, RT, BASE, CUTOFFS, STEP, n=100, seed=7)
    assert a["net_pay_p50"] == b["net_pay_p50"]  # same seed -> identical


def test_method_alts_widen_the_band():
    # method (structural) uncertainty must widen the band vs parameter-only (VOLVE calibration fix)
    base_mc = propagate_net_pay(VSH, PHIE, RT, BASE, CUTOFFS, STEP, n=300, seed=1)
    wide_mc = propagate_net_pay(
        VSH,
        PHIE,
        RT,
        BASE,
        CUTOFFS,
        STEP,
        n=300,
        seed=1,
        vsh_alts=[VSH, np.full(N, 0.35)],
        phie_alts=[PHIE, np.full(N, 0.10)],
    )
    base_w = base_mc["net_pay_p90"] - base_mc["net_pay_p10"]
    wide_w = wide_mc["net_pay_p90"] - wide_mc["net_pay_p10"]
    assert wide_w > base_w
    assert wide_mc["methods_sampled"] == {"vsh": 2, "phie": 2}


def test_build_method_alts_from_curves():
    curves = {"GR": np.linspace(20, 100, N), "RHOB": np.full(N, 2.4), "NPHI": np.full(N, 0.2)}
    v_alts, p_alts = build_method_alts(curves, VSH, PHIE, 20.0, 120.0, 2.65, 1.0, 0.45, 0.10, 0.35)
    # base+linear+clavier+neutron-density+multimineral (2 non-GR) ; base+density+neutron
    assert len(v_alts) == 5 and len(p_alts) == 3


def test_sensitivity_identifies_dominant():
    sens = sensitivity_net_pay(VSH, PHIE, RT, BASE, CUTOFFS, STEP)
    assert sens["dominant_parameter"] in ("Rw", "m", "n", "a")
    assert sens["dominant_swing_m"] >= 0.0


def test_multi_seed_robustness():
    out = multi_seed_robustness(VSH, PHIE, RT, BASE, CUTOFFS, STEP, n=100)
    assert "robust" in out and len(out["p50_by_seed"]) == 4


def test_confidence_tier():
    assert confidence_tier(["default", "core"]) == BRACKETED
    assert confidence_tier(["offset", "core"]) == QUALIFIED
    assert confidence_tier(["core"]) == FIRM


def test_high_leverage_flag_warns_on_default():
    params = {"Rw": ParamValue(0.04, "ohm-m", "default", "regional")}
    flag = high_leverage_flag("Rw", params)
    assert flag["warn"] is True and "DEFAULT" in flag["message"]


def test_ece_perfect_calibration():
    conf = np.array([0.9, 0.9, 0.1, 0.1])
    correct = np.array([1.0, 1.0, 0.0, 0.0])  # 90%-conf correct, 10%-conf wrong
    assert expected_calibration_error(conf, correct, n_bins=10) < 0.2


def test_reliability_diagram_writes_png(tmp_path):
    conf = np.random.default_rng(0).uniform(0, 1, 50)
    correct = (conf > 0.5).astype(float)
    out = tmp_path / "rel.png"
    ece = reliability_diagram(conf, correct, out)
    assert out.exists() and ece >= 0.0


def test_pipeline_adds_uncertainty(tmp_path):
    ledger = run_pipeline(FIXTURE, out_dir=str(tmp_path), uncertainty=True)
    assert "uncertainty" in ledger
    assert "net_pay_p10_p50_p90" in ledger["run"]
    assert "dominant_parameter" in ledger["uncertainty"]["sensitivity"]
    # multi-seed robustness now wired into the report's uncertainty block
    assert "robust" in ledger["uncertainty"]["robustness"]
