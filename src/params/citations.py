"""Static curated citations table (no RAG). Each parameter resolves to exactly one source.

An unknown parameter hard-fails — the system never emits a guessed citation.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.params.schema import Citation

VERSION = "0.1.0"

_CITATIONS_PATH = Path(__file__).with_name("citations.json")


def load_citations(path: str | Path = _CITATIONS_PATH) -> dict[str, Citation]:
    """Load the citations table into typed :class:`Citation` records."""
    raw = json.loads(Path(path).read_text())
    return {key: Citation(parameter=key, **fields) for key, fields in raw.items()}


def cite(parameter: str, table: dict[str, Citation] | None = None) -> Citation:
    """Return the frozen citation for a parameter.

    Raises:
        KeyError: if the parameter has no curated citation (hard fail, never guess).
    """
    table = table if table is not None else load_citations()
    if parameter not in table:
        raise KeyError(f"no curated citation for parameter {parameter!r} (hard fail)")
    return table[parameter]
