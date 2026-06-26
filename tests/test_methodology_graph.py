"""Tests for the methodology graph (V2-B)."""

from src.agents.methodology_graph import MethodologyGraph


def _valid_graph() -> MethodologyGraph:
    g = MethodologyGraph(mode="free", model="qwen3:30b-a3b", model_digest="sha256:ab")
    obs = g.add(
        "observation",
        {
            "tool": "model_mismatch_nd",
            "finding": "dirty rock",
            "source_ledger_key": "ledger:eda.litho",
        },
    )
    dec = g.add(
        "decision",
        {"rationale": "dirty rock so Simandoux beats Archie", "chosen": "sw_simandoux"},
        depends_on=(obs,),
    )
    act = g.add(
        "tool_call",
        {
            "tool": "sw_simandoux",
            "args": {"electrical_preset": "carbonate_default"},
            "result_ledger_key": "ledger:sw_simandoux",
            "result_hash": "x",
        },
        depends_on=(dec,),
    )
    g.add("section", {"section_id": "shaly_sand_saturation"}, depends_on=(act,))
    return g


def test_add_generates_prefixed_ids():
    g = _valid_graph()
    ids = [n.id for n in g.nodes]
    assert ids == ["obs_1", "dec_1", "act_1", "sec_1"]


def test_valid_graph_passes():
    g = _valid_graph()
    assert g.validate({"sw_simandoux": 0.3}) == []


def test_validate_flags_missing_dep():
    g = MethodologyGraph(mode="free", model="m")
    g.add("decision", {"rationale": "x"}, depends_on=("nope",))
    assert any("missing" in i for i in g.validate())


def test_validate_flags_numeric_literal_in_rationale():
    g = MethodologyGraph(mode="free", model="m")
    g.add("decision", {"rationale": "Sw is 0.33 so it is pay"})  # LLM embedded a number
    issues = g.validate()
    assert any("numeric literal" in i for i in issues)


def test_validate_allows_integer_counts_in_text():
    g = MethodologyGraph(mode="free", model="m")
    g.add("decision", {"rationale": "3 low-resistivity intervals warrant a Pickett"})
    assert g.validate() == []  # integers (counts) are fine; only decimals flagged


def test_validate_flags_unresolved_ledger_key():
    g = MethodologyGraph(mode="free", model="m")
    act = g.add("tool_call", {"tool": "t", "result_ledger_key": "ledger:ghost"})
    assert any("not in ledger" in i for i in g.validate({"other": 1}))
    assert act == "act_1"


def test_to_mermaid_and_json():
    g = _valid_graph()
    assert "flowchart TD" in g.to_mermaid()
    j = g.to_json()
    assert j["mode"] == "free" and len(j["nodes"]) == 4
