"""Objection record + objection typing.

Objection types (Charter / design problem #5):
- ``mechanical``  : anchored to something external (physical bound, cross-curve). Must correct.
- ``support``     : context-free ("not justified by what is presented"). Justify or correct.
- ``irreducible`` : data-limited ("cannot validate — no core"). Not looped; escalates to gating.
"""

from __future__ import annotations

from dataclasses import dataclass

VERSION = "0.1.0"

MECHANICAL, SUPPORT, IRREDUCIBLE = "mechanical", "support", "irreducible"
_TYPES = (MECHANICAL, SUPPORT, IRREDUCIBLE)


@dataclass(frozen=True)
class Objection:
    """A single typed objection raised by a validator."""

    validator_id: str
    objection_type: str
    detail: str
    severity: str = "high"

    def __post_init__(self) -> None:
        if self.objection_type not in _TYPES:
            raise ValueError(f"unknown objection type: {self.objection_type!r}")
