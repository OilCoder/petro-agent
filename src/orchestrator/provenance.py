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


def pin_versions(seeds: dict[str, int] | None = None) -> dict[str, Any]:
    """Collect all pinned versions/seeds for the ledger run object."""
    from src.petrophysics import phie, sw, vsh

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
        },
        "seeds": seeds or {"monte_carlo": 42},
    }
