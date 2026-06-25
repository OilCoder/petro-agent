"""Tests for Phase-2 parameter resolution, provenance, config hash, and citations."""

import pytest

from src.params.citations import cite, load_citations
from src.params.config_loader import (
    config_hash,
    larionov_variant,
    load_aliases,
    load_config,
    resolve_all,
    resolve_param,
)
from src.params.schema import DEFAULT

REGION = "paleozoic_kansas"


def test_resolve_param_default():
    p = resolve_param(load_config(), REGION, "m")
    assert p.value == 2.0 and p.provenance == DEFAULT and p.source_description


def test_resolve_all_keys():
    params = resolve_all(load_config(), REGION)
    for key in ("gr_min", "gr_max", "a", "m", "n", "Rw", "rho_ma", "vsh_cutoff"):
        assert key in params and params[key].provenance in ("core", "offset", "default")


def test_well_override_precedence():
    cfg = load_config()
    cfg["well_overrides"] = {
        "15-135-99999": {
            "Rw": {
                "value": 0.038,
                "unit": "ohm-m",
                "provenance": "core",
                "source_description": "core/SP-derived for this well",
            }
        }
    }
    p = resolve_param(cfg, REGION, "Rw", uwi="15-135-99999")
    assert p.value == 0.038 and p.provenance == "core"
    # different well falls through to regional default
    assert resolve_param(cfg, REGION, "Rw", uwi="other").provenance == DEFAULT


def test_config_hash_is_stable_hex():
    h = config_hash()
    assert len(h) == 64 and config_hash() == h


def test_larionov_variant():
    assert larionov_variant("paleozoic") == ("old_rocks", False)
    assert larionov_variant("tertiary") == ("tertiary", False)
    assert larionov_variant("unknown") == ("old_rocks", True)
    assert larionov_variant("") == ("old_rocks", True)


def test_aliases_load():
    aliases = load_aliases()
    assert "RHOZ" in aliases["RHOB"] and "ILD" in aliases["RT"]


def test_cite_resolves_to_one_source():
    table = load_citations()
    c = cite("m", table)
    assert c.author.startswith("Archie") and c.year == "1942"


def test_cite_unknown_hardfails():
    with pytest.raises(KeyError):
        cite("nonexistent_param")
