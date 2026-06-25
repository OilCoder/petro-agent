"""Deterministic LangGraph orchestrator: owns the compute→validate→correct loop.

The orchestrator is a deterministic state machine, never an LLM (Charter Invariant 2).
It owns the loop, the gating compuertas, and the termination/circuit-breaker logic.
"""
