"""Chat client wrappers with pinned, deterministic decoding.

Returns a ``chat(system, user) -> str`` callable. Agents take this callable by
dependency injection so unit tests can pass a fake (no model needed).

Two backends share the ``ChatFn`` contract:
- **Ollama** (local) — the report-product runtime.
- **OpenRouter** (cloud, OpenAI-compatible) — a *ceiling-control measurement
  instrument* only, never the report runtime. Selected when the model id looks
  like ``vendor/model`` (or ``backend="openrouter"``).
"""

from __future__ import annotations

import os
from collections.abc import Callable

VERSION = "0.1.0"

ChatFn = Callable[[str, str], str]

WRITER_MODEL = "qwen3:30b-a3b"
REVIEWER_MODEL = "llama3.1:8b"

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_API_KEY_ENV = "OPENROUTER_API_KEY"


def make_chat(
    model: str = WRITER_MODEL,
    host: str | None = None,
    seed: int = 42,
    backend: str = "auto",
) -> ChatFn:
    """Build a deterministic ``chat(system, user) -> str`` callable.

    Args:
        model: Model id. Ollama tag (``qwen3:30b-a3b``) or OpenRouter
            ``vendor/model`` id (``deepseek/deepseek-r1:free``).
        host: Ollama host override (ignored for the OpenRouter backend).
        seed: Decoding seed (best-effort on cloud providers).
        backend: ``"auto"`` (route to OpenRouter when ``"/"`` is in ``model``,
            else Ollama), or force ``"ollama"`` / ``"openrouter"``.

    Returns:
        A ChatFn closure over the chosen backend.

    Raises:
        ValueError: If ``backend`` is not one of auto/ollama/openrouter.
    """
    if backend == "auto":
        backend = "openrouter" if "/" in model else "ollama"
    if backend == "ollama":
        return _make_ollama_chat(model, host, seed)
    if backend == "openrouter":
        return _make_openrouter_chat(model, seed)
    raise ValueError(f"unknown backend: {backend!r}")


def _make_ollama_chat(model: str, host: str | None, seed: int) -> ChatFn:
    """Build a ChatFn backed by a local Ollama model (the report runtime)."""
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


def _make_openrouter_chat(model: str, seed: int) -> ChatFn:
    """Build a ChatFn backed by OpenRouter — a ceiling-control instrument only.

    Cloud is never the report runtime; it answers "is it the flow or the model?"
    by running the same loop with a frontier model. Infra failures (non-200,
    transport) raise loudly so they are never mistaken for model incapability;
    only a genuine empty completion returns ``""`` (flows into the agent's
    empty→fallback cascade and is recorded honestly).

    Raises:
        RuntimeError: If the API key is unset, or the request fails / non-200.
    """
    import httpx

    api_key = os.environ.get(OPENROUTER_API_KEY_ENV)
    if not api_key:
        raise RuntimeError(f"{OPENROUTER_API_KEY_ENV} is unset (OpenRouter backend)")

    def chat(system: str, user: str) -> str:
        try:
            resp = httpx.post(
                OPENROUTER_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "temperature": 0.0,
                    "seed": seed,
                },
                timeout=120.0,
            )
        except httpx.HTTPError as e:  # transport: infra failure, not model incapability
            raise RuntimeError(f"OpenRouter request failed: {e}") from e
        if resp.status_code != 200:
            raise RuntimeError(f"OpenRouter HTTP {resp.status_code}: {resp.text[:200]}")
        content = resp.json()["choices"][0]["message"]["content"]
        return str(content or "")

    return chat
