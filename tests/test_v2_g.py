"""V2-G: provenance pinning (Tier 1, CI-gating) + a model-in-the-loop smoke (Tier 2, manual).

Tier 1 runs in CI (no model). Tier 2 is skipped unless Ollama is reachable — it is
model-version-sensitive and excluded from the deterministic gate.
"""

import shutil
import subprocess

import numpy as np
import pytest

from src.orchestrator.provenance import model_digest, pin_versions

# ----------------------------------------
# Tier 1 — deterministic (CI-gating)
# ----------------------------------------


def test_pin_versions_includes_formula_registry():
    v = pin_versions()
    assert "formula_registry" in v["engine_versions"]


def test_model_digest_returns_string():
    assert isinstance(model_digest("nonexistent-model"), str)


# ----------------------------------------
# Tier 2 — model-in-the-loop (manual, non-gating)
# ----------------------------------------


def _ollama_up() -> bool:
    if not shutil.which("ollama"):
        return False
    try:
        return subprocess.run(["ollama", "list"], capture_output=True, timeout=5).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


@pytest.mark.skipif(not _ollama_up(), reason="Ollama not reachable (Tier 2, model-in-the-loop)")
def test_analyst_with_real_model_produces_graph():
    from src.agents.analyst import run_analyst
    from src.agents.client import make_chat

    n = 60
    ctx = {
        "curves": {
            "GR": np.full(n, 60.0),
            "RT": np.full(n, 8.0),
            "RHOB": np.full(n, 2.55),
            "NPHI": np.full(n, 0.22),
        },
        "phie": np.full(n, 0.2),
        "vsh": np.full(n, 0.35),
        "depth_m": np.arange(n, dtype=float) * 0.5,
        "step_m": 0.5,
        "quality_map": np.array(["GOOD"] * n, dtype=object),
    }
    ledger: dict = {}
    run_analyst(ledger, ctx, "free", make_chat(model="llama3.1:8b", seed=42), "llama3.1:8b")
    graph = ledger["run"]["methodology_graph"]
    assert graph["nodes"] and any(node["type"] == "decision" for node in graph["nodes"])
    assert "analyst" in ledger["run"]  # signaled record present whether or not it fell back
