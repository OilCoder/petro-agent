"""Regression: vsh_step's default calibration name must be a registry key.

The report's [FIJO] Vsh section marks "Selected" with a checkmark by comparing
``vsh_comparison.selected`` against the comparison-table keys. The engine default
used to record ``vsh_larionov_old_rocks`` (internal variant name), which is not a
table key (``vsh_larionov_old``), so the column rendered empty in free mode even
after the seed-baseline fallback was fixed.
"""

import numpy as np

from src.orchestrator.steps import vsh_step
from src.petrophysics.vsh import vsh_method_comparison

GR = np.linspace(20.0, 100.0, 30)


def test_default_old_rocks_calibration_uses_registry_key():
    _, cal = vsh_step({"GR": GR}, 20.0, 120.0, "old_rocks", method=None)
    selected = cal["vsh_method"]["value"]
    assert selected == "vsh_larionov_old"
    assert selected in vsh_method_comparison(GR, 20.0, 120.0)
    assert cal["vsh_method"]["chosen_by_model"] is False


def test_default_tertiary_calibration_uses_registry_key():
    _, cal = vsh_step({"GR": GR}, 20.0, 120.0, "tertiary", method=None)
    selected = cal["vsh_method"]["value"]
    assert selected == "vsh_larionov_tertiary"
    assert selected in vsh_method_comparison(GR, 20.0, 120.0)
