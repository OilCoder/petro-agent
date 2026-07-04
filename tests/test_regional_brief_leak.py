"""GA-5 mechanical leak gate: the regional brief is DATA, never direction.

Permanent CI gate — any future edit of the brief that introduces a method id, a loop
action id, or a directed imperative breaks this test. Bare-word action ids that are
ordinary geology vocabulary (lithology, permeability, histogram, …) are exempt from the
id ban because banning English domain nouns would not reduce direction risk; directing
language is what leaks, and the imperative gate covers it.
"""

import re
from pathlib import Path

from src.agents.loop_actions import _OBSERVE_NEEDS, PRODUCES
from src.params.config_loader import load_regional_brief
from src.petrophysics.registry import METHOD_REGISTRY

BRIEF = load_regional_brief()

# Unambiguous system tokens: every underscore-bearing id is a machine name, never prose.
_SYSTEM_IDS = [
    tok
    for tok in (
        list(METHOD_REGISTRY)
        + list(PRODUCES)
        + list(_OBSERVE_NEEDS)
        + ["set_zone_of_interest", "zone_of_interest"]
    )
    if "_" in tok
]

# Directed imperatives: the brief must never tell the analyst what to do.
_IMPERATIVES = re.compile(
    r"\b(choose|select|restrict|use|set|compute|apply|pick|run|prefer|avoid)\s+(the|a|an|this|your)\b"
    r"|\byou\s+(should|must|need\s+to|have\s+to)\b",
    re.IGNORECASE,
)


def test_brief_exists_and_is_nonempty():
    assert Path("src/params/regional_brief_kansas.md").exists()
    assert len(BRIEF) > 500


def test_brief_contains_no_system_ids():
    assert _SYSTEM_IDS  # the gate is real: the lists resolved to actual ids
    hits = [tok for tok in _SYSTEM_IDS if tok in BRIEF]
    assert hits == [], f"system ids leaked into the brief: {hits}"


def test_brief_contains_no_directed_imperatives():
    hits = _IMPERATIVES.findall(BRIEF)
    assert not hits, f"directed imperatives in the brief: {hits}"


def test_brief_marks_unverified_claims():
    # honesty contract: lease-level specifics the project has not verified say so
    assert "por confirmar" in BRIEF or "unverified" in BRIEF


def test_brief_carries_identity_but_no_technical_field_specs():
    # GB-3 user rule: naming the field is OK; technical specifications of it are NOT.
    assert "Schaben" in BRIEF and "Ness County" in BRIEF
    banned = ("Mississippian", "dolomit", "limestone", "chert", "brine", "salinit", "Osagian")
    hits = [t for t in banned if t.lower() in BRIEF.lower()]
    assert hits == [], f"technical field specs leaked into the brief: {hits}"
