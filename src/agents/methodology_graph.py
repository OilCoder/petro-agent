"""The methodology graph: the agent's auditable chain of thought (v2).

A typed DAG (observation -> decision -> tool_call -> section) that records what the agent
explored, decided, executed, and added. Persisted in the ledger, rendered in the report.
The LLM only authors ``decision`` nodes (text rationale, never numbers); the dispatcher
writes ``observation``/``tool_call`` (number + hash). ``validate`` is a deterministic gate:
it rejects cycles, dangling deps, unresolved ledger keys, and loose numeric literals in the
agent's reasoning text — keeping the invariant (the LLM never produces a digit).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

VERSION = "0.1.0"

NODE_TYPES = ("observation", "decision", "tool_call", "section")
_DECIMAL_IN_TEXT = re.compile(r"(?<![\w:])\d+\.\d+")  # a computed-looking value in prose
_MERMAID_BREAKING = re.compile(r'["\[\]]')  # chars that break a Mermaid quoted node label


def _mermaid_label(text: str, limit: int = 60) -> str:
    """Sanitize and word-boundary-truncate a node label for a Mermaid quoted string."""
    safe = " ".join(_MERMAID_BREAKING.sub("", text).split())
    if len(safe) > limit:
        safe = safe[:limit].rsplit(" ", 1)[0] + "…"
    return safe


@dataclass(frozen=True)
class GraphNode:
    """One node of the methodology graph."""

    id: str
    type: str
    depends_on: tuple[str, ...]
    payload: dict[str, Any]

    def __post_init__(self) -> None:
        if self.type not in NODE_TYPES:
            raise ValueError(f"unknown node type: {self.type!r}")


@dataclass
class MethodologyGraph:
    """The agent's decision DAG for one report."""

    mode: str  # "guided" | "free"
    model: str
    model_digest: str = ""
    nodes: list[GraphNode] = field(default_factory=list)
    _counter: dict[str, int] = field(default_factory=dict)

    _PREFIX = {"observation": "obs", "decision": "dec", "tool_call": "act", "section": "sec"}

    def add(self, type: str, payload: dict[str, Any], depends_on: tuple[str, ...] = ()) -> str:
        """Append a node and return its generated id (obs_/dec_/act_/sec_ + counter)."""
        prefix = self._PREFIX[type]
        self._counter[prefix] = self._counter.get(prefix, 0) + 1
        node_id = f"{prefix}_{self._counter[prefix]}"
        self.nodes.append(GraphNode(node_id, type, tuple(depends_on), payload))
        return node_id

    def to_json(self) -> dict[str, Any]:
        """Serialize to the ledger-stored dict."""
        return {
            "mode": self.mode,
            "model": self.model,
            "model_digest": self.model_digest,
            "nodes": [
                {"id": n.id, "type": n.type, "depends_on": list(n.depends_on), "payload": n.payload}
                for n in self.nodes
            ],
        }

    def to_mermaid(self) -> str:
        """Render a Mermaid flowchart of the decision graph for the report."""
        lines = ["```mermaid", "flowchart TD"]
        for n in self.nodes:
            label = (
                n.payload.get("rationale")
                or n.payload.get("finding")
                or n.payload.get("tool")
                or n.payload.get("section_id")
                or n.type
            )
            lines.append(f'    {n.id}["{n.type}: {_mermaid_label(str(label))}"]')
            for dep in n.depends_on:
                lines.append(f"    {dep} --> {n.id}")
        lines.append("```")
        return "\n".join(lines)

    def validate(self, ledger: dict[str, Any] | None = None) -> list[str]:
        """Return a list of issues (empty = valid). A non-empty result is a MECHANICAL gate.

        Checks: unique ids, deps exist, acyclic, tool_call result keys resolve in the ledger,
        and NO loose decimal literal in decision/observation prose (the LLM must reference a
        ledger key, never embed a computed number).
        """
        issues: list[str] = []
        ids = [n.id for n in self.nodes]
        if len(ids) != len(set(ids)):
            issues.append("duplicate node ids")
        idset = set(ids)
        for n in self.nodes:
            for dep in n.depends_on:
                if dep not in idset:
                    issues.append(f"{n.id} depends on missing node {dep}")
        issues += self._acyclic_issues()
        issues += self._numeric_literal_issues()
        if ledger is not None:
            issues += self._ledger_key_issues(ledger)
        return issues

    def _acyclic_issues(self) -> list[str]:
        graph = {n.id: set(n.depends_on) for n in self.nodes}
        visited: set[str] = set()
        stack: set[str] = set()

        def walk(node: str) -> bool:
            visited.add(node)
            stack.add(node)
            for dep in graph.get(node, ()):
                if dep not in visited and walk(dep):
                    return True
                if dep in stack:
                    return True
            stack.discard(node)
            return False

        for nid in graph:
            if nid not in visited and walk(nid):
                return ["graph has a cycle"]
        return []

    def _numeric_literal_issues(self) -> list[str]:
        issues: list[str] = []
        for n in self.nodes:
            if n.type in ("decision", "observation"):
                for key in ("rationale", "finding"):
                    text = str(n.payload.get(key, ""))
                    if _DECIMAL_IN_TEXT.search(text):
                        issues.append(
                            f"{n.id}: numeric literal in '{key}' (reference a ledger key)"
                        )
        return issues

    def _ledger_key_issues(self, ledger: dict[str, Any]) -> list[str]:
        issues: list[str] = []
        for n in self.nodes:
            if n.type == "tool_call":
                key = n.payload.get("result_ledger_key", "")
                ref = str(key).removeprefix("ledger:")
                if ref and ref not in ledger:
                    issues.append(f"{n.id}: result_ledger_key '{key}' not in ledger")
        return issues
