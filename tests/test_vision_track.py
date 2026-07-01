"""Vision ceiling track: examine_figures is offered only to vision-capable runs, reads figures
QUALITATIVELY (never a number off a plot), and degrades safely when no vision backend is wired.
"""

from src.agents.loop_actions import available_actions, observe


def test_examine_figures_offered_only_with_vision():
    curves = {"GR", "RHOB", "NPHI", "RT"}
    assert "examine_figures" not in available_actions({"vsh"}, curves, vision=False)
    assert "examine_figures" in available_actions({"vsh"}, curves, vision=True)


def test_examine_figures_reads_qualitatively_via_vision_chat():
    seen: dict[str, object] = {}

    def fake_vision(system: str, user: str, image_paths: list[str]) -> str:
        seen["system"] = system
        seen["images"] = image_paths
        return "Density-neutron shows a limestone-to-dolomite trend; logs clean, no washouts."

    ctx = {"vision_chat": fake_vision, "figure_paths": ["/tmp/a.png", "/tmp/b.png"]}
    out = observe("examine_figures", ctx, {})

    assert "dolomite" in out["qualitative_reading"]
    assert seen["images"] == ["/tmp/a.png", "/tmp/b.png"]
    # the guardrail must forbid reading numbers off a plot (invariant guard)
    assert "NEVER" in str(seen["system"]) and "number" in str(seen["system"]).lower()


def test_examine_figures_without_vision_backend_degrades_safely():
    out = observe("examine_figures", {}, {})
    assert "note" in out and "qualitative_reading" not in out
