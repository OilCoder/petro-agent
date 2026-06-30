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
# Transient upstream conditions on free model pools — retried with backoff (not hard failures).
OPENROUTER_RETRY_STATUS = frozenset({429, 502, 503})
OPENROUTER_BACKOFFS = (2.0, 5.0, 10.0, 20.0)


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
    by running the same loop with a frontier model. Transient upstream conditions
    (429/502/503, transport errors) are retried with backoff; persistent infra
    failures and hard errors (e.g. 401/404) raise loudly so they are never
    mistaken for model incapability. Only a genuine empty completion returns
    ``""`` (flows into the agent's empty→fallback cascade and is recorded
    honestly). ``seed``/``temperature`` are best-effort on cloud providers.

    Raises:
        RuntimeError: If the API key is unset, a hard error is returned, or the
            retries are exhausted on transient conditions.
    """
    import time

    import httpx

    api_key = os.environ.get(OPENROUTER_API_KEY_ENV)
    if not api_key:
        raise RuntimeError(f"{OPENROUTER_API_KEY_ENV} is unset (OpenRouter backend)")

    def chat(system: str, user: str) -> str:
        last = ""
        for attempt in range(len(OPENROUTER_BACKOFFS) + 1):
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
                    timeout=180.0,
                )
            except httpx.HTTPError as e:  # transport: transient infra, retry
                last = f"transport: {e}"
            else:
                if resp.status_code == 200:
                    data = resp.json()
                    choices = data.get("choices")
                    if choices:
                        return str(choices[0]["message"].get("content") or "")
                    # 200 carrying an error envelope (flaky free pool) — transient, retry
                    last = f"200 without choices: {str(data)[:200]}"
                elif resp.status_code not in OPENROUTER_RETRY_STATUS:
                    raise RuntimeError(f"OpenRouter HTTP {resp.status_code}: {resp.text[:200]}")
                else:
                    last = f"HTTP {resp.status_code}: {resp.text[:200]}"
            if attempt < len(OPENROUTER_BACKOFFS):
                time.sleep(OPENROUTER_BACKOFFS[attempt])
        raise RuntimeError(f"OpenRouter exhausted retries ({last})")

    return chat
