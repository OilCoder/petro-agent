"""Action frontier for the agentic loop: physics-valid next steps + recompute invalidation.

The orchestrator owns WHICH actions are valid at each step (the agent only picks one). Physics is
not a choice: ``available_actions`` enforces the dependency chain (PHIE needs Vsh, Sw needs PHIE,
…). Recompute is allowed — when a property is (re)computed, ``invalidate_downstream`` marks its
dependents stale so they must be recomputed for their sections to stay consistent.
"""

from __future__ import annotations

# Property produced by each compute action.
PRODUCES: dict[str, str] = {
    "compute_vsh": "vsh",
    "compute_phie": "phie",
    "compute_sw": "sw",
    "apply_cutoffs": "netpay",
    "run_uncertainty": "uncertainty",
    "permeability": "permeability",
    "rock_quality": "rock_quality",
    "electrofacies": "electrofacies",
    "lithology": "lithology",
}

# Compute action -> (prerequisite properties that must be VALID, required curves present).
_REQUIRES: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "compute_vsh": ((), ("GR",)),
    "compute_phie": (("vsh",), ("RHOB", "NPHI")),
    "compute_sw": (("phie",), ("RT",)),
    "apply_cutoffs": (("sw",), ()),
    "run_uncertainty": (("netpay",), ()),
    "permeability": (("phie", "sw"), ()),
    "rock_quality": (("phie", "sw"), ()),
    "electrofacies": ((), ("GR", "RHOB", "NPHI")),
    "lithology": ((), ("RHOB", "NPHI")),
}

# Dependency graph (property -> the properties it directly depends on), for recompute invalidation.
DEPENDENCIES: dict[str, tuple[str, ...]] = {
    "phie": ("vsh",),
    "sw": ("phie",),
    "netpay": ("sw",),
    "uncertainty": ("netpay",),
    "permeability": ("phie", "sw"),
    "rock_quality": ("phie", "sw"),
}

# Observation actions (read-only): the property/curve they need to be meaningful.
_OBSERVE_NEEDS: dict[str, tuple[str, ...]] = {
    "zone_stats": ("netpay",),
    "percentiles": (),  # target chosen at call time (a present curve or computed property)
    "value_at": (),
    "extremes": (),
    "histogram": (),
    "crossplot": ("__curves__:RHOB,NPHI",),
    "low_res_scan": ("__curves__:RT",),
}


def available_actions(valid: set[str], curves: set[str]) -> list[str]:
    """Return the action ids valid right now (compute + observation + FINISH).

    Args:
        valid: properties already computed AND not stale (e.g. {"vsh", "phie"}).
        curves: canonical curves present in the well.

    Returns:
        Sorted-by-category list of available action ids; always includes ``finish``.
    """
    actions: list[str] = []
    for action, (deps, need_curves) in _REQUIRES.items():
        if all(d in valid for d in deps) and all(c in curves for c in need_curves):
            actions.append(action)
    # observation actions
    for obs, needs in _OBSERVE_NEEDS.items():
        ok = True
        for need in needs:
            if need.startswith("__curves__:"):
                ok = ok and all(c in curves for c in need.split(":", 1)[1].split(","))
            else:
                ok = ok and need in valid
        if ok:
            actions.append(obs)
    actions.append("finish")
    return actions


def invalidate_downstream(valid: set[str], prop: str) -> set[str]:
    """Return ``valid`` with every (transitive) dependent of ``prop`` removed (recompute staleness).

    Recomputing ``prop`` makes everything that depends on it stale until recomputed. The recomputed
    property itself stays valid; its transitive dependents drop out.
    """
    stale: set[str] = set()
    frontier = [prop]
    while frontier:
        cur = frontier.pop()
        for dependent, deps in DEPENDENCIES.items():
            if cur in deps and dependent not in stale:
                stale.add(dependent)
                frontier.append(dependent)
    return set(valid) - stale
