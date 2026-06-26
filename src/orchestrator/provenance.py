"""Version pinning for the ledger: git SHA, library versions, engine versions, seeds.

Makes a run reproducible and defensible months later (Charter Invariant 5 / problem #8).
"""

from __future__ import annotations

import subprocess
from importlib import metadata
from pathlib import Path
from typing import Any

VERSION = "0.1.0"

_REPO = Path(__file__).resolve().parents[2]


def _git_sha() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=_REPO,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return out.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _pkg(name: str) -> str:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return "absent"


def model_digest(model: str) -> str:
    """Best-effort Ollama model digest (id), so a re-pulled tag is detectable. 'unknown' if absent.

    The model identity in the methodology graph must be (name + digest): two runs with the
    same seed but a different underlying model are then distinguishable in the ledger (V2-G).
    """
    try:
        out = subprocess.run(
            ["ollama", "list"], capture_output=True, text=True, timeout=5, check=False
        )
        for line in out.stdout.splitlines():
            parts = line.split()
            if parts and parts[0] == model and len(parts) > 1:
                return parts[1]
    except (OSError, subprocess.SubprocessError):
        pass
    return "unknown"


def pin_versions(seeds: dict[str, int] | None = None) -> dict[str, Any]:
    """Collect all pinned versions/seeds for the ledger run object."""
    from src.petrophysics import phie, registry, sw, vsh

    return {
        "git_sha": _git_sha(),
        "libraries": {
            "lasio": _pkg("lasio"),
            "numpy": _pkg("numpy"),
            "langgraph": _pkg("langgraph"),
            "ollama": _pkg("ollama"),
            "matplotlib": _pkg("matplotlib"),
        },
        "engine_versions": {
            "calc_vsh": vsh.VERSION,
            "calc_phie": phie.VERSION,
            "calc_sw": sw.VERSION,
            "formula_registry": registry.VERSION,
        },
        "seeds": seeds or {"monte_carlo": 42},
    }
