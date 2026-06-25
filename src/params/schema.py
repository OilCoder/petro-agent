"""Typed records for parameters and citations."""

from __future__ import annotations

from dataclasses import dataclass

CORE, OFFSET, DEFAULT = "core", "offset", "default"
_TIERS = (CORE, OFFSET, DEFAULT)


@dataclass(frozen=True)
class ParamValue:
    """A resolved parameter with its provenance."""

    value: float
    unit: str
    provenance: str  # core | offset | default
    source_description: str

    def __post_init__(self) -> None:
        if self.provenance not in _TIERS:
            raise ValueError(f"unknown provenance tier: {self.provenance!r}")


@dataclass(frozen=True)
class Citation:
    """A frozen literature/source citation for a parameter."""

    parameter: str
    value: str
    valid_range: str
    author: str
    year: str
    locator: str
    scope: str
