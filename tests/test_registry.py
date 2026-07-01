"""Tests for the method registry and available_methods (V2-A)."""

from src.petrophysics.registry import (
    CUTOFF_PRESETS,
    ELECTRICAL_PRESETS,
    METHOD_REGISTRY,
    available_methods,
)


def test_registry_has_multiple_methods_per_property():
    by_prop: dict[str, int] = {}
    for spec in METHOD_REGISTRY.values():
        by_prop[spec.property] = by_prop.get(spec.property, 0) + 1
    # the point of v2: real choice -> >=2 methods for vsh, porosity, sw
    assert by_prop["vsh"] >= 2 and by_prop["porosity"] >= 2 and by_prop["sw"] >= 2


def test_available_methods_filters_by_curves():
    # only GR + RT present -> vsh (GR) and sw (RT) available; no porosity (needs RHOB/NPHI/DT)
    avail = available_methods({"GR": None, "RT": None})
    assert "vsh_linear" in avail.get("vsh", [])
    assert "vsh_neutron_density" not in avail.get("vsh", [])  # needs RHOB+NPHI
    assert "sw_simandoux" in avail.get("sw", [])
    assert "porosity" not in avail  # no RHOB/NPHI/DT


def test_available_methods_full_suite():
    avail = available_methods({"GR": None, "RHOB": None, "NPHI": None, "RT": None, "DT": None})
    assert "phie_density_neutron" in avail["porosity"]
    assert "phi_sonic_wyllie" in avail["porosity"]  # DT present
    assert "litho_nd_crossplot" in avail["lithology"]
    assert "vsh_neutron_density" in avail["vsh"]  # non-GR method now selectable (RHOB+NPHI present)


def test_registry_ids_self_consistent():
    for key, spec in METHOD_REGISTRY.items():
        assert key == spec.id and callable(spec.fn) and spec.required_curves


def test_presets_have_required_keys():
    for p in ELECTRICAL_PRESETS.values():
        assert {"a", "m", "n", "rw", "rsh"} <= set(p)
    for c in CUTOFF_PRESETS.values():
        assert {"vsh_cutoff", "phie_cutoff", "sw_cutoff"} <= set(c)
