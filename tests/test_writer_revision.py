"""GD draft-revise loop: the writer rereads its OWN rendered draft; the claim verifier
mechanically rejects any revision that introduces an unledgered number."""

import json
import os

from src.agents.analyst_loop import run_analyst_loop
from src.agents.writer import revise_narrative
from src.orchestrator.finalize import finalize_run
from src.orchestrator.graph import run_descriptive_pass

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "synthetic_oldrocks.las")

_SCRIPT = [
    {"action": "compute_vsh", "method": "vsh_linear"},
    {"action": "compute_phie"},
    {"action": "compute_sw"},
    {"action": "apply_cutoffs"},
    {"action": "run_uncertainty"},
    {"action": "finish"},
]


def _completed_ledger(tmp_path):
    ledger, ctx = run_descriptive_pass(FIXTURE, out_dir=str(tmp_path))

    def chat(system, user):
        if "SKEPTICAL" in system:
            return json.dumps({"objections": []})
        if "field notebook" in system:
            return "note"
        try:
            return json.dumps(next(it))
        except StopIteration:
            return json.dumps({"action": "finish"})

    it = iter(_SCRIPT)
    run_analyst_loop(ledger, ctx, "free", chat, "fake", max_steps=16, author=True)
    finalize_run(ledger, ctx)
    return ledger


def _render(narrative):
    return f"# DRAFT\n\n{narrative['executive_summary']}\n\n{narrative['conclusions']}\n"


def test_clean_revision_is_accepted_and_recorded(tmp_path):
    ledger = _completed_ledger(tmp_path)
    seen: list[str] = []

    def chat(system, user):
        seen.append(user)
        return json.dumps(
            {
                "executive_summary": "The interval reads as a bracketed range, not a point.",
                "conclusions": "Core calibration is the highest-leverage next step.",
            }
        )

    first = {"executive_summary": "draft one.", "conclusions": "draft one conclusions."}
    final = revise_narrative(ledger, _render, first, chat, max_rounds=2)
    assert final["executive_summary"].startswith("The interval reads")
    stats = ledger["run"]["report_revisions"]
    assert stats["revised"] >= 1 and stats["rejected"] == 0
    # the writer actually saw its OWN rendered draft
    assert any("YOUR CURRENT DRAFT" in u and "draft one." in u for u in seen)


def test_revision_with_unledgered_number_is_rejected(tmp_path):
    ledger = _completed_ledger(tmp_path)

    def chat(system, user):
        return json.dumps(
            {
                "executive_summary": "Porosity averages 0.777 across the pay.",  # invented
                "conclusions": "ok.",
            }
        )

    first = {"executive_summary": "honest draft.", "conclusions": "honest conclusions."}
    final = revise_narrative(ledger, _render, first, chat, max_rounds=2)
    assert final == first  # the invented number never ships
    stats = ledger["run"]["report_revisions"]
    assert stats["rejected"] == 1 and stats["revised"] == 0


def test_unchanged_draft_stops_the_loop(tmp_path):
    ledger = _completed_ledger(tmp_path)
    first = {"executive_summary": "stable.", "conclusions": "stable c."}

    def chat(system, user):
        return json.dumps(first)

    final = revise_narrative(ledger, _render, first, chat, max_rounds=3)
    assert final == first
    stats = ledger["run"]["report_revisions"]
    assert stats["unchanged"] == 1 and stats["rounds"] == 1
