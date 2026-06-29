"""Load the parameter config and resolve parameters with provenance.

Provenance hierarchy: well_overrides (per-UWI) -> regional_defaults. The PROV header
tag drives the Larionov variant. The config file's SHA-256 hash is logged in the ledger.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from src.params.schema import ParamValue

VERSION = "0.1.0"

_DEFAULTS_PATH = Path(__file__).with_name("regional_defaults.json")
_ALIASES_PATH = Path(__file__).with_name("mnemonic_aliases.json")

_PROV_TO_VARIANT = {"paleozoic": "old_rocks", "tertiary": "tertiary"}


def load_config(path: str | Path = _DEFAULTS_PATH) -> dict:
    """Load the parameter config JSON."""
    return json.loads(Path(path).read_text())


def load_aliases(path: str | Path = _ALIASES_PATH) -> dict[str, list[str]]:
    """Load the canonical mnemonic alias map."""
    return json.loads(Path(path).read_text())


def config_hash(path: str | Path = _DEFAULTS_PATH) -> str:
    """SHA-256 of the config file (logged in the ledger run object for reproducibility)."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _to_param(entry: dict) -> ParamValue:
    return ParamValue(
        value=float(entry["value"]),
        unit=str(entry["unit"]),
        provenance=str(entry["provenance"]),
        source_description=str(entry["source_description"]),
    )


def resolve_param(config: dict, region: str, key: str, uwi: str | None = None) -> ParamValue:
    """Resolve one parameter: a per-UWI override wins over the regional default.

    Raises:
        KeyError: if the region or key is unknown.
    """
    overrides = config.get("well_overrides", {})
    if uwi and uwi in overrides and key in overrides[uwi]:
        return _to_param(overrides[uwi][key])
    region_block = config["regional_defaults"][region]
    return _to_param(region_block[key])


def resolve_all(config: dict, region: str, uwi: str | None = None) -> dict[str, ParamValue]:
    """Resolve every parameter in a region (applying any per-UWI overrides)."""
    keys = config["regional_defaults"][region].keys()
    return {k: resolve_param(config, region, k, uwi) for k in keys}


def larionov_variant(prov: str) -> tuple[str, bool]:
    """Map a PROV tag to a Larionov variant.

    Returns ``(variant, degraded)``; an absent/unrecognised tag falls back to
    ``old_rocks`` with ``degraded=True`` (caller logs a degradation entry).
    """
    key = (prov or "").strip().lower()
    if key in _PROV_TO_VARIANT:
        return _PROV_TO_VARIANT[key], False
    return "old_rocks", True
