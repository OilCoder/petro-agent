"""Ollama chat client wrapper with pinned, deterministic decoding.

Returns a ``chat(system, user) -> str`` callable. Agents take this callable by
dependency injection so unit tests can pass a fake (no model needed).
"""

from __future__ import annotations

import os
from collections.abc import Callable

VERSION = "0.1.0"

ChatFn = Callable[[str, str], str]

WRITER_MODEL = "qwen3:30b-a3b"
REVIEWER_MODEL = "llama3.1:8b"


def make_chat(
    model: str = WRITER_MODEL,
    host: str | None = None,
    seed: int = 42,
) -> ChatFn:
    """Build a deterministic chat callable backed by a local Ollama model."""
    import ollama

    client = ollama.Client(host=host or os.environ.get("OLLAMA_HOST", "127.0.0.1:11434"))

    def chat(system: str, user: str) -> str:
        resp = client.chat(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            options={"seed": seed, "temperature": 0.0},
        )
        return str(resp["message"]["content"])

    return chat
